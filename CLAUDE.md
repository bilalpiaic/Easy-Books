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

**Seeding:** On startup, `db.py` creates a default `Tenant`, seeds a Chart of Accounts, and optionally creates an admin user from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` env vars. Delete `backend/database.db` to reset to seeded state.

**API conventions:**
- All endpoints prefixed with `/api`
- DB dependency: `SessionDep = Annotated[Session, Depends(get_session)]`
- Auth enforcement: `CurrentUserDep = Annotated[User, Depends(get_current_user)]`
- Swagger UI available at `http://localhost:8000/docs` during dev

### Frontend (`frontend/`)

**Routing:** Next.js App Router. The `(dashboard)` route group wraps all authenticated pages. `DashboardLayout` checks `isAuthenticated()` and redirects to `/login` if needed.

**API layer:** `src/lib/api.ts` — `apiFetch(path, options)` auto-injects the `Authorization: Bearer` header from `localStorage` key `access_token`.

**State:** `SettingsContext` (`src/context/`) fetches `/api/settings` on init and provides currency/company settings app-wide. No external state management library.

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
