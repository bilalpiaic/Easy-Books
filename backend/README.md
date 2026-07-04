# Easy-Books Backend

FastAPI + SQLModel + Python 3.11+. Talks to SQLite in dev and PostgreSQL in production.

## Quick start

```bash
cd backend

# Install dependencies (uv recommended; pip works too)
uv sync                        # or: python -m venv .venv && .venv/bin/pip install -r requirements.txt

# Start dev server (auto-reloads)
python main.py                 # → http://localhost:8000  (Swagger UI at /docs)
```

For one-shot dev (backend + frontend + demo seed together), use `./dev.sh` at the repo root.

## Commands

| Command | Description |
|---|---|
| `python main.py` | Dev server with hot-reload on port 8000 |
| `uv run pytest` | Run all tests |
| `uv run pytest -v` | Verbose |
| `uv run pytest tests/test_auth.py` | Single file |
| `uv run pytest -k test_name` | Single test |
| `PYTHONPATH=. uv run python -m scripts.seed_demo` | Seed all 7 demo tenants (one per business model, incl. PRA retail + hospital) with 50+ records per entity: invoices, bills, payments, typed vouchers, 2 fiscal years of data, deferred-revenue origination, multiple users per tenant |
| `PYTHONPATH=. uv run python -m scripts.autoseed_demo` | First-run demo loader — no-ops if any user exists or `SEED_DEMO=false` (used by installers) |
| `uv run alembic upgrade head` | Apply pending migrations |
| `uv run alembic heads` | Show current migration head |

## Structure

```
backend/
├── main.py              # FastAPI bootstrap — middleware, router mounts, /api/v1 alias, Stripe webhook
├── models.py            # SQLModel tables (core): CoA, invoices/bills, products, payroll+attendance,
│                        #   permissions, commissions, promo rules, deferred revenue, dashboard layout
├── models_telecom.py    # 23 tc_* tables for telecom_franchise
├── models_healthcare.py # 19 hc_* tables: patients, doctors, wards/beds, OPD/IPD, lab, procedures, store
├── db.py                # Engine, create_all, hierarchical default CoA (group skeleton + parented
│                        #   leaves; posting to leaves only), 7 demo tenants, MODULE_REGISTRY
│                        #   (installable modules) + MODULES_BY_MODEL defaults
├── auth.py              # JWT (HS256) + bcrypt
├── routers/             # 61 domain routers
│   ├── common.py        # Shared deps: SessionDep, CurrentUserDep, WriteUserDep, AdminUserDep
│   ├── auth.py          # signup, login, logout, /me, profile, accept-invite
│   ├── users.py         # team management (admin+): create/invite/role/activate
│   ├── permissions.py   # granular access control — 60-resource registry, per-user matrix, my-data-only
│   ├── invoices.py  bills.py  payments.py  credit_notes.py  debit_notes.py  advances.py
│   ├── customers.py  vendors.py            # CRUD + period statements (opening/closing balance)
│   ├── payroll.py  attendance.py           # employee/salary-structure CRUD, PayrollRun lifecycle
│   │                                       #   (draft→approve→post GL→void), biometric import
│   ├── commissions.py  promo_rules.py      # commission plans/ledger + promo discount rules
│   ├── healthcare.py  healthcare_reports.py  # OPD/IPD/lab/procedures/store + 7 report endpoints
│   ├── telecom.py  telecom_reports.py      # 40+ telecom franchise endpoints
│   ├── reports.py       # GL + hierarchical statements + dashboards (see below)
│   ├── report_builder.py  # dynamic report builder — whitelisted sources, saved reports, CSV/XLSX export
│   ├── search.py        # GET /api/search — universal search across 8 entity types
│   ├── ai_chat.py       # POST /api/ai/chat — AI Financial Assistant (Anthropic agent loop over
│   │                    #   7 read-only report tools; gated by ai_assistant module + ANTHROPIC_API_KEY)
│   ├── purchase_demands.py  # PD-YYYY-seq quantity-only requisitions; approve/cancel/close, self-approval blocked
│   ├── quotations.py    # VQ-YYYY-seq vendor quotations against an approved demand; freezes on CS approval
│   ├── comparatives.py  # CS-YYYY-seq comparison matrix + lowest-or-justify approval + convert-to-PO
│   ├── system_update.py # in-app update: GitHub commit check, pull+migrate+rebuild, changelog
│   ├── admin.py         # Demo-data seed/purge (admin+) — backs Settings → Sample/Demo Data
│   ├── product_categories.py  # ProductCategory CRUD — 2-level taxonomy (parent → sub-category)
│   ├── attachments.py   # Supabase-storage file uploads (avatars, document attachments)
│   └── …                # accounts, assets, budgets, purchase_orders, bom, grn, production_orders,
│                        #   rate_plans, exchange_rates, reconciliations, recurring, periods,
│                        #   deferred_revenue, analytic_accounts, pra, modules, settings, backup, …
├── services/
│   ├── posting.py       # THE only GL writer — enforces ∑Dr=∑Cr + all invariants
│   ├── account_tree.py  # Hierarchical roll-up engine for TB/BS/P&L (parent = own + Σ leaves)
│   ├── permissions.py   # perm_dep() dependency factory + effective-rights resolution + own-data filter
│   ├── deferred.py      # Deferred-revenue origination (is_deferred → 2300 + schedules)
│   ├── inventory.py     # Weighted-Average cost + FIFO layer relief
│   ├── report_engine.py # Pure query builder for the report builder (tenant-safe select())
│   ├── report_sources/  # Declarative data-source registry — the report-builder security boundary
│   ├── depreciation.py  # Asset depreciation schedules
│   ├── pdf.py  email.py # Document rendering + SMTP delivery
│   ├── healthcare_posting.py  tracker_posting.py  franchise_posting.py  # domain GL posting
│   ├── fx.py            # FX rate lookup + inverse fallback
│   ├── money.py         # Decimal helpers, ROUND_HALF_EVEN
│   ├── csrf.py          # Double-submit CSRF middleware
│   └── idempotency.py   # Response-cache middleware
├── scripts/
│   ├── seed_demo.py     # Idempotent rich seeder — 50+ records per entity per tenant
│   └── autoseed_demo.py # Guarded first-run loader for installers (skips if any user exists)
└── tests/
```

