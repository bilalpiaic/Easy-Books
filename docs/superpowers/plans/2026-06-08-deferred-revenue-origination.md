# Deferred Revenue Origination (#47) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `Product.is_deferred` into invoicing so a deferred line credits Deferred Revenue (2300) instead of Sales Revenue, creates a per-line `DeferredRevenueSchedule`, and rebuilds/blocks correctly on edit — reusing the existing recognition engine.

**Architecture:** A new pure-logic module `backend/services/deferred.py` owns deferral classification, the revenue/deferred split, account resolution, and the schedule lifecycle. `create_invoice` and `update_invoice` both call it, so the two paths cannot diverge. GST is never deferred (tax point = invoice date). No schema change — all model fields already exist.

**Tech Stack:** FastAPI, SQLModel, SQLite (dev) / Postgres (prod), pytest. Money via `services/money.py` (`D`, `money`, `ZERO`). GL via `services/posting.py` (`EntryInput`, `post_transaction`).

**Spec:** `docs/superpowers/specs/2026-06-08-deferred-revenue-origination-design.md`

**Coordination note:** This branch (`feature/issue47-deferred-revenue-origination`) is based on `main`, which does **not** yet contain the #48 fix (open as PR #54). Both #47 and #48 modify `update_invoice`. If PR #54 merges first, rebase this branch onto updated `main`; the GL-split insert in Task 6 goes in the re-post block (after `inv.transaction_id = txn.id`), which #48 does not touch, so the conflict is mechanical.

---

## File Structure

| File | Responsibility | Tasks |
|------|----------------|-------|
| `backend/routers/products.py` | Accept `is_deferred` + `recognition_months` on product create/update | 1 |
| `backend/services/deferred.py` (new) | `_add_months`, `plan_deferral`, `resolve_deferred_account`, `create_schedules`, `has_any_recognition`, `reverse_schedules` | 2,3,4 |
| `backend/routers/deferred_revenue.py` | Import `_add_months` from the service (dedup) | 2 |
| `backend/routers/invoices.py` `create_invoice` | Revenue/deferred GL split + schedule creation | 5 |
| `backend/routers/invoices.py` `update_invoice` | Block-if-recognized guard; reverse + rebuild schedules; split on re-post | 6 |
| `backend/tests/test_deferred_service.py` (new) | Unit tests for the service | 2,3,4 |
| `backend/tests/test_deferred_invoice_origination.py` (new) | Integration: create posts split + schedule | 5 |
| `backend/tests/test_deferred_invoice_edit.py` (new) | Integration: edit rebuild/block | 6 |
| `backend/tests/test_deferred_recognition_e2e.py` (new) | Integration: existing engine recognizes an originated schedule | 7 |
| `frontend/src/app/(dashboard)/products/page.tsx` | Expose deferred checkbox + months input | 8 |

**Run tests from `backend/` with `PYTHONPATH=.` (conftest imports `db` as a top-level module).**

---

### Task 1: Product schema accepts deferral flags

**Files:**
- Modify: `backend/routers/products.py` (`ProductCreate`, ~line 17-27)
- Test: `backend/tests/test_deferred_service.py` (new — first test goes here)

`create_product` does `Product(**body.model_dump())` and `update_product` does `setattr` per field, so adding the two fields to `ProductCreate` persists them on both create and update with no further change.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_deferred_service.py`:

```python
"""Unit + schema tests for deferred-revenue origination (#47)."""
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db as _db_module
from models import Product, Tenant


def test_product_create_accepts_deferred_flags(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h, json={
        "name": "Support Plan", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": 24,
    }).json()
    got = client.get(f"/api/products/{p['id']}", headers=h).json()
    assert got["is_deferred"] is True
    assert got["recognition_months"] == 24
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_service.py::test_product_create_accepts_deferred_flags -v`
Expected: FAIL — `is_deferred` is dropped by `ProductCreate` (returns default `False`/`12`).

- [ ] **Step 3: Add the fields to `ProductCreate`**

In `backend/routers/products.py`, add to `ProductCreate` (after `category_id`):

```python
    is_deferred: bool = False
    recognition_months: int = 12
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_service.py::test_product_create_accepts_deferred_flags -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routers/products.py backend/tests/test_deferred_service.py
git commit -m "feat(products): accept is_deferred + recognition_months on create/update (#47)"
```

---

### Task 2: `services/deferred.py` — `_add_months` (moved from router)

**Files:**
- Create: `backend/services/deferred.py`
- Modify: `backend/routers/deferred_revenue.py` (import `_add_months` from the service)
- Test: `backend/tests/test_deferred_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_deferred_service.py`:

```python
def test_add_months_advances_date():
    from services.deferred import _add_months
    assert _add_months("2026-01-31", 1) == "2026-02-28"   # clamps to month end
    assert _add_months("2026-03-01", 12) == "2027-03-01"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_service.py::test_add_months_advances_date -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.deferred'`

