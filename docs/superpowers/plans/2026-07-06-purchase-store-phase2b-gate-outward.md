# Purchase/Store Phase 2b — Gate Outward Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Gate Outward — the dispatch-side mirror of Gate Inward — covering sales-invoice exits, purchase-return (debit-note) exits, and scrap disposal (with its own draft→approve→GL workflow).

**Architecture:** One `GateOutward`/`GateOutwardLine` table pair with a `source_doc_type` discriminator (`invoice`/`debit_note`/`scrap`). Invoice/debit-note exits are pure memo (create = approved, no GL). Scrap exits are the one case where the Gate Outward entry IS the transaction: created as `draft`, and only `PATCH /{id}/approve` posts GL (via a small, backward-compatible extension to `services/inventory.py::consume_stock`) and relieves stock. Spec: `docs/superpowers/specs/2026-07-06-purchase-store-phase2b-gate-outward-design.md`.

**Tech Stack:** FastAPI + SQLModel + Alembic (backend), Next.js 16 App Router + Tailwind v4 (frontend), pytest.

## Global Constraints

- Run backend tests from `backend/` as: `PYTHONPATH=. uv run pytest tests/<file> -q`, FOREGROUND only.
- 2 pre-existing failures on main (`test_account_hierarchy.py::test_cannot_create_child_under_posted_account`, `test_update_migration.py::test_upgrade_over_create_all_db_is_safe`) — not yours, don't chase.
- All new tables tenant-scoped; every query filters `tenant_id`. Voucher `GO-YYYY-seq` via `next_number(session, tenant_id, "gate_outward", "GO", fmt="{prefix}-{YYYY}-{seq:04d}")`.
- Migration: new file `0031_gate_outward.py`, revises `0030_gate_inward`; `bind.dialect.has_table(...)` guard per repo convention (SQLite can't ALTER-ADD constraints).
- Frontend: every new route goes into BOTH `NAV` and `SUB_NAV` + `SECTION_PREFIXES` in `frontend/src/lib/nav.ts` (standing requirement — regression 2026-07-05). Dates via `fmtDate()`; amounts via `fmt()` from `useFmt()`; no voucher-type badges; `print:hidden` on toolbars.
- Money values: `from services.money import D, money`.
- Invoice eligibility for Gate Outward: any status EXCEPT `"void"` (stock is consumed at invoice *creation* regardless of draft/sent/paid status, so draft is a valid dispatch source — only `void` signals "this never happened / don't ship").
- DebitNote eligibility: exclude status `"draft"` defensively (in current code, `create_debit_note` always commits with `status="posted"` in the same call, so no real draft DN persists — but the CheckConstraint allows it, so guard anyway).
- Commit after every task with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

---

### Task 1: Models, migration, permission resource

**Files:**
- Modify: `backend/models.py` (after `DebitNoteLine`, ~line 1167)
- Create: `backend/alembic/versions/0031_gate_outward.py`
- Modify: `backend/services/permissions.py:44` (after `purchase.gate`)
- Test: `backend/tests/test_gate_outward.py` (new)

**Interfaces:**
- Produces: `models.GateOutward` (`id, tenant_id, number, source_doc_type, source_doc_id, gate_date, time_out, vehicle_no, challan_no, remarks, status, created_by_id, approved_by_id, approved_at, cancel_reason, created_at`), `models.GateOutwardLine` (`id, gate_outward_id, product_id, qty, unit_cost, unit_value`), permission key `"store.gate_outward"`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_gate_outward.py`:

```python
"""#137 Phase 2b — Gate Outward: invoice/debit-note memo exits + scrap draft→approve."""
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


def test_gate_outward_models_and_permission_registered(client: TestClient):
    from models import GateOutward, GateOutwardLine  # importable = tables exist
    from services.permissions import PERMISSION_RESOURCES
    assert "store.gate_outward" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["store.gate_outward"]["category"] == "Store"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py -q`
Expected: FAIL — `ImportError: cannot import name 'GateOutward'`

- [ ] **Step 3: Add models**

In `backend/models.py`, directly after `class DebitNoteLine` (~line 1167):

```python
class GateOutward(SQLModel, table=True):
    """Dispatch exit at the gate (#137 Phase 2b). Mirrors GateInward but for
    goods leaving: invoice/debit_note sources are pure memo (stock already
    left the books when the source document was created/posted); scrap has
    no source document — its own approval IS the transaction that consumes
    stock and posts GL."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_go_number_per_tenant"),
        CheckConstraint("status IN ('draft','approved','cancelled')", name="ck_go_status"),
        CheckConstraint(
            "source_doc_type IN ('invoice','debit_note','scrap')",
            name="ck_go_source_doc_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)                        # GO-YYYY-seq
    source_doc_type: str                                   # invoice | debit_note | scrap
    source_doc_id: Optional[int] = None                    # null only for scrap
    gate_date: str
    time_out: Optional[str] = None                         # "HH:MM"
    vehicle_no: Optional[str] = None
    challan_no: Optional[str] = None
    remarks: Optional[str] = None
    status: str = Field(default="draft")                   # draft | approved | cancelled
    created_by_id: int = Field(foreign_key="user.id")
    approved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    approved_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GateOutwardLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_go_line_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    gate_outward_id: int = Field(foreign_key="gateoutward.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id")
    qty: Money = money_col()
    unit_cost: Money = money_col(default=Decimal("0"))     # scrap only
    unit_value: Money = money_col(default=Decimal("0"))    # scrap only
```

- [ ] **Step 4: Register permission resource**

In `backend/services/permissions.py`, after the `purchase.gate` line (line 44):

```python
    "store.gate_outward":     {"label": "Gate Outward",            "category": "Store"},
```

- [ ] **Step 5: Create migration**

Create `backend/alembic/versions/0031_gate_outward.py`:

```python
"""gate outward (#137 Phase 2b)

Revision ID: 0031_gate_outward
Revises: 0030_gate_inward
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0031_gate_outward'
down_revision: Union[str, Sequence[str], None] = '0030_gate_inward'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'gateoutward'):
        op.create_table('gateoutward',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('source_doc_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('source_doc_id', sa.Integer(), nullable=True),
        sa.Column('gate_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('time_out', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('vehicle_no', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('challan_no', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('remarks', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('cancel_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('draft','approved','cancelled')", name='ck_go_status'),
        sa.CheckConstraint("source_doc_type IN ('invoice','debit_note','scrap')", name='ck_go_source_doc_type'),
        sa.ForeignKeyConstraint(['approved_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'number', name='unique_go_number_per_tenant')
        )
        op.create_index(op.f('ix_gateoutward_number'), 'gateoutward', ['number'], unique=False)
        op.create_index(op.f('ix_gateoutward_tenant_id'), 'gateoutward', ['tenant_id'], unique=False)

    if not bind.dialect.has_table(bind, 'gateoutwardline'):
        op.create_table('gateoutwardline',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gate_outward_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('unit_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.CheckConstraint('qty > 0', name='ck_go_line_qty_positive'),
        sa.ForeignKeyConstraint(['gate_outward_id'], ['gateoutward.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_gateoutwardline_gate_outward_id'), 'gateoutwardline', ['gate_outward_id'], unique=False)


def downgrade() -> None:
    op.drop_table('gateoutwardline')
    op.drop_table('gateoutward')
```

- [ ] **Step 6: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py -q`
Expected: 1 passed

- [ ] **Step 7: Verify migration runs**

Run: `PYTHONPATH=. uv run alembic upgrade head`
Expected: no error; `0031_gate_outward` applied.

- [ ] **Step 8: Commit**

```bash
git add backend/models.py backend/alembic/versions/0031_gate_outward.py backend/services/permissions.py backend/tests/test_gate_outward.py
git commit -m "feat(gate-outward): GateOutward models + migration 0031 + store.gate_outward resource (#137 P2b)"
```

---

### Task 2: `consume_stock` source_doc_type parameter

**Files:**
- Modify: `backend/services/inventory.py` (`consume_stock` signature ~line 168, `record_movement` call ~line 265)
- Test: `backend/tests/test_gate_outward.py` (append)

**Interfaces:**
- Produces: `consume_stock(session, *, tenant_id, product_id, qty, block_negative=False, source_doc_id=None, source_doc_type="invoice") -> Decimal` — new optional kwarg, existing three call sites (`routers/invoices.py:52,65`, `routers/production_orders.py:453`) untouched and unaffected (default preserves current "invoice" tagging).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_gate_outward.py`:

```python
def test_consume_stock_accepts_source_doc_type_override(client: TestClient):
    """Existing callers (invoices) still get 'invoice'; new callers can override."""
    from decimal import Decimal
    from sqlmodel import Session, select
    from models import Product, StockMovement, Tenant
    from services.inventory import consume_stock
    import db as _db

    with Session(_db.engine) as s:
        t = Tenant(name="ConsCo"); s.add(t); s.commit(); s.refresh(t)
        p = Product(tenant_id=t.id, name="Widget", product_type="stock",
                    stock_qty=Decimal("50"), avg_cost=Decimal("10"))
        s.add(p); s.commit(); s.refresh(p)

        cogs = consume_stock(
            s, tenant_id=t.id, product_id=p.id, qty=Decimal("5"),
            source_doc_id=999, source_doc_type="gate_outward",
        )
        s.commit()
        assert cogs == Decimal("50")  # 5 * avg_cost(10)

        mv = s.exec(
            select(StockMovement).where(StockMovement.product_id == p.id)
        ).first()
        assert mv.source_doc_type == "gate_outward"
        assert mv.source_doc_id == 999
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py::test_consume_stock_accepts_source_doc_type_override -q`
Expected: FAIL — `TypeError: consume_stock() got an unexpected keyword argument 'source_doc_type'`

- [ ] **Step 3: Add the parameter**

In `backend/services/inventory.py`, change the `consume_stock` signature (~line 168):

```python
def consume_stock(
    session: Session,
    *,
    tenant_id: int,
    product_id: int,
    qty: Decimal,
    block_negative: bool = False,
    source_doc_id: Optional[int] = None,
    source_doc_type: str = "invoice",
) -> Decimal:
```

Update its docstring's `source_doc_id` note to also mention the new param:

```python
    source_doc_id: the originating document's id so the resulting
    StockMovement can be looked up by (source_doc_type, source_doc_id).
    source_doc_type: defaults to 'invoice' (existing behavior for every
    current caller); pass an override for non-invoice consumers (e.g.
    'gate_outward' for scrap disposal).
```

In the `record_movement(...)` call inside `consume_stock` (~line 265), change:

```python
            source_doc_type="invoice",
```

to:

```python
            source_doc_type=source_doc_type,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py -q`
Expected: 2 passed

- [ ] **Step 5: Regression-check existing callers unaffected**

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py tests/test_gate_inward.py -q`
Expected: all pass (unrelated to this change — proves the default kwarg didn't disturb existing invoice/production-order consumption).

- [ ] **Step 6: Commit**

```bash
git add backend/services/inventory.py backend/tests/test_gate_outward.py
git commit -m "feat(gate-outward): consume_stock accepts source_doc_type override (#137 P2b)"
```

---

### Task 3: Gate Outward router — invoice/debit-note memo exits

**Files:**
- Create: `backend/routers/gate_outward.py`
- Modify: `backend/main.py` (mount — copy the `gate_inward` router's include pattern)
- Test: `backend/tests/test_gate_outward.py` (append)

**Interfaces:**
- Produces: `GET/POST /api/gate-outwards`, `GET /api/gate-outwards/{id}`, `PATCH /api/gate-outwards/{id}/cancel`. This task covers ONLY `source_doc_type in ("invoice", "debit_note")` — the `approve` endpoint and scrap creation land in Task 4.
- Create body: `{source_doc_type, source_doc_id?, gate_date, time_out?, vehicle_no?, challan_no?, remarks?, lines: [{product_id, qty}]}`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_gate_outward.py`:

```python
def _posted_invoice(client, auth, lines=None):
    r = client.post("/api/invoices", headers=auth, json={
        "issue_date": "2026-07-06", "due_date": "2026-08-06",
        "customer_name": "Walk-in Customer",
        "lines": lines or [{"description": "Widget", "qty": 3, "rate": 20}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_go_invoice_memo_lifecycle(client: TestClient):
    auth = _signup(client, "go1@t.com")
    inv = _posted_invoice(client, auth)

    r = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv["id"],
        "gate_date": "2026-07-06", "vehicle_no": "LEB-1111",
        "lines": [{"product_id": inv["lines"][0]["product_id"], "qty": 3}],
    })
    assert r.status_code == 201, r.text
    go = r.json()
    assert go["number"].startswith("GO-")
    assert go["status"] == "approved"  # immediate, no draft step for memo exits

    r = client.patch(f"/api/gate-outwards/{go['id']}/cancel", headers=auth,
                     json={"reason": "wrong truck logged"})
    assert r.status_code == 200
    assert client.get(f"/api/gate-outwards/{go['id']}", headers=auth).json()["status"] == "cancelled"


def test_go_rejects_void_invoice_and_foreign_tenant(client: TestClient):
    auth = _signup(client, "go2@t.com")
    inv = _posted_invoice(client, auth)
    client.post("/api/invoices/bulk", headers=auth,
                json={"ids": [inv["id"]], "action": "void"})
    r = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv["id"],
        "gate_date": "2026-07-06",
        "lines": [{"product_id": inv["lines"][0]["product_id"], "qty": 1}],
    })
    assert r.status_code == 400
    assert "void" in r.json()["detail"].lower()

    auth_b = _signup(client, "go2b@t.com")
    inv_a = _posted_invoice(client, auth)
    r = client.post("/api/gate-outwards", headers=auth_b, json={
        "source_doc_type": "invoice", "source_doc_id": inv_a["id"],
        "gate_date": "2026-07-06",
        "lines": [{"product_id": inv_a["lines"][0]["product_id"], "qty": 1}],
    })
    assert r.status_code == 404


def test_go_multiple_partial_exits_allowed_for_same_invoice(client: TestClient):
    """Reconciliation-only, not enforcement — no qty cap, batched shipment is fine."""
    auth = _signup(client, "go3@t.com")
    inv = _posted_invoice(client, auth, lines=[{"description": "Widget", "qty": 10, "rate": 5}])
    pid = inv["lines"][0]["product_id"]
    for _ in range(2):
        r = client.post("/api/gate-outwards", headers=auth, json={
            "source_doc_type": "invoice", "source_doc_id": inv["id"],
            "gate_date": "2026-07-06",
            "lines": [{"product_id": pid, "qty": 10}],  # deliberately over — no cap
        })
        assert r.status_code == 201, r.text
```

(Verified: `POST /api/invoices/bulk` takes `BulkInvoiceAction{ids: list[int], action: Literal["mark_sent","void","delete"]}` — `backend/routers/invoices.py:970-977`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py -q`
Expected: 3 new FAIL with 404 (routes not mounted).

- [ ] **Step 3: Implement `backend/routers/gate_outward.py`**

```python
"""Gate Outward — dispatch exit at the gate (#137 Phase 2b).

invoice/debit_note sources are pure memo: stock already left the books
when the source document was created/posted, so this only records the
physical exit for reconciliation. Scrap has no source document and its
own approval endpoint (see Task 4) is the transaction that consumes stock
and posts GL — this file's create/list/get/cancel handle all three types,
but only invoice/debit_note reach 'approved' immediately at creation.
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import DebitNote, GateOutward, GateOutwardLine, Invoice
from routers.common import SessionDep, WriteUserDep, log_audit, next_number
from services.money import D
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(
    prefix="/api/gate-outwards", tags=["gate-outwards"],
    dependencies=[perm_dep("store.gate_outward")],
)


class GOLineIn(BaseModel):
    product_id: int
    qty: float
    unit_cost: float = 0
    unit_value: float = 0


class GOIn(BaseModel):
    source_doc_type: str
    source_doc_id: Optional[int] = None
    gate_date: str
    time_out: Optional[str] = None
    vehicle_no: Optional[str] = None
    challan_no: Optional[str] = None
    remarks: Optional[str] = None
    lines: List[GOLineIn] = []


class GOCancel(BaseModel):
    reason: str


def _get_go(session, user, go_id: int) -> GateOutward:
    go = session.exec(
        select(GateOutward).where(
            GateOutward.id == go_id, GateOutward.tenant_id == user.tenant_id
        )
    ).first()
    if not go:
        raise HTTPException(404, "Gate outward not found")
    return go


def _serialize(session, go: GateOutward) -> dict:
    lines = session.exec(
        select(GateOutwardLine).where(GateOutwardLine.gate_outward_id == go.id)
    ).all()
    out = go.model_dump()
    out["lines"] = [l.model_dump() for l in lines]
    if go.source_doc_type == "invoice" and go.source_doc_id:
        inv = session.get(Invoice, go.source_doc_id)
        out["reference"] = inv.number if inv else None
    elif go.source_doc_type == "debit_note" and go.source_doc_id:
        dn = session.get(DebitNote, go.source_doc_id)
        out["reference"] = dn.number if dn else None
    else:
        out["reference"] = "Scrap"
    return out


def _validate_source_doc(session, user, source_doc_type: str, source_doc_id: Optional[int]) -> None:
    if source_doc_type == "invoice":
        inv = session.exec(
            select(Invoice).where(Invoice.id == source_doc_id, Invoice.tenant_id == user.tenant_id)
        ).first()
        if not inv:
            raise HTTPException(404, "Invoice not found")
        if inv.status == "void":
            raise HTTPException(400, "Cannot record a gate exit against a void invoice")
    elif source_doc_type == "debit_note":
        dn = session.exec(
            select(DebitNote).where(DebitNote.id == source_doc_id, DebitNote.tenant_id == user.tenant_id)
        ).first()
        if not dn:
            raise HTTPException(404, "Debit note not found")
        if dn.status == "draft":
            raise HTTPException(400, "Cannot record a gate exit against a draft debit note")
    elif source_doc_type != "scrap":
        raise HTTPException(400, f"Unknown source_doc_type: {source_doc_type!r}")


@router.get("")
def list_gos(
    session: SessionDep, user: WriteUserDep,
    source_doc_type: Optional[str] = None, status: Optional[str] = None,
):
    q = select(GateOutward).where(GateOutward.tenant_id == user.tenant_id)
    if source_doc_type:
        q = q.where(GateOutward.source_doc_type == source_doc_type)
    if status:
        q = q.where(GateOutward.status == status)
    q = apply_own_filter(q, GateOutward, user, session)
    rows = session.exec(q.order_by(GateOutward.id.desc())).all()
    return [_serialize(session, go) for go in rows]


@router.get("/{go_id}")
def get_go(session: SessionDep, user: WriteUserDep, go_id: int):
    return _serialize(session, _get_go(session, user, go_id))


@router.post("", status_code=201)
def create_go(session: SessionDep, user: WriteUserDep, body: GOIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    if body.source_doc_type in ("invoice", "debit_note") and not body.source_doc_id:
        raise HTTPException(400, "source_doc_id is required for this source_doc_type")

    _validate_source_doc(session, user, body.source_doc_type, body.source_doc_id)

    # Memo exits (invoice/debit_note) go straight to 'approved' — nothing to
    # approve, no GL/stock effect. Scrap creation (draft + approval) is Task 4.
    status = "approved" if body.source_doc_type in ("invoice", "debit_note") else "draft"

    number = next_number(
        session, user.tenant_id, "gate_outward", "GO", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    go = GateOutward(
        tenant_id=user.tenant_id, number=number,
        source_doc_type=body.source_doc_type, source_doc_id=body.source_doc_id,
        gate_date=body.gate_date, time_out=body.time_out,
        vehicle_no=body.vehicle_no, challan_no=body.challan_no,
        remarks=body.remarks, status=status, created_by_id=user.id,
    )
    session.add(go)
    session.flush()
    for l in body.lines:
        if D(l.qty) <= 0:
            raise HTTPException(400, "qty must be positive")
        session.add(GateOutwardLine(
            gate_outward_id=go.id, product_id=l.product_id, qty=D(l.qty),
            unit_cost=D(l.unit_cost), unit_value=D(l.unit_value),
        ))
    log_audit(session, user, "CREATE", "gate_outward", go.id, {"number": number})
    session.commit()
    return _serialize(session, go)


@router.patch("/{go_id}/cancel")
def cancel_go(session: SessionDep, user: WriteUserDep, go_id: int, body: GOCancel):
    go = _get_go(session, user, go_id)
    if not body.reason.strip():
        raise HTTPException(400, "A cancellation reason is required")
    if go.status == "cancelled":
        raise HTTPException(400, "Gate outward is already cancelled")
    if go.source_doc_type == "scrap" and go.status == "approved":
        raise HTTPException(400, "Cannot cancel an approved scrap entry — GL has been posted")
    go.status = "cancelled"
    go.cancel_reason = body.reason.strip()
    session.add(go)
    log_audit(session, user, "UPDATE", "gate_outward", go.id,
              {"action": "cancelled", "reason": go.cancel_reason})
    session.commit()
    return {"success": True, "status": "cancelled"}
```

- [ ] **Step 4: Mount the router**

In `backend/main.py`, add `gate_outward` alongside the `gate_inward` import/include.

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py -q`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/routers/gate_outward.py backend/main.py backend/tests/test_gate_outward.py
git commit -m "feat(gate-outward): router — invoice/debit-note memo exits, list/get/cancel (#137 P2b)"
```

---

### Task 4: Scrap draft→approve workflow + GL posting

**Files:**
- Modify: `backend/routers/gate_outward.py` (add the approve endpoint + scrap-aware create validation)
- Test: `backend/tests/test_gate_outward.py` (append)

**Interfaces:**
- Produces: `PATCH /api/gate-outwards/{id}/approve` — scrap only.
- Consumes: `services.inventory.consume_stock(..., source_doc_type="gate_outward")` (Task 2), `services.posting.post_transaction`/`EntryInput`, `routers.common.get_or_create_account`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_gate_outward.py`:

```python
def _stock_product(client, auth, qty=100, avg_cost=10):
    """Create a stock product with a known qty/avg_cost by inserting it
    directly (bypassing the product-creation API, which has no field for
    pre-setting stock_qty/avg_cost — those only move via consume_stock/
    receive_stock in normal use)."""
    from decimal import Decimal
    from sqlmodel import Session
    from models import Product
    import db as _db
    r = client.get("/api/auth/me", headers=auth)
    tenant_id = r.json()["tenant"]["id"]
    with Session(_db.engine) as s:
        p = Product(tenant_id=tenant_id, name="Scrap Widget", product_type="stock",
                    stock_qty=Decimal(str(qty)), avg_cost=Decimal(str(avg_cost)))
        s.add(p); s.commit(); s.refresh(p)
        return p.id


def test_go_scrap_draft_then_approve_posts_gl_and_relieves_stock(client: TestClient):
    auth = _signup(client, "go4@t.com")
    pid = _stock_product(client, auth, qty=100, avg_cost=Decimal("10") if False else 10)

    r = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 5, "unit_cost": 10, "unit_value": 2}],
    })
    assert r.status_code == 201, r.text
    go = r.json()
    assert go["status"] == "draft"

    # draft: no GL, no stock change yet
    from decimal import Decimal as Dec
    prod = client.get(f"/api/products/{pid}", headers=auth).json()
    assert Dec(str(prod["stock_qty"])) == Dec("100")

    r = client.patch(f"/api/gate-outwards/{go['id']}/approve", headers=auth)
    assert r.status_code == 200, r.text
    go_after = client.get(f"/api/gate-outwards/{go['id']}", headers=auth).json()
    assert go_after["status"] == "approved"

    prod_after = client.get(f"/api/products/{pid}", headers=auth).json()
    assert Dec(str(prod_after["stock_qty"])) == Dec("95")


def test_go_scrap_self_approval_blocked(client: TestClient):
    auth = _signup(client, "go5@t.com")
    pid = _stock_product(client, auth)
    go = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 1, "unit_cost": 10}],
    }).json()
    r = client.patch(f"/api/gate-outwards/{go['id']}/approve", headers=auth)
    assert r.status_code == 400
    assert "self" in r.json()["detail"].lower() or "creator" in r.json()["detail"].lower()


