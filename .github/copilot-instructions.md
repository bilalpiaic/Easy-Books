# Easy-Books: Copilot Development Guide

Easy-Books is a multi-tenant double-entry accounting SaaS with a modern stack (FastAPI + SQLModel backend, Next.js 16 + React 19 frontend) and a legacy Express/vanilla reference app. Focus development on the modern stack unless explicitly asked otherwise.

Current (v2.5.0): multi-level Chart of Accounts (group parents + leaf accounts; posting to active leaves only) with hierarchical Trial Balance / Balance Sheet / P&L (`services/account_tree.py` roll-up; nested-tree payloads single-period, flat comparison mode); deferred-revenue origination (`services/deferred.py`; `product.is_deferred` → Deferred Revenue 2300 + recognition schedules); posted-document editing (reverse-and-repost, negative-stock guard); voucher series (SL/PU/CR/CP/JV/CN/DN).

## Build, test, and lint commands

### Backend (FastAPI, Python 3.11+)
```bash
cd backend
uv sync
python main.py
uv run pytest
uv run pytest tests/test_auth.py
uv run pytest -k test_name
```

### Frontend (Next.js 16, TypeScript)
```bash
cd frontend
npm install
npm run dev
npm run build
npm start
npm run lint
npx tsc --noEmit
```

### Legacy stack (reference only)
```bash
npm install
node server.js
```

## High-level architecture

- **Backend:** `backend/main.py` wires middleware and mounts 37+ domain routers in `backend/routers/`. Business logic lives in `backend/services/` — especially `services/posting.py`, the only path that writes `JournalEntry` rows and enforces GL invariants. **Alembic migrations are the source of truth** (`backend/alembic/versions/`): add a column/table → update `models.py`, run `uv run alembic revision --autogenerate -m "..."` and `uv run alembic upgrade head`; `create_all()` still runs in dev for zero-setup boot; standalone installers and `run_packaged.py` run `alembic upgrade head` on every launch. Notable routers: `routers/reports.py` (GL with opening/closing balance on date filters + `/api/reports/product-ledger`, `/api/reports/inventory-performance`, `/api/reports/customer-performance`), `routers/admin.py` (demo-data seed/purge), `routers/product_categories.py` (`ProductCategory` CRUD — 2-level parent → sub-category taxonomy).
- **Frontend:** Next.js App Router with authenticated pages under `src/app/(dashboard)/`. `SettingsContext` initializes app settings from `/api/settings` (includes `block_negative_stock` over-sell guard), and `src/lib/api.ts` is the single fetch wrapper. Manufacturing and Telecom Franchise UI sections are gated by `business_model` from `/api/auth/me`. The sidebar includes a dedicated **Inventory** nav group: Products, Product Categories (`/products/categories`), Product Ledger, and Inventory Performance. `components/UpdateModal.tsx` provides the Settings → Check for Updates UI (uses `window.easybooks` Electron bridge on desktop; falls back to CLI `update.bat`/`update.sh` on script/web installs).
- **Legacy:** `server.js` + `public/` are reference-only for the old stack.

## Key conventions

- **Multi-tenancy:** Every model includes `tenant_id`; queries must filter by tenant; unique constraints (account codes, JV numbers) are tenant-scoped. JWT payload includes both `sub` (email) and `tenant_id`. `business_model` ∈ `simple | services | trader | manufacturing | telecom_franchise` (DB CHECK).
- **Telecom franchise (V3):** Models live in `backend/models_telecom.py` (23 `tc_*` tables, re-exported by `models.py`). GL postings go through `services/tracker_posting.py` + `services/franchise_posting.py` (which still call `services/posting.py`). Routes under `routers/telecom.py` + `routers/telecom_reports.py`. Frontend under `src/app/(dashboard)/telecom/` using `components/telecom/ActionForm` + `primitives`.
- **Users/RBAC (V3.6):** `routers/users.py` (admin+ via `AdminUserDep`) handles multi-user-per-tenant — create/invite/role/activate/reset-password; `UserInvite` table backs tokenized invites; profile self-service (name/phone/password/avatar) is in `routers/auth.py`. `get_current_user` rejects `is_active=false` users (403) on every request. Guards: no self-role-change/self-deactivation, owner role is owner-only, last active owner is protected. Frontend: `src/app/(dashboard)/profile`, `.../team` (role-gated), public `src/app/accept-invite`.
- **Posting rules:** `sum(debit) == sum(credit)` and no negative amounts. Use `services/posting.py` for any new GL writes. The `block_negative_stock` setting (default `false`) enables an over-sell guard: `consume_stock(block_negative=True)` raises HTTP 400 if a sale would drive `stock_qty` below 0; purchases are never blocked.
- **Money:** Backend uses `Decimal` (`NUMERIC(18,4)`) with banker's rounding (`ROUND_HALF_EVEN`) via `services/money.py`.
- **Auth hardening:** Login returns both Bearer token and HttpOnly cookie; cookie-auth mutations must echo `eb_csrf` in `X-CSRF-Token`. Idempotency is enabled via the `Idempotency-Key` header.
- **API versioning:** Endpoints are mounted at `/api/*` and `/api/v1/*`; keep v1 stable for SDK consumers.
- **Frontend constraints:** Next.js 16 has breaking changes — read `frontend/AGENTS.md` and `node_modules/next/dist/docs/` before editing.

## Dev environment

- **`./dev.sh`** — starts backend (port 8000) + frontend (port 3000) together. Auto-seeds all 5 demo tenants with 50+ records per entity type before starting. Handles WSL2 node/npm path issues automatically.
- **Alembic migrations** — `uv run alembic revision --autogenerate -m "..."` + `uv run alembic upgrade head` for schema changes; `create_all()` bootstraps a fresh checkout; delete `backend/database.db` to reset.
- **5 demo tenants** — simple / services / trader / manufacturing / telecom_franchise, all at `demo.<model>@easy-books.app` / `demo1234`.

## References

- **README.md** for full feature set and environment variables.
- **BLUEPRINT.md** and **WORKFLOW.md** for domain flows, GL mappings, and the manufacturing (§4.7) + telecom-franchise (§4.8) lifecycles.
- **GEMINI.md** for a concise repo overview.
