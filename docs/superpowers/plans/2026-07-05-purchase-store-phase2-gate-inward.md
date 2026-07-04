# Purchase/Store Phase 2 — Gate Inward Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Gate Inward (GI) control document between PO approval and billing, gate-register + 3-way-match reports, and land the three Phase-1 carry-ins (uninstall guards, tenant-filter hardening, module copy).

**Architecture:** GI is a memo document (no GL, no stock movement) with lines against PO lines. Coverage math lives in a pure service (`services/gate.py`) consumed by both the GI router and the billing gate in `purchase_orders.py`. Stock continues to arrive at bill posting. Spec: `docs/superpowers/specs/2026-07-05-purchase-store-phase2-design.md`.

**Tech Stack:** FastAPI + SQLModel + Alembic (backend), Next.js 16 App Router + Tailwind v4 (frontend), pytest.

## Global Constraints

- Run backend tests from `backend/` as: `PYTHONPATH=. uv run pytest tests/<file> -q`
- 2 pre-existing failures on main (`test_account_hierarchy.py::test_cannot_create_child_under_posted_account`, `test_update_migration.py::test_upgrade_over_create_all_db_is_safe`) — not yours, don't chase.
- All new tables tenant-scoped; every query filters `tenant_id`. Voucher `GI-YYYY-seq` via `next_number(session, tenant_id, "gate_inward", "GI", fmt="{prefix}-{YYYY}-{seq:04d}")`.
- Migrations: SQLite can't ALTER-ADD constraints — new tables get `bind.dialect.has_table(...)` guards; no FK-adding ALTERs (see `0029_purchase_demand_comparative.py`).
- Frontend: every new route goes into BOTH `NAV` and `SUB_NAV` + `SECTION_PREFIXES` in `frontend/src/lib/nav.ts` (regression 2026-07-05). Dates via `fmtDate` from `@/lib/utils`; amounts via `fmt()` from `useFmt()`; no voucher-type badges; `print:hidden` on toolbars.
- Money values: `from services.money import D, money`; `Money`/`money_col` in models.
- Commit after every task with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Models, migration, permission resource, module copy

**Files:**
- Modify: `backend/models.py` (after `PurchaseOrderLine`, ~line 909)
- Create: `backend/alembic/versions/0030_gate_inward.py`
- Modify: `backend/services/permissions.py:43` (after `purchase.comparative`)
- Modify: `backend/db.py` (`MODULE_REGISTRY["purchase_store"]["description"]`, ~line 472)
- Test: `backend/tests/test_gate_inward.py` (new)

**Interfaces:**
- Produces: `models.GateInward` (fields: `id, tenant_id, number, po_id, gate_date, time_in, vehicle_no, challan_no, remarks, status, cancel_reason, created_by_id, created_at`), `models.GateInwardLine` (`id, gate_inward_id, po_line_id, product_id, qty_received`), permission key `"purchase.gate"`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_gate_inward.py`:

```python
"""#137 Phase 2 — Gate Inward chain: GI → billing gate → reports."""
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


def test_gate_models_and_permission_registered(client: TestClient):
    from models import GateInward, GateInwardLine  # importable = tables exist
    from services.permissions import PERMISSION_RESOURCES
    assert "purchase.gate" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["purchase.gate"]["category"] == "Purchasing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q`
Expected: FAIL — `ImportError: cannot import name 'GateInward'`

- [ ] **Step 3: Add models**

In `backend/models.py`, directly after `class PurchaseOrderLine` (~line 909):

```python
class GateInward(SQLModel, table=True):
    """Gate entry at goods receipt (#137 Phase 2). Memo document — no GL,
    no stock movement; stock still arrives at bill posting. The control is
    append-only recording + per-line qty caps + the billing gate."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_gi_number_per_tenant"),
        CheckConstraint("status IN ('open','billed','cancelled')", name="ck_gi_status"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)                       # GI-YYYY-seq
    po_id: int = Field(foreign_key="purchaseorder.id", index=True)
    gate_date: str
    time_in: Optional[str] = None                         # "HH:MM"
    vehicle_no: Optional[str] = None
    challan_no: Optional[str] = None                      # challan / bilty
    remarks: Optional[str] = None
    status: str = Field(default="open")                   # open | billed | cancelled
    cancel_reason: Optional[str] = None
    created_by_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GateInwardLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("qty_received > 0", name="ck_gi_line_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    gate_inward_id: int = Field(foreign_key="gateinward.id", ondelete="CASCADE", index=True)
    po_line_id: int = Field(foreign_key="purchaseorderline.id")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    qty_received: Money = money_col()
```

- [ ] **Step 4: Register permission resource**

In `backend/services/permissions.py`, after the `purchase.comparative` line (line 43):

```python
    "purchase.gate":          {"label": "Gate Inward",             "category": "Purchasing"},
```

- [ ] **Step 5: Update module copy**

In `backend/db.py`, `MODULE_REGISTRY["purchase_store"]["description"]` becomes:

```python
        "description": "Procure-to-pay controls: purchase demands, vendor quotation comparison, approval-gated purchase orders, and gate-inward receipt control with 3-way match. Store issues arrive in an upcoming phase.",
```

- [ ] **Step 6: Create migration**

Create `backend/alembic/versions/0030_gate_inward.py`:

```python
"""gate inward (#137 Phase 2)

Revision ID: 0030_gate_inward
Revises: 0029_purchase_demand_comparative
Create Date: 2026-07-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0030_gate_inward'
down_revision: Union[str, Sequence[str], None] = '0029_purchase_demand_comparative'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'gateinward'):
        op.create_table('gateinward',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('po_id', sa.Integer(), nullable=False),
        sa.Column('gate_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('time_in', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('vehicle_no', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('challan_no', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('remarks', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('cancel_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('open','billed','cancelled')", name='ck_gi_status'),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['po_id'], ['purchaseorder.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'number', name='unique_gi_number_per_tenant')
        )
        op.create_index(op.f('ix_gateinward_number'), 'gateinward', ['number'], unique=False)
        op.create_index(op.f('ix_gateinward_po_id'), 'gateinward', ['po_id'], unique=False)
        op.create_index(op.f('ix_gateinward_tenant_id'), 'gateinward', ['tenant_id'], unique=False)

    if not bind.dialect.has_table(bind, 'gateinwardline'):
        op.create_table('gateinwardline',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gate_inward_id', sa.Integer(), nullable=False),
        sa.Column('po_line_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('qty_received', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.CheckConstraint('qty_received > 0', name='ck_gi_line_qty_positive'),
        sa.ForeignKeyConstraint(['gate_inward_id'], ['gateinward.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['po_line_id'], ['purchaseorderline.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_gateinwardline_gate_inward_id'), 'gateinwardline', ['gate_inward_id'], unique=False)


def downgrade() -> None:
    op.drop_table('gateinwardline')
    op.drop_table('gateinward')
```

