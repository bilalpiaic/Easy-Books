# Purchase/Store Phase 3+4 — Store Issue + Vendor Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `StoreIssue` — the last leg of the procure-to-pay chain, general departmental/cost-center stock consumption with real GL posting — plus the vendor-performance report, a `/purchases` hub page, demo-seeder coverage, and docs delta that close out #137's original phasing.

**Architecture:** `StoreIssue`/`StoreIssueLine` post immediately on create (no draft/approve — unlike scrap Gate-Outward, this is routine consumption gated only by `block_negative_stock`). Each line calls the existing `consume_stock` (unchanged signature) to relieve inventory and calculate cost; one JV posts `Dr <user-picked Expense account> (analytic_account_id=X) / Cr Inventory` via the existing `post_transaction`. Two new store-side reports (Issue Register, Stock Tie-out) join `store_reports.py`; Vendor Performance (Phase 4) joins the existing `purchase_reports.py`. Spec: `docs/superpowers/specs/2026-07-10-purchase-store-phase3-4-store-issue-design.md`.

**Tech Stack:** FastAPI + SQLModel + Alembic (backend), Next.js 16 App Router + Tailwind v4 (frontend), pytest.

## Global Constraints

- Run backend tests from `backend/` as: `PYTHONPATH=. uv run pytest tests/<file> -q`, FOREGROUND only.
- 2 pre-existing failures on main (`test_account_hierarchy.py::test_cannot_create_child_under_posted_account`, `test_update_migration.py::test_upgrade_over_create_all_db_is_safe`) — not yours, don't chase.
- All new tables tenant-scoped; every query filters `tenant_id`. Voucher `SI-YYYY-seq` via `next_number(session, tenant_id, "store_issue", "SI", fmt="{prefix}-{YYYY}-{seq:04d}")`.
- Migration: new file `0032_store_issue.py`, revises `0031_gate_outward`; `bind.dialect.has_table(...)` guard per repo convention (SQLite can't ALTER-ADD constraints).
- Frontend: every new route goes into BOTH `NAV` and `SUB_NAV` + `SECTION_PREFIXES` in `frontend/src/lib/nav.ts` (standing requirement). Dates via `fmtDate()`; amounts via `fmt()` from `useFmt()`; no voucher-type badges; `print:hidden` on toolbars.
- Money values: `from services.money import D, money`.
- `consume_stock` (`services/inventory.py:168`) has NO `location_id` parameter — do not invent one. `from_location_id` on `StoreIssue` is a validated, stored, descriptive field only.
- `GoodsReceiptNote`/`GRNLine` is NOT part of the purchase chain — do not reference it anywhere in this work. The real receipt event is Bill creation (`record_purchase`, tagged `source_doc_type="bill"`).
- Commit after every task with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

---

### Task 1: Models, migration, permission resource, uninstall-guard fix

**Files:**
- Modify: `backend/models.py` (after `GateOutwardLine`, ~line 1183)
- Create: `backend/alembic/versions/0032_store_issue.py`
- Modify: `backend/services/permissions.py:45` (after `store.gate_outward`)
- Modify: `backend/routers/modules.py:91-108` (`_purchase_store_docs`)
- Test: `backend/tests/test_store_issues.py` (new)

**Interfaces:**
- Produces: `models.StoreIssue` (`id, tenant_id, number, issue_date, from_location_id, analytic_account_id, debit_account_id, notes, transaction_id, created_by_id, created_at`), `models.StoreIssueLine` (`id, store_issue_id, product_id, qty, unit_cost`), permission key `"store.issue"`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_store_issues.py`:

```python
"""#137 Phase 3 — Store Issue: departmental/cost-center consumption with
immediate GL posting + stock relief (no draft/approve gate)."""
from decimal import Decimal

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


def test_store_issue_models_and_permission_registered(client: TestClient):
    from models import StoreIssue, StoreIssueLine  # importable = tables exist
    from services.permissions import PERMISSION_RESOURCES
    assert "store.issue" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["store.issue"]["category"] == "Store"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_store_issues.py -q`
Expected: FAIL — `ImportError: cannot import name 'StoreIssue'`

- [ ] **Step 3: Add models**

In `backend/models.py`, directly after `class GateOutwardLine` (~line 1183):

```python
class StoreIssue(SQLModel, table=True):
    """Store consumption to a department/cost-center/project (#137 Phase 3).
    Deliberately separate from ProductionOrder's own raw-material
    consumption path — this is the "everything else" leg. Posts GL and
    relieves stock immediately on create; block_negative_stock is the
    control, not a second approver (unlike scrap Gate-Outward)."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_si_number_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)                            # SI-YYYY-seq
    issue_date: str
    from_location_id: int = Field(foreign_key="stocklocation.id")
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    debit_account_id: int = Field(foreign_key="account.id")
    notes: Optional[str] = None
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_by_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StoreIssueLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_si_line_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    store_issue_id: int = Field(foreign_key="storeissue.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id")
    qty: Money = money_col()
    unit_cost: Money = money_col(default=Decimal("0"))         # written after posting
```

- [ ] **Step 4: Register permission resource**

In `backend/services/permissions.py`, after the `store.gate_outward` line:

```python
    "store.issue":            {"label": "Store Issue",             "category": "Store"},
```

- [ ] **Step 5: Fix the uninstall guard (carry-in fix + new model)**

In `backend/routers/modules.py`, `_purchase_store_docs` is currently missing `GateOutward` entirely (a gap left over from Phase 2b that never got backfilled) — fix that in the same edit that adds `StoreIssue`:

```python
def _purchase_store_docs(session: Session, tenant_id: int) -> dict[str, int]:
    """Blocking document counts for purchase_store uninstall."""
    from sqlalchemy import func
    from sqlmodel import select
    from models import (ComparativeStatement, GateInward, GateOutward,
                        PurchaseDemand, StoreIssue, VendorQuotation)
    counts = {}
    for label, model in (
        ("purchase demands", PurchaseDemand),
        ("vendor quotations", VendorQuotation),
        ("comparative statements", ComparativeStatement),
        ("gate inwards", GateInward),
        ("gate outwards", GateOutward),
        ("store issues", StoreIssue),
    ):
        n = session.exec(
            select(func.count(model.id)).where(model.tenant_id == tenant_id)
        ).one()
        if n:
            counts[label] = n
    return counts
```

- [ ] **Step 6: Create migration**

Create `backend/alembic/versions/0032_store_issue.py`:

```python
"""store issue (#137 Phase 3)

Revision ID: 0032_store_issue
Revises: 0031_gate_outward
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0032_store_issue'
down_revision: Union[str, Sequence[str], None] = '0031_gate_outward'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'storeissue'):
        op.create_table('storeissue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('issue_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('from_location_id', sa.Integer(), nullable=False),
        sa.Column('analytic_account_id', sa.Integer(), nullable=True),
        sa.Column('debit_account_id', sa.Integer(), nullable=False),
        sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['analytic_account_id'], ['analyticaccount.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['debit_account_id'], ['account.id'], ),
        sa.ForeignKeyConstraint(['from_location_id'], ['stocklocation.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'number', name='unique_si_number_per_tenant')
        )
        op.create_index(op.f('ix_storeissue_number'), 'storeissue', ['number'], unique=False)
        op.create_index(op.f('ix_storeissue_tenant_id'), 'storeissue', ['tenant_id'], unique=False)

    if not bind.dialect.has_table(bind, 'storeissueline'):
        op.create_table('storeissueline',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_issue_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.CheckConstraint('qty > 0', name='ck_si_line_qty_positive'),
        sa.ForeignKeyConstraint(['store_issue_id'], ['storeissue.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_storeissueline_store_issue_id'), 'storeissueline', ['store_issue_id'], unique=False)


def downgrade() -> None:
    op.drop_table('storeissueline')
    op.drop_table('storeissue')
```

- [ ] **Step 7: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_store_issues.py -q`
Expected: 1 passed

- [ ] **Step 8: Verify migration runs**

Run: `PYTHONPATH=. uv run alembic upgrade head`
Expected: no error; `0032_store_issue` applied.

- [ ] **Step 9: Commit**

```bash
git add backend/models.py backend/alembic/versions/0032_store_issue.py backend/services/permissions.py backend/routers/modules.py backend/tests/test_store_issues.py
git commit -m "feat(store-issue): StoreIssue models + migration 0032 + store.issue resource + uninstall-guard fix (#137 P3)"
```

---

### Task 2: Store Issue router — create/list/get with GL posting

**Files:**
- Create: `backend/routers/store_issues.py`
- Modify: `backend/main.py` (mount — copy the `gate_outward` router's include pattern)
- Test: `backend/tests/test_store_issues.py` (append)

**Interfaces:**
- Produces: `GET/POST /api/store-issues`, `GET /api/store-issues/{id}`.
- Consumes: `services.inventory.consume_stock(session, tenant_id, product_id, qty, block_negative, source_doc_id, source_doc_type="store_issue")`, `services.posting.post_transaction`/`EntryInput`, `routers.common.next_number`/`apply_own_filter`.
- Create body: `{issue_date, from_location_id, analytic_account_id?, debit_account_id, notes?, lines: [{product_id, qty}]}`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_store_issues.py`:

```python
def _get_tenant_id(client, auth) -> int:
    return client.get("/api/auth/me", headers=auth).json()["tenant"]["id"]


def _stock_product(client, auth, qty=100, avg_cost=10):
    """Direct insert — the product-creation API has no field for pre-setting
    stock_qty/avg_cost; those only move via consume_stock/record_purchase."""
    from sqlmodel import Session
    from models import Product
    import db as _db
    tenant_id = _get_tenant_id(client, auth)
    with Session(_db.engine) as s:
        p = Product(tenant_id=tenant_id, name="Consumable Widget", product_type="stock",
                    stock_qty=Decimal(str(qty)), avg_cost=Decimal(str(avg_cost)))
        s.add(p); s.commit(); s.refresh(p)
        return p.id


def _own_location(client, auth) -> int:
    """The seeded default 'own' StockLocation ("MAIN"/"Main Store"), created
    by db.py's seed_data for every tenant regardless of business model.
    GET /api/stock-locations returns {"total":.., "items":[...]}, not a
    bare list — routers/stock_locations.py:36-45."""
    rows = client.get("/api/stock-locations", headers=auth).json()["items"]
    own = next(l for l in rows if l["type"] == "own")
    return own["id"]


def _expense_account(client, auth, code="5100", name="Office Supplies Expense") -> int:
    """GET /api/accounts returns {"total":.., "items":[...]}, not a bare
    list — routers/accounts.py:289-349."""
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    existing = next((a for a in accounts if a["code"] == code), None)
    if existing:
        return existing["id"]
    r = client.post("/api/accounts", headers=auth, json={
        "code": code, "name": name, "type": "Expense",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_store_issue_create_posts_gl_and_relieves_stock(client: TestClient):
    auth = _signup(client, "si1@t.com")
    pid = _stock_product(client, auth, qty=100, avg_cost=10)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": pid, "qty": 5}],
    })
    assert r.status_code == 201, r.text
    si = r.json()
    assert si["number"].startswith("SI-")

    prod = client.get(f"/api/products/{pid}", headers=auth).json()
    assert Decimal(str(prod["stock_qty"])) == Decimal("95")

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    def _find(node, code):
        if node.get("code") == code:
            return node
        for child in node.get("children") or []:
            found = _find(child, code)
            if found is not None:
                return found
        return None
    def bal(code):
        for node in tb["tree"]:
            found = _find(node, code)
            if found is not None:
                return found
        return None
    expense = bal("5100")
    assert expense is not None and Decimal(str(expense["debit"])) == Decimal("50")  # 5 * avg_cost(10)


def test_store_issue_with_analytic_account(client: TestClient):
    auth = _signup(client, "si2@t.com")
    pid = _stock_product(client, auth)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    aa = client.post("/api/analytic-accounts", headers=auth, json={
        "code": "CC-100", "name": "Maintenance Dept", "type": "cost_center",
    })
    assert aa.status_code in (200, 201), aa.text
    aa_id = aa.json()["id"]

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "analytic_account_id": aa_id,
        "lines": [{"product_id": pid, "qty": 2}],
    })
    assert r.status_code == 201, r.text
    detail = client.get(f"/api/store-issues/{r.json()['id']}", headers=auth).json()
    assert detail["analytic_account_id"] == aa_id


def test_store_issue_requires_expense_type_debit_account(client: TestClient):
    auth = _signup(client, "si3@t.com")
    pid = _stock_product(client, auth)
    loc_id = _own_location(client, auth)
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    asset_acct = next(a for a in accounts if a["type"] == "Asset" and not a.get("is_group"))

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": asset_acct["id"],
        "lines": [{"product_id": pid, "qty": 1}],
    })
    assert r.status_code == 400
    assert "expense" in r.json()["detail"].lower()


def test_store_issue_blocks_negative_stock_when_setting_enabled(client: TestClient):
    auth = _signup(client, "si4@t.com")
    pid = _stock_product(client, auth, qty=3, avg_cost=10)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    client.patch("/api/settings", headers=auth, json={"block_negative_stock": "true"})

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": pid, "qty": 10}],
    })
    assert r.status_code == 400
    prod = client.get(f"/api/products/{pid}", headers=auth).json()
    assert Decimal(str(prod["stock_qty"])) == Decimal("3")  # unchanged, no partial mutation


