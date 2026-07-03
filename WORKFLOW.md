# Easy-Books — Workflow & Architecture Guide

> Multi-tenant double-entry accounting SaaS
> FastAPI + SQLModel (backend) · Next.js 16 + React 19 + Tailwind v4 (frontend)
> SQLite for dev, PostgreSQL-ready for prod · JWT + HttpOnly cookie auth · RBAC · CSRF · idempotency · multi-currency

---

## TABLE OF CONTENTS

1. [Snapshot](#1-snapshot)
2. [International Accounting Standards Alignment](#31-international-accounting-standards-alignment)
3. [Getting Started: Demo Tenants & Customization](#32-getting-started-demo-tenants--customization)
4. [Architecture](#2-architecture)
5. [Data Model](#3-data-model)
6. [The Accounting Cycles](#4-the-accounting-cycles)
   - 6.1 [Sales / Receivables](#41-sales--receivables)
   - 6.2 [Purchase / Payables](#42-purchase--payables)
   - 6.3 [Inventory (Weighted-Average)](#43-inventory-weighted-average)
   - 6.4 [Banking & Reconciliation](#44-banking--reconciliation)
   - 6.5 [Manual Journal Entries](#45-manual-journal-entries)
   - 6.6 [Period-End Close](#46-period-end-close)
   - 6.7 [Manufacturing (V2)](#47-manufacturing-v2)
   - 6.8 [Telecom Franchise (V3)](#48-telecom-franchise-v3)
   - 6.9 [Healthcare / Hospital (V3.0)](#49-healthcare--hospital-v30)
7. [Cross-Cutting Features](#5-cross-cutting-features)
   - 7.1 [Multi-Currency & FX](#51-multi-currency--fx)
   - 7.2 [Tax Codes](#52-tax-codes)
   - 7.3 [Payment Allocations](#53-payment-allocations)
   - 7.4 [Recurring Entries](#54-recurring-entries)
   - 7.5 [Bank Statement Import](#55-bank-statement-import)
   - 7.6 [Reversal Semantics](#56-reversal-semantics)
   - 7.7 [Sub-Ledgers & Audit-Trail Drill-Down](#57-sub-ledgers--audit-trail-drill-down)
8. [Report Catalog](#7-report-catalog)
9. [API Endpoint Catalog](#8-api-endpoint-catalog)
10. [Security Model](#9-security-model)
    - 10.1 [Multi-Tenant Isolation](#91-multi-tenant-isolation)
    - 10.2 [RBAC](#92-rbac)
    - 10.3 [Auth: JWT + HttpOnly Cookie](#93-auth-jwt--httponly-cookie)
    - 10.4 [CSRF (Double-Submit-Cookie)](#94-csrf-double-submit-cookie)
    - 10.5 [Login Throttle](#95-login-throttle)
    - 10.6 [Period Lock](#96-period-lock)
    - 10.7 [Idempotency Keys](#97-idempotency-keys)
11. [Engineered Invariants](#10-engineered-invariants)
12. [Verification & Smoke Tests](#11-verification--smoke-tests)
13. [Default Chart of Accounts](#12-default-chart-of-accounts)
14. [Migration History](#13-migration-history)

---

## 1. SNAPSHOT

| Aspect | Detail |
|---|---|
| Purpose | Multi-tenant double-entry accounting — GL, invoicing, billing, inventory, banking, multi-currency, tax, period close |
| Accounting compliance | **∑Dr = ∑Cr exact** (Decimal NUMERIC(18,4)), **IAS 2 / ASC 330** inventory at WAvg cost, **IAS 21** multi-currency with FX-rate snapshots, **GST output/input** separated, **period-lock** enforced at posting service, **IAS 1** audit-trail traceability via hyperlinked GL |
| Demo tenants | 7 pre-seeded: simple/services/trader/manufacturing/telecom_franchise/pra_einvoice/hospital (email: demo.{model}@easy-books.app, password: demo1234) — each populated with 100 invoices, 100 bills, 70 payments, 25 customers, 25 vendors, 3 bank accounts, 4 payment terms, 6 recurring templates; hospital tenant additionally has 5 doctors, 4 wards, 50 patients, 200 OPD tokens, 20 admissions, 80 lab orders |
| Customization | Business tagline + company branding per tenant via `/dashboard/settings`; **per-user dashboard layout** — drag/resize/add/remove widgets, per-breakpoint (desktop/tablet/phone), saved per user account (v2.5+); **Section Hub Pages** (`/receivable`, `/payable`, `/inventory`, `/banking`) — command-centre views with aging/stock/balance bands (v2.7+); **Dark Mode + 5 color themes** (v2.7+); **multi-language** EN/UR/ZH with RTL support (v2.7+); **PRA portal mode** — admin/owner can toggle between Full Accounting view and a clean 7-item PRA-focused sidebar; non-admin users always land in portal mode (v2.8.1+); **Ctrl+K universal search** — 3-tier command palette (open tabs → nav index → API, 8 entity types, prefix filter syntax, recent searches) (v3.0+); **in-app auto-update** — `UpdateAvailablePopup` + `UpdateProgressScreen` with 4-phase progress and changelog (v3.0+); **mobile navigation** — `BottomNav`, `FAB`, `MoreDrawer` (v3.0+); **QB token system** — all 155+ pages migrated to CSS custom properties, dark mode entirely token-driven (v3.0+) |
| Multi-tenancy | One `Tenant` per business; every record carries `tenant_id`; queries scope to it; central posting service double-checks account ownership |
| Auth | JWT bearer **and** HttpOnly cookie; CSRF on cookie path; bcrypt password hashing |
| Roles | `owner | admin | accountant | viewer` (CHECK-constrained at DB) |
| Storage | SQLite (dev) → Postgres (prod) via SQLModel; **Alembic** migrations are the schema source of truth (`create_all()` still bootstraps a fresh dev DB; installers run `alembic upgrade head` on launch) |
| Reports | Live from `JournalEntry`; closed periods read materialised `AccountBalance` (**ISA 230** audit documentation) |
| API surface | 80+ endpoints, mounted twice at `/api/*` and `/api/v1/*` |

---

## 1.1 UI SYSTEM — DEVELOPER REFERENCE (v2.7)

### Theme system

`ThemeContext` (`src/context/ThemeContext.tsx`) manages display mode and color theme globally.

- **Modes:** `light` | `dark` | `system`. Stored in `localStorage` key `eb.theme`. Applied as `[data-theme]` on `<html>`. An inline anti-flash script in `layout.tsx` sets this attribute before hydration so there is no visible flash.
- **Colors:** `gold` (default) | `emerald` | `sapphire` | `rose` | `slate`. Stored in `localStorage` key `eb.color`. Applied as `[data-color]` on `<html>`. CSS custom properties in `globals.css` provide per-theme accent variables.
- When adding a new component: use Tailwind classes that respect the `[data-theme]` and `[data-color]` selectors; do not hard-code hex colors for interactive or accent elements.

### Internationalisation (i18n)

`LocaleContext` (`src/context/LocaleContext.tsx`) wraps `react-i18next`. Translation files are in `src/i18n/locales/{en,ur,zh}/`.

- **Adding a translated string:** add the key to all three locale JSON files; use `const { t } = useTranslation('namespace')` in the component.
- **RTL:** `locale === "ur"` sets `document.dir = "rtl"` automatically — no manual RTL CSS is needed in new components as long as they use logical CSS properties or standard Tailwind classes.
- **Namespaces:** `nav`, `section`, `common`, `status`, `dashboard`, `hub`, `auth`, `settings`, `col`, `page`.
- The globe icon in the header (`components/Header.tsx`) opens the language picker; preference is saved to both `localStorage` and `/api/settings` (`app_language`).

### Mobile layout rules

- Use `text-xl sm:text-3xl` for page `<h1>` titles.
- Use `grid-cols-2 sm:grid-cols-3` (or `sm:grid-cols-4`) for stats grids — never bare `grid-cols-3` or `grid-cols-4`.
- Add `flex-wrap` to all button toolbars.
- Wrap line-item tables in `<div className="overflow-x-auto">` and set `min-w-[640px]` on the inner `<table>`.
- Form grids: use `grid-cols-1 sm:grid-cols-2` (or `sm:grid-cols-3`) so fields stack on phones.

### GlobalSearch — Ctrl+K Command Palette (v3.0)

`components/GlobalSearch.tsx` — portal overlay (mounted on `<body>`) opened by Ctrl+K or the TopNav search icon (`search:open` custom event).

**3-tier search:**

| Tier | Latency | Source |
|------|---------|--------|
| Open tabs | 0 ms | `useTabs` context |
| Nav index | 0 ms | `lib/navIndex.ts` — Layer 1: sidebar nav pages; Layer 2: 14 quick-action shortcuts; Layer 3: 22 report pages with keyword aliases |
| API | 150 ms debounce | `GET /api/search?q=&types=` — 8 entity types |

**Prefix filter syntax** (typed before the query):

| Prefix | Entity type |
|--------|-------------|
| `inv:` | Invoices |
| `cust:` | Customers |
| `tab:` | Open tabs |
| `acc:` | Accounts |
| `emp:` | Employees |
| `jv:` | Transactions |
| `rpt:` | Reports / utility pages |
| `new:` | Quick-action shortcuts |
| `bill:` | Bills |
| `prod:` | Products |
| `vendor:` | Vendors |

Results carry `label`, `sub`, `href`, `date`, `amount`, `status` badge (color-coded). Recent searches stored in `localStorage` key `eb.recent-searches` (max 5). Empty state shows quick-action chips + prefix hint bar. Keyboard: Ctrl+K opens, ArrowUp/Down navigates, Enter follows href, Esc closes.

### TopNav — Portal Dropdowns + Dark Nav Inversion (v3.0)

`components/TopNav.tsx` was fully rewritten:

- Scrollable tab strip with `overflow-x: auto scrollbar-hide`; `ResizeObserver` shows left/right chevron scroll arrows + gradient fades when content overflows.
- `More ▾` dropdown lives outside the scroll container — always reachable.
- Dropdowns use `ReactDOM.createPortal` + `getBoundingClientRect()` for `position: fixed` placement, avoiding `overflow-x` clipping.
- CSS vars `--nav-bg`, `--nav-text`, `--nav-sub`, `--nav-dim`, `--nav-sep`, `--nav-hover`, `--nav-active` flip in `[data-theme="dark"]` so the nav bar is light-on-dark (cream/charcoal) — visually distinct from the dark page background.
- **Icon + label items (v3.1):** every section-dropdown item renders `<item.icon>` (from the `SUB_NAV` `NavItem.icon` field) + label at uniform weight and padding. `SECTION_OVERVIEW` rows carry their own icons and are styled as normal menu items — never as headings (#132). The mobile `MoreDrawer` items render the same icon treatment.

### Freeze panes — .table-freeze / .freeze-col (v3.1)

`globals.css` FREEZE PANES block. `.table-freeze` on the div directly wrapping a `<table>` caps its height (`max-height: var(--table-freeze-h, calc(100dvh - 240px))`) so the wrapper becomes the vertical scrollport — this is what makes the sticky `<thead>` and sticky `<tfoot>` (totals row) actually engage; a plain `overflow-x-auto` wrapper grows with content and never scrolls vertically, so sticky headers inside it silently do nothing. Add `.freeze-col` on the same wrapper to also pin the first column (corner cell z-25 > thead z-20 > column cells z-5). Rollout: aging AR/AP, customer/inventory performance, GL ledger, product ledger, report-builder grid, healthcare + manufacturing reports, customer/vendor statements, telecom tracker. **Every sticky rule is reset under `@media print`** — print depends on `thead { display: table-header-group }` for per-page header repetition, so any new freeze rule must be added to the print reset too.

### KpiCard — unified dashboard stat tile (v3.1)

`components/dashboard/KpiCard.tsx` replaced the divergent `PrimaryKpi`/`SecondaryKpi`. Props: `title`, `value` (null → shimmer), optional `icon` (layout switches: icon top-left / title bottom-left / value bottom-right when present; title top-left / value bottom-right when absent), `tone` (`green|red|amber|emerald|blue|neutral` colored-tile variants), `href` (renders a `Link`), `sub`, `badge`, `iconClass`, `valueClass`. Neutral tone uses CSS theme variables (`--bg-card`, `--border`, `--text-primary`) — never hardcode hex in stat tiles; dark mode depends on it.

### In-App Auto-Update System (v3.0)

**`UpdateAvailablePopup.tsx`** — shown by `DashboardLayout` on every mount (admin/owner only) when `GET /api/system/update/status` reports new commits behind `HEAD`. Actions:
- **Update Now** — launches the update sequence
- **Later** — session-dismissed (`localStorage` key `eb.update-later-session`)
- **Skip version** — SHA-keyed persistent dismiss (`localStorage` key `eb.update-skip`)

**`UpdateProgressScreen.tsx`** — fullscreen portal during an active update:
- Animated SVG ring (spinning) with Zap icon
- 4-phase text labels: **Pull → Compile → Bundle → Start**
- Progress bar clamps to 90 % until the commit hash changes
- Polls `GET /version.json` every 5 s; success → green ring + CheckCircle + "What's New" from `/api/system/update/changelog`; error → AlertCircle + manual CLI instructions

**Backend:** `GET /api/system/update/status` (GitHub Commits API), `POST /api/system/update` (`git pull` + migrations + rebuild), `GET /api/system/update/changelog?since=<sha>&limit=8`.

**Post-update:** `eb.just-updated` in localStorage triggers a congratulations toast after reload.

### Mobile Navigation — BottomNav, FAB, MoreDrawer (v3.0)

- **`BottomNav.tsx`** — fixed bottom bar with core nav items; hidden at `sm:` breakpoint and above.
- **`FAB.tsx`** — floating action button (bottom-right) for quick new-entry creation; expands to show module-gated "New…" options (`invoice`, `bill`, `journal entry`, etc.).
- **`MoreDrawer.tsx`** — slide-up drawer from the "More" tab in `BottomNav`; renders the full nav list filtered by `installedModules`; closes on backdrop tap.

### QB UI Token System (v3.0)

All 155+ pages and components have been migrated from hardcoded hex to CSS custom properties in `globals.css`:
- **Page tokens:** `--bg-page`, `--bg-card`, `--border`, `--text-primary`, `--text-secondary`, `--text-muted`, `--primary`, `--primary-light`, `--primary-dark`
- **Nav tokens:** `--nav-bg`, `--nav-text`, `--nav-sub`, `--nav-dim`, `--nav-sep`, `--nav-hover`, `--nav-active`

In `[data-theme="dark"]` all tokens flip — dark mode is now entirely token-driven with no scattered `dark:` Tailwind class exceptions.

---

## 2. ARCHITECTURE

### 2.1 Request lifecycle

```
USER ACTION (browser POST or SDK call)
    │
    ▼
┌──────────────────────────────────────────────┐
│ FastAPI middleware stack (outer-most first)  │
│  1. CsrfMiddleware                           │
│     • If cookie auth + mutating method:      │
│       require X-CSRF-Token == eb_csrf cookie │
│     • Bearer-header callers exempt           │
│  2. IdempotencyMiddleware                    │
│     • If Idempotency-Key + 2xx prior:        │
│       return cached body                     │
│  3. CORSMiddleware                           │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│ Dependency resolution                        │
│  • SessionDep  → DB connection               │
│  • CurrentUserDep / WriteUserDep             │
│    → decode JWT from Bearer OR cookie        │
│    → load User, enforce min role             │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│ Endpoint handler                             │
│  1. Pydantic validates body                  │
│  2. tenant_id filter on every query          │
│  3. Business logic                           │
│  4. services.posting.post_transaction(...)   │
│     ↳ Σdr==Σcr · no neg · no both-sided      │
│     ↳ period-lock · account-tenant ownership │
│  5. log_audit(...)                           │
│  6. session.commit()                         │
└──────────────────────────────────────────────┘
    │
    ▼ JSON response (idempotency middleware caches if header was set)
```

### 2.2 Folder layout

```
backend/
├── main.py                ← bootstrap: middleware, routers, /api/v1 aliases
├── models.py              ← SQLModel tables (28 tables current)
├── auth.py                ← JWT + bcrypt + secret hardening
├── db.py                  ← engine, seed_data, default CoA
├── scripts/seed_demo.py
├── routers/               ← 21 domain routers
│   ├── common.py          ← SessionDep, CurrentUserDep, WriteUserDep,
│   │                        require_min_role, next_number, get_or_create_account
│   ├── auth.py            ← signup/login/logout/me + DB throttle + CSRF cookie
│   ├── invoices.py · bills.py · payments.py
│   ├── tax_codes.py · exchange_rates.py · recurring.py
│   ├── bank_accounts.py · bank_imports.py · reconciliations.py
│   ├── periods.py         ← list/lock/close/reopen
│   ├── transactions.py    ← manual JV + reverse-with-unwind + read
│   ├── reports.py         ← TB · ledger · P&L · BS · CF · tax · dashboard
│   ├── accounts.py · customers.py · vendors.py · products.py
│   ├── audit.py · settings.py · imports.py · aging.py
└── services/              ← pure logic, no FastAPI imports
    ├── posting.py         ← central GL writer (invariants here)
    ├── inventory.py       ← WAvg cost · receipt/consumption · reverse
    ├── fx.py              ← rate_to_base with inverse fallback
    ├── money.py           ← D() · money() · ROUND_HALF_EVEN
    ├── csrf.py            ← double-submit middleware
    └── idempotency.py     ← response-cache middleware

frontend/src/app/(dashboard)/
├── dashboard/             ← KPI cards + 12-month charts
├── entry/                 ← manual JV form (Dr = Cr live tally)
├── journal/ · ledger/     ← read-only GL views
├── trial-balance/         ← Dr/Cr per account, warning if imbalanced
├── pl/ · balance/ · cashflow/ · tax/
├── invoices/ · bills/     ← list + create + status + aging panels
├── payments-received/ · bill-payments/
├── customers/ · vendors/ · products/
├── coa/                   ← Chart of Accounts CRUD
├── bank-accounts/ · reconciliations/
├── settings/              ← company name, fiscal year, prefixes, currency
├── workflow/              ← visual flowcharts (this file in pictures)
└── guide/                 ← interactive user guide
```

---

## 3.1 INTERNATIONAL ACCOUNTING STANDARDS ALIGNMENT

Easy-Books implements the following international accounting standards and best practices:

| Standard | Implementation | Evidence |
|---|---|---|
| **IAS 1** (Presentation of Financial Statements) | Consistent ledger presentation; all GL items traced to source documents | Every JournalEntry links back to Invoice/Bill/Payment/GRN via reverse-resolution lookup; clickable GL hyperlinks to source docs |
| **IAS 2** (Inventory) | Weighted-Average cost method; no negative stock | `services/inventory.py`: `record_purchase()` appends layer; `consume_stock()` relieves at running WAvg; FIFO layer depletion |
| **IAS 8** (Accounting Policies) | Consistent methods across periods; change tracking via audit log | Audit trail logs every transaction mutation (INSERT/UPDATE/DELETE); period-close materialises balances immutably |
| **IAS 18 / IFRS 15** (Revenue Recognition) | Revenue posted on invoice issue; partial payments tracked separately | Invoice `status ∈ {draft, issued, partial, paid, overdue}`; allocations preserve invoice total vs paid amount |
| **IAS 21** (Effects of Changes in Foreign Exchange Rates) | FX rates snapshot at transaction date; no retroactive revaluation (V1) | `Invoice/Bill.currency + .exchange_rate` captured at issue; `ExchangeRate(date, from, to, rate)` catalog with date fallback |
| **IAS 32 / IFRS 9** (Financial Instruments) | Separate asset/liability/equity classification; payables credit-normal | `Account.type ∈ {Asset, Liability, Equity, Revenue, Expense}`; AP ledger shows credit-normal (positive = we owe) |
| **ISA 230** (Audit Documentation) | Complete audit trail; reperformance from any JE to source | Every GL line hyperlinks to its original document (Invoice, Bill, Payment, GRN); time-stamped mutations in audit log |
| **ISA 315** (Understanding the Entity) | Internal controls enforced in code (not UI) | Period-lock prevents posting into closed periods; tenant_id scoped queries prevent cross-tenant reads; central posting service is sole GL writer |
| **IFRS 16** (Leases) | Custodial goods tracking for manufacturing (V2) | `StockLocation.type ∈ {own, customer_custodial, wip}`; memo account pair `1210/2150` for customer goods on hand |

**Compliance checks embedded in posting service** (`services/posting.py`):
- ✓ `∑debit == ∑credit` exact (Decimal precision)
- ✓ No negative amounts in any line
- ✓ No both-sided rows (Dr > 0 AND Cr > 0)
- ✓ No posting into locked periods
- ✓ Account belongs to posting user's tenant
- ✓ JV number unique per tenant per period

---

## 3. DATA MODEL

```
                                Tenant
                                  │ 1..N
       ┌──────────┬───────────────┼──────────────┬─────────┬─────────┐
       ▼          ▼               ▼              ▼         ▼         ▼
     User      Account     SequenceCounter   ExchangeRate AuditLog Settings
   (role)    (CoA)                                                  (kv)

  Customer  Vendor   Product────┐
     │       │          │       │ 1..N
     │       │          │       ▼
     │       │          │   InventoryLayer  (one per stock receipt)
     │       │          │
     ▼       ▼          ▼
  Invoice  Bill   ─┬─ InvoiceLine
     │      │     └─ BillLine
     │      │
     │      ▼
     │   ┌──────────────┐
     ▼   │ Transaction  │── JournalEntry  (debit XOR credit > 0; CHECK)
  PaymentReceived  ──┐    └─┬────────────┘
  BillPayment     ───┤      │ 1..N
                     │      ▼
                     │   Account
                     ▼
              PaymentAllocation  (invoice_id XOR bill_id; amount > 0)

  AccountingPeriod ─── AccountBalance   (materialised on close)
                          │
                          └ TaxCode (output|input)

  BankAccount ─── Reconciliation ─── ReconciliationLine
                  │
  BankStatementImport (file_hash unique per account)
        │ 1..N
        ▼
  StatementLine ── matched_transaction_id ─▶ Transaction

  RecurringTemplate (frequency, next_run, entries_json)

  IdempotencyKey (tenant + key unique; cached response body)
  LoginAttempt (ip, attempted_at; sliding window throttle)

  ── Manufacturing (V2) ──────────────────────────────────────────────
  StockLocation (own | customer_custodial | wip)
        ▲                ▲
        │                │
  InventoryLayer ──── StockMovement   (event log; reconstructs layers)
   (per product +
    location, with
    owner_customer_id
    + lot_no)

  BomHeader ─── BomLine (own_stock | customer_supplied; versioned)
  RatePlan ─── CustomerRatePlan (many-to-many, only one active per cust)

  GoodsReceiptNote ─── GRNLine          (custodial intake; optional memo JE)
  ProductionOrder (state machine: draft→started→completed→delivered→billed)
        │                                                    │
        ▼                                                    ▼
   (links bom_id, customer_id,                          (invoice_id once
    rate_plan_id, output_qty,                            billed — back-
    own_material_cost, output_unit_cost)                 reference to Invoice)
```

**Read it as:** every business is a `Tenant`. Every operational document (invoice, bill, payment, manual JV) ultimately writes a `Transaction` (the JV header) with 2+ `JournalEntry` rows. Reports aggregate `JournalEntry` directly.

### 3.1 Settings & Customization

| Field | Purpose | Type | IAS/IFRS |
|---|---|---|---|
| `company_name` | Business legal entity name | String | **IAS 1.49** — entity identification |
| `business_tagline` | Tagline/motto (e.g., "Double-Entry Accounting") | String | **IAS 1.45** — presentation consistency |
| `tax_id` | Tax identification number / EIN | String | **IAS 1.49** — statutory reporting |
| `currency` | Base currency for all transactions | Code (PKR/USD/EUR/etc.) | **IAS 21** — functional currency |
| `fiscal_year_start` | Accounting year start month | Month | **IAS 1.49** — reporting period |
| `financial_statement_date` | Statement date preference | month_end \| quarter_end \| year_end | **IAS 1.49** |
| `invoice_prefix` / `bill_prefix` | Document numbering | String | **IAS 1.99** — document identification |

---

## 3.2 GETTING STARTED: DEMO TENANTS & CUSTOMIZATION

### Demo Tenant Initialization

**Both standalone script installs** (`install-and-run.*`) **and the desktop (Electron) app auto-load the 6 demo companies on first install** (`SEED_DEMO=true` default). Both run `scripts.autoseed_demo` after `alembic upgrade head`; the guard skips if any user already exists, so **updating an existing install is migrate-only — no demo data is added**. Set `SEED_DEMO=false` for a clean install with no demo data. Log in immediately with `demo1234` — no signup required.

**Settings → Sample / Demo Data** lets you **Load** or **Remove** the demo companies at any time on any install type. (Admin/owner only.)

**Dev / cloud installs** (`dev.sh` / hosted): Easy-Books auto-creates 6 pre-seeded demo tenants (one per business model) on first database run. `dev.sh` also seeds each with 50+ records per entity type:

| Tenant | Email | Model | Use Case |
|---|---|---|---|
| Demo Simple Co. | `demo.simple@easy-books.app` | Simple | Solo/micro-business (essentials only) |
| Demo Services Ltd. | `demo.services@easy-books.app` | Services | Agencies & consultancies (recurring revenue) |
| Demo Trading Co. | `demo.trader@easy-books.app` | Trader | Buy-and-resell (inventory + COGS) |
| Demo Mfg Co. | `demo.manufacturing@easy-books.app` | Manufacturing | Value-addition (BoMs, GRN, PO lifecycle) |
| Demo Telecom Co. | `demo.telecom@easy-books.app` | Telecom Franchise | Operator franchise — Tracker, RSO chain, FCA targets |
| Demo PRA Co. | `demo.pra@easy-books.app` | PRA e-Invoice | Pakistani retail — PRA eIMS, PKR, NTN/CNIC, PCT codes |

**Password (all):** `demo1234`

Each demo tenant receives:
- ✓ Seeded Chart of Accounts (22+ per model)
- ✓ Sequence counters (invoice, bill, GRN, PO numbers)
- ✓ Stock locations (MAIN + model-specific)
- ✓ Default business tagline: "Easy-Books · Double-Entry Accounting"

### Mock Data Population (Optional)

To populate demo tenants with realistic transactional data for QA/onboarding:

```bash
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
```

Each demo tenant receives:
- 25 Customers + 25 Vendors (with full contact info)
- 100 Invoices + 100 Bills (spread across past 365 days, never future-dated)
- 70 Payments Received + 70 Bill Payments (multi-invoice allocations)
- 3 Bank Accounts (Current, Savings, Payroll)
- 4 Payment Terms (Due on Receipt, Net 15, Net 30, Net 60)
- 6 Recurring Templates across all frequencies
- 60+ Manual Journal Entries cycling through all CoA accounts
- Manufacturing tenant: 12 BOMs, 12 Rate Plans, 12 GRNs, 12 Production Orders

**Script is idempotent:** re-running skips entities already present.

### Company Branding & Settings

Every tenant customises its profile via `/dashboard/settings`:

| Setting | Default | Display Location |
|---|---|---|
| Company Name | "My Company" | Header, all reports, print header |
| Business Tagline | "Easy-Books · Double-Entry Accounting" | Header + printed documents |
| Company Logo | — | Print header (img tag, served from `/uploads/`) |
| Address Lines, City, Country | — | Print header (**IAS 1.49** disclosure) |
| Phone, Website | — | Print header footer |
| Tax ID | "" | Reports footer |
| Currency | "PKR" | All monetary fields, reports |
| Fiscal Year Start | "January" | Period definitions, year-end close |
| Invoice / Bill number format | `{prefix}-{seq:04d}` | Supports `{YYYY}` and `{MM}` tokens, e.g. `INV-{YYYY}-{seq:04d}` → `INV-2026-0001` |
| Default GL Accounts | AR=1100, AP=2000, Revenue=4000, COGS=5010 | Auto-selected on invoice/bill create |

**Payment Terms** — managed via `/settings` → Payment Terms tab:

| Code | Name | Days |
|---|---|---|
| `RECEIPT` | Due on Receipt | 0 |
| `NET15` | Net 15 Days | 15 |
| `NET30` | Net 30 Days | 30 |
| `NET60` | Net 60 Days | 60 |

Assign a term to a customer or vendor; when creating an invoice/bill the due date auto-calculates (`issue_date + term.days`).

**Logo upload flow:**
1. Go to `/settings` → Company Profile → click logo upload zone
2. `POST /api/settings/logo` (multipart) → stores file in `backend/uploads/`
3. Setting key `logo_url` = `/uploads/<filename>`; `PrintHeader` renders `<img>` at top of every printed document

All settings are persisted per-tenant via `PATCH /api/settings` (**IAS 1.49** entity consistency).

---

## 4. THE ACCOUNTING CYCLES

**All accounting cycles comply with:**
- **IAS 1** — Presentation & classification (Dr/Cr, deferred revenue)
- **IAS 18 / IFRS 15** — Revenue recognition (invoice-at-issue method)
- **IAS 2** — Inventory valuation (Weighted-Average cost, FIFO depletion)
- **IAS 21** — FX effects (snapshot at transaction date, no retroactive revaluation in V1)
- **ISA 230** — Audit trail completeness (every GL item traces to source document)

---

### 4.1 SALES / RECEIVABLES (**IAS 18 / IFRS 15**)

Revenue is recognised on invoice issue; partial payments tracked separately per **IFRS 15.B2.1** (control of goods transfers to customer).

```
  CREATE CUSTOMER          ISSUE INVOICE              RECEIVE PAYMENT
       │                        │                            │
       │ POST /api/customers    │ POST /api/invoices         │ POST /api/payments-received
       ▼                        ▼                            ▼
  Customer row            Invoice + N lines            PaymentReceived
                          + Transaction (JV)           + Transaction (JV)
                          + JournalEntry × 3+          + JournalEntry × 2
                          + AuditLog                   + PaymentAllocation rows
                          + (optional) COGS JV         + Invoice.status derived
                          + Product.stock_qty -=         (paid | partial)
```

| # | Action | Page | Endpoint | DB writes | GL impact | Standard |
|---|---|---|---|---|---|---|
| 1 | Add customer | `/customers` | `POST /api/customers` | `Customer` | — | **IAS 1** |
| 2 | Issue invoice | `/invoices` | `POST /api/invoices` | `Invoice` + lines + `Transaction` + JEs (+ COGS sub-JV for stock) | **Dr AR · Cr Revenue · Cr GST Output** | **IFRS 15** |
| 3 | Receive payment | `/payments-received` | `POST /api/payments-received` | `PaymentReceived` + `Transaction` + JEs + `PaymentAllocation[]` | **Dr Cash/Bank · Cr AR** | **IAS 32** |
| 4 | View AR aging | `/aging/receivable` | `GET /api/invoices/aging` | — | Current/1–30/31–60/61–90/90+ buckets net of allocations; drill-down to customer ledger | **IAS 1.99** |
| 5 | Customer performance | `/customer-performance` | `GET /api/reports/customer-performance` | — | Revenue, invoice count, outstanding AR, avg days-to-pay per customer | **IAS 1** |

**On-hand display:** invoice line items show **On hand: N** for stock products, sourced live from `Product.stock_qty`, so you see available quantity at the point of entry.

**Invoice GL — service sale, 1000 + 17% GST, base currency:**
```
                              DEBIT       CREDIT
1100 Accounts Receivable     1,170.00
4000 Sales Revenue                       1,000.00
2200 GST Payable (Output)                  170.00
                             ─────────   ─────────
                             1,170.00    1,170.00 ✓  (IAS 1.44 — balanced)
```

**Invoice GL — stock sale, 3 units × 100 (cost 6/unit), base currency:**
```
JV #1 (sale):
                              DEBIT       CREDIT
1100 Accounts Receivable       300.00
4000 Sales Revenue                         300.00

JV #2 (COGS, separate JV):
                              DEBIT       CREDIT
5010 Cost of Goods Sold         18.00
1200 Inventory                              18.00

Side effects:
  Product.stock_qty -= 3
  InventoryLayer.qty_remaining -= 3 (FIFO depletion)
```

**Foreign-currency invoice (EUR 1000 at rate 1.10):**
```
Document stays in EUR:  Invoice.subtotal = 1000, currency=EUR, exchange_rate=1.10
GL posts in base USD:   Dr AR 1100.00 / Cr Revenue 1100.00
```

**Payment receipt (partial — pay 700 of 1000):**
```
                              DEBIT       CREDIT
1000 Cash in Hand              700.00
1100 Accounts Receivable                   700.00

Side effects:
  PaymentAllocation { invoice_id, amount=700 } row
  Invoice.status = 'partial'  (700 < 1000)
```

**Deferred revenue (IFRS 15 — services / subscriptions).** When an invoice line's product is flagged `is_deferred`, its net is credited to **Deferred Revenue (2300)** instead of Sales Revenue and a `DeferredRevenueSchedule` is originated over the product's `recognition_months` (`services/deferred.py`). Posting: `Dr AR / Cr Deferred Revenue (2300)` for the deferred portion `+ Cr Revenue` for any normal lines `+ Cr GST` (GST is never deferred — tax point is the invoice date). The recognition run (`POST /api/deferred-revenue/run-recognition`) then releases revenue period by period (`Dr 2300 / Cr Revenue`).

**Editing a posted invoice.** `PUT /api/invoices/{id}` reverses the original JV(s) and re-posts from the edited lines — blocked if the invoice is paid or sits in a locked period. The re-consume honours the `block_negative_stock` guard; for a deferred invoice the schedule is rebuilt, but the edit is **blocked once any period has been recognised** (void & reissue instead).

---

### 4.2 PURCHASE / PAYABLES

```
  CREATE VENDOR             RECEIVE BILL                PAY BILL
       │                        │                            │
       │ POST /api/vendors      │ POST /api/bills            │ POST /api/bill-payments
       ▼                        ▼                            ▼
   Vendor row             Bill + N lines               BillPayment
                          + Transaction (JV)           + Transaction (JV)
                          + JournalEntry × 2+          + JournalEntry × 2
                          + Product.stock_qty +=       + PaymentAllocation[]
                          + InventoryLayer per         + Bill.status derived
                            stock line                   (paid | partial)
```

**Bill GL — stock purchase, 20 units × 5:**
```
                              DEBIT       CREDIT
1200 Inventory                 100.00
2000 Accounts Payable                      100.00

Side effects:
  Product.stock_qty += 20
  InventoryLayer { qty_received=20, qty_remaining=20, unit_cost=5, source_doc='BILL-0042' }
  Product.avg_cost recomputed via weighted-average formula
```

**Bill GL — service expense, 1000 + 17% GST input:**
```
                              DEBIT       CREDIT
5000 General Expenses        1,000.00
1250 GST Receivable (Input)    170.00
2000 Accounts Payable                    1,170.00
```

---

### 4.3 INVENTORY (Weighted-Average)

**Inventory sidebar section:** the navigation sidebar surfaces a dedicated **Inventory** section containing: **Products**, **Product Categories** (`/products/categories`), **Product Ledger** (`/products/ledger`), and **Inventory Performance** (`/inventory/performance`).

**Before creating stock products**, set up your product categories at **Inventory → Product Categories** (`/products/categories`). Categories are a 2-level hierarchy (parent → sub-category); new tenants get a starter set seeded for their business model. Assign a category on the product add/edit form; filter the products list by category.

Inventory is cross-cutting — it rides on top of Bills (inflow) and Invoices (outflow). Only `Product.product_type == 'stock'` products participate; services bypass.

```
┌──────────────────────────────────────────────────────────────────┐
│                  INVENTORY MECHANICS (WAvg / IAS 2)              │
├──────────────────────────────────────────────────────────────────┤
│ On purchase (record_purchase):                                   │
│   new_avg = (old_qty × old_avg + qty × unit_cost) / (old_qty +   │
│             qty)                                                 │
│   InventoryLayer row appended (source_doc = bill.number)         │
│   Product.stock_qty += qty                                       │
│                                                                  │
│ On sale (consume_stock):                                         │
│   cogs = qty × current_avg_cost   ← charged at running avg       │
│   Layers depleted FIFO (qty_remaining decremented oldest-first)  │
│   Product.stock_qty -= qty                                       │
│   Returns cogs → posted as Dr COGS / Cr Inventory in a SEPARATE  │
│   JV so reversal of the sale doesn't accidentally untangle COGS  │
│                                                                  │
│ Over-sell guard: consume_stock(block_negative=True) raises a     │
│ 400 error if the sale would drive stock_qty below 0.  Enabled    │
│ when the tenant setting `block_negative_stock=true` (default     │
│ false). Purchases call record_purchase() — never blocked.        │
│ Toggle at Settings → Inventory → Block overselling.             │
│                                                                  │
│ Concurrency: Product row is SELECTed FOR UPDATE on both paths so │
│ two simultaneous sales can't oversell on Postgres.               │
└──────────────────────────────────────────────────────────────────┘
```

**Example — two purchases then a sale:**
```
1. record_purchase(10 @ 5):
     stock_qty = 10, avg_cost = 5.00
     Layer[0]: qty_remaining=10, unit_cost=5

2. record_purchase(10 @ 7):
     stock_qty = 20, avg_cost = (10×5 + 10×7)/20 = 6.00
     Layer[1]: qty_remaining=10, unit_cost=7

3. consume_stock(3):
     cogs = 3 × 6.00 = 18.00
     stock_qty = 17, avg_cost = 6.00 (unchanged)
     Layer[0]: qty_remaining=7 (FIFO depletion)
     Layer[1]: qty_remaining=10
```

---

### 4.4 BANKING & RECONCILIATION

```
  CREATE BANK ACCOUNT      UPLOAD STATEMENT             RECONCILE PERIOD
        │                        │                            │
        │ POST /api/bank-        │ POST /api/bank-imports     │ POST /api/reconciliations
        │ accounts               │ (multipart CSV)            │
        ▼                        ▼                            ▼
   BankAccount             BankStatementImport          Reconciliation
   (linked to CoA          + StatementLine[]            + ReconciliationLine[]
    Asset acct)            (file_hash unique)             from JEs in period
                                 │                            │
                                 │ POST /api/bank-imports     │ user matches lines
                                 │ /{id}/auto-match           │
                                 ▼                            ▼
                          Auto-match by amount         PATCH /…/lines/{id}
                          + ±3-day window                 is_matched=true
                          → link to Transaction              │
                                                             ▼
                                                       POST /…/close
                                                       (period locked)
```

**CSV format (generic 5-column):**
```
date,description,debit,credit,balance
2026-05-02,Customer payment Alice,0,500,1500
2026-05-03,Stripe payout,0,1000,2500
2026-05-04,Office rent,200,0,2300
```

`debit` and `credit` are the **bank's perspective**: credit = money into the account; debit = money leaving. Either column may be blank.

---

### 4.5 MANUAL JOURNAL ENTRIES

Used for adjustments, opening balances, depreciation, accruals, prepayments, corrections.

```
  CAPTURE JV              JOURNAL                      REVERSE (if error)
       │                      │                             │
       │ POST /api/transactions│ GET /api/reports/journal   │ POST /api/transactions
       ▼                      ▼                             │ /{id}/reverse
  Transaction          paginated list                       ▼
  + N journal lines    of all JVs                     New "Reversal of JV-XXX"
  Dr = Cr enforced                                    Original.is_reversed = true
  AuditLog                                            + unwinds derived state
                                                        (see §5.6)
```

**Form (`/entry`):**
```
[ Date ]  [ Description ]  [ Reference # ]
┌──────────────────────────────────────────┐
│ Account         │ Debit       │ Credit   │
├──────────────────────────────────────────┤
│ 1000 Cash    ▼  │  10,000     │     —    │
│ 4000 Revenue ▼  │      —      │  10,000  │
├──────────────────────────────────────────┤
│ + Add row                                │
└──────────────────────────────────────────┘
            Total Dr: 10,000
            Total Cr: 10,000  ✓ balanced
                                  [ Save ]
```

**JV numbering** uses `Transaction.id` (DB-assigned), so it's race-free under concurrent writes. Invoice/bill numbers use a separate `SequenceCounter` table (§10).

---

### 4.5a PAYROLL CYCLE

Payroll runs against all active employees who have a salary structure configured.

```
  SETUP                    CREATE RUN               APPROVE           POST GL           PAY EMPLOYEES
   │                          │                         │                │                   │
   │ salary components         │ POST /api/payroll/runs  │ POST .../approve│ POST .../post      │ BP Bank Payment
   │ employee salary structure │ (period dates)          │                │ (PR-YYYY-seq JV)  │ Dr Sal. Payable
   │                           ▼                         ▼                ▼                   │ Cr Bank
   │                      PayrollRun (draft)        PayrollRun        Transaction +           ▼
   │                      + PayrollLine × N         (approved)        JournalEntry[]     Payable cleared
   │                      + PayrollLineDetail                          balanced
   ▼                        (auto-computed)
  Catalog + structures
  in place
```

**Step-by-step:**

1. **Set up salary components** (Admin → Payroll → Salary Components):
   - Define each component: code, name, type (`earnings` / `deductions` / `statutory`), GL account, fixed vs %-of-basic.

2. **Assign component amounts to each employee** (Employees → Salary Structure tab):
   - Select component, enter amount or pct_of_basic, set effective dates.

3. **Create payroll run** (Payroll → New → set period):
   - System auto-computes all lines from active structures.
   - In Draft status: individual amounts can be overridden inline.

4. **Approve** (status: Draft → Approved):
   - Human review gate; no GL entry yet.

5. **Post to GL** (status: Approved → Posted):

```
Dr  Salary Expense         5,200   (per SalaryComponent.gl_account_id, aggregated)
  Cr  Salaries Payable     4,100   (net pay)
  Cr  Income Tax Payable     600
  Cr  EOBI Payable           500
  ─────────────────────────────────
  ∑Dr = ∑Cr = 5,200  ✓
```

6. **Pay employees** — create a Bank Payment voucher (`BP`) against Salaries Payable to clear the liability.

7. **Void if needed** — creates a reversing JV; restores the Salaries Payable balance; status → Void.

### 4.5b ATTENDANCE → PAYROLL INTEGRATION

Attendance records feed into payroll planning:

- Monthly grid shows working days, absences, leaves per employee (colour-coded: Present/Absent/Half Day/Leave/Holiday/Off).
- Payroll run can reference attendance to validate expected working days.
- Bulk entry grid allows setting a full month's attendance in one `POST /api/attendance/bulk` call.
- Biometric import (`POST /api/attendance/import/biometric`) matches records by `employee_code`, stores raw device payload in `raw_data`, sets `source = biometric`; delete is blocked for biometric records to preserve device audit integrity.
- Future: auto-deduct absent/unpaid leave days from gross pay during run computation.

---

### 4.6 PERIOD-END CLOSE

```
  CREATE PERIOD          CLOSE PERIOD                  REOPEN (if needed)
       │                      │                              │
       │ POST /api/periods    │ POST /api/periods/{id}/close │ POST /api/periods/{id}
       ▼                      ▼                              │ /reopen
  AccountingPeriod       1. Aggregate Revenue/Expense        ▼
   (open, unlocked)         net balances in period      AccountBalance rows
                         2. Post closing JV:            for this period
                              Dr Revenue (sum net Cr)   ARE DELETED
                              Cr Expense (sum net Dr)   (live aggregation
                              Cr/Dr Retained Earnings    resumes)
                         3. Materialise AccountBalance  Period.is_locked = false
                            per account                 Closing JV stays in
                         4. Period.is_locked = true       place — reverse it
                                                          separately if needed
```

**Why two pieces (closing JV + balance materialisation)?**
- The closing JV zeroes income-statement accounts into Retained Earnings, so next period starts clean.
- The materialised `AccountBalance` makes future trial-balance reads against this period O(accounts) instead of O(journal entries) — useful as the GL grows.

---

### 4.7 MANUFACTURING (V2)

Applies only to tenants where `Tenant.business_model == 'manufacturing'`. The signup flow seeds three stock locations (`MAIN` own, `GODOWN` customer_custodial, `WIP` work-in-progress) and an extended CoA that includes the memo pair `1210 Customer Goods on Hand` / `2150 Customer Goods Liability`.

The cycle is built around **value-addition on customer-supplied goods** — the customer brings raw material, you add labour + (possibly) your own consumables, you bill them per output unit.

```
  SETUP                       INTAKE                    PRODUCTION                   BILLING
   │                            │                          │                            │
   │ POST /api/products         │ POST /api/grn            │ POST /api/production-     │ Invoice
   │ POST /api/bom              │   (customer goods        │   orders                  │ generated
   │   (recipe with own_stock   │    → GODOWN, memo)       │                           │ at completion
   │    + customer_supplied)    │                          │ Each transition is a     │ of /bill stage
   │ POST /api/rate-plans       │ Optional declared_value  │ separate JV:             │
   │ POST /api/rate-plans/      │   triggers memo JE       │                           │
   │   assign (cust ↔ plan)     │   Dr 1210 / Cr 2150     │ start ─→ Dr WIP /         │
   │                            │                          │           Cr RawMaterial │
   │                            │                          │ complete → Dr FG / Cr WIP│
   │                            │                          │ deliver → Dr COGS / Cr FG│
   │                            │                          │           Dr 2150/Cr 1210│
   │                            │                          │           (memo release)  │
   │                            │                          │ bill ────→ Dr AR /       │
   │                            │                          │           Cr 4010 Service│
   ▼                            ▼                          ▼                            ▼
   Catalogues ready          Goods in custody          PO walks the state machine     Cash collectible
                                                       draft → started → completed
                                                       → delivered → billed
```

**State machine:**

| State | Posted on entry | Movement type | Notes |
|---|---|---|---|
| `draft` | — | — | Only metadata; cancellable |
| `started` | `Dr 1201 WIP / Cr 1200 Raw Material` for own_stock components | `ISSUE` (own) + `CUSTODIAL_ISSUE` (customer) | Snapshots `own_material_cost` |
| `completed` | `Dr 1202 Finished Goods / Cr 1201 WIP` at absorbed cost | `COMPLETION` | Sets `output_unit_cost = own_material_cost / output_qty` |
| `delivered` | `Dr 5010 COGS / Cr 1202 Finished Goods` + memo release `Dr 2150 / Cr 1210` for fully drained GRNs | `DELIVERY` | |
| `billed` | `Dr 1100 AR / Cr 4010 Service Revenue (Value-Add)` via RatePlan formula | — | Creates Invoice row and links via `ProductionOrder.invoice_id` |
| `cancelled` | — | — | Only legal from `draft`; later states require manual JV reversal |

**Rate plan formula (used at the `bill` stage):**

```
base       = per_unit_rate × output_qty
if includes_materials_at_cost:
    base  += own_material_cost                  (your consumables, at WAvg)
overhead   = base × overhead_pct / 100
subtotal   = base + overhead
margin     = subtotal × margin_pct / 100
total      = subtotal + margin                   (excl. GST)
```

The invoice is built with itemised lines (value-add, materials passthrough, overhead, margin) so the customer can see exactly what they're paying for.

**Custodial vs own — invariant:** customer-supplied material **never** touches your asset accounts. It lives only in
1. The custodial inventory layers (`InventoryLayer.owner_customer_id = customer.id`, `unit_cost = 0`)
2. The memo pair `1210/2150` (with `Account.is_memo = True` so it's excluded from formal A=L+E totals on the balance sheet)
3. The stock movement log with `posted_to_gl = false`

Memo balance is released only when **all** layers of a given GRN are fully drained — partial usage keeps the memo intact (the customer's stake is still in your custody, just embedded in your WIP/FG).

**Manufacturing reports (V2.5):**

| Endpoint | Returns |
|---|---|
| `GET /api/manufacturing/dashboard` | `{ pipeline: {by state→count}, totals: {wip_cost, finished_goods_cost, custodial_qty} }` |
| `GET /api/manufacturing/wip-aging` | Open POs (state=`started`) bucketed `0-7d / 8-14d / 15-30d / 30d+` |
| `GET /api/manufacturing/production-summary` | POs grouped by state with count + output_qty + cost; optional `start`, `end` filters |
| `GET /api/manufacturing/customer-custody` | Per-(customer, product) qty on hand + unreleased declared value |

---

### 4.8 TELECOM FRANCHISE (V3)

Applies only to tenants where `Tenant.business_model == 'telecom_franchise'`. Signup seeds a 56-account franchise CoA and a franchise-specific module set. 23 `tc_*` tables (`models_telecom.py`) model the operational entities, but the **only** GL writer is still `services/posting.py` — every posting below is a balanced, tenant-scoped JV created via `tracker_posting.py` / `franchise_posting.py`.

The model mirrors a real mobile-operator franchise: you pre-fund a **Tracker** wallet with the operator, convert it to spendable **load float** (earning a 3% uplift), push that float down a **MSR → RSO → Retail** distribution chain, collect cash daily, sell/activate SIMs, hit monthly **FCA** (first-call-activation) targets, run a **mobile-money** agency, bill **postpaid** on the operator's behalf, reconcile **commission statements**, and amortise the **franchise fee** / pay **royalty**.

```
  FUND THE WALLET            DISTRIBUTE LOAD             SELL & ACTIVATE            SETTLE & RECONCILE
   │                          │                           │                          │
   │ deposit  Dr 1210/Cr Bank │ MSR→RSO  Dr 1212/Cr 1211 │ stock debit Dr 1200/     │ RSO daily collection
   │ load     Dr 1211 (×1.03) │ RSO→Retail Dr 1213/Cr1212│   Cr 1210 (+ tc_sim_batch)│   Dr Bank / Cr 1212
   │          Cr 1210 (cash)  │                           │ counter sale + COGS       │   / Cr 1120 (±var→5070/4900)
   │          Cr 4020 (3%)    │                           │ activation → accrue       │ commission statement
   │                          │                           │   Dr 1110 / Cr 4020       │   settle vs 1110 (var→4061)
   ▼                          ▼                           ▼                          ▼
  deposit_balance==GL 1210   load receivables build      SIM inventory relieves      receivables clear
  load_balance ==GL 1211                                 commission accrues          fee amortises / royalty pays
```

**Tracker & load order (`tracker_posting.py`):**

| Operation | JV | Side-effect |
|---|---|---|
| `post_tracker_deposit` | `Dr 1210 Tracker Deposit / Cr 1010 Bank` | `tc_tracker_account.deposit_balance += amount` |
| `post_load_order` | `Dr 1211 Load Float (cash×1.03) / Cr 1210 (cash) / Cr 4020 Load Uplift (cash×0.03)` | deposit_balance −= cash; load_balance += face. Rejects if deposit insufficient |
| `post_stock_debit` | `Dr 1200/1201/1204 Inventory / Cr 1210` | creates a `tc_sim_batch` for code 1200; deposit_balance −= cost |
| `post_msr_to_rso_transfer` | `Dr 1212 RSO Load Rec / Cr 1211 Load Float` | load_balance −= amount; `tc_load_transfer` row |
| `post_rso_to_retail_transfer` | `Dr 1213 Retail Load Rec / Cr 1212 RSO Load Rec` | `tc_load_transfer` row |
| `post_rso_daily_collection` | `Dr 1010 Bank / Cr 1212 (load) / Cr 1120 (stock)`; variance > 0 → `Cr 4900`, < 0 → `Dr 5070` | `tc_rso_daily_collection` row |
| `post_counter_sim_sale` | sale `Dr Cash / Cr 4030` + COGS `Dr 5011 / Cr 1200` | two JVs |
| `post_rso_sim_issue` | `Dr 1120 RSO Stock Rec (face) / Cr 1200 (cost) / Cr 4050 (margin)` | `tc_rso_stock_issue`; batch.qty_activated += qty |
| `post_fca_target_commission` | `Dr 1210 or Bank / Cr 4060 FCA Target Commission` | credits tracker deposit when `credit_to='tracker'` |
| `post_fca_target_penalty` | `Dr 5090 Target Shortfall Penalty / Cr 1210` | — |

**Mobile money / postpaid / commission / franchise (`franchise_posting.py`):**

| Operation | JV |
|---|---|
| `post_mm_float_top_up` | `Dr 1214 MM Float Asset / Cr Cash` |
| `post_mm_customer_deposit` | `Dr Cash / Cr 2100 MM Float Liability` (float *decreases*) |
| `post_mm_customer_withdrawal` | `Dr 2100 / Cr Cash` (float *increases*) |
| `post_mm_commission_credit` | `Dr 1214 or Bank / Cr 4022 MM Commission` |
| `post_mm_reconciliation` | diff → `Dr 5070` (shortage) or `Cr 4900` (overage); no entry when balanced |
| `post_commission_accrual` | `Dr 1110 Commission Receivable / Cr revenue (4020 default)`; sets activation `commission_status='accrued'` |
| `post_commission_statement_settlement` | `Dr Bank/Tracker / Cr 1110 (accrued)`; variance → `Cr 4061` (favourable) or `Dr 5000` (adverse). Zero lines skipped |
| `post_postpaid_bill` | `Dr 1130 Postpaid Cust Rec / Cr 2110 Collections Payable` (gross) |
| `post_postpaid_collection` | `Dr Cash / Cr 1130` |
| `post_postpaid_remittance` | `Dr 2110 (gross) / Cr Bank (net) / Cr 4040 Postpaid Commission` |
| `post_franchise_fee_capitalisation` | `Dr 1300 Franchise Intangible / Cr Bank` |
| `post_franchise_fee_amortisation` | `Dr 5030 Fee Amortisation / Cr 1301 Accum. Amort.` (monthly = fee ÷ amortisation_months) |
| `post_royalty_accrual` | `Dr 5040 Royalty Expense / Cr 2120 Royalty Payable` |
| `post_royalty_payment` | `Dr 2120 / Cr Bank` |

**FCA invariant:** first-call activations are **counted, not journalised** per event (`tc_fca_event` rows). Only the monthly target settlement (commission or penalty) hits the GL.

**Reconciliation invariants (verified):**
- `tc_tracker_account.deposit_balance` == GL balance of `1210`
- `tc_tracker_account.load_balance` == GL balance of `1211`
- 3-line load order balances exactly (`cash×1.03 == cash + cash×0.03`)
- Trial balance nets to zero across the full franchise posting set

**Telecom reports (V3):**

| Endpoint | Returns |
|---|---|
| `GET /api/telecom/reports/dashboard` | Tracker & load positions, commission receivable, RSO count/stock-rec, MM float, SIM utilisation, FCA month progress |
| `GET /api/telecom/reports/commission-aging` | Accrued commission receivable bucketed `current / 1-30 / 31-60 / 61-90 / 90+` |
| `GET /api/telecom/reports/rso-ledger` | Per-RSO: load in (MSR), load out (retail), cash collected (load/stock/total), open load balance |
| `GET /api/telecom/reports/float-statement` | MM accounts: system float vs GL `1214` for reconciliation |
| `GET /api/telecom/reports/sim-utilisation` | Per-batch received / activated / available + unit cost |
| `GET /api/telecom/reports/postpaid-book` | All postpaid bill cycles with collection + remittance status |
| `GET /api/telecom/reports/revenue-by-stream` | Revenue per franchise stream (CoA 4xxx), sign-flipped + total |
| `GET /api/telecom/reports/fca-target` | Current-month FCA actual vs target, achievement %, delta |
| `GET /api/telecom/reports/tracker-statement` | Tracker txn ledger + GL-vs-denormalised deposit/load reconciliation |

---

### 4.9 HEALTHCARE / HOSPITAL (V3.0)

Applies only to tenants where `Tenant.business_model == 'hospital'` with the `healthcare` module installed (`deps: ["base","hrm","inventory"]`). Signup seeds a hospital CoA (accounts 2310, 4100–4122, 5120–5130) in addition to the standard backbone. All 19 `hc_*` clinical tables live in `models_healthcare.py`; GL writing still goes through `services/posting.py`.

**The central design decision: Patient = Customer.** Every `POST /api/healthcare/patients` auto-creates a matching `Customer` record. This means AR aging, customer statements, payment allocation, and receivables reports all work without modification for hospital AR.

```
  REGISTER PATIENT          OPD VISIT                  LAB / PROCEDURE            IPD ADMISSION → DISCHARGE
   │                         │                          │                           │
   │ create patient           │ token → visit           │ walk-in order → bill      │ admit: Dr Cash / Cr 2310 Deposit
   │ → auto-creates Customer  │ → Dr 1100 / Cr 4100    │   Dr 1100 / Cr 4110       │ charges accumulate (no GL per row)
   │   in AR system           │ OPD Revenue             │   Lab Revenue             │ discharge: single consolidated invoice
   │                          │                         │                           │   Dr 1100 / Cr 4100–4122
   │                          │                         │ procedure order → bill    │ deposit settled:
   │                          │                         │   Dr 1100 / Cr 4120       │   Dr 2310 / Cr 1100
   ▼                          ▼                         ▼                           ▼
  MR-YYYYNNNN issued        visit recorded            invoice in AR              bed freed; ADM-YYYYNNNN closed
  customer_id linked        prescription written      results entered            consolidated invoice in AR
```

**GL posting reference (healthcare):**

| Event | Dr | Cr | Voucher Prefix |
|---|---|---|---|
| OPD consultation billed | 1100 AR | 4100 OPD Revenue | HC-OPD |
| OPD follow-up billed | 1100 AR | 4100 OPD Revenue | HC-OPD |
| IPD deposit received | 1000 Cash | 2310 Patient Advances | HC-DEP |
| Lab order billed (walk-in/OPD) | 1100 AR | 4110 Lab Revenue | HC-LAB |
| Procedure billed (OPD/walk-in) | 1100 AR | 4120 Procedure Revenue | HC-PROC |
| IPD discharge — ward charges | 1100 AR | 4121 Ward/Bed Charges | HC-IPD |
| IPD discharge — deposit settled | 2310 Patient Advances | 1100 AR | HC-IPD |
| Medical supply issue (internal) | 5120 Medical Supplies | 1300 Inventory | HC-ISS |
| Lab reagent consumption | 5130 Lab Reagents | 1300 Inventory | HC-ISS |

**IPD charge accumulation (key invariant):** `hc_admission_charge` rows are **never individually GL-posted**. They accumulate cost records only. At discharge, `POST /api/healthcare/admissions/{id}/discharge` rolls all charges into one balanced JV. This prevents micro-JV sprawl (a 5-day stay might have 20+ nursing charges).

**OPD token queue:** token numbers reset daily per doctor (`MAX(token_number) WHERE visit_date = today AND doctor_id = X`). No "OPD session" table; the date + doctor_id composite is sufficient.

**Ward/bed state machine:**
```
available → occupied  (POST /admissions, bed_id supplied)
occupied  → available (POST /admissions/{id}/discharge)
any       → maintenance (PUT /beds/{id} status=maintenance — admin only)
```

**Healthcare reports (`/api/healthcare/reports/`):**

| Endpoint | Returns |
|---|---|
| `dashboard` | KPIs: tokens today, patients admitted, bed occupancy %, revenue today |
| `opd-summary` | Tokens issued / visits by date range; top complaints |
| `doctor-collections` | Visits + revenue per doctor in period |
| `lab-summary` | Lab orders by status + source; revenue |
| `ipd-census` | Ward-level admissions/discharges/avg LOS, bed utilisation |
| `revenue-by-type` | GL credits 4100–4121 by account (OPD/Lab/Procedure/Ward) |

---

## 5. CROSS-CUTTING FEATURES

### 5.1 Multi-Currency & FX

```
Tenant.base_currency  (e.g. "USD")  ← reporting currency
                       │
Document carries:      │
  currency        ◀────┘   e.g. "EUR"
  exchange_rate           snapshot at issue time (EUR → USD)
  subtotal / total        in document currency

GL posts in base currency:
  Dr/Cr amount = document_amount × exchange_rate
```

**Rate resolution (`services.fx.rate_to_base`):**
1. Identity (1.0) when `from == base`.
2. Direct `(from → base)` row, latest on/before issue date.
3. Inverse `(base → from)` row → `rate = 1 / inverse_rate`. (Operators don't have to enter both directions.)
4. Else `LookupError` → endpoint returns 400 with a clear message.

**ExchangeRate catalog (`/api/exchange-rates`):**
- UNIQUE `(tenant_id, date, from, to)` — POST upserts when the triple matches.
- CHECK `rate > 0`.

---

### 5.2 Tax Codes

Per-tenant catalog (`TaxCode`) decouples rate + GL account from the document. Designed for future per-line tax assignment; the current invoice/bill flow still uses a single `gst_rate` per document but can reference a catalog entry.

```
TaxCode(code, name, rate, type, gl_account_id)
  type ∈ {'output', 'input'}     ← CHECK enforced
  rate >= 0                       ← CHECK enforced

CRUD: GET/POST/PUT /api/tax-codes
```

**Why catalog?** A tenant can change its standard rate (e.g. 17% → 18%) without touching historical documents.

---

### 5.3 Payment Allocations

A single payment can settle multiple invoices/bills with partial amounts. The allocation modal (on `/payments-received` and `/bill-payments`) shows all open invoices/bills for the counterparty with their outstanding balance and an editable "Amount to Apply" column. A running "Total Applied vs Payment" counter warns if amounts don't balance.

```
PaymentReceived (amount=1000)
   ├─ PaymentAllocation { invoice_id=A, amount=300 }   → invoice A 'partial'
   ├─ PaymentAllocation { invoice_id=B, amount=500 }   → invoice B 'paid'
   └─ PaymentAllocation { invoice_id=C, amount=200 }   → invoice C 'partial'

Constraint:  invoice_id XOR bill_id     ← CHECK enforced
Constraint:  amount > 0                 ← CHECK enforced
Constraint:  sum(allocations) <= payment.amount  ← endpoint enforces
```

**Status derivation (live in payments router):**
```python
allocated = sum(PaymentAllocation.amount where invoice_id = X)
if allocated >= invoice.total:   status = 'paid'
elif allocated > 0:              status = 'partial'
else:                            status = 'sent'   (or 'draft' if never sent)
```

The dashboard `ar_outstanding` and the aging report both subtract `sum(allocations)` from `total` so partial payments show the *remaining* balance, not gross.

---

### 5.4 Recurring Entries

```
RecurringTemplate(name, frequency, next_run, entries_json, is_active)
  frequency ∈ {daily, weekly, monthly, quarterly, yearly}  ← CHECK enforced
  entries_json: JSON list of {account_id, debit, credit}

Worker endpoint: POST /api/recurring/run-due
  → for each template where next_run <= today:
       post_transaction(...)
       last_run = next_run
       next_run = advance(next_run, frequency)
```

`monthly` and longer frequencies clamp the day-of-month to the last valid day of the target month (e.g. 31 Jan → 28 Feb). Idempotent per `(template, next_run)` — running it twice for the same date is a no-op the second time because `next_run` advances after the first call.

**Frontend** — `/recurring` page:
- Lists all templates (name, frequency, next_run, last_run, active badge)
- "Create Recurring" button → modal with name, frequency dropdown, next_run picker, and a GL line-item table
- Per-row: Edit, Deactivate toggle, "Run Now" (calls `POST /api/recurring/run-due` with dry_run=false for the single template)
- Overdue templates (next_run <= today) highlighted in red

---

### 5.5 Bank Statement Import

```
POST /api/bank-imports  (multipart: bank_account_id, file)
  ↳ SHA-256 hash file → unique per (tenant, account) — duplicate → 409
  ↳ parse CSV (date, description, debit, credit, balance)
  ↳ StatementLine[] created, is_matched=false

POST /api/bank-imports/{id}/auto-match
  ↳ for each unmatched line:
      find Transactions in [date-3, date+3] whose JE sum == line amount
      excluding JVs already claimed by *this import's* matched lines
      if exactly 1 candidate → link line → JV, is_matched=true

PATCH /api/statement-lines/{id}   { matched_transaction_id: N }
  ↳ manual match (after operator review)
```

Ambiguous matches (>1 candidate) leave the line unmatched for manual resolution.

---

### 5.6 Reversal Semantics

`POST /api/transactions/{id}/reverse` is more than negating the JEs. The handler inspects what document points at the transaction (via `Invoice.transaction_id`, `Bill.transaction_id`, `PaymentReceived.transaction_id`, `BillPayment.transaction_id`) and propagates:

| Source document | Side effects unwound |
|---|---|
| `PaymentReceived` | Delete `PaymentAllocation` rows for this payment; recompute `Invoice.status` for each touched invoice |
| `BillPayment` | Same, on the AP side |
| `Invoice` | For each stock line, call `reverse_consumption()` (stock returns at the COGS rate); auto-reverse the separate COGS sub-JV; flip `Invoice.status = 'void'` |
| `Bill` | Call `reverse_purchase(source_doc=bill.number)` to drop the inventory layer; recompute `avg_cost` from remaining layers; flip `Bill.status = 'void'` |
| Manual JV | Just post the mirror JV — no derived state |

Original transaction is **never deleted**:
- `Transaction.is_reversed = true`
- `Transaction.reversed_by_id = <new_jv_id>`

Double-reversal is rejected with 400.

---

### 5.7 Sub-Ledgers & Audit-Trail Drill-Down

The General Ledger answers *"what's the balance of account X?"*. Sub-ledgers answer *"which customer / vendor / product caused that balance, and which document booked it?"*. Easy-Books renders three sub-ledgers and a cyclic drill-down link graph on top of the GL.

#### 5.7.1 Standards alignment

| Requirement | Standard | How Easy-Books satisfies it |
|---|---|---|
| Consistent presentation of balances | **IAS 1.45** | Every list page uses the same `<DocLink>` resolver and column conventions |
| Reperformability of every posting | **ISA 230 §A6** | `GET /api/transactions/{id}.source_docs[]` reverse-resolves any JV to its originating Invoice / Bill / Payment / GRN |
| Internal control traceability | **ISA 315.A82** | Cyclic drill-down — Trial Balance → Account Ledger → JV → source doc → party ledger → invoice → back to JV — has no orphan nodes |
| Inventory disclosure by class | **IAS 2.36(d)** | Stock card per product shows running qty + value with movement type (`RECEIPT/ISSUE/COMPLETION/DELIVERY/ADJUSTMENT`) |
| Receivable / payable disclosure | **IFRS 7.7, IAS 1.78(b)** | Customer & vendor ledgers expose opening, period activity, closing balance, FX-converted to tenant base currency |
| Audit log of changes | **ISA 240, SOC 2 CC7.3** | Every mutation writes an `AuditLog` row — visible at `/api/audit-log` |

#### 5.7.2 The three sub-ledgers

**AR sub-ledger (debit-normal)** — `GET /api/customers/{id}/ledger?start=…&end=…`
- Aggregates `JournalEntry` rows that touch AR (`account.code = 1100`) for invoices/payments belonging to this customer
- Running balance = `Σ debit − Σ credit` (positive = customer owes you)
- `qty_out` column derived from stock-product invoice lines for quick "did we ship something on this invoice?" reads
- Frontend page: `/customers/[id]/ledger` — summary tiles (Opening / Charged / Paid / Closing) + table + Print

**AP sub-ledger (credit-normal)** — `GET /api/vendors/{id}/ledger?start=…&end=…`
- Aggregates AP postings (`account.code = 2000`) for bills/bill-payments belonging to this vendor
- Running balance = `Σ credit − Σ debit` (positive = you owe vendor) — flipped to keep "amount owed" intuition
- Frontend page: `/vendors/[id]/ledger`

**Product stock card** — `GET /api/products/{id}/stock-card?start=…&end=…`
- StockMovement event log is the source of truth (not `Product.stock_qty`, which is a projection)
- Opening qty/value = pre-period in/out sums; each row carries `qty_in`, `qty_out`, `running_qty`, `unit_cost`, `running_value`
- Frontend page: `/products/[id]/stock-card`

#### 5.7.3 Source-document reverse-resolution

`GET /api/transactions/{id}` now returns:

```json
{
  "id": 84,
  "jv_number": "JV-2026-0084",
  "date": "2026-05-22",
  "is_reversed": false,
  "reversed_by_id": null,
  "lines": [ … ],
  "source_docs": [
    { "kind": "invoice", "id": 17, "number": "INV-2026-0017" }
  ]
}
```

The resolver checks `Invoice.transaction_id`, `Bill.transaction_id`, `PaymentReceived.transaction_id`, `BillPayment.transaction_id`, `GoodsReceiptNote.transaction_id` (and the auto-generated COGS sub-JV's parent invoice via the `parent_transaction_id` link). A reversed JV exposes both the original `source_docs[]` AND `reversed_by_id` pointing forward to the mirror JV.

#### 5.7.4 The `<DocLink>` resolver

Single source of truth for "given an entity kind + id, where does it live?". `frontend/src/components/DocLink.tsx`:

```tsx
type DocKind =
  | "account"   // ?account={name}             → /ledger
  | "transaction" | "invoice" | "bill"         → /journal/{id}, /invoices/{id}, /bills/{id}
  | "customer" | "vendor" | "product"          → /customers/{id}/ledger, /vendors/{id}/ledger, /products/{id}/stock-card
  | "payment-received" | "bill-payment"        → /payments-received/{id}, /bill-payments/{id}
  | "grn" | "production-order"                 → /manufacturing/grn/{id}, /manufacturing/production-orders/{id}
```

Every list page (`/invoices`, `/bills`, `/customers`, `/vendors`, `/products`, `/ledger`, `/journal`, `/coa`, `/trial-balance`, etc.) wraps code/number/name cells in `<DocLink type=… id=… label=… />`. Hover gives the standard underline-on-hover affordance; click navigates. No URL is ever constructed inline in a page — change the routing convention in one place, every page follows.

#### 5.7.5 The cyclic drill-down graph

```
Trial Balance ─click code──▶ Account Ledger ─click JV──▶ JV Detail ─click source───┐
       ▲                                                        │                 │
       │                                                        ▼                 ▼
       │                                                  Invoice / Bill     Customer / Vendor
       │                                                        │                 Ledger
       │                                                        ▼                 │
       └──────────── click account code on JV ◀─── Source doc detail ◀────────────┘
```

Every node in the graph has at least one inbound and one outbound link — no dead ends. This is the property `ISA 315.A82` calls *"reperformability of the audit trail"*.

| Business event | Debit | Credit | Side effects |
|---|---|---|---|
| Invoice (service) | 1100 AR | 4000 Revenue + 2200 GST Out | — |
| Invoice (stock) | 1100 AR | 4000 Revenue + 2200 GST Out | `stock_qty -=`, FIFO layer depletion, **separate JV**: Dr 5010 COGS / Cr 1200 Inventory |
| Invoice (foreign currency) | 1100 AR (in **base**, = doc × rate) | 4000 Revenue (in base) | Invoice keeps `currency`, `exchange_rate`, `subtotal/total` in doc currency |
| Payment received | 1000 Cash / 1010 Bank | 1100 AR | `PaymentAllocation` row(s); `Invoice.status` recomputed |
| Bill (service) | 5xxx Expense + 1250 GST In | 2000 AP | — |
| Bill (stock) | 1200 Inventory | 2000 AP | `stock_qty +=`, `InventoryLayer` row appended, `avg_cost` recomputed |
| Bill payment | 2000 AP | 1000 Cash / 1010 Bank | `PaymentAllocation` row(s); `Bill.status` recomputed |
| Period close (Revenue close) | 4xxx Revenue | 3100 Retained Earnings | Materialises `AccountBalance`; locks period |
| Period close (Expense close) | 3100 Retained Earnings | 5xxx Expense | Same |
| Opening balance (Asset) | Asset account | 3000 Owner Capital | One-time, manual JV |
| Depreciation | 5050 Depreciation Exp | 1510 Accumulated Depreciation | Monthly, manual or recurring |
| Bad-debt write-off | 5060 Bad Debt Exp | 1100 AR | When uncollectible |
| Owner draw | 3010 Drawings | 1000 Cash | Reduces equity |
| Reversal (any) | Mirror of original | Mirror of original | Unwinds derived state per §5.6 |

**Universal invariant:** ∑Dr = ∑Cr exact (`Decimal`). Backend rejects unbalanced JVs at the posting service.

---

### 5.8 Bulk Actions

List pages (`/invoices`, `/bills`, `/customers`, `/vendors`, `/products`) support checkbox-based bulk operations via a floating `BulkActionBar` that appears when ≥1 row is checked.

| Page | Available bulk actions |
|------|----------------------|
| Invoices | Mark as Sent, Void, Delete (draft only) |
| Bills | Mark as Received, Void, Delete (draft only) |
| Customers | Delete (no outstanding balance) |
| Vendors | Delete (no outstanding balance) |
| Products | Delete (zero stock) |

**Backend:** `POST /api/invoices/bulk` / `POST /api/bills/bulk` accept `{ ids: [int], action: "mark_sent"|"void"|"delete" }`. Guards ensure only `draft` invoices/bills can be deleted; `void` transitions status to `"void"` without GL reversal (the document never posted).

---

### 5.9 Customer & Vendor Statements

A statement is a period summary sent to a counterparty confirming their account standing.

**Customer Statement** — `GET /api/customers/{id}/statement?from_date=&to_date=`:
```json
{
  "customer": { "id": 1, "name": "Alpha Retail Group", ... },
  "period": { "from": "2026-01-01", "to": "2026-05-25" },
  "opening_balance": "0.00",
  "invoices": [ { "number": "INV-0001", "date": "...", "total": "...", "outstanding": "..." } ],
  "payments": [ { "date": "...", "amount": "..." } ],
  "closing_balance": "15000.00"
}
```

**Vendor Statement** mirrors the above but uses bills + bill-payments.

Frontend pages at `/customers/[id]/statement` and `/vendors/[id]/statement` render a print-friendly statement with date-range pickers, summary tiles (Opening Balance / Invoices Billed / Closing Balance), line-item tables for documents and payments, and a Print button. Accessible from the customer/vendor ledger page via "Print Statement" button.

---

## 7. REPORT CATALOG

```
                          ┌────────────────────┐
                          │   JournalEntry     │ ← source of truth
                          └─────────┬──────────┘
                                    │
        ┌──────────┬─────────┬──────┴──────┬──────────┬──────────┬─────────┐
        ▼          ▼         ▼             ▼          ▼          ▼         ▼
   Journal     Ledger    Trial Bal     Income      Balance    Cash Flow   Tax
                                       Stmt        Sheet      (indirect)  Summary
   /journal   /ledger   /trial-balance /pl         /balance   /cashflow   /tax
```

For **closed periods**, trial-balance and ledger reads can pull from materialised `AccountBalance` rows (written at period close) — O(accounts) instead of O(journal_entries). The open period still aggregates live.

| Report | Endpoint | What it computes |
|---|---|---|
| Journal | `GET /api/reports/journal` | Flat list of JEs ↔ Transaction ↔ Account, paginated, filterable |
| Ledger | `GET /api/reports/ledger?account_id=…&start=…&end=…` | JEs grouped by account, running balance per row; when date-filtered shows **Opening Balance** (pre-period net) and **Closing Balance** (`opening + debits − credits`, sign per account type) |
| Trial Balance | `GET /api/reports/trial-balance?start=…&end=…` | `SUM(debit), SUM(credit)` per account; verifies ∑Dr = ∑Cr |
| Income Statement | `GET /api/reports/income-statement` | Revenue (4xxx) − Expense (5xxx) for date range |
| Balance Sheet | `GET /api/reports/balance-sheet` | Assets = Liabilities + Equity (incl. current-period retained earnings) |
| Cash Flow | `GET /api/reports/cash-flow` | Indirect method: Net Income + non-cash + Δ working capital; **reconciling row** shows unclassified Δ bank balance in amber; ✓ when fully reconciled (IAS 7) |
| Tax Summary | `GET /api/reports/tax-summary` | Output GST (2200) − Input GST (1250) = Net GST Payable; income-tax slab estimate |
| AR Aging | `GET /api/invoices/aging` | Buckets Current/1–30/31–60/61–90/90+ of **outstanding** (gross − sum(allocations)); items include `customer_id` for drill-down |
| AP Aging | `GET /api/bills/aging` | Same for bills; items include `vendor_id` for drill-down |
| AR Aging page | `/aging/receivable` | Dedicated AR Aging report with drill-down to customer ledger; bucket summary cards are click-to-filter (click again or "Show all" to reset) |
| AP Aging page | `/aging/payable` | Same for AP; bucket cards click-to-filter |
| Product Ledger | `GET /api/reports/product-ledger` | Stock movements + running quantity per product; filter by store or **Consolidated** |
| Inventory Performance | `GET /api/reports/inventory-performance` | Per product: on-hand qty + value (qty × avg cost), low-stock flag, last-movement date, units sold + COGS over a period |
| Customer Performance | `GET /api/reports/customer-performance` | Per customer: revenue, invoice count, outstanding AR, avg days-to-pay; ranked |
| Dashboard KPIs | `GET /api/reports/dashboard` | Revenue, expense, AR/AP outstanding (net of allocations), overdue counts, low stock |
| Dashboard charts | `GET /api/reports/dashboard/charts?months=12` | 12-month series for chart components; Top Customers capped at 10 (v3.1) |
| Net Worth trend | `GET /api/reports/dashboard/net-worth?months=N` | Monthly cumulative Assets / Liabilities / Net Worth series (v3.1); one grouped query + Python cumulative sums, gap months carried forward |
| Report Builder | `POST /api/report-builder/run` | User-configurable ad-hoc report: column chooser, filter predicates, group-by/aggregates, pagination — over any whitelisted source; tenant isolation enforced by the engine |

**Hierarchical statements (V2.5).** In single-period mode, Trial Balance, Balance Sheet, and Income Statement roll up over the multi-level Chart of Accounts (`services/account_tree.py`): each parent's subtotal = its own direct balance + the sum of its descendant leaves, zero subtrees pruned. The payloads are nested trees — TB `{tree, totals}`, BS `{assets, liabilities, equity, totals}` (with a synthetic current-period retained-earnings line), P&L `{revenue, expenses, totals}` + `net_profit`. The frontend renders them with the `<AccountTree>` component (expand/collapse, parent subtotals, and click-through drill from a leaf line → its ledger → the underlying voucher). **Comparison mode** keeps the flat `{current, comparison}` shape.

**Voucher series.** Posted transactions carry a `voucher_type` (Sales `SL`, Purchase `PU`, Receipt `CR`, Payment `CP`, Journal `JV`, Credit-Note `CN`, Debit-Note `DN`) with per-type numbering; the Cash Book and Bank Book and the voucher-type filters on the ledgers read from it.

**Freeze panes (v3.1).** Table-based report pages (aging AR/AP, performance reports, GL/product ledgers, report-builder grid, healthcare + manufacturing reports, statements, telecom tracker) scroll inside a `.table-freeze` bounded viewport: the header row and totals row stay pinned while data scrolls, and wide reports also lock the first column (`.freeze-col`). See §1.1 UI System for mechanics; all sticky rules are reset in print.

---

## 8. API ENDPOINT CATALOG

Every route is mounted twice: at `/api/*` (legacy) and `/api/v1/*` (versioned alias). Future breaking changes ship under `/api/v2/`.

### 8.1 Auth, profile & settings
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/signup` | Create tenant + seed CoA + `owner` user (password ≥ 8) |
| POST | `/api/auth/login` | OAuth2 password → JWT + HttpOnly cookie + CSRF cookie + body `{access_token, role, csrf_token, must_change_password}`. Rejects inactive users (403); stamps `last_login_at` |
| POST | `/api/auth/logout` | Clears both cookies |
| GET | `/api/auth/me` | Current user (id, email, full_name, phone, avatar_url, role, must_change_password, created_at, last_login_at, tenant) |
| PATCH | `/api/auth/me` | Update own `full_name` / `phone` |
| POST | `/api/auth/change-password` | Verify current → set new (≥ 8); clears `must_change_password` |
| POST/DELETE | `/api/auth/me/avatar` | Upload (multipart, PNG/JPEG/GIF/WebP ≤ 5 MB) / remove own avatar |
| GET | `/api/auth/users/{id}/avatar` | Serve a tenant member's avatar (tenant-scoped; 404 cross-tenant) |
| GET | `/api/auth/invite/{token}` | Public — inspect a pending invite (email, role, company) |
| POST | `/api/auth/accept-invite` | Public — `{token, full_name, password}` → activates the User and logs in |
| GET/PATCH | `/api/settings` | Company name, fiscal year start, currency display, document prefixes |

### 8.1a Team / user management (`/api/users`, admin+)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/users` | List tenant members (role, is_active, last_login, …) |
| POST | `/api/users` | Create a member with a temporary password (returned once); `must_change_password=true` |
| PATCH | `/api/users/{id}` | Change `full_name` / `role` / `is_active`. Guards below |
| POST | `/api/users/{id}/reset-password` | Issue a new temporary password (forces change at next login) |
| DELETE | `/api/users/{id}` | Soft-delete (deactivate) — audit rows reference the user id |
| GET/POST | `/api/users/invites` | List pending / create a tokenized invite (7-day expiry) → `{token, accept_path}` |
| DELETE | `/api/users/invites/{id}` | Revoke a pending invite |

**Role guards** (enforced in `routers/users.py`): you cannot change your own role or deactivate yourself; only an **owner** may grant or modify the `owner` role; the **last active owner** cannot be demoted or deactivated.

### 8.2 Master data
| Method | Path | Purpose |
|---|---|---|
| GET/POST/PUT/DELETE | `/api/customers` (+ `/{id}`) | Hard-delete blocked when invoices exist (soft-delete via PUT `is_active=False`) |
| GET/POST/PUT/DELETE | `/api/vendors` (+ `/{id}`) | Same |
| GET/POST/PUT/DELETE | `/api/products` (+ `/{id}`) | Hard-delete blocked when line items reference |
| GET | `/api/products/stock-summary` | All stock-type products with current `stock_qty` and `avg_cost` |
| GET/POST/PUT/DELETE | `/api/accounts` (+ `/{id}`) | Chart of Accounts; hard-delete blocked when JEs exist |
| GET/POST/PUT/DELETE | `/api/bank-accounts` (+ `/{id}`) | Linked to a CoA Asset account |
| GET/POST/PUT/DELETE | `/api/tax-codes` (+ `/{id}`) | output \| input; CHECK rate ≥ 0 |
| GET/POST/DELETE | `/api/exchange-rates` | Upsert on `(date, from, to)`; CHECK rate > 0 |

### 8.3 Transactional
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/invoices` | List / create invoice; auto-posts JV + COGS sub-JV when stock |
| PATCH | `/api/invoices/{id}/status` | Manual override (`sent`, `void`, …) |
| GET | `/api/invoices/aging` | Outstanding-balance aging |
| GET/POST | `/api/bills` | Same shape as invoices |
| PATCH | `/api/bills/{id}/status` | — |
| GET | `/api/bills/aging` | — |
| GET/POST | `/api/payments-received` | Accepts `allocations: [{invoice_id, amount}]` + legacy single-invoice shortcut |
| GET/POST | `/api/bill-payments` | Same |
| POST | `/api/transactions` | Manual JV |
| GET | `/api/transactions/{id}` | JV detail with all JEs **+ `source_docs[]` + `is_reversed` + `reversed_by_id`** (§5.7.3) |
| POST | `/api/transactions/{id}/reverse` | Mirror JV + unwinds derived state (§5.6) |

### 8.4 Periods & audit
| Method | Path | Purpose |
|---|---|---|
| GET/POST/DELETE | `/api/periods` (+ `/{id}`) | List / create / delete period |
| PATCH | `/api/periods/{id}/lock` | Toggle lock (writes blocked when locked) |
| POST | `/api/periods/{id}/close` | Closing JV + materialise `AccountBalance` + lock |
| POST | `/api/periods/{id}/reopen` | Unlock + drop materialised balances |
| GET | `/api/audit-log` | Mutation history |

### 8.5 Recurring & reconciliation
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/recurring` | List/create templates |
| POST | `/api/recurring/run-due` | Worker endpoint — materialises all due templates |
| GET/POST | `/api/reconciliations` (+ `/{id}`) | Period bank reconciliation |
| PATCH | `/api/reconciliations/{id}/lines/{lid}` | Match/unmatch line |
| POST | `/api/reconciliations/{id}/close` | Lock the reconciliation |

### 8.6 Bank imports
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/bank-imports` | List / upload CSV (multipart); 409 on duplicate file |
| GET | `/api/bank-imports/{id}/lines` | All statement lines |
| POST | `/api/bank-imports/{id}/auto-match` | Amount + date-window matching |
| PATCH | `/api/statement-lines/{id}` | Manual match by `matched_transaction_id` |

### 8.7 Reports
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/reports/journal` | Paginated JEs |
| GET | `/api/reports/ledger` | Per-account running balance |
| GET | `/api/reports/trial-balance` | Per-account Dr/Cr totals |
| GET | `/api/reports/income-statement` | P&L |
| GET | `/api/reports/balance-sheet` | A = L + E |
| GET | `/api/reports/cash-flow` | Indirect method |
| GET | `/api/reports/tax-summary` | GST + income-tax slabs |
| GET | `/api/reports/dashboard` | KPIs (outstanding net of allocations) |
| GET | `/api/reports/dashboard/charts?months=12` | Chart series (Top Customers capped at 10, v3.1) |
| GET | `/api/reports/dashboard/net-worth?months=N` | Monthly cumulative Assets / Liabilities / Net Worth series (v3.1) |
| GET | `/api/reports/product-ledger?product_id=…&store=…` | Stock movements + running qty; `store=all` for consolidated view |
| GET | `/api/reports/inventory-performance?start=…&end=…` | Per-product on-hand qty/value, low-stock flag, last movement, units sold + COGS |
| GET | `/api/reports/customer-performance?start=…&end=…` | Per-customer revenue, invoice count, outstanding AR, avg days-to-pay |
| GET | `/api/customers/{id}/ledger?start=…&end=…` | AR sub-ledger — opening, period activity (qty_out + Dr/Cr), running balance, closing (§5.7.2) |
| GET | `/api/vendors/{id}/ledger?start=…&end=…` | AP sub-ledger — credit-normal (positive = owed) |
| GET | `/api/products/{id}/stock-card?start=…&end=…` | StockMovement-driven qty + value card (IAS 2.36(d) reading) |

### 8.7a Customer & Vendor Statements
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/customers/{id}/statement?from_date=&to_date=` | Account statement: opening balance, period invoices (outstanding per line), period payments, closing balance |
| GET | `/api/vendors/{id}/statement?from_date=&to_date=` | AP mirror: opening balance, period bills, period bill payments, closing balance |

### 8.7b Sales Commissions
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/commissions/plans` | List all commission plans with staff name |
| POST | `/api/commissions/plans` | Create a plan (rate, targets, effective dates) |
| PUT | `/api/commissions/plans/{id}` | Update a plan |
| DELETE | `/api/commissions/plans/{id}` | Remove a plan |
| GET | `/api/commissions/staff` | List all users who have/had a plan |
| GET | `/api/commissions/ledger` | List all computed commission entries |
| POST | `/api/commissions/compute` | Compute commissions for a period (month), creates ledger entries |
| POST | `/api/commissions/ledger/{id}/approve` | Approve a computed entry for posting |
| POST | `/api/commissions/ledger/{id}/post` | Post GL entry (Dr Commission Expense / Cr Commissions Payable) |

### 8.7c Promotional Price Discounts
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/promo-rules` | List all promo rules |
| POST | `/api/promo-rules` | Create a rule (product, min_qty, discount_pct, date range) |
| PUT | `/api/promo-rules/{id}` | Update a rule |
| DELETE | `/api/promo-rules/{id}` | Remove a rule |
| POST | `/api/promo-rules/check` | Given invoice lines, return applicable discount suggestions |

### 8.7d User Permissions (Granular Access Control)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/permissions/me` | Current user's effective permission set (all resources) |
| GET | `/api/permissions/resources` | Full list of 60 protected resource keys |
| GET | `/api/permissions/users/{id}` | Effective permissions for another user (admin only) |
| PUT | `/api/permissions/users/{id}` | Set/clear permission overrides for a user (admin only) |
| PATCH | `/api/permissions/users/{id}/my-data-only` | Toggle the my-data-only flag for a user |

### 8.8 CSV bulk import (master data)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/import/{entity}/sample` | Blank CSV template |
| POST | `/api/import/accounts` \| `customers` \| `vendors` \| `products` \| `transactions` | Bulk create; per-row error collection; partial-success OK |

### 8.9 Telecom franchise (V3 — `business_model = telecom_franchise`)
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/telecom/operators` · `/tracker-accounts` | Operator + tracker (MSR) wallet master data |
| POST | `/api/telecom/tracker/deposits` · `/load-orders` · `/stock-debits` | Fund wallet, place 3% load order, procure SIM/IMSI stock |
| GET | `/api/telecom/tracker/transactions` | Tracker txn ledger |
| GET/POST | `/api/telecom/rso/agents` · `/rso/retail-outlets` | RSO channel master data |
| POST | `/api/telecom/load-transfers/msr-to-rso` · `/rso-to-retail` | Distribute load down the chain |
| GET/POST | `/api/telecom/rso/collections` | RSO daily cash collection (load + stock ± variance) |
| POST | `/api/telecom/rso/sim-issues` | Issue SIM stock to an RSO |
| GET | `/api/telecom/sim/batches` · GET/POST `/sim/activations` | SIM inventory + activations |
| POST | `/api/telecom/sim/activations/accrue-commission` · `/sim/counter-sales` | Accrue activation commission; walk-in sale |
| GET/POST | `/api/telecom/fca/events` · `/kpi/targets` | FCA counter + monthly targets |
| POST | `/api/telecom/fca/target-commission` · `/fca/target-penalty` | Monthly target settlement |
| GET/POST | `/api/telecom/mm/accounts` · POST `/mm/top-up` · `/mm/deposit` · `/mm/withdrawal` · `/mm/commission` · `/mm/reconcile` · GET `/mm/transactions` | Mobile-money agency |
| GET/POST | `/api/telecom/postpaid/connections` · POST `/postpaid/bills` · `/postpaid/collect` · `/postpaid/remit` · GET `/postpaid/cycles` | Postpaid billing on operator's behalf |
| GET/POST | `/api/telecom/commissions/statements` · POST `/commissions/settle` | Commission statement + reconciliation |
| GET/POST | `/api/telecom/franchise/agreements` · POST `/franchise/capitalise-fee` · `/franchise/amortise` · `/franchise/royalty/accrue` · `/franchise/royalty/pay` | Franchise fee + royalty |
| GET/POST | `/api/telecom/imei` | Device IMEI inventory |
| GET | `/api/telecom/reports/*` | 9 franchise reports (see §4.8) |

---

## 9. SECURITY MODEL

### 9.1 Multi-tenant isolation

Every query in every endpoint filters by `tenant_id` from the JWT. Cross-tenant lookups return **404, not 403**, to prevent enumeration. The central posting service `services.posting._check_accounts_belong_to_tenant` is a belt-and-braces check that no JV can post into another tenant's chart of accounts.

### 9.2 RBAC

| Role | Reads | Writes | Period close / lock | Account delete | Manage users |
|---|---|---|---|---|---|
| `viewer` | ✔ | — | — | — | — |
| `accountant` | ✔ | ✔ | — | — | — |
| `admin` | ✔ | ✔ | ✔ | ✔ | ✔ (not owner role) |
| `owner` | ✔ | ✔ | ✔ | ✔ | ✔ (incl. owner role) |

DB-level `CHECK role IN ('owner','admin','accountant','viewer')`. First user of a tenant becomes `owner` at signup. Dependencies in `routers/common.py`:
- `CurrentUserDep` — any authenticated **and active** user. `get_current_user` re-checks `is_active` on **every** request, so deactivating a member locks them out immediately even with a still-valid token (403).
- `WriteUserDep` — `accountant+`
- `AdminUserDep` — `admin+` (gates the entire `/api/users` surface)

`require_min_role(role)` factory generates more if needed.

### 9.2a Multi-user onboarding & guards

Two ways to add members to a tenant (no email provider required):
1. **Admin-created** — `POST /api/users` mints the account with a temporary password returned **once**; `must_change_password=true` forces a reset at first login (the SPA redirects such logins to `/profile?changePassword=1`).
2. **Invite link** — `POST /api/users/invites` creates a `UserInvite` (unique token, 7-day expiry). The recipient opens `/accept-invite?token=…`, sets name + password, and `POST /api/auth/accept-invite` materialises an active `User` and logs them in. A copyable link is the fallback when email isn't wired.

Management guards (see §8.1a): no self-role-change, no self-deactivation, owner-role changes are owner-only, and the last active owner is protected from demotion/deactivation — so a tenant can never be locked out of its own admin surface.

### 9.3 Auth: JWT + HttpOnly cookie

```
LOGIN
  → POST /api/auth/login  (OAuth2 password form)
  → returns: { access_token, role, csrf_token }
  → sets:    Cookie eb_access (HttpOnly, SameSite=Lax, Secure in prod)
             Cookie eb_csrf   (non-HttpOnly so SPA can read it)

AUTHENTICATING A REQUEST
  • Bearer header (SDK / curl / mobile):
      Authorization: Bearer <token>      ← preferred for non-browser clients
  • OR cookie (browser SPA):
      eb_access cookie set automatically
  Backend tries Bearer first, then cookie.
```

JWT payload: `{sub, tenant_id, full_name, role, exp}`. HMAC-SHA256. `JWT_SECRET_KEY` env var required — startup fails if missing/default when `APP_ENV=production`.

### 9.4 CSRF (Double-Submit-Cookie)

`services/csrf.CsrfMiddleware` rejects mutating requests authenticated by cookie unless the `X-CSRF-Token` header matches the `eb_csrf` cookie.

```
Browser SPA flow:
  1. POST /api/auth/login  → response body has csrf_token, cookies set
  2. SPA reads csrf_token (either from body or by reading eb_csrf cookie)
  3. For every mutating call:
       fetch(url, {
         method: 'POST',
         credentials: 'include',
         headers: { 'X-CSRF-Token': csrf_token },
         body: ...
       })

Bearer SDK flow:
  No CSRF — the Authorization header proves intent.

Exempt endpoints: /api/auth/signup · /api/auth/login · /api/auth/logout
(They mint the tokens; can't require them.)
```

### 9.5 Login throttle

`LoginAttempt(ip, attempted_at)` table. Sliding 60s window, 10 attempts per IP. State is in the DB so workers share the counter and it survives restarts. Old rows pruned in the same call that reads them — no cron job.

### 9.6 Period lock

Every call to `services.posting.post_transaction` runs `_check_period_locked(tenant_id, date)`. A `PostingError(400)` is raised if the txn date falls in an `AccountingPeriod` with `is_locked=true`. Backdated edits into closed periods are impossible.

### 9.7 Idempotency keys

`services/idempotency.IdempotencyMiddleware` watches for `Idempotency-Key` header on mutating methods. If the `(tenant_id, key)` pair has a cached 2xx response in `IdempotencyKey`, the original body is returned with `Idempotency-Replay: true` and no handler runs. Use it on any flaky mobile network to make POSTs safely retryable.

---

## 10. ENGINEERED INVARIANTS

### Accounting
- **Σ Dr == Σ Cr** exact (`Decimal` equality, no float tolerance). Enforced in `services.posting._validate_entries` and by DB CHECK on every JournalEntry row (single-sided rule + non-negative).
- **Money is `Decimal`** end-to-end. `NUMERIC(18,4)` columns; `ROUND_HALF_EVEN` (banker's rounding) when quantizing to cents at the boundary.
- **Period lock** before every GL write.
- **Inventory at WAvg** (IAS 2). Stock receipts append a layer; sales relieve at running avg; concurrent updates serialized via `SELECT FOR UPDATE`.
- **Audit log** on every mutation (user, action, entity, JSON detail).
- **Reversal** never deletes — `is_reversed=true` + link to the reversing JV.

### Software
- **Tenant isolation** at the data layer; central posting service verifies every account belongs to the caller's tenant.
- **Atomic numbering** via `SequenceCounter` with `SELECT FOR UPDATE`. Two concurrent POSTs cannot mint the same invoice/bill number; reversal/delete doesn't reset the sequence.
- **Idempotency keys** for safe POST retry.
- **API versioning** — every route at `/api/*` and `/api/v1/*`.
- **CSRF** double-submit-cookie on cookie-auth path.
- **DB-backed login throttle** — shared across workers.
- **Schema bootstrap** — **Alembic** migrations are the source of truth (`backend/alembic/versions/`). `create_all()` still runs on startup so a fresh checkout boots without a migration step; the standalone installers + packaged desktop run `alembic upgrade head` on launch, so new columns/tables reach upgraded users non-destructively (no manual `ALTER`/reset). SQLite caveat: strip FK lines on ALTER and guard new tables with `has_table(...)`.

---

## 11. VERIFICATION & SMOKE TESTS

```
END-TO-END SMOKE
────────────────
1. Signup    → POST /api/auth/signup       tenant + owner created
2. Login     → POST /api/auth/login        Bearer + cookie + CSRF
3. Customer  → POST /api/customers         Master data
4. Invoice   → POST /api/invoices          Dr AR / Cr Revenue (+ COGS if stock)
5. Payment   → POST /api/payments-received Dr Cash / Cr AR + allocation
6. /journal  → JV-NNNNN appears
7. /trial-balance → ∑Dr == ∑Cr (warning hidden)
8. /balance       → Assets == Liabilities + Equity
9. /invoices/aging → outstanding net of payment
10. Reverse the payment JV → allocation removed, invoice 'sent' again
11. /trial-balance → still balanced
12. Close period → closing JV + AccountBalance rows
13. Backdated invoice → 400 (period locked)
14. Reopen period → balances dropped, lock cleared
```

Test suite: **404 pytest tests** across `backend/tests/`. Run: `cd backend && PYTHONPATH=. uv run pytest`.

---

## 12. DEFAULT CHART OF ACCOUNTS

Auto-seeded on signup. 22 accounts across the five standard types:

| Code | Name | Type | First-touch endpoint |
|---|---|---|---|
| 1000 | Cash in Hand | Asset | Payments default |
| 1010 | Bank | Asset | Bank account default |
| 1100 | Accounts Receivable | Asset | Invoice default |
| 1200 | Inventory (Raw Material) | Asset | Stock bills |
| 1201 | Finished Goods Inventory | Asset | Manual |
| 1250 | GST Receivable (Input) | Asset | Bill GST |
| 1300 | Work-in-Progress | Asset | Manual |
| 2000 | Accounts Payable | Liability | Bill default |
| 2100 | Advances Received | Liability | Manual |
| 2200 | GST Payable (Output) | Liability | Invoice GST |
| 3000 | Owner Capital | Equity | Manual (opening) |
| 3010 | Drawings | Equity | Manual |
| 3100 | Retained Earnings | Equity | Period close (auto) |
| 4000 | Sales Revenue | Revenue | Invoice default |
| 4900 | Other Income | Revenue | Manual |
| 5000 | General Expenses | Expense | Bill default |
| 5010 | Cost of Goods Sold | Expense | Stock sales (auto) |
| 5050 | Depreciation Expense | Expense | Recurring/manual |
| 5100 | Labour & Wages | Expense | Manual |
| 5300 | Rent & Utilities | Expense | Recurring/manual |
| 5400 | Transport & Delivery | Expense | Manual |
| 5900 | Other Expenses | Expense | Manual |

**Model-specific CoA:** the `manufacturing` model extends this with raw-material/WIP/FG layers, the custodial memo pair `1210/2150`, direct labour and overhead. The `telecom_franchise` model swaps in a dedicated **56-account franchise CoA** seeded by `db.py` (`_COA_TELECOM_FRANCHISE_EXTRA`): Tracker Deposit `1210`, Load Float `1211`, RSO/Retail load receivables `1212/1213`, MM float `1214`, SIM/IMSI/device inventory `1200–1204`, Commission Receivable `1110`, Franchise Intangible `1300`/Accum. Amort `1301`; Operator Payable `2010`, MM Float Liability `2100`, Postpaid Collections Payable `2110`, Royalty Payable `2120`; revenue `4000–4061` (incl. 3% load uplift `4020`, FCA target commission `4060`); COGS/expense `5010–5090` (fee amortisation `5030`, royalty `5040`, tracker/float variance `5070`, target penalty `5090`). See §4.8.

---

## 13. MIGRATION HISTORY

| Revision | Title | What it adds |
|---|---|---|
| `0001_baseline` | Baseline from SQLModel metadata | All initial tables (22) |
| `0002_user_role` | RBAC | `User.role` + CHECK |
| `0003_p3_tax_alloc_recurring` | P3 tables | `TaxCode`, `PaymentAllocation`, `RecurringTemplate` |
| `0004_idempotency_keys` | P4 | `IdempotencyKey` |
| `0005_multi_currency` | P5 | `Tenant.base_currency`; `Invoice.currency` + `exchange_rate`; `Bill.currency` + `exchange_rate`; `ExchangeRate` table |
| `0006_bank_imports` | P6 | `BankStatementImport` + `StatementLine` |
| `0007_account_balance` | P7 | `AccountBalance` (materialised on period close) |
| `0008_sequence_counter` | Commit B | `SequenceCounter` for atomic doc numbering; backfills existing tenants at `max(existing)+1` |
| `0009_login_attempts` | Commit C | `LoginAttempt` for DB-backed throttle |
| `0010_business_model` | V2.1 | `Tenant.business_model` + `Tenant.enabled_modules` + `Account.is_memo` |
| `0011_stock_locations` | V2.2 | `StockLocation` + `StockMovement` + `InventoryLayer.location_id`/`owner_customer_id`/`lot_no`; backfills `MAIN` per tenant and `GODOWN`/`WIP` for manufacturing |
| `0012_bom_rate_plans` | V2.3 | `BomHeader`, `BomLine`, `RatePlan`, `CustomerRatePlan` |
| `0013_grn_production_order` | V2.4 | `GoodsReceiptNote`, `GRNLine`, `ProductionOrder` (with state-machine CHECK) |
| telecom franchise (V3) | V3.1–3.5 | 23 `tc_*` tables (`models_telecom.py`); `Tenant.business_model` CHECK extended with `telecom_franchise` |
| user/team (V3.6) | V3.6 | `User.phone`/`avatar_url`/`must_change_password`/`created_at`/`last_login_at` columns + `UserInvite` table |

All migrations are idempotent (check inspector before `create_table` / `add_column`), so they can safely be re-run on a fresh-baseline DB. In dev (`SCHEMA_BOOTSTRAP=create_all`) new tables are auto-created; new columns on existing tables are added with a one-shot `ALTER TABLE` (SQLite-safe).

| `0014_credit_notes` | G-02 | `CreditNote`, `CreditNoteLine` |
| `0015_fixed_assets` | G-05 | `FixedAsset`, `DepreciationEntry` |
| `0016_tenant_cost_method` | G-09 | `Tenant.cost_method` (`wavg`/`fifo`) |
| `0017_budget` | G-10 | `Budget` |
| `0018_analytic_accounts` | G-07 | `AnalyticAccount`, `JournalEntry.analytic_account_id` |
| `0019_deferred_revenue` | G-08 | `DeferredRevenueSchedule`, `Product.is_deferred/recognition_months` |
| `0019b_purchase_orders` | G-06 | `PurchaseOrder`, `PurchaseOrderLine` |
| `0019c_invoice_payment_link` | G-12 | `Invoice.payment_link_url/payment_link_status` |
| `0020_returns_and_advances` | S13 | `DebitNote`, `DebitNoteLine`, `CustomerAdvance`, `VendorAdvance`; CoA `1260`/`2310` |
| `0020_user_rights` | #70 | `UserPermission` (tenant/user/resource/access_level/my_data_only); `User.created_by_id`; `my_data_only` column |
| `0021_commissions` | #71 | `CommissionPlan` (user, rate, targets, effective dates); `CommissionLedger` (computed entry, status, GL posting) |
| `0022_promo_rules` | #72 | `PromoRule` (product, min_qty, discount_pct, date range); `InvoiceLine.discount_pct` + `InvoiceLine.promo_rule_id` |

---

## NEW TRANSACTION CYCLES (Sprint 7–12)

These cycles route through the same central `services/posting.py` writer, so every one is balanced and audit-traceable.

### Credit Note (ISA 240)
```
Issue CN  →  Dr 4000 Sales Revenue / Cr 1100 AR   (reverse of an invoice)
            CN-NNNN sequence · optional link to original invoice · status draft→posted→applied
```

### Fixed Asset Depreciation (IAS 16)
```
Register asset (cost, salvage, useful life, method)
Run depreciation per period  →  Dr 5050 Depreciation Expense / Cr 1090 Accumulated Depreciation
Book value = cost − accumulated; stops at salvage value
```

### Purchase Order → Bill (IAS 2.11)
```
Raise PO (PO-NNNN)  →  Approve (admin+)  →  Convert to Bill (BILL-NNNN)
On convert:  Dr Expense / Cr 2000 Accounts Payable   (po.bill_id linked, status=billed)
```

### Deferred Revenue (IFRS 15) — services
```
Invoice deferred item  →  Dr 1100 AR / Cr 2300 Deferred Revenue
Run recognition / period  →  Dr 2300 Deferred Revenue / Cr 4020 Revenue
```

### FX Revaluation (IAS 21.23)
```
Period end: outstanding × (closing_rate − original_rate)
Gain:  Dr 1100 AR / Cr 4901 Unrealised FX Gain-Loss
Loss:  Dr 4901 / Cr 1100 AR
```

### Sales Return (enhanced Credit Note, IAS 2 / ISA 240)
```
Value:    Dr 4000 Revenue (+ Dr 2200 GST) / Cr 1100 AR
Restock:  Dr 1200 Inventory / Cr 5010 COGS  (Q × avg_cost)  + stock_qty += Q
```

### Purchase Return (Debit Note vs original bill, IAS 2.11)
```
Dr 2000 AP / Cr 1200 Inventory (at original layer cost) + Cr 1250 GST Input
stock_qty -= Q   (return_to_vendor; capped at the bill's remaining layer qty)
```

### Customer Advance (prepayment received)
```
Record:  Dr 1010 Bank / Cr 2310 Customer Advances
Apply:   Dr 2310 Customer Advances / Cr 1100 AR   (settles an invoice)
```

### Vendor Advance (prepayment paid)
```
Record:  Dr 1260 Advances to Vendors / Cr 1010 Bank
Apply:   Dr 2000 AP / Cr 1260 Advances to Vendors  (settles a bill)
```

### Period Close (IAS 1)  — POST /api/periods/{id}/close?mode=soft|year_end
```
mode=soft (monthly/quarterly):  lock period + snapshot AccountBalance.
                                P&L is NOT zeroed (within-year P&L stays cumulative).
mode=year_end:                  Dr Revenue / Cr Expense / Cr-or-Dr Retained Earnings
                                (net income → 3100), then lock + snapshot.
Balance-sheet accounts carry forward automatically — balances are computed live
from the all-time GL, so the next period opens at the prior closing balance
(no opening-balance JV). GET /api/periods/{id}/close-preview shows net income first.
```

### Tenant-aware guidance
`/guide` and `/workflow` read `tenant.business_model` from `/api/auth/me` and show only the cycles
relevant to that model (inventory & purchase orders for stock-keeping models, deferred revenue for
services, production for manufacturing, tracker/RSO for telecom). See USER_GUIDE §18 for the matrix.

---

---

## IN-APP UPDATE CHECK

Easy-Books has a **proactive auto-update system** (v3.0) that checks for updates on every `DashboardLayout` mount and prompts admin/owner users immediately.

### Update components

| Component | Role |
|-----------|------|
| `UpdateAvailablePopup.tsx` | Bottom-sheet notification with **Update Now** / **Later** (session) / **Skip version** (SHA-keyed) actions |
| `UpdateProgressScreen.tsx` | Fullscreen portal during active update — animated ring, 4-phase labels (Pull → Compile → Bundle → Start), polling, success/error states |
| `UpdateModal.tsx` | Settings → Updates tab — manual trigger; shows CLI command on script/web installs, calls Electron bridge on desktop |

### Install-type behaviour

| Install type | Auto-check | Update mechanism |
|---|---|---|
| **Desktop (Electron)** | On launch via `electron-updater` | Downloads and installs in background; **Restart to apply** prompt when ready; `alembic upgrade head` runs on next launch |
| **Script install** (`install-and-run.*`) | `DashboardLayout` polls `/api/system/update/status` | `UpdateProgressScreen` runs `POST /api/system/update` (`git pull` + migrations + rebuild); or user runs `update.bat` / `update.sh` manually |
| **Web / dev** | Same as script install | Same backend endpoints |

### Wiring

- `desktop/preload.js` — exposes `window.easybooks.checkForUpdates()` / `onUpdateAvailable(cb)` / `onUpdateDownloaded(cb)` / `installUpdate()` over the context bridge
- `desktop/main.js::wireAutoUpdater()` — configures `autoUpdater` for the GitHub releases feed; emits IPC events consumed by the renderer
- `backend/routers/system.py` — `GET /api/system/update/status` (GitHub Commits API), `POST /api/system/update` (shell + alembic + npm), `GET /api/system/update/changelog`
- `eb.just-updated` localStorage key — triggers a congratulations toast after the page reloads following a successful update

---

---

## PRINT SYSTEM (v2.7, overhauled v3.1)

### Dot-matrix format (v3.1)

All printouts render in **Courier New**, black-and-white, no background fills — sized for dot-matrix / continuous-paper printing. Tailwind v4 font-size CSS variables are overridden under `@media print` so screen sizing never leaks into printouts, and row spacing is compressed for denser data fit per page.

### Orientation rules

`PrintHeader` accepts an `orientation` prop. When `"landscape"` is passed it dynamically injects `<style data-print-landscape>@media print { @page { size: A4 landscape; } }</style>` via `useEffect` (CSS `@page` cannot be toggled by class in standard CSS). Portrait is the default via `globals.css`.

| Landscape pages | Portrait pages |
|-----------------|----------------|
| AR/AP Aging, Customer Performance, Inventory Performance, Product Ledger, **General Ledger (v3.1)**, Journal list, Invoices list, Bills list, Products list, Customer/Vendor Ledgers, Stock Card | Cash Book, Bank Book, Balance Sheet, P&L, Trial Balance, Cash Flow, Tax Summary, Statements, Payments lists, CoA, all voucher print pages |

### Date helpers (`frontend/src/lib/utils.ts`)

| Helper | Input | Output |
|--------|-------|--------|
| `fmtDate(str)` | ISO string `"2026-06-20"` or datetime `"2026-06-20T…"` | `"20-06-26"` |
| `fmtDateJs(date)` | JS `Date` object | `"20-06-26"` |

All 37+ date-bearing pages import and use these helpers.

### Print hygiene CSS (`globals.css` + `print:hidden`)

- `.print-landscape` no-op class replaced by dynamic `<style>` injection
- `@media print { td span, th span { ... } }` flattens any remaining badge pills to plain text
- `print:hidden` Tailwind class hides: FilterBar, Pagination, SortableHeader, all toolbar buttons, checkbox columns, action columns
- Greenbar row shading removed; output is plain white with light border-only row dividers
- **Freeze-pane reset (v3.1):** all `.table-freeze`/`.freeze-col` sticky positioning and `max-height` are neutralised under `@media print` so reports always paginate in full — any new freeze rule must be added to this reset block too

### Column layout in tabular reports

- Date and JV# `<td>` cells carry `whitespace-nowrap` — content never breaks across lines
- Description columns have no `max-w-*` constraint — absorb remaining table width naturally
- Amount columns carry `whitespace-nowrap` and `font-mono`
- Voucher type badges removed from all report tables — the JV# prefix (CP / SL / BR etc.) already encodes the type

---

---

## MODULE SYSTEM — DEVELOPER REFERENCE

### Overview

Easy-Books uses an installable module system modelled after Odoo's App Store. Modules are defined statically in `backend/db.py` (`MODULE_REGISTRY`) and control:

1. Which sidebar sections are visible (via `forModule` in `frontend/src/lib/nav.ts`)
2. Which modules a tenant has enabled (stored as a JSON list in `Tenant.enabled_modules`)
3. Future per-module billing metadata (`Tenant.module_meta`)

### Adding a new module

1. **Register it in `MODULE_REGISTRY`** (`backend/db.py`):
   ```python
   "my_module": {
       "label": "My Module",
       "description": "One-line description for the Apps card.",
       "category": "Operations",      # Core | Operations | HR | Industry
       "icon": "Package",             # lucide-react icon name (string)
       "deps": ["base"],              # IDs of required modules (transitive)
       "always": False,               # True = cannot be uninstalled
       "tier": "free",                # billing tier (future use)
       "nav_sections": ["MySection"], # sidebar section names it enables
   }
   ```

2. **Add it to `MODULES_BY_MODEL`** if it should be included by default for a business model.

3. **Add the nav items** in `frontend/src/lib/nav.ts`:
   - Add each nav item with `forModule: "my_module"`.
   - Add the section name to `ALL_SECTIONS` (controls render order; System stays last).

4. **Add the icon to `ICON_MAP`** in `frontend/src/app/onboarding/page.tsx` so it renders in the onboarding module picker.

5. **No migration needed** — `enabled_modules` is a freeform JSON string; the new module ID is simply absent from existing tenants until they install it.

### `forModule` nav gate pattern

Every nav item that belongs to an optional module carries:
```ts
{ label: "My Feature", href: "/my-feature", icon: SomeIcon, section: "MySection", forModule: "my_module" }
```

`Sidebar.tsx` reads `installedModules` from `ModuleContext` and calls:
```ts
if (i.forModule && !installedModules.has(i.forModule)) return false
```

Items with no `forModule` (or `forModule: undefined`) are always visible.

### Module API endpoints

| Endpoint | Behaviour |
|----------|-----------|
| `GET /api/modules` | Lists all `MODULE_REGISTRY` entries with `installed` flag and metadata for the current tenant |
| `POST /api/modules/{id}/install` | Resolves transitive deps via `_all_deps()`, adds all to `enabled_modules`, writes `module_meta[id].installed_at` |
| `POST /api/modules/{id}/uninstall` | Blocks if `module.always` or if any installed module lists this one in its deps |

Both mutating endpoints require `role in ("admin", "owner")`.

### Legacy `enabled_modules` normalization

Old tenants stored strings like `["invoicing","billing","manual_jv"]`. `_get_enabled()` in `routers/modules.py` detects this by checking if any stored value appears in `MODULE_REGISTRY`. If none match, it falls back to `MODULES_BY_MODEL.get(tenant.business_model, ["base"])`. No data migration SQL is needed.

### Onboarding flow (developer view)

```
POST /api/auth/login
  → backend: if enabled_modules == ["base"] AND module_meta == {} → onboarding_required: true
  → frontend: login page detects flag → router.push("/onboarding")

/onboarding page (standalone, no sidebar):
  → GET /api/modules
  → user toggles optional modules (deps auto-added client-side + server-side)
  → POST /api/modules/{id}/install for each selection (sequentially; server resolves deps again)
  → localStorage.setItem("eb.onboarded.<email>", "1")
  → router.replace("/dashboard")

OnboardingGuard (in DashboardLayout, inside ModuleProvider):
  → safety net for direct URL navigation
  → if installedModules.size === 1 && has("base") && no localStorage flag → redirect to /onboarding
```

---

## UPGRADE WORKFLOW

### Three paths to upgrade

**Script install (macOS / Linux):**
```bash
cd ~/easy-books
./update.sh
```

**Script install (Windows):** Double-click `update.bat` in the Easy-Books folder.

**Desktop app:** The app checks for updates automatically on every launch. When a new release is available you will see an in-app prompt — click **Download** then **Restart** to apply. Manual check: **Settings → Check for Updates**.

**Developer mode:**
```bash
git pull
cd backend && uv sync && uv run alembic upgrade head
cd ../frontend && npm install && npm run build
# Restart servers
```

### What happens under the hood

1. `git pull --ff-only` — fetches the new code.
2. `uv sync` — updates backend Python dependencies.
3. `alembic upgrade head` — applies any pending schema migrations forward; existing data is preserved.
4. Frontend rebuild — triggered automatically when the commit hash differs from `frontend/.next/.built-commit`; `NEXT_PUBLIC_APP_VERSION` is injected at build time so the version badge is accurate.
5. Servers restart.

### Data safety guarantee

User data lives in `~/.easy-books` (Linux/macOS) or `%USERPROFILE%\.easy-books` (Windows) — completely outside the app folder. No update step ever touches this directory.

### Auto-backup before migrations

Before each `alembic upgrade head` run the installer writes a timestamped backup of the SQLite database to `~/.easy-books/backups/database_YYYYMMDD_HHMMSS.bak`. Restore by stopping the app and copying the `.bak` file back to `~/.easy-books/database.db`.

### Version check

- **In-app:** Settings → About — shows the version badge (reads `NEXT_PUBLIC_APP_VERSION` in production, live-fetches `/api/version` in dev mode).
- **API:** `GET /api/version` — returns `{"version": "x.y.z", "alembic_head": "..."}`.
- **Settings → Check for Updates** — compares running version to latest GitHub Release.

---

> **Last updated:** 2026-06-28
> **Branch:** `main`
> **Live demo:** `./dev.sh` (backend :8000, frontend :3000)
> **Repository:** https://github.com/bilalpiaic/Easy-Books
