# Standalone-Install Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Easy-Books safe & pleasant to install, evaluate, and **update** on a standalone PC — fix demo-data delivery, add a user-managed 2-level stock-category hierarchy, move Quick Actions to a top toolbar, wire best-practice updates, and refresh the docs.

**Architecture:** Backend = FastAPI/SQLModel + Alembic (SQLite local / Postgres hosted). Frontend = Next.js 16 App Router. Standalone ships two ways: `install-and-run.*` scripts and an Electron desktop app (`run_packaged.py` + `desktop/`). WS-1 makes **both** run Alembic on launch so updates apply new *columns*; everything else builds on that.

**Tech Stack:** FastAPI · SQLModel · Alembic · pytest · Next.js/React/TypeScript · Tailwind v4 · Electron/electron-builder/electron-updater.

> **Spec:** `docs/superpowers/specs/2026-05-31-standalone-install-polish-design.md`.
> **Status note (verified 2026-05-31):** Desktop Phase-2 Tasks 1–4 are **landed** (`desktop/main.js`, `preload.js`, `package.json`, `prepare-resources.*`, `run_packaged.py`, `easybooks-backend.spec`). `desktop/electron-builder.yml` was **just created** (Phase-2 Task 5 Step 1). Remaining desktop work (icons, signing, publish, electron-updater wiring) is covered by the existing `docs/superpowers/plans/2026-05-29-phase2-desktop-installer.md` — WS-5 below **references** it rather than duplicating it (DRY).

---

## Plan-level refinement vs. spec (WS-1)

The spec proposed decoupling `create_db_and_tables()` into `bootstrap_schema()` + `seed_defaults()` and switching the script path to `SCHEMA_BOOTSTRAP=alembic`. **This plan uses a lower-risk equivalent:** the script installers run `alembic upgrade head` *before* launch while keeping the default `SCHEMA_BOOTSTRAP=create_all`. Because every migration is guarded (`has_table` for tables, `get_columns()` for columns — see `analytic_accounts` migration), running the chain over a create_all-built DB is idempotent, and the existing startup seeding is preserved untouched. After Alembic reaches head, the lifespan `create_all()` is a harmless no-op. This achieves the goal (new **columns** reach upgraded script-installer users) without re-gating seeding. The desktop path already runs Alembic via `run_packaged.py` and is unchanged.

---

## FILE STRUCTURE

| File | Responsibility | WS |
|------|---------------|----|
| `install-and-run.ps1` / `.sh` (modify) | Run `alembic upgrade head` before launch; default `SEED_DEMO=false` (clean install) | 1, 2 |
| `backend/tests/test_update_migration.py` (new) | Upgrade-over-create_all DB is safe & idempotent | 1 |
| `backend/routers/admin.py` (new) | `POST/DELETE /api/admin/demo/seed` — on-demand demo tenants + teardown | 2 |
| `backend/tests/test_admin_demo.py` (new) | Seed creates 5 tenants idempotently; purge removes them; admin-gated | 2 |
| `backend/main.py` (modify) | Register `admin.router` | 2 |
| `frontend/src/app/(dashboard)/settings/page.tsx` (modify) | "Sample / Demo Data" card (mirrors Backup/Restore) | 2 |
| `backend/models.py` (modify) | `ProductCategory` table + `Product.category_id` | 3 |
| `backend/alembic/versions/<new>_product_categories.py` (new) | Guarded table + column migration | 3 |
| `backend/routers/product_categories.py` (new) | Category CRUD + 2-level validation | 3 |
| `backend/tests/test_product_categories.py` (new) | 2-level rule, delete-guard, tenant isolation | 3 |
| `backend/routers/products.py` (modify) | Accept/return `category_id`; `category_id` filter | 3 |
| `backend/db.py` (modify) | Seed starter categories per business model in `seed_data()` | 3 |
| `frontend/src/app/(dashboard)/products/categories/page.tsx` (new) | Category manager UI | 3 |
| `frontend/src/app/(dashboard)/products/page.tsx` (modify) | Parent→sub picker + category filter | 3 |
| `frontend/src/app/(dashboard)/dashboard/page.tsx` (modify) | Quick Actions → top toolbar | 4 |
| `desktop/main.js` (modify) | electron-updater wiring (Phase-2 Task 7) | 5 |
| `update.ps1` / `update.sh` / `update.bat` (new) | Script-install update command (pull → migrate → rebuild) | 5 |
| `frontend/src/components/VersionBadge.tsx` (new) | Show running version | 5 |
| `USER_GUIDE.md`, `WORKFLOW.md`, `DEPLOYMENT_LOCAL.md`, `CLAUDE.md` (modify) | Document all of the above | 6 |
| `README.md` (restructure) | Reflect current reality | 6 |

---

## WS-1 — Safe schema migration on update

### Task 1: Script installers run Alembic; prove upgrade-over-create_all is safe