def test_store_issue_multi_line_sums_cost(client: TestClient):
    auth = _signup(client, "si5@t.com")
    pid1 = _stock_product(client, auth, qty=50, avg_cost=4)
    pid2 = _stock_product(client, auth, qty=50, avg_cost=6)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": pid1, "qty": 5}, {"product_id": pid2, "qty": 5}],
    })
    assert r.status_code == 201, r.text
    detail = client.get(f"/api/store-issues/{r.json()['id']}", headers=auth).json()
    line1 = next(l for l in detail["lines"] if l["product_id"] == pid1)
    line2 = next(l for l in detail["lines"] if l["product_id"] == pid2)
    assert Decimal(str(line1["unit_cost"])) == Decimal("4")
    assert Decimal(str(line2["unit_cost"])) == Decimal("6")


def test_store_issue_rejects_empty_lines_and_foreign_tenant_refs(client: TestClient):
    auth = _signup(client, "si6@t.com")
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "lines": [],
    })
    assert r.status_code == 400

    auth_b = _signup(client, "si6b@t.com")
    pid_b = _stock_product(client, auth_b)
    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "lines": [{"product_id": pid_b, "qty": 1}],
    })
    assert r.status_code == 404


def test_store_issue_permission_view_only_blocked_from_create(client: TestClient):
    auth = _signup(client, "si7@t.com")
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    client.patch("/api/settings", headers=auth, json={"user_rights_enabled": "true"})
    client.post("/api/users", headers=auth, json={
        "email": "siviewer@t.com", "password": "password123",
        "full_name": "Viewer", "role": "accountant",
    })
    users = client.get("/api/users", headers=auth).json()
    uid = next(u["id"] for u in users if u["email"] == "siviewer@t.com")
    client.put(f"/api/permissions/users/{uid}", headers=auth,
              json=[{"resource_key": "store.issue", "access_level": "view"}])
    r = client.post("/api/auth/login",
                    data={"username": "siviewer@t.com", "password": "password123"})
    viewer = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get("/api/store-issues", headers=viewer).status_code == 200
    r = client.post("/api/store-issues", headers=viewer, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "lines": [],
    })
    assert r.status_code == 403
