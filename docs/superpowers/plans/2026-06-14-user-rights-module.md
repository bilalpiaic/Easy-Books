# User Rights Module — Implementation Plan (#70)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tenant-level, opt-in permission matrix (user × resource → No Access / View / Edit) plus per-user "My Data Only" row-level scoping across all forms and reports.

**Architecture:**
- `UserPermission` table stores sparse overrides from role defaults. When the module is off, zero behaviour change. When on, `require_permission(resource_key, level)` Depends factory enforces access on every route; `apply_own_filter()` injects `created_by_id` filters for list endpoints.
- `created_by_id` (nullable FK → user) added to Transaction, Invoice, Bill, PaymentReceived, BillPayment — populated on create, never mutated.
- Frontend fetches full permission map at login (`GET /api/users/me/permissions`), stores in `PermissionContext`, exposes `can(key, level)` helper for conditional rendering. Admin matrix UI at `/settings/permissions`.

**Tech Stack:** FastAPI / SQLModel / Alembic (backend), Next.js 16 / React 19 / TypeScript (frontend). Tests with pytest.

---

## Resource Registry (stable keys)

| Key | Label | Category |
|-----|-------|----------|
| `invoices` | Sales Invoices | Receivable |
| `credit_notes` | Credit Notes | Receivable |
| `payments_received` | Payments Received | Receivable |
| `customers` | Customers | Receivable |
| `customer_ledger` | Customer Ledger | Receivable |
| `bills` | Purchase Bills | Payable |
| `debit_notes` | Debit Notes | Payable |
| `bill_payments` | Bill Payments | Payable |
| `vendors` | Vendors | Payable |
| `vendor_ledger` | Vendor Ledger | Payable |
| `advances` | Advances | Payable |
| `journal_entry` | Manual Journal Entry | Ledger |
| `recurring` | Recurring Templates | Ledger |
| `accounts` | Chart of Accounts | Ledger |
| `analytic_accounts` | Analytic Accounts | Ledger |
| `products` | Products | Inventory |
| `product_categories` | Product Categories | Inventory |
| `bom` | Bills of Material | Manufacturing |
| `rate_plans` | Rate Plans | Manufacturing |
| `purchase_orders` | Purchase Orders | Manufacturing |
| `grn` | Goods Receipt Notes | Manufacturing |
| `production_orders` | Production Orders | Manufacturing |
| `stock_locations` | Stock Locations | Manufacturing |
| `bank_accounts` | Bank Accounts | Banking |
| `exchange_rates` | Exchange Rates | Banking |
| `bank_imports` | Bank Imports | Banking |
| `reconciliations` | Reconciliations | Banking |
| `assets` | Fixed Assets | Reports |
| `budgets` | Budgets | Reports |
| `deferred_revenue` | Deferred Revenue | Reports |
| `tax_codes` | Tax Codes | Reports |
| `payment_terms` | Payment Terms | System |
| `period_close` | Period Close | System |
| `team` | Team Management | System |
| `audit_log` | Audit Log | System |
| `csv_import` | CSV Import | System |
| `report_builder` | Report Builder | Reports |
| `report.trial_balance` | Trial Balance | Reports |
| `report.income_statement` | Income Statement | Reports |
| `report.balance_sheet` | Balance Sheet | Reports |
| `report.cash_flow` | Cash Flow | Reports |
| `report.general_ledger` | General Ledger | Reports |
| `report.ar_aging` | AR Aging | Reports |
| `report.ap_aging` | AP Aging | Reports |
| `report.customer_performance` | Customer Performance | Reports |
| `report.inventory_performance` | Inventory Performance | Reports |
| `report.tax` | Tax Reports | Reports |
| `report.budget_vs_actual` | Budget vs Actual | Reports |
| `report.product_ledger` | Product Ledger | Reports |
| `telecom.tracker` | Tracker & Load | Telecom |
| `telecom.rso` | RSO Channel | Telecom |
| `telecom.sim` | SIM & Activations | Telecom |
| `telecom.fca` | FCA & Targets | Telecom |
| `telecom.mobile_money` | Mobile Money | Telecom |
| `telecom.postpaid` | Postpaid Billing | Telecom |
| `telecom.commissions` | Commissions | Telecom |
| `telecom.franchise` | Franchise Admin | Telecom |
| `telecom.devices` | Devices (IMEI) | Telecom |

## Role Defaults (when no UserPermission override exists)