def test_go_scrap_cancel_allowed_only_while_draft(client: TestClient):
    auth = _signup(client, "go6@t.com")
    pid = _stock_product(client, auth)
    go = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 1, "unit_cost": 10}],
    }).json()
    r = client.patch(f"/api/gate-outwards/{go['id']}/cancel", headers=auth,
                     json={"reason": "wrong product"})
    assert r.status_code == 200

    go2 = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 1, "unit_cost": 10}],
    }).json()
    auth2 = _second_admin(client, auth)
    client.patch(f"/api/gate-outwards/{go2['id']}/approve", headers=auth2)
    r = client.patch(f"/api/gate-outwards/{go2['id']}/cancel", headers=auth,
                     json={"reason": "too late"})
    assert r.status_code == 400


def _second_admin(client, auth, email="approver2@t.com"):
    client.post("/api/users", headers=auth, json={
        "email": email, "password": "password123", "full_name": "Approver", "role": "admin",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_go_scrap_gl_balanced_with_revenue_leg(client: TestClient):
    """value > 0 posts BOTH the revenue JV and the expense/inventory JV."""
    auth = _signup(client, "go7@t.com")
    pid = _stock_product(client, auth, qty=50, avg_cost=8)
    go = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 10, "unit_cost": 8, "unit_value": 3}],
    }).json()
    auth2 = _second_admin(client, auth)
    r = client.patch(f"/api/gate-outwards/{go['id']}/approve", headers=auth2)
    assert r.status_code == 200, r.text

    from decimal import Decimal

    def _find_account(node, code):
        if node.get("code") == code:
            return node
        for child in node.get("children") or []:
            found = _find_account(child, code)
            if found is not None:
                return found
        return None

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    def bal(code):
        for node in tb["tree"]:
            found = _find_account(node, code)
            if found is not None:
                return found
        return None

    cash = bal("1000")
    scrap_rev = bal("4902")
    scrap_exp = bal("5901")
    assert cash is not None and Decimal(str(cash["debit"])) == Decimal("30")   # 10 * unit_value(3)
    assert scrap_rev is not None and Decimal(str(scrap_rev["credit"])) == Decimal("30")
    assert scrap_exp is not None and Decimal(str(scrap_exp["debit"])) == Decimal("80")  # 10 * unit_cost(8)