Note: check the `Numeric(precision=18, scale=6)` against what 0029 used for
`PurchaseDemandLine.qty` (`grep -n "qty" backend/alembic/versions/0029_*.py`)
and copy that exact type.

- [ ] **Step 7: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q`
Expected: 1 passed

- [ ] **Step 8: Verify migration runs**

Run: `PYTHONPATH=. uv run alembic upgrade head`
Expected: no error; `0030_gate_inward` applied (dev DB already has tables via create_all — the has_table guard makes it a no-op there; the command proving it parses/executes is the point).

- [ ] **Step 9: Commit**

```bash
git add backend/models.py backend/alembic/versions/0030_gate_inward.py backend/services/permissions.py backend/db.py backend/tests/test_gate_inward.py
git commit -m "feat(gate): GateInward models + migration 0030 + purchase.gate resource (#137 P2)"
```

---

### Task 2: Coverage service

**Files:**
- Create: `backend/services/gate.py`
- Test: `backend/tests/test_gate_inward.py` (append)

**Interfaces:**
- Produces: `gi_coverage(session, tenant_id: int, po_id: int) -> dict[int, Decimal]` (po_line_id → Σ qty_received over non-cancelled GIs) and `po_fully_covered(session, tenant_id: int, po_id: int) -> bool`.
- Consumes: `models.GateInward`, `models.GateInwardLine`, `models.PurchaseOrderLine`, `services.money.D`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_gate_inward.py`)

```python
def test_gi_coverage_pure_math(client: TestClient):
    """Coverage helper sums non-cancelled GI lines per PO line."""
    from decimal import Decimal
    from sqlmodel import Session
    from models import (GateInward, GateInwardLine, PurchaseOrder,
                        PurchaseOrderLine, Tenant, User)
    from services.gate import gi_coverage, po_fully_covered
    import db as _db
    with Session(_db.engine) as s:
        t = Tenant(name="CovCo"); s.add(t); s.commit(); s.refresh(t)
        u = User(email="cov@t.test", hashed_password="x", full_name="U",
                 tenant_id=t.id, role="owner")
        s.add(u); s.commit(); s.refresh(u)
        po = PurchaseOrder(tenant_id=t.id, number="PO-X", order_date="2026-07-05",
                           status="approved")
        s.add(po); s.commit(); s.refresh(po)
        l1 = PurchaseOrderLine(po_id=po.id, description="A", qty=Decimal("10"), rate=Decimal("2"), amount=Decimal("20"))
        l2 = PurchaseOrderLine(po_id=po.id, description="B", qty=Decimal("5"), rate=Decimal("3"), amount=Decimal("15"))
        s.add(l1); s.add(l2); s.commit(); s.refresh(l1); s.refresh(l2)

        gi1 = GateInward(tenant_id=t.id, number="GI-1", po_id=po.id,
                         gate_date="2026-07-05", created_by_id=u.id)
        s.add(gi1); s.commit(); s.refresh(gi1)
        s.add(GateInwardLine(gate_inward_id=gi1.id, po_line_id=l1.id, qty_received=Decimal("4")))
        gi2 = GateInward(tenant_id=t.id, number="GI-2", po_id=po.id,
                         gate_date="2026-07-05", created_by_id=u.id, status="cancelled")
        s.add(gi2); s.commit(); s.refresh(gi2)
        s.add(GateInwardLine(gate_inward_id=gi2.id, po_line_id=l1.id, qty_received=Decimal("99")))
        s.commit()

        cov = gi_coverage(s, t.id, po.id)
        assert cov == {l1.id: Decimal("4")}          # cancelled GI excluded
        assert po_fully_covered(s, t.id, po.id) is False

        gi3 = GateInward(tenant_id=t.id, number="GI-3", po_id=po.id,
                         gate_date="2026-07-05", created_by_id=u.id)
        s.add(gi3); s.commit(); s.refresh(gi3)
        s.add(GateInwardLine(gate_inward_id=gi3.id, po_line_id=l1.id, qty_received=Decimal("6")))
        s.add(GateInwardLine(gate_inward_id=gi3.id, po_line_id=l2.id, qty_received=Decimal("5")))
        s.commit()
        assert po_fully_covered(s, t.id, po.id) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py::test_gi_coverage_pure_math -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.gate'`

- [ ] **Step 3: Implement `backend/services/gate.py`**

```python
"""Gate Inward coverage math (#137 Phase 2) — pure logic, no GL, no writes."""
from decimal import Decimal

from sqlmodel import Session, select

from models import GateInward, GateInwardLine, PurchaseOrderLine
from services.money import D


def gi_coverage(session: Session, tenant_id: int, po_id: int) -> dict[int, Decimal]:
    """po_line_id → Σ qty_received across the PO's non-cancelled Gate Inwards."""
    cov: dict[int, Decimal] = {}
    rows = session.exec(
        select(GateInwardLine)
        .join(GateInward, GateInward.id == GateInwardLine.gate_inward_id)
        .where(
            GateInward.po_id == po_id,
            GateInward.tenant_id == tenant_id,
            GateInward.status != "cancelled",
        )
    ).all()
    for line in rows:
        cov[line.po_line_id] = cov.get(line.po_line_id, D(0)) + D(line.qty_received)
    return cov


def po_fully_covered(session: Session, tenant_id: int, po_id: int) -> bool:
    """True when every PO line's qty is fully covered by non-cancelled GI lines."""
    po_lines = session.exec(
        select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po_id)
    ).all()
    if not po_lines:
        return False
    cov = gi_coverage(session, tenant_id, po_id)
    return all(cov.get(l.id, D(0)) >= D(l.qty) for l in po_lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/gate.py backend/tests/test_gate_inward.py
git commit -m "feat(gate): coverage service — gi_coverage + po_fully_covered (#137 P2)"
```

---

### Task 3: Gate Inward router (create / list / get / cancel)

**Files:**
- Create: `backend/routers/gate_inward.py`
- Modify: `backend/main.py` (mount — copy the exact `include_router` pattern used for `purchase_demands`)
- Test: `backend/tests/test_gate_inward.py` (append)