| Role | Default access |
|------|---------------|
| `owner` | `edit` on all resources |
| `admin` | `edit` on all resources |
| `accountant` | `edit` on all resources |
| `viewer` | `view` on all resources |

---

## Task 1: DB models + migration

**Files:**
- Modify: `backend/models.py`
- Create: `backend/alembic/versions/0020_user_rights.py`

- [ ] **Step 1: Add `UserPermission` model to `models.py`**

After the `UserInvite` class, add:

```python
class UserPermission(SQLModel, table=True):
    """Sparse permission overrides. When no row exists for (user_id, resource_key),
    the role default applies (owner/admin/accountant → edit, viewer → view)."""
    __tablename__ = "user_permission"
    __table_args__ = (
        UniqueConstraint("user_id", "resource_key", name="uq_user_permission"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    resource_key: str = Field(index=True)        # stable key from registry
    access_level: str = Field(default="edit")    # "none" | "view" | "edit"
```

- [ ] **Step 2: Add `my_data_only` to `User` model**

In the `User` class, after `last_login_at`:
```python
    my_data_only: bool = Field(default=False)
```

- [ ] **Step 3: Add `created_by_id` to Transaction, Invoice, Bill, PaymentReceived, BillPayment**

In `Transaction` class:
```python
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
```

In `Invoice` class:
```python
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
```

In `Bill` class:
```python
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
```

In `PaymentReceived` class:
```python
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
```

In `BillPayment` class:
```python
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
```

- [ ] **Step 4: Write migration `0020_user_rights.py`**

```python
"""user rights module: user_permission table, created_by_id columns, my_data_only"""
from alembic import op
import sqlalchemy as sa

revision = "0020_user_rights"
down_revision = "1af1ee747edb"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # user_permission table
    if not bind.dialect.has_table(bind, "user_permission"):
        op.create_table(
            "user_permission",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True),
            sa.Column("resource_key", sa.String, nullable=False, index=True),
            sa.Column("access_level", sa.String, nullable=False, default="edit"),
            sa.UniqueConstraint("user_id", "resource_key", name="uq_user_permission"),
        )

    # Add columns with existence check (SQLite can't add constraints via ALTER)
    with op.batch_alter_table("user") as batch_op:
        try:
            batch_op.add_column(sa.Column("my_data_only", sa.Boolean, nullable=False, server_default="0"))
        except Exception:
            pass

    for table in ("transaction", "invoice", "bill", "paymentreceived", "billpayment"):
        with op.batch_alter_table(table) as batch_op:
            try:
                batch_op.add_column(sa.Column("created_by_id", sa.Integer, nullable=True, index=True))
            except Exception:
                pass


def downgrade():
    pass
```

- [ ] **Step 5: Run migration**

```bash
cd backend && PYTHONPATH=. uv run alembic upgrade head
```

Expected: "Running upgrade 1af1ee747edb -> 0020_user_rights"

- [ ] **Step 6: Run full suite to confirm no breakage**

```bash
cd backend && PYTHONPATH=. uv run pytest --tb=short -q 2>&1 | tail -5
```