```

(Response shape verified: `GET /api/reports/trial-balance` returns
`{"tree": [...], "totals": {...}}`; each tree node carries `code`,
`debit`, `credit`, `children` — `services/account_tree.py:46-54`,
`routers/reports.py:80-111`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py -q`
Expected: new tests FAIL — approve endpoint doesn't exist (404), or `import Decimal` missing at top of test file (add `from decimal import Decimal` to the test file's imports if not already present from Task 2).

- [ ] **Step 3: Implement the approve endpoint**

Add to `backend/routers/gate_outward.py` (imports first — add these to the top of the file):

```python
from datetime import datetime

from models import GateOutwardLine as _GOLine  # already imported above; no-op if present
from routers.common import AdminUserDep, get_or_create_account
from services.inventory import consume_stock
from services.money import money
from services.posting import EntryInput, post_transaction
```

(Merge these into the existing import block from Task 3 rather than duplicating — `AdminUserDep`, `get_or_create_account` join the existing `routers.common` import line; `consume_stock`, `EntryInput`/`post_transaction`, `money` are new lines.)

Then add the endpoint:

```python
@router.patch("/{go_id}/approve")
def approve_go(session: SessionDep, user: AdminUserDep, go_id: int):
    go = _get_go(session, user, go_id)
    if go.source_doc_type != "scrap":
        raise HTTPException(400, "Only scrap gate-outward entries require approval")
    if go.status != "draft":
        raise HTTPException(400, f"Cannot approve a gate outward with status '{go.status}'")
    if go.created_by_id == user.id:
        raise HTTPException(400, "A gate outward cannot be approved by its creator")

    lines = session.exec(
        select(GateOutwardLine).where(GateOutwardLine.gate_outward_id == go.id)
    ).all()

    total_cost = D("0")
    total_value = D("0")
    for l in lines:
        cogs = consume_stock(
            session, tenant_id=user.tenant_id, product_id=l.product_id,
            qty=D(l.qty), source_doc_id=go.id, source_doc_type="gate_outward",
        )
        total_cost += cogs
        total_value += D(l.qty) * D(l.unit_value)

    if total_value > 0:
        cash_acc = get_or_create_account(session, user.tenant_id, "1000", "Cash in Hand", "Asset")
        scrap_rev_acc = get_or_create_account(session, user.tenant_id, "4902", "Scrap Sales", "Revenue")
        post_transaction(
            session, user, date=go.gate_date,
            description=f"Scrap sale proceeds — {go.number}",
            entries=[
                EntryInput(account_id=cash_acc.id, debit=money(total_value)),
                EntryInput(account_id=scrap_rev_acc.id, credit=money(total_value)),
            ],
            voucher_type="JV",
            audit_entity_type="gate_outward",
            audit_detail={"go_number": go.number, "leg": "scrap_revenue"},
        )

    if total_cost > 0:
        scrap_exp_acc = get_or_create_account(session, user.tenant_id, "5901", "Scrap Disposal Expense", "Expense")
        inv_acc = get_or_create_account(session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset")
        post_transaction(
            session, user, date=go.gate_date,
            description=f"Scrap disposal cost — {go.number}",
            entries=[
                EntryInput(account_id=scrap_exp_acc.id, debit=money(total_cost)),
                EntryInput(account_id=inv_acc.id, credit=money(total_cost)),
            ],
            voucher_type="JV",
            audit_entity_type="gate_outward",
            audit_detail={"go_number": go.number, "leg": "scrap_cost"},
        )

    go.status = "approved"
    go.approved_by_id = user.id
    go.approved_at = datetime.utcnow()
    session.add(go)
    log_audit(session, user, "UPDATE", "gate_outward", go.id, {"action": "approved"})
    session.commit()
    return {"success": True, "status": "approved"}
```

