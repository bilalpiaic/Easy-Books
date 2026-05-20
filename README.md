# Easy-Books

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Easy-Books** is a multi-tenant double-entry accounting SaaS. It enforces book-keeping invariants in the database (∑Dr = ∑Cr, no negative amounts, no posting into locked periods), keeps inventory at Weighted-Average cost, and computes every report live from the General Ledger — no batch jobs.

Stack: FastAPI + SQLModel + Alembic (backend) · Next.js 16 + React 19 + Tailwind v4 (frontend) · SQLite for dev, PostgreSQL for prod.

---

## What's in the box

### Accounting
- **Double-entry, exact** — Decimal money throughout (`NUMERIC(18,4)`, banker's rounding). The central `services/posting.py` is the *only* code path that creates `JournalEntry` rows; it refuses unbalanced JVs, negative amounts, both-sided rows, empty rows, and writes into locked periods.
- **Weighted-Average inventory** — IAS 2 / ASC 330 compliant. Each receipt appends an `InventoryLayer`; sales relieve at the running WAvg cost, FIFO-deplete layers, and post a separate COGS sub-JV.
- **Tax codes catalog** — per-tenant `TaxCode(code, name, rate, type, gl_account)`. Output (sales) vs Input (purchase) tagged; CHECK enforces.
- **Multi-currency** — `Tenant.base_currency`; per-document `currency` + snapshot `exchange_rate`. `ExchangeRate(date, from, to, rate)` catalog with date-fallback lookup and automatic inverse (USD→EUR resolves an EUR→USD entry).
- **Payment allocations** — one payment can settle multiple invoices/bills with partial amounts. Invoice/Bill `status` derives from `sum(allocations) vs total`: `partial` when some is paid, `paid` when fully covered.
- **Period close** — `POST /api/periods/{id}/close` posts the closing JV (Revenue/Expense → Retained Earnings), locks the period, and materialises per-account balances into `AccountBalance` for fast trial-balance reads. `/reopen` unlocks and invalidates the cache.
- **Recurring journal entries** — `RecurringTemplate` with `daily | weekly | monthly | quarterly | yearly`. `POST /api/recurring/run-due` materialises every template whose `next_run <= today` and advances the schedule. Idempotent per `(template, next_run)`.
- **Reversal** — `POST /api/transactions/{id}/reverse` posts the mirror JV *and* unwinds derived state: payment allocations are dropped (statuses recomputed), invoice reversal restores stock and reverses the COGS sub-JV automatically, bill reversal peels back the inventory layer and recomputes `avg_cost`.

### Banking
- **Bank account balances** derived live from the GL — no separate ledger to drift.
- **CSV statement import** — generic 5-column CSV (date,description,debit,credit,balance), de-duped by SHA-256 file hash. `auto-match` links lines to existing JVs by amount + ±3-day window; manual match supported.
- **Reconciliation** — per-period bank reconciliation with line matching and lock-on-close.

### Multi-tenant SaaS
- **Self-service signup** creates an isolated tenant + seeded Chart of Accounts (22 default accounts).
- **RBAC** — `owner | admin | accountant | viewer`. First user of a tenant is `owner`. `WriteUserDep` guards every mutating endpoint (`accountant+` required); `AdminUserDep` is available for elevated-admin endpoints.
- **Tenant isolation** at the data layer — every query filters by `tenant_id`; cross-tenant reads return 404 (never 403 — no enumeration). The central posting service double-checks that referenced accounts belong to the caller's tenant.
- **Audit log** — every mutation writes a row (user, action, entity, before/after JSON).

### Auth & API hardening
- **JWT + HttpOnly cookie** — login returns both a Bearer token (for SDK/curl/mobile) and sets an `eb_access` HttpOnly cookie (for browser SPAs). Both work side-by-side.
- **CSRF protection** — double-submit-cookie. Cookie-authenticated mutations must echo the `eb_csrf` cookie in `X-CSRF-Token`. Bearer-header callers are exempt (no ambient browser authority).
- **Login throttle** — DB-backed `LoginAttempt` table, 10 attempts per IP per 60 s rolling window. Survives uvicorn worker restarts and is shared across workers.
- **Idempotency keys** — middleware caches the response of any POST/PUT/PATCH/DELETE that carries an `Idempotency-Key` header, keyed by `(tenant, key)`. Retries return the cached body with `Idempotency-Replay: true`.
- **API versioning** — every endpoint is mounted at `/api/*` and at `/api/v1/*`; v1 is the stable surface for SDKs, future breaking changes ship under `/api/v2`.
- **Atomic numbering** — invoice/bill numbers come from a per-tenant `SequenceCounter` with `SELECT FOR UPDATE`. Two concurrent POSTs cannot mint the same number; reversal/delete doesn't reset the sequence.

### Reports (all live from the GL)
Trial balance · General ledger (running balance per account) · Income statement · Balance sheet · Cash flow (indirect method) · Tax summary (GST output/input + income-tax slab estimate) · AR/AP aging (uses **outstanding** balance, net of partial payments) · Dashboard KPIs + charts.

---

## Getting started

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm (or pnpm)

### One-shot dev script

```bash
git clone https://github.com/bilalpiaic/Easy-Books.git
cd Easy-Books

# Backend dependencies
python -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt

# Frontend dependencies
( cd frontend && npm install )

# Bring the local SQLite DB up to the latest schema
( cd backend && DATABASE_URL=sqlite:///$(pwd)/database.db \
    VIRTUAL_ENV=$(pwd)/.venv .venv/bin/alembic upgrade head )

# Start backend + frontend together with prefixed log streams
./dev.sh
```

Backend: http://localhost:8000 (API docs at `/docs`)
Frontend: http://localhost:3000

Press `Ctrl-C` once to stop both cleanly.

### First-time signup

Open http://localhost:3000/signup, fill in your name, company, email, and a password (≥ 8 chars). A new tenant is created with a default Chart of Accounts; you're auto-logged-in as `owner` of that tenant.

### Environment variables

| Var | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Connection string. `postgres://…` is rewritten to `postgresql://…`. | SQLite at `backend/database.db` |
| `JWT_SECRET_KEY` | HMAC secret for JWT signing. **Required in production** — startup fails if missing/default when `APP_ENV=production`. | Insecure default in dev |
| `APP_ENV` | `development` or `production`. Affects cookie `Secure` flag, JWT secret check. | `development` |
| `FRONTEND_ORIGIN` | Comma-separated CORS allow-list. | `http://localhost:3000` |
| `SCHEMA_BOOTSTRAP` | `create_all` (default — `SQLModel.metadata.create_all` on startup) or `alembic` (skip startup DDL; run migrations explicitly). | `create_all` |
| `SEED_COMPANY_NAME` | Default company name for the first tenant. | `My Company` |

---

## Architecture

```
backend/
├── main.py                  ← FastAPI bootstrap (~80 lines): middleware, routers
├── models.py                ← SQLModel tables
├── auth.py                  ← JWT + bcrypt
├── db.py                    ← engine, seed_data, default CoA
├── alembic/versions/        ← 0001 → 0009 (idempotent migrations)
├── routers/                 ← 21 domain routers
│   ├── common.py            ← shared deps (SessionDep, CurrentUserDep, WriteUserDep, …)
│   ├── auth.py              ← signup, login, logout, /me
│   ├── invoices.py · bills.py · payments.py
│   ├── tax_codes.py · exchange_rates.py · recurring.py
│   ├── bank_accounts.py · bank_imports.py · reconciliations.py
│   ├── periods.py · transactions.py · reports.py
│   └── …
├── services/                ← pure-logic modules (no FastAPI)
│   ├── posting.py           ← THE central GL writer
│   ├── inventory.py         ← WAvg cost + reverse helpers
│   ├── fx.py                ← exchange-rate lookup with inverse fallback
│   ├── money.py             ← Decimal helpers, ROUND_HALF_EVEN
│   ├── csrf.py              ← double-submit CSRF middleware
│   └── idempotency.py       ← response-cache middleware
└── tests/                   ← 63 tests (pytest)

frontend/src/
├── app/login/ · app/signup/
├── app/(dashboard)/         ← auth-gated, 23 pages
│   ├── dashboard/           ← KPIs + charts
│   ├── invoices/ · bills/ · payments-received/ · bill-payments/
│   ├── customers/ · vendors/ · products/
│   ├── entry/               ← manual JV
│   ├── journal/ · ledger/   ← read-only GL views
│   ├── trial-balance/ · pl/ · balance/ · cashflow/ · tax/
│   ├── coa/                 ← Chart of Accounts editor
│   ├── bank-accounts/ · reconciliations/
│   ├── workflow/            ← visual flowcharts
│   ├── guide/               ← user guide (multi-tab)
│   └── settings/
├── components/              ← Sidebar, Header, modals, charts, CsvImportButton
└── lib/                     ← apiFetch, auth, utils
```

---

## Development workflow

```bash
# Run all backend tests
cd backend && .venv/bin/python -m pytest

# Apply migrations to a database
DATABASE_URL=sqlite:///./database.db .venv/bin/alembic upgrade head

# Generate a new migration (autogenerate from model diffs)
.venv/bin/alembic revision --autogenerate -m "your message"

# Type-check the frontend
cd frontend && npx tsc --noEmit
```

---

## Status & roadmap

This branch (`saas-transition-foundation`) carries the active SaaS work. Shipped to date:

- **P0** — Decimal money, central posting service, COGS, period-lock
- **P1** — Router split (21 routers), atomic numbering, Alembic baseline
- **P2** — RBAC, HttpOnly cookie auth, password min-length, secret hardening
- **P3** — Tax codes, payment allocations, period close, recurring entries
- **P4** — Idempotency keys, `/api/v1` versioning
- **P5** — Multi-currency invoices/bills + FX rate lookup
- **P6** — Bank statement CSV import + auto-match
- **P7** — Materialised account balances + correct partial-payment aging
- **A** — Dashboard outstanding, reversal completeness, delete safety
- **B** — FX inverse fallback, scoped auto-match, atomic numbering via `SequenceCounter`
- **C** — CSRF middleware, DB-backed login throttle

Not yet shipped (worth considering):
- FX revaluation at period end (unrealised gain/loss on open AR/AP)
- Multi-currency on payments
- Daily overdue sweep (`Invoice.status = 'overdue'` is unwritten)
- Frontend currency selector + role display + allocations UI + CSRF token wiring
- Email send, PDF generation, payment-link integration
- E2E tests (Playwright)

---

## Further reading

- [`WORKFLOW.md`](./WORKFLOW.md) — full accounting workflows, GL Dr/Cr maps, report-linking matrix, API catalog, RBAC matrix, multi-currency mechanics, idempotency/CSRF semantics, period-close mechanics.
- [`DEPLOYMENT.md`](./DEPLOYMENT.md) — Vercel deployment for backend + frontend.
- In-app **User Guide** (`/guide`) — interactive tabbed walkthrough for every feature.
- In-app **Workflow** (`/workflow`) — visual flowcharts for each accounting cycle.

---

## License

MIT. See [`LICENSE`](./LICENSE).
