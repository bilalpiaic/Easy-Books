# Dynamic Reporting Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a user-configurable report builder over curated single-source datasets — column chooser, click-to-filter, grouping + totals, saved reports, and CSV/XLSX export — that is multi-tenant safe by construction.

**Architecture:** A declarative data-source **registry** (Python, the security boundary) whitelists queryable columns per source. A pure-logic **engine** turns a validated `ReportConfig` into a tenant-scoped, read-only SQLModel `select()` with DB-side filter/group/aggregate + pagination. Thin FastAPI routers expose `/sources`, `/run`, `/reports` CRUD, `/export`. A metadata-driven React `<ReportGrid>` renders any source with no per-source code.

**Tech Stack:** FastAPI, SQLModel, SQLAlchemy, Alembic, pytest (backend); Next.js 16 / React 19 / TS (frontend). `openpyxl` for XLSX. Spec: `docs/superpowers/specs/2026-06-03-dynamic-reporting-framework-design.md`.

---

## Conventions (read once)

- **Branch:** work on `feature/dynamic-reporting-framework` (already created off `main`; the spec is committed there as `a44c4ee`).
- **Deps:** `SessionDep = Annotated[Session, Depends(get_session)]`, `CurrentUserDep` (any authed user), `WriteUserDep` (accountant+) — all from `routers/common.py`. `get_or_create_account` lives there too.
- **Tests:** pytest with the `client` fixture (in-memory SQLite, auto-creates tables) from `tests/conftest.py`. Use this `_auth` helper verbatim and a fresh email per test file:
  ```python
  def _auth(client):
      client.post("/api/auth/signup", json={"email": "rb@rb.test", "password": "password123",
                                             "full_name": "U", "company_name": "RB Co"})
      r = client.post("/api/auth/login", data={"username": "rb@rb.test", "password": "password123"})
      return {"Authorization": f"Bearer {r.json()['access_token']}"}
  ```
  Signup base currency is **USD**. To touch the DB directly: `with Session(app.state.engine) as s:`.