**Files:**
- Test: `backend/tests/test_update_migration.py`
- Modify: `install-and-run.ps1`, `install-and-run.sh`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_update_migration.py
"""An existing DB that was built by create_all() (no alembic_version row) must
upgrade to head idempotently — this is what a script-installer user hits on
their first update after we start running Alembic on launch."""
import importlib
from sqlalchemy import create_engine, inspect, text


def test_upgrade_over_create_all_db_is_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import local_config; importlib.reload(local_config)
    import db; importlib.reload(db)

    # 1. Simulate an old install: schema via create_all, a row of real data, NO alembic_version.
    db.SQLModel.metadata.create_all(db.engine)
    with db.engine.begin() as conn:
        conn.execute(text("INSERT INTO tenant (name) VALUES ('Acme')"))
    assert "alembic_version" not in set(inspect(db.engine).get_table_names())

    # 2. Run the same upgrade the installer will run.
    import run_packaged; importlib.reload(run_packaged)
    run_packaged.migrate()  # alembic upgrade head against the same sqlite file

    # 3. Schema is at head, the data survived, and a second upgrade is a no-op.
    insp = inspect(db.engine)
    assert "alembic_version" in set(insp.get_table_names())
    with db.engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM tenant")).scalar() == "Acme"
    run_packaged.migrate()  # idempotent second run must not raise
```

- [ ] **Step 2: Run — expect PASS** (guards already make this safe; the test pins the guarantee)

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_update_migration.py -v`
Expected: PASS. *If it fails with a duplicate-table/column error, a migration is missing its guard — fix that migration to follow the `analytic_accounts` pattern (`has_table` / `get_columns()`), then re-run.*

- [ ] **Step 3: Make the PowerShell installer migrate before launch**

In `install-and-run.ps1`, the launch section sets `EB_DATA_DIR` then frees ports (around lines 66-78). Immediately **after** the `New-Item ... $env:EB_DATA_DIR` line and **before** "Free ports", insert:

```powershell
# Migrate the user's DB forward so updates apply new columns (not just tables).
Log 'Applying database migrations...'
Push-Location backend
uv run alembic upgrade head
Pop-Location
```

Also change the demo default (clean install — sample data is loaded on demand from Settings, see WS-2). Replace the `SEED_DEMO` line (currently `'true'`):

```powershell
if (-not $env:SEED_DEMO)   { $env:SEED_DEMO   = 'false' }   # clean install; load demo data on demand from Settings → Sample Data
```

- [ ] **Step 4: Make the bash installer migrate before launch**

In `install-and-run.sh`, find the `export SEED_DEMO="${SEED_DEMO:-true}"` line (≈71) and change it to:

```bash
export SEED_DEMO="${SEED_DEMO:-false}"   # clean install; load demo data on demand from Settings → Sample Data
```

Then, just before the backend is launched (after `EB_DATA_DIR` is exported/created), add:

```bash
echo "applying database migrations..."
( cd backend && PYTHONPATH=. uv run alembic upgrade head ) || echo "warning: alembic upgrade reported an issue (continuing)"
```

- [ ] **Step 5: Verify the full suite still passes**

Run: `cd backend && PYTHONPATH=. uv run pytest -q`
Expected: all green (no regressions).

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_update_migration.py install-and-run.ps1 install-and-run.sh
git commit -m "feat(local): script installers run Alembic on launch so updates apply new columns"
```

---

## WS-2 — One-click sample data

### Task 2: Admin demo-seed + purge endpoints

**Files:**
- Create: `backend/routers/admin.py`, `backend/tests/test_admin_demo.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_admin_demo.py
from fastapi.testclient import TestClient