(Verified: `"1200", "Inventory (Raw Material)"` is the exact code/name pair
`routers/debit_notes.py:134` already uses for the same purpose — matching it
here means scrap postings land on the same Inventory account every other
stock-relieving transaction uses, not a second competing leaf account.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/gate_outward.py backend/tests/test_gate_outward.py
git commit -m "feat(gate-outward): scrap draft-to-approve workflow with GL posting (#137 P2b)"
```

---

### Task 5: Store reports — gate-outward register + dispatch reconciliation

**Files:**
- Create: `backend/routers/store_reports.py`
- Modify: `backend/main.py` (mount)
- Test: `backend/tests/test_gate_outward.py` (append)

**Interfaces:**
- Produces:
  - `GET /api/store-reports/gate-outward-register?start=&end=&q=&source_doc_type=` → `[{go fields, reference, item_count, total_qty}]`
  - `GET /api/store-reports/dispatch-reconciliation?start=&end=` → `[{doc_type, doc_number, party, doc_date, has_gate_exit, go_number}]`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_gate_outward.py`:

```python
def test_gate_outward_register_and_search(client: TestClient):
    auth = _signup(client, "rep1@t.com")
    inv = _posted_invoice(client, auth)
    client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv["id"],
        "gate_date": "2026-07-06", "vehicle_no": "LEB-8888", "challan_no": "CH-501",
        "lines": [{"product_id": inv["lines"][0]["product_id"], "qty": 3}],
    })
    rows = client.get("/api/store-reports/gate-outward-register", headers=auth).json()
    assert len(rows) == 1
    assert rows[0]["reference"] == inv["number"]

    rows = client.get("/api/store-reports/gate-outward-register?q=CH-501", headers=auth).json()
    assert len(rows) == 1
    rows = client.get("/api/store-reports/gate-outward-register?q=NOPE", headers=auth).json()
    assert rows == []


def test_dispatch_reconciliation_flags_missing_exit(client: TestClient):
    auth = _signup(client, "rep2@t.com")
    inv_with_exit = _posted_invoice(client, auth)
    inv_without_exit = _posted_invoice(client, auth)
    client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv_with_exit["id"],
        "gate_date": "2026-07-06",
        "lines": [{"product_id": inv_with_exit["lines"][0]["product_id"], "qty": 3}],
    })
    rows = client.get("/api/store-reports/dispatch-reconciliation", headers=auth).json()
    by_number = {r["doc_number"]: r for r in rows}
    assert by_number[inv_with_exit["number"]]["has_gate_exit"] is True
    assert by_number[inv_without_exit["number"]]["has_gate_exit"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py -q`
Expected: 2 new FAIL with 404.

- [ ] **Step 3: Implement `backend/routers/store_reports.py`**

```python
"""Store-domain reports (#137 Phase 2b): gate-outward register + dispatch
reconciliation. Kept separate from purchase_reports.py — Gate Outward spans
Sales/Purchases/Inventory, not purely the purchase chain."""
from typing import Optional

from fastapi import APIRouter
from sqlmodel import select

from models import DebitNote, GateOutward, GateOutwardLine, Invoice
from routers.common import SessionDep, WriteUserDep
from services.money import D
from services.permissions import perm_dep

router = APIRouter(prefix="/api/store-reports", tags=["store-reports"])


@router.get("/gate-outward-register", dependencies=[perm_dep("store.gate_outward")])
def gate_outward_register(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    q: Optional[str] = None, source_doc_type: Optional[str] = None,
):
    query = select(GateOutward).where(GateOutward.tenant_id == user.tenant_id)
    if start:
        query = query.where(GateOutward.gate_date >= start)
    if end:
        query = query.where(GateOutward.gate_date <= end)
    if source_doc_type:
        query = query.where(GateOutward.source_doc_type == source_doc_type)
    gos = session.exec(query.order_by(GateOutward.id.desc())).all()

    out = []
    for go in gos:
        if q:
            needle = q.lower()
            hay = f"{go.vehicle_no or ''} {go.challan_no or ''}".lower()
            if needle not in hay:
                continue
        lines = session.exec(
            select(GateOutwardLine).where(GateOutwardLine.gate_outward_id == go.id)
        ).all()
        row = go.model_dump()
        if go.source_doc_type == "invoice" and go.source_doc_id:
            inv = session.get(Invoice, go.source_doc_id)
            row["reference"] = inv.number if inv else None
        elif go.source_doc_type == "debit_note" and go.source_doc_id:
            dn = session.get(DebitNote, go.source_doc_id)
            row["reference"] = dn.number if dn else None
        else:
            row["reference"] = "Scrap"
        row["item_count"] = len(lines)
        row["total_qty"] = sum(D(l.qty) for l in lines)
        out.append(row)
    return out


@router.get("/dispatch-reconciliation", dependencies=[perm_dep("store.gate_outward")])
def dispatch_reconciliation(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    exits_by_doc: dict[tuple[str, int], str] = {}
    for go in session.exec(
        select(GateOutward).where(
            GateOutward.tenant_id == user.tenant_id,
            GateOutward.status != "cancelled",
            GateOutward.source_doc_type.in_(["invoice", "debit_note"]),
        )
    ).all():
        exits_by_doc[(go.source_doc_type, go.source_doc_id)] = go.number

    out = []

    inv_query = select(Invoice).where(
        Invoice.tenant_id == user.tenant_id, Invoice.status != "void"
    )
    if start:
        inv_query = inv_query.where(Invoice.issue_date >= start)
    if end:
        inv_query = inv_query.where(Invoice.issue_date <= end)
    for inv in session.exec(inv_query).all():
        go_number = exits_by_doc.get(("invoice", inv.id))
        out.append({
            "doc_type": "invoice", "doc_number": inv.number,
            "party": inv.customer_name, "doc_date": inv.issue_date,
            "has_gate_exit": go_number is not None, "go_number": go_number,
        })

    dn_query = select(DebitNote).where(
        DebitNote.tenant_id == user.tenant_id, DebitNote.status != "draft"
    )
    if start:
        dn_query = dn_query.where(DebitNote.issue_date >= start)
    if end:
        dn_query = dn_query.where(DebitNote.issue_date <= end)
    for dn in session.exec(dn_query).all():
        go_number = exits_by_doc.get(("debit_note", dn.id))
        out.append({
            "doc_type": "debit_note", "doc_number": dn.number,
            "party": dn.vendor_name, "doc_date": dn.issue_date,
            "has_gate_exit": go_number is not None, "go_number": go_number,
        })

    return out
```

- [ ] **Step 4: Mount** — add `store_reports` next to `gate_outward` in `backend/main.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/store_reports.py backend/main.py backend/tests/test_gate_outward.py
git commit -m "feat(gate-outward): gate-outward register + dispatch-reconciliation reports (#137 P2b)"
```

---

### Task 6: Permission-gated write endpoints + full backend test pass

**Files:**
- Modify: `backend/routers/gate_outward.py` (add edit-level dep to `create_go`/`cancel_go`, matching the fix applied to Gate Inward in Phase 2 final review)
- Test: `backend/tests/test_gate_outward.py` (append)

**Interfaces:**
- Consumes: `perm_dep("store.gate_outward", "edit")` — same idiom as `perm_dep("purchase.gate", "edit")` added to `gate_inward.py` in Phase 2's final-review fix (commit `864fbcd`).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_gate_outward.py`:

```python
def test_go_mutating_endpoints_require_edit_level(client: TestClient):
    auth = _signup(client, "go8@t.com")
    inv = _posted_invoice(client, auth)
    client.patch("/api/settings", headers=auth, json={"user_rights_enabled": "true"})
    client.post("/api/users", headers=auth, json={
        "email": "goviewer@t.com", "password": "password123",
        "full_name": "Viewer", "role": "accountant",
    })
    users = client.get("/api/users", headers=auth).json()
    uid = next(u["id"] for u in users if u["email"] == "goviewer@t.com")
    client.put(f"/api/permissions/users/{uid}", headers=auth,
              json=[{"resource_key": "store.gate_outward", "access_level": "view"}])
    r = client.post("/api/auth/login",
                    data={"username": "goviewer@t.com", "password": "password123"})
    viewer = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get("/api/gate-outwards", headers=viewer).status_code == 200
    r = client.post("/api/gate-outwards", headers=viewer, json={
        "source_doc_type": "invoice", "source_doc_id": inv["id"],
        "gate_date": "2026-07-06",
        "lines": [{"product_id": inv["lines"][0]["product_id"], "qty": 1}],
    })
    assert r.status_code == 403
```

(Verified: `PUT /api/permissions/users/{id}` takes a bare JSON array —
`updates: List[PermissionUpdate]`, each `{resource_key: str, access_level:
"none"|"view"|"edit"|"default"}` — `backend/routers/permissions.py:19-27,57-61`.
Not wrapped in an object.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py::test_go_mutating_endpoints_require_edit_level -q`
Expected: FAIL — POST returns 201/400 (validation reached) instead of 403.

- [ ] **Step 3: Add edit-level deps**

In `backend/routers/gate_outward.py`, change the route decorators:

```python
@router.post("", status_code=201, dependencies=[perm_dep("store.gate_outward", "edit")])
def create_go(...):
```

```python
@router.patch("/{go_id}/cancel", dependencies=[perm_dep("store.gate_outward", "edit")])
def cancel_go(...):
```

(`approve_go` already requires `AdminUserDep`, which is a stronger gate than `store.gate_outward` edit level — no change needed there.)

- [ ] **Step 4: Run the full gate-outward + gate-inward + purchase-flow suites**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_outward.py tests/test_gate_inward.py tests/test_purchase_flow.py -q`
Expected: all pass.

- [ ] **Step 5: Run the full backend suite**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: only the 2 known pre-existing failures.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/gate_outward.py backend/tests/test_gate_outward.py
git commit -m "feat(gate-outward): require edit-level permission on mutating endpoints (#137 P2b)"
```

---

### Task 7: Frontend — Store nav section + Gate Outward pages

**Files:**
- Modify: `frontend/src/lib/nav.ts` (new "Store" TOP_NAV section + SUB_NAV + SECTION_PREFIXES + ALL_SECTIONS + NAV entries)
- Create: `frontend/src/app/(dashboard)/store/gate-outward/page.tsx`
- Create: `frontend/src/app/(dashboard)/store/gate-outward/new/page.tsx`
- Create: `frontend/src/app/(dashboard)/store/gate-outward/[id]/page.tsx`

**Interfaces:**
- Consumes: `GET/POST /api/gate-outwards`, `GET /api/gate-outwards/{id}`, `PATCH /{id}/cancel`, `PATCH /{id}/approve`, `GET /api/invoices?status=...`, `GET /api/debit-notes`, `GET /api/products`.
- Pattern sources: Gate Inward's pages (`purchases/gate-inward/{page,new/page,[id]/page}.tsx`) for list/form/detail structure; adapt for the three-way source-type branch.

- [ ] **Step 1: Nav wiring**

In `frontend/src/lib/nav.ts`:

(a) `NavItem.forModule` union (line 21) already includes `"purchase_store"` — no change needed there.

(b) Add to `NAV` (after the Purchases block, before Inventory, ~line 62):

```ts
  { label: "Gate Outward",     href: "/store/gate-outward",              icon: DoorOpen,   section: "Store", forModule: "purchase_store" },
  { label: "Outward Register", href: "/store/gate-outward-register",     icon: ScrollText, section: "Store", forModule: "purchase_store" },
  { label: "Dispatch Recon",   href: "/store/dispatch-reconciliation",   icon: CheckCheck, section: "Store", forModule: "purchase_store" },
```

(`DoorOpen`, `ScrollText`, `CheckCheck` already imported from Phase 2's Gate Inward work.)

(c) Add `"Store"` to `ALL_SECTIONS` (line 137), after `"Purchases"`:

```ts
export const ALL_SECTIONS = ["Overview","Ledger","Receivable","Payable","Purchases","Store","Inventory","Manufacturing","Telecom","Healthcare","Banking","Reports","Payroll","System"]
```

(d) Widen `TopNavSection.forModule` (line 166) to include `"purchase_store"`:

```ts
  forModule?: "inventory" | "production" | "hrm" | "telecom" | "pra" | "healthcare" | "purchase_store"
```

(e) Add a `store` entry to `TOP_NAV` (after `purchases`, in the module-gated block):

```ts
  { key: "store",         label: "Store",         forModule: "purchase_store" },
```

(f) Add `store` to `SECTION_PREFIXES` (after `purchases`):

```ts
  store:         ["/store"],
```

(g) Add a `store` entry to `SUB_NAV` (mirroring the `purchases` block's shape):

```ts
  store: [
    { label: "Gate Outward",     href: "/store/gate-outward",            icon: DoorOpen,   section: "store", forModule: "purchase_store" },
    { label: "Outward Register", href: "/store/gate-outward-register",   icon: ScrollText, section: "store", forModule: "purchase_store" },
    { label: "Dispatch Recon",   href: "/store/dispatch-reconciliation", icon: CheckCheck, section: "store", forModule: "purchase_store" },
  ],
```

(h) Add `"Store"` to `getSectionHref`'s map (default landing when clicked):

```ts
    store:         "/store/gate-outward",
```

- [ ] **Step 2: List page** — `store/gate-outward/page.tsx`

Copy the structure of `purchases/gate-inward/page.tsx`. Columns: GO# (link to detail), Date, Type (Invoice/Debit Note/Scrap — plain text, no badge), Reference, Status. "New Gate Outward" link to `/store/gate-outward/new`.

- [ ] **Step 3: New form** — `store/gate-outward/new/page.tsx`

Structure from Gate Inward's new-form, adapted for the three-way branch:
- Radio/segmented control: Invoice / Debit Note / Scrap.
- Invoice/Debit Note selected: dropdown of documents (`apiFetch("/api/invoices")` filtered client-side to `status !== "void"`, or `/api/debit-notes` filtered to `status !== "draft"`); on selection, fetch the document and pre-fill lines (product + qty) as read-only display rows (qty comes from the source document, matching the spec's "reconciliation not control" design — no user-editable qty override for memo exits, since the point is recording what the document already says left).
- Scrap selected: bare line editor — product picker (`apiFetch("/api/products")`), qty input, unit_cost input (default: fetch the selected product's `avg_cost` and pre-fill), unit_value input (default 0).
- Header fields: gate_date (default today), time_out, vehicle_no, challan_no, remarks.
- Submit → `POST /api/gate-outwards`; on 201 `router.push` to detail; surface API `detail` string on 400/404.

- [ ] **Step 4: Detail page** — `store/gate-outward/[id]/page.tsx`

Structure from Gate Inward's detail page: `<PrintHeader title={go.number} subtitle={fmtDate(go.gate_date)} />` (portrait), header grid (type, reference, vehicle, challan, time-out, status), lines table. Actions (`print:hidden`):
- Print button.
- If `source_doc_type === "scrap" && status === "draft"`: "Approve" button (admin/owner only — check `getCurrentUser().role`), disabled with tooltip when `created_by_id === currentUser.id` ("You cannot approve your own entry"); calls `PATCH /{id}/approve`.
- Cancel button with inline reason input: shown when `status !== "cancelled"` AND NOT (`source_doc_type === "scrap" && status === "approved"`) — mirrors the backend's exact cancel-eligibility rule.

- [ ] **Step 5: Verify**

Run in `frontend/`: `npx tsc --noEmit && npx eslint src/lib/nav.ts "src/app/(dashboard)/store/gate-outward"`
Expected: clean (no new errors vs. the documented pre-existing baseline).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/nav.ts "frontend/src/app/(dashboard)/store/gate-outward"
git commit -m "feat(gate-outward-ui): Store nav section + gate-outward list/new/detail pages (#137 P2b)"
```

---

### Task 8: Frontend — register + reconciliation report pages

**Files:**
- Create: `frontend/src/app/(dashboard)/store/gate-outward-register/page.tsx`
- Create: `frontend/src/app/(dashboard)/store/dispatch-reconciliation/page.tsx`

**Interfaces:**
- Consumes: `GET /api/store-reports/gate-outward-register`, `GET /api/store-reports/dispatch-reconciliation`.

- [ ] **Step 1: Gate Outward Register page**

Copy the landscape-report skeleton from `purchases/gate-register/page.tsx`. `<PrintHeader title="Gate Outward Register" orientation="landscape" />`; filter bar (`print:hidden`): start/end dates + search + a source-type dropdown (All/Invoice/Debit Note/Scrap). Table in `.table-freeze`: GO#, Date, Type, Reference, Vehicle, Challan, Items, Qty (`fmt()`), Status.

- [ ] **Step 2: Dispatch Reconciliation page**

Same skeleton. `<PrintHeader title="Dispatch Reconciliation" orientation="landscape" />`; date-range filter. Table in `.table-freeze`: Doc Type, Doc #, Party, Date, Gate Exit (✓/✗ or the GO# if present). Rows where `has_gate_exit === false` get `className="bg-amber-50 dark:bg-amber-900/20"`.

- [ ] **Step 3: Verify**

Run in `frontend/`: `npx tsc --noEmit && npm run lint 2>&1 | tail -5` (no NEW errors vs. the documented pre-existing baseline).

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)/store/gate-outward-register" "frontend/src/app/(dashboard)/store/dispatch-reconciliation"
git commit -m "feat(gate-outward-ui): gate-outward register + dispatch-reconciliation report pages (#137 P2b)"
```

---

### Task 9: Docs delta + full verification

**Files:**
- Modify: `CLAUDE.md` (models.py row: extend the purchase-chain sentence with GateOutward/GateOutwardLine; routers table: add `gate_outward.py` + `store_reports.py`; add a note that `services/inventory.py::consume_stock` now accepts `source_doc_type`)
- Verify: full backend suite + frontend build + live e2e drive

- [ ] **Step 1: CLAUDE.md delta** — three edits:
  1. Extend the `models.py` row's purchase-chain sentence: `GateOutward (GO-YYYY-seq, dispatch exit — memo for invoice/debit_note sources, draft→approve with GL posting for scrap) + GateOutwardLine (#137 P2b).`
  2. Add router rows after `routers/purchase_reports.py`:
     - `routers/gate_outward.py` | Dispatch exit — memo for invoice/debit_note (create = approved, reconciliation only); scrap is draft→approve, GL posts only at approval via `consume_stock(..., source_doc_type="gate_outward")`. Gated by `store.gate_outward`.
     - `routers/store_reports.py` | Gate-outward register + dispatch reconciliation (posted invoices/debit-notes with no matching gate exit flagged).
  3. In the `block_negative_stock` settings bullet (`CLAUDE.md` line 151, the only existing mention of `consume_stock`), append: `consume_stock also accepts an optional source_doc_type override (default "invoice") so non-sale consumers — Gate Outward's scrap approval — tag their own StockMovement rows correctly instead of being mislabeled as invoices.`

- [ ] **Step 2: Full backend suite**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: only the 2 known pre-existing failures.

- [ ] **Step 3: Frontend build**

Run in `frontend/`: `npm run build`
Expected: builds clean.

- [ ] **Step 4: End-to-end drive**

Use the project verify skill (`.claude/skills/verify/SKILL.md`): launch both dev servers, log in as `demo.manufacturing@easy-books.app` / `demo1234`, and drive:
1. Create a sales invoice; record a Gate Outward against it (memo, immediate "approved").
2. Create a scrap Gate Outward (draft); confirm stock unchanged; log in as a second admin user and approve it; confirm stock decreased and the trial balance shows the new Scrap Sales/Scrap Disposal Expense accounts.
3. Open `/store/gate-outward-register` — both entries appear, search works.
4. Open `/store/dispatch-reconciliation` — the invoice with a gate exit shows ✓; create a second invoice with no exit and confirm it's flagged.
5. Screenshot the register and reconciliation pages.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md delta for gate outward (#137 P2b)"
```