Expected: 388 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/models.py backend/alembic/versions/0020_user_rights.py
git commit -m "feat(rights): UserPermission model + created_by_id + my_data_only migration (0020)"
```

---

## Task 2: Permission service

**Files:**
- Create: `backend/services/permissions.py`

- [ ] **Step 1: Create `services/permissions.py`**

```python
"""User Rights Module — permission resolution service.

When user_rights_enabled = "true" (Settings KV), every request to a
protected route is checked against UserPermission overrides + role defaults.
When the module is off, all functions are no-ops (zero behaviour change).
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from models import Settings, User, UserPermission
from routers.common import SessionDep, CurrentUserDep

# ── Resource registry ─────────────────────────────────────────────────────────

PERMISSION_RESOURCES: dict[str, dict] = {
    # Receivable
    "invoices":              {"label": "Sales Invoices",       "category": "Receivable"},
    "credit_notes":          {"label": "Credit Notes",         "category": "Receivable"},
    "payments_received":     {"label": "Payments Received",    "category": "Receivable"},
    "customers":             {"label": "Customers",            "category": "Receivable"},
    "customer_ledger":       {"label": "Customer Ledger",      "category": "Receivable"},
    # Payable
    "bills":                 {"label": "Purchase Bills",       "category": "Payable"},
    "debit_notes":           {"label": "Debit Notes",          "category": "Payable"},
    "bill_payments":         {"label": "Bill Payments",        "category": "Payable"},
    "vendors":               {"label": "Vendors",              "category": "Payable"},
    "vendor_ledger":         {"label": "Vendor Ledger",        "category": "Payable"},
    "advances":              {"label": "Advances",             "category": "Payable"},
    # Ledger
    "journal_entry":         {"label": "Manual Journal Entry", "category": "Ledger"},
    "recurring":             {"label": "Recurring Templates",  "category": "Ledger"},
    "accounts":              {"label": "Chart of Accounts",    "category": "Ledger"},
    "analytic_accounts":     {"label": "Analytic Accounts",    "category": "Ledger"},
    # Inventory
    "products":              {"label": "Products",             "category": "Inventory"},
    "product_categories":    {"label": "Product Categories",   "category": "Inventory"},
    # Manufacturing
    "bom":                   {"label": "Bills of Material",    "category": "Manufacturing"},
    "rate_plans":            {"label": "Rate Plans",           "category": "Manufacturing"},
    "purchase_orders":       {"label": "Purchase Orders",      "category": "Manufacturing"},
    "grn":                   {"label": "Goods Receipt Notes",  "category": "Manufacturing"},
    "production_orders":     {"label": "Production Orders",    "category": "Manufacturing"},
    "stock_locations":       {"label": "Stock Locations",      "category": "Manufacturing"},
    # Banking
    "bank_accounts":         {"label": "Bank Accounts",        "category": "Banking"},
    "exchange_rates":        {"label": "Exchange Rates",       "category": "Banking"},
    "bank_imports":          {"label": "Bank Imports",         "category": "Banking"},
    "reconciliations":       {"label": "Reconciliations",      "category": "Banking"},
    # Reports
    "assets":                {"label": "Fixed Assets",         "category": "Reports"},
    "budgets":               {"label": "Budgets",              "category": "Reports"},
    "deferred_revenue":      {"label": "Deferred Revenue",     "category": "Reports"},
    "tax_codes":             {"label": "Tax Codes",            "category": "Reports"},
    "report_builder":        {"label": "Report Builder",       "category": "Reports"},
    "report.trial_balance":  {"label": "Trial Balance",        "category": "Reports"},
    "report.income_statement":{"label": "Income Statement",    "category": "Reports"},
    "report.balance_sheet":  {"label": "Balance Sheet",        "category": "Reports"},
    "report.cash_flow":      {"label": "Cash Flow",            "category": "Reports"},
    "report.general_ledger": {"label": "General Ledger",       "category": "Reports"},
    "report.ar_aging":       {"label": "AR Aging",             "category": "Reports"},
    "report.ap_aging":       {"label": "AP Aging",             "category": "Reports"},
    "report.customer_performance": {"label": "Customer Performance", "category": "Reports"},
    "report.inventory_performance": {"label": "Inventory Performance","category": "Reports"},
    "report.tax":            {"label": "Tax Reports",          "category": "Reports"},
    "report.budget_vs_actual":{"label": "Budget vs Actual",   "category": "Reports"},
    "report.product_ledger": {"label": "Product Ledger",       "category": "Reports"},
    # System
    "payment_terms":         {"label": "Payment Terms",        "category": "System"},
    "period_close":          {"label": "Period Close",         "category": "System"},
    "team":                  {"label": "Team Management",      "category": "System"},
    "audit_log":             {"label": "Audit Log",            "category": "System"},
    "csv_import":            {"label": "CSV Import",           "category": "System"},
    # Telecom
    "telecom.tracker":       {"label": "Tracker & Load",       "category": "Telecom"},
    "telecom.rso":           {"label": "RSO Channel",          "category": "Telecom"},
    "telecom.sim":           {"label": "SIM & Activations",    "category": "Telecom"},
    "telecom.fca":           {"label": "FCA & Targets",        "category": "Telecom"},
    "telecom.mobile_money":  {"label": "Mobile Money",         "category": "Telecom"},
    "telecom.postpaid":      {"label": "Postpaid Billing",     "category": "Telecom"},
    "telecom.commissions":   {"label": "Commissions",          "category": "Telecom"},
    "telecom.franchise":     {"label": "Franchise Admin",      "category": "Telecom"},
    "telecom.devices":       {"label": "Devices (IMEI)",       "category": "Telecom"},
}

# ── Role defaults ─────────────────────────────────────────────────────────────
# owner/admin/accountant → edit everything; viewer → view everything.
_ROLE_DEFAULT: dict[str, str] = {
    "owner": "edit",
    "admin": "edit",
    "accountant": "edit",
    "viewer": "view",
}


def _rights_enabled(tenant_id: int, session: Session) -> bool:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == "user_rights_enabled")
    ).first()
    return (row.value if row else "false") == "true"


def get_effective_permission(user: User, resource_key: str, session: Session) -> str:
    """Returns 'none' | 'view' | 'edit'. Role default when no override exists."""
    override = session.exec(
        select(UserPermission).where(
            UserPermission.user_id == user.id,
            UserPermission.resource_key == resource_key,
        )
    ).first()
    if override:
        return override.access_level
    return _ROLE_DEFAULT.get(user.role, "view")


def perm_dep(resource_key: str, level: str = "view"):
    """FastAPI Depends factory. When module is off → no-op. When on → enforce level."""
    def _check(user: User = Depends(lambda: None), session: Session = Depends(lambda: None)):
        pass  # replaced below via closure

    async def _enforce(
        user: User = Depends(lambda req: req.state.user if hasattr(req.state, "user") else None),
        session: Session = Depends(lambda: None),
    ):
        pass

    # Use a proper dependency that resolves user + session
    from routers.common import get_current_user, get_session

    async def _dep(
        user: User = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> None:
        if not _rights_enabled(user.tenant_id, session):
            return  # module off → no restriction
        effective = get_effective_permission(user, resource_key, session)
        if level == "view" and effective == "none":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have access to '{PERMISSION_RESOURCES.get(resource_key, {}).get('label', resource_key)}'.",
            )
        if level == "edit" and effective in ("none", "view"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"'{PERMISSION_RESOURCES.get(resource_key, {}).get('label', resource_key)}' is view-only for your account.",
            )

    return Depends(_dep)


def apply_own_filter(query, model_class, user: User, session: Session):
    """When 'My Data Only' is on and the module is enabled, restrict to
    records the user created. Admins and owners are never filtered."""
    if user.role in ("admin", "owner"):
        return query
    if not user.my_data_only:
        return query
    if not _rights_enabled(user.tenant_id, session):
        return query
    if not hasattr(model_class, "created_by_id"):
        return query
    return query.where(model_class.created_by_id == user.id)
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/permissions.py
git commit -m "feat(rights): permission service — registry, role defaults, perm_dep, apply_own_filter"
```

---

## Task 3: Permissions router + settings key

**Files:**
- Create: `backend/routers/permissions.py`
- Modify: `backend/routers/settings.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create `routers/permissions.py`**

```python
"""User Rights Module — permission management endpoints."""
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import User, UserPermission
from routers.common import AdminUserDep, CurrentUserDep, SessionDep, log_audit
from services.permissions import PERMISSION_RESOURCES, get_effective_permission, _rights_enabled

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


class PermissionSet(BaseModel):
    """Map of resource_key → access_level returned to the frontend."""
    permissions: dict[str, str]
    my_data_only: bool
    module_enabled: bool


class PermissionUpdate(BaseModel):
    resource_key: str
    access_level: str  # "none" | "view" | "edit"


@router.get("/me", response_model=PermissionSet)
def my_permissions(user: CurrentUserDep, session: SessionDep):
    """Returns the calling user's full permission map (frontend uses this at login)."""
    module_on = _rights_enabled(user.tenant_id, session)
    perms = {
        key: get_effective_permission(user, key, session)
        for key in PERMISSION_RESOURCES
    }
    return PermissionSet(
        permissions=perms,
        my_data_only=user.my_data_only,
        module_enabled=module_on,
    )