- [ ] **Step 3: Create the module with `_add_months`**

Create `backend/services/deferred.py`:

```python
"""Deferred-revenue origination (#47): classify deferred invoice lines, split
the revenue credit between Sales Revenue and Deferred Revenue (2300), and
manage the per-line DeferredRevenueSchedule lifecycle. Shared by create_invoice
and update_invoice so the two paths cannot diverge.

GST is never deferred — only net line revenue is parked in 2300. Recognition
itself is unchanged: the existing /api/deferred-revenue/run-recognition engine
posts Dr 2300 / Cr Revenue over each schedule's window.
"""
import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from models import Account, DeferredRevenueSchedule, Product
from services.money import D, ZERO, money


def _add_months(date_str: str, months: int) -> str:
    """Advance a YYYY-MM-DD date by `months` months, clamping to month end."""
    d = date.fromisoformat(date_str)
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()
```

- [ ] **Step 4: Point the router at the shared helper**

In `backend/routers/deferred_revenue.py`: delete its local `_add_months` function (the `def _add_months(...)` block and its `import calendar`) and add to the imports:

```python
from services.deferred import _add_months
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_service.py::test_add_months_advances_date tests/ -k deferred -v`
Expected: PASS. Also run the recognition router's existing tests if any: `PYTHONPATH=. uv run pytest -k recognition -v` → PASS (no regression from the move).

- [ ] **Step 6: Commit**

```bash
git add backend/services/deferred.py backend/routers/deferred_revenue.py backend/tests/test_deferred_service.py
git commit -m "refactor(deferred): extract _add_months into services/deferred.py (#47)"
```

---

### Task 3: `plan_deferral` + `resolve_deferred_account`

**Files:**
- Modify: `backend/services/deferred.py`
- Test: `backend/tests/test_deferred_service.py`

`plan_deferral` classifies lines by `product.is_deferred` and returns the deferred per-line specs plus `deferred_net_base` (sum of deferred line nets). The caller derives `revenue_net_base = subtotal_base - deferred_net_base` so the GL always balances (avoids per-line rounding drift).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_deferred_service.py`:

```python
@pytest.fixture
def dsession():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Tenant(id=1, name="T1"))
        s.commit()
        yield s


def _add_product(s, *, is_deferred, months=12, rev_acct=None):
    p = Product(tenant_id=1, name="P", product_type="service",
                is_deferred=is_deferred, recognition_months=months,
                revenue_account_id=rev_acct)
    s.add(p); s.commit(); s.refresh(p)
    return p


def test_plan_deferral_splits_deferred_and_normal(dsession):
    from types import SimpleNamespace
    from services.deferred import plan_deferral
    s = dsession
    pd = _add_product(s, is_deferred=True, months=24, rev_acct=7)
    pn = _add_product(s, is_deferred=False)
    lines = [
        SimpleNamespace(product_id=pd.id, qty=Decimal("2"), rate=Decimal("50")),  # 100 deferred
        SimpleNamespace(product_id=pn.id, qty=Decimal("1"), rate=Decimal("30")),  # 30 normal
        SimpleNamespace(product_id=None,  qty=Decimal("1"), rate=Decimal("10")),  # 10 normal (no product)
    ]
    plan = plan_deferral(s, tenant_id=1, lines=lines, fx_rate=Decimal("1"))
    assert plan.deferred_net_base == money(Decimal("100"))
    assert len(plan.deferred_lines) == 1
    assert plan.deferred_lines[0].recognition_months == 24
    assert plan.deferred_lines[0].revenue_account_id == 7
    assert plan.deferred_lines[0].net_base == money(Decimal("100"))


def test_plan_deferral_none_deferred(dsession):
    from types import SimpleNamespace
    from services.deferred import plan_deferral
    s = dsession
    pn = _add_product(s, is_deferred=False)
    lines = [SimpleNamespace(product_id=pn.id, qty=Decimal("3"), rate=Decimal("10"))]
    plan = plan_deferral(s, tenant_id=1, lines=lines, fx_rate=Decimal("1"))
    assert plan.deferred_net_base == ZERO
    assert plan.deferred_lines == []


