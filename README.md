# Easy-Books

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Easy-Books** is a multi-tenant double-entry accounting SaaS. It enforces book-keeping invariants in the database (∑Dr = ∑Cr, no negative amounts, no posting into locked periods), keeps inventory at Weighted-Average cost, and computes every report live from the General Ledger — no batch jobs.

Stack: FastAPI + SQLModel (backend) · Next.js 16 + React 19 + Tailwind v4 (frontend) · SQLite for dev, PostgreSQL for prod.

---

## What's in the box

### New in Sprint 7–12 (IAS/IFRS + product-parity roadmap)
- **Credit Notes** (ISA 240) — adjust posted invoices without breaking the audit trail; separate `CN-` sequence, posts Dr Revenue / Cr AR.
- **Fixed Assets & Depreciation** (IAS 16) — asset register with straight-line and reducing-balance methods; per-period depreciation posting.
- **Purchase Orders** (IAS 2.11) — raise → approve → convert-to-bill, a lightweight 3-way match (Trader/Manufacturing/Telecom).
- **Analytic accounts / cost centers** (IAS 1) — optional segment dimension on GL lines + Analytic P&L report.
- **Deferred revenue** (IFRS 15) — recognition schedules for service/subscription billing.
- **Budgets vs Actual** (IAS 1) — monthly per-account budgets with variance reporting.
- **FIFO option** (IAS 2.25) — tenant-level choice of Weighted-Average or FIFO cost flow.
- **Comparative-period** P&L and Balance Sheet (IAS 1.38); **FX revaluation** of open AR (IAS 21.23); **bank-rec zero-difference** enforcement (IAS 7.48).
- **Server-side PDF** invoices (WeasyPrint), **Stripe** payment links, **SMTP email** notifications, and **Alembic** migrations.
- **Tenant-aware guide & workflow** — each business model sees only the sections relevant to its features.