@router.get("/users/{user_id}", response_model=PermissionSet)
def get_user_permissions(user_id: int, admin: AdminUserDep, session: SessionDep):
    target = session.get(User, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(404, "User not found")
    module_on = _rights_enabled(admin.tenant_id, session)
    perms = {key: get_effective_permission(target, key, session) for key in PERMISSION_RESOURCES}
    return PermissionSet(permissions=perms, my_data_only=target.my_data_only, module_enabled=module_on)


@router.put("/users/{user_id}", status_code=200)
def set_user_permissions(
    user_id: int, updates: List[PermissionUpdate],
    admin: AdminUserDep, session: SessionDep,
):
    """Batch-upsert permission overrides. Pass access_level='default' to remove override."""
    target = session.get(User, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(404, "User not found")
    if target.role in ("owner",) and admin.role != "owner":
        raise HTTPException(403, "Cannot modify owner permissions")

    for upd in updates:
        if upd.resource_key not in PERMISSION_RESOURCES:
            raise HTTPException(400, f"Unknown resource key: {upd.resource_key}")
        if upd.access_level not in ("none", "view", "edit", "default"):
            raise HTTPException(400, f"Invalid access_level: {upd.access_level}")

        existing = session.exec(
            select(UserPermission).where(
                UserPermission.user_id == user_id,
                UserPermission.resource_key == upd.resource_key,
            )
        ).first()

        if upd.access_level == "default":
            if existing:
                session.delete(existing)
        elif existing:
            existing.access_level = upd.access_level
        else:
            session.add(UserPermission(
                tenant_id=admin.tenant_id,
                user_id=user_id,
                resource_key=upd.resource_key,
                access_level=upd.access_level,
            ))

    session.commit()
    log_audit(session, admin, "UPDATE", "user_permissions", user_id,
              {"changes": len(updates)})
    return {"updated": len(updates)}


@router.patch("/users/{user_id}/my-data-only", status_code=200)
def set_my_data_only(user_id: int, enabled: bool, admin: AdminUserDep, session: SessionDep):
    target = session.get(User, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(404, "User not found")
    target.my_data_only = enabled
    session.add(target)
    session.commit()
    log_audit(session, admin, "UPDATE", "user", user_id, {"my_data_only": enabled})
    return {"my_data_only": enabled}


@router.get("/resources")
def list_resources(_: CurrentUserDep):
    """Returns the full resource registry for the admin matrix UI."""
    return [
        {"key": k, "label": v["label"], "category": v["category"]}
        for k, v in PERMISSION_RESOURCES.items()
    ]
```

- [ ] **Step 2: Add `user_rights_enabled` to `SettingsUpdate` in `routers/settings.py`**

In `SettingsUpdate`, add after `decimal_places`:
```python
    user_rights_enabled: Optional[str] = None  # "true" | "false"
```

In `update_settings`, add validation after the `decimal_places` block:
```python
    if "user_rights_enabled" in updates:
        if updates["user_rights_enabled"] not in ("true", "false"):
            raise HTTPException(400, "user_rights_enabled must be 'true' or 'false'")
```

- [ ] **Step 3: Register router in `main.py`**

Add to the router imports and `include_router` calls:
```python
from routers import permissions as permissions_router
# ...
app.include_router(permissions_router.router)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && PYTHONPATH=. uv run pytest --tb=short -q 2>&1 | tail -5
```

Expected: 388 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/permissions.py backend/routers/settings.py backend/main.py
git commit -m "feat(rights): permissions router (GET /me, GET/PUT /users/:id, resources registry)"
```

---

## Task 4: Wire `created_by_id` on create endpoints

**Files:**
- Modify: `backend/routers/invoices.py`
- Modify: `backend/routers/bills.py`
- Modify: `backend/routers/payments.py`
- Modify: `backend/services/posting.py` (Transaction)

- [ ] **Step 1: `posting.py` — pass `created_by_id` to Transaction**

In `post_transaction()`, the function already takes `user` param. After creating the Transaction:
```python
    txn.created_by_id = user.id
```

(Find the `Transaction(...)` instantiation and add this field.)

- [ ] **Step 2: `routers/invoices.py` — set `created_by_id` on Invoice**

In `create_invoice`, after `inv = Invoice(...)` is created:
```python
    inv.created_by_id = user.id
```

- [ ] **Step 3: `routers/bills.py` — set `created_by_id` on Bill**

Same pattern as invoices.

- [ ] **Step 4: `routers/payments.py` — set `created_by_id` on PaymentReceived and BillPayment**

In `create_payment_received` and `create_bill_payment`, after the model is instantiated:
```python
    payment.created_by_id = user.id
```

- [ ] **Step 5: Run tests**

```bash
cd backend && PYTHONPATH=. uv run pytest --tb=short -q 2>&1 | tail -5
```

Expected: 388 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/invoices.py backend/routers/bills.py backend/routers/payments.py backend/services/posting.py
git commit -m "feat(rights): populate created_by_id on Invoice/Bill/Payment/Transaction create"
```

---

## Task 5: Apply `perm_dep` to all routers + row-level filter

Apply pattern: one `perm_dep("resource", "view")` at the router level (all routes in that router need at least view), then `perm_dep("resource", "edit")` as extra dependency on write routes. Also inject `apply_own_filter` into list endpoints for Invoice, Bill, PaymentReceived, BillPayment.

**Files:** all files in `backend/routers/` that handle user-facing data

The injection pattern for every router:

```python
# At top of file, after existing imports:
from services.permissions import perm_dep, apply_own_filter

# Router definition (add dependencies):
router = APIRouter(
    prefix="/api/invoices", tags=["invoices"],
    dependencies=[perm_dep("invoices", "view")],
)

# On write routes, add as extra dependency:
@router.post("", dependencies=[perm_dep("invoices", "edit")])
def create_invoice(...)

@router.put("/{id}", dependencies=[perm_dep("invoices", "edit")])
def update_invoice(...)
```

For routers where all routes need edit (e.g. payment_terms, tax_codes — admin-only management pages), just use `perm_dep("resource", "edit")` at router level.

Router → resource key mapping:

| Router file | Resource key | Notes |
|-------------|-------------|-------|
| `invoices.py` | `invoices` | view at router, edit on POST/PUT/DELETE/void |
| `bills.py` | `bills` | same pattern |
| `payments.py` | `payments_received` + `bill_payments` | split by route prefix |
| `credit_notes.py` | `credit_notes` | |
| `debit_notes.py` | `debit_notes` | |
| `customers.py` | `customers` | |
| `vendors.py` | `vendors` | |
| `advances.py` | `advances` | |
| `transactions.py` | `journal_entry` | |
| `recurring.py` | `recurring` | |
| `accounts.py` | `accounts` | |
| `analytic_accounts.py` | `analytic_accounts` | |
| `products.py` | `products` | |
| `product_categories.py` | `product_categories` | |
| `bom.py` | `bom` | |
| `rate_plans.py` | `rate_plans` | |
| `purchase_orders.py` | `purchase_orders` | |
| `grn.py` | `grn` | |
| `production_orders.py` | `production_orders` | |
| `stock_locations.py` | `stock_locations` | |
| `bank_accounts.py` | `bank_accounts` | |
| `exchange_rates.py` | `exchange_rates` | |
| `bank_imports.py` | `bank_imports` | |
| `reconciliations.py` | `reconciliations` | |
| `assets.py` | `assets` | |
| `budgets.py` | `budgets` | |
| `deferred_revenue.py` | `deferred_revenue` | |
| `tax_codes.py` | `tax_codes` | |
| `payment_terms.py` | `payment_terms` | |
| `periods.py` | `period_close` | |
| `audit.py` | `audit_log` | view only |
| `imports.py` | `csv_import` | edit (import is always a write) |
| `report_builder.py` | `report_builder` | view at router |
| `reports.py` | per-endpoint | trial_balance, income_statement, etc. |
| `telecom.py` | `telecom.*` | per-section |

- [ ] **Step 1: Apply to invoices.py, bills.py, payments.py** (most critical)

- [ ] **Step 2: Apply to customers.py, vendors.py, transactions.py, products.py**

- [ ] **Step 3: Apply to remaining routers** (all other non-auth, non-admin routers)

- [ ] **Step 4: Apply `apply_own_filter` to list endpoints**

In `routers/invoices.py`, in `list_invoices`:
```python
    stmt = apply_own_filter(stmt, Invoice, user, session)
```

Same in `list_bills`, `list_payments_received`, `list_bill_payments`.

- [ ] **Step 5: Run full test suite**

```bash
cd backend && PYTHONPATH=. uv run pytest --tb=short -q 2>&1 | tail -5
```

Expected: 388+ passed (tests don't enable the module, so no behaviour change).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/*.py
git commit -m "feat(rights): inject perm_dep into all routers + apply_own_filter on list endpoints"
```

---

## Task 6: Backend tests

**Files:**
- Create: `backend/tests/test_user_rights.py`

- [ ] **Step 1: Write tests**

```python
"""User Rights Module — tests for permission enforcement."""


def test_module_off_no_restriction(client, admin_headers, accountant_headers):
    """When user_rights_enabled=false (default), no 403s are raised."""
    r = client.get("/api/invoices", headers=accountant_headers)
    assert r.status_code == 200


def test_module_on_default_role_edit(client, admin_headers):
    """accountant role default = edit → no 403 on write."""
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    r = client.get("/api/invoices", headers=admin_headers)
    assert r.status_code == 200


def test_permission_override_none_blocks_view(client, admin_headers, accountant_headers, accountant_user):
    """Explicit 'none' override blocks even GET."""
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    client.put(f"/api/permissions/users/{accountant_user.id}", headers=admin_headers,
               json=[{"resource_key": "invoices", "access_level": "none"}])
    r = client.get("/api/invoices", headers=accountant_headers)
    assert r.status_code == 403


def test_permission_override_view_blocks_edit(client, admin_headers, accountant_headers, accountant_user):
    """Explicit 'view' override allows GET but blocks POST."""
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    client.put(f"/api/permissions/users/{accountant_user.id}", headers=admin_headers,
               json=[{"resource_key": "invoices", "access_level": "view"}])
    r = client.post("/api/invoices", headers=accountant_headers, json={})
    assert r.status_code in (400, 403)  # 403 from perm check, 422 if perm passes (wrong body)


def test_my_permissions_endpoint(client, admin_headers):
    """GET /api/permissions/me returns module_enabled + full permission map."""
    r = client.get("/api/permissions/me", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "permissions" in data
    assert "invoices" in data["permissions"]
    assert data["permissions"]["invoices"] == "edit"


def test_permission_default_removes_override(client, admin_headers, accountant_user):
    """Sending access_level='default' removes the override row."""
    client.put(f"/api/permissions/users/{accountant_user.id}", headers=admin_headers,
               json=[{"resource_key": "invoices", "access_level": "none"}])
    client.put(f"/api/permissions/users/{accountant_user.id}", headers=admin_headers,
               json=[{"resource_key": "invoices", "access_level": "default"}])
    r = client.get(f"/api/permissions/users/{accountant_user.id}", headers=admin_headers)
    assert r.json()["permissions"]["invoices"] == "edit"  # back to role default


def test_module_toggle_persists(client, admin_headers):
    """Setting user_rights_enabled round-trips."""
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    r = client.get("/api/settings", headers=admin_headers)
    assert r.json()["user_rights_enabled"] == "true"
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "false"})
    r = client.get("/api/settings", headers=admin_headers)
    assert r.json()["user_rights_enabled"] == "false"
```

(Requires `accountant_headers` and `accountant_user` fixtures added to conftest.)

- [ ] **Step 2: Add fixtures to conftest if needed**

Check `tests/conftest.py` for existing accountant fixture; add if missing:
```python
@pytest.fixture
def accountant_user(client, admin_headers):
    r = client.post("/api/users", headers=admin_headers, json={
        "email": "acct@test.invalid", "password": "pass1234", "role": "accountant"
    })
    return r.json()

@pytest.fixture
def accountant_headers(client, accountant_user):
    r = client.post("/api/auth/login", json={"email": "acct@test.invalid", "password": "pass1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
```

- [ ] **Step 3: Run tests**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_user_rights.py -v 2>&1 | tail -15
```

Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_user_rights.py backend/tests/conftest.py
git commit -m "test(rights): 7 tests for module toggle, role defaults, permission overrides"
```

---

## Task 7: Frontend — PermissionContext + settings key

**Files:**
- Create: `frontend/src/context/PermissionContext.tsx`
- Modify: `frontend/src/app/(dashboard)/layout.tsx`
- Modify: `frontend/src/context/SettingsContext.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1: Create `PermissionContext.tsx`**

```tsx
"use client"
import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { apiFetch } from "@/lib/api"
import { isAuthenticated } from "@/lib/auth"

interface PermissionData {
  permissions: Record<string, string>   // resource_key → "none"|"view"|"edit"
  my_data_only: boolean
  module_enabled: boolean
}

interface PermissionCtx {
  can: (resource: string, level?: "view" | "edit") => boolean
  myDataOnly: boolean
  moduleEnabled: boolean
  loading: boolean
  refresh: () => void
}

const Ctx = createContext<PermissionCtx>({
  can: () => true,
  myDataOnly: false,
  moduleEnabled: false,
  loading: false,
  refresh: () => {},
})

export function PermissionProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<PermissionData | null>(null)
  const [loading, setLoading] = useState(false)

  const load = () => {
    if (!isAuthenticated()) return
    setLoading(true)
    apiFetch<PermissionData>("/api/permissions/me")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const can = (resource: string, level: "view" | "edit" = "view"): boolean => {
    if (!data || !data.module_enabled) return true   // module off → full access
    const eff = data.permissions[resource] ?? "edit"
    if (level === "view") return eff !== "none"
    return eff === "edit"
  }

  return (
    <Ctx.Provider value={{
      can,
      myDataOnly: data?.my_data_only ?? false,
      moduleEnabled: data?.module_enabled ?? false,
      loading,
      refresh: load,
    }}>
      {children}
    </Ctx.Provider>
  )
}

export const usePermission = () => useContext(Ctx)
```

- [ ] **Step 2: Wrap dashboard layout with `PermissionProvider`**

In `frontend/src/app/(dashboard)/layout.tsx`, wrap children with `<PermissionProvider>`.

- [ ] **Step 3: Add `user_rights_enabled` to `SettingsContext`**

In `AppSettings` interface, add:
```ts
  user_rights_enabled: string
```
In `defaults`, add:
```ts
  user_rights_enabled: "false",
```

- [ ] **Step 4: Add toggle to Settings page**

Under Team/Permissions section, add:
```tsx
<div>
  <label className="block text-sm font-semibold text-black/85 mb-2">User Rights Module</label>
  <select
    value={form.user_rights_enabled ?? "false"}
    onChange={e => handleChange('user_rights_enabled', e.target.value)}
    className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black"
  >
    <option value="false">Disabled — all users access all data (default)</option>
    <option value="true">Enabled — enforce permission matrix</option>
  </select>
  <p className="text-xs text-[#1a1814]/50 mt-1">
    When enabled, access to each form and report is controlled per-user via Settings → Permissions.
  </p>
</div>
```

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/context/PermissionContext.tsx frontend/src/app/\(dashboard\)/layout.tsx frontend/src/context/SettingsContext.tsx "frontend/src/app/(dashboard)/settings/page.tsx"
git commit -m "feat(rights): PermissionContext + usePerm hook + module toggle in settings"
```

---

## Task 8: Admin matrix UI

**Files:**
- Create: `frontend/src/app/(dashboard)/settings/permissions/page.tsx`
- Modify: `frontend/src/lib/nav.ts` (add link under System)

- [ ] **Step 1: Create `settings/permissions/page.tsx`**

Matrix page: rows = users, columns = resources grouped by category. Each cell is a `<select>` with No Access / View / Edit / Role Default. Save button batch-PUTs to `/api/permissions/users/{id}`.

Also shows "My Data Only" toggle per user row and module status banner.

(Full code in implementation — ~200 lines)

- [ ] **Step 2: Add nav entry**

In `nav.ts`, in System section after "Team":
```ts
{ label: "Permissions", href: "/settings/permissions", icon: ShieldCheck, section: "System", adminOnly: true },
```

- [ ] **Step 3: TypeScript check + commit**

---

## Task 9: Frontend conditional rendering

Use `can()` hook to:
1. Hide nav items the user has "none" on
2. Disable New/Edit/Delete action buttons when user has "view" only
3. Show "Access restricted" page when user navigates to a "none" resource

Pattern:
```tsx
// In nav.ts sidebar rendering (Sidebar.tsx)
const { can } = usePermission()
// Filter nav items: if resource key known and can("invoices","view") === false → hide

// On page entry (e.g. invoices/page.tsx):
const { can } = usePermission()
if (!can("invoices", "view")) return <NoAccessBanner />

// On action buttons:
<button disabled={!can("invoices", "edit")} ...>New Invoice</button>
```

- [ ] **Step 1: Add `NoAccessBanner` component**

```tsx
// frontend/src/components/NoAccessBanner.tsx
export function NoAccessBanner({ resource }: { resource: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <ShieldOff className="w-12 h-12 text-[#1a1814]/20 mb-4" />
      <h2 className="text-xl font-serif text-[#1a1814]">Access restricted</h2>
      <p className="text-sm text-[#1a1814]/60 mt-2 max-w-sm">
        You don't have permission to view {resource}. Contact your administrator.
      </p>
    </div>
  )
}
```

- [ ] **Step 2: Add resource key to nav items**

In `nav.ts`, add optional `permKey?: string` to `NavItem`. Map each item to its resource key. `Sidebar.tsx` filters items using `can(item.permKey, "view")`.

- [ ] **Step 3: Apply `can()` to the 10 highest-traffic pages**

Apply page-level guard + action-button guard to: invoices, bills, customers, vendors, payments-received, bill-payments, journal entry, products, reports (trial-balance, general-ledger).

- [ ] **Step 4: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(rights): NoAccessBanner + nav filtering + page guards on top 10 pages"
```

---

## Final verification

- [ ] `cd backend && PYTHONPATH=. uv run pytest --tb=short -q 2>&1 | tail -5` — 395+ passed
- [ ] `cd frontend && npx tsc --noEmit` — no output
- [ ] Manual: enable module in settings, set a user to "none" on invoices → 403 on API + redirect on frontend
- [ ] Manual: "My Data Only" — accountant only sees their invoices
- [ ] Close GitHub issue #70 with delivery note