def test_plan_deferral_floors_months_at_one(dsession):
    from types import SimpleNamespace
    from services.deferred import plan_deferral
    s = dsession
    pd = _add_product(s, is_deferred=True, months=0)
    lines = [SimpleNamespace(product_id=pd.id, qty=Decimal("1"), rate=Decimal("10"))]
    plan = plan_deferral(s, tenant_id=1, lines=lines, fx_rate=Decimal("1"))
    assert plan.deferred_lines[0].recognition_months == 1


def test_resolve_deferred_account_defaults_to_2300(dsession):
    from services.deferred import resolve_deferred_account
    acc = resolve_deferred_account(dsession, tenant_id=1)
    assert acc.code == "2300"
    assert acc.type == "Liability"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_service.py -k "plan_deferral or resolve_deferred" -v`
Expected: FAIL — `ImportError: cannot import name 'plan_deferral'`

- [ ] **Step 3: Implement `plan_deferral` + `resolve_deferred_account`**

Append to `backend/services/deferred.py`:

```python
@dataclass
class LineDeferral:
    net_base: Decimal
    recognition_months: int
    revenue_account_id: int | None


@dataclass
class DeferralPlan:
    deferred_lines: list[LineDeferral] = field(default_factory=list)
    deferred_net_base: Decimal = ZERO


def plan_deferral(session: Session, tenant_id: int, lines, fx_rate: Decimal) -> DeferralPlan:
    """Classify lines by product.is_deferred. Returns the deferred per-line specs
    and their summed net (base currency). Lines with no product, or a
    non-deferred product, are ignored here (they stay as normal revenue)."""
    plan = DeferralPlan()
    for ln in lines:
        if not getattr(ln, "product_id", None):
            continue
        prod = session.exec(
            select(Product).where(
                Product.id == ln.product_id, Product.tenant_id == tenant_id
            )
        ).first()
        if not prod or not prod.is_deferred:
            continue
        net_base = money(D(ln.qty) * D(ln.rate) * D(fx_rate))
        if net_base <= ZERO:
            continue
        plan.deferred_lines.append(LineDeferral(
            net_base=net_base,
            recognition_months=max(1, int(prod.recognition_months or 0)),
            revenue_account_id=prod.revenue_account_id,
        ))
        plan.deferred_net_base = money(plan.deferred_net_base + net_base)
    return plan


