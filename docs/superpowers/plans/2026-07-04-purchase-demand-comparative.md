# Purchase Demand + Comparative Statement (#137 Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the front half of the procure-to-pay chain — Purchase Demand → Vendor Quotations → Comparative Statement → PO — as the first slice of the installable `purchase_store` module, with real internal controls (approver ≠ creator, lowest-or-justify, setting-gated chain enforcement).

**Architecture:** Five new tenant-scoped SQLModel tables + two nullable columns on `PurchaseOrder`; three new FastAPI routers mirroring the existing `purchase_orders.py` idioms (`next_number`, `log_audit`, `perm_dep`, status CheckConstraints); `purchase_store` registered in `MODULE_REGISTRY`; frontend gets a Purchases nav section (new `notForModule` flag generalizes nav gating) and six pages including a comparative matrix builder. All Phase-1 documents are memo documents — **zero GL impact**.

**Tech Stack:** FastAPI + SQLModel + Alembic (backend), Next.js 16 / React 19 / Tailwind v4 / lucide-react (frontend), pytest.

**Spec:** `docs/superpowers/specs/2026-07-03-purchase-demand-comparative-design.md`

## Global Constraints

- Every query tenant-scoped: `.where(Model.tenant_id == user.tenant_id)` — no exceptions.
- Voucher numbers via `next_number(session, tenant_id, name, prefix, fmt="{prefix}-{YYYY}-{seq:04d}")` → `PD-2026-0001`, `VQ-2026-0001`, `CS-2026-0001`.
- Money fields use `Money = money_col()`; arithmetic through `services.money.D` / `money`.
- Every state change calls `log_audit(session, user, action, entity_type, entity_id, detail)`.
- New tables in Alembic migration get `bind.dialect.has_table(...)` guards; ALTERs adding FK columns have the FK line stripped (SQLite) — see migrations 0016/0017 for the pattern.
- Demand lines carry **no rate fields** (requester never sets prices).
- Frontend: `apiFetch` for all calls, `fmtDate` for all dates, lucide-react icons only, full-page forms (no modals), `print:hidden` on toolbars.
- Run backend tests with `PYTHONPATH=. uv run pytest` from `backend/`. 4 pre-existing failures on main (admin_demo/business_model/update_migration) are NOT yours to fix — compare against a baseline run.
- Work on branch `feat/purchase-demand-comparative` off `main`.

---

### Task 1: Models + Alembic migration

**Files:**
- Modify: `backend/models.py` (append after `PurchaseOrderLine`, ~line 907)
- Modify: `backend/models.py:873-896` (`PurchaseOrder` — 2 new columns)
- Create: `backend/alembic/versions/0029_purchase_demand_comparative.py` (via autogenerate, then edit)

**Interfaces:**
- Produces: `PurchaseDemand`, `PurchaseDemandLine`, `VendorQuotation`, `VendorQuotationLine`, `ComparativeStatement` models; `PurchaseOrder.demand_id`, `PurchaseOrder.comparative_id` (both `Optional[int]`). Table names (SQLModel defaults): `purchasedemand`, `purchasedemandline`, `vendorquotation`, `vendorquotationline`, `comparativestatement`.

- [ ] **Step 1: Create the branch**

```bash
cd /home/mbilal71/projects/Easy-Books && git checkout -b feat/purchase-demand-comparative main
```

- [ ] **Step 2: Add the five models to `backend/models.py`** (after `PurchaseOrderLine`):

```python
class PurchaseDemand(SQLModel, table=True):
    """Purchase requisition — quantity-only memo document (#137 Phase 1).
    Requester never sets prices; that segregation is the control."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_pd_number_per_tenant"),
        CheckConstraint(
            "status IN ('draft','approved','converted','closed','cancelled')",
            name="ck_pd_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    demand_date: str
    required_by: Optional[str] = None
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    purpose: Optional[str] = None
    notes: Optional[str] = None
    status: str = Field(default="draft")
    created_by_id: int = Field(foreign_key="user.id")
    approved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PurchaseDemandLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    demand_id: int = Field(foreign_key="purchasedemand.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None


class VendorQuotation(SQLModel, table=True):
    """One vendor's offer against an approved demand. Memo document."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_vq_number_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    demand_id: int = Field(foreign_key="purchasedemand.id", index=True)
    vendor_id: int = Field(foreign_key="vendor.id")
    quote_date: str
    valid_until: Optional[str] = None
    delivery_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VendorQuotationLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quotation_id: int = Field(foreign_key="vendorquotation.id", ondelete="CASCADE")
    demand_line_id: int = Field(foreign_key="purchasedemandline.id")
    rate: Money = money_col()
    qty: Money = money_col(default=Decimal("1"))
    amount: Money = money_col()


class ComparativeStatement(SQLModel, table=True):
    """Quotation comparison + vendor selection. One per demand. Memo document."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_cs_number_per_tenant"),
        UniqueConstraint("tenant_id", "demand_id", name="unique_cs_per_demand"),
        CheckConstraint(
            "status IN ('draft','approved','converted','cancelled')",
            name="ck_cs_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    demand_id: int = Field(foreign_key="purchasedemand.id", index=True)
    cs_date: str
    selected_quotation_id: Optional[int] = Field(default=None, foreign_key="vendorquotation.id")
    justification: Optional[str] = None
    status: str = Field(default="draft")
    created_by_id: int = Field(foreign_key="user.id")
    approved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    approved_at: Optional[datetime] = None
    po_id: Optional[int] = Field(default=None, foreign_key="purchaseorder.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

Verify first that the analytic accounts table is named `analyticaccount`: `grep -n "class AnalyticAccount" backend/models.py` and check for an explicit `__tablename__`. If it differs, use the actual name in the FK string.

- [ ] **Step 3: Add the two PO columns** inside `class PurchaseOrder` (after `bill_id`):

```python
    demand_id: Optional[int] = Field(default=None, foreign_key="purchasedemand.id")
    comparative_id: Optional[int] = Field(default=None, foreign_key="comparativestatement.id")
```

- [ ] **Step 4: Sanity-import**

Run: `cd backend && PYTHONPATH=. uv run python -c "import models; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Generate + edit the migration**

```bash
uv run alembic revision --autogenerate -m "purchase demand comparative"
```

Edit the generated file: (a) rename to `0029_purchase_demand_comparative.py` and set `revision = "0029_purchase_demand_comparative"`, `down_revision = "0028_tenant_hospital_model"`; (b) wrap each `op.create_table(...)` in `if not bind.dialect.has_table(bind, "<table>"):` (copy the guard shape from `0016`/`0017`); (c) in the `purchaseorder` ALTER, keep only the two `op.add_column` lines — delete any `create_foreign_key` calls (SQLite cannot ADD CONSTRAINT); guard them with a column-existence check copied from 0016/0017.

- [ ] **Step 6: Apply and verify**

Run: `uv run alembic upgrade head && uv run alembic heads`
Expected: `0029_purchase_demand_comparative (head)`

- [ ] **Step 7: Run the full test suite as baseline**

Run: `PYTHONPATH=. uv run pytest -q 2>&1 | tail -3`
Expected: same failure count as main (4 pre-existing). Record the number.

- [ ] **Step 8: Commit**

```bash
git add backend/models.py backend/alembic/versions/0029_purchase_demand_comparative.py
git commit -m "feat(purchase): PD/VQ/CS models + PO chain columns (#137 P1)"
```

---

### Task 2: Module + permission registration