def _admin_headers(client):
    # Reuse the project's existing auth test helper if present; otherwise sign up.
    r = client.post("/api/auth/signup", json={
        "email": "owner@acme.test", "password": "pw12345678",
        "full_name": "Owner", "company_name": "Acme",
    })
    assert r.status_code in (200, 201), r.text
    tok = client.post("/api/auth/login", data={
        "username": "owner@acme.test", "password": "pw12345678",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_demo_seed_is_idempotent_and_admin_gated(client):
    # Unauthenticated → 401
    assert client.post("/api/admin/demo/seed").status_code == 401

    headers = _admin_headers(client)
    r1 = client.post("/api/admin/demo/seed", headers=headers)
    assert r1.status_code == 200, r1.text
    assert len(r1.json()["tenants"]) == 5

    # Second call creates no duplicates (idempotent seeder).
    r2 = client.post("/api/admin/demo/seed", headers=headers)
    assert r2.status_code == 200
    emails = {t["email"] for t in r2.json()["tenants"]}
    assert "demo.simple@easy-books.app" in emails

    # Purge removes the demo tenants.
    rd = client.delete("/api/admin/demo/seed", headers=headers)
    assert rd.status_code == 200
    assert rd.json()["removed_tenants"] >= 5
```

> **Note:** if the repo's tests use a shared `client`/auth fixture (check `backend/tests/conftest.py` and an existing test like `tests/test_auth.py`), reuse it instead of the inline signup above to match conventions.

- [ ] **Step 2: Run — expect FAIL** (router missing → 404, assertions fail)

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_admin_demo.py -v`

- [ ] **Step 3: Create `backend/routers/admin.py`**

```python
"""Admin-only maintenance endpoints: load/remove the demo sample data.

Demo tenants are SEPARATE from the caller's own tenant, so loading them never
touches the user's real books. The seeder (scripts.seed_demo) is idempotent.
Imported lazily to avoid a db <-> scripts.seed_demo import cycle.
"""
from fastapi import APIRouter
from sqlmodel import SQLModel, select

from models import Tenant, User
from .common import AdminUserDep, SessionDep, log_audit

router = APIRouter(prefix="/api/admin", tags=["admin"])

DEMO_EMAILS = [
    "demo.simple@easy-books.app", "demo.services@easy-books.app",
    "demo.trader@easy-books.app", "demo.manufacturing@easy-books.app",
    "demo.telecom@easy-books.app",
]


@router.post("/demo/seed")
def seed_demo(session: SessionDep, user: AdminUserDep):
    """Create the 5 demo companies (login: each email / demo1234) with rich data."""
    from scripts.seed_demo import seed_all_demos  # lazy: avoids import cycle
    reports = seed_all_demos()
    log_audit(session, user, "demo_seed", "system", None, {"count": len(reports)})
    session.commit()
    return {"tenants": reports}


@router.delete("/demo/seed")
def purge_demo(session: SessionDep, user: AdminUserDep):
    """Remove the 5 demo companies and every row scoped to them."""
    demo_users = session.exec(select(User).where(User.email.in_(DEMO_EMAILS))).all()
    tenant_ids = sorted({u.tenant_id for u in demo_users})
    removed = 0
    for tid in tenant_ids:
        # Delete child rows first: reversed() yields tables in FK-safe order.
        for table in reversed(SQLModel.metadata.sorted_tables):
            if "tenant_id" in table.c:
                session.execute(table.delete().where(table.c.tenant_id == tid))
        session.execute(Tenant.__table__.delete().where(Tenant.__table__.c.id == tid))
        removed += 1
    log_audit(session, user, "demo_purge", "system", None, {"removed": removed})
    session.commit()
    return {"removed_tenants": removed}
```

- [ ] **Step 4: Register the router** — in `backend/main.py`, add `admin` to the `from routers import (...)` block and append `admin.router` to the `_ROUTERS` list.

```python
# in the import list:
    accounts, advances, aging, analytic_accounts, admin, assets, attachments, ...
# in _ROUTERS (near backup.router):
    backup.router,
    admin.router,
```

- [ ] **Step 5: Run — expect PASS**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_admin_demo.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/admin.py backend/tests/test_admin_demo.py backend/main.py
git commit -m "feat(local): admin endpoints to load/remove demo sample data on demand"
```

### Task 3: Settings "Sample / Demo Data" card

**Files:** Modify `frontend/src/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1: Add the card** — mirror the existing Backup/Restore card (≈ lines 855-905). Insert a new `<section>` after it:

```tsx
{/* Sample / Demo Data (evaluation) */}
<section className="bg-white border border-[#ede9e2] rounded-xl p-5 space-y-3">
  <h2 className="text-lg font-serif text-[#1a1814]">Sample / Demo Data</h2>
  <p className="text-sm text-[#1a1814]/60">
    Create 5 ready-made demo companies (one per business model) so you can explore Easy-Books
    with realistic data. They are <strong>separate</strong> from your own company and log in with
    <code className="mx-1 px-1 bg-[#f6f3ee] rounded">demo1234</code>
    (e.g. <code>demo.simple@easy-books.app</code>). Remove them any time.
  </p>
  <div className="flex flex-wrap gap-2">
    <button
      className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium hover:bg-[#a07f33] disabled:opacity-50"
      onClick={async (e) => {
        const btn = e.currentTarget; btn.disabled = true
        const base = process.env.NEXT_PUBLIC_API_URL ?? ""
        try {
          const res = await fetch(`${base}/api/admin/demo/seed`, { method: "POST", credentials: "include" })
          alert(res.ok
            ? "Demo companies loaded. Log out and sign in with demo1234 to explore them."
            : "Could not load demo data (admin only).")
        } finally { btn.disabled = false }
      }}
    >Load demo companies</button>
    <button
      className="px-4 py-2 rounded-lg border border-[#ede9e2] text-sm font-medium hover:bg-[#faf8f4]"
      onClick={async () => {
        if (!confirm("Remove all 5 demo companies and their data? Your own company is not affected.")) return
        const base = process.env.NEXT_PUBLIC_API_URL ?? ""
        const res = await fetch(`${base}/api/admin/demo/seed`, { method: "DELETE", credentials: "include" })
        alert(res.ok ? "Demo companies removed." : "Could not remove demo data (admin only).")
      }}
    >Remove demo companies</button>
  </div>
</section>
```

- [ ] **Step 2: Verify in the browser** — `cd frontend && npm run dev`, open `/settings`, confirm the card renders and the buttons hit the API (Network tab → 200). Loading then logging in as `demo.simple@easy-books.app / demo1234` shows populated data.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(dashboard)/settings/page.tsx"
git commit -m "feat(local): Settings card to load/remove demo sample data"
```

---

## WS-3 — 2-level stock categories

### Task 4: `ProductCategory` model + `Product.category_id` + migration

**Files:**
- Modify: `backend/models.py`
- Create: `backend/alembic/versions/aa01prodcat__product_categories.py`
- Test: `backend/tests/test_product_categories.py` (model part)

- [ ] **Step 1: Add the model** — in `backend/models.py`, immediately **above** `class Product` (line 339), add:

```python
class ProductCategory(SQLModel, table=True):
    """A 2-level product taxonomy. parent_id NULL → a top-level category;
    parent_id set → a sub-category. Depth is capped at 2 by the router."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "parent_id", "name", name="unique_category_name_per_parent"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    parent_id: Optional[int] = Field(default=None, foreign_key="productcategory.id", index=True)
    is_active: bool = Field(default=True)
```

Then add one field to `class Product` (after `tenant_id`, line 341):

```python
    category_id: Optional[int] = Field(default=None, foreign_key="productcategory.id", index=True)
```

- [ ] **Step 2: Hand-write the migration** (follow the `analytic_accounts` guard pattern). Create `backend/alembic/versions/aa01prodcat__product_categories.py`:

```python
"""product_categories

Revision ID: aa01prodcat
Revises: 520ea8c9ea33
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "aa01prodcat"
down_revision: Union[str, Sequence[str], None] = "520ea8c9ea33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "productcategory"):
        op.create_table(
            "productcategory",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "parent_id", "name", name="unique_category_name_per_parent"),
        )
        op.create_index(op.f("ix_productcategory_tenant_id"), "productcategory", ["tenant_id"])
        op.create_index(op.f("ix_productcategory_parent_id"), "productcategory", ["parent_id"])

    cols = {c["name"] for c in sa.inspect(bind).get_columns("product")}
    if "category_id" not in cols:
        op.add_column("product", sa.Column("category_id", sa.Integer(), nullable=True))
        op.create_index(op.f("ix_product_category_id"), "product", ["category_id"])
    # FK on product.category_id omitted: SQLite cannot ADD CONSTRAINT via ALTER.


def downgrade() -> None:
    op.drop_index(op.f("ix_product_category_id"), table_name="product")
    op.drop_column("product", "category_id")
    op.drop_index(op.f("ix_productcategory_parent_id"), table_name="productcategory")
    op.drop_index(op.f("ix_productcategory_tenant_id"), table_name="productcategory")
    op.drop_table("productcategory")
```

- [ ] **Step 3: Apply + verify the migration**

```bash
cd backend && PYTHONPATH=. uv run alembic upgrade head
PYTHONPATH=. uv run python -c "from sqlalchemy import create_engine, inspect; from local_config import sqlite_path; i=inspect(create_engine(f'sqlite:///{sqlite_path()}')); print('productcategory' in i.get_table_names(), 'category_id' in {c['name'] for c in i.get_columns('product')})"
```
Expected: `True True`

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/alembic/versions/aa01prodcat__product_categories.py
git commit -m "feat(products): ProductCategory table + Product.category_id (2-level taxonomy)"
```

### Task 5: Category CRUD router + 2-level validation

**Files:**
- Create: `backend/routers/product_categories.py`
- Test: `backend/tests/test_product_categories.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_product_categories.py  (uses the same auth helper/fixture as test_admin_demo)
def test_two_level_cap_and_delete_guard(client):
    from tests.test_admin_demo import _admin_headers
    h = _admin_headers(client)

    parent = client.post("/api/product-categories", json={"name": "SIM"}, headers=h).json()
    sub = client.post("/api/product-categories", json={"name": "Prepaid", "parent_id": parent["id"]}, headers=h).json()

    # A third level is rejected.
    r = client.post("/api/product-categories", json={"name": "Lyca", "parent_id": sub["id"]}, headers=h)
    assert r.status_code == 400
    assert "two levels" in r.json()["detail"].lower()

    # Deleting a parent that still has children is blocked.
    rd = client.delete(f"/api/product-categories/{parent['id']}", headers=h)
    assert rd.status_code == 400

    # Deleting the leaf works, then the parent works.
    assert client.delete(f"/api/product-categories/{sub['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/product-categories/{parent['id']}", headers=h).status_code == 200
```

- [ ] **Step 2: Run — expect FAIL** (404, no router)

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_product_categories.py -v`

- [ ] **Step 3: Create `backend/routers/product_categories.py`**

```python
"""Product category CRUD with a hard 2-level depth cap (parent → sub)."""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import Product, ProductCategory
from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/product-categories", tags=["product-categories"])


class CategoryIn(BaseModel):
    name: str
    parent_id: Optional[int] = None
    is_active: bool = True


def _owned(session, tenant_id, cat_id) -> ProductCategory:
    cat = session.get(ProductCategory, cat_id)
    if not cat or cat.tenant_id != tenant_id:
        raise HTTPException(404, "Category not found")
    return cat


@router.get("")
def list_categories(session: SessionDep, user: CurrentUserDep):
    """Return categories as a nested parent→children tree."""
    rows = session.exec(
        select(ProductCategory).where(ProductCategory.tenant_id == user.tenant_id)
    ).all()
    by_parent: dict = {}
    for c in rows:
        by_parent.setdefault(c.parent_id, []).append(
            {"id": c.id, "name": c.name, "parent_id": c.parent_id, "is_active": c.is_active}
        )
    roots = by_parent.get(None, [])
    for r in roots:
        r["children"] = by_parent.get(r["id"], [])
    return roots


@router.post("")
def create_category(body: CategoryIn, session: SessionDep, user: WriteUserDep):
    if body.parent_id is not None:
        parent = _owned(session, user.tenant_id, body.parent_id)
        if parent.parent_id is not None:
            raise HTTPException(400, "Categories support only two levels (parent → sub-category).")
    cat = ProductCategory(tenant_id=user.tenant_id, name=body.name.strip(),
                          parent_id=body.parent_id, is_active=body.is_active)
    session.add(cat)
    log_audit(session, user, "create", "product_category", None, {"name": cat.name})
    session.commit(); session.refresh(cat)
    return {"id": cat.id, "name": cat.name, "parent_id": cat.parent_id, "is_active": cat.is_active}


@router.patch("/{cat_id}")
def update_category(cat_id: int, body: CategoryIn, session: SessionDep, user: WriteUserDep):
    cat = _owned(session, user.tenant_id, cat_id)
    if body.parent_id is not None:
        if body.parent_id == cat_id:
            raise HTTPException(400, "A category cannot be its own parent.")
        parent = _owned(session, user.tenant_id, body.parent_id)
        if parent.parent_id is not None:
            raise HTTPException(400, "Categories support only two levels (parent → sub-category).")
        # Block demoting a parent that itself has children.
        has_children = session.exec(
            select(ProductCategory).where(ProductCategory.parent_id == cat_id)
        ).first()
        if has_children:
            raise HTTPException(400, "Move or delete its sub-categories first.")
    cat.name = body.name.strip(); cat.parent_id = body.parent_id; cat.is_active = body.is_active
    session.add(cat); session.commit(); session.refresh(cat)
    return {"id": cat.id, "name": cat.name, "parent_id": cat.parent_id, "is_active": cat.is_active}


@router.delete("/{cat_id}")
def delete_category(cat_id: int, session: SessionDep, user: WriteUserDep):
    cat = _owned(session, user.tenant_id, cat_id)
    if session.exec(select(ProductCategory).where(ProductCategory.parent_id == cat_id)).first():
        raise HTTPException(400, "Delete its sub-categories first.")
    if session.exec(select(Product).where(Product.category_id == cat_id)).first():
        raise HTTPException(400, "Reassign products off this category first.")
    session.delete(cat); session.commit()
    return {"ok": True}
```

- [ ] **Step 4: Register** — in `backend/main.py` add `product_categories` to the import block and `product_categories.router` to `_ROUTERS` (next to `products.router`).

- [ ] **Step 5: Run — expect PASS**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_product_categories.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/product_categories.py backend/tests/test_product_categories.py backend/main.py
git commit -m "feat(products): category CRUD router with 2-level cap + delete guards"
```

### Task 6: Wire `category_id` into products + seed starter categories

**Files:** Modify `backend/routers/products.py`, `backend/db.py`

- [ ] **Step 1: Accept `category_id`** — in `backend/routers/products.py`, add `category_id: Optional[int] = None` to the `ProductCreate` model, set it on create and in the update handler, include it in the list response, and add a filter:

```python
# ProductCreate: add field
    category_id: Optional[int] = None
# in list_products(...), add param `category_id: Optional[int] = None` and:
    if category_id is not None:
        q = q.where(Product.category_id == category_id)
```

- [ ] **Step 2: Seed starter categories** — in `backend/db.py` `seed_data()`, after the StockLocation seeding, add a per-model starter set (generic; users edit in-app):

```python
        # Starter product categories (parent → sub). Generic defaults; editable in-app.
        STARTER_CATEGORIES = {
            "trader":            {"Goods": ["General", "Imported"]},
            "manufacturing":     {"Raw Materials": ["Metals", "Consumables"], "Finished Goods": ["Standard"]},
            "telecom_franchise": {"SIM": ["Prepaid", "Postpaid"], "Devices": ["Handsets", "Accessories"]},
        }
        from models import ProductCategory
        if not s.exec(select(ProductCategory).where(ProductCategory.tenant_id == tenant_id)).first():
            for parent_name, subs in STARTER_CATEGORIES.get(model, {}).items():
                parent = ProductCategory(tenant_id=tenant_id, name=parent_name)
                s.add(parent); s.flush()
                for sub in subs:
                    s.add(ProductCategory(tenant_id=tenant_id, name=sub, parent_id=parent.id))
            s.commit()
```

- [ ] **Step 3: Test** — extend `tests/test_product_categories.py`:

```python
def test_product_can_be_assigned_a_category(client):
    from tests.test_admin_demo import _admin_headers
    h = _admin_headers(client)
    cat = client.post("/api/product-categories", json={"name": "Goods"}, headers=h).json()
    p = client.post("/api/products", json={"name": "Widget", "product_type": "stock",
                                           "category_id": cat["id"]}, headers=h).json()
    listed = client.get(f"/api/products?category_id={cat['id']}", headers=h).json()
    assert any(x["id"] == p["id"] for x in (listed if isinstance(listed, list) else listed["items"]))
```

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_product_categories.py -v` → PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/products.py backend/db.py backend/tests/test_product_categories.py
git commit -m "feat(products): assign/filter products by category + seed starter categories"
```

### Task 7: Frontend — category manager + product picker/filter

**Files:**
- Create: `frontend/src/app/(dashboard)/products/categories/page.tsx`
- Modify: `frontend/src/app/(dashboard)/products/page.tsx`

- [ ] **Step 1: Category manager page** — create `products/categories/page.tsx` (client component, mirrors the products page conventions: `apiFetch`, modal, list). It lists the parent→children tree from `GET /api/product-categories`, with "Add parent" and per-parent "Add sub-category" actions (`POST`), inline rename (`PATCH`), and delete (`DELETE`, surfacing the 400 guard messages via `alert`). Use the brand styles (`bg-white border border-[#ede9e2] rounded-xl`, gold `#b8943f` accents).

```tsx
'use client'
import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

interface Cat { id: number; name: string; parent_id: number | null; is_active: boolean; children?: Cat[] }

export default function CategoriesPage() {
  const [tree, setTree] = useState<Cat[]>([])
  const load = () => apiFetch<Cat[]>('/api/product-categories').then(setTree).catch(() => {})
  useEffect(() => { load() }, [])

  const add = async (parent_id: number | null) => {
    const name = prompt(parent_id ? 'New sub-category name' : 'New parent category name')?.trim()
    if (!name) return
    await apiFetch('/api/product-categories', { method: 'POST', body: JSON.stringify({ name, parent_id }) })
    load()
  }
  const remove = async (id: number) => {
    try { await apiFetch(`/api/product-categories/${id}`, { method: 'DELETE' }); load() }
    catch (e) { alert((e as Error).message) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-serif font-semibold text-[#1a1814]">Product Categories</h1>
        <button onClick={() => add(null)} className="px-3 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium">+ Parent category</button>
      </div>
      <div className="space-y-2">
        {tree.map(parent => (
          <div key={parent.id} className="bg-white border border-[#ede9e2] rounded-xl p-3">
            <div className="flex items-center justify-between">
              <span className="font-medium text-[#1a1814]">{parent.name}</span>
              <div className="flex gap-2 text-sm">
                <button onClick={() => add(parent.id)} className="text-[#b8943f]">+ Sub</button>
                <button onClick={() => remove(parent.id)} className="text-red-600">Delete</button>
              </div>
            </div>
            <div className="mt-2 ml-4 flex flex-wrap gap-2">
              {(parent.children ?? []).map(sub => (
                <span key={sub.id} className="inline-flex items-center gap-2 px-2 py-1 rounded-lg bg-[#faf8f4] border border-[#ede9e2] text-xs">
                  {sub.name}
                  <button onClick={() => remove(sub.id)} className="text-red-500">×</button>
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Product form picker + list filter** — in `products/page.tsx`:
  - Add `category_id: number | null` to the `Product` interface and `category_id: string` to `FormState`/`emptyForm`.
  - Fetch categories once (`apiFetch<Cat[]>('/api/product-categories')`) and store in state.
  - In the modal form, add a **parent select** and a dependent **sub-category select** (the sub list = the chosen parent's `children`); submit the chosen leaf id as `category_id`.
  - Add a category dropdown next to the search box that sets a `categoryFilter` and appends `&category_id=<id>` to the products fetch URL.

- [ ] **Step 3: Verify** — `cd frontend && npm run dev`; visit `/products/categories` (create a parent + sub), then `/products` (assign a product, filter by category). Confirm 2nd-level cap is enforced (the UI only offers parent→sub).

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)/products/categories/page.tsx" "frontend/src/app/(dashboard)/products/page.tsx"
git commit -m "feat(products): category manager UI + parent→sub picker and filter"
```

---

## WS-4 — Quick Actions to the top

### Task 8: Move Quick Actions into a top toolbar

**Files:** Modify `frontend/src/app/(dashboard)/dashboard/page.tsx`

- [ ] **Step 1: Extract the action list** — the 6 actions currently live inline at lines 393-399. Define them once above the `return` (so the toolbar can map over them):

```tsx
const QUICK_ACTIONS = [
  { label: "New Invoice",   href: "/invoices",  icon: FileSignature, color: "text-green-600" },
  { label: "New Bill",      href: "/bills",     icon: Receipt,       color: "text-orange-600" },
  { label: "New Entry",     href: "/entry",     icon: Hash,          color: "text-blue-600" },
  { label: "Products",      href: "/products",  icon: Package,       color: "text-purple-600" },
  { label: "Workflow Guide",href: "/workflow",  icon: TrendingUp,    color: "text-[#b8943f]" },
  { label: "User Guide",    href: "/guide",     icon: Wallet,        color: "text-[#1a1814]" },
]
```

- [ ] **Step 2: Insert the toolbar under the header** — directly after the header `</div>` block (the `flex ... justify-between` ending at line 225), add:

```tsx
{/* Quick Actions — top toolbar */}
<div className="bg-white border border-[#ede9e2] rounded-xl shadow-sm px-3 py-2 flex flex-wrap items-center gap-2">
  <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/45 mr-1">Quick Actions</span>
  {QUICK_ACTIONS.map(({ label, href, icon: Icon, color }) => (
    <Link key={href} href={href}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-transparent hover:bg-[#faf8f4] hover:border-[#b8943f]/30 transition-all">
      <Icon className={`w-4 h-4 ${color}`} />
      <span className="text-sm font-medium text-[#1a1814]/80">{label}</span>
    </Link>
  ))}
</div>
```

- [ ] **Step 3: Remove the old bottom block + widen Recent Transactions** — delete the bottom "Quick actions" card (lines 389-409) and change the wrapping grid (`grid ... lg:grid-cols-3` at line 388) plus the Recent Transactions card's `lg:col-span-2` so Recent Transactions spans full width.

- [ ] **Step 4: Verify** — `npm run dev`, open `/dashboard`: the action bar sits directly under the "Dashboard" title; Recent Transactions is full-width at the bottom; no leftover empty column.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(dashboard)/dashboard/page.tsx"
git commit -m "feat(dashboard): move Quick Actions into a top toolbar under the title"
```

---

## WS-5 — Best-practice update delivery

> **Reuse, don't rebuild:** the desktop installer/signing/publish/auto-update flow is already specified in `docs/superpowers/plans/2026-05-29-phase2-desktop-installer.md` (Tasks 5-9). `electron-builder.yml` is now created. This WS adds the two pieces that plan leaves open and that apply to the **script** path too.

### Task 9: Wire electron-updater (Phase-2 Task 7)

**Files:** Modify `desktop/main.js`

- [ ] **Step 1** — after `createWindow()` resolves, add auto-update. At the top of `desktop/main.js` add `const { autoUpdater } = require("electron-updater")`, and inside `app.whenReady().then(...)` after `createWindow()`:

```js
    app.whenReady().then(() => {
      startSidecars(); createWindow()
      try { autoUpdater.checkForUpdatesAndNotify() } catch (_) {}
    })
```

- [ ] **Step 2** — document that this is inert until a GitHub Release exists (the `publish` block in `electron-builder.yml`). No runtime test is feasible without a published release; verification is the manual upgrade test in the Phase-2 plan (Task 8, "Upgrade test").

- [ ] **Step 3: Commit**

```bash
git add desktop/main.js desktop/electron-builder.yml
git commit -m "feat(desktop): auto-update via electron-updater + electron-builder publish config"
```

### Task 10: Script-install update command + version badge

**Files:** Create `update.sh`, `update.ps1`, `update.bat`; Create `frontend/src/components/VersionBadge.tsx`

- [ ] **Step 1: `update.sh`** (data dir is never touched; migrations run via the installer relaunch):

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Updating Easy-Books (your data in \$EB_DATA_DIR is left untouched)..."
git pull --ff-only
( cd backend && uv sync )
( cd frontend && npm install && npx next build )
echo "Update complete. Relaunching..."
exec ./install-and-run.sh   # runs 'alembic upgrade head' then starts the app (WS-1)
```

- [ ] **Step 2: `update.ps1`** — same flow in PowerShell: `git pull --ff-only`; `Push-Location backend; uv sync; Pop-Location`; rebuild frontend; then `& "$PSScriptRoot\install-and-run.ps1" -Rebuild`. And `update.bat`: a one-liner that calls `powershell -ExecutionPolicy Bypass -File "%~dp0update.ps1"`.

- [ ] **Step 3: Version badge** — read the version at build time and show it in the footer/Settings.

```tsx
// frontend/src/components/VersionBadge.tsx
export default function VersionBadge() {
  const v = process.env.NEXT_PUBLIC_APP_VERSION ?? "dev"
  return <span className="text-[11px] text-[#1a1814]/40">Easy-Books v{v}</span>
}
```
Set `NEXT_PUBLIC_APP_VERSION` from `package.json` version in the build step, and render `<VersionBadge />` in the settings page footer.

- [ ] **Step 4: Verify** — `chmod +x update.sh`; run it on a clone with a dummy upstream commit → it pulls, rebuilds, relaunches, data intact. Confirm the badge shows the version.

- [ ] **Step 5: Commit**

```bash
git add update.sh update.ps1 update.bat frontend/src/components/VersionBadge.tsx
git commit -m "feat(local): script-install update command + in-app version badge"
```

---

## WS-6 — Docs + README

### Task 11: Update guides

**Files:** Modify `USER_GUIDE.md`, `WORKFLOW.md`, `DEPLOYMENT_LOCAL.md`, `CLAUDE.md`

- [ ] **Step 1: `DEPLOYMENT_LOCAL.md`** — add an **"Updating Easy-Books & your data"** section: (a) where data lives (`%USERPROFILE%\.easy-books` / Electron `userData`); (b) updates run `alembic upgrade head` first → data migrated forward, never wiped; (c) script path: run `update.*`; (d) desktop path: auto-update + the signing/publish runbook (point to the Phase-2 plan; do **not** commit certs); (e) a "back up first via Settings → Backup" tip.
- [ ] **Step 2: `USER_GUIDE.md`** — add: **Sample/Demo Data** (Settings card, demo logins, removal); **Product Categories** (parent→sub, how to assign/filter); note Quick Actions are now the top toolbar.
- [ ] **Step 3: `WORKFLOW.md`** — add a short "Set up product categories" step before stock-product creation; reference the demo-data button for evaluation.
- [ ] **Step 4: `CLAUDE.md`** — document: installers run Alembic on launch (WS-1 refinement); `routers/admin.py` demo seed/purge; `ProductCategory` 2-level model + migration; `routers/product_categories.py`; update story.
- [ ] **Step 5: Commit**

```bash
git add USER_GUIDE.md WORKFLOW.md DEPLOYMENT_LOCAL.md CLAUDE.md
git commit -m "docs: sample data, product categories, quick-actions, update & data-safety"
```

### Task 12: Restructure README.md

**Files:** Modify `README.md`

- [ ] **Step 1: Rewrite** the README around the current reality, in this order: **What it is** (SaaS double-entry bookkeeping for SMEs) → **Screens/feature highlights** → **Two ways to run** (① one-click standalone `install-and-run.bat`/desktop app; ② developer mode `dev.sh`) → **Demo / sample data** (the Settings button + demo logins) → **Updating & data safety** (one paragraph: data lives outside the app; updates migrate forward) → **Tech stack** → **Development** (backend/frontend commands from CLAUDE.md) → **Docs index** (link USER_GUIDE, WORKFLOW, DEPLOYMENT_LOCAL, BLUEPRINT). Demote the legacy Express/`public/` stack to a single "Legacy reference" line.
- [ ] **Step 2: Verify** links resolve (`grep -o "\]([^)]*\.md)" README.md` → each path exists).
- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: restructure README around the current standalone + desktop reality"
```

---

## Self-Review

**Spec coverage:** WS-1→Task 1 ✓ · WS-2→Tasks 2-3 ✓ · WS-3→Tasks 4-7 ✓ · WS-4→Task 8 ✓ · WS-5→Tasks 9-10 (+ created `electron-builder.yml`; Phase-2 plan covers signing/publish) ✓ · WS-6→Tasks 11-12 ✓. Data-safety explainer → Task 11 Step 1 ✓.

**Placeholder scan:** No "TBD/TODO". Frontend Tasks 7 Step 2 and the docs tasks describe edits to *existing* large files by exact anchor + concrete snippets rather than reproducing whole files — acceptable per "follow existing patterns"; every *new* file has complete code.

**Type/name consistency:** `ProductCategory(name, parent_id, is_active, tenant_id)` and `Product.category_id` are used identically across model (T4), migration (T4), router (T5), products wiring (T6), and frontend (T7). Endpoint paths `/api/product-categories` and `/api/admin/demo/seed` match between backend and frontend. `seed_all_demos()` (T2) matches the real function in `scripts/seed_demo.py`. Migration `down_revision = "520ea8c9ea33"` is the verified current head.

**Known assumptions to confirm at execution time:** (1) the auth test helper — reuse `backend/tests/conftest.py`'s fixture if it differs from the inline `_admin_headers`; (2) `products.py` list response shape (array vs `{items}`) — Task 6 Step 3 handles both.

---

## VERIFICATION (whole plan)

```bash
cd backend && PYTHONPATH=. uv run pytest -q          # full suite green incl. new tests
cd backend && PYTHONPATH=. uv run alembic upgrade head   # migration applies cleanly
cd frontend && npm run build                          # frontend compiles
```
**Definition of done:** a standalone install starts clean; Settings → "Load demo companies" populates the 5 demo logins; products support parent→sub categories with the 3rd level blocked; Quick Actions sit in the top toolbar; the script `update.*` command and desktop auto-update are wired; updating an existing install migrates the DB forward with data intact; all guides + README reflect the new reality.