def resolve_deferred_account(session: Session, tenant_id: int) -> Account:
    """Tenant's Deferred Revenue account: settings override → 2300 → auto-create."""
    from routers.common import get_default_account
    return get_default_account(
        session, tenant_id, "default_deferred_revenue_account",
        "2300", "Deferred Revenue", "Liability",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_service.py -k "plan_deferral or resolve_deferred" -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/deferred.py backend/tests/test_deferred_service.py
git commit -m "feat(deferred): plan_deferral classification + deferred-account resolution (#47)"
```

---

### Task 4: `create_schedules`, `has_any_recognition`, `reverse_schedules`

**Files:**
- Modify: `backend/services/deferred.py`
- Test: `backend/tests/test_deferred_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_deferred_service.py`:

```python
def _add_account(s, code, typ="Liability"):
    a = Account(tenant_id=1, code=code, name=code, type=typ)
    s.add(a); s.commit(); s.refresh(a)
    return a


def test_create_schedules_one_row_per_deferred_line(dsession):
    from types import SimpleNamespace
    from services.deferred import plan_deferral, create_schedules, LineDeferral, DeferralPlan
    from models import DeferredRevenueSchedule
    s = dsession
    _add_account(s, "2300")
    rev = _add_account(s, "4000", "Revenue")
    plan = DeferralPlan(
        deferred_lines=[LineDeferral(net_base=money(Decimal("120")), recognition_months=12, revenue_account_id=rev.id)],
        deferred_net_base=money(Decimal("120")),
    )
    inv = SimpleNamespace(id=99, issue_date="2026-03-01")
    user = SimpleNamespace(tenant_id=1)
    rows = create_schedules(s, user, inv, plan)
    assert len(rows) == 1
    sch = s.exec(select(DeferredRevenueSchedule).where(DeferredRevenueSchedule.invoice_id == 99)).all()
    assert len(sch) == 1
    assert sch[0].total_amount == money(Decimal("120"))
    assert sch[0].start_date == "2026-03-01"
    assert sch[0].end_date == "2027-03-01"
    assert sch[0].revenue_account_id == rev.id
    assert sch[0].status == "active"


def test_has_any_recognition_and_reverse(dsession):
    from services.deferred import has_any_recognition, reverse_schedules
    from models import DeferredRevenueSchedule
    s = dsession
    a23 = _add_account(s, "2300"); a40 = _add_account(s, "4000", "Revenue")
    s.add(DeferredRevenueSchedule(
        tenant_id=1, invoice_id=99, total_amount=money(Decimal("120")),
        recognised_amount=ZERO, start_date="2026-03-01", end_date="2027-03-01",
        frequency="monthly", next_recognition_date="2026-03-01", status="active",
        deferred_revenue_account_id=a23.id, revenue_account_id=a40.id,
    ))
    s.commit()
    assert has_any_recognition(s, 1, 99) is False
    # Recognise part of it
    row = s.exec(select(DeferredRevenueSchedule).where(DeferredRevenueSchedule.invoice_id == 99)).first()
    row.recognised_amount = money(Decimal("10")); s.add(row); s.commit()
    assert has_any_recognition(s, 1, 99) is True
    # reverse_schedules deletes rows for the invoice
    reverse_schedules(s, 1, 99); s.commit()
    assert s.exec(select(DeferredRevenueSchedule).where(DeferredRevenueSchedule.invoice_id == 99)).all() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_service.py -k "create_schedules or has_any or reverse" -v`
Expected: FAIL — `ImportError: cannot import name 'create_schedules'`

- [ ] **Step 3: Implement the three functions**

Append to `backend/services/deferred.py`:

```python
def create_schedules(session: Session, user, invoice, plan: DeferralPlan) -> list:
    """One DeferredRevenueSchedule per deferred line, all sharing invoice.id.
    Amounts are base currency. Revenue recognises to the product's revenue
    account (fallback 4000)."""
    deferred_acc = resolve_deferred_account(session, user.tenant_id)
    default_rev = None
    rows = []
    for spec in plan.deferred_lines:
        rev_id = spec.revenue_account_id
        if rev_id is None:
            if default_rev is None:
                from routers.common import get_default_account
                default_rev = get_default_account(
                    session, user.tenant_id, "default_revenue_account",
                    "4000", "Sales Revenue", "Revenue",
                )
            rev_id = default_rev.id
        sch = DeferredRevenueSchedule(
            tenant_id=user.tenant_id,
            invoice_id=invoice.id,
            total_amount=spec.net_base,
            recognised_amount=ZERO,
            start_date=invoice.issue_date,
            end_date=_add_months(invoice.issue_date, spec.recognition_months),
            frequency="monthly",
            next_recognition_date=invoice.issue_date,
            status="active",
            deferred_revenue_account_id=deferred_acc.id,
            revenue_account_id=rev_id,
        )
        session.add(sch)
        rows.append(sch)
    session.flush()
    return rows


def has_any_recognition(session: Session, tenant_id: int, invoice_id: int) -> bool:
    """True if any schedule for the invoice has recognised revenue."""
    rows = session.exec(
        select(DeferredRevenueSchedule).where(
            DeferredRevenueSchedule.tenant_id == tenant_id,
            DeferredRevenueSchedule.invoice_id == invoice_id,
        )
    ).all()
    return any(D(r.recognised_amount) > ZERO for r in rows)


def reverse_schedules(session: Session, tenant_id: int, invoice_id: int) -> None:
    """Delete the invoice's (un-recognized) schedule rows ahead of a rebuild."""
    rows = session.exec(
        select(DeferredRevenueSchedule).where(
            DeferredRevenueSchedule.tenant_id == tenant_id,
            DeferredRevenueSchedule.invoice_id == invoice_id,
        )
    ).all()
    for r in rows:
        session.delete(r)
    session.flush()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_service.py -v`
Expected: PASS (all service tests green)

- [ ] **Step 5: Commit**

```bash
git add backend/services/deferred.py backend/tests/test_deferred_service.py
git commit -m "feat(deferred): schedule create/reverse + recognition guard (#47)"
```

---

### Task 5: `create_invoice` — GL split + schedule creation

**Files:**
- Modify: `backend/routers/invoices.py` `create_invoice` (revenue-credit block, ~lines 308-344)
- Test: `backend/tests/test_deferred_invoice_origination.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_deferred_invoice_origination.py`:

```python
"""Invoicing a deferred product credits Deferred Revenue + builds a schedule (#47)."""
from decimal import Decimal

from sqlmodel import Session, select

import db as _db_module
from models import Account, DeferredRevenueSchedule, JournalEntry
from services.money import D


def _credits_to(code):
    with Session(_db_module.engine) as s:
        acc = s.exec(select(Account).where(Account.code == code)).first()
        if not acc:
            return 0.0
        rows = s.exec(select(JournalEntry).where(JournalEntry.account_id == acc.id)).all()
        return float(sum(D(r.credit) for r in rows))


def _mk_deferred_product(client, h, months=12):
    return client.post("/api/products", headers=h, json={
        "name": "Support", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": months,
    }).json()


def test_deferred_line_credits_2300_not_revenue(client, admin_headers):
    h = admin_headers
    p = _mk_deferred_product(client, h, months=12)
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 1, "rate": 120}],
    })
    assert r.status_code in (200, 201), r.text
    assert _credits_to("2300") == 120.0      # net parked in Deferred Revenue
    assert _credits_to("4000") == 0.0        # nothing in Sales Revenue
    with Session(_db_module.engine) as s:
        sch = s.exec(select(DeferredRevenueSchedule)).all()
    assert len(sch) == 1
    assert sch[0].start_date == "2026-03-01"
    assert sch[0].end_date == "2027-03-01"


