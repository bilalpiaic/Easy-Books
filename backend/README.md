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
| `PYTHONPATH=. uv run python -m scripts.seed_demo` | Seed all 5 demo tenants with 100 invoices, 100 bills, 70 payments, 25 customers/vendors, 3 bank accounts, 4 payment terms, 6 recurring templates |

## Structure

```
backend/
├── main.py              # FastAPI bootstrap — middleware + router mounts
├── models.py            # SQLModel tables (core)
├── models_telecom.py    # 23 tc_* tables for telecom_franchise
├── db.py                # Engine, create_all, seed 5 demo tenants; hierarchical default CoA (group skeleton + parented leaves; posting to leaves only)
├── auth.py              # JWT (HS256) + bcrypt
├── routers/             # 29 domain routers
│   ├── common.py        # Shared deps: SessionDep, CurrentUserDep, WriteUserDep, AdminUserDep
│   ├── auth.py          # signup, login, logout, /me, profile, accept-invite
│   ├── users.py         # team management (admin+): create/invite/role/activate
│   ├── invoices.py  bills.py  payments.py
│   ├── reports.py       # GL + report endpoints (see below)
│   ├── admin.py         # Demo-data seed/purge (admin+) — backs Settings → Sample/Demo Data
│   ├── product_categories.py  # ProductCategory CRUD — 2-level taxonomy (parent → sub-category)
│   ├── telecom_reports.py  manufacturing_reports.py
│   ├── telecom.py       # 40+ telecom franchise endpoints
│   └── …
├── services/
│   ├── posting.py       # THE only GL writer — enforces ∑Dr=∑Cr + all invariants
│   ├── account_tree.py  # Hierarchical roll-up engine for TB/BS/P&L (parent = own + Σ leaves)
│   ├── deferred.py      # Deferred-revenue origination (is_deferred → 2300 + schedules)
│   ├── inventory.py     # Weighted-Average cost + FIFO layer relief
│   ├── tracker_posting.py   # Telecom balanced JVs
│   ├── franchise_posting.py # Telecom mobile-money/postpaid/commission JVs
│   ├── fx.py            # FX rate lookup + inverse fallback
│   ├── money.py         # Decimal helpers, ROUND_HALF_EVEN
│   ├── csrf.py          # Double-submit CSRF middleware
│   └── idempotency.py   # Response-cache middleware
├── scripts/
│   └── seed_demo.py     # Idempotent seeder — 100 invoices/bills, 70 payments, 25 customers/vendors per tenant; spans 2 fiscal years, typed vouchers, deferred-revenue origination, multiple users
└── tests/
```

## Schema management

**Alembic migrations are the source of truth** (`backend/alembic/versions/`, revisions through 0019). `SQLModel.metadata.create_all()` still runs on every startup so a fresh checkout boots without a migration step, but all schema changes must go through Alembic:

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

## Key models and report endpoints

**`models.py`** includes `ProductCategory` — a 2-level taxonomy (parent category → sub-category). Deleting a category is blocked while sub-categories or products reference it.

**`routers/reports.py`** exposes:

| Endpoint | Notes |
|---|---|
| `GET /api/reports/ledger` | General Ledger — when `start`/`end` date params are supplied returns **Opening Balance** (net of all JEs before `start`) and **Closing Balance** (`opening + Σdebits − Σcredits`) per account |
| `GET /api/reports/product-ledger` | Per-product stock movement ledger |
| `GET /api/reports/inventory-performance` | Inventory performance summary |
| `GET /api/reports/customer-performance` | Customer revenue and payment performance |

## Environment variables

| Var | Default | Notes |
|---|---|---|
| `DATABASE_URL` | SQLite at `backend/database.db` | Set to `postgresql://…` in production |
| `JWT_SECRET_KEY` | Insecure dev default | **Required in production** (`openssl rand -hex 32`) |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS allow-list (comma-separated) |
| `SEED_ADMIN_EMAIL` | — | Creates an admin user on first boot |
| `SEED_ADMIN_PASSWORD` | — | Required if `SEED_ADMIN_EMAIL` is set |
| `SEED_COMPANY_NAME` | `My Company` | Default company name for the seeded tenant |
| `UPLOAD_ROOT` | `uploads` | Filesystem root for user avatars + attachments |

## API conventions

- All endpoints at `/api/*` (also mirrored at `/api/v1/*` for SDK consumers)
- DB session: `SessionDep = Annotated[Session, Depends(get_session)]`
- Auth: `CurrentUserDep` (any active user), `WriteUserDep` (accountant+), `AdminUserDep` (admin+)
- Swagger UI: `http://localhost:8000/docs`