**Interfaces:**
- Produces: `GET/POST /api/gate-inwards`, `GET /api/gate-inwards/{id}`, `PATCH /api/gate-inwards/{id}/cancel`. Create body: `{po_id, gate_date, time_in?, vehicle_no?, challan_no?, remarks?, lines: [{po_line_id, qty_received}]}`. Serialized GI dict includes `lines` and `po_number`.
- Consumes: `services.gate.gi_coverage`, `po_fully_covered`; `perm_dep("purchase.gate")`, `apply_own_filter`, `next_number`, `log_audit` from `routers.common`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_gate_inward.py`)

```python
def _approved_po(client, auth, lines=None):
    """Bare PO (chain setting off) + approve it. Returns the PO dict with lines."""
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-05", "vendor_name": "Steel Traders",
        "lines": lines or [
            {"description": "Steel rods 12mm", "qty": 100, "rate": 5},
            {"description": "Binding wire", "qty": 20, "rate": 2},
        ],
    })
    assert r.status_code == 201, r.text
    po = r.json()
    client.patch(f"/api/purchase-orders/{po['id']}/approve", headers=auth)
    return client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()


def _po_line_ids(po):
    return [l["id"] for l in po["lines"]]


def test_gi_lifecycle_partial_then_full(client: TestClient):
    auth = _signup(client, "gi1@t.com")
    po = _approved_po(client, auth)
    l1, l2 = _po_line_ids(po)

    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05", "time_in": "09:30",
        "vehicle_no": "LEB-1234", "challan_no": "CH-778",
        "lines": [{"po_line_id": l1, "qty_received": 100}],
    })
    assert r.status_code == 201, r.text
    gi = r.json()
    assert gi["number"].startswith("GI-")
    assert gi["status"] == "open"

    # partial coverage → PO still 'approved'
    po_now = client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()
    assert po_now["status"] == "approved"

    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l2, "qty_received": 20}],
    })
    assert r.status_code == 201, r.text

    # full coverage → PO flips to 'received'
    po_now = client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()
    assert po_now["status"] == "received"


def test_gi_over_receipt_rejected(client: TestClient):
    auth = _signup(client, "gi2@t.com")
    po = _approved_po(client, auth)
    l1, _ = _po_line_ids(po)
    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 101}],
    })
    assert r.status_code == 400
    assert "exceed" in r.json()["detail"].lower()


def test_gi_rejects_draft_and_foreign_po(client: TestClient):
    auth = _signup(client, "gi3@t.com")
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-05", "vendor_name": "V",
        "lines": [{"description": "W", "qty": 1, "rate": 1}],
    })
    draft_po = r.json()
    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": draft_po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": draft_po["lines"][0]["id"], "qty_received": 1}],
    })
    assert r.status_code == 400  # draft PO not receivable

    # foreign tenant's PO → 404
    auth_b = _signup(client, "gi3b@t.com")
    po_a = _approved_po(client, auth)
    r = client.post("/api/gate-inwards", headers=auth_b, json={
        "po_id": po_a["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": _po_line_ids(po_a)[0], "qty_received": 1}],
    })
    assert r.status_code == 404


def test_gi_cancel_requires_reason_and_restores_headroom(client: TestClient):
    auth = _signup(client, "gi4@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    l1 = _po_line_ids(po)[0]
    gi = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 10}],
    }).json()
    assert client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()["status"] == "received"

    r = client.patch(f"/api/gate-inwards/{gi['id']}/cancel", headers=auth, json={})
    assert r.status_code == 422 or r.status_code == 400  # reason required

    r = client.patch(f"/api/gate-inwards/{gi['id']}/cancel", headers=auth,
                     json={"reason": "wrong vehicle logged"})
    assert r.status_code == 200
    # coverage dropped → PO back to 'approved'; headroom restored
    assert client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()["status"] == "approved"
    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 10}],
    })
    assert r.status_code == 201, r.text


def test_gi_create_requires_write_role(client: TestClient):
    auth = _signup(client, "gi5@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 1, "rate": 1}])
    client.post("/api/users", headers=auth, json={
        "email": "gateviewer@t.com", "password": "password123",
        "full_name": "Viewer", "role": "viewer",
    })
    r = client.post("/api/auth/login",
                    data={"username": "gateviewer@t.com", "password": "password123"})
    viewer = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/api/gate-inwards", headers=viewer, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": _po_line_ids(po)[0], "qty_received": 1}],
    })
    assert r.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q`
Expected: 5 new FAIL with 404 (routes not mounted), 2 previous pass.

- [ ] **Step 3: Implement `backend/routers/gate_inward.py`**

```python
"""Gate Inward — receipt control at the gate (#137 Phase 2). Memo, no GL."""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import GateInward, GateInwardLine, PurchaseOrder, PurchaseOrderLine
from routers.common import SessionDep, WriteUserDep, log_audit, next_number
from services.gate import gi_coverage
from services.money import D
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(
    prefix="/api/gate-inwards", tags=["gate-inwards"],
    dependencies=[perm_dep("purchase.gate")],
)


class GILineIn(BaseModel):
    po_line_id: int
    qty_received: Decimal


class GIIn(BaseModel):
    po_id: int
    gate_date: str
    time_in: Optional[str] = None
    vehicle_no: Optional[str] = None
    challan_no: Optional[str] = None
    remarks: Optional[str] = None
    lines: List[GILineIn] = []


class GICancel(BaseModel):
    reason: str


def _get_gi(session, user, gi_id: int) -> GateInward:
    gi = session.exec(
        select(GateInward).where(
            GateInward.id == gi_id, GateInward.tenant_id == user.tenant_id
        )
    ).first()
    if not gi:
        raise HTTPException(404, "Gate inward not found")
    return gi


def _serialize(session, gi: GateInward) -> dict:
    lines = session.exec(
        select(GateInwardLine).where(GateInwardLine.gate_inward_id == gi.id)
    ).all()
    po = session.get(PurchaseOrder, gi.po_id)
    out = gi.model_dump()
    out["lines"] = [l.model_dump() for l in lines]
    out["po_number"] = po.number if po else None
    out["vendor_name"] = po.vendor_name if po else None
    return out


def _recompute_po_status(session, tenant_id: int, po: PurchaseOrder) -> None:
    """Coverage is the single source of truth for approved ↔ received."""
    from services.gate import po_fully_covered
    full = po_fully_covered(session, tenant_id, po.id)
    if full and po.status == "approved":
        po.status = "received"
        session.add(po)
    elif not full and po.status == "received":
        po.status = "approved"
        session.add(po)


@router.get("")
def list_gis(
    session: SessionDep, user: WriteUserDep,
    po_id: Optional[int] = None, status: Optional[str] = None,
):
    q = select(GateInward).where(GateInward.tenant_id == user.tenant_id)
    if po_id:
        q = q.where(GateInward.po_id == po_id)
    if status:
        q = q.where(GateInward.status == status)
    q = apply_own_filter(q, GateInward, user, session)
    rows = session.exec(q.order_by(GateInward.id.desc())).all()
    return [_serialize(session, gi) for gi in rows]


@router.get("/{gi_id}")
def get_gi(session: SessionDep, user: WriteUserDep, gi_id: int):
    return _serialize(session, _get_gi(session, user, gi_id))