```

(Verified: `GET /api/stock-locations` returns a bare list with `type`/`id`
fields — `routers/stock_locations.py`. `POST /api/accounts` takes
`{code, name, type}` matching `Account`'s own field names —
`routers/accounts.py`. `POST /api/analytic-accounts` takes
`{code, name, type}` — `routers/analytic_accounts.py`. All confirmed by
reading the respective router files before writing this test.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_store_issues.py -q`
Expected: new tests FAIL with 404 (routes not mounted).

- [ ] **Step 3: Implement `backend/routers/store_issues.py`**

```python
"""Store Issue — departmental/cost-center consumption out of the store
(#137 Phase 3). Deliberately separate from ProductionOrder's own
raw-material consumption path. Posts GL and relieves stock immediately on
create — no draft/approve gate; block_negative_stock is the control."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import Account, AnalyticAccount, Settings, StockLocation, StoreIssue, StoreIssueLine
from routers.common import SessionDep, WriteUserDep, log_audit, next_number
from services.inventory import consume_stock
from services.money import D, money
from services.permissions import apply_own_filter, perm_dep
from services.posting import EntryInput, post_transaction

router = APIRouter(
    prefix="/api/store-issues", tags=["store-issues"],
    dependencies=[perm_dep("store.issue")],
)


class SILineIn(BaseModel):
    product_id: int
    qty: float


class SIIn(BaseModel):
    issue_date: str
    from_location_id: int
    analytic_account_id: Optional[int] = None
    debit_account_id: int
    notes: Optional[str] = None
    lines: List[SILineIn] = []


def _get_si(session, user, si_id: int) -> StoreIssue:
    si = session.exec(
        select(StoreIssue).where(
            StoreIssue.id == si_id, StoreIssue.tenant_id == user.tenant_id
        )
    ).first()
    if not si:
        raise HTTPException(404, "Store issue not found")
    return si


def _serialize(session, si: StoreIssue) -> dict:
    lines = session.exec(
        select(StoreIssueLine).where(StoreIssueLine.store_issue_id == si.id)
    ).all()
    out = si.model_dump()
    out["lines"] = [l.model_dump() for l in lines]
    loc = session.get(StockLocation, si.from_location_id)
    out["location_name"] = loc.name if loc else None
    acct = session.get(Account, si.debit_account_id)
    out["debit_account_name"] = acct.name if acct else None
    if si.analytic_account_id:
        aa = session.get(AnalyticAccount, si.analytic_account_id)
        out["analytic_account_name"] = aa.name if aa else None
    return out


def _block_negative_stock(session, tenant_id: int) -> bool:
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id, Settings.key == "block_negative_stock",
        )
    ).first()
    return bool(row and (row.value or "").lower() == "true")


@router.get("")
def list_store_issues(
    session: SessionDep, user: WriteUserDep,
    from_location_id: Optional[int] = None, analytic_account_id: Optional[int] = None,
    start: Optional[str] = None, end: Optional[str] = None,
):
    q = select(StoreIssue).where(StoreIssue.tenant_id == user.tenant_id)
    if from_location_id:
        q = q.where(StoreIssue.from_location_id == from_location_id)
    if analytic_account_id:
        q = q.where(StoreIssue.analytic_account_id == analytic_account_id)
    if start:
        q = q.where(StoreIssue.issue_date >= start)
    if end:
        q = q.where(StoreIssue.issue_date <= end)
    q = apply_own_filter(q, StoreIssue, user, session)
    rows = session.exec(q.order_by(StoreIssue.id.desc())).all()
    return [_serialize(session, si) for si in rows]


@router.get("/{si_id}")
def get_store_issue(session: SessionDep, user: WriteUserDep, si_id: int):
    return _serialize(session, _get_si(session, user, si_id))


@router.post("", status_code=201, dependencies=[perm_dep("store.issue", "edit")])
def create_store_issue(session: SessionDep, user: WriteUserDep, body: SIIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")

    loc = session.exec(
        select(StockLocation).where(
            StockLocation.id == body.from_location_id, StockLocation.tenant_id == user.tenant_id
        )
    ).first()
    if not loc:
        raise HTTPException(404, "Stock location not found")

    debit_acct = session.exec(
        select(Account).where(
            Account.id == body.debit_account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not debit_acct:
        raise HTTPException(404, "Debit account not found")
    if debit_acct.type != "Expense":
        raise HTTPException(400, f"Debit account must be an Expense-type account, got '{debit_acct.type}'")

    if body.analytic_account_id:
        aa = session.exec(
            select(AnalyticAccount).where(
                AnalyticAccount.id == body.analytic_account_id,
                AnalyticAccount.tenant_id == user.tenant_id,
            )
        ).first()
        if not aa:
            raise HTTPException(404, "Analytic account not found")

    for l in body.lines:
        if D(l.qty) <= 0:
            raise HTTPException(400, "qty must be positive")

    number = next_number(
        session, user.tenant_id, "store_issue", "SI", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    si = StoreIssue(
        tenant_id=user.tenant_id, number=number, issue_date=body.issue_date,
        from_location_id=body.from_location_id, analytic_account_id=body.analytic_account_id,
        debit_account_id=body.debit_account_id, notes=body.notes, created_by_id=user.id,
    )
    session.add(si)
    session.flush()

    block_negative = _block_negative_stock(session, user.tenant_id)
    total_cost = D("0")
    line_rows = []
    for l in body.lines:
        qty = D(l.qty)
        try:
            cost = consume_stock(
                session, tenant_id=user.tenant_id, product_id=l.product_id, qty=qty,
                block_negative=block_negative, source_doc_id=si.id,
                source_doc_type="store_issue",
            )
        except Exception as e:  # InventoryError
            raise HTTPException(400, str(e))
        total_cost += cost
        row = StoreIssueLine(
            store_issue_id=si.id, product_id=l.product_id, qty=qty,
            unit_cost=money(cost / qty) if qty else D("0"),
        )
        session.add(row)
        line_rows.append(row)

    if total_cost > 0:
        inv_acct = session.exec(
            select(Account).where(Account.tenant_id == user.tenant_id, Account.code == "1200")
        ).first()
        if not inv_acct:
            from routers.common import get_or_create_account
            inv_acct = get_or_create_account(
                session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset"
            )
        txn = post_transaction(
            session, user, date=body.issue_date,
            description=f"Store issue — {number}",
            entries=[
                EntryInput(
                    account_id=debit_acct.id, debit=money(total_cost),
                    analytic_account_id=body.analytic_account_id,
                ),
                EntryInput(account_id=inv_acct.id, credit=money(total_cost)),
            ],
            voucher_type="JV",
            audit_entity_type="store_issue",
            audit_detail={"si_number": number},
        )
        si.transaction_id = txn.id

    log_audit(session, user, "CREATE", "store_issue", si.id, {"number": number})
    session.commit()
    return _serialize(session, si)
```

