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
- **Sub-ledger views & audit-trail drill-down** — per-customer AR ledger, per-vendor AP ledger (credit-normal — positive = "we owe"), per-product stock card with running quantity & value. Reverse-resolution from any `JournalEntry` back to its source document (Invoice, Bill, Payment, GRN) is wired into `GET /api/transactions/{id}.source_docs[]`. Every account code, JV-number, invoice/bill/voucher number, customer name, vendor name and product code rendered in the app is a clickable link to its primary record — closing the IAS 1 / ISA 230 audit-trail loop end-to-end. Aligns with **IAS 1.45** (consistency of presentation), **ISA 230** (audit documentation — reperformance), **ISA 315** (internal control via traceability), and **IAS 2.36(d)** (carrying-amount disclosure per inventory class).

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
Trial balance · General ledger (running balance per account) · **AR sub-ledger** (per customer) · **AP sub-ledger** (per vendor, credit-normal) · **Stock card** (per product, qty + value) · Income statement · Balance sheet · Cash flow (indirect method) · Tax summary (GST output/input + income-tax slab estimate) · AR/AP aging (uses **outstanding** balance, net of partial payments) · Dashboard KPIs + charts. Every list page and every report is hyperlinked: click any account, JV, invoice, bill, customer, vendor or product to drill straight to the source document — no URL typing, no orphan rows.

### Manufacturing track (V2)

For tenants with `business_model = manufacturing`, Easy-Books adds a complete value-addition workflow on top of the core ledger:

- **Business-model selection at signup** — `simple | services | trader | manufacturing`. Each variant gets a tailored Chart of Accounts (the manufacturing CoA includes raw-material, WIP, FG, the custodial memo pair `1210/2150`, direct labour, overhead) and a different set of enabled UI modules.
- **Multi-location inventory** — `StockLocation(code, type)` with `own | customer_custodial | wip` types. Manufacturing tenants seed `MAIN`, `GODOWN`, `WIP` out of the box. Layers are keyed by `(product, location)` so the same product can live in multiple stores at different costs.
- **Lot tracking + stock-movement event log** — every receipt/issue/consumption writes a `StockMovement` row (`RECEIPT | CUSTODIAL_RECEIPT | ISSUE | CUSTODIAL_ISSUE | COMPLETION | DELIVERY | SHIPMENT | ADJUSTMENT`). The log is the source of truth; `InventoryLayer` is a materialised projection.
- **Bills of Material** — versioned recipes (`BomHeader` + `BomLine`). Each line tags its source as `own_stock` (consumes from your inventory at WAvg cost — hits WIP) or `customer_supplied` (consumes from a customer godown — memo-only, never your asset). Posting a new version auto-deactivates the prior one; historical PO references stay reconstructable.
- **Rate plans** — versioned value-addition pricing (`RatePlan + CustomerRatePlan`). Formula: `per_unit_rate × qty + (materials_passthrough? own_material_cost) + overhead% + margin%`. A customer can be assigned multiple plans; reassignment auto-deactivates the previous active one.
- **Goods Receipt Note** — `POST /api/grn` receives customer-supplied material into a godown. Custodial — never your asset. Optional `declared_value` triggers a memo JE (`Dr 1210 / Cr 2150`); custody is automatically released on delivery.
- **Production Order lifecycle** — `draft → started → completed → delivered → billed` (or `cancelled` from draft). Each transition posts the right journal entries:
  - **start** — `Dr WIP / Cr Raw Material` (own_stock); `CUSTODIAL_ISSUE` movement only for customer_supplied lines (no GL).
  - **complete** — `Dr Finished Goods / Cr WIP` at absorbed cost; output capitalised as a fresh InventoryLayer at the computed unit cost.
  - **deliver** — `Dr COGS / Cr Finished Goods`; releases custodial memo balance (`Dr 2150 / Cr 1210`) for any GRNs whose layers are fully drained.
  - **bill** — generates an Invoice via the assigned RatePlan (`Dr AR / Cr 4010 Service Revenue`).
- **Manufacturing reports** — `/api/manufacturing/dashboard` (pipeline counts + WIP/FG/custodial totals), `/wip-aging` (open POs bucketed by days since start), `/production-summary` (state-grouped totals), `/customer-custody` (who has what on hand).
- **Adaptive UI** — the sidebar reads `business_model` from `/api/auth/me` and only surfaces the Manufacturing section (Production Floor, BoMs, Rate Plans, GRN, Production Orders) when applicable. Every manufacturing page ships with an inline `HelpCallout` + `EmptyStateGuide` so a first-time user always knows what the page does, why, and the next concrete step.

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
├── alembic/versions/        ← 0001 → 0013 (idempotent migrations)
├── routers/                 ← 26 domain routers
│   ├── common.py            ← shared deps (SessionDep, CurrentUserDep, WriteUserDep, …)
│   ├── auth.py              ← signup (with business_model), login, logout, /me
│   ├── invoices.py · bills.py · payments.py
│   ├── tax_codes.py · exchange_rates.py · recurring.py
│   ├── bank_accounts.py · bank_imports.py · reconciliations.py
│   ├── periods.py · transactions.py · reports.py
│   ├── stock_locations.py   ← (V2.2) locations + movements + custody
│   ├── bom.py               ← (V2.3) Bills of Material catalogue
│   ├── rate_plans.py        ← (V2.3) RatePlan + customer assignment
│   ├── grn.py               ← (V2.4) Goods Receipt Note + memo JE
│   ├── production_orders.py ← (V2.4) PO lifecycle (start/complete/deliver/bill)
│   ├── manufacturing_reports.py ← (V2.5) dashboard + wip-aging + custody
│   └── …
├── services/                ← pure-logic modules (no FastAPI)
│   ├── posting.py           ← THE central GL writer
│   ├── inventory.py         ← WAvg cost + reverse helpers
│   ├── fx.py                ← exchange-rate lookup with inverse fallback
│   ├── money.py             ← Decimal helpers, ROUND_HALF_EVEN
│   ├── csrf.py              ← double-submit CSRF middleware
│   └── idempotency.py       ← response-cache middleware
└── tests/                   ← 122 tests (pytest)