def test_mixed_invoice_splits_revenue_and_keeps_gst(client, admin_headers):
    h = admin_headers
    pd = _mk_deferred_product(client, h)
    pn = client.post("/api/products", headers=h, json={
        "name": "Setup", "product_type": "service", "default_rate": 80,
    }).json()
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 10,
        "lines": [
            {"product_id": pd["id"], "description": "Support", "qty": 1, "rate": 120},
            {"product_id": pn["id"], "description": "Setup",   "qty": 1, "rate": 80},
        ],
    })
    assert r.status_code in (200, 201), r.text
    assert _credits_to("2300") == 120.0      # deferred net
    assert _credits_to("4000") == 80.0       # normal net
    assert _credits_to("2200") == 20.0       # GST on 200 @ 10% — posted immediately


def test_non_deferred_invoice_unchanged(client, admin_headers):
    h = admin_headers
    pn = client.post("/api/products", headers=h, json={
        "name": "Setup", "product_type": "service", "default_rate": 80,
    }).json()
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": pn["id"], "description": "Setup", "qty": 1, "rate": 80}],
    })
    assert r.status_code in (200, 201), r.text
    assert _credits_to("4000") == 80.0
    assert _credits_to("2300") == 0.0
    with Session(_db_module.engine) as s:
        assert s.exec(select(DeferredRevenueSchedule)).all() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_invoice_origination.py -v`
Expected: FAIL — `test_deferred_line_credits_2300_not_revenue` and the mixed test fail (everything still credits 4000; no schedule row). `test_non_deferred_invoice_unchanged` passes already.

- [ ] **Step 3: Add the import**

In `backend/routers/invoices.py`, near the other service imports (top of file):

```python
from services.deferred import plan_deferral, resolve_deferred_account, create_schedules
```

- [ ] **Step 4: Replace the revenue-credit block in `create_invoice`**

Find this block (the `rev_acc = …` resolution through the `entries = [...]` if/elif/else, ~lines 308-332):

```python
    rev_acc = (
        session.get(Account, body.revenue_account_id)
        if body.revenue_account_id
        else get_default_account(session, user.tenant_id, "default_revenue_account", "4000", "Sales Revenue", "Revenue")
    )

    # Convert document amounts → base currency for GL posting.
    total_base = money(total * fx_rate)
    subtotal_base = money(subtotal * fx_rate)
    gst_base = money(gst_amount * fx_rate)

    entries = [EntryInput(account_id=ar_acc.id, debit=total_base)]
    if use_per_line_tax and per_gl_tax:
        # Post each distinct tax GL account separately.
        entries.append(EntryInput(account_id=rev_acc.id, credit=subtotal_base))
        for gl_id, tax_amt in per_gl_tax.items():
            entries.append(EntryInput(account_id=gl_id, credit=money(tax_amt * fx_rate)))
    elif gst_amount > 0:
        gst_acc = get_or_create_account(
            session, user.tenant_id, "2200", "GST Payable (Output)", "Liability"
        )
        entries.append(EntryInput(account_id=rev_acc.id, credit=subtotal_base))
        entries.append(EntryInput(account_id=gst_acc.id, credit=gst_base))
    else:
        entries.append(EntryInput(account_id=rev_acc.id, credit=total_base))