- [ ] **Step 4: Mount the router**

In `backend/main.py`, add `store_issues` alongside the `store_reports` import/include.

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_store_issues.py -q`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add backend/routers/store_issues.py backend/main.py backend/tests/test_store_issues.py
git commit -m "feat(store-issue): router — create/list/get with immediate GL posting (#137 P3)"
```

---

### Task 3: Store reports — issue register + stock tie-out

**Files:**
- Modify: `backend/routers/store_reports.py` (append endpoints)
- Test: `backend/tests/test_store_issues.py` (append)

**Interfaces:**
- Produces:
  - `GET /api/store-reports/issue-register?start=&end=&analytic_account_id=&q=` → `[{si fields, location_name, debit_account_name, analytic_account_name, item_count, total_cost}]`
  - `GET /api/store-reports/stock-tie-out?start=&end=&product_id=` → `[{product_id, product_name, opening_qty, received_qty, issued_qty, expected_closing, actual_closing, variance}]`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_store_issues.py`:

```python
def test_issue_register_filters(client: TestClient):
    auth = _signup(client, "rep1@t.com")
    pid = _stock_product(client, auth, qty=50, avg_cost=5)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "notes": "monthly maintenance draw",
        "lines": [{"product_id": pid, "qty": 3}],
    })
    rows = client.get("/api/store-reports/issue-register", headers=auth).json()
    assert len(rows) == 1
    assert Decimal(str(rows[0]["total_cost"])) == Decimal("15")  # 3 * 5

    rows = client.get("/api/store-reports/issue-register?q=maintenance", headers=auth).json()
    assert len(rows) == 1
    rows = client.get("/api/store-reports/issue-register?q=NOPE", headers=auth).json()
    assert rows == []


def test_stock_tie_out_zero_variance_on_clean_data(client: TestClient):
    """A product whose only movements in-window are one bill receipt and
    one store issue should tie out exactly."""
    auth = _signup(client, "rep2@t.com")
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    vendors = client.post("/api/vendors", headers=auth, json={"name": "Tie-Out Vendor"}).json()
    products = client.post("/api/products", headers=auth, json={
        "name": "Tie-Out Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    bill = client.post("/api/bills", headers=auth, json={
        "vendor_id": vendors["id"], "bill_date": "2026-07-01", "due_date": "2026-07-31",
        "lines": [{"description": "Tie-Out Widget", "product_id": products["id"], "qty": 20, "rate": 5}],
    })
    assert bill.status_code == 201, bill.text

    client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": products["id"], "qty": 6}],
    })

    rows = client.get(
        f"/api/store-reports/stock-tie-out?product_id={products['id']}", headers=auth
    ).json()
    assert len(rows) == 1
    row = rows[0]
    assert Decimal(str(row["received_qty"])) == Decimal("20")
    assert Decimal(str(row["issued_qty"])) == Decimal("6")
    assert Decimal(str(row["variance"])) == Decimal("0")
```

(Verified: `POST /api/bills` with a line carrying `product_id` triggers
`record_purchase` at creation — `routers/bills.py:301` — so the resulting
`StockMovement` is tagged `source_doc_type="bill"`, `direction="RECEIPT"`,
confirmed by reading `services/inventory.py::record_purchase`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_store_issues.py -q`
Expected: 2 new FAIL with 404.

- [ ] **Step 3: Implement the endpoints**

Append to `backend/routers/store_reports.py` (add these imports to the top of the file, merging with the existing import block rather than duplicating):

```python
from models import (Account, AnalyticAccount, Product, StockLocation,
                     StockMovement, StoreIssue, StoreIssueLine)
```

Then add:

```python
@router.get("/issue-register", dependencies=[perm_dep("store.issue")])
def issue_register(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    analytic_account_id: Optional[int] = None, q: Optional[str] = None,
):
    query = select(StoreIssue).where(StoreIssue.tenant_id == user.tenant_id)
    if start:
        query = query.where(StoreIssue.issue_date >= start)
    if end:
        query = query.where(StoreIssue.issue_date <= end)
    if analytic_account_id:
        query = query.where(StoreIssue.analytic_account_id == analytic_account_id)
    rows = session.exec(query.order_by(StoreIssue.id.desc())).all()

    out = []
    for si in rows:
        if q:
            needle = q.lower()
            hay = f"{si.number} {si.notes or ''}".lower()
            if needle not in hay:
                continue
        lines = session.exec(
            select(StoreIssueLine).where(StoreIssueLine.store_issue_id == si.id)
        ).all()
        row = si.model_dump()
        loc = session.get(StockLocation, si.from_location_id)
        row["location_name"] = loc.name if loc else None
        acct = session.get(Account, si.debit_account_id)
        row["debit_account_name"] = acct.name if acct else None
        if si.analytic_account_id:
            aa = session.get(AnalyticAccount, si.analytic_account_id)
            row["analytic_account_name"] = aa.name if aa else None
        row["item_count"] = len(lines)
        row["total_cost"] = sum(D(l.qty) * D(l.unit_cost) for l in lines)
        out.append(row)
    return out


@router.get("/stock-tie-out", dependencies=[perm_dep("store.issue")])
def stock_tie_out(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    product_id: Optional[int] = None,
):
    """Product-level, tenant-wide (not per-location — consume_stock has no
    location_id, so per-location tie-out would silently misreport; see
    design decision #5)."""
    prod_query = select(Product).where(Product.tenant_id == user.tenant_id, Product.product_type == "stock")
    if product_id:
        prod_query = prod_query.where(Product.id == product_id)
    products = session.exec(prod_query).all()

    out = []
    for prod in products:
        mv_query = select(StockMovement).where(
            StockMovement.tenant_id == user.tenant_id, StockMovement.product_id == prod.id,
        )
        movements = session.exec(mv_query).all()

        received_qty = D("0")
        issued_qty = D("0")
        opening_qty = D("0")
        for mv in movements:
            # StockMovement's timestamp field is `occurred_at`, NOT
            # `created_at` (models.py:646) — verified before writing this.
            mv_date = mv.occurred_at.strftime("%Y-%m-%d")
            in_window = (not start or mv_date >= start) and (not end or mv_date <= end)
            if mv.direction == "RECEIPT" and mv.source_doc_type == "bill":
                if in_window:
                    received_qty += D(mv.qty)
                elif start and mv_date < start:
                    opening_qty += D(mv.qty)
            elif mv.direction == "SHIPMENT" and mv.source_doc_type == "store_issue":
                if in_window:
                    issued_qty += D(mv.qty)
                elif start and mv_date < start:
                    opening_qty -= D(mv.qty)

        expected_closing = opening_qty + received_qty - issued_qty
        actual_closing = D(prod.stock_qty)
        out.append({
            "product_id": prod.id, "product_name": prod.name,
            "opening_qty": opening_qty, "received_qty": received_qty,
            "issued_qty": issued_qty, "expected_closing": expected_closing,
            "actual_closing": actual_closing,
            "variance": actual_closing - expected_closing,
        })
    return out
```