- **Run one test:** `cd backend && uv run pytest tests/<file>::<test> -v`. Full suite: `uv run pytest`.
- **Money:** money columns deserialize to `Decimal`; **serialize to the API as `str`** (repo convention). Use `Decimal` server-side.
- **Migrations:** `cd backend && uv run alembic revision -m "report_definition"`, hand-write the upgrade, guard new tables with `if not bind.dialect.has_table(bind, "reportdefinition"):`, set `down_revision = "aa01prodcat"` (current head — confirm with `uv run alembic heads`). Then `uv run alembic upgrade head`.
- **Router registration:** add `report_builder` to the `from routers import (...)` block and the `_ROUTERS` list in `main.py`.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Frontend gate (no jest):** after each frontend task run `npm run lint` and `npx tsc --noEmit` and `npm run build`; all must be clean. Use `apiFetch` (auto-injects auth), `useFmt`/`useSettings` for money, and reuse `SortableHeader` (props: `label, field, sortBy, sortDir, onSort, className`). Check `node_modules/next/dist/docs/` + `frontend/AGENTS.md` before writing App-Router code.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/services/report_sources/__init__.py` | dataclasses (`FieldType`, `FieldDef`, `JoinPath`, `ReportSource`) + `REGISTRY` (all v1 sources) — the whitelist |
| `backend/services/report_engine.py` | `ReportConfig` Pydantic models + `run_report()` query builder + helpers (`build_predicate`, `coerce`, `apply_date_range`, `agg_expr`) |
| `backend/models.py` | add `ReportDefinition` table |
| `backend/alembic/versions/<rev>_report_definition.py` | guarded table migration |
| `backend/routers/report_builder.py` | `/sources`, `/run`, `/reports` CRUD, `/export` |
| `backend/main.py` | register router |
| `backend/tests/test_report_engine.py` | engine units |
| `backend/tests/test_report_builder_safety.py` | safety + tenant isolation |
| `backend/tests/test_report_builder_run.py` | run integration |
| `backend/tests/test_report_builder_reports.py` | saved CRUD |
| `backend/tests/test_report_builder_export.py` | export |
| `frontend/src/lib/reportTypes.ts` | shared TS types for sources/config/result |
| `frontend/src/components/report-builder/*.tsx` | `ReportGrid`, `ColumnChooser`, `FilterBar`, `GroupByPicker`, `SavedReportsMenu`, `ExportMenu` |
| `frontend/src/app/(dashboard)/reports/builder/page.tsx` | orchestration page |
| `frontend/src/components/Sidebar.tsx` | add Report Builder nav entry |

---

## Phase 1 — Registry + Engine (backend, no HTTP)

### Task 1.1: Registry dataclasses + first sources

**Files:**
- Create: `backend/services/report_sources/__init__.py`

- [ ] **Step 1: Write the dataclasses + Invoices/Bills/Journal sources**

```python
"""Declarative report data-source registry — the security boundary.

User report configs reference only the string `key`s defined here; the engine
resolves them to real SQLModel columns. An unknown key is a 400, never a query.
`tenant_id` is intentionally NOT a field on any source — the engine injects it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sqlalchemy.orm.attributes import InstrumentedAttribute

from models import (Account, Bill, BillPayment, Customer, Invoice, JournalEntry,
                    PaymentReceived, Product, StockMovement, Transaction, Vendor)


class FieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    MONEY = "money"
    DATE = "date"
    ENUM = "enum"
    BOOL = "bool"


# Operators allowed per field type (also enforced server-side in the engine).
OPS_BY_TYPE: dict[FieldType, list[str]] = {
    FieldType.TEXT:   ["equals", "contains", "starts_with", "in"],
    FieldType.NUMBER: ["equals", "gt", "gte", "lt", "lte", "between"],
    FieldType.MONEY:  ["equals", "gt", "gte", "lt", "lte", "between"],
    FieldType.DATE:   ["equals", "before", "after", "between"],
    FieldType.ENUM:   ["equals", "in"],
    FieldType.BOOL:   ["equals"],
}


@dataclass(frozen=True)
class JoinPath:
    local: InstrumentedAttribute   # e.g. Invoice.customer_id
    target: type                   # e.g. Customer (SQLModel table)
    target_key: InstrumentedAttribute  # e.g. Customer.id


@dataclass(frozen=True)
class FieldDef:
    key: str
    label: str
    type: FieldType
    column: InstrumentedAttribute
    join: Optional[JoinPath] = None
    enum_values: Optional[list[str]] = None
    aggregatable: bool = False
    groupable: bool = True


@dataclass(frozen=True)
class ReportSource:
    key: str
    label: str
    model: type
    fields: dict[str, FieldDef]
    default_columns: list[str]
    date_field: Optional[str] = None

    def field(self, key: str) -> FieldDef:
        try:
            return self.fields[key]
        except KeyError:
            raise KeyError(key)  # router converts to HTTP 400


def _f(key, label, type_, column, **kw) -> FieldDef:
    return FieldDef(key=key, label=label, type=type_, column=column, **kw)


INVOICES = ReportSource(
    key="invoices", label="Invoices", model=Invoice, date_field="issue_date",
    default_columns=["number", "customer_name", "issue_date", "status", "total"],
    fields={
        "number":        _f("number", "Invoice #", FieldType.TEXT, Invoice.number),
        "customer_name": _f("customer_name", "Customer", FieldType.TEXT, Invoice.customer_name),
        "customer_region": _f("customer_region", "Region", FieldType.TEXT, Customer.region,
                              join=JoinPath(Invoice.customer_id, Customer, Customer.id)),
        "issue_date":    _f("issue_date", "Issue Date", FieldType.DATE, Invoice.issue_date),
        "due_date":      _f("due_date", "Due Date", FieldType.DATE, Invoice.due_date),
        "status":        _f("status", "Status", FieldType.ENUM, Invoice.status,
                            enum_values=["draft", "sent", "posted", "partial", "paid"]),
        "currency":      _f("currency", "Currency", FieldType.TEXT, Invoice.currency),
        "subtotal":      _f("subtotal", "Subtotal", FieldType.MONEY, Invoice.subtotal, aggregatable=True),
        "gst_amount":    _f("gst_amount", "Tax", FieldType.MONEY, Invoice.gst_amount, aggregatable=True),
        "total":         _f("total", "Total", FieldType.MONEY, Invoice.total, aggregatable=True),
    },
)

BILLS = ReportSource(
    key="bills", label="Bills", model=Bill, date_field="bill_date",
    default_columns=["number", "vendor_name", "bill_date", "status", "total"],
    fields={
        "number":      _f("number", "Bill #", FieldType.TEXT, Bill.number),
        "vendor_name": _f("vendor_name", "Vendor", FieldType.TEXT, Bill.vendor_name),
        "bill_date":   _f("bill_date", "Bill Date", FieldType.DATE, Bill.bill_date),
        "due_date":    _f("due_date", "Due Date", FieldType.DATE, Bill.due_date),
        "status":      _f("status", "Status", FieldType.ENUM, Bill.status,
                          enum_values=["draft", "posted", "partial", "paid"]),
        "currency":    _f("currency", "Currency", FieldType.TEXT, Bill.currency),
        "subtotal":    _f("subtotal", "Subtotal", FieldType.MONEY, Bill.subtotal, aggregatable=True),
        "gst_amount":  _f("gst_amount", "Tax", FieldType.MONEY, Bill.gst_amount, aggregatable=True),
        "total":       _f("total", "Total", FieldType.MONEY, Bill.total, aggregatable=True),
    },
)

JOURNAL_LINES = ReportSource(
    key="journal_lines", label="Journal Entry Lines", model=JournalEntry, date_field="date",
    default_columns=["date", "account_code", "account_name", "debit", "credit"],
    fields={
        "date":         _f("date", "Date", FieldType.DATE, Transaction.date,
                           join=JoinPath(JournalEntry.transaction_id, Transaction, Transaction.id)),
        "jv_number":    _f("jv_number", "JV #", FieldType.TEXT, Transaction.jv_number,
                           join=JoinPath(JournalEntry.transaction_id, Transaction, Transaction.id)),
        "account_code": _f("account_code", "Account Code", FieldType.TEXT, Account.code,
                           join=JoinPath(JournalEntry.account_id, Account, Account.id)),
        "account_name": _f("account_name", "Account", FieldType.TEXT, Account.name,
                           join=JoinPath(JournalEntry.account_id, Account, Account.id)),
        "account_type": _f("account_type", "Type", FieldType.TEXT, Account.type,
                           join=JoinPath(JournalEntry.account_id, Account, Account.id)),
        "debit":        _f("debit", "Debit", FieldType.MONEY, JournalEntry.debit, aggregatable=True),
        "credit":       _f("credit", "Credit", FieldType.MONEY, JournalEntry.credit, aggregatable=True),
    },
)
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd backend && uv run python -c "from services.report_sources import INVOICES, BILLS, JOURNAL_LINES; print(len(INVOICES.fields), 'invoice fields')"`
Expected: prints `10 invoice fields`, no import error.

> NOTE: confirm `Account.type`, `Transaction.jv_number`, `Customer.region` exist (verified in `models.py` at design time). If `Customer.region` is absent, drop the `customer_region` field — it is the only optional one.

- [ ] **Step 3: Commit**

```bash
git add backend/services/report_sources/__init__.py
git commit -m "feat(reports): report-source registry + Invoices/Bills/Journal sources

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.2: Remaining v1 sources + REGISTRY

**Files:**
- Modify: `backend/services/report_sources/__init__.py`

- [ ] **Step 1: Append the remaining sources and the REGISTRY dict** (end of file)

```python
PAYMENTS_RECEIVED = ReportSource(
    key="payments_received", label="Payments Received", model=PaymentReceived, date_field="payment_date",
    default_columns=["payment_date", "customer_name", "method", "amount"],
    fields={
        "payment_date":  _f("payment_date", "Date", FieldType.DATE, PaymentReceived.payment_date),
        "customer_name": _f("customer_name", "Customer", FieldType.TEXT, PaymentReceived.customer_name),
        "method":        _f("method", "Method", FieldType.ENUM, PaymentReceived.method,
                            enum_values=["cash", "bank", "card", "cheque"]),
        "reference":     _f("reference", "Reference", FieldType.TEXT, PaymentReceived.reference),
        "amount":        _f("amount", "Amount", FieldType.MONEY, PaymentReceived.amount, aggregatable=True),
    },
)

PAYMENTS_MADE = ReportSource(
    key="payments_made", label="Payments Made", model=BillPayment, date_field="payment_date",
    default_columns=["payment_date", "vendor_name", "method", "amount"],
    fields={
        "payment_date": _f("payment_date", "Date", FieldType.DATE, BillPayment.payment_date),
        "vendor_name":  _f("vendor_name", "Vendor", FieldType.TEXT, BillPayment.vendor_name),
        "method":       _f("method", "Method", FieldType.ENUM, BillPayment.method,
                           enum_values=["cash", "bank", "card", "cheque"]),
        "reference":    _f("reference", "Reference", FieldType.TEXT, BillPayment.reference),
        "amount":       _f("amount", "Amount", FieldType.MONEY, BillPayment.amount, aggregatable=True),
    },
)

PRODUCTS = ReportSource(
    key="products", label="Products", model=Product, date_field=None,
    default_columns=["sku", "name", "stock_qty", "sale_price"],
    fields={
        "sku":        _f("sku", "SKU", FieldType.TEXT, Product.sku),
        "name":       _f("name", "Name", FieldType.TEXT, Product.name),
        "stock_qty":  _f("stock_qty", "On Hand", FieldType.NUMBER, Product.stock_qty, aggregatable=True),
        "sale_price": _f("sale_price", "Sale Price", FieldType.MONEY, Product.sale_price, aggregatable=True),
        "cost_price": _f("cost_price", "Cost", FieldType.MONEY, Product.cost_price, aggregatable=True),
    },
)

STOCK_MOVEMENTS = ReportSource(
    key="stock_movements", label="Stock Movements", model=StockMovement, date_field="date",
    default_columns=["date", "product_id", "kind", "qty", "unit_cost"],
    fields={
        "date":       _f("date", "Date", FieldType.DATE, StockMovement.date),
        "product_id": _f("product_id", "Product ID", FieldType.NUMBER, StockMovement.product_id),
        "kind":       _f("kind", "Kind", FieldType.TEXT, StockMovement.kind),
        "qty":        _f("qty", "Qty", FieldType.NUMBER, StockMovement.qty, aggregatable=True),
        "unit_cost":  _f("unit_cost", "Unit Cost", FieldType.MONEY, StockMovement.unit_cost, aggregatable=True),
    },
)

CUSTOMERS = ReportSource(
    key="customers", label="Customers", model=Customer, date_field=None,
    default_columns=["name", "email", "phone"],
    fields={
        "name":  _f("name", "Name", FieldType.TEXT, Customer.name),
        "email": _f("email", "Email", FieldType.TEXT, Customer.email),
        "phone": _f("phone", "Phone", FieldType.TEXT, Customer.phone),
    },
)

VENDORS = ReportSource(
    key="vendors", label="Vendors", model=Vendor, date_field=None,
    default_columns=["name", "email", "phone"],
    fields={
        "name":  _f("name", "Name", FieldType.TEXT, Vendor.name),
        "email": _f("email", "Email", FieldType.TEXT, Vendor.email),
        "phone": _f("phone", "Phone", FieldType.TEXT, Vendor.phone),
    },
)

REGISTRY: dict[str, ReportSource] = {s.key: s for s in (
    INVOICES, BILLS, JOURNAL_LINES, PAYMENTS_RECEIVED, PAYMENTS_MADE,
    PRODUCTS, STOCK_MOVEMENTS, CUSTOMERS, VENDORS,
)}
```

- [ ] **Step 2: Verify field columns exist on the models**

Run: `cd backend && uv run python -c "from services.report_sources import REGISTRY; print(len(REGISTRY), 'sources'); [print(k, len(s.fields)) for k,s in REGISTRY.items()]"`
Expected: prints `9 sources` and a field count per source, no `AttributeError`.

> NOTE: if any column name differs (e.g. `Product.sku`/`stock_qty`/`sale_price`/`cost_price`, `StockMovement.date`/`kind`/`qty`/`unit_cost`, `Customer.email`/`phone`), open `models.py`, find the real attribute, and fix the `_f(...)` column reference. Do not invent columns — drop a field if no equivalent exists.

- [ ] **Step 3: Commit**

```bash
git add backend/services/report_sources/__init__.py
git commit -m "feat(reports): remaining v1 sources + REGISTRY

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.3: Engine — `ReportConfig` + predicate/coerce helpers (TDD)

**Files:**
- Create: `backend/services/report_engine.py`
- Test: `backend/tests/test_report_engine.py`

- [ ] **Step 1: Write the failing unit test**

```python
"""Engine helpers — pure logic, no HTTP/DB."""
from decimal import Decimal
import pytest
from services.report_engine import coerce_value, ReportConfig, FilterClause
from services.report_sources import FieldType


def test_coerce_money_to_decimal():
    assert coerce_value(FieldType.MONEY, "12.50") == Decimal("12.50")

def test_coerce_number_to_decimal():
    assert coerce_value(FieldType.NUMBER, 3) == Decimal("3")

def test_coerce_date_validates_iso():
    assert coerce_value(FieldType.DATE, "2026-05-01") == "2026-05-01"
    with pytest.raises(ValueError):
        coerce_value(FieldType.DATE, "not-a-date")

def test_reportconfig_defaults_empty():
    c = ReportConfig(columns=["total"])
    assert c.filters == [] and c.sort == [] and c.group_by == [] and c.aggregates == []
```

- [ ] **Step 2: Run it — expect failure**

Run: `cd backend && uv run pytest tests/test_report_engine.py -v`
Expected: FAIL (`ImportError: cannot import name 'coerce_value'`).

- [ ] **Step 3: Write the config models + helpers**

```python
"""Report engine: ReportConfig schema + tenant-safe query builder.

Read-only. The caller never commits. Every identifier is resolved through the
registry; tenant_id is injected unconditionally."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from services.report_sources import FieldDef, FieldType, OPS_BY_TYPE, ReportSource


class FilterClause(BaseModel):
    field: str
    op: str
    value: Any = None


class SortClause(BaseModel):
    field: str
    dir: str = "asc"


class Aggregate(BaseModel):
    field: str
    fn: str  # sum | avg | count | min | max


class DateRange(BaseModel):
    preset: Optional[str] = None      # this_month | this_quarter | this_year | ytd
    start: Optional[str] = None
    end: Optional[str] = None


class ReportConfig(BaseModel):
    columns: list[str] = Field(default_factory=list)
    filters: list[FilterClause] = Field(default_factory=list)
    sort: list[SortClause] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregates: list[Aggregate] = Field(default_factory=list)
    date_range: Optional[DateRange] = None


class ReportError(ValueError):
    """Engine validation failure → HTTP 400 at the router."""


def coerce_value(ftype: FieldType, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [coerce_value(ftype, v) for v in value]
    if ftype in (FieldType.MONEY, FieldType.NUMBER):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ReportError(f"not a number: {value!r}")
    if ftype == FieldType.DATE:
        try:
            _date.fromisoformat(str(value))
        except ValueError:
            raise ReportError(f"not an ISO date: {value!r}")
        return str(value)
    if ftype == FieldType.BOOL:
        return bool(value)
    return str(value)
```

- [ ] **Step 4: Run the test — expect PASS**

Run: `cd backend && uv run pytest tests/test_report_engine.py -v`
Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/report_engine.py backend/tests/test_report_engine.py
git commit -m "feat(reports): ReportConfig schema + value coercion (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.4: Engine — predicate builder (TDD)

**Files:**
- Modify: `backend/services/report_engine.py`
- Test: `backend/tests/test_report_engine.py`

- [ ] **Step 1: Add failing tests**

```python
from services.report_engine import build_predicate, ReportError
from services.report_sources import INVOICES

def test_build_predicate_money_gte():
    f = INVOICES.field("total")
    pred = build_predicate(f, "gte", coerce_value(f.type, "1000"))
    assert pred is not None  # compiles to a SQLAlchemy expression

def test_build_predicate_rejects_bad_op_for_type():
    f = INVOICES.field("total")  # MONEY
    with pytest.raises(ReportError):
        build_predicate(f, "contains", Decimal("1"))

def test_build_predicate_between_needs_two_values():
    f = INVOICES.field("total")
    with pytest.raises(ReportError):
        build_predicate(f, "between", [Decimal("1")])
```

- [ ] **Step 2: Run — expect failure**

Run: `cd backend && uv run pytest tests/test_report_engine.py -k predicate -v`
Expected: FAIL (`ImportError: build_predicate`).

- [ ] **Step 3: Implement `build_predicate`** (append to `report_engine.py`)

```python
def build_predicate(f: FieldDef, op: str, value: Any):
    if op not in OPS_BY_TYPE[f.type]:
        raise ReportError(f"operator {op!r} not allowed on {f.type.value} field {f.key!r}")
    col = f.column
    if op == "equals":
        return col == value
    if op == "contains":
        return col.contains(value)
    if op == "starts_with":
        return col.startswith(value)
    if op == "in":
        vals = value if isinstance(value, list) else [value]
        return col.in_(vals)
    if op == "gt":
        return col > value
    if op == "gte":
        return col >= value
    if op == "lt":
        return col < value
    if op == "lte":
        return col <= value
    if op == "before":
        return col < value
    if op == "after":
        return col > value
    if op == "between":
        if not isinstance(value, list) or len(value) != 2:
            raise ReportError("between requires exactly two values")
        return col.between(value[0], value[1])
    raise ReportError(f"unknown operator {op!r}")
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_report_engine.py -k predicate -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/report_engine.py backend/tests/test_report_engine.py
git commit -m "feat(reports): type-checked filter predicate builder (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.5: Engine — `run_report` + date range + aggregates (TDD against DB)

**Files:**
- Modify: `backend/services/report_engine.py`
- Test: `backend/tests/test_report_builder_run.py`

- [ ] **Step 1: Write the failing integration test** (seeds 2 invoices, runs a filtered + grouped report)

```python
"""run_report end-to-end via the engine, against seeded invoices."""
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlmodel import Session
from main import app
from services.report_engine import run_report, ReportConfig, FilterClause, Aggregate


def _auth(client):
    client.post("/api/auth/signup", json={"email": "run@rb.test", "password": "password123",
                                          "full_name": "U", "company_name": "RB Co"})
    r = client.post("/api/auth/login", data={"username": "run@rb.test", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_two_invoices(client, auth):
    c = client.post("/api/customers", headers=auth, json={"name": "Acme"}).json()
    for amt, cur in ((1000, "USD"), (2000, "USD")):
        client.post("/api/invoices", headers=auth, json={
            "customer_id": c["id"], "issue_date": "2026-05-02", "due_date": "2026-06-30",
            "gst_rate": 0, "currency": cur, "lines": [{"description": "S", "qty": 1, "rate": amt}]})


def test_run_filters_and_sums(client: TestClient):
    auth = _auth(client)
    _seed_two_invoices(client, auth)
    with Session(app.state.engine) as s:
        from models import User
        from sqlmodel import select as sel
        user = s.exec(sel(User)).first()
        cfg = ReportConfig(columns=["number", "total"],
                           filters=[FilterClause(field="total", op="gte", value="1500")],
                           aggregates=[Aggregate(field="total", fn="sum")])
        res = run_report(s, tenant_id=user.tenant_id, source_key="invoices",
                         config=cfg, page=0, page_size=100)
    assert res.total_count == 1                       # only the 2000 invoice
    assert res.footers["total"] == "2000.00"
    assert res.rows[0]["total"] == "2000.00"
```

- [ ] **Step 2: Run — expect failure**

Run: `cd backend && uv run pytest tests/test_report_builder_run.py::test_run_filters_and_sums -v`
Expected: FAIL (`ImportError: run_report`).

- [ ] **Step 3: Implement `run_report` + helpers** (append to `report_engine.py`)

```python
@dataclass
class ColumnMeta:
    key: str
    label: str
    type: str
    aggregatable: bool


@dataclass
class ReportResult:
    columns: list[ColumnMeta]
    rows: list[dict]
    group_by: list[str]
    footers: Optional[dict]
    page: int
    page_size: int
    total_count: int


_AGG_FN = {
    "sum": func.sum, "avg": func.avg, "count": func.count,
    "min": func.min, "max": func.max,
}
MAX_EXPORT_ROWS = 10_000


def _ser(v: Any) -> Any:
    return format(v, "f") if isinstance(v, Decimal) else v


def _money_str(v: Any) -> str:
    return format(Decimal(str(v or 0)).quantize(Decimal("0.01")), "f")


def _preset_range(preset: str) -> tuple[str, str]:
    from datetime import date
    t = date.today()
    if preset == "this_month":
        start = t.replace(day=1)
    elif preset == "this_quarter":
        start = t.replace(month=((t.month - 1) // 3) * 3 + 1, day=1)
    elif preset in ("this_year", "ytd"):
        start = t.replace(month=1, day=1)
    else:
        raise ReportError(f"unknown date preset {preset!r}")
    return start.isoformat(), t.isoformat()


def _apply_date_range(stmt, date_field: FieldDef, dr: DateRange):
    if dr.preset:
        start, end = _preset_range(dr.preset)
    else:
        start, end = dr.start, dr.end
    if start:
        stmt = stmt.where(date_field.column >= start)
    if end:
        stmt = stmt.where(date_field.column <= end)
    return stmt


def _collect_joins(source: ReportSource, fields: list[FieldDef]):
    seen, joins = set(), []
    for f in fields:
        if f.join and id(f.join) not in seen:
            seen.add(id(f.join))
            joins.append(f.join)
    return joins


def run_report(session: Session, *, tenant_id: int, source_key: str,
               config: ReportConfig, page: int, page_size: int) -> ReportResult:
    source = REGISTRY.get(source_key)
    if source is None:
        raise ReportError(f"unknown source {source_key!r}")

    try:
        sel_fields = [source.field(k) for k in (config.columns or source.default_columns)]
        filt_fields = [source.field(c.field) for c in config.filters]
        grp_fields = [source.field(k) for k in config.group_by]
        agg_fields = [(source.field(a.field), a) for a in config.aggregates]
        sort_fields = [(source.field(s.field), s) for s in config.sort]
    except KeyError as e:
        raise ReportError(f"unknown field {e.args[0]!r}")

    date_f = source.field(source.date_field) if (config.date_range and source.date_field) else None
    all_used = sel_fields + filt_fields + grp_fields + [f for f, _ in agg_fields] + \
        [f for f, _ in sort_fields] + ([date_f] if date_f else [])
    joins = _collect_joins(source, all_used)

    def base(stmt):
        stmt = stmt.select_from(source.model)
        for j in joins:
            stmt = stmt.join(j.target, j.local == j.target_key)
        stmt = stmt.where(source.model.tenant_id == tenant_id)   # ALWAYS injected
        for c in config.filters:
            f = source.field(c.field)
            stmt = stmt.where(build_predicate(f, c.op, coerce_value(f.type, c.value)))
        if date_f:
            stmt = _apply_date_range(stmt, date_f, config.date_range)
        return stmt

    if config.group_by:
        cols = [source.field(k).column.label(k) for k in config.group_by]
        for f, a in agg_fields:
            cols.append(_AGG_FN[a.fn](f.column).label(f.key))
        q = base(select(*cols)).group_by(*[source.field(k).column for k in config.group_by])
        col_keys = config.group_by + [f.key for f, _ in agg_fields]
    else:
        q = base(select(*[f.column.label(f.key) for f in sel_fields]))
        col_keys = [f.key for f in sel_fields]

    for f, s in sort_fields:
        q = q.order_by(f.column.desc() if s.dir == "desc" else f.column.asc())

    total = session.scalar(select(func.count()).select_from(q.subquery()))
    rows_raw = session.exec(q.offset(page * page_size).limit(page_size)).mappings().all()

    key_type = {f.key: f.type for f in all_used}
    rows = [{k: (_money_str(r[k]) if key_type.get(k) == FieldType.MONEY else _ser(r[k]))
             for k in col_keys} for r in rows_raw]

    footers = None
    if config.aggregates and not config.group_by:
        fcols = [_AGG_FN[a.fn](source.field(a.field).column).label(a.field) for a in config.aggregates]
        frow = session.exec(base(select(*fcols))).mappings().first()
        footers = {a.field: (_money_str(frow[a.field]) if source.field(a.field).type == FieldType.MONEY
                             else _ser(frow[a.field])) for a in config.aggregates}

    meta = [ColumnMeta(f.key, f.label, f.type.value, f.aggregatable)
            for f in (sel_fields if not config.group_by
                      else grp_fields + [f for f, _ in agg_fields])]
    return ReportResult(meta, rows, config.group_by, footers, page, page_size, total or 0)
```

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_report_builder_run.py::test_run_filters_and_sums -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/report_engine.py backend/tests/test_report_builder_run.py
git commit -m "feat(reports): tenant-safe run_report engine w/ group/aggregate (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 2 — API: `/sources` + `/run`

### Task 2.1: Router with `/sources` + `/run` (TDD)

**Files:**
- Create: `backend/routers/report_builder.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_report_builder_run.py`

- [ ] **Step 1: Add failing endpoint tests**

```python
def test_sources_lists_invoices(client: TestClient):
    auth = _auth(client)
    r = client.get("/api/report-builder/sources", headers=auth)
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()}
    assert "invoices" in keys and "journal_lines" in keys
    inv = next(s for s in r.json() if s["key"] == "invoices")
    assert any(f["key"] == "total" and f["type"] == "money" for f in inv["fields"])


def test_run_endpoint_returns_rows(client: TestClient):
    auth = _auth(client)
    _seed_two_invoices(client, auth)
    r = client.post("/api/report-builder/run", headers=auth, json={
        "source_key": "invoices",
        "config": {"columns": ["number", "total"], "sort": [{"field": "total", "dir": "desc"}]}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_count"] == 2
    assert body["rows"][0]["total"] == "2000.00"   # desc sort


def test_run_unknown_field_is_400(client: TestClient):
    auth = _auth(client)
    r = client.post("/api/report-builder/run", headers=auth, json={
        "source_key": "invoices", "config": {"columns": ["nope"]}})
    assert r.status_code == 400
```

- [ ] **Step 2: Run — expect failure**

Run: `cd backend && uv run pytest tests/test_report_builder_run.py -k "sources or run_endpoint or unknown_field" -v`
Expected: FAIL (404 — router not mounted).

- [ ] **Step 3: Write the router**

```python
"""User-level dynamic report builder API."""
from dataclasses import asdict
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from routers.common import CurrentUserDep, SessionDep
from services.report_engine import ReportConfig, ReportError, run_report
from services.report_sources import REGISTRY

router = APIRouter(prefix="/api/report-builder", tags=["report-builder"])


@router.get("/sources")
def list_sources(user: CurrentUserDep):
    out = []
    for s in REGISTRY.values():
        out.append({
            "key": s.key, "label": s.label, "date_field": s.date_field,
            "default_columns": s.default_columns,
            "fields": [{"key": f.key, "label": f.label, "type": f.type.value,
                        "enum_values": f.enum_values, "aggregatable": f.aggregatable,
                        "groupable": f.groupable} for f in s.fields.values()],
        })
    return out


class RunBody(BaseModel):
    source_key: str
    config: ReportConfig
    page: int = 0
    page_size: int = 100


@router.post("/run")
def run(body: RunBody, session: SessionDep, user: CurrentUserDep):
    try:
        res = run_report(session, tenant_id=user.tenant_id, source_key=body.source_key,
                         config=body.config, page=body.page, page_size=min(body.page_size, 500))
    except ReportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "columns": [asdict(c) for c in res.columns],
        "rows": res.rows, "group_by": res.group_by, "footers": res.footers,
        "page": res.page, "page_size": res.page_size, "total_count": res.total_count,
    }
```

- [ ] **Step 4: Register the router in `main.py`**

In the `from routers import (...)` block add `report_builder`; in the `_ROUTERS` list add a line `report_builder.router,`.

- [ ] **Step 5: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_report_builder_run.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/report_builder.py backend/main.py backend/tests/test_report_builder_run.py
git commit -m "feat(reports): /sources + /run endpoints (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2.2: Safety + tenant-isolation suite (TDD)

**Files:**
- Test: `backend/tests/test_report_builder_safety.py`

- [ ] **Step 1: Write the suite**

```python
"""Report builder safety — the most important suite."""
from fastapi.testclient import TestClient


def _signup(client, email):
    client.post("/api/auth/signup", json={"email": email, "password": "password123",
                                          "full_name": "U", "company_name": email})
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_unknown_source_400(client: TestClient):
    auth = _signup(client, "s1@rb.test")
    r = client.post("/api/report-builder/run", headers=auth,
                    json={"source_key": "secrets", "config": {"columns": []}})
    assert r.status_code == 400


def test_op_type_mismatch_400(client: TestClient):
    auth = _signup(client, "s2@rb.test")
    r = client.post("/api/report-builder/run", headers=auth, json={
        "source_key": "invoices",
        "config": {"columns": ["total"], "filters": [{"field": "total", "op": "contains", "value": "x"}]}})
    assert r.status_code == 400


def test_tenant_isolation(client: TestClient):
    a = _signup(client, "tenantA@rb.test")
    cust = client.post("/api/customers", headers=a, json={"name": "SecretCo"}).json()
    client.post("/api/invoices", headers=a, json={
        "customer_id": cust["id"], "issue_date": "2026-05-02", "due_date": "2026-06-30",
        "gst_rate": 0, "currency": "USD", "lines": [{"description": "S", "qty": 1, "rate": 999}]})
    b = _signup(client, "tenantB@rb.test")
    r = client.post("/api/report-builder/run", headers=b, json={
        "source_key": "invoices", "config": {"columns": ["number", "customer_name", "total"]}})
    assert r.status_code == 200
    assert r.json()["total_count"] == 0            # B sees none of A's data
    assert all("SecretCo" != row.get("customer_name") for row in r.json()["rows"])
```

- [ ] **Step 2: Run — expect PASS** (engine already enforces these)

Run: `cd backend && uv run pytest tests/test_report_builder_safety.py -v`
Expected: all PASS. If `test_tenant_isolation` fails, STOP — the tenant filter is broken; do not proceed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_report_builder_safety.py
git commit -m "test(reports): safety + tenant-isolation suite

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 3 — Saved reports

### Task 3.1: `ReportDefinition` model + migration

**Files:**
- Modify: `backend/models.py`
- Create: `backend/alembic/versions/<rev>_report_definition.py`

- [ ] **Step 1: Add the model** (near other tables in `models.py`)

```python
class ReportDefinition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    source_key: str
    config: str = Field(sa_column=Column(JSON))   # ReportConfig JSON
    visibility: str = Field(default="private")    # "private" | "shared"
    owner_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

Ensure `from sqlalchemy import Column, JSON` is imported at the top of `models.py` (add if missing).

- [ ] **Step 2: Create the migration**

Run: `cd backend && uv run alembic heads` → confirm it prints `aa01prodcat`. Then create `backend/alembic/versions/<rev>_report_definition.py`:

```python
"""report definition

Revision ID: reportdef01
Revises: aa01prodcat
"""
from alembic import op
import sqlalchemy as sa

revision = "reportdef01"
down_revision = "aa01prodcat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "reportdefinition"):
        op.create_table(
            "reportdefinition",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), index=True, nullable=False),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("source_key", sa.String, nullable=False),
            sa.Column("config", sa.JSON, nullable=False),
            sa.Column("visibility", sa.String, nullable=False, server_default="private"),
            sa.Column("owner_id", sa.Integer, sa.ForeignKey("user.id"), index=True, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    op.drop_table("reportdefinition")
```

- [ ] **Step 3: Apply + verify**

Run: `cd backend && uv run alembic upgrade head && uv run alembic current`
Expected: no error; `current` shows `reportdef01`.

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/alembic/versions/reportdef01_report_definition.py
git commit -m "feat(reports): ReportDefinition table + migration

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3.2: Saved-report CRUD (TDD)

**Files:**
- Modify: `backend/routers/report_builder.py`
- Test: `backend/tests/test_report_builder_reports.py`

- [ ] **Step 1: Write the failing CRUD tests**

```python
"""Saved report CRUD + visibility."""
from fastapi.testclient import TestClient


def _signup(client, email):
    client.post("/api/auth/signup", json={"email": email, "password": "password123",
                                          "full_name": "U", "company_name": email})
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _save(client, auth, name="My Report", visibility="private"):
    return client.post("/api/report-builder/reports", headers=auth, json={
        "name": name, "source_key": "invoices", "visibility": visibility,
        "config": {"columns": ["number", "total"],
                   "filters": [{"field": "status", "op": "in", "value": ["sent"]}]}})


def test_save_list_load_roundtrip(client: TestClient):
    auth = _signup(client, "c1@rb.test")
    rid = _save(client, auth).json()["id"]
    listed = client.get("/api/report-builder/reports", headers=auth).json()
    assert any(x["id"] == rid for x in listed)
    one = client.get(f"/api/report-builder/reports/{rid}", headers=auth).json()
    assert one["config"]["columns"] == ["number", "total"]


def test_save_invalid_config_400(client: TestClient):
    auth = _signup(client, "c2@rb.test")
    r = client.post("/api/report-builder/reports", headers=auth, json={
        "name": "Bad", "source_key": "invoices",
        "config": {"columns": ["does_not_exist"]}})
    assert r.status_code == 400


def test_private_hidden_from_others_shared_visible(client: TestClient):
    a = _signup(client, "owner@rb.test")
    # NOTE: second user in SAME tenant requires an invite flow; here we assert
    # cross-tenant invisibility (private AND shared never leak across tenants).
    priv = _save(client, a, name="Priv", visibility="private").json()["id"]
    b = _signup(client, "other@rb.test")
    assert all(x["id"] != priv for x in client.get("/api/report-builder/reports", headers=b).json())


def test_delete_owner_only(client: TestClient):
    a = _signup(client, "del@rb.test")
    rid = _save(client, a).json()["id"]
    assert client.delete(f"/api/report-builder/reports/{rid}", headers=a).status_code == 200
    assert client.get(f"/api/report-builder/reports/{rid}", headers=a).status_code == 404
```

- [ ] **Step 2: Run — expect failure**

Run: `cd backend && uv run pytest tests/test_report_builder_reports.py -v`
Expected: FAIL (404 — CRUD routes missing).

- [ ] **Step 3: Add CRUD to `report_builder.py`**

```python
from datetime import datetime
import json as _json
from sqlmodel import select
from models import ReportDefinition


def _validate_config(source_key: str, config: ReportConfig):
    from services.report_engine import build_predicate, coerce_value
    from services.report_sources import REGISTRY
    src = REGISTRY.get(source_key)
    if src is None:
        raise HTTPException(400, f"unknown source {source_key!r}")
    try:
        for k in config.columns:
            src.field(k)
        for c in config.filters:
            f = src.field(c.field)
            build_predicate(f, c.op, coerce_value(f.type, c.value))
        for a in config.aggregates:
            if not src.field(a.field).aggregatable:
                raise ReportError(f"{a.field} is not aggregatable")
        for k in config.group_by:
            src.field(k)
    except (KeyError, ReportError) as e:
        raise HTTPException(400, f"invalid config: {e}")


class SaveBody(BaseModel):
    name: str
    source_key: str
    config: ReportConfig
    visibility: str = "private"


def _serialize(rd: ReportDefinition) -> dict:
    return {"id": rd.id, "name": rd.name, "source_key": rd.source_key,
            "visibility": rd.visibility, "owner_id": rd.owner_id,
            "config": _json.loads(rd.config)}


@router.get("/reports")
def list_reports(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(select(ReportDefinition).where(
        ReportDefinition.tenant_id == user.tenant_id)).all()
    visible = [r for r in rows if r.visibility == "shared" or r.owner_id == user.id]
    return [_serialize(r) for r in visible]


@router.get("/reports/{rid}")
def get_report(rid: int, session: SessionDep, user: CurrentUserDep):
    rd = session.get(ReportDefinition, rid)
    if not rd or rd.tenant_id != user.tenant_id or \
       (rd.visibility != "shared" and rd.owner_id != user.id):
        raise HTTPException(404, "not found")
    return _serialize(rd)


@router.post("/reports")
def save_report(body: SaveBody, session: SessionDep, user: CurrentUserDep):
    _validate_config(body.source_key, body.config)
    rd = ReportDefinition(tenant_id=user.tenant_id, name=body.name, source_key=body.source_key,
                          config=body.config.model_dump_json(), visibility=body.visibility,
                          owner_id=user.id, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    session.add(rd); session.commit(); session.refresh(rd)
    return _serialize(rd)


@router.patch("/reports/{rid}")
def update_report(rid: int, body: SaveBody, session: SessionDep, user: CurrentUserDep):
    rd = session.get(ReportDefinition, rid)
    if not rd or rd.tenant_id != user.tenant_id:
        raise HTTPException(404, "not found")
    if rd.owner_id != user.id:
        raise HTTPException(403, "owner only")
    _validate_config(body.source_key, body.config)
    rd.name, rd.source_key = body.name, body.source_key
    rd.config, rd.visibility = body.config.model_dump_json(), body.visibility
    rd.updated_at = datetime.utcnow()
    session.add(rd); session.commit(); session.refresh(rd)
    return _serialize(rd)


@router.delete("/reports/{rid}")
def delete_report(rid: int, session: SessionDep, user: CurrentUserDep):
    rd = session.get(ReportDefinition, rid)
    if not rd or rd.tenant_id != user.tenant_id:
        raise HTTPException(404, "not found")
    if rd.owner_id != user.id:
        raise HTTPException(403, "owner only")
    session.delete(rd); session.commit()
    return {"ok": True}
```

Add `from services.report_engine import ReportError` to the router imports if not already present.

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_report_builder_reports.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/report_builder.py backend/tests/test_report_builder_reports.py
git commit -m "feat(reports): saved-report CRUD + visibility (TDD)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 4 — Export

### Task 4.1: CSV + XLSX export (TDD)

**Files:**
- Modify: `backend/routers/report_builder.py`
- Test: `backend/tests/test_report_builder_export.py`
- Modify: `backend/pyproject.toml` (add `openpyxl`)

- [ ] **Step 1: Add the dependency**

Run: `cd backend && uv add openpyxl`
Expected: `openpyxl` appears in `pyproject.toml` deps.

- [ ] **Step 2: Write failing tests**

```python
"""Report export (CSV/XLSX)."""
import io
from fastapi.testclient import TestClient


def _auth(client):
    client.post("/api/auth/signup", json={"email": "exp@rb.test", "password": "password123",
                                          "full_name": "U", "company_name": "Exp Co"})
    r = client.post("/api/auth/login", data={"username": "exp@rb.test", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed(client, auth):
    c = client.post("/api/customers", headers=auth, json={"name": "Acme"}).json()
    client.post("/api/invoices", headers=auth, json={
        "customer_id": c["id"], "issue_date": "2026-05-02", "due_date": "2026-06-30",
        "gst_rate": 0, "currency": "USD", "lines": [{"description": "S", "qty": 1, "rate": 1000}]})


def test_export_csv(client: TestClient):
    auth = _auth(client); _seed(client, auth)
    r = client.post("/api/report-builder/export?format=csv", headers=auth,
                    json={"source_key": "invoices", "config": {"columns": ["number", "total"]}})
    assert r.status_code == 200
    text = r.content.decode()
    assert "number,total" in text.replace(" ", "")
    assert "1000.00" in text


def test_export_xlsx_is_valid_workbook(client: TestClient):
    auth = _auth(client); _seed(client, auth)
    r = client.post("/api/report-builder/export?format=xlsx", headers=auth,
                    json={"source_key": "invoices", "config": {"columns": ["number", "total"]}})
    assert r.status_code == 200
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.active["A1"].value == "number"
```

- [ ] **Step 3: Run — expect failure**

Run: `cd backend && uv run pytest tests/test_report_builder_export.py -v`
Expected: FAIL (404 — export route missing).

- [ ] **Step 4: Add the export endpoint**

```python
import csv, io
from fastapi.responses import StreamingResponse
from services.report_engine import MAX_EXPORT_ROWS


@router.post("/export")
def export_report(body: RunBody, session: SessionDep, user: CurrentUserDep,
                  format: str = Query("csv")):
    try:
        res = run_report(session, tenant_id=user.tenant_id, source_key=body.source_key,
                         config=body.config, page=0, page_size=MAX_EXPORT_ROWS)
    except ReportError as e:
        raise HTTPException(400, str(e))
    headers = [c.key for c in res.columns]

    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf); w.writerow(headers)
        for row in res.rows:
            w.writerow([row.get(h, "") for h in headers])
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={body.source_key}.csv"})

    if format == "xlsx":
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.append(headers)
        for row in res.rows:
            ws.append([row.get(h, "") for h in headers])
        out = io.BytesIO(); wb.save(out); out.seek(0)
        return StreamingResponse(out,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={body.source_key}.xlsx"})

    raise HTTPException(400, f"unknown format {format!r}")
```

- [ ] **Step 5: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_report_builder_export.py -v`
Expected: both PASS.

- [ ] **Step 6: Full backend suite green**

Run: `cd backend && uv run pytest`
Expected: all pass (existing + new). Fix any regression before continuing.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/report_builder.py backend/tests/test_report_builder_export.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(reports): CSV + XLSX export

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 5 — Frontend

### Task 5.1: Shared types + API helpers

**Files:**
- Create: `frontend/src/lib/reportTypes.ts`

- [ ] **Step 1: Write the types**

```typescript
export type FieldType = "text" | "number" | "money" | "date" | "enum" | "bool"

export interface FieldMeta {
  key: string; label: string; type: FieldType
  enum_values: string[] | null; aggregatable: boolean; groupable: boolean
}
export interface SourceMeta {
  key: string; label: string; date_field: string | null
  default_columns: string[]; fields: FieldMeta[]
}
export interface FilterClause { field: string; op: string; value: unknown }
export interface SortClause { field: string; dir: "asc" | "desc" }
export interface Aggregate { field: string; fn: "sum" | "avg" | "count" | "min" | "max" }
export interface DateRange { preset?: string; start?: string; end?: string }
export interface ReportConfig {
  columns: string[]; filters: FilterClause[]; sort: SortClause[]
  group_by: string[]; aggregates: Aggregate[]; date_range?: DateRange | null
}
export interface ColumnMeta { key: string; label: string; type: string; aggregatable: boolean }
export interface RunResult {
  columns: ColumnMeta[]; rows: Record<string, string>[]; group_by: string[]
  footers: Record<string, string> | null; page: number; page_size: number; total_count: number
}
export interface SavedReport {
  id: number; name: string; source_key: string; visibility: string
  owner_id: number; config: ReportConfig
}
export const OPS_BY_TYPE: Record<FieldType, string[]> = {
  text: ["equals", "contains", "starts_with", "in"],
  number: ["equals", "gt", "gte", "lt", "lte", "between"],
  money: ["equals", "gt", "gte", "lt", "lte", "between"],
  date: ["equals", "before", "after", "between"],
  enum: ["equals", "in"],
  bool: ["equals"],
}
export const emptyConfig = (cols: string[] = []): ReportConfig =>
  ({ columns: cols, filters: [], sort: [], group_by: [], aggregates: [], date_range: null })
```

- [ ] **Step 2: Type-check + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

```bash
git add frontend/src/lib/reportTypes.ts
git commit -m "feat(reports): shared report-builder TS types

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5.2: `<ReportGrid>` + `ColumnChooser` + `FilterBar` + `GroupByPicker`

**Files:**
- Create: `frontend/src/components/report-builder/ReportGrid.tsx`
- Create: `frontend/src/components/report-builder/ColumnChooser.tsx`
- Create: `frontend/src/components/report-builder/FilterBar.tsx`
- Create: `frontend/src/components/report-builder/GroupByPicker.tsx`

- [ ] **Step 1: `ReportGrid.tsx`** (renders result + footers + click-to-filter + sort)

```tsx
"use client"
import SortableHeader from "@/components/SortableHeader"
import type { RunResult, SortClause } from "@/lib/reportTypes"

interface Props {
  result: RunResult | null
  sort: SortClause[]
  onSort: (field: string, dir: "asc" | "desc") => void
  onCellFilter: (field: string, value: string) => void
}

export default function ReportGrid({ result, sort, onSort, onCellFilter }: Props) {
  if (!result) return <div className="p-8 text-black/50">Configure a report to begin.</div>
  const sb = sort[0]?.field ?? ""
  const sd = sort[0]?.dir ?? "asc"
  return (
    <div className="overflow-auto border border-[#ede9e2] rounded-xl bg-white">
      <table className="w-full text-sm">
        <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
          <tr>{result.columns.map(c => (
            <SortableHeader key={c.key} label={c.label} field={c.key}
              sortBy={sb} sortDir={sd} onSort={onSort}
              className={c.type === "money" || c.type === "number" ? "text-right" : ""} />
          ))}</tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i} className="border-b border-[#f1ede6] hover:bg-[#faf8f4]">
              {result.columns.map(c => (
                <td key={c.key}
                  onClick={() => onCellFilter(c.key, String(row[c.key] ?? ""))}
                  className={`px-6 py-3 cursor-pointer ${c.type === "money" || c.type === "number" ? "text-right tabular-nums" : ""}`}
                  title="Filter by this value">
                  {row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {result.footers && (
          <tfoot className="bg-[#f6f3ee] font-bold border-t-2 border-[#b8943f]">
            <tr>{result.columns.map((c, i) => (
              <td key={c.key} className={`px-6 py-3 ${c.type === "money" ? "text-right tabular-nums" : ""}`}>
                {i === 0 ? "TOTAL" : (result.footers?.[c.key] ?? "")}
              </td>
            ))}</tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
```

- [ ] **Step 2: `ColumnChooser.tsx`** (checkbox toggle of source fields)

```tsx
"use client"
import type { SourceMeta } from "@/lib/reportTypes"

interface Props { source: SourceMeta; columns: string[]; onChange: (cols: string[]) => void }

export default function ColumnChooser({ source, columns, onChange }: Props) {
  const toggle = (key: string) =>
    onChange(columns.includes(key) ? columns.filter(c => c !== key) : [...columns, key])
  return (
    <details className="relative">
      <summary className="px-3 py-2 text-sm border border-[#ede9e2] rounded-lg cursor-pointer bg-white">+ Columns</summary>
      <div className="absolute z-10 mt-1 w-56 bg-white border border-[#ede9e2] rounded-lg shadow-lg p-2 max-h-72 overflow-auto">
        {source.fields.map(f => (
          <label key={f.key} className="flex items-center gap-2 px-2 py-1 text-sm hover:bg-[#f6f3ee] rounded cursor-pointer">
            <input type="checkbox" checked={columns.includes(f.key)} onChange={() => toggle(f.key)} />
            {f.label}
          </label>
        ))}
      </div>
    </details>
  )
}
```

- [ ] **Step 3: `FilterBar.tsx`** (active filter chips + add-filter editor; widget by type)

```tsx
"use client"
import { useState } from "react"
import { X } from "lucide-react"
import type { SourceMeta, FilterClause } from "@/lib/reportTypes"
import { OPS_BY_TYPE } from "@/lib/reportTypes"

interface Props { source: SourceMeta; filters: FilterClause[]; onChange: (f: FilterClause[]) => void }

export default function FilterBar({ source, filters, onChange }: Props) {
  const [field, setField] = useState(source.fields[0]?.key ?? "")
  const meta = source.fields.find(f => f.key === field)
  const ops = meta ? OPS_BY_TYPE[meta.type] : []
  const [op, setOp] = useState(ops[0] ?? "equals")
  const [value, setValue] = useState("")

  const add = () => {
    if (!field) return
    onChange([...filters, { field, op, value }])
    setValue("")
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select value={field} onChange={e => setField(e.target.value)} className="text-sm border border-[#ede9e2] rounded px-2 py-1">
        {source.fields.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
      </select>
      <select value={op} onChange={e => setOp(e.target.value)} className="text-sm border border-[#ede9e2] rounded px-2 py-1">
        {ops.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      {meta?.type === "enum"
        ? <select value={value} onChange={e => setValue(e.target.value)} className="text-sm border border-[#ede9e2] rounded px-2 py-1">
            <option value="">—</option>{(meta.enum_values ?? []).map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        : <input value={value} onChange={e => setValue(e.target.value)}
            type={meta?.type === "date" ? "date" : meta?.type === "money" || meta?.type === "number" ? "number" : "text"}
            className="text-sm border border-[#ede9e2] rounded px-2 py-1" placeholder="value" />}
      <button onClick={add} className="text-sm px-3 py-1 border border-[#b8943f] text-[#b8943f] rounded">+ Filter</button>
      {filters.map((f, i) => (
        <span key={i} className="inline-flex items-center gap-1 text-xs bg-[#f6f3ee] border border-[#ede9e2] rounded-full px-3 py-1">
          {f.field} {f.op} {String(Array.isArray(f.value) ? f.value.join(",") : f.value)}
          <X size={12} className="cursor-pointer" onClick={() => onChange(filters.filter((_, j) => j !== i))} />
        </span>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: `GroupByPicker.tsx`**

```tsx
"use client"
import type { SourceMeta } from "@/lib/reportTypes"

interface Props { source: SourceMeta; groupBy: string[]; onChange: (g: string[]) => void }

export default function GroupByPicker({ source, groupBy, onChange }: Props) {
  const val = groupBy[0] ?? ""
  return (
    <select value={val} onChange={e => onChange(e.target.value ? [e.target.value] : [])}
      className="text-sm border border-[#ede9e2] rounded-lg px-3 py-2 bg-white">
      <option value="">No grouping</option>
      {source.fields.filter(f => f.groupable).map(f => <option key={f.key} value={f.key}>Group by {f.label}</option>)}
    </select>
  )
}
```

- [ ] **Step 5: Type-check + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

```bash
git add frontend/src/components/report-builder/
git commit -m "feat(reports): ReportGrid + column/filter/group controls

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5.3: `SavedReportsMenu` + `ExportMenu`

**Files:**
- Create: `frontend/src/components/report-builder/SavedReportsMenu.tsx`
- Create: `frontend/src/components/report-builder/ExportMenu.tsx`

- [ ] **Step 1: `SavedReportsMenu.tsx`**

```tsx
"use client"
import type { SavedReport } from "@/lib/reportTypes"

interface Props {
  saved: SavedReport[]
  onLoad: (r: SavedReport) => void
  onSave: () => void
  onDelete: (id: number) => void
}

export default function SavedReportsMenu({ saved, onLoad, onSave, onDelete }: Props) {
  return (
    <details className="relative">
      <summary className="px-3 py-2 text-sm border border-[#ede9e2] rounded-lg cursor-pointer bg-white">Saved ▾</summary>
      <div className="absolute z-10 mt-1 right-0 w-64 bg-white border border-[#ede9e2] rounded-lg shadow-lg p-2">
        <button onClick={onSave} className="w-full text-left px-2 py-1 text-sm font-bold text-[#b8943f]">+ Save current…</button>
        <div className="border-t border-[#ede9e2] my-1" />
        {saved.length === 0 && <p className="px-2 py-1 text-xs text-black/40">No saved reports</p>}
        {saved.map(r => (
          <div key={r.id} className="flex items-center justify-between px-2 py-1 text-sm hover:bg-[#f6f3ee] rounded">
            <button onClick={() => onLoad(r)} className="text-left flex-1 truncate">{r.name}
              {r.visibility === "shared" && <span className="ml-1 text-xs text-black/40">· shared</span>}</button>
            <button onClick={() => onDelete(r.id)} className="text-xs text-red-600 ml-2">✕</button>
          </div>
        ))}
      </div>
    </details>
  )
}
```

- [ ] **Step 2: `ExportMenu.tsx`** (posts config, downloads blob)

```tsx
"use client"
import { apiFetch } from "@/lib/api"
import type { ReportConfig } from "@/lib/reportTypes"

interface Props { sourceKey: string; config: ReportConfig }

async function download(sourceKey: string, config: ReportConfig, format: "csv" | "xlsx") {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
  const base = process.env.NEXT_PUBLIC_API_URL ?? ""
  const res = await fetch(`${base}/api/report-builder/export?format=${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ source_key: sourceKey, config }),
  })
  const blob = await res.blob()
  const a = document.createElement("a")
  a.href = URL.createObjectURL(blob)
  a.download = `${sourceKey}.${format}`
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function ExportMenu({ sourceKey, config }: Props) {
  return (
    <details className="relative">
      <summary className="px-3 py-2 text-sm border border-[#ede9e2] rounded-lg cursor-pointer bg-white">Export ▾</summary>
      <div className="absolute z-10 mt-1 right-0 w-40 bg-white border border-[#ede9e2] rounded-lg shadow-lg p-2">
        <button onClick={() => download(sourceKey, config, "csv")} className="w-full text-left px-2 py-1 text-sm hover:bg-[#f6f3ee] rounded">CSV</button>
        <button onClick={() => download(sourceKey, config, "xlsx")} className="w-full text-left px-2 py-1 text-sm hover:bg-[#f6f3ee] rounded">Excel (XLSX)</button>
        <button onClick={() => window.print()} className="w-full text-left px-2 py-1 text-sm hover:bg-[#f6f3ee] rounded">Print</button>
      </div>
    </details>
  )
}
```

> NOTE: confirm `apiFetch` import path/signature in `src/lib/api.ts`. The export uses raw `fetch` (not `apiFetch`) because it streams a binary blob, not JSON — mirror `apiFetch`'s base-URL + token logic (shown above).

- [ ] **Step 3: Type-check + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

```bash
git add frontend/src/components/report-builder/SavedReportsMenu.tsx frontend/src/components/report-builder/ExportMenu.tsx
git commit -m "feat(reports): saved-reports + export menus

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5.4: Builder page (orchestration) + sidebar

**Files:**
- Create: `frontend/src/app/(dashboard)/reports/builder/page.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Write the page**

```tsx
"use client"
import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import ReportGrid from "@/components/report-builder/ReportGrid"
import ColumnChooser from "@/components/report-builder/ColumnChooser"
import FilterBar from "@/components/report-builder/FilterBar"
import GroupByPicker from "@/components/report-builder/GroupByPicker"
import SavedReportsMenu from "@/components/report-builder/SavedReportsMenu"
import ExportMenu from "@/components/report-builder/ExportMenu"
import { emptyConfig } from "@/lib/reportTypes"
import type { SourceMeta, ReportConfig, RunResult, SavedReport } from "@/lib/reportTypes"

export default function ReportBuilderPage() {
  const [sources, setSources] = useState<SourceMeta[]>([])
  const [sourceKey, setSourceKey] = useState("")
  const [config, setConfig] = useState<ReportConfig>(emptyConfig())
  const [result, setResult] = useState<RunResult | null>(null)
  const [saved, setSaved] = useState<SavedReport[]>([])
  const source = sources.find(s => s.key === sourceKey)

  useEffect(() => {
    apiFetch<SourceMeta[]>("/api/report-builder/sources").then(s => {
      setSources(s)
      if (s[0]) { setSourceKey(s[0].key); setConfig(emptyConfig(s[0].default_columns)) }
    })
    apiFetch<SavedReport[]>("/api/report-builder/reports").then(setSaved)
  }, [])

  const run = useCallback((sk: string, cfg: ReportConfig) => {
    if (!sk) return
    apiFetch<RunResult>("/api/report-builder/run", {
      method: "POST", body: JSON.stringify({ source_key: sk, config: cfg }),
    }).then(setResult).catch(() => setResult(null))
  }, [])

  useEffect(() => { run(sourceKey, config) }, [sourceKey, config, run])

  const patch = (p: Partial<ReportConfig>) => setConfig(c => ({ ...c, ...p }))
  const pickSource = (k: string) => {
    const s = sources.find(x => x.key === k)
    setSourceKey(k); setConfig(emptyConfig(s?.default_columns ?? []))
  }
  const onSort = (field: string, dir: "asc" | "desc") => patch({ sort: [{ field, dir }] })
  const onCellFilter = (field: string, value: string) =>
    patch({ filters: [...config.filters, { field, op: "equals", value }] })

  const saveCurrent = async () => {
    const name = window.prompt("Report name?")
    if (!name) return
    const shared = window.confirm("Share with the whole organisation? (Cancel = private)")
    const rd = await apiFetch<SavedReport>("/api/report-builder/reports", {
      method: "POST",
      body: JSON.stringify({ name, source_key: sourceKey, config, visibility: shared ? "shared" : "private" }),
    })
    setSaved(s => [...s, rd])
  }
  const loadReport = (r: SavedReport) => { setSourceKey(r.source_key); setConfig(r.config) }
  const del = async (id: number) => {
    await apiFetch(`/api/report-builder/reports/${id}`, { method: "DELETE" })
    setSaved(s => s.filter(x => x.id !== id))
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-serif">Report Builder</h1>
      <div className="flex flex-wrap items-center gap-2">
        <select value={sourceKey} onChange={e => pickSource(e.target.value)}
          className="text-sm border border-[#ede9e2] rounded-lg px-3 py-2 bg-white">
          {sources.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        {source && <ColumnChooser source={source} columns={config.columns} onChange={c => patch({ columns: c })} />}
        {source && <GroupByPicker source={source} groupBy={config.group_by}
          onChange={g => patch({ group_by: g, aggregates: g.length
            ? source.fields.filter(f => f.aggregatable && config.columns.includes(f.key)).map(f => ({ field: f.key, fn: "sum" as const }))
            : config.aggregates })} />}
        <div className="ml-auto flex gap-2">
          <SavedReportsMenu saved={saved} onLoad={loadReport} onSave={saveCurrent} onDelete={del} />
          <ExportMenu sourceKey={sourceKey} config={config} />
        </div>
      </div>
      {source && <FilterBar source={source} filters={config.filters} onChange={f => patch({ filters: f })} />}
      <ReportGrid result={result} sort={config.sort} onSort={onSort} onCellFilter={onCellFilter} />
      {result && <p className="text-xs text-black/40">{result.total_count} rows</p>}
    </div>
  )
}
```

- [ ] **Step 2: Add the sidebar entry** under the `Reports` section in `Sidebar.tsx` (match the existing object shape; import an icon e.g. `Table2` from lucide-react):

```tsx
{ label: "Report Builder", href: "/reports/builder", icon: Table2, section: "Reports" },
```

- [ ] **Step 3: Lint + type-check + build**

Run: `cd frontend && npm run lint && npx tsc --noEmit && npm run build`
Expected: all clean (zero errors).

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)/reports/builder/page.tsx" frontend/src/components/Sidebar.tsx
git commit -m "feat(reports): report builder page + sidebar entry

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 6 — Docs + green suite + finish

### Task 6.1: Documentation

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `USER_GUIDE.md`, `WORKFLOW.md`

- [ ] **Step 1:** In `CLAUDE.md` router table add a row: `routers/report_builder.py | Dynamic report builder — /sources, /run, /reports CRUD, /export over a whitelisted data-source registry (services/report_sources)`. Add a line under the reports section noting the registry pattern.
- [ ] **Step 2:** In `README.md` features list, add "Report Builder — user-configurable reports (column chooser, click-to-filter, grouping/totals, saved views, CSV/XLSX export)".
- [ ] **Step 3:** In `USER_GUIDE.md` add a "Report Builder" section under Reports: choosing a source, picking columns, click-to-filter, grouping/totals, saving (private/shared), export.
- [ ] **Step 4:** In `WORKFLOW.md` reports table add a Report Builder row (endpoint `POST /api/report-builder/run`).
- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md USER_GUIDE.md WORKFLOW.md
git commit -m "docs(reports): document the dynamic report builder

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6.2: Demo seed + final verification

**Files:**
- Modify: `backend/scripts/seed_demo.py`

- [ ] **Step 1:** Add 1–2 starter saved reports per demo tenant in `seed_demo.py` (idempotent — skip if a `ReportDefinition` with the same name+tenant exists). Example config: an "Outstanding Invoices" shared report on `invoices` filtered `status in [sent, partial]`, columns `[number, customer_name, due_date, total]`, grouped by `customer_name` with `sum(total)`.

```python
# inside the per-tenant seed, after invoices exist:
from models import ReportDefinition
import json
existing = session.exec(select(ReportDefinition).where(
    ReportDefinition.tenant_id == tenant.id,
    ReportDefinition.name == "Outstanding Invoices")).first()
if not existing:
    session.add(ReportDefinition(
        tenant_id=tenant.id, name="Outstanding Invoices", source_key="invoices",
        visibility="shared", owner_id=admin_user.id,
        config=json.dumps({"columns": ["number", "customer_name", "due_date", "total"],
                           "filters": [{"field": "status", "op": "in", "value": ["sent", "partial"]}],
                           "sort": [{"field": "due_date", "dir": "asc"}],
                           "group_by": ["customer_name"],
                           "aggregates": [{"field": "total", "fn": "sum"}], "date_range": None}),
        created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
```

- [ ] **Step 2: Re-seed + full backend suite**

Run: `cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo && uv run pytest`
Expected: seeder runs clean; full suite green.

- [ ] **Step 3: Frontend build**

Run: `cd frontend && npm run lint && npx tsc --noEmit && npm run build`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/seed_demo.py
git commit -m "feat(reports): seed a starter saved report per demo tenant

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: Finish the branch** — use `superpowers:finishing-a-development-branch` to verify tests, then open a PR.

---

## Self-review notes (coverage check)

- **Spec §1 registry** → Tasks 1.1–1.2 (all 9 sources + REGISTRY). ✅
- **Spec §2 storage / ReportConfig** → Task 1.3 (config), 3.1 (table+migration). ✅
- **Spec §3 engine (tenant inject, registry-resolve, group/aggregate, pagination)** → Tasks 1.4–1.5. ✅
- **Spec §3 endpoints** (`/sources`,`/run`,`/reports`,`/export`) → Tasks 2.1, 3.2, 4.1. ✅
- **Spec §4 frontend** (grid + 5 controls + page + sidebar) → Tasks 5.1–5.4. ✅
- **Spec §5 tests** (engine units, safety/isolation, run, CRUD, export, frontend gate) → Tasks 1.3–1.5, 2.1–2.2, 3.2, 4.1, 5.x. ✅
- **Docs + demo seed** → Tasks 6.1–6.2. ✅
- **Type consistency:** `ReportConfig`/`FilterClause`/`Aggregate`/`run_report`/`ReportResult`/`ColumnMeta` names match across backend tasks; TS `ReportConfig`/`RunResult`/`SourceMeta` match the JSON the endpoints emit. ✅
