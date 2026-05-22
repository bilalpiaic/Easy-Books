# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Easy-Books** is a SaaS double-entry bookkeeping application for SMEs. It is a **monorepo with two parallel implementations**:

- **Modern Stack (Primary):** `frontend/` (Next.js 16 / React 19 / TypeScript) + `backend/` (FastAPI / Python 3.11+)
- **Legacy Stack (Reference only):** `server.js` (Express) + `public/` (Vanilla JS)

Focus development on the modern stack unless explicitly working on the legacy reference implementation.

---

## Commands

### Backend (FastAPI)

```bash
cd backend
uv sync                                         # install dependencies
python main.py                                  # dev server → http://localhost:8000
uv run pytest                                   # run all tests
uv run pytest -v                                # verbose
uv run pytest tests/test_auth.py               # single file
uv run pytest -k test_name                     # single test by name
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev        # dev server → http://localhost:3000
npm run build
npm start          # production
npm run lint       # ESLint
```

### Legacy Stack

```bash
npm install && node server.js    # runs on root package.json
```

---

## Architecture

### Backend (`backend/`)

| File | Purpose |
|------|---------|
| `main.py` | All FastAPI routes and dependency injection (~81 KB) |
| `models.py` | SQLModel table + schema definitions |
| `db.py` | Engine creation, startup seeding (default tenant + CoA + admin user) |
| `auth.py` | JWT encoding/decoding, bcrypt password hashing |

**Database:** SQLite (`backend/database.db`) in dev; PostgreSQL via `DATABASE_URL` in production. Schema is created via `SQLModel.metadata.create_all()` — no Alembic migrations exist.

**Seeding:** On startup, `db.py` creates:
- A default `Tenant`, seeds a Chart of Accounts, and optionally creates an admin user from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` env vars
- Four pre-seeded demo tenants (one per business model) with placeholder users for immediate testing
- Delete `backend/database.db` to reset to seeded state

**Demo Tenants (auto-created on first run):**
| Email | Model | Password |
|-------|-------|----------|
| `demo.simple@easy-books.app` | Simple | `demo1234` |
| `demo.services@easy-books.app` | Services | `demo1234` |
| `demo.trader@easy-books.app` | Trader | `demo1234` |
| `demo.manufacturing@easy-books.app` | Manufacturing | `demo1234` |

To populate demo tenants with mock data (12+ customers, vendors, invoices, bills per tenant):
```bash
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
```

**API conventions:**
- All endpoints prefixed with `/api`
- DB dependency: `SessionDep = Annotated[Session, Depends(get_session)]`
- Auth enforcement: `CurrentUserDep = Annotated[User, Depends(get_current_user)]`
- Swagger UI available at `http://localhost:8000/docs` during dev

### Frontend (`frontend/`)

**Routing:** Next.js App Router. The `(dashboard)` route group wraps all authenticated pages. `DashboardLayout` checks `isAuthenticated()` and redirects to `/login` if needed.

**API layer:** `src/lib/api.ts` — `apiFetch(path, options)` auto-injects the `Authorization: Bearer` header from `localStorage` key `access_token`.

**Settings System:** `SettingsContext` (`src/context/SettingsContext.tsx`) fetches `/api/settings` on app init and provides settings app-wide via `useSettings()` hook. Settings include:
- `company_name` — displayed in header and reports
- `business_tagline` — shown below company name (e.g., "Easy-Books · Double-Entry Accounting")
- `currency`, `fiscal_year_start`, `financial_statement_date` — accounting preferences
- `invoice_prefix`, `bill_prefix` — document numbering
- `tax_id`, `email_notifications` — compliance and notifications

**Company Branding:** Users customize their branding via `/dashboard/settings`:
- Company name appears in `Header` + `PrintHeader`
- Business tagline appears below company name in header and all printed documents
- All settings are persisted per-tenant via `/api/settings` PATCH endpoint

**UI conventions:**
- Icons: `lucide-react` only
- Styling: Tailwind CSS v4 with `tailwind-merge`
- Brand colors: Background `#f6f3ee` (cream), Accent `#b8943f` (gold), Text `#1a1814` (charcoal)
- Fonts: DM Sans (UI), DM Serif Display (headings)

### Multi-Tenancy

Every data model includes `tenant_id`. Unique constraints (account codes, JV numbers) are tenant-scoped, not global. The JWT payload carries both `sub` (email) and `tenant_id` — never query accounting data without filtering by `tenant_id`.

### Double-Entry Bookkeeping Invariant

`sum(debit) == sum(credit)` must hold for every posted transaction. This is validated in `POST /api/transactions` before any DB write. `JournalEntry` rows store separate `debit` and `credit` float fields; exactly one must be > 0 per line.

---

## Environment Variables

**Backend** (`backend/.env`):
```
DATABASE_URL=              # PostgreSQL (production); omit to use SQLite
JWT_SECRET_KEY=            # openssl rand -hex 32
FRONTEND_ORIGIN=http://localhost:3000
SEED_ADMIN_EMAIL=
SEED_ADMIN_PASSWORD=
SEED_COMPANY_NAME=
```

**Frontend** (`frontend/.env.local`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Important Constraints

- **Next.js 16 breaking changes** — APIs and file conventions differ from earlier versions. Before writing frontend code, check `node_modules/next/dist/docs/` and heed `frontend/AGENTS.md`.
- **Tenant isolation** — always filter by `tenant_id`; missing this silently leaks cross-tenant data.
- **Debit/credit balance** — validate totals before any transaction commit.
- **JWT payload** — must include both `sub` and `tenant_id`; auth middleware depends on both fields.
- **No migration tool** — schema changes require manual coordination; `create_all()` only adds new tables, it does not alter existing ones.

---

## Adding Common Features

**New report:**
1. Add FastAPI endpoint in `backend/main.py` using `select()` with tenant filter.
2. Create `frontend/src/app/(dashboard)/[report-name]/page.tsx`.
3. Use `apiFetch` for data; `react-chartjs-2` for visualizations.

**New transaction type:**
1. Validate `sum(debit) == sum(credit)` in the endpoint.
2. Generate a unique `jv_number` per tenant.
3. Insert one `Transaction` + N `JournalEntry` rows atomically.

**New account type:**
1. Update `Account.type` documentation/enum.
2. Add seeding defaults in `db.py` if needed.
3. Update any report aggregation logic that groups by account type.

**Customize company branding/settings:**
1. Add new setting key to `AppSettings` interface in `frontend/src/context/SettingsContext.tsx`
2. Add default value to `defaults` object in same file
3. Add field to `SettingsUpdate` model in `backend/routers/settings.py`
4. Add UI input field to `frontend/src/app/(dashboard)/settings/page.tsx`
5. Display setting value where needed (Header, PrintHeader, etc.) using `useSettings()` hook
6. Settings are auto-persisted via `/api/settings` PATCH endpoint — no additional backend logic needed
