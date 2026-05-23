# Easy-Books: Copilot Development Guide

Easy-Books is a multi-tenant double-entry accounting SaaS with a modern stack (FastAPI + SQLModel backend, Next.js 16 + React 19 frontend) and a legacy Express/vanilla reference app. Focus development on the modern stack unless explicitly asked otherwise.

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

- **Backend:** `backend/main.py` wires middleware and mounts domain routers in `backend/routers/`. Business logic lives in `backend/services/` — especially `services/posting.py`, the only path that writes `JournalEntry` rows and enforces GL invariants. Migrations are in `backend/alembic/`; schema bootstrapping is controlled by `SCHEMA_BOOTSTRAP` (`create_all` vs `alembic`).
- **Frontend:** Next.js App Router with authenticated pages under `src/app/(dashboard)/`. `SettingsContext` initializes app settings from `/api/settings`, and `src/lib/api.ts` is the single fetch wrapper. Manufacturing UI is gated by `business_model` from `/api/auth/me`.
- **Legacy:** `server.js` + `public/` are reference-only for the old stack.

## Key conventions

- **Multi-tenancy:** Every model includes `tenant_id`; queries must filter by tenant; unique constraints (account codes, JV numbers) are tenant-scoped. JWT payload includes both `sub` (email) and `tenant_id`.
- **Posting rules:** `sum(debit) == sum(credit)` and no negative amounts. Use `services/posting.py` for any new GL writes.
- **Money:** Backend uses `Decimal` (`NUMERIC(18,4)`) with banker's rounding (`ROUND_HALF_EVEN`) via `services/money.py`.
- **Auth hardening:** Login returns both Bearer token and HttpOnly cookie; cookie-auth mutations must echo `eb_csrf` in `X-CSRF-Token`. Idempotency is enabled via the `Idempotency-Key` header.
- **API versioning:** Endpoints are mounted at `/api/*` and `/api/v1/*`; keep v1 stable for SDK consumers.
- **Frontend constraints:** Next.js 16 has breaking changes — read `frontend/AGENTS.md` and `node_modules/next/dist/docs/` before editing.

## References

- **README.md** for full feature set and environment variables.
- **BLUEPRINT.md** and **WORKFLOW.md** for domain flows, GL mappings, and manufacturing lifecycle.
- **GEMINI.md** for a concise repo overview.