**Files:**
- Modify: `backend/db.py` (MODULE_REGISTRY, after the `ai_assistant` entry; MODULES_BY_MODEL)
- Modify: `backend/services/permissions.py` (PERMISSION_RESOURCES dict)
- Test: `backend/tests/test_purchase_flow.py` (new file, started here)

**Interfaces:**
- Produces: module id `"purchase_store"`; permission resource keys `"purchase.demand"`, `"purchase.comparative"`.

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_purchase_flow.py`:

```python
"""#137 Phase 1 — Demand → Quotation → Comparative → PO chain."""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str, model: str = "manufacturing") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": model,
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_purchase_store_module_registered(client: TestClient):
    auth = _signup(client, "mod@t.com")
    mods = client.get("/api/modules", headers=auth).json()
    ids = {m["id"] for m in mods}
    assert "purchase_store" in ids
    entry = next(m for m in mods if m["id"] == "purchase_store")
    assert entry["installed"] is True  # manufacturing pre-installs it


def test_permission_resources_registered(client: TestClient):
    from services.permissions import PERMISSION_RESOURCES
    assert "purchase.demand" in PERMISSION_RESOURCES
    assert "purchase.comparative" in PERMISSION_RESOURCES
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py -v`
Expected: both FAIL (`purchase_store` not in ids / KeyError).

- [ ] **Step 3: Register the module** in `backend/db.py` MODULE_REGISTRY (after `ai_assistant`):

```python
    "purchase_store": {
        "label":       "Purchases & Store",
        "description": "Full procure-to-pay chain: purchase demands, vendor quotation comparison, gate inward, GRN, and store issues — with approval controls.",
        "category":    "Operations",
        "icon":        "ShoppingCart",
        "deps":        ["inventory"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Purchases"],
    },
```

And in `MODULES_BY_MODEL`, change the manufacturing line to include it:

```python
    "manufacturing":     ["base", "inventory", "production", "purchase_store"],
```

- [ ] **Step 4: Register permissions** in `backend/services/permissions.py`, next to the `"purchase_orders"` entry:

```python
    "purchase.demand":      {"label": "Purchase Demands",       "category": "Purchasing"},
    "purchase.comparative": {"label": "Comparative Statements", "category": "Purchasing"},
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/db.py backend/services/permissions.py backend/tests/test_purchase_flow.py
git commit -m "feat(purchase): purchase_store module + permission resources (#137 P1)"
```

---

### Task 3: Purchase Demands router

**Files:**
- Create: `backend/routers/purchase_demands.py`
- Modify: `backend/main.py` (import + `_ROUTERS` append)
- Test: `backend/tests/test_purchase_flow.py` (append)

**Interfaces:**
- Consumes: `PurchaseDemand`, `PurchaseDemandLine` (Task 1).
- Produces: `GET/POST /api/purchase-demands`, `GET/PUT /api/purchase-demands/{id}`, `PATCH .../{id}/approve|cancel|close`. Demand JSON shape: `{id, number, demand_date, required_by, analytic_account_id, purpose, notes, status, created_by_id, approved_by_id, lines: [{id, product_id, description, qty, unit}]}`. Helper `_get_demand(session, user, demand_id)` (404s cross-tenant) reused nowhere else — each router owns its own.

- [ ] **Step 1: Append failing tests** to `backend/tests/test_purchase_flow.py`:

```python
def _make_demand(client, auth, lines=None):
    r = client.post(
        "/api/purchase-demands",
        headers=auth,
        json={
            "demand_date": "2026-07-04",
            "purpose": "Line restock",
            "lines": lines or [{"description": "Steel rods 12mm", "qty": 100, "unit": "kg"}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _second_admin(client, auth, email="approver@t.com"):
    """Invite a second admin in the same tenant and return their auth header."""
    client.post(
        "/api/users",
        headers=auth,
        json={"email": email, "password": "password123", "full_name": "Approver", "role": "admin"},
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_demand_lifecycle_and_self_approval_block(client: TestClient):
    auth = _signup(client, "pd1@t.com")
    d = _make_demand(client, auth)
    assert d["number"].startswith("PD-") and d["status"] == "draft"
    assert d["lines"][0]["description"] == "Steel rods 12mm"

    # Self-approval must be rejected
    r = client.patch(f"/api/purchase-demands/{d['id']}/approve", headers=auth)
    assert r.status_code == 400
    assert "creator" in r.json()["detail"].lower()

    # A different admin approves
    auth2 = _second_admin(client, auth)
    r = client.patch(f"/api/purchase-demands/{d['id']}/approve", headers=auth2)
    assert r.status_code == 200
    got = client.get(f"/api/purchase-demands/{d['id']}", headers=auth).json()
    assert got["status"] == "approved" and got["approved_by_id"] is not None

    # Editing an approved demand is blocked
    r = client.put(
        f"/api/purchase-demands/{d['id']}", headers=auth,
        json={"demand_date": "2026-07-05", "lines": [{"description": "x", "qty": 1}]},
    )
    assert r.status_code == 400


def test_demand_tenant_isolation(client: TestClient):
    auth_a = _signup(client, "pd2a@t.com")
    auth_b = _signup(client, "pd2b@t.com")
    d = _make_demand(client, auth_a)
    assert client.get(f"/api/purchase-demands/{d['id']}", headers=auth_b).status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py -v -k demand`
Expected: FAIL — 404 on POST (router not mounted).

- [ ] **Step 3: Create `backend/routers/purchase_demands.py`**:

```python
"""Purchase Demands — quantity-only requisitions (#137 Phase 1). Memo documents, no GL."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import PurchaseDemand, PurchaseDemandLine
from routers.common import AdminUserDep, SessionDep, WriteUserDep, log_audit, next_number
from services.money import D
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(
    prefix="/api/purchase-demands", tags=["purchase-demands"],
    dependencies=[perm_dep("purchase.demand")],
)


class DemandLineIn(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None


class DemandIn(BaseModel):
    demand_date: str
    required_by: Optional[str] = None
    analytic_account_id: Optional[int] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None
    lines: List[DemandLineIn] = []


def _serialize(session, d: PurchaseDemand) -> dict:
    lines = session.exec(
        select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == d.id)
    ).all()
    out = d.model_dump()
    out["lines"] = [l.model_dump() for l in lines]
    return out


def _get_demand(session, user, demand_id: int) -> PurchaseDemand:
    d = session.exec(
        select(PurchaseDemand).where(
            PurchaseDemand.id == demand_id, PurchaseDemand.tenant_id == user.tenant_id
        )
    ).first()
    if not d:
        raise HTTPException(404, "Demand not found")
    return d


@router.get("")
def list_demands(session: SessionDep, user: WriteUserDep, status: Optional[str] = None):
    q = select(PurchaseDemand).where(PurchaseDemand.tenant_id == user.tenant_id)
    if status:
        q = q.where(PurchaseDemand.status == status)
    q = apply_own_filter(q, PurchaseDemand, user)
    rows = session.exec(q.order_by(PurchaseDemand.id.desc())).all()
    return [_serialize(session, d) for d in rows]


@router.get("/{demand_id}")
def get_demand(session: SessionDep, user: WriteUserDep, demand_id: int):
    return _serialize(session, _get_demand(session, user, demand_id))


@router.post("", status_code=201)
def create_demand(session: SessionDep, user: WriteUserDep, body: DemandIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    number = next_number(
        session, user.tenant_id, "purchase_demand", "PD", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    d = PurchaseDemand(
        tenant_id=user.tenant_id, number=number, demand_date=body.demand_date,
        required_by=body.required_by, analytic_account_id=body.analytic_account_id,
        purpose=body.purpose, notes=body.notes, status="draft", created_by_id=user.id,
    )
    session.add(d)
    session.flush()
    for l in body.lines:
        session.add(PurchaseDemandLine(
            demand_id=d.id, product_id=l.product_id,
            description=l.description, qty=D(l.qty), unit=l.unit,
        ))
    log_audit(session, user, "CREATE", "purchase_demand", d.id, {"number": number})
    session.commit()
    return _serialize(session, d)


@router.put("/{demand_id}")
def update_demand(session: SessionDep, user: WriteUserDep, demand_id: int, body: DemandIn):
    d = _get_demand(session, user, demand_id)
    if d.status != "draft":
        raise HTTPException(400, f"Cannot edit a demand with status '{d.status}'")
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    d.demand_date = body.demand_date
    d.required_by = body.required_by
    d.analytic_account_id = body.analytic_account_id
    d.purpose = body.purpose
    d.notes = body.notes
    for old in session.exec(
        select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == d.id)
    ).all():
        session.delete(old)
    for l in body.lines:
        session.add(PurchaseDemandLine(
            demand_id=d.id, product_id=l.product_id,
            description=l.description, qty=D(l.qty), unit=l.unit,
        ))
    session.add(d)
    log_audit(session, user, "UPDATE", "purchase_demand", d.id, {"number": d.number})
    session.commit()
    return _serialize(session, d)


@router.patch("/{demand_id}/approve")
def approve_demand(session: SessionDep, user: AdminUserDep, demand_id: int):
    d = _get_demand(session, user, demand_id)
    if d.status != "draft":
        raise HTTPException(400, f"Cannot approve a demand with status '{d.status}'")
    if d.created_by_id == user.id:
        raise HTTPException(400, "A demand cannot be approved by its creator")
    d.status = "approved"
    d.approved_by_id = user.id
    d.approved_at = datetime.utcnow()
    session.add(d)
    log_audit(session, user, "UPDATE", "purchase_demand", d.id, {"action": "approved"})
    session.commit()
    return {"success": True, "status": "approved"}


@router.patch("/{demand_id}/cancel")
def cancel_demand(session: SessionDep, user: AdminUserDep, demand_id: int):
    d = _get_demand(session, user, demand_id)
    if d.status not in ("draft", "approved"):
        raise HTTPException(400, f"Cannot cancel a demand with status '{d.status}'")
    d.status = "cancelled"
    session.add(d)
    log_audit(session, user, "UPDATE", "purchase_demand", d.id, {"action": "cancelled"})
    session.commit()
    return {"success": True, "status": "cancelled"}


@router.patch("/{demand_id}/close")
def close_demand(session: SessionDep, user: AdminUserDep, demand_id: int):
    d = _get_demand(session, user, demand_id)
    if d.status != "approved":
        raise HTTPException(400, "Only approved demands can be closed")
    d.status = "closed"
    session.add(d)
    log_audit(session, user, "UPDATE", "purchase_demand", d.id, {"action": "closed"})
    session.commit()
    return {"success": True, "status": "closed"}
```

- [ ] **Step 4: Mount it** — in `backend/main.py` add `purchase_demands` to the `from routers import (...)` list and `purchase_demands.router,` to `_ROUTERS`.

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py -v`
Expected: all PASS. Note: `_second_admin` assumes `POST /api/users` invites with a password — verify the actual body shape with `grep -n "def create_user\|class UserCreate" backend/routers/users.py` and adjust the helper to match before debugging anything else.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/purchase_demands.py backend/main.py backend/tests/test_purchase_flow.py
git commit -m "feat(purchase): demand CRUD + approve/cancel/close with self-approval block (#137 P1)"
```

---

### Task 4: Vendor Quotations router

**Files:**
- Create: `backend/routers/quotations.py`
- Modify: `backend/main.py` (mount)
- Test: `backend/tests/test_purchase_flow.py` (append)

**Interfaces:**
- Consumes: `_make_demand`/`_second_admin` test helpers (Task 3); `VendorQuotation`, `VendorQuotationLine` (Task 1).
- Produces: `GET /api/quotations?demand_id=`, `GET/{id}`, `POST`, `PUT/{id}`, `DELETE/{id}`. Quotation JSON: `{id, number, demand_id, vendor_id, quote_date, ..., lines: [{id, demand_line_id, rate, qty, amount}], total}`. Rule: quotations attach only to `approved` demands; frozen once the demand's CS is approved/converted.

- [ ] **Step 1: Append failing tests**:

```python
def _make_vendor(client, auth, name="Acme Steel"):
    r = client.post("/api/vendors", headers=auth, json={"name": name})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _approved_demand(client, auth):
    d = _make_demand(client, auth)
    auth2 = _second_admin(client, auth, email=f"appr-{d['id']}@t.com")
    client.patch(f"/api/purchase-demands/{d['id']}/approve", headers=auth2)
    return client.get(f"/api/purchase-demands/{d['id']}", headers=auth).json(), auth2


def _quote(client, auth, demand, vendor_id, rate):
    return client.post(
        "/api/quotations", headers=auth,
        json={
            "demand_id": demand["id"], "vendor_id": vendor_id, "quote_date": "2026-07-04",
            "lines": [{"demand_line_id": demand["lines"][0]["id"], "rate": rate,
                       "qty": demand["lines"][0]["qty"]}],
        },
    )


def test_quotation_requires_approved_demand(client: TestClient):
    auth = _signup(client, "vq1@t.com")
    v = _make_vendor(client, auth)
    draft = _make_demand(client, auth)
    r = _quote(client, auth, draft, v["id"], 250)
    assert r.status_code == 400  # demand still draft

    approved, _ = _approved_demand(client, auth)
    r = _quote(client, auth, approved, v["id"], 250)
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["number"].startswith("VQ-") and float(q["total"]) == 250 * 100
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py -v -k quotation`
Expected: FAIL (404 — router missing).

- [ ] **Step 3: Create `backend/routers/quotations.py`**:

```python
"""Vendor Quotations against approved Purchase Demands (#137 Phase 1). Memo documents."""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    ComparativeStatement, PurchaseDemand, PurchaseDemandLine,
    Vendor, VendorQuotation, VendorQuotationLine,
)
from routers.common import SessionDep, WriteUserDep, log_audit, next_number
from services.money import D, money
from services.permissions import perm_dep

router = APIRouter(
    prefix="/api/quotations", tags=["quotations"],
    dependencies=[perm_dep("purchase.comparative")],
)


class QuoteLineIn(BaseModel):
    demand_line_id: int
    rate: Decimal
    qty: Decimal = Decimal("1")


class QuoteIn(BaseModel):
    demand_id: int
    vendor_id: int
    quote_date: str
    valid_until: Optional[str] = None
    delivery_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    lines: List[QuoteLineIn] = []


def _serialize(session, q: VendorQuotation) -> dict:
    lines = session.exec(
        select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
    ).all()
    out = q.model_dump()
    out["lines"] = [l.model_dump() for l in lines]
    out["total"] = sum(D(l.amount) for l in lines)
    return out


def _frozen(session, tenant_id: int, demand_id: int) -> bool:
    """Quotations freeze once the demand's CS is approved or converted."""
    cs = session.exec(
        select(ComparativeStatement).where(
            ComparativeStatement.tenant_id == tenant_id,
            ComparativeStatement.demand_id == demand_id,
        )
    ).first()
    return bool(cs and cs.status in ("approved", "converted"))


def _get_quote(session, user, quote_id: int) -> VendorQuotation:
    q = session.exec(
        select(VendorQuotation).where(
            VendorQuotation.id == quote_id, VendorQuotation.tenant_id == user.tenant_id
        )
    ).first()
    if not q:
        raise HTTPException(404, "Quotation not found")
    return q


def _validate_and_write_lines(session, user, body: QuoteIn, q: VendorQuotation) -> None:
    demand_line_ids = {
        l.id for l in session.exec(
            select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == body.demand_id)
        ).all()
    }
    for l in body.lines:
        if l.demand_line_id not in demand_line_ids:
            raise HTTPException(400, f"demand_line_id {l.demand_line_id} is not on this demand")
        session.add(VendorQuotationLine(
            quotation_id=q.id, demand_line_id=l.demand_line_id,
            rate=D(l.rate), qty=D(l.qty), amount=money(D(l.rate) * D(l.qty)),
        ))


@router.get("")
def list_quotes(session: SessionDep, user: WriteUserDep, demand_id: Optional[int] = None):
    q = select(VendorQuotation).where(VendorQuotation.tenant_id == user.tenant_id)
    if demand_id:
        q = q.where(VendorQuotation.demand_id == demand_id)
    return [_serialize(session, r) for r in session.exec(q.order_by(VendorQuotation.id)).all()]


@router.get("/{quote_id}")
def get_quote(session: SessionDep, user: WriteUserDep, quote_id: int):
    return _serialize(session, _get_quote(session, user, quote_id))


@router.post("", status_code=201)
def create_quote(session: SessionDep, user: WriteUserDep, body: QuoteIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    demand = session.exec(
        select(PurchaseDemand).where(
            PurchaseDemand.id == body.demand_id, PurchaseDemand.tenant_id == user.tenant_id
        )
    ).first()
    if not demand:
        raise HTTPException(404, "Demand not found")
    if demand.status != "approved":
        raise HTTPException(400, "Quotations can only be added to an approved demand")
    if _frozen(session, user.tenant_id, demand.id):
        raise HTTPException(400, "Comparative already approved — quotations are frozen")
    vendor = session.exec(
        select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)
    ).first()
    if not vendor:
        raise HTTPException(400, "Vendor not found for this tenant")

    number = next_number(
        session, user.tenant_id, "vendor_quotation", "VQ", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    q = VendorQuotation(
        tenant_id=user.tenant_id, number=number, demand_id=body.demand_id,
        vendor_id=body.vendor_id, quote_date=body.quote_date, valid_until=body.valid_until,
        delivery_terms=body.delivery_terms, payment_terms=body.payment_terms, notes=body.notes,
    )
    session.add(q)
    session.flush()
    _validate_and_write_lines(session, user, body, q)
    log_audit(session, user, "CREATE", "vendor_quotation", q.id, {"number": number})
    session.commit()
    return _serialize(session, q)


@router.put("/{quote_id}")
def update_quote(session: SessionDep, user: WriteUserDep, quote_id: int, body: QuoteIn):
    q = _get_quote(session, user, quote_id)
    if _frozen(session, user.tenant_id, q.demand_id):
        raise HTTPException(400, "Comparative already approved — quotations are frozen")
    if body.demand_id != q.demand_id:
        raise HTTPException(400, "A quotation cannot move to a different demand")
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    q.vendor_id = body.vendor_id
    q.quote_date = body.quote_date
    q.valid_until = body.valid_until
    q.delivery_terms = body.delivery_terms
    q.payment_terms = body.payment_terms
    q.notes = body.notes
    for old in session.exec(
        select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
    ).all():
        session.delete(old)
    _validate_and_write_lines(session, user, body, q)
    session.add(q)
    log_audit(session, user, "UPDATE", "vendor_quotation", q.id, {"number": q.number})
    session.commit()
    return _serialize(session, q)


@router.delete("/{quote_id}")
def delete_quote(session: SessionDep, user: WriteUserDep, quote_id: int):
    q = _get_quote(session, user, quote_id)
    if _frozen(session, user.tenant_id, q.demand_id):
        raise HTTPException(400, "Comparative already approved — quotations are frozen")
    for l in session.exec(
        select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
    ).all():
        session.delete(l)
    session.delete(q)
    log_audit(session, user, "DELETE", "vendor_quotation", quote_id, {"number": q.number})
    session.commit()
    return {"success": True}
```

- [ ] **Step 4: Mount in `main.py`** (import + `_ROUTERS`), then run tests

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py -v`
Expected: all PASS. (Verify the vendor-create body with `grep -n "class VendorCreate\|def create_vendor" backend/routers/vendors.py` and fix `_make_vendor` if the required fields differ.)

- [ ] **Step 5: Commit**

```bash
git add backend/routers/quotations.py backend/main.py backend/tests/test_purchase_flow.py
git commit -m "feat(purchase): vendor quotations with demand-line validation + freeze rule (#137 P1)"
```

---

### Task 5: Comparative Statements router (matrix, lowest-or-justify, convert-to-PO)

**Files:**
- Create: `backend/routers/comparatives.py`
- Modify: `backend/main.py` (mount)
- Test: `backend/tests/test_purchase_flow.py` (append)

**Interfaces:**
- Consumes: models from Task 1; test helpers from Tasks 3–4; `PurchaseOrder`/`PurchaseOrderLine` models.
- Produces: `GET /api/comparatives`, `GET/{id}` (matrix), `POST {demand_id, cs_date}`, `PUT/{id}` (select + justify), `PATCH/{id}/approve`, `POST/{id}/convert-to-po`. Matrix shape: `{**cs, demand: {...}, quotations: [quote dicts w/ total], matrix: [{demand_line, cells: [{quotation_id, rate, amount}]}]}`.

- [ ] **Step 1: Append failing tests**:

```python
def _cs_setup(client, prefix):
    """Demand with two quotes: vendor A @250 (lowest), vendor B @300."""
    auth = _signup(client, f"{prefix}@t.com")
    va = _make_vendor(client, auth, "Vendor A")
    vb = _make_vendor(client, auth, "Vendor B")
    demand, auth2 = _approved_demand(client, auth)
    qa = _quote(client, auth, demand, va["id"], 250).json()
    qb = _quote(client, auth, demand, vb["id"], 300).json()
    cs = client.post(
        "/api/comparatives", headers=auth,
        json={"demand_id": demand["id"], "cs_date": "2026-07-04"},
    ).json()
    return auth, auth2, demand, qa, qb, cs


def test_cs_lowest_or_justify(client: TestClient):
    auth, auth2, demand, qa, qb, cs = _cs_setup(client, "cs1")

    # Selecting the HIGHER quote without justification → blocked at approve
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": qb["id"], "justification": None})
    r = client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2)
    assert r.status_code == 400 and "justif" in r.json()["detail"].lower()

    # With justification → approved
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": qb["id"],
                     "justification": "Vendor A failed last delivery"})
    r = client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2)
    assert r.status_code == 200

    # Quotations are now frozen
    r = _quote(client, auth, demand, qa["vendor_id"], 111)
    assert r.status_code == 400


def test_cs_self_approval_block_and_convert(client: TestClient):
    auth, auth2, demand, qa, qb, cs = _cs_setup(client, "cs2")
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": qa["id"], "justification": None})

    # Creator cannot approve their own CS
    r = client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth)
    assert r.status_code == 400

    client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2)
    r = client.post(f"/api/comparatives/{cs['id']}/convert-to-po", headers=auth)
    assert r.status_code == 201, r.text
    po = r.json()
    assert po["status"] == "draft"
    assert po["comparative_id"] == cs["id"] and po["demand_id"] == demand["id"]
    assert float(po["total"]) == 250 * 100  # winner's rate × demand qty

    # CS and demand both flip to converted
    assert client.get(f"/api/comparatives/{cs['id']}", headers=auth).json()["status"] == "converted"
    assert client.get(f"/api/purchase-demands/{demand['id']}", headers=auth).json()["status"] == "converted"


def test_cs_single_quote_needs_justification(client: TestClient):
    auth = _signup(client, "cs3@t.com")
    v = _make_vendor(client, auth)
    demand, auth2 = _approved_demand(client, auth)
    q = _quote(client, auth, demand, v["id"], 500).json()
    cs = client.post("/api/comparatives", headers=auth,
                     json={"demand_id": demand["id"], "cs_date": "2026-07-04"}).json()
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": q["id"], "justification": None})
    assert client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2).status_code == 400
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": q["id"], "justification": "Single-source item"})
    assert client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2).status_code == 200
```

- [ ] **Step 2: Run to verify failure** — `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py -v -k cs` → FAIL (404).

- [ ] **Step 3: Create `backend/routers/comparatives.py`**:

```python
"""Comparative Statements — quotation comparison + vendor selection (#137 Phase 1).
Control rules: one CS per demand; approver ≠ creator; lowest-or-justify."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    ComparativeStatement, PurchaseDemand, PurchaseDemandLine, PurchaseOrder,
    PurchaseOrderLine, Vendor, VendorQuotation, VendorQuotationLine,
)
from routers.common import AdminUserDep, SessionDep, WriteUserDep, log_audit, next_number
from services.money import D, money
from services.permissions import perm_dep

router = APIRouter(
    prefix="/api/comparatives", tags=["comparatives"],
    dependencies=[perm_dep("purchase.comparative")],
)


class CSCreate(BaseModel):
    demand_id: int
    cs_date: str


class CSUpdate(BaseModel):
    selected_quotation_id: Optional[int] = None
    justification: Optional[str] = None


def _get_cs(session, user, cs_id: int) -> ComparativeStatement:
    cs = session.exec(
        select(ComparativeStatement).where(
            ComparativeStatement.id == cs_id,
            ComparativeStatement.tenant_id == user.tenant_id,
        )
    ).first()
    if not cs:
        raise HTTPException(404, "Comparative not found")
    return cs


def _quote_totals(session, demand_id: int) -> dict[int, object]:
    """quotation_id → Decimal total, for every quotation on the demand."""
    totals: dict[int, object] = {}
    for q in session.exec(
        select(VendorQuotation).where(VendorQuotation.demand_id == demand_id)
    ).all():
        lines = session.exec(
            select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
        ).all()
        totals[q.id] = sum(D(l.amount) for l in lines)
    return totals


def _serialize(session, user, cs: ComparativeStatement) -> dict:
    demand = session.get(PurchaseDemand, cs.demand_id)
    demand_lines = session.exec(
        select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == cs.demand_id)
    ).all()
    quotes = session.exec(
        select(VendorQuotation).where(
            VendorQuotation.demand_id == cs.demand_id,
            VendorQuotation.tenant_id == user.tenant_id,
        ).order_by(VendorQuotation.id)
    ).all()
    totals = _quote_totals(session, cs.demand_id)
    vendors = {
        v.id: v.name for v in session.exec(
            select(Vendor).where(Vendor.tenant_id == user.tenant_id)
        ).all()
    }
    quote_lines = {
        q.id: {
            l.demand_line_id: l for l in session.exec(
                select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
            ).all()
        }
        for q in quotes
    }
    out = cs.model_dump()
    out["demand"] = {**demand.model_dump(), "lines": [dl.model_dump() for dl in demand_lines]}
    out["quotations"] = [
        {**q.model_dump(), "vendor_name": vendors.get(q.vendor_id, "—"),
         "total": totals.get(q.id, 0)}
        for q in quotes
    ]
    out["matrix"] = [
        {
            "demand_line": dl.model_dump(),
            "cells": [
                {
                    "quotation_id": q.id,
                    "rate": (quote_lines[q.id].get(dl.id).rate
                             if quote_lines[q.id].get(dl.id) else None),
                    "amount": (quote_lines[q.id].get(dl.id).amount
                               if quote_lines[q.id].get(dl.id) else None),
                }
                for q in quotes
            ],
        }
        for dl in demand_lines
    ]
    return out


@router.get("")
def list_cs(session: SessionDep, user: WriteUserDep, status: Optional[str] = None):
    q = select(ComparativeStatement).where(ComparativeStatement.tenant_id == user.tenant_id)
    if status:
        q = q.where(ComparativeStatement.status == status)
    return [
        _serialize(session, user, cs)
        for cs in session.exec(q.order_by(ComparativeStatement.id.desc())).all()
    ]


@router.get("/{cs_id}")
def get_cs(session: SessionDep, user: WriteUserDep, cs_id: int):
    return _serialize(session, user, _get_cs(session, user, cs_id))


@router.post("", status_code=201)
def create_cs(session: SessionDep, user: WriteUserDep, body: CSCreate):
    demand = session.exec(
        select(PurchaseDemand).where(
            PurchaseDemand.id == body.demand_id,
            PurchaseDemand.tenant_id == user.tenant_id,
        )
    ).first()
    if not demand:
        raise HTTPException(404, "Demand not found")
    if demand.status != "approved":
        raise HTTPException(400, "A comparative requires an approved demand")
    existing = session.exec(
        select(ComparativeStatement).where(
            ComparativeStatement.tenant_id == user.tenant_id,
            ComparativeStatement.demand_id == body.demand_id,
        )
    ).first()
    if existing:
        raise HTTPException(400, f"Comparative {existing.number} already exists for this demand")
    number = next_number(
        session, user.tenant_id, "comparative_statement", "CS", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    cs = ComparativeStatement(
        tenant_id=user.tenant_id, number=number, demand_id=body.demand_id,
        cs_date=body.cs_date, status="draft", created_by_id=user.id,
    )
    session.add(cs)
    log_audit(session, user, "CREATE", "comparative_statement", None, {"number": number})
    session.commit()
    session.refresh(cs)
    return _serialize(session, user, cs)


@router.put("/{cs_id}")
def update_cs(session: SessionDep, user: WriteUserDep, cs_id: int, body: CSUpdate):
    cs = _get_cs(session, user, cs_id)
    if cs.status != "draft":
        raise HTTPException(400, f"Cannot edit a comparative with status '{cs.status}'")
    if body.selected_quotation_id is not None:
        q = session.exec(
            select(VendorQuotation).where(
                VendorQuotation.id == body.selected_quotation_id,
                VendorQuotation.demand_id == cs.demand_id,
                VendorQuotation.tenant_id == user.tenant_id,
            )
        ).first()
        if not q:
            raise HTTPException(400, "Selected quotation is not on this demand")
    cs.selected_quotation_id = body.selected_quotation_id
    cs.justification = body.justification
    session.add(cs)
    log_audit(session, user, "UPDATE", "comparative_statement", cs.id, {"number": cs.number})
    session.commit()
    return _serialize(session, user, cs)


@router.patch("/{cs_id}/approve")
def approve_cs(session: SessionDep, user: AdminUserDep, cs_id: int):
    cs = _get_cs(session, user, cs_id)
    if cs.status != "draft":
        raise HTTPException(400, f"Cannot approve a comparative with status '{cs.status}'")
    if cs.created_by_id == user.id:
        raise HTTPException(400, "A comparative cannot be approved by its creator")
    if not cs.selected_quotation_id:
        raise HTTPException(400, "Select a winning quotation before approval")
    totals = _quote_totals(session, cs.demand_id)
    if not totals:
        raise HTTPException(400, "No quotations on this demand")
    selected_total = totals.get(cs.selected_quotation_id)
    lowest_total = min(totals.values())
    needs_justification = len(totals) < 2 or selected_total != lowest_total
    if needs_justification and not (cs.justification and cs.justification.strip()):
        raise HTTPException(
            400,
            "Justification required: fewer than two quotations, or the selected "
            "quotation is not the lowest",
        )
    cs.status = "approved"
    cs.approved_by_id = user.id
    cs.approved_at = datetime.utcnow()
    session.add(cs)
    log_audit(session, user, "UPDATE", "comparative_statement", cs.id, {"action": "approved"})
    session.commit()
    return {"success": True, "status": "approved"}


@router.post("/{cs_id}/convert-to-po", status_code=201)
def convert_to_po(session: SessionDep, user: WriteUserDep, cs_id: int):
    cs = _get_cs(session, user, cs_id)
    if cs.status != "approved":
        raise HTTPException(400, "Only an approved comparative can convert to a PO")
    quote = session.get(VendorQuotation, cs.selected_quotation_id)
    vendor = session.get(Vendor, quote.vendor_id)
    demand = session.get(PurchaseDemand, cs.demand_id)
    demand_lines = {
        dl.id: dl for dl in session.exec(
            select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == cs.demand_id)
        ).all()
    }
    quote_lines = session.exec(
        select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == quote.id)
    ).all()

    subtotal = money(sum(D(l.amount) for l in quote_lines))
    po_number = next_number(session, user.tenant_id, "purchase_order", "PO")
    po = PurchaseOrder(
        tenant_id=user.tenant_id, number=po_number, vendor_id=vendor.id,
        vendor_name=vendor.name, order_date=cs.cs_date,
        description=f"Converted from {cs.number} ({demand.number})",
        subtotal=subtotal, total=subtotal, status="draft",
        demand_id=cs.demand_id, comparative_id=cs.id,
    )
    session.add(po)
    session.flush()
    for ql in quote_lines:
        dl = demand_lines[ql.demand_line_id]
        session.add(PurchaseOrderLine(
            po_id=po.id, product_id=dl.product_id, description=dl.description,
            qty=D(ql.qty), unit=dl.unit, rate=D(ql.rate), amount=money(D(ql.qty) * D(ql.rate)),
        ))
    cs.status = "converted"
    cs.po_id = po.id
    demand.status = "converted"
    session.add(cs)
    session.add(demand)
    log_audit(session, user, "CREATE", "purchase_order", po.id,
              {"number": po_number, "from_comparative": cs.number})
    session.commit()
    session.refresh(po)
    return po
```

- [ ] **Step 4: Mount in `main.py`**, run tests

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/comparatives.py backend/main.py backend/tests/test_purchase_flow.py
git commit -m "feat(purchase): comparative statements — matrix, lowest-or-justify, convert-to-PO (#137 P1)"
```

---

### Task 6: Chain enforcement on PO creation + `require_purchase_chain` setting

**Files:**
- Modify: `backend/routers/purchase_orders.py` (POCreate + `create_po`)
- Modify: `backend/routers/settings.py` (`SettingsUpdate` — add field)
- Test: `backend/tests/test_purchase_flow.py` (append)

**Interfaces:**
- Consumes: `routers.modules._get_enabled(tenant)`; `Settings` KV model.
- Produces: `POCreate.demand_id` / `POCreate.comparative_id` optional fields; 400 on bare PO when chain required.

- [ ] **Step 1: Append failing tests**:

```python
def test_chain_enforcement(client: TestClient):
    # manufacturing tenant → purchase_store pre-installed → chain required by default
    auth = _signup(client, "enf1@t.com")
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-04",
        "vendor_name": "Walk-in Vendor",
        "lines": [{"description": "Widget", "qty": 1, "rate": 10}],
    })
    assert r.status_code == 400
    assert "demand" in r.json()["detail"].lower() or "comparative" in r.json()["detail"].lower()

    # Toggle the setting off → bare PO allowed
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-04",
        "vendor_name": "Walk-in Vendor",
        "lines": [{"description": "Widget", "qty": 1, "rate": 10}],
    })
    assert r.status_code == 201, r.text


def test_no_enforcement_without_module(client: TestClient):
    # simple tenant → purchase_store NOT installed → no enforcement
    auth = _signup(client, "enf2@t.com", model="simple")
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-04",
        "vendor_name": "Walk-in Vendor",
        "lines": [{"description": "Widget", "qty": 1, "rate": 10}],
    })
    assert r.status_code == 201, r.text