```

Replace it with (revenue credit split; tax entries unchanged):

```python
    rev_acc = (
        session.get(Account, body.revenue_account_id)
        if body.revenue_account_id
        else get_default_account(session, user.tenant_id, "default_revenue_account", "4000", "Sales Revenue", "Revenue")
    )

    # Convert document amounts → base currency for GL posting.
    total_base = money(total * fx_rate)
    subtotal_base = money(subtotal * fx_rate)
    gst_base = money(gst_amount * fx_rate)

    # Split the net revenue credit between Sales Revenue and Deferred Revenue
    # (2300) for any is_deferred product lines. revenue_net is derived from
    # subtotal_base so the split always balances. GST is never deferred.
    deferral = plan_deferral(session, user.tenant_id, body.lines, fx_rate)
    revenue_net_base = money(subtotal_base - deferral.deferred_net_base)

    entries = [EntryInput(account_id=ar_acc.id, debit=total_base)]
    if revenue_net_base > ZERO:
        entries.append(EntryInput(account_id=rev_acc.id, credit=revenue_net_base))
    if deferral.deferred_net_base > ZERO:
        deferred_acc = resolve_deferred_account(session, user.tenant_id)
        entries.append(EntryInput(account_id=deferred_acc.id, credit=deferral.deferred_net_base))

    if use_per_line_tax and per_gl_tax:
        for gl_id, tax_amt in per_gl_tax.items():
            entries.append(EntryInput(account_id=gl_id, credit=money(tax_amt * fx_rate)))
    elif gst_amount > 0:
        gst_acc = get_or_create_account(
            session, user.tenant_id, "2200", "GST Payable (Output)", "Liability"
        )
        entries.append(EntryInput(account_id=gst_acc.id, credit=gst_base))
```

- [ ] **Step 5: Create schedules after the main txn is posted**

Immediately after `invoice.transaction_id = txn.id` / `session.add(invoice)` (right before the COGS `if total_cogs > 0:` block, ~line 345), insert:

```python
    if deferral.deferred_net_base > ZERO:
        create_schedules(session, user, invoice, deferral)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_invoice_origination.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Run adjacent invoice suites (regression)**

Run: `PYTHONPATH=. uv run pytest tests/ -k "invoice or oversell or tax" -v`
Expected: PASS — existing invoice/tax/GL behavior unchanged.

- [ ] **Step 8: Commit**

```bash
git add backend/routers/invoices.py backend/tests/test_deferred_invoice_origination.py
git commit -m "feat(invoices): split revenue to Deferred Revenue + create schedules on deferred lines (#47)"
```

---

### Task 6: `update_invoice` — block-if-recognized, rebuild, split on re-post

**Files:**
- Modify: `backend/routers/invoices.py` `update_invoice` (guard near line 401; re-post block ~lines 619-627; schedule rebuild after re-post)
- Test: `backend/tests/test_deferred_invoice_edit.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_deferred_invoice_edit.py`:

```python
"""Editing a posted invoice with deferred lines: rebuild before recognition,
block after (#47)."""
from decimal import Decimal

from sqlmodel import Session, select

import db as _db_module
from models import Account, DeferredRevenueSchedule, JournalEntry
from services.money import D, money


def _credits_to(code):
    with Session(_db_module.engine) as s:
        acc = s.exec(select(Account).where(Account.code == code)).first()
        if not acc:
            return 0.0
        rows = s.exec(select(JournalEntry).where(JournalEntry.account_id == acc.id)).all()
        return float(sum(D(r.credit) for r in rows))


def _mk(client, h):
    p = client.post("/api/products", headers=h, json={
        "name": "Support", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": 12,
    }).json()
    inv = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 1, "rate": 120}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    return p, inv


def _schedules():
    with Session(_db_module.engine) as s:
        return s.exec(select(DeferredRevenueSchedule)).all()


def test_edit_before_recognition_rebuilds_schedule(client, admin_headers):
    h = admin_headers
    p, inv = _mk(client, h)
    assert len(_schedules()) == 1 and float(_schedules()[0].total_amount) == 120.0
    # Edit qty 1 → 2 (now 240 deferred)
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 2, "rate": 120}],
    })
    assert r.status_code in (200, 201), r.text
    sch = _schedules()
    assert len(sch) == 1                       # replaced, not duplicated
    assert float(sch[0].total_amount) == 240.0
    # Net deferred credit after reversal+repost = 240 (original 120 reversed by the
    # main-JV reversal, new 240 posted).
    assert _credits_to("2300") - _debits_to_2300() == 240.0


def _debits_to_2300():
    with Session(_db_module.engine) as s:
        acc = s.exec(select(Account).where(Account.code == "2300")).first()
        rows = s.exec(select(JournalEntry).where(JournalEntry.account_id == acc.id)).all()
        return float(sum(D(r.debit) for r in rows))


def test_edit_after_recognition_is_blocked(client, admin_headers):
    h = admin_headers
    p, inv = _mk(client, h)
    # Recognise one month so recognised_amount > 0
    rr = client.post("/api/deferred-revenue/run-recognition?recognition_date=2026-03-15", headers=h)
    assert rr.status_code == 200, rr.text
    assert any(float(s.recognised_amount) > 0 for s in _schedules())
    # Now editing must be blocked
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 2, "rate": 120}],
    })
    assert r.status_code == 400, r.text
    assert "recogni" in r.json()["detail"].lower()
    # Schedule untouched
    assert float(_schedules()[0].total_amount) == 120.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_invoice_edit.py -v`