@router.post("", status_code=201)
def create_gi(session: SessionDep, user: WriteUserDep, body: GIIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == body.po_id, PurchaseOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po.status not in ("approved", "received"):
        raise HTTPException(
            400, f"Gate inward requires an approved PO (status is '{po.status}')"
        )

    po_lines = {
        l.id: l for l in session.exec(
            select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
        ).all()
    }
    cov = gi_coverage(session, user.tenant_id, po.id)
    for l in body.lines:
        po_line = po_lines.get(l.po_line_id)
        if not po_line:
            raise HTTPException(400, f"po_line_id {l.po_line_id} is not on this PO")
        if D(l.qty_received) <= 0:
            raise HTTPException(400, "qty_received must be positive")
        remaining = D(po_line.qty) - cov.get(l.po_line_id, D(0))
        if D(l.qty_received) > remaining:
            raise HTTPException(
                400,
                f"Line '{po_line.description}': received qty would exceed the PO "
                f"(ordered {po_line.qty}, remaining {remaining})",
            )

    number = next_number(
        session, user.tenant_id, "gate_inward", "GI", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    gi = GateInward(
        tenant_id=user.tenant_id, number=number, po_id=po.id,
        gate_date=body.gate_date, time_in=body.time_in,
        vehicle_no=body.vehicle_no, challan_no=body.challan_no,
        remarks=body.remarks, status="open", created_by_id=user.id,
    )
    session.add(gi)
    session.flush()
    for l in body.lines:
        session.add(GateInwardLine(
            gate_inward_id=gi.id, po_line_id=l.po_line_id,
            product_id=po_lines[l.po_line_id].product_id,
            qty_received=D(l.qty_received),
        ))
    session.flush()
    _recompute_po_status(session, user.tenant_id, po)
    log_audit(session, user, "CREATE", "gate_inward", gi.id, {"number": number})
    session.commit()
    return _serialize(session, gi)


@router.patch("/{gi_id}/cancel")
def cancel_gi(session: SessionDep, user: WriteUserDep, gi_id: int, body: GICancel):
    gi = _get_gi(session, user, gi_id)
    if not body.reason.strip():
        raise HTTPException(400, "A cancellation reason is required")
    if gi.status == "cancelled":
        raise HTTPException(400, "Gate inward is already cancelled")
    po = session.get(PurchaseOrder, gi.po_id)
    if gi.status == "billed" or (po and po.status == "billed"):
        raise HTTPException(400, "Cannot cancel a gate inward on a billed PO")
    gi.status = "cancelled"
    gi.cancel_reason = body.reason.strip()
    session.add(gi)
    session.flush()
    if po:
        _recompute_po_status(session, user.tenant_id, po)
    log_audit(session, user, "UPDATE", "gate_inward", gi.id,
              {"action": "cancelled", "reason": gi.cancel_reason})
    session.commit()
    return {"success": True, "status": "cancelled"}
```

- [ ] **Step 4: Mount the router**

In `backend/main.py`, find the line importing/mounting `purchase_demands` and add `gate_inward` alongside it, same style (e.g. `app.include_router(gate_inward.router)`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add backend/routers/gate_inward.py backend/main.py backend/tests/test_gate_inward.py
git commit -m "feat(gate): gate-inward router — create/list/get/cancel with qty caps (#137 P2)"
```

---

### Task 4: Billing gate in purchase_orders.py

**Files:**
- Modify: `backend/routers/purchase_orders.py` (`convert_to_bill`, `get_po`, add `_gate_required` next to `_chain_required` at line 83)
- Test: `backend/tests/test_gate_inward.py` (append)

**Interfaces:**
- Consumes: `services.gate.po_fully_covered`, `gi_coverage`.
- Produces: `GET /api/purchase-orders/{id}` response gains `"gi_coverage": {po_line_id: qty}` and `"gate_required": bool`; convert-to-bill 400 message contains "gate inward".

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_billing_blocked_without_full_gi_coverage(client: TestClient):
    auth = _signup(client, "gate1@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    l1 = _po_line_ids(po)[0]

    # no GI at all → blocked (manufacturing tenant, setting defaults on)
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 400
    assert "gate inward" in r.json()["detail"].lower()

    # partial GI → still blocked
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 4}],
    })
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 400

    # full GI → allowed; GIs flip to billed
    gi2 = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 6}],
    }).json()
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 201, r.text
    gi_now = client.get(f"/api/gate-inwards/{gi2['id']}", headers=auth).json()
    assert gi_now["status"] == "billed"

    # billed PO → GI cancel refused
    r = client.patch(f"/api/gate-inwards/{gi2['id']}/cancel", headers=auth,
                     json={"reason": "attempted tamper"})
    assert r.status_code == 400


def test_billing_allowed_when_gate_setting_off(client: TestClient):
    auth = _signup(client, "gate2@t.com")
    client.patch("/api/settings", headers=auth, json={"require_gate_inward": "false"})
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 201, r.text