```

- [ ] **Step 2: Run to verify failure** — first test FAILS (PO returns 201, no enforcement yet).

- [ ] **Step 3: Implement.** In `backend/routers/purchase_orders.py`:

Add to imports: `from models import ComparativeStatement, Settings, Tenant` (merge into the existing `from models import ...` line).

Add to `POCreate`:

```python
    demand_id: Optional[int] = None
    comparative_id: Optional[int] = None
```

Add the helper above `create_po`:

```python
def _chain_required(session, tenant_id: int) -> bool:
    """True when purchase_store is installed AND require_purchase_chain isn't 'false'."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return False
    from routers.modules import _get_enabled
    if "purchase_store" not in _get_enabled(tenant):
        return False
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id, Settings.key == "require_purchase_chain"
        )
    ).first()
    return not (row and str(row.value).strip().lower() == "false")
```

At the top of `create_po`, after the empty-lines check:

```python
    if body.comparative_id:
        cs = session.exec(
            select(ComparativeStatement).where(
                ComparativeStatement.id == body.comparative_id,
                ComparativeStatement.tenant_id == user.tenant_id,
                ComparativeStatement.status.in_(["approved", "converted"]),
            )
        ).first()
        if not cs:
            raise HTTPException(400, "comparative_id does not reference an approved comparative")
    elif _chain_required(session, user.tenant_id):
        raise HTTPException(
            400,
            "This company requires purchases to go through Demand → Comparative approval. "
            "Create a demand, compare quotations, then convert the comparative to a PO "
            "(or disable 'Require purchase chain' in Settings).",
        )
```

And pass the links into the `PurchaseOrder(...)` constructor: `demand_id=body.demand_id, comparative_id=body.comparative_id,`.

In `backend/routers/settings.py`, add to the `SettingsUpdate` model: `require_purchase_chain: Optional[str] = None` (match the style of the other optional keys — check whether values are `str` or typed; mirror `block_negative_stock`).

- [ ] **Step 4: Run the full suite**

Run: `PYTHONPATH=. uv run pytest -q 2>&1 | tail -3`
Expected: baseline failures only; all `test_purchase_flow.py` PASS. **Watch for collateral damage:** any pre-existing PO test that creates bare POs under a manufacturing tenant will now 400 — fix those tests by using a `simple`/`trader` tenant or toggling the setting, and note it in the commit message.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/purchase_orders.py backend/routers/settings.py backend/tests/test_purchase_flow.py
git commit -m "feat(purchase): setting-gated chain enforcement on PO creation (#137 P1)"
```

---

### Task 7: Frontend nav — Purchases section + `notForModule`

**Files:**
- Modify: `frontend/src/lib/nav.ts` (NavItem type, NAV entries, ALL_SECTIONS, new `navVisible` helper)
- Modify: every consumer that filters on `forModule` — find them: `grep -rn "forModule" frontend/src --include="*.tsx" --include="*.ts" -l` (expect `Sidebar.tsx`, `TopNav.tsx`, `MoreDrawer.tsx`, possibly `navIndex.ts`)
- Modify: `frontend/src/app/(dashboard)/layout.tsx` (TITLE_MAP entry for Purchases)

**Interfaces:**
- Produces: `navVisible(item, installedModules)` exported from `nav.ts`; `"purchase_store"` in the forModule union; `notForModule` field; "Purchases" in `ALL_SECTIONS` (insert after "Payable").

- [ ] **Step 1: Extend the type + helper** in `nav.ts`:

```ts
export type NavItem = {
  label: string
  href: string
  icon: React.ElementType
  section: string
  /** Module ID — item is hidden when this module is not installed. */
  forModule?: "inventory" | "production" | "hrm" | "telecom" | "pra" | "healthcare" | "purchase_store"
  /** Module ID — item is hidden when this module IS installed (dual-home entries). */
  notForModule?: "purchase_store"
  /** Only shown to admin+ (admin or owner). */
  adminOnly?: boolean
}

/** Single visibility predicate — use everywhere instead of ad-hoc forModule checks. */
export function navVisible(item: NavItem, installed: Set<string>): boolean {
  if (item.forModule && !installed.has(item.forModule)) return false
  if (item.notForModule && installed.has(item.notForModule)) return false
  return true
}
```

- [ ] **Step 2: Add Purchases entries** to `NAV` (icons from lucide-react — add `ClipboardCheck`, `Scale`, `ShoppingCart` to the import):

```ts
  { label: "Demands",       href: "/purchases/demands",     icon: ClipboardCheck, section: "Purchases", forModule: "purchase_store" },
  { label: "Comparatives",  href: "/purchases/comparatives", icon: Scale,         section: "Purchases", forModule: "purchase_store" },
```

Then find the existing Purchase Orders and GRN entries (`grep -n "purchase-orders\|/grn" frontend/src/lib/nav.ts`), add `notForModule: "purchase_store"` to each **in place**, and add duplicates of both entries (same label/href/icon) with `section: "Purchases", forModule: "purchase_store"`. Insert `"Purchases"` into `ALL_SECTIONS` immediately after `"Payable"`.

- [ ] **Step 3: Swap consumers to `navVisible`.** In each file found by the grep, replace the existing `item.forModule && !installedModules.has(item.forModule)`-style predicate with `!navVisible(item, installedModules)` (import from `@/lib/nav`). Leave `navIndex.ts` (search layer) untouched.

- [ ] **Step 4: TITLE_MAP** — in `(dashboard)/layout.tsx` find `TITLE_MAP` and add `Purchases: { href: "/purchases/demands", title: "Purchases" }` following the existing entry shape exactly (check one entry first — shape may be a plain string map).

- [ ] **Step 5: Verify**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: build succeeds, no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/nav.ts frontend/src/components/Sidebar.tsx frontend/src/components/TopNav.tsx frontend/src/components/MoreDrawer.tsx "frontend/src/app/(dashboard)/layout.tsx"
git commit -m "feat(nav): Purchases section + notForModule dual-home gating (#137 P1)"
```

---

### Task 8: Demands list + detail pages

**Files:**
- Create: `frontend/src/app/(dashboard)/purchases/demands/page.tsx`
- Create: `frontend/src/app/(dashboard)/purchases/demands/[id]/page.tsx`

**Interfaces:**
- Consumes: `GET /api/purchase-demands`, `PATCH .../approve|cancel|close`, `GET /api/quotations?demand_id=` (Tasks 3–4 shapes).
- Produces: routes `/purchases/demands`, `/purchases/demands/[id]`.

- [ ] **Step 1: List page** — `purchases/demands/page.tsx`:

```tsx
"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Demand = {
  id: number; number: string; demand_date: string; required_by?: string
  purpose?: string; status: string
  lines: { id: number; description: string; qty: number; unit?: string }[]
}

const STATUSES = ["all", "draft", "approved", "converted", "closed", "cancelled"]

export default function DemandsPage() {
  const [rows, setRows] = useState<Demand[] | null>(null)
  const [status, setStatus] = useState("all")

  useEffect(() => {
    const qs = status === "all" ? "" : `?status=${status}`
    apiFetch<Demand[]>(`/api/purchase-demands${qs}`).then(setRows).catch(() => setRows([]))
  }, [status])

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between print:hidden">
        <div className="flex gap-1">
          {STATUSES.map(s => (
            <button key={s} onClick={() => setStatus(s)}
              className={`px-3 py-1 rounded-full text-xs border ${status === s
                ? "bg-[var(--primary)] text-white border-transparent"
                : "border-[var(--border)] text-[var(--text-secondary)]"}`}>
              {s}
            </button>
          ))}
        </div>
        <Link href="/purchases/demands/new"
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Demand
        </Link>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">PD #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Purpose</th>
              <th className="px-3 py-2">Items</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(d => (
              <tr key={d.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/purchases/demands/${d.id}`} className="text-[var(--primary)]">{d.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(d.demand_date)}</td>
                <td className="px-3 py-2">{d.purpose || "—"}</td>
                <td className="px-3 py-2">{d.lines.length}</td>
                <td className="px-3 py-2">{d.status}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--text-muted)]">No demands yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Detail page** — `purchases/demands/[id]/page.tsx`. Shows header fields, lines table, quotations received (`GET /api/quotations?demand_id=`), and action buttons (Approve / Cancel / Close / Edit-when-draft / "New Quotation" when approved / "Create Comparative" when approved and quotes ≥ 1). Include `<PrintHeader title={demand.number} subtitle={fmtDate(demand.demand_date)} />` at top (portrait — this IS the PD print view); wrap buttons in `print:hidden`. Buttons call the PATCH endpoints via `apiFetch(..., { method: "PATCH" })` then re-fetch; render error `detail` in a small red banner (self-approval 400 surfaces here). "Create Comparative" does `POST /api/comparatives {demand_id, cs_date: today}` then routes to `/purchases/comparatives/[id]`. Follow the list-page styling above; ~120 lines.

- [ ] **Step 3: Verify** — `npm run build` passes; manually: `./dev.sh`, log in as `demo.manufacturing@easy-books.app` / `demo1234`, see empty Demands list.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)/purchases/demands/page.tsx" "frontend/src/app/(dashboard)/purchases/demands/[id]/page.tsx"
git commit -m "feat(purchase-ui): demands list + detail/print pages (#137 P1)"
```

---

### Task 9: Demand new/edit form

**Files:**
- Create: `frontend/src/app/(dashboard)/purchases/demands/new/page.tsx`
- Create: `frontend/src/app/(dashboard)/purchases/demands/[id]/edit/page.tsx`

**Interfaces:**
- Consumes: `POST/PUT /api/purchase-demands` (`DemandIn` shape from Task 3), `GET /api/products`, `GET /api/analytic-accounts` (verify path: `grep -n "prefix=" backend/routers/analytic_accounts.py`).

- [ ] **Step 1: Shared form component.** Create the form inside `new/page.tsx` and export it for reuse by the edit page (same pattern as existing full-page forms — check `frontend/src/app/(dashboard)/purchase-orders/new/page.tsx` first and mirror its structure). Fields: demand_date (default today), required_by, analytic account `<select>` (fetched, optional, label "Department / Cost Center"), purpose, notes, and a lines grid: product picker `<select>` (optional — picking one fills description/unit), description text, qty number, unit text, add/remove row buttons. Submit → `apiFetch("/api/purchase-demands", { method: "POST", body: JSON.stringify(form) })` → route to `/purchases/demands/[id]`. **No rate column anywhere on this form.**

- [ ] **Step 2: Edit page** loads the demand, blocks with a notice unless `status === "draft"`, pre-fills, submits via PUT.

- [ ] **Step 3: Verify** — `npm run build`; manually create a demand end-to-end in the browser.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)/purchases/demands/new/page.tsx" "frontend/src/app/(dashboard)/purchases/demands/[id]/edit/page.tsx"
git commit -m "feat(purchase-ui): demand entry form — quantity-only, no rates (#137 P1)"
```

---

### Task 10: Quotation entry form

**Files:**
- Create: `frontend/src/app/(dashboard)/purchases/demands/[id]/quotations/new/page.tsx`

**Interfaces:**
- Consumes: `POST /api/quotations` (`QuoteIn` from Task 4), `GET /api/vendors`, demand detail.

- [ ] **Step 1: Build the form.** Loads the demand; renders vendor `<select>` (required), quote_date, valid_until, delivery/payment terms, notes, then **one row per demand line** (description + qty shown read-only from the demand; editable `rate` and `qty` inputs per row; amount = rate × qty computed live). Submit posts `{demand_id, vendor_id, quote_date, ..., lines: [{demand_line_id, rate, qty}]}` → back to demand detail. Show API error `detail` (e.g. "Quotations can only be added to an approved demand").

- [ ] **Step 2: Verify + commit**

```bash
cd frontend && npm run build
git add "frontend/src/app/(dashboard)/purchases/demands/[id]/quotations/new/page.tsx"
git commit -m "feat(purchase-ui): per-vendor quotation entry against demand lines (#137 P1)"
```

---

### Task 11: Comparatives list + matrix builder

**Files:**
- Create: `frontend/src/app/(dashboard)/purchases/comparatives/page.tsx`
- Create: `frontend/src/app/(dashboard)/purchases/comparatives/[id]/page.tsx`

**Interfaces:**
- Consumes: `GET /api/comparatives`, `GET/{id}` matrix shape (Task 5), `PUT/{id}`, `PATCH/{id}/approve`, `POST/{id}/convert-to-po`.

- [ ] **Step 1: List page** — mirror the demands list (columns: CS #, date, demand #, status; status filter chips).

- [ ] **Step 2: Matrix builder** — the centerpiece. Layout:
  - `<PrintHeader title={cs.number} subtitle={fmtDate(cs.cs_date)} />` — this page doubles as the CS print view (portrait).
  - Matrix table: first column = demand line (description, qty, unit — sticky via `.freeze-col` on the wrapper); one column per quotation (header: vendor name + VQ #; footer row: totals). Each cell shows rate and amount; **the lowest rate per row and the lowest total get a green highlight** (`bg-green-50 text-green-700 font-medium`; wrap the comparison in a helper `isLowest(cells, cell)` that ignores null cells).
  - Selection: radio per quotation column header (`disabled` unless `status === "draft"`); a justification `<textarea>` that renders with an amber note whenever `quotations.length < 2 || selected !== lowestTotalQuotationId` ("Justification required — selection is not the lowest quote / single quotation"). Save button → `PUT`.
  - Actions (all `print:hidden`, states driven by `cs.status`): **Approve** (PATCH; surface the 400 detail — self-approval and missing-justification errors land here), **Convert to PO** (POST → route to `/purchase-orders/${po.id}` — verify the existing PO detail route with `ls "frontend/src/app/(dashboard)" | grep -i purchase` and use it), status pill otherwise.

- [ ] **Step 3: Verify** — `npm run build`; manual browser pass of the full chain: demand → approve (second user) → 2 quotations → CS → select + justify → approve → convert → PO appears in the PO list.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)/purchases/comparatives/page.tsx" "frontend/src/app/(dashboard)/purchases/comparatives/[id]/page.tsx"
git commit -m "feat(purchase-ui): comparative matrix builder — lowest highlight, justify, convert (#137 P1)"
```

---

### Task 12: Settings toggle, docs delta, final verification

**Files:**
- Modify: `frontend/src/context/SettingsContext.tsx` (add `require_purchase_chain` to `AppSettings` + defaults)
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx` (toggle)
- Modify: `CLAUDE.md`, `README.md`, `BLUEPRINT.md`, `WORKFLOW.md`, `backend/README.md` (docs delta)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Settings toggle.** Add `require_purchase_chain: string` to the `AppSettings` interface with default `"true"`. On the Settings page, next to the `block_negative_stock` control (mirror its exact markup), add: label "Require purchase chain (Demand → Comparative → PO)", helper text "New purchase orders must come from an approved comparative statement", visible only when `installedModules.has("purchase_store")` (via `useModules()`).

- [ ] **Step 2: Docs delta** (follow the v3.2 delta commit `bc683ab` as the template):
  - `CLAUDE.md`: routers table rows for `purchase_demands.py`/`quotations.py`/`comparatives.py`; 8 → 9 modules in the db.py row; `require_purchase_chain` in the settings list.
  - `README.md`: "Purchases & Store module (v3.3)" feature block (demand → comparative → PO chain, approver ≠ creator, lowest-or-justify); module count 8 → 9.
  - `BLUEPRINT.md`: `purchase_store` row in the MODULE_REGISTRY table; `/api/purchase-demands`, `/api/quotations`, `/api/comparatives` endpoint sections; Sprint 23 table.
  - `WORKFLOW.md`: API table rows; a "Purchase chain (v3.3)" section describing the enforcement rule.
  - `backend/README.md`: 58 → 61 routers; three new router lines in the structure tree.

- [ ] **Step 3: Full verification**

```bash
cd backend && PYTHONPATH=. uv run pytest -q 2>&1 | tail -3   # baseline failures only
cd ../frontend && npm run build 2>&1 | tail -3               # clean build
```

- [ ] **Step 4: Commit + hand off**

```bash
git add -A && git commit -m "feat(purchase): settings toggle + v3.3 docs delta (#137 P1)"
```

Then use `superpowers:finishing-a-development-branch` — expected outcome: PR titled "feat: Purchase Demand + Comparative Statement — #137 Phase 1" referencing issue #137 and the spec.

---

## Self-Review Notes

- **Spec coverage:** models/migration (T1), module+permissions (T2), demands router (T3), quotations + freeze rule (T4), CS + lowest-or-justify + approver≠creator + convert (T5), chain enforcement + setting (T6), nav + notForModule (T7), 6 pages incl. matrix + PD/CS print views (T8–T11), settings toggle + docs (T12). `my_data_only` covered via `apply_own_filter` in T3. Uninstall-blocked-while-documents-exist: **deliberately deferred to Phase 2** — the modules router has no per-module uninstall hooks today and the generic mechanism belongs with the module's completion; noted here so it isn't silently lost.
- **Type consistency:** `_serialize`/`_get_demand`/`_get_cs`/`_get_quote` names consistent; `DemandIn`/`QuoteIn`/`CSCreate`/`CSUpdate` match between router code and test payloads; PO constructor uses the two new columns from T1.
- **Known verify-points for executors** (marked inline): `POST /api/users` body shape (T3), vendor-create body (T4), analytic-accounts route (T9), TITLE_MAP shape (T7), PO detail route (T11).
