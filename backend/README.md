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
| `PYTHONPATH=. .venv/bin/python -m scripts.seed_demo` | Seed all 5 demo tenants with 50+ records per type |

## Structure

```
backend/
├── main.py              # FastAPI bootstrap — middleware + router mounts
├── models.py            # SQLModel tables (core)
├── models_telecom.py    # 23 tc_* tables for telecom_franchise
├── db.py                # Engine, create_all, seed 5 demo tenants
├── auth.py              # JWT (HS256) + bcrypt
├── routers/             # 29 domain routers
│   ├── common.py        # Shared deps: SessionDep, CurrentUserDep, WriteUserDep, AdminUserDep
│   ├── auth.py          # signup, login, logout, /me, profile, accept-invite
│   ├── users.py         # team management (admin+): create/invite/role/activate
│   ├── invoices.py  bills.py  payments.py
│   ├── reports.py  telecom_reports.py  manufacturing_reports.py
│   ├── telecom.py       # 40+ telecom franchise endpoints
│   └── …
├── services/
│   ├── posting.py       # THE only GL writer — enforces ∑Dr=∑Cr + all invariants
│   ├── inventory.py     # Weighted-Average cost + FIFO layer relief
│   ├── tracker_posting.py   # Telecom balanced JVs
│   ├── franchise_posting.py # Telecom mobile-money/postpaid/commission JVs
│   ├── fx.py            # FX rate lookup + inverse fallback
│   ├── money.py         # Decimal helpers, ROUND_HALF_EVEN
│   ├── csrf.py          # Double-submit CSRF middleware
│   └── idempotency.py   # Response-cache middleware
├── scripts/
│   └── seed_demo.py     # Idempotent seeder — 50+ per entity per tenant
└── tests/
```

## Schema management

There is **no Alembic**. `SQLModel.metadata.create_all()` runs on every startup and creates missing tables. It does **not** alter existing tables. For columns added to an existing table, either:

- Run `ALTER TABLE <table> ADD COLUMN <col> <type> DEFAULT <default>;` on the SQLite file
- Or delete `backend/database.db` to get a fresh seeded database

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