def test_billing_unaffected_without_module(client: TestClient):
    auth = _signup(client, "gate3@t.com", model="simple")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 201, r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q`
Expected: `test_billing_blocked_without_full_gi_coverage` FAILS (conversion succeeds with 201 — no gate yet); the two "allowed" tests may already pass.

- [ ] **Step 3: Implement the gate**

In `backend/routers/purchase_orders.py`:

(a) Below `_chain_required` (after line 97), add:

```python
def _gate_required(session, tenant_id: int) -> bool:
    """True when purchase_store is installed AND require_gate_inward isn't 'false'."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return False
    from routers.modules import _get_enabled
    if "purchase_store" not in _get_enabled(tenant):
        return False
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id, Settings.key == "require_gate_inward"
        )
    ).first()
    return not (row and str(row.value).strip().lower() == "false")
```

(b) In `convert_to_bill`, after the `po.status == "cancelled"` check (line ~214), add:

```python
    if _gate_required(session, user.tenant_id):
        from services.gate import po_fully_covered
        if not po_fully_covered(session, user.tenant_id, po.id):
            raise HTTPException(
                400,
                "This company requires goods to pass the gate before billing. "
                "Record Gate Inward entries covering every PO line "
                "(or disable 'Require gate inward' in Settings).",
            )
```

(c) At the end of `convert_to_bill`, just before `session.commit()` (after `po.status = "billed"`), add:

```python
    from models import GateInward
    for gi in session.exec(
        select(GateInward).where(
            GateInward.po_id == po.id,
            GateInward.tenant_id == user.tenant_id,
            GateInward.status == "open",
        )
    ).all():
        gi.status = "billed"
        session.add(gi)
```

(d) In `get_po` (line 68), enrich the response. Find where the PO dict is
returned (it serializes PO + lines) and add before returning:

```python
    from services.gate import gi_coverage
    out["gi_coverage"] = {
        str(k): str(v) for k, v in gi_coverage(session, user.tenant_id, po.id).items()
    }
    out["gate_required"] = _gate_required(session, user.tenant_id)
```

(Adapt `out` to the actual local variable name used in `get_po`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py tests/test_purchase_flow.py -q`
Expected: all pass (Phase-1 flow tests must stay green — they bill POs only in tenants without the module or via the demand chain; if any Phase-1 test now fails on the gate, it bills a manufacturing-tenant PO and must set `require_gate_inward=false` in its arrange step — apply that fix in the test with a comment).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/purchase_orders.py backend/tests/test_gate_inward.py backend/tests/test_purchase_flow.py
git commit -m "feat(gate): billing gate — convert-to-bill requires full GI coverage (#137 P2)"
```

---

### Task 5: Settings toggle plumbing

**Files:**
- Modify: `backend/routers/settings.py:57` (add field after `require_purchase_chain`)
- Modify: `frontend/src/context/SettingsContext.tsx:38,87`
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx` (~line 700, beside the existing chain toggle)
- Test: covered by Task 4's `test_billing_allowed_when_gate_setting_off` (backend); frontend by lint/tsc.

**Interfaces:**
- Produces: setting key `require_gate_inward` ("true"/"false" strings, default "true").

- [ ] **Step 1: Backend field**

In `backend/routers/settings.py`, after `require_purchase_chain: Optional[str] = None` (line 57):

```python
    require_gate_inward: Optional[str] = None
```

- [ ] **Step 2: Frontend context**

In `frontend/src/context/SettingsContext.tsx`: add `require_gate_inward: string` to the `AppSettings` interface (after line 38) and `require_gate_inward: "true",` to `defaults` (after line 87).

- [ ] **Step 3: Settings page toggle**

In `frontend/src/app/(dashboard)/settings/page.tsx`, duplicate the existing `require_purchase_chain` toggle block (ends ~line 717) directly below itself, changing: key to `require_gate_inward`, label to `Require gate inward before billing`, help text to `Purchase orders can only be billed once Gate Inward entries cover every line.` Keep the same `installedModules.has("purchase_store")` visibility condition the chain toggle uses.

- [ ] **Step 4: Verify**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q` (backend still green)
Run in `frontend/`: `npx tsc --noEmit && npx eslint src/context/SettingsContext.tsx "src/app/(dashboard)/settings/page.tsx"`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/settings.py frontend/src/context/SettingsContext.tsx "frontend/src/app/(dashboard)/settings/page.tsx"
git commit -m "feat(gate): require_gate_inward setting toggle (#137 P2)"
```

---

### Task 6: Reports — gate register + 3-way match

**Files:**
- Create: `backend/routers/purchase_reports.py`
- Modify: `backend/main.py` (mount)
- Test: `backend/tests/test_gate_inward.py` (append)

**Interfaces:**
- Produces:
  - `GET /api/purchase-reports/gate-register?start=&end=&q=` → `[{gi fields, po_number, vendor_name, item_count, total_qty, recorded_by}]`
  - `GET /api/purchase-reports/three-way-match?start=&end=` → `[{po_number, vendor_name, line_description, po_qty, po_rate, po_amount, gi_qty, bill_qty, bill_amount, qty_variance, amount_variance, flag}]`
- Consumes: `services.gate.gi_coverage`. Bill lines are matched to PO lines **by position** (conversion copies lines in order — document this limit in a code comment).

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_gate_register_and_search(client: TestClient):
    auth = _signup(client, "rep1@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    l1 = _po_line_ids(po)[0]
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05", "vehicle_no": "LEB-9999",
        "challan_no": "CH-123", "lines": [{"po_line_id": l1, "qty_received": 10}],
    })
    rows = client.get("/api/purchase-reports/gate-register", headers=auth).json()
    assert len(rows) == 1
    assert rows[0]["vehicle_no"] == "LEB-9999"
    assert float(rows[0]["total_qty"]) == 10.0

    rows = client.get("/api/purchase-reports/gate-register?q=CH-123", headers=auth).json()
    assert len(rows) == 1
    rows = client.get("/api/purchase-reports/gate-register?q=NOPE", headers=auth).json()
    assert rows == []


def test_three_way_match_variances(client: TestClient):
    auth = _signup(client, "rep2@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 2}])
    l1 = _po_line_ids(po)[0]
    # receive only 8 of 10, then bill with the setting off (variance scenario)
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 8}],
    })
    client.patch("/api/settings", headers=auth, json={"require_gate_inward": "false"})
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 201, r.text

    rows = client.get("/api/purchase-reports/three-way-match", headers=auth).json()
    assert len(rows) == 1
    row = rows[0]
    assert float(row["po_qty"]) == 10.0
    assert float(row["gi_qty"]) == 8.0
    assert float(row["bill_qty"]) == 10.0
    assert float(row["qty_variance"]) == -2.0     # gi_qty − po_qty
    assert row["flag"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q`
Expected: the 2 new tests FAIL with 404.

- [ ] **Step 3: Implement `backend/routers/purchase_reports.py`**

```python
"""Purchase-chain audit reports (#137 Phase 2): gate register + 3-way match."""
from typing import Optional

from fastapi import APIRouter
from sqlmodel import select

from models import (Bill, BillLine, GateInward, GateInwardLine, PurchaseOrder,
                    PurchaseOrderLine, User)
from routers.common import SessionDep, WriteUserDep
from services.gate import gi_coverage
from services.money import D
from services.permissions import perm_dep

router = APIRouter(prefix="/api/purchase-reports", tags=["purchase-reports"])


@router.get("/gate-register", dependencies=[perm_dep("purchase.gate")])
def gate_register(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None, q: Optional[str] = None,
):
    query = select(GateInward).where(GateInward.tenant_id == user.tenant_id)
    if start:
        query = query.where(GateInward.gate_date >= start)
    if end:
        query = query.where(GateInward.gate_date <= end)
    gis = session.exec(query.order_by(GateInward.id.desc())).all()

    users = {u.id: u.full_name for u in session.exec(
        select(User).where(User.tenant_id == user.tenant_id)).all()}
    out = []
    for gi in gis:
        if q:
            needle = q.lower()
            hay = f"{gi.vehicle_no or ''} {gi.challan_no or ''}".lower()
            if needle not in hay:
                continue
        lines = session.exec(
            select(GateInwardLine).where(GateInwardLine.gate_inward_id == gi.id)
        ).all()
        po = session.get(PurchaseOrder, gi.po_id)
        row = gi.model_dump()
        row["po_number"] = po.number if po else None
        row["vendor_name"] = po.vendor_name if po else None
        row["item_count"] = len(lines)
        row["total_qty"] = sum(D(l.qty_received) for l in lines)
        row["recorded_by"] = users.get(gi.created_by_id, "—")
        out.append(row)
    return out


@router.get("/three-way-match", dependencies=[perm_dep("purchase.comparative")])
def three_way_match(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    query = select(PurchaseOrder).where(PurchaseOrder.tenant_id == user.tenant_id)
    if start:
        query = query.where(PurchaseOrder.order_date >= start)
    if end:
        query = query.where(PurchaseOrder.order_date <= end)
    pos = session.exec(query.order_by(PurchaseOrder.id)).all()

    out = []
    for po in pos:
        cov = gi_coverage(session, user.tenant_id, po.id)
        has_bill = bool(po.bill_id)
        if not cov and not has_bill:
            continue  # nothing received or billed — nothing to match
        po_lines = session.exec(
            select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
            .order_by(PurchaseOrderLine.id)
        ).all()
        # Bill lines are copies of PO lines made in order at conversion —
        # positional zip is the only available linkage (BillLine has no
        # po_line_id). Manually edited bills may mis-align; acceptable for
        # a variance-flagging report.
        bill_lines = []
        if has_bill:
            bill_lines = session.exec(
                select(BillLine).where(BillLine.bill_id == po.bill_id)
                .order_by(BillLine.id)
            ).all()
        for i, pl in enumerate(po_lines):
            bl = bill_lines[i] if i < len(bill_lines) else None
            gi_qty = cov.get(pl.id, D(0))
            bill_qty = D(bl.qty) if bl else D(0)
            bill_amount = D(bl.amount) if bl else D(0)
            qty_variance = gi_qty - D(pl.qty)
            amount_variance = bill_amount - D(pl.amount)
            out.append({
                "po_number": po.number,
                "vendor_name": po.vendor_name,
                "line_description": pl.description,
                "po_qty": pl.qty, "po_rate": pl.rate, "po_amount": pl.amount,
                "gi_qty": gi_qty,
                "bill_qty": bill_qty, "bill_amount": bill_amount,
                "qty_variance": qty_variance,
                "amount_variance": amount_variance,
                "flag": bool(qty_variance != 0 or amount_variance != 0),
            })
    return out
```

- [ ] **Step 4: Mount** — add `purchase_reports` next to `gate_inward` in `backend/main.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/purchase_reports.py backend/main.py backend/tests/test_gate_inward.py
git commit -m "feat(gate): gate-register + 3-way-match report endpoints (#137 P2)"
```

---

### Task 7: Carry-in — uninstall guards

**Files:**
- Modify: `backend/routers/modules.py` (guard registry + uninstall check, insert after the `_dependents_of` blocking check ~line 205)
- Test: `backend/tests/test_gate_inward.py` (append)

**Interfaces:**
- Produces: `MODULE_UNINSTALL_GUARDS: dict[str, Callable[[Session, int], dict[str, int]]]` in `routers/modules.py`; uninstall returns 400 listing blocking counts.

- [ ] **Step 1: Write the failing test** (append)

```python
def test_uninstall_blocked_while_documents_exist(client: TestClient):
    auth = _signup(client, "uni1@t.com")
    r = client.post("/api/purchase-demands", headers=auth, json={
        "demand_date": "2026-07-05",
        "lines": [{"description": "Steel", "qty": 1}],
    })
    assert r.status_code == 201
    r = client.post("/api/modules/purchase_store/uninstall", headers=auth)
    assert r.status_code == 400
    assert "purchase demand" in r.json()["detail"].lower()

    # cancelled documents still block (audit trail preserved) — purge is the
    # only way out; verify a fresh tenant with no documents can uninstall
    auth2 = _signup(client, "uni2@t.com", model="trader")
    client.post("/api/modules/purchase_store/install", headers=auth2)
    r = client.post("/api/modules/purchase_store/uninstall", headers=auth2)
    assert r.status_code == 200
```

(Route shape verified: `@router.post("/api/modules/{module_id}/uninstall")` at
`backend/routers/modules.py:174`; install is the sibling route above it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py::test_uninstall_blocked_while_documents_exist -q`
Expected: FAIL — uninstall currently returns 200.

- [ ] **Step 3: Implement guards in `backend/routers/modules.py`**

Near the top (after `_dependents_of`):

```python
def _purchase_store_docs(session, tenant_id: int) -> dict[str, int]:
    """Blocking document counts for purchase_store uninstall."""
    from sqlalchemy import func
    from models import (ComparativeStatement, GateInward, PurchaseDemand,
                        VendorQuotation)
    counts = {}
    for label, model in (
        ("purchase demands", PurchaseDemand),
        ("vendor quotations", VendorQuotation),
        ("comparative statements", ComparativeStatement),
        ("gate inwards", GateInward),
    ):
        n = session.exec(
            select(func.count(model.id)).where(model.tenant_id == tenant_id)
        ).one()
        if n:
            counts[label] = n
    return counts


# module_id → callable(session, tenant_id) → {doc label: count}; non-empty blocks uninstall
MODULE_UNINSTALL_GUARDS = {
    "purchase_store": _purchase_store_docs,
}
```

In `uninstall_module`, after the `_dependents_of` blocking check (after the
`raise` at ~line 205):

```python
    guard = MODULE_UNINSTALL_GUARDS.get(module_id)
    if guard:
        blocking_docs = guard(session, current_user.tenant_id)
        if blocking_docs:
            detail = ", ".join(f"{n} {label}" for label, n in blocking_docs.items())
            raise HTTPException(
                400,
                f"Cannot uninstall {module_id!r}: this company has {detail}. "
                "The document trail must be kept — uninstall is only possible "
                "on a company with no purchase-chain documents."
            )
```

(`from sqlmodel import select` is already imported in modules.py; verify `func` import placement.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py tests/test_modules_api.py -q 2>/dev/null || PYTHONPATH=. uv run pytest tests/test_gate_inward.py -q`
Then the full purchase set: `PYTHONPATH=. uv run pytest tests/ -q -k "purchase or module or gate"`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/modules.py backend/tests/test_gate_inward.py
git commit -m "feat(modules): uninstall guards — purchase_store blocked while documents exist (#137 P2 carry-in)"
```

---

### Task 8: Carry-in — tenant-filter hardening

**Files:**
- Modify: `backend/routers/quotations.py` (`_validate_and_write_lines`, line 72)
- Modify: `backend/routers/comparatives.py` (`_quote_totals` line 46 + its 2 call sites at lines 70 and 192; approve completeness queries lines 207–218)
- Test: `backend/tests/test_gate_inward.py` (append)

**Interfaces:**
- `_quote_totals` signature changes to `_quote_totals(session, tenant_id: int, demand_id: int)` — update both call sites.

- [ ] **Step 1: Write the failing-or-green test** (append — this is defense-in-depth; the test pins the behavior)

```python
def test_quotation_lines_cannot_reference_foreign_demand_lines(client: TestClient):
    """Tenant B's demand-line IDs must never validate for tenant A's quotation."""
    auth_a = _signup(client, "hard1a@t.com")
    auth_b = _signup(client, "hard1b@t.com")
    # tenant B demand
    d_b = client.post("/api/purchase-demands", headers=auth_b, json={
        "demand_date": "2026-07-05", "lines": [{"description": "X", "qty": 1}],
    }).json()
    # tenant A demand + vendor
    d_a = client.post("/api/purchase-demands", headers=auth_a, json={
        "demand_date": "2026-07-05", "lines": [{"description": "Y", "qty": 1}],
    }).json()
    v = client.post("/api/vendors", headers=auth_a, json={"name": "V"}).json()
    # tenant A quotes tenant A's demand but smuggles tenant B's line id
    r = client.post("/api/quotations", headers=auth_a, json={
        "demand_id": d_a["id"], "vendor_id": v["id"], "quote_date": "2026-07-05",
        "lines": [{"demand_line_id": d_b["lines"][0]["id"], "rate": 5, "qty": 1}],
    })
    assert r.status_code == 400
```

Note: check the exact `QuoteIn` body fields first (`sed -n '20,50p' backend/routers/quotations.py`) and adjust field names (`quote_date` etc.) to match.

- [ ] **Step 2: Run it** — it should already PASS (transitively safe today). If it fails, that's a live cross-tenant bug: fix becomes urgent, same edits below.

- [ ] **Step 3: Harden `quotations.py`**

In `_validate_and_write_lines`, replace the `demand_line_ids` query:

```python
    from models import PurchaseDemand
    demand_line_ids = {
        l.id for l in session.exec(
            select(PurchaseDemandLine)
            .join(PurchaseDemand, PurchaseDemand.id == PurchaseDemandLine.demand_id)
            .where(
                PurchaseDemandLine.demand_id == body.demand_id,
                PurchaseDemand.tenant_id == user.tenant_id,
            )
        ).all()
    }
```

- [ ] **Step 4: Harden `comparatives.py`**

(a) `_quote_totals` gains a tenant filter:

```python
def _quote_totals(session, tenant_id: int, demand_id: int) -> dict[int, object]:
    """quotation_id → Decimal total, for every quotation on the demand."""
    totals: dict[int, object] = {}
    for q in session.exec(
        select(VendorQuotation).where(
            VendorQuotation.demand_id == demand_id,
            VendorQuotation.tenant_id == tenant_id,
        )
    ).all():
        lines = session.exec(
            select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
        ).all()
        totals[q.id] = sum(D(l.amount) for l in lines)
    return totals
```

Update both call sites: `_quote_totals(session, user.tenant_id, cs.demand_id)`.

(b) In `approve_cs`, join tenant into the two completeness queries:

```python
    demand_line_ids = {
        dl.id for dl in session.exec(
            select(PurchaseDemandLine)
            .join(PurchaseDemand, PurchaseDemand.id == PurchaseDemandLine.demand_id)
            .where(
                PurchaseDemandLine.demand_id == cs.demand_id,
                PurchaseDemand.tenant_id == user.tenant_id,
            )
        ).all()
    }
    quoted_line_ids = {
        ql.demand_line_id for ql in session.exec(
            select(VendorQuotationLine)
            .join(VendorQuotation, VendorQuotation.id == VendorQuotationLine.quotation_id)
            .where(
                VendorQuotationLine.quotation_id == cs.selected_quotation_id,
                VendorQuotation.tenant_id == user.tenant_id,
            )
        ).all()
    }
```

- [ ] **Step 5: Run the full purchase suite**

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py tests/test_gate_inward.py -q`
Expected: all pass — behavior unchanged, filters now local.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/quotations.py backend/routers/comparatives.py backend/tests/test_gate_inward.py
git commit -m "fix(purchase): defense-in-depth tenant filters on quotation/comparative subqueries (#137 P2 carry-in)"
```

---

### Task 9: Frontend — nav wiring + GI pages

**Files:**
- Modify: `frontend/src/lib/nav.ts` (NAV Purchases block line ~58; SUB_NAV.purchases line ~266; SECTION_PREFIXES already has `/purchases`)
- Create: `frontend/src/app/(dashboard)/purchases/gate-inward/page.tsx`
- Create: `frontend/src/app/(dashboard)/purchases/gate-inward/new/page.tsx`
- Create: `frontend/src/app/(dashboard)/purchases/gate-inward/[id]/page.tsx`

**Interfaces:**
- Consumes: `GET/POST /api/gate-inwards`, `GET /api/gate-inwards/{id}`, `PATCH /{id}/cancel`, `GET /api/purchase-orders?status=approved`, `GET /api/purchase-orders/{id}` (with `gi_coverage`).
- Pattern sources (copy structure/styling from these): list → `purchases/demands/page.tsx`, form → `purchases/demands/[id]/quotations/new/page.tsx`, detail/print → `purchases/demands/[id]/page.tsx`.

- [ ] **Step 1: Nav entries**

In `NAV` (after the Comparatives line, 59):

```ts
  { label: "Gate Inward",      href: "/purchases/gate-inward", icon: DoorOpen,     section: "Purchases", forModule: "purchase_store" },
```

In `SUB_NAV.purchases` (after Comparatives):

```ts
    { label: "Gate Inward",     href: "/purchases/gate-inward",         icon: DoorOpen,       section: "purchases", forModule: "purchase_store" },
```

Import `DoorOpen` from `lucide-react` in the existing import block.

- [ ] **Step 2: List page** — `purchases/gate-inward/page.tsx`

Copy the structure of `purchases/demands/page.tsx` exactly (client component, `apiFetch("/api/gate-inwards")`, table inside the standard card wrapper, `print:hidden` toolbar with a "New Gate Inward" `Link` to `/purchases/gate-inward/new`). Columns: GI# (link to detail), Date (`fmtDate`), PO#, Vendor, Vehicle, Challan, Status (plain text — no badge pills in print, use existing status-badge component the demands list uses on screen). Empty state: "No gate entries yet. Record one from an approved purchase order."

- [ ] **Step 3: New form** — `purchases/gate-inward/new/page.tsx`

Structure from the quotation-entry form. Behavior:
- Read `?po=<id>` via `useSearchParams`; if absent show a PO `<select>` populated from `apiFetch("/api/purchase-orders?status=approved")` + `?status=received` merged.
- On PO selection, `apiFetch(/api/purchase-orders/{id})` → render one row per PO line: description, ordered qty, already-received qty (`gi_coverage[line.id] ?? 0`), and an input `qty_received` defaulted to `ordered − received` (0-remaining rows default 0 and stay editable-off).
- Header inputs: gate_date (default today), time_in, vehicle_no, challan_no, remarks.
- Submit → `POST /api/gate-inwards` with only lines where `qty_received > 0`; on 201 `router.push` to the detail page; surface API `detail` string on 400.

- [ ] **Step 4: Detail page** — `purchases/gate-inward/[id]/page.tsx`

Structure from the demand detail page: `<PrintHeader title={gi.number} subtitle={fmtDate(gi.gate_date)} />` (portrait — no orientation prop), header grid (PO#, vendor, vehicle, challan, time-in, recorded status), lines table (item description via line product/PO context, qty received), remarks. Actions (in `print:hidden` toolbar): Print button (`window.print()`), Cancel button → prompt for reason (small inline form, not `window.prompt`) → `PATCH /cancel`; hide Cancel when status ≠ `open`.

- [ ] **Step 5: Verify**

Run in `frontend/`: `npx tsc --noEmit && npx eslint src/lib/nav.ts "src/app/(dashboard)/purchases/gate-inward"`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/nav.ts "frontend/src/app/(dashboard)/purchases/gate-inward"
git commit -m "feat(gate-ui): gate-inward list/new/detail pages + nav (both registries) (#137 P2)"
```

---

### Task 10: Frontend — report pages + PO detail coverage

**Files:**
- Create: `frontend/src/app/(dashboard)/purchases/gate-register/page.tsx`
- Create: `frontend/src/app/(dashboard)/purchases/three-way-match/page.tsx`
- Modify: `frontend/src/lib/nav.ts` (two more entries in NAV + SUB_NAV.purchases)
- Modify: PO detail page (find with `ls "frontend/src/app/(dashboard)/manufacturing/purchase-orders"`) — coverage indicator + Record Gate Inward button + convert-to-bill guard

**Interfaces:**
- Consumes: `GET /api/purchase-reports/gate-register`, `GET /api/purchase-reports/three-way-match`, `GET /api/purchase-orders/{id}` (`gi_coverage`, `gate_required`).

- [ ] **Step 1: Nav entries** — same dual-registry pattern as Task 9:

```ts
  { label: "Gate Register",    href: "/purchases/gate-register",   icon: ScrollText, section: "Purchases", forModule: "purchase_store" },
  { label: "3-Way Match",      href: "/purchases/three-way-match", icon: CheckCheck, section: "Purchases", forModule: "purchase_store" },
```

(and the `SUB_NAV.purchases` twins with `section: "purchases"`; `ScrollText`/`CheckCheck` are already imported in nav.ts).

- [ ] **Step 2: Gate register page**

Copy an existing landscape report page's skeleton (e.g. the product-ledger page). `<PrintHeader title="Gate Register" orientation="landscape" />`; `print:hidden` filter bar: start/end date inputs + search input (vehicle/challan), refetch on change with the query string. Table in a `.table-freeze` wrapper: GI#, Date (`fmtDate`, `whitespace-nowrap`), Time, Vehicle, Challan, PO#, Vendor, Items, Qty (`fmt()`), Recorded by, Status.

- [ ] **Step 3: 3-way match page**

Same skeleton. `<PrintHeader title="3-Way Match — PO vs Gate vs Bill" orientation="landscape" />`; start/end filters. Table in `.table-freeze`: PO#, Vendor, Line, PO Qty, PO Rate, PO Amount, GI Qty, Bill Qty, Bill Amount, Qty Var, Amt Var. Rows with `flag === true` get `className="bg-amber-50 dark:bg-amber-900/20"` on screen (prints flatten via globals.css). All amounts via `fmt()`; currency code once in the `<th>`.

- [ ] **Step 4: PO detail changes**

In the PO detail page: after loading the PO, if `po.gate_required`:
- render a small "Gate coverage" line per PO line: `received/ordered` from `gi_coverage`,
- "Record Gate Inward" button → `Link` to `/purchases/gate-inward/new?po=${po.id}`,
- disable the convert-to-bill button while any line's coverage < qty, with `title="Record gate inward entries covering every line first"`.

- [ ] **Step 5: Verify**

Run in `frontend/`: `npx tsc --noEmit && npm run lint 2>&1 | tail -5` (no NEW errors vs the 66 pre-existing).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/nav.ts "frontend/src/app/(dashboard)/purchases" "frontend/src/app/(dashboard)/manufacturing/purchase-orders"
git commit -m "feat(gate-ui): gate register + 3-way match reports; PO coverage gate (#137 P2)"
```

---

### Task 11: Docs delta + full verification

**Files:**
- Modify: `CLAUDE.md` (models.py row: add GateInward/GateInwardLine to the purchase chain sentence; routers table: add `gate_inward.py` + `purchase_reports.py` rows; settings list: add `require_gate_inward`)
- Verify: full backend suite + frontend build + end-to-end drive

- [ ] **Step 1: CLAUDE.md delta** — three edits:
  1. In the `models.py` table row, extend the "**Purchase chain (#137 P1)**" sentence with: `GateInward (GI-YYYY-seq, memo gate entry vs PO, status open/billed/cancelled, append-only once billed) + GateInwardLine (per-PO-line qty caps) (#137 P2).`
  2. Add router rows after `routers/comparatives.py`:
     - `routers/gate_inward.py` | Gate Inward vs approved PO (#137 P2) — per-line qty ≤ PO remaining; coverage flips PO approved↔received; cancel-with-reason only while PO unbilled; gated by `purchase.gate`.
     - `routers/purchase_reports.py` | Gate register (vehicle/challan search) + 3-way match (PO vs Σ GI vs Bill, positional line match, variance flags).
  3. In the settings bullet list after `require_purchase_chain`: add `require_gate_inward` — when not `"false"` (default on), `convert-to-bill` requires full GI coverage once `purchase_store` is installed.

- [ ] **Step 2: Full backend suite**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: only the 2 known pre-existing failures (`test_account_hierarchy`, `test_update_migration`).

- [ ] **Step 3: Frontend build**

Run in `frontend/`: `npm run build`
Expected: builds clean.

- [ ] **Step 4: End-to-end drive**

Use the project verify skill (`.claude/skills/verify/SKILL.md`): launch both dev servers, log in as `demo.manufacturing@easy-books.app` / `demo1234`, and drive: create a bare PO (chain setting off) → approve → Record Gate Inward from PO detail → check PO flips to received → convert to bill → GI shows billed → Gate Register and 3-Way Match pages render with the entry. Screenshot the register.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md delta for gate inward (#137 P2)"
```