## Schema management

**Alembic migrations are the source of truth** (`backend/alembic/versions/`, 40+ revisions — current head `0029_purchase_demand_comparative`; confirm with `uv run alembic heads`). `SQLModel.metadata.create_all()` still runs on every startup so a fresh checkout boots without a migration step (disable with `SCHEMA_BOOTSTRAP=alembic`), but all schema changes must go through Alembic:

```bash
# Add a column or table
# 1. Update models.py
# 2. Generate the migration
uv run alembic revision --autogenerate -m "describe your change"
# 3. Apply it
uv run alembic upgrade head
```

**SQLite caveats:**
- Alembic cannot `ADD CONSTRAINT` via ALTER — strip auto-generated FK lines from migrations that alter existing tables (see migrations 0016/0017 for the pattern; app-level tenant checks enforce integrity)
- New-table migrations must guard with `bind.dialect.has_table(...)` so they coexist with `create_all()`

The standalone installers (`install-and-run.*`) and `run_packaged.py` run `alembic upgrade head` on every launch, so updating to a newer release migrates the existing database forward in place — existing data is preserved.

To reset to a fully seeded state, delete `backend/database.db`.

## Key report endpoints

**`routers/reports.py`** exposes:

| Endpoint | Notes |
|---|---|
| `GET /api/reports/ledger` | General Ledger — when `start`/`end` date params are supplied returns **Opening Balance** (net of all JEs before `start`) and **Closing Balance** (`opening + Σdebits − Σcredits`) per account |
| `GET /api/reports/trial-balance` | Hierarchical `{tree, totals}` — nested account tree rolled up via `services/account_tree.py`; comparison mode (`compare_start`/`compare_end`) stays flat |
| `GET /api/reports/balance-sheet` | Hierarchical `{assets, liabilities, equity, totals}` with synthetic current-year Retained Earnings line |
| `GET /api/reports/income-statement` | Hierarchical `{revenue, expenses, totals}` + `net_profit` |
| `GET /api/reports/dashboard/net-worth?months=N` | Monthly cumulative Assets / Liabilities / Net Worth series — powers the dashboard Net Worth Trend widget |
| `GET /api/reports/product-ledger` | Per-product stock movement ledger (each movement carries its resolved store location) |
| `GET /api/reports/product-coa` | Main→Sub→Item closing-stock valuation tree grouped by product category — backs the Products page Tree view |
| `GET /api/reports/inventory-performance` | Inventory performance summary |
| `GET /api/reports/customer-performance` | Customer revenue and payment performance |

Domain report routers add more: `healthcare_reports.py` (7 endpoints under `/api/healthcare/reports/`), `telecom_reports.py`, `manufacturing_reports.py`, and the dynamic `report_builder.py` (whitelisted sources, saved reports, formula-injection-safe CSV/XLSX export).

## Environment variables

| Var | Default | Notes |
|---|---|---|
| `DATABASE_URL` | SQLite at `backend/database.db` | Set to `postgresql://…` in production |
| `JWT_SECRET_KEY` | Insecure dev default | **Required in production** (`openssl rand -hex 32`) |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS allow-list (comma-separated) |
| `SEED_ADMIN_EMAIL` | — | Creates an admin user on first boot |
| `SEED_ADMIN_PASSWORD` | — | Required if `SEED_ADMIN_EMAIL` is set |
| `SEED_COMPANY_NAME` | `My Company` | Default company name for the seeded tenant |
| `SEED_DEMO` | `true` (installers) | `false` skips the first-run demo-data auto-load |
| `SCHEMA_BOOTSTRAP` | `create_all` | Set to `alembic` to skip startup `create_all()` (packaged/CI runs) |
| `UPLOAD_ROOT` | `uploads` | Filesystem root for user avatars + attachments |
| `MAX_UPLOAD_BYTES` | 25 MB | Attachment size limit |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_BUCKET` | — / — / `attachments` | Cloud file storage for attachments (unset → uploads disabled with a clear error) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `FROM_EMAIL` | — | Outbound email (invoice delivery, invites) |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | — | Invoice pay-links + payment webhook |
| `ANTHROPIC_API_KEY` | — | Enables the AI Financial Assistant (`POST /api/ai/chat`); unset → 503 with a clear message |

## API conventions

- All endpoints at `/api/*` (also mirrored at `/api/v1/*` for SDK consumers)
- DB session: `SessionDep = Annotated[Session, Depends(get_session)]`
- Auth: `CurrentUserDep` (any active user), `WriteUserDep` (accountant+), `AdminUserDep` (admin+)
- Granular rights: `perm_dep(resource_key, level)` from `services/permissions.py` — injected into 35+ routers; merges role defaults with per-user `UserPermission` overrides
- Swagger UI: `http://localhost:8000/docs`
