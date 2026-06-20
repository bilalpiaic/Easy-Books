# Easy-Books: Copilot Development Guide

Easy-Books is a multi-tenant double-entry accounting SaaS with a modern stack (FastAPI + SQLModel backend, Next.js 16 + React 19 frontend) and a legacy Express/vanilla reference app. Focus development on the modern stack unless explicitly asked otherwise.

Current (v2.7): multi-level CoA (group parents + posting-only leaves) with hierarchical TB/BS/P&L (`services/account_tree.py`); deferred-revenue origination (`services/deferred.py`); granular permissions (`services/permissions.py`, 60-resource matrix); sales commissions + promo discounts; full-page data-entry forms; per-user resizable dashboard (react-grid-layout v2, v3 per-breakpoint layout schema); customer/vendor statements.

**v2.7 additions:** Section Hub Pages (`/receivable`, `/payable`, `/inventory`, `/banking`) driven by `HubPage`/`hubConfigs` + band components (`AgingBand`, `LowStockBand`, `AccountListBand`); collapsible 3-state sidebar (collapsed/open/pinned via localStorage, hover tooltip, auto-pin); 3-mode voucher form (Journal/Payment CP-BP/Receipt CR-BR, mode-specific GL pickers, JV prefix per mode); print system overhaul (dot-matrix B&W, `dd-mm-yy` via `fmtDate()`/`fmtDateJs()`, dynamic `@page` landscape via `PrintHeader` `useEffect`, `print:hidden` hygiene, `whitespace-nowrap` date/JV# cells, no voucher-type badge spans, `(amount)` negatives).

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

- **Backend:** `backend/main.py` wires middleware and mounts 40+ domain routers in `backend/routers/`. Business logic lives in `backend/services/` — especially `services/posting.py`, the only path that writes `JournalEntry` rows and enforces GL invariants. **Alembic migrations are the source of truth** (`backend/alembic/versions/`, through `0022_promo_rules`): add a column/table → update `models.py`, run `uv run alembic revision --autogenerate -m "..."` and `uv run alembic upgrade head`; `create_all()` still runs in dev for zero-setup boot; standalone installers and `run_packaged.py` run `alembic upgrade head` on every launch. Notable routers: `routers/reports.py` (GL with opening/closing balance on date filters + product-ledger, inventory-performance, customer-performance), `routers/admin.py` (demo-data seed/purge), `routers/product_categories.py` (2-level taxonomy), `routers/commissions.py` (plan/compute/approve/post), `routers/promo_rules.py` (rules + /check), `routers/permissions.py` (60-resource matrix + `perm_dep()` factory).
- **Frontend:** Next.js App Router with authenticated pages under `src/app/(dashboard)/`. `SettingsContext` initializes app settings from `/api/settings` (includes `block_negative_stock` over-sell guard); `src/lib/api.ts` is the single fetch wrapper; `src/lib/utils.ts` exports `fmtDate(str)` and `fmtDateJs(date)` — the **only** approved date formatters (`dd-mm-yy`; never use `.toLocaleDateString()` or raw ISO strings). Section Hub Pages: `/receivable`, `/payable`, `/inventory`, `/banking` use `HubPage` + `hubConfigs` + band components. Sidebar (`Sidebar.tsx`) is collapsible 3-state (collapsed/open/pinned, localStorage, hover tooltip, auto-pin). New Entry (`/journal/new`) is a 3-mode form: Journal/Payment(CP-BP)/Receipt(CR-BR). `PrintHeader.tsx` accepts `orientation` — set `"landscape"` only for wide tables; it injects `@page` CSS via `useEffect`. `components/UpdateModal.tsx` provides Settings → Check for Updates (Electron bridge on desktop; CLI command on web/script installs).
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
- **Date formatting:** always use `fmtDate(str)` (ISO string → `"dd-mm-yy"`) or `fmtDateJs(date)` (JS Date → `"dd-mm-yy"`) from `src/lib/utils.ts`. Never render raw ISO strings or call `.toLocaleDateString()` in the UI.
- **Print hygiene:** add `print:hidden` to all filter controls, pagination, sort handles, toolbar buttons, checkbox columns, and action columns. Use `<PrintHeader orientation="landscape">` only for wide tables — portrait is the default. Never add `max-w-xs` on description `<td>` cells; add `whitespace-nowrap` on Date and JV#/Doc# cells.
- **No voucher-type badges:** the JV number prefix (CP/SL/BR/JV etc.) already encodes the type — do not add `<span>` badge pills next to JV numbers in any report table.

## Dev environment

- **`./dev.sh`** — starts backend (port 8000) + frontend (port 3000) together. Auto-seeds all 5 demo tenants with 50+ records per entity type before starting. Handles WSL2 node/npm path issues automatically.
- **Alembic migrations** — `uv run alembic revision --autogenerate -m "..."` + `uv run alembic upgrade head` for schema changes; `create_all()` bootstraps a fresh checkout; delete `backend/database.db` to reset.
- **5 demo tenants** — simple / services / trader / manufacturing / telecom_franchise, all at `demo.<model>@easy-books.app` / `demo1234`.

## References

- **README.md** for full feature set and environment variables.
- **BLUEPRINT.md** and **WORKFLOW.md** for domain flows, GL mappings, and the manufacturing (§4.7) + telecom-franchise (§4.8) lifecycles.
- **GEMINI.md** for a concise repo overview.