### Accounting
- **Double-entry, exact** — Decimal money throughout (`NUMERIC(18,4)`, banker's rounding). The central `services/posting.py` is the *only* code path that creates `JournalEntry` rows; it refuses unbalanced JVs, negative amounts, both-sided rows, empty rows, and writes into locked periods.
- **Weighted-Average inventory** — IAS 2 / ASC 330 compliant. Each receipt appends an `InventoryLayer`; sales relieve at the running WAvg cost, FIFO-deplete layers, and post a separate COGS sub-JV.
- **Tax codes catalog** — per-tenant `TaxCode(code, name, rate, type, gl_account)`. Output (sales) vs Input (purchase) tagged; per-line tax code on invoice/bill lines with separate GL posting per code.
- **Multi-currency** — `Tenant.base_currency`; per-document `currency` + snapshot `exchange_rate`. `ExchangeRate(date, from, to, rate)` catalog with date-fallback lookup and automatic inverse.
- **Payment allocations** — one payment settles multiple invoices/bills with partial amounts. Invoice/Bill `status` derives from `sum(allocations) vs total`: `partial` when some is paid, `paid` when fully covered.
- **Payment terms** — `PaymentTerm(code, name, days)` per tenant. Default set: Due on Receipt, Net 15, Net 30, Net 60. Assigned to customers, vendors, invoices, bills. Due date auto-calculates on invoice creation.
- **Period close** — `POST /api/periods/{id}/close` posts the closing JV (Revenue/Expense → Retained Earnings), locks the period, and materialises per-account balances into `AccountBalance` for fast trial-balance reads. `/reopen` unlocks and invalidates the cache.
- **Recurring journal entries** — `RecurringTemplate` with `daily | weekly | monthly | quarterly | yearly`. `POST /api/recurring/run-due` materialises every template whose `next_run <= today` and advances the schedule. Full UI (list, create, edit, deactivate, Run Now).
- **Overdue auto-flag** — Invoice/Bill `status` is set to `overdue` automatically on list and detail fetch when `due_date < today` and status is not `paid/partial/reversed`.
- **Reversal** — `POST /api/transactions/{id}/reverse` posts the mirror JV *and* unwinds derived state: payment allocations dropped, stock and COGS sub-JV reversed automatically.
- **Sub-ledger views & audit-trail drill-down** — per-customer AR ledger, per-vendor AP ledger (credit-normal), per-product stock card with running qty & value. Every account code, JV number, invoice/bill/voucher number, customer name, vendor name and product code rendered in the app is a clickable link to its primary record. Aligns with **IAS 1.45**, **ISA 230**, **ISA 315**, and **IAS 2.36(d)**.

### AR/AP UX
- **Draft editing** — Invoices and bills in `draft` status have an Edit button that opens the create modal pre-filled; on save, existing lines are deleted and re-inserted; if a transaction was posted, the old JV is reversed and a new one posted.
- **Multi-allocation payment modal** — selecting a customer/vendor in the payment form shows all open invoices/bills as a checklist table with outstanding balance and an "Amount to Apply" input per row. Running total validates against payment amount.
- **Customer/Vendor statements** — printable statement showing all invoices/bills, payments, opening balance, and closing balance for any date range. Accessible from the ledger page.
- **Notes & Internal Memo** — every invoice and bill stores a customer-facing `notes` field (printed on documents) and a staff-only `internal_memo` field. Both shown in detail view; notes appear on print layout.
- **Bulk actions** — select multiple invoices/bills → mark as sent, void, or delete (draft only). Floating `BulkActionBar` appears with count and action buttons.

### Banking
- **Bank account balances** derived live from the GL — no separate ledger to drift.
- **CSV statement import** — generic 5-column CSV (date,description,debit,credit,balance), de-duped by SHA-256 file hash. `auto-match` links lines to existing JVs by amount + ±3-day window.
- **Reconciliation** — per-period bank reconciliation with line matching and lock-on-close.

### Dashboard & Reports
- **Dashboard tiles** — Net Profit, Cash & Bank, AR Outstanding, AP Due This Week, overdue invoices, low-stock items.
- **AR Aging chart** — 5-bucket mini chart (Current, 1–30, 31–60, 61–90, 90+) on the dashboard.
- **All reports live from the GL** — Trial Balance, General Ledger, AR/AP sub-ledgers, Stock Card, Income Statement, Balance Sheet, Cash Flow (indirect), Tax Summary (GST output/input), AR/AP Aging.

### Settings & Customisation
- **Company profile** — name, tagline, address, city, country, phone, website, Tax ID, logo upload. All printed on documents via `PrintHeader`.
- **Default GL accounts** — configurable AR account, AP account, revenue account, COGS account (override the hardcoded defaults per tenant).
- **Document number formats** — customisable format strings with `{prefix}`, `{YYYY}`, `{MM}`, `{seq:04d}` tokens. Live preview in settings.
- **Payment terms CRUD** — add custom Net-N terms from the settings page.
- **Onboarding checklist** — dismissible setup card on the dashboard for new tenants. Steps: upload logo, set payment terms, add first customer, create first invoice, bank account.
- **Audit log tabs** — Timeline (grouped by day), By User, By Entity, CSV export. Filterable by date range and entity type.

### Multi-tenant SaaS
- **Self-service signup** creates an isolated tenant + seeded Chart of Accounts.
- **RBAC** — `owner | admin | accountant | viewer`. First user is `owner`. `WriteUserDep` guards every mutating endpoint.
- **Team & multi-user** — multiple users per tenant. Admin creates accounts with temp passwords or sends invite links (7-day expiry, tokenized). Roles, activate/deactivate, reset passwords. Last-active-owner guard.
- **User profile** — edit name & phone, change password, upload avatar (PNG/JPEG/GIF/WebP ≤ 5 MB).
- **Tenant isolation** at the data layer — every query filters by `tenant_id`; cross-tenant reads return 404.
- **Audit log** — every mutation writes a row (user, action, entity, before/after JSON).

### Auth & API hardening
- **JWT + HttpOnly cookie** — login returns both a Bearer token and sets an `eb_access` HttpOnly cookie.
- **CSRF protection** — double-submit-cookie. Cookie-authenticated mutations must echo `eb_csrf` in `X-CSRF-Token`.
- **Login throttle** — DB-backed `LoginAttempt` table, 10 attempts per IP per 60 s rolling window.
- **Idempotency keys** — POST/PUT/PATCH/DELETE with `Idempotency-Key` header are cached by `(tenant, key)`.
- **API versioning** — every endpoint at `/api/*` and `/api/v1/*`.
- **Atomic numbering** — invoice/bill numbers from `SequenceCounter` with `SELECT FOR UPDATE`.

### Manufacturing track (V2)

For tenants with `business_model = manufacturing`: multi-location inventory, Bills of Material (versioned recipes), Rate Plans (value-addition pricing), Goods Receipt Note (custodial), Production Order lifecycle (draft→started→completed→delivered→billed) with full GL postings at each stage, manufacturing reports (dashboard, WIP aging, production summary, customer custody).

### Telecom Franchise track (V3)

For tenants with `business_model = telecom_franchise`: 56-account franchise CoA, Tracker wallet & load orders (3% uplift), MSR→RSO→Retail distribution chain, SIM inventory & activations, FCA targets, Mobile Money agency, Postpaid billing, Commission reconciliation, Franchise fee amortisation & royalty. 23 dedicated `tc_*` tables, 9 telecom reports.

---

## Getting started

### Prerequisites
- Python 3.11+
- Node.js 20+ (LTS) — Linux binary required; on WSL2, `dev.sh` auto-resolves the correct binary
- npm

### One-shot dev script

```bash
git clone https://github.com/bilalpiaic/Easy-Books.git
cd Easy-Books

# Backend dependencies
cd backend && uv sync    # or: pip install -r requirements.txt
cd ..

# Frontend dependencies
cd frontend && npm install
cd ..

# Start backend + frontend together (seeds demo data automatically)
./dev.sh
```

Backend: http://localhost:8000 (API docs at `/docs`)  
Frontend: http://localhost:3000

Press `Ctrl-C` once to stop both cleanly.

### First-time signup

Open http://localhost:3000/signup, fill in your name, company, email, and a password (≥ 8 chars). A new tenant is created with a default Chart of Accounts; you're auto-logged-in as `owner` of that tenant.

### Demo accounts (pre-seeded)

Five demo tenants are auto-created on first run, one per business model. `dev.sh` populates each with rich mock data covering a full year of activity (idempotent — safe to re-run):

| Email | Password | Model |
|-------|----------|-------|
| `demo.simple@easy-books.app` | `demo1234` | Simple invoicing |
| `demo.services@easy-books.app` | `demo1234` | Services / recurring revenue |
| `demo.trader@easy-books.app` | `demo1234` | Inventory / buy-and-resell |
| `demo.manufacturing@easy-books.app` | `demo1234` | Manufacturing / value-addition |
| `demo.telecom@easy-books.app` | `demo1234` | Telecom Franchise |

Each demo tenant contains **100 invoices, 100 bills, 70 payments received, 70 bill payments, 25 customers, 25 vendors, 3 bank accounts, 4 payment terms, 6 recurring templates**, plus 60+ manual journal entries covering all COA accounts (rent, salaries, depreciation, GST settlement, etc.) spread across the past 365 days. Manufacturing tenant additionally has 50 BoMs, 50 GRNs, 50 production orders, 50 rate plans.

To seed manually (or re-seed after a DB reset):

```bash
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
```

### Environment variables

| Var | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Connection string. `postgres://…` is rewritten to `postgresql://…`. | SQLite at `backend/database.db` |
| `JWT_SECRET_KEY` | HMAC secret for JWT signing. **Required in production**. | Insecure default in dev |
| `APP_ENV` | `development` or `production`. Affects cookie `Secure` flag, JWT secret check. | `development` |
| `FRONTEND_ORIGIN` | Comma-separated CORS allow-list. | `http://localhost:3000` |
| `UPLOAD_ROOT` | Filesystem root for uploaded files (attachments, avatars). | `uploads` |
| `SEED_COMPANY_NAME` | Default company name for the first tenant. | `My Company` |

---

## Architecture

```
backend/
├── main.py                  ← FastAPI bootstrap (~90 lines): middleware, routers
├── models.py                ← SQLModel tables (incl. PaymentTerm, BankAccount)
├── auth.py                  ← JWT + bcrypt
├── db.py                    ← engine, seed_data, default CoA + payment terms
├── routers/                 ← 32 domain routers
│   ├── common.py            ← shared deps (SessionDep, CurrentUserDep, WriteUserDep, AdminUserDep)
│   ├── auth.py              ← signup, login, logout, /me, profile, avatar, change-password
│   ├── users.py             ← team management (admin+): create/invite/role/activate/reset-password
│   ├── invoices.py          ← CRUD + bulk actions + draft editing
│   ├── bills.py             ← CRUD + bulk actions + draft editing
│   ├── payments.py          ← multi-allocation payments received + bill payments
│   ├── payment_terms.py     ← CRUD payment terms
│   ├── tax_codes.py         ← CRUD tax codes
│   ├── exchange_rates.py    ← FX rate catalog
│   ├── recurring.py         ← recurring templates + run-due
│   ├── bank_accounts.py     ← bank accounts + CSV import
│   ├── reconciliations.py   ← per-period bank reconciliation
│   ├── periods.py           ← accounting period close/reopen
│   ├── transactions.py      ← manual JV + reversal
│   ├── reports.py           ← dashboard + trial-balance + income-statement + balance-sheet + cash-flow + tax
│   ├── aging.py             ← AR/AP aging buckets (mounted BEFORE invoices/bills routers)
│   ├── subledger.py         ← customer/vendor ledger + statement; product stock-card
│   ├── settings.py          ← company profile, logo, default GL accounts, number formats
│   ├── audit.py             ← audit log with date/user/entity filters
│   ├── imports.py           ← CSV bulk import with validate + commit
│   └── …                    ← manufacturing, telecom, stock locations, attachments
├── services/
│   ├── posting.py           ← THE central GL writer (invariant enforcer)
│   ├── inventory.py         ← WAvg cost + reverse helpers
│   ├── tracker_posting.py   ← telecom tracker/load/RSO/SIM JVs
│   ├── franchise_posting.py ← mobile-money/postpaid/commission/franchise JVs
│   ├── fx.py                ← exchange-rate lookup with inverse fallback
│   └── money.py             ← Decimal helpers, ROUND_HALF_EVEN
├── scripts/seed_demo.py     ← full-year data seeder: 100 invoices/bills, all COA accounts
└── tests/                   ← 128 pytest tests

frontend/src/
├── app/(dashboard)/
│   ├── dashboard/           ← KPIs, cash tile, AP-due tile, AR aging chart, onboarding checklist
│   ├── invoices/            ← list with filter/sort/bulk/aging; [id]/ detail with breadcrumb, notes, Edit
│   ├── bills/               ← list with filter/sort/bulk/aging; [id]/ detail
│   ├── payments-received/   ← multi-allocation modal; [id]/ detail + print
│   ├── bill-payments/       ← multi-allocation modal; [id]/ detail + print
│   ├── customers/           ← list; [id]/ledger/; [id]/statement/ (printable)
│   ├── vendors/             ← list; [id]/ledger/; [id]/statement/ (printable)
│   ├── products/            ← list with low-stock filter; [id]/stock-card/
│   ├── entry/               ← manual JV
│   ├── journal/             ← GL journal list; [id]/ detail with source-doc links
│   ├── ledger/              ← General Ledger running balance
│   ├── recurring/           ← recurring templates: list, create, edit, deactivate, Run Now
│   ├── trial-balance/ pl/ balance/ cashflow/ tax/
│   ├── coa/                 ← Chart of Accounts editor
│   ├── bank-accounts/ reconciliations/
│   ├── settings/            ← company profile, logo, payment terms, default GL accounts, number formats, audit log
│   ├── profile/             ← name/phone, avatar, password, account info
│   ├── team/                ← members list, add/invite, role/activate/reset
│   ├── manufacturing/       ← V2: production floor, BoMs, rate plans, GRN, production orders
│   ├── telecom/             ← V3: tracker, RSO, SIM, FCA, MM, postpaid, commissions, franchise
│   └── guide/ workflow/     ← in-app user guide + visual flowcharts
├── components/
│   ├── Sidebar.tsx           ← adaptive: manufacturing/telecom/team sections gated on model & role
│   ├── FilterBar.tsx         ← reusable filter row: search, status multi-select, date range
│   ├── SortableHeader.tsx    ← sortable <th> with chevron icons
│   ├── BulkActionBar.tsx     ← floating bar for bulk operations
│   ├── LineItemsTable.tsx    ← line-item editor with optional per-line tax column
│   ├── PrintHeader.tsx       ← branded print output with logo, address, company info
│   ├── AttachmentPanel.tsx   ← document attachments (upload, preview, delete)
│   └── …                     ← Pagination, SkeletonRow, CsvImportButton, DocLink
└── lib/                      ← apiFetch, auth, utils
```

---

## Development workflow

```bash
# Run all backend tests (128 tests)
cd backend && PYTHONPATH=. uv run pytest -q

# Type-check the frontend
cd frontend && npx tsc --noEmit

# Build the frontend (zero-error check)
cd frontend && npx next build

# Re-seed demo data (idempotent)
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
```

**Schema changes:** There is no migration tool. `SQLModel.metadata.create_all()` adds new tables on startup but does not alter existing ones. For columns added to an existing table, run `ALTER TABLE` on the SQLite file directly, or delete `backend/database.db` to get a fresh seeded DB.

**Router ordering:** The `aging.router` must be registered before `invoices.router` and `bills.router` in `main.py` — otherwise FastAPI's `/{invoice_id}` route captures `GET /api/invoices/aging` before the aging handler.

---

## Status

**Shipped sprints:**

| Sprint | Features |
|--------|---------|
| Sprint 1 | Draft invoice/bill editing · Multi-allocation payment modal · Dashboard cash + aging · Column sorting + filter bar · Overdue auto-flag |
| Sprint 2 | Notes/memo on invoices+bills · Company profile (logo, address) in settings + PrintHeader · Payment terms (Net-15/30/60/DOR) on customers, vendors, invoices, bills |
| Sprint 3 | Bulk actions (mark-sent, void, delete) · Recurring journal UI · Low-stock filter + row highlighting · Customer/vendor statement pages |
| Sprint 4 | Default GL accounts in settings · Per-line tax codes on invoices+bills · CSV import preview (validate + commit) |
| Sprint 5 | Onboarding checklist · Audit log tabs (timeline, by-user, by-entity, CSV export) · Document number format with year/month tokens |
| Sprint 6 | Browser tab `<title>` · "Back to list" breadcrumbs on all detail pages · Keyboard shortcut `N` for New · Empty-state CTAs on all list pages |
| Seed upgrade | 100 invoices/bills per tenant · Full 365-day date scatter · All COA accounts covered · Bank accounts · Payment terms · Notes/memos on all documents |
| Sprint 7–12 | Bank-rec zero-difference · Credit Notes · Comparative P&L/Balance Sheet · Multi-currency UI · Fixed Assets + depreciation · Purchase Orders · Analytic accounts · Deferred revenue · FIFO option · Budgets vs Actual · Stripe links · Alembic · Server-side PDF · FX revaluation · SMTP email · tenant-aware guide/workflow · demo seeding for all new modules |

**Backend test suite:** 139 tests pass (`PYTHONPATH=. uv run pytest -q`)

**Not yet shipped:**
- Multi-currency on payments (invoice currency is snapshot at issue)
- Production-order reversal helper, partial delivery, scrap write-off
- Payroll module (IAS 19) — manual JV only today
- E2E tests (Playwright)

---

## Further reading

- [`BLUEPRINT.md`](./BLUEPRINT.md) — complete project blueprint: every model, every endpoint, every flow, every decision.
- [`WORKFLOW.md`](./WORKFLOW.md) — full accounting workflows, GL Dr/Cr maps, report-linking matrix, API catalog.
- [`DEPLOYMENT.md`](./DEPLOYMENT.md) — Vercel deployment for backend + frontend.
- In-app **User Guide** (`/guide`) — interactive tabbed walkthrough for every feature.
- In-app **Workflow** (`/workflow`) — visual flowcharts for each accounting cycle.

---

## License

MIT. See [`LICENSE`](./LICENSE).