(Verified: `StockMovement.occurred_at` (not `created_at`) and
`direction`/`source_doc_type` are the exact field names —
`models.py:629-649` — matched deliberately for consistency with
`services/inventory.py` and `gate_outward.py`'s own report.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_store_issues.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/store_reports.py backend/tests/test_store_issues.py
git commit -m "feat(store-issue): issue-register + stock-tie-out reports (#137 P3)"
```

---

### Task 4: Vendor performance report (Phase 4)

**Files:**
- Modify: `backend/routers/purchase_reports.py` (append endpoint)
- Test: `backend/tests/test_vendor_performance.py` (new)

**Interfaces:**
- Produces: `GET /api/purchase-reports/vendor-performance?start=&end=&vendor_id=` → `[{vendor_id, vendor_name, po_count, avg_lead_time_days, short_receipt_rate_pct, rate_trend: [{product_id, product_name, quote_date, rate}]}]`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_vendor_performance.py`:

```python
"""#137 Phase 4 — vendor performance: delivery lead time + rate trend +
short-receipt-rate proxy (documented stand-in for true rejection rate,
which this schema can't track — see spec decision #4)."""
from datetime import date, timedelta

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


def _full_chain_po(client, auth, vendor_id, product_id, qty=10, rate=5,
                    order_date="2026-06-01", gi_date="2026-06-08"):
    """Builds one PurchaseOrder with a linked GateInward, bypassing the
    Demand/Comparative chain (purchase_store's require_purchase_chain
    defaults on, but auto-toggles off once a demand-less PO is the only
    path being tested — matches the existing test_purchase_flow.py
    convention of disabling the chain setting for isolated PO tests).

    NOTE: POST /api/purchase-orders returns the bare PurchaseOrder row with
    no "lines" key (routers/purchase_orders.py:150 `return po` — only
    GET /{po_id} attaches lines, routers/purchase_orders.py:68-80). Must
    re-fetch via GET to get each line's id for the Gate Inward call."""
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    po = client.post("/api/purchase-orders", headers=auth, json={
        "vendor_id": vendor_id, "order_date": order_date,
        "lines": [{"product_id": product_id, "description": "Item", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/purchase-orders/{po['id']}/approve", headers=auth)
    po = client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": gi_date,
        "lines": [{"po_line_id": po["lines"][0]["id"], "qty_received": qty}],
    })
    return po


def test_vendor_performance_lead_time(client: TestClient):
    auth = _signup(client, "vp1@t.com")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Lead Time Vendor"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "VP Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    _full_chain_po(client, auth, vendor["id"], product["id"],
                    order_date="2026-06-01", gi_date="2026-06-08")   # 7 days
    _full_chain_po(client, auth, vendor["id"], product["id"],
                    order_date="2026-06-10", gi_date="2026-06-15")   # 5 days

    rows = client.get("/api/purchase-reports/vendor-performance", headers=auth).json()
    row = next(r for r in rows if r["vendor_id"] == vendor["id"])
    assert row["po_count"] == 2
    assert row["avg_lead_time_days"] == 6.0  # (7+5)/2


def test_vendor_performance_rate_trend(client: TestClient):
    auth = _signup(client, "vp2@t.com")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Rate Vendor"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "Rate Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    demand = client.post("/api/purchase-demands", headers=auth, json={
        "demand_date": "2026-05-01", "required_by": "2026-06-01", "purpose": "restock",
        "lines": [{"product_id": product["id"], "description": "Item", "qty": 10}],
    }).json()
    client.patch(f"/api/purchase-demands/{demand['id']}/approve", headers=auth)
    client.post("/api/quotations", headers=auth, json={
        "demand_id": demand["id"], "vendor_id": vendor["id"], "quote_date": "2026-05-05",
        "lines": [{"demand_line_id": demand["lines"][0]["id"], "rate": 8, "qty": 10}],
    })

    rows = client.get("/api/purchase-reports/vendor-performance", headers=auth).json()
    row = next(r for r in rows if r["vendor_id"] == vendor["id"])
    assert len(row["rate_trend"]) == 1
    assert row["rate_trend"][0]["product_id"] == product["id"]
    assert row["rate_trend"][0]["rate"] == 8


def test_vendor_performance_short_receipt_matches_three_way_match(client: TestClient):
    """Cross-checks against the existing 3-way-match calc rather than
    re-deriving variance independently, per spec's stated guard against
    the two silently diverging."""
    auth = _signup(client, "vp3@t.com")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Short Vendor"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "Short Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    _full_chain_po(client, auth, vendor["id"], product["id"], qty=10, gi_date="2026-06-08")
    # Deliberately short-receive: only 7 of 10 actually received this time
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    po2 = client.post("/api/purchase-orders", headers=auth, json={
        "vendor_id": vendor["id"], "order_date": "2026-06-10",
        "lines": [{"product_id": product["id"], "description": "Item", "qty": 10, "rate": 5}],
    }).json()
    client.patch(f"/api/purchase-orders/{po2['id']}/approve", headers=auth)
    po2 = client.get(f"/api/purchase-orders/{po2['id']}", headers=auth).json()  # re-fetch for lines
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po2["id"], "gate_date": "2026-06-17",
        "lines": [{"po_line_id": po2["lines"][0]["id"], "qty_received": 7}],
    })

    twm_rows = client.get("/api/purchase-reports/three-way-match", headers=auth).json()
    twm_variance = sum(r["qty_variance"] for r in twm_rows if r["vendor_name"] == "Short Vendor")

    vp_rows = client.get("/api/purchase-reports/vendor-performance", headers=auth).json()
    row = next(r for r in vp_rows if r["vendor_id"] == vendor["id"])
    ordered_total = 20  # 10 + 10 across the two POs
    expected_pct = round(abs(twm_variance) / ordered_total * 100, 2)
    assert row["short_receipt_rate_pct"] == expected_pct
```

(Verified against actual endpoint shapes read before writing: `POST
/api/gate-inwards` line body is `{po_line_id, qty_received}` —
`routers/gate_inward.py`; `POST /api/quotations` line body is
`{demand_line_id, rate, qty}` — matches `VendorQuotationLine`'s own
fields exactly; `GET /api/purchase-reports/three-way-match` row shape
includes `qty_variance`, `vendor_name` — `routers/purchase_reports.py:53-104`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_vendor_performance.py -q`
Expected: FAIL with 404 (endpoint not mounted).

- [ ] **Step 3: Implement the endpoint**

Append to `backend/routers/purchase_reports.py` (merge these into the
existing import block rather than duplicating):

```python
from models import PurchaseDemandLine, Vendor, VendorQuotation, VendorQuotationLine
```

Then add:

```python
@router.get("/vendor-performance", dependencies=[perm_dep("purchase.comparative")])
def vendor_performance(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    vendor_id: Optional[int] = None,
):
    vendor_query = select(Vendor).where(Vendor.tenant_id == user.tenant_id)
    if vendor_id:
        vendor_query = vendor_query.where(Vendor.id == vendor_id)
    vendors = session.exec(vendor_query).all()

    out = []
    for vendor in vendors:
        po_query = select(PurchaseOrder).where(
            PurchaseOrder.tenant_id == user.tenant_id, PurchaseOrder.vendor_id == vendor.id,
        )
        if start:
            po_query = po_query.where(PurchaseOrder.order_date >= start)
        if end:
            po_query = po_query.where(PurchaseOrder.order_date <= end)
        pos = session.exec(po_query).all()
        if not pos:
            continue

        lead_times = []
        total_ordered = D("0")
        total_variance = D("0")
        for po in pos:
            po_lines = session.exec(
                select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
            ).all()
            total_ordered += sum(D(l.qty) for l in po_lines)
            cov = gi_coverage(session, user.tenant_id, po.id)
            for l in po_lines:
                total_variance += cov.get(l.id, D(0)) - D(l.qty)

            gis = session.exec(
                select(GateInward).where(
                    GateInward.po_id == po.id, GateInward.status != "cancelled",
                ).order_by(GateInward.gate_date)
            ).all()
            if gis:
                earliest_gi = gis[0]
                d_po = _date.fromisoformat(po.order_date)
                d_gi = _date.fromisoformat(earliest_gi.gate_date)
                lead_times.append((d_gi - d_po).days)

        quotation_rows = session.exec(
            select(VendorQuotation, VendorQuotationLine, PurchaseDemandLine)
            .join(VendorQuotationLine, VendorQuotationLine.quotation_id == VendorQuotation.id)
            .join(PurchaseDemandLine, PurchaseDemandLine.id == VendorQuotationLine.demand_line_id)
            .where(VendorQuotation.tenant_id == user.tenant_id, VendorQuotation.vendor_id == vendor.id)
            .order_by(VendorQuotation.quote_date)
        ).all()
        rate_trend = [
            {
                "product_id": pdl.product_id, "product_name": None,
                "quote_date": vq.quote_date, "rate": float(D(vql.rate)),
            }
            for vq, vql, pdl in quotation_rows
        ]

        out.append({
            "vendor_id": vendor.id, "vendor_name": vendor.name,
            "po_count": len(pos),
            "avg_lead_time_days": round(sum(lead_times) / len(lead_times), 2) if lead_times else None,
            # Proxy for rejection rate — this schema has no accepted/rejected
            # split anywhere (see spec decision #4). Negative variance only
            # (short-receipts), never counts over-receipt as "rejection".
            "short_receipt_rate_pct": (
                round(abs(min(total_variance, D(0))) / total_ordered * 100, 2)
                if total_ordered > 0 else 0.0
            ),
            "rate_trend": rate_trend,
        })
    return out
```

Add the missing imports at the top of the file if not already present:

```python
from datetime import date as _date
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_vendor_performance.py -q`
Expected: 3 passed

- [ ] **Step 5: Run the full purchase-chain regression**

Run: `PYTHONPATH=. uv run pytest tests/test_purchase_flow.py tests/test_gate_inward.py tests/test_gate_outward.py tests/test_store_issues.py tests/test_vendor_performance.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/purchase_reports.py backend/tests/test_vendor_performance.py
git commit -m "feat(vendor-performance): lead-time + rate-trend + short-receipt-rate report (#137 P4)"
```

---

### Task 5: Frontend — Store Issue nav + list/new/detail pages

**Files:**
- Modify: `frontend/src/lib/nav.ts` (Store section gains Store Issue entries)
- Create: `frontend/src/app/(dashboard)/store/issues/page.tsx`
- Create: `frontend/src/app/(dashboard)/store/issues/new/page.tsx`
- Create: `frontend/src/app/(dashboard)/store/issues/[id]/page.tsx`

**Interfaces:**
- Consumes: `GET/POST /api/store-issues`, `GET /api/store-issues/{id}`, `GET /api/stock-locations`, `GET /api/analytic-accounts`, `GET /api/accounts`, `GET /api/products`.
- Pattern sources: `store/gate-outward/{page,new/page,[id]/page}.tsx` for list/form/detail structure.

- [ ] **Step 1: Nav wiring**

In `frontend/src/lib/nav.ts`, add to `NAV` (after the existing Gate Outward/Outward Register/Dispatch Recon block, ~line 67):

```ts
  { label: "Store Issues",     href: "/store/issues",                    icon: PackageMinus, section: "Store", forModule: "purchase_store" },
```

(`PackageMinus` needs importing from `lucide-react` at the top of the file if not already present.)

Add the matching entry to the `store` array inside `SUB_NAV` (~line 289):

```ts
    { label: "Store Issues",     href: "/store/issues",                  icon: PackageMinus, section: "store", forModule: "purchase_store" },
```

- [ ] **Step 2: List page** — `store/issues/page.tsx`

Copy the structure of `store/gate-outward/page.tsx`. Columns: SI# (link to detail), Date, Location, Debit Account, Analytic Account, Cost (`fmt()`). "New Store Issue" link to `/store/issues/new`.

- [ ] **Step 3: New form** — `store/issues/new/page.tsx`

Structure from Gate Outward's scrap line-editor branch, simplified (single flow, no source-type radio):
- Header fields: issue_date (default today), location picker (`apiFetch("/api/stock-locations")`, dropdown of `{code} — {name}`), debit account picker (`apiFetch("/api/accounts")` filtered client-side to `type === "Expense"`), analytic account picker (`apiFetch("/api/analytic-accounts")`, optional — include a "None" option), notes textarea.
- Line items: product picker (`apiFetch("/api/products")` filtered to `product_type === "stock"`, showing `on_hand` from the product's `stock_qty` field next to each option) + qty input. "Add line" button, same repeater pattern as Gate Inward's new-form.
- Submit → `POST /api/store-issues`; on 201 `router.push` to detail; surface API `detail` string on 400/404 (e.g. the Expense-type-account 400, or an insufficient-stock 400 from `block_negative_stock`).

- [ ] **Step 4: Detail page** — `store/issues/[id]/page.tsx`

Structure from Gate Outward's detail page (no approve/cancel actions here — Store Issue has neither):
`<PrintHeader title={si.number} subtitle={fmtDate(si.issue_date)} />` (portrait), header grid (location_name, debit_account_name, analytic_account_name if present, notes), lines table (Product, Qty, Unit Cost, Line Total). Print button only (`print:hidden` wrapper) — no Approve/Cancel, matching the "posted fact, no edit/cancel" rule.

- [ ] **Step 5: Verify**

Run in `frontend/`: `npx tsc --noEmit && npx eslint src/lib/nav.ts "src/app/(dashboard)/store/issues"`
Expected: clean (no new errors vs. the documented pre-existing baseline).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/nav.ts "frontend/src/app/(dashboard)/store/issues"
git commit -m "feat(store-issue-ui): nav entry + store-issue list/new/detail pages (#137 P3)"
```

---

### Task 6: Frontend — report pages (issue register, stock tie-out, vendor performance)

**Files:**
- Create: `frontend/src/app/(dashboard)/store/issue-register/page.tsx`
- Create: `frontend/src/app/(dashboard)/store/stock-tie-out/page.tsx`
- Create: `frontend/src/app/(dashboard)/purchases/vendor-performance/page.tsx`
- Modify: `frontend/src/lib/nav.ts` (register all three routes)

**Interfaces:**
- Consumes: `GET /api/store-reports/issue-register`, `GET /api/store-reports/stock-tie-out`, `GET /api/purchase-reports/vendor-performance`.

- [ ] **Step 1: Nav wiring**

Add to `NAV`'s `store` entries:

```ts
  { label: "Issue Register",   href: "/store/issue-register",            icon: ScrollText,   section: "Store", forModule: "purchase_store" },
  { label: "Stock Tie-Out",    href: "/store/stock-tie-out",             icon: CheckCheck,   section: "Store", forModule: "purchase_store" },
```

Add to `NAV`'s `purchases` entries (after 3-Way Match):

```ts
  { label: "Vendor Performance", href: "/purchases/vendor-performance",  icon: TrendingUp,   section: "Purchases", forModule: "purchase_store" },
```

Mirror both additions in the `store`/`purchases` arrays inside `SUB_NAV`.

- [ ] **Step 2: Issue Register page**

Copy the landscape-report skeleton from `store/gate-outward-register/page.tsx`. `<PrintHeader title="Issue Register" orientation="landscape" />`; filter bar (`print:hidden`): start/end dates + search + analytic-account dropdown. Table in `.table-freeze`: SI#, Date, Location, Debit Account, Analytic Account, Items, Cost (`fmt()`).

- [ ] **Step 3: Stock Tie-Out page**

Same skeleton. `<PrintHeader title="Stock Tie-Out" orientation="landscape" />`; date-range filter + product dropdown. Table in `.table-freeze`: Product, Opening, Received, Issued, Expected Closing, Actual Closing, Variance (`fmt()`, red text + `whitespace-nowrap` when non-zero).

- [ ] **Step 4: Vendor Performance page**

Copy the skeleton from `purchases/three-way-match/page.tsx`. `<PrintHeader title="Vendor Performance" orientation="landscape" />`; date-range filter + vendor dropdown. Table in `.table-freeze`: Vendor, PO Count, Avg Lead Time (days), Short-Receipt Rate (%) — with a footnote line below the table: "Short-receipt rate approximates rejection rate from quantity variance; this system does not track a separate accepted/rejected quantity." A second, secondary table or expandable row per vendor shows the rate trend (Product, Quote Date, Rate) — reuse the existing expandable-row pattern from `customer-performance/page.tsx` if one exists, otherwise a simple nested `<table>` per vendor row.

- [ ] **Step 5: Verify**

Run in `frontend/`: `npx tsc --noEmit && npm run lint 2>&1 | tail -5` (no NEW errors vs. the documented pre-existing baseline).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/nav.ts "frontend/src/app/(dashboard)/store/issue-register" "frontend/src/app/(dashboard)/store/stock-tie-out" "frontend/src/app/(dashboard)/purchases/vendor-performance"
git commit -m "feat(store-issue-ui): issue-register, stock-tie-out, vendor-performance report pages (#137 P3/P4)"
```

---

### Task 7: `/purchases` hub page

**Files:**
- Modify: `frontend/src/lib/hubConfigs.ts` (new `PURCHASES_CONFIG`)
- Create: `frontend/src/app/(dashboard)/purchases/page.tsx`
- Modify: `frontend/src/app/(dashboard)/layout.tsx` (`TITLE_MAP` entry)
- Modify: `frontend/src/lib/nav.ts` (`getSectionHref`'s `purchases` key)

**Interfaces:**
- Consumes: `GET /api/purchase-demands`, `GET /api/purchase-orders`, `GET /api/gate-inwards`, `GET /api/reports/inventory-performance` (same fetch `INVENTORY_CONFIG` already uses).
- Produces: `PURCHASES_CONFIG: HubConfig` matching the real 4-KPI + 1-band + actions contract (`components/hub/HubPage.tsx:35-44`) — NOT an arbitrary multi-band list.

- [ ] **Step 1: Add `PURCHASES_CONFIG` to `hubConfigs.ts`**

Add near `INVENTORY_CONFIG` (reuses its exact band + one of its KPIs verbatim):

```ts
export const PURCHASES_CONFIG: HubConfig = {
  section: "Purchases",
  title: "Purchases",
  icon: ShoppingCart,
  fetch: () =>
    Promise.all([
      apiFetch<Record<string, unknown>[]>("/api/purchase-demands"),
      apiFetch<Record<string, unknown>[]>("/api/purchase-orders"),
      apiFetch<Record<string, unknown>[]>("/api/gate-inwards"),
      apiFetch<{ items: Record<string, unknown>[] }>("/api/reports/inventory-performance"),
    ]) as Promise<HubRawData>,
  kpis: [
    {
      label: "Pending Demands",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([demands]) => (demands as any[]).filter((d: any) => ["draft", "approved"].includes(d.status)).length,
    },
    {
      label: "POs Awaiting Billing",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([, pos]) => (pos as any[]).filter((p: any) => ["approved", "received"].includes(p.status)).length,
    },
    {
      label: "Gate Entries Awaiting Billing",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([, , gis]) => (gis as any[]).filter((g: any) => g.status === "open").length,
    },
    {
      label: "Low Stock",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([, , , inv]) => (inv.items ?? []).filter((i: any) => i.low_stock && i.on_hand > 0).length,
      tone: ([, , , inv]) =>
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (inv.items ?? []).filter((i: any) => i.low_stock && i.on_hand > 0).length > 0 ? "warning" : "normal",
    },
  ],
  band: "low-stock",
  bandData: ([, , , inv]) => ({
    items: [...(inv.items ?? [])]
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .filter((i: any) => i.low_stock || i.on_hand <= 0)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .sort((a: any, b: any) => {
        if (a.on_hand <= 0 && b.on_hand > 0) return -1
        if (b.on_hand <= 0 && a.on_hand > 0) return 1
        const ra = a.on_hand / (a.reorder_level || 1)
        const rb = b.on_hand / (b.reorder_level || 1)
        return ra - rb
      })
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .map((i: any) => ({ name: i.name, on_hand: i.on_hand, reorder_level: i.reorder_level ?? 0 })),
  }),
  actions: [
    { label: "New Demand",         href: "/purchases/demands/new",         icon: PlusCircle, primary: true },
    { label: "Comparatives",       href: "/purchases/comparatives",        icon: Scale                     },
    { label: "Gate Inward",        href: "/purchases/gate-inward",         icon: DoorOpen                  },
    { label: "Purchase Orders",    href: "/manufacturing/purchase-orders", icon: ShoppingCart              },
    { label: "Store Issues",       href: "/store/issues",                  icon: PackageMinus              },
    { label: "Vendor Performance", href: "/purchases/vendor-performance",  icon: TrendingUp                },
  ],
}
```

(`ShoppingCart`, `Scale`, `DoorOpen`, `PackageMinus`, `PlusCircle`,
`TrendingUp` — confirm each is already imported at the top of
`hubConfigs.ts`; add any missing ones to the existing `lucide-react`
import line.)

- [ ] **Step 2: Hub page route**

Create `frontend/src/app/(dashboard)/purchases/page.tsx`:

```tsx
"use client"

import HubPage from "@/components/hub/HubPage"
import { PURCHASES_CONFIG } from "@/lib/hubConfigs"

export default function PurchasesHubPage() {
  return <HubPage config={PURCHASES_CONFIG} />
}
```

- [ ] **Step 3: Breadcrumb/title wiring**

In `frontend/src/app/(dashboard)/layout.tsx`, add to `TITLE_MAP`:

```ts
  "/purchases": "Purchases",
```

- [ ] **Step 4: Section header now lands on the hub**

In `frontend/src/lib/nav.ts`, change `getSectionHref`'s `purchases` entry from `"/payable"` (a pre-existing stopgap, now superseded) to:

```ts
    purchases:     "/purchases",
```

- [ ] **Step 5: Verify**

Run in `frontend/`: `npx tsc --noEmit && npx eslint src/lib/hubConfigs.ts "src/app/(dashboard)/purchases/page.tsx" src/app/\(dashboard\)/layout.tsx src/lib/nav.ts`
Expected: clean (no new errors vs. the documented pre-existing baseline).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/hubConfigs.ts "frontend/src/app/(dashboard)/purchases/page.tsx" "frontend/src/app/(dashboard)/layout.tsx" frontend/src/lib/nav.ts
git commit -m "feat(purchases-hub): /purchases hub page (#137 P3)"
```

---

### Task 8: Demo seeder — Store Issues (Phase 4)

**Files:**
- Modify: `backend/scripts/seed_demo.py` (`_seed_purchase_store_chain`, ~line 1501)

**Interfaces:**
- Consumes: `StoreIssue`/`StoreIssueLine` models (Task 1), `next_number` (existing helper already imported in this file).

- [ ] **Step 1: Extend the seeder**

In `backend/scripts/seed_demo.py`, inside `_seed_purchase_store_chain` (~line 1501), after the existing Gate Outward seeding block (before the function returns), add Store Issues across a few cost centers:

```python
    # Store Issues (#137 Phase 4) — a handful of departmental consumption
    # entries so Issue Register / Stock Tie-out / Vendor Performance all
    # have data on first login.
    own_location = s.exec(
        select(StockLocation).where(StockLocation.tenant_id == tid, StockLocation.type == "own")
    ).first()
    if own_location:
        expense_acct = get_or_create_account(s, tid, "5100", "Office Supplies Expense", "Expense")
        maint_acct = get_or_create_account(s, tid, "5150", "Maintenance Expense", "Expense")
        cost_centers = s.exec(
            select(AnalyticAccount).where(AnalyticAccount.tenant_id == tid)
        ).all()
        issue_dates = _spread_dates(4, days_ago=90, min_days_ago=10)
        for i, (product, acct) in enumerate(
            zip(random.sample(stock_products, min(4, len(stock_products))),
                [expense_acct, maint_acct, expense_acct, maint_acct])
        ):
            si_number = next_number(s, tid, "store_issue", "SI", fmt="{prefix}-{YYYY}-{seq:04d}")
            si = StoreIssue(
                tenant_id=tid, number=si_number, issue_date=issue_dates[i],
                from_location_id=own_location.id, debit_account_id=acct.id,
                analytic_account_id=cost_centers[i % len(cost_centers)].id if cost_centers else None,
                notes=f"Demo store issue #{i + 1}", created_by_id=clerk.id,
            )
            s.add(si); s.flush()
            qty = D(random.randint(2, 8))
            cost = consume_stock(
                s, tenant_id=tid, product_id=product.id, qty=qty,
                source_doc_id=si.id, source_doc_type="store_issue",
            )
            s.add(StoreIssueLine(
                store_issue_id=si.id, product_id=product.id, qty=qty,
                unit_cost=money(cost / qty) if qty else D("0"),
            ))
            if cost > 0:
                inv_acct = get_or_create_account(s, tid, "1200", "Inventory (Raw Material)", "Asset")
                txn = post_transaction(
                    s, owner, date=issue_dates[i], description=f"Store issue — {si_number}",
                    entries=[
                        EntryInput(account_id=acct.id, debit=money(cost),
                                   analytic_account_id=si.analytic_account_id),
                        EntryInput(account_id=inv_acct.id, credit=money(cost)),
                    ],
                    voucher_type="JV", audit_entity_type="store_issue",
                    audit_detail={"si_number": si_number},
                )
                si.transaction_id = txn.id
            s.commit()
```

Add the necessary imports at the top of `seed_demo.py` if not already present (check the existing import block first — `StockLocation`, `AnalyticAccount`, `get_or_create_account`, `consume_stock`, `post_transaction`, `EntryInput` are all very likely already imported for the Gate Inward/Outward seeding just above this block; only add `StoreIssue`, `StoreIssueLine` if missing):

```python
from models import StoreIssue, StoreIssueLine
```

- [ ] **Step 2: Verify the seeder runs clean**

Run: `cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo`
Expected: no error; re-running is a no-op (the function's own idempotency guard — `if s.exec(select(PurchaseDemand)...).first(): return` — already covers this whole function including the new block, since it's appended before that early return's scope ends... verify placement: the new block must be BEFORE any `return` and AFTER the idempotency check, same as the rest of the function body).

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed_demo.py
git commit -m "feat(seed): Store Issue demo data for manufacturing tenant (#137 P4)"
```

---

### Task 9: Docs delta + full verification

**Files:**
- Modify: `CLAUDE.md` (models.py row, routers table, services table)
- Verify: full backend suite + frontend build + live e2e drive

- [ ] **Step 1: CLAUDE.md delta** — edits:
  1. Extend the `models.py` row's purchase-chain sentence (the one ending `...Gate Outward (GO-YYYY-seq...) + GateOutwardLine (#137 P2b).`) with: ` StoreIssue (SI-YYYY-seq, departmental/cost-center consumption — posts Dr user-picked Expense account (analytic-tagged) / Cr Inventory immediately on create, no draft/approve gate) + StoreIssueLine (#137 P3).`
  2. Add router rows after `routers/store_reports.py`:
     - `routers/store_issues.py` | Store Issue — departmental consumption; posts GL + relieves stock atomically on create via `consume_stock(..., source_doc_type="store_issue")`; debit account must be Expense-type. Gated by `store.issue`.
  3. Extend the `routers/store_reports.py` line to also mention: `Issue Register + Stock Tie-out (product-level, not per-location — consume_stock has no location_id).`
  4. Extend the `routers/purchase_reports.py` line to also mention: `Vendor Performance (delivery lead time, quotation rate trend, short-receipt-rate proxy for rejection rate).`
  5. Add a new Frontend bullet under "Purchases + Store nav sections": `/purchases` is now a hub page (`HubConfig` pattern, 4 KPIs + low-stock band + 6 actions) — the Purchases section header link changed from `/payable` to `/purchases` accordingly.
  6. Note in the same section: Store Issue lives under the **Store** nav section (`/store/issues`), not Purchases — it's the store-side consumption leg, same placement logic as Gate Outward.

- [ ] **Step 2: Full backend suite**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: only the 2 known pre-existing failures.

- [ ] **Step 3: Frontend build**

Run in `frontend/`: `npm run build`
Expected: builds clean.

- [ ] **Step 4: End-to-end drive**

Use the project verify skill (`.claude/skills/verify/SKILL.md`): launch both dev servers, log in as `demo.manufacturing@easy-books.app` / `demo1234`, and drive:
1. Open `/purchases` — hub loads with 4 KPIs, low-stock band, 6 action tiles; click each action tile once to confirm it navigates correctly.
2. Create a Store Issue (`/store/issues/new`): pick a location, an Expense-type debit account, an analytic account, one product line; submit; confirm redirect to detail page and the number starts with `SI-`.
3. Confirm the product's stock quantity decreased on `/products/{id}`.
4. Open `/store/issue-register` — the new entry appears; search by its notes text works.
5. Open `/store/stock-tie-out` — filter to the issued product; variance is 0 (assuming no other untracked movements for that product in the seeded data).
6. Open `/purchases/vendor-performance` — seeded vendors show lead time + rate trend; footnote about the short-receipt-rate proxy is visible.
7. Screenshot `/purchases`, `/store/issues/[id]`, `/store/stock-tie-out`, `/purchases/vendor-performance`.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md delta for Store Issue + vendor performance (#137 P3/P4)"
```