Expected: FAIL — edit doesn't rebuild (no schedule split logic in update path) and isn't blocked after recognition.

- [ ] **Step 3: Add the import**

Ensure `backend/routers/invoices.py` imports the edit helpers (extend the Task 5 import line):

```python
from services.deferred import (
    plan_deferral, resolve_deferred_account, create_schedules,
    has_any_recognition, reverse_schedules,
)
```

- [ ] **Step 4: Add the block-if-recognized guard**

In `update_invoice`, right after the `assert_doc_editable(...)` call (~line 401), add:

```python
    if has_any_recognition(session, user.tenant_id, inv.id):
        raise HTTPException(
            400,
            "Cannot edit: revenue already recognized for this invoice's deferred "
            "schedule. Void and reissue instead.",
        )
```

- [ ] **Step 5: Split the revenue credit in the re-post block**

Find the re-post block in `update_invoice` (~lines 619-627):

```python
    entries = [EntryInput(account_id=ar_acc.id, debit=total_base)]
    if gst_amount > 0:
        gst_acc = get_or_create_account(
            session, user.tenant_id, "2200", "GST Payable (Output)", "Liability"
        )
        entries.append(EntryInput(account_id=rev_acc.id, credit=subtotal_base))
        entries.append(EntryInput(account_id=gst_acc.id, credit=gst_base))
    else:
        entries.append(EntryInput(account_id=rev_acc.id, credit=total_base))
```

Replace with:

```python
    deferral = plan_deferral(session, user.tenant_id, body.lines, fx_rate)
    revenue_net_base = money(subtotal_base - deferral.deferred_net_base)

    entries = [EntryInput(account_id=ar_acc.id, debit=total_base)]
    if revenue_net_base > ZERO:
        entries.append(EntryInput(account_id=rev_acc.id, credit=revenue_net_base))
    if deferral.deferred_net_base > ZERO:
        deferred_acc = resolve_deferred_account(session, user.tenant_id)
        entries.append(EntryInput(account_id=deferred_acc.id, credit=deferral.deferred_net_base))
    if gst_amount > ZERO:
        gst_acc = get_or_create_account(
            session, user.tenant_id, "2200", "GST Payable (Output)", "Liability"
        )
        entries.append(EntryInput(account_id=gst_acc.id, credit=gst_base))
```

- [ ] **Step 6: Rebuild schedules after re-post**

Immediately after `inv.transaction_id = txn.id` / `session.add(inv)` in the re-post section (~line 639, before the COGS block), insert:

```python
    # The old deferred credit was reversed with the main-JV reversal above; the
    # old (un-recognized) schedule rows are stale, so drop and rebuild them.
    reverse_schedules(session, user.tenant_id, inv.id)
    if deferral.deferred_net_base > ZERO:
        create_schedules(session, user, inv, deferral)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_invoice_edit.py -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Run invoice-edit regression suites**

Run: `PYTHONPATH=. uv run pytest tests/ -k "edit_posted or deferred" -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/routers/invoices.py backend/tests/test_deferred_invoice_edit.py
git commit -m "feat(invoices): rebuild deferred schedules on edit, block once recognized (#47)"
```

---

### Task 7: Recognition end-to-end on an originated schedule

**Files:**
- Test only: `backend/tests/test_deferred_recognition_e2e.py` (new)

Verifies the existing engine recognizes a schedule that origination (not the seeder) produced. No production code expected — if this fails, the bug is in Task 5's schedule fields.

- [ ] **Step 1: Write the test**

Create `backend/tests/test_deferred_recognition_e2e.py`:

```python
"""The existing run-recognition engine recognizes an origination-built schedule (#47)."""
from sqlmodel import Session, select