frontend/src/
├── app/login/ · app/signup/  ← signup is a 2-step wizard with business-model picker
├── app/(dashboard)/          ← auth-gated, 28 pages
│   ├── dashboard/            ← KPIs + charts
│   ├── invoices/ · invoices/[id]/   ← list + non-print interactive detail (Back/Print/Reverse)
│   ├── bills/    · bills/[id]/      ← list + non-print interactive detail
│   ├── payments-received/ · bill-payments/
│   ├── customers/ · customers/[id]/ledger/   ← per-customer AR sub-ledger (running balance)
│   ├── vendors/   · vendors/[id]/ledger/     ← per-vendor AP sub-ledger (credit-normal)
│   ├── products/  · products/[id]/stock-card/← StockMovement-driven qty + value card
│   ├── entry/                ← manual JV
│   ├── journal/ · journal/[id]/ · ledger/  ← read-only GL views + JV detail w/ source-doc link
│   ├── trial-balance/ · pl/ · balance/ · cashflow/ · tax/
│   ├── coa/                  ← Chart of Accounts editor
│   ├── bank-accounts/ · reconciliations/
│   ├── manufacturing/        ← V2: shows only when business_model='manufacturing'
│   │   ├── page.tsx          ← Production Floor dashboard
│   │   ├── boms/             ← Bills of Material
│   │   ├── rate-plans/       ← Rate Plan catalogue
│   │   ├── grn/              ← Goods Receipt Note
│   │   └── production-orders/← PO lifecycle (one-click advance)
│   ├── workflow/             ← visual flowcharts
│   ├── guide/                ← user guide (multi-tab)
│   └── settings/
├── components/
│   ├── Sidebar.tsx           ← adaptive — Manufacturing section gated on tenant
│   ├── BusinessModelPicker.tsx ← used by signup wizard
│   ├── DocLink.tsx           ← central drill-down resolver: maps {type,id} → /detail href
│   ├── PrintHeader.tsx       ← branded A4 portrait/landscape print output
│   ├── guidance/             ← HelpCallout, FieldHint, EmptyStateGuide
│   └── …                     ← Header, modals, charts, CsvImportButton
└── lib/                      ← apiFetch, auth, utils
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

**Core platform (P-track)**
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

**Drill-down + sub-ledger track (D-track)**
- **PR-A** — Backend sub-ledger endpoints (`/customers/{id}/ledger`, `/vendors/{id}/ledger`, `/products/{id}/stock-card`) + transaction source-doc reverse-resolution on `GET /api/transactions/{id}`
- **PR-B** — Non-print interactive detail pages: `/invoices/[id]`, `/bills/[id]`, `/journal/[id]` with toolbar (Back / Print / Reverse)
- **PR-C** — Customer ledger + Vendor ledger (credit-normal) + Product stock card pages, each with date filter, summary tiles and print
- **PR-D** — Drill-down link sweep across every list page via the new `<DocLink>` resolver (11 entity kinds)
- **PR-E** — COA account code & name hyperlinked to their respective account ledgers, closing the cyclic audit trail

**Manufacturing track (V-track)**
- **V2.1** — Business-model selection at signup, per-model Chart of Accounts, `Account.is_memo` for custodial pairs, guidance scaffolding (`HelpCallout`, `FieldHint`, `EmptyStateGuide`)
- **V2.2** — `StockLocation` (own / customer_custodial / wip) + `StockMovement` event log + lot tracking on `InventoryLayer`
- **V2.3** — `BomHeader`/`BomLine` versioned recipes + `RatePlan` value-addition pricing + `CustomerRatePlan` assignment
- **V2.4** — `GoodsReceiptNote` custodial flow + `ProductionOrder` state machine (start/complete/deliver/bill) with full GL postings
- **V2.5** — Manufacturing reports (dashboard, wip-aging, production-summary, customer-custody) + adaptive sidebar + per-page in-app guidance

**Test coverage:** 122 backend tests; full lifecycle end-to-end smoke verified.

Not yet shipped (worth considering):
- FX revaluation at period end (unrealised gain/loss on open AR/AP)
- Multi-currency on payments
- Daily overdue sweep (`Invoice.status = 'overdue'` is unwritten)
- Production-order reversal helper (currently requires manual JE reversal)
- Overhead/labour absorption at PO start (currently only own_stock material flows through WIP)
- Frontend currency selector + role display + allocations UI + CSRF token wiring
- Email send, PDF generation, payment-link integration
- E2E tests (Playwright)

---

## Further reading

- [`BLUEPRINT.md`](./BLUEPRINT.md) — complete project blueprint: every model, every endpoint, every flow, every decision.
- [`WORKFLOW.md`](./WORKFLOW.md) — full accounting workflows, GL Dr/Cr maps, report-linking matrix, API catalog, RBAC matrix, multi-currency mechanics, manufacturing cycle, idempotency/CSRF semantics, period-close mechanics.
- [`DEPLOYMENT.md`](./DEPLOYMENT.md) — Vercel deployment for backend + frontend.
- In-app **User Guide** (`/guide`) — interactive tabbed walkthrough for every feature.
- In-app **Workflow** (`/workflow`) — visual flowcharts for each accounting cycle.

---

## License

MIT. See [`LICENSE`](./LICENSE).