import db as _db_module
from models import DeferredRevenueSchedule


def test_recognition_advances_originated_schedule(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h, json={
        "name": "Support", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": 12,
    }).json()
    client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 1, "rate": 120}],
    })
    r = client.post("/api/deferred-revenue/run-recognition?recognition_date=2026-03-31", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["recognised_count"] == 1
    with Session(_db_module.engine) as s:
        sch = s.exec(select(DeferredRevenueSchedule)).first()
    assert float(sch.recognised_amount) == 10.0   # 120 / 12 months
```

- [ ] **Step 2: Run the test**

Run: `PYTHONPATH=. uv run pytest tests/test_deferred_recognition_e2e.py -v`
Expected: PASS. If it fails on the recognized amount, re-check `end_date`/`next_recognition_date` from Task 4.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_deferred_recognition_e2e.py
git commit -m "test(deferred): recognition engine works on originated schedule (#47)"
```

---

### Task 8: Frontend — expose deferred flags on the product form

**Files:**
- Modify: `frontend/src/app/(dashboard)/products/page.tsx`

The backend now persists `is_deferred` + `recognition_months`; the create/edit product form must let users set them. Locate the product form state/inputs in this file (search for the `default_rate` input and the form-state object the modal uses) and follow the same pattern.

- [ ] **Step 1: Add the fields to the form**

In the product form-state object, add `is_deferred: false` and `recognition_months: 12` defaults, and include them in the create/update payload sent to `/api/products`. Add two inputs alongside the existing fields (match the surrounding Tailwind/`lucide-react` style):

```tsx
<label className="flex items-center gap-2">
  <input
    type="checkbox"
    checked={form.is_deferred}
    onChange={(e) => setForm({ ...form, is_deferred: e.target.checked })}
  />
  Deferred revenue (recognize over time)
</label>
{form.is_deferred && (
  <label className="block">
    Recognition months
    <input
      type="number"
      min={1}
      value={form.recognition_months}
      onChange={(e) => setForm({ ...form, recognition_months: Number(e.target.value) })}
      className="..."  /* copy className from the default_rate input */
    />
  </label>
)}
```

(Adapt `form`/`setForm` names to whatever the file uses — e.g. a `useState` object or individual states. If editing an existing product, hydrate these two fields from the fetched product like the other fields are hydrated.)

- [ ] **Step 2: Verify the build compiles**

Run: `cd frontend && npm run lint`
Expected: no new errors in `products/page.tsx`.

- [ ] **Step 3: Manual check (optional)**

If running the app: create a product with the checkbox on, set months to 24, save, reopen — the values persist (backend Task 1 already verified server-side).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\(dashboard\)/products/page.tsx
git commit -m "feat(products-ui): deferred-revenue checkbox + recognition months (#47)"
```

---

### Task 9: Full verification

- [ ] **Step 1: Run the entire backend suite**

Run: `cd backend && PYTHONPATH=. uv run pytest -q`
Expected: all pass (existing 303 + the new deferred tests). No new warnings beyond the pre-existing `utcnow` deprecations.

- [ ] **Step 2: Update the roadmap**

In `docs/ROADMAP.md`, move #47 from "Not started" to done, noting deferred-revenue origination shipped. (If this branch was rebased onto a `main` that already has the #48 re-scope text from PR #54, edit that entry; otherwise add the done note.)

- [ ] **Step 3: Commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs(roadmap): #47 deferred-revenue origination shipped"
```

---

## Self-Review notes

- **Spec coverage:** §1 (no schema change) → Tasks confirm via reuse; §2 service module → Tasks 2-4; §3 create split → Task 5; §4 edit guard/rebuild → Task 6; §5 edge cases (mixed, floor months, base currency, telecom caveat) → Tasks 3/5 tests + `resolve_deferred_account`; §6 testing → Tasks 2-7; §7 frontend → Task 8.
- **Rounding:** `revenue_net_base = subtotal_base − deferred_net_base` (not an independent sum) guarantees the split balances the AR debit.
- **Edit GL:** no separate deferred-reversal JV — the deferred credit rides inside the main invoice JV that the edit already reverses; only schedule rows are explicitly rebuilt.
