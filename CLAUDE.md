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
| `main.py` | FastAPI bootstrap — middleware wiring and router mounts (~80 lines) |
| `models.py` | SQLModel table + schema definitions (includes `ProductCategory` for the 2-level product taxonomy). `Account` has `parent_id` + `is_group` (multi-level CoA; posting to active leaves only). `Product` has `is_deferred` + `recognition_months` (deferred revenue). `DeferredRevenueSchedule` tracks IFRS-15 recognition per invoice. `UserPermission` — sparse override table keyed by `(tenant_id, user_id, resource_key)` with `access_level` (`none/view/edit`) and `my_data_only` flag; module-gated via `settings.user_rights_enabled`. `CommissionPlan` + `CommissionLedger` — rate/target plans per user; compute → approve → post GL entry flow. `PromoRule` — product/min-qty/discount-pct rules; `InvoiceLine.discount_pct` + `promo_rule_id` apply the discount (`amount = qty × rate × (1 − discount_pct/100)`). |
| `models_telecom.py` | 23 `tc_*` tables for the Telecom Franchise business model |
| `models.py` (`UserDashboardLayout`) | Per-user dashboard layout KV — `(tenant_id, user_id)` → opaque `layout` JSON; schema-agnostic (v3 sparse breakpoint overrides). `GET/PUT /api/dashboard/layout`. |
| `db.py` | Engine creation, startup seeding (default tenant + CoA + admin user + 5 demo tenants). **The default Chart of Accounts is hierarchical** — a shared group skeleton (`_COA_GROUPS`: `1`/`11`/`12`/`2`/`21`/`3`/`4`/`41`/`49`/`5`/`51`/`52`/`59`) + leaf accounts carrying `parent_code`; `_coa_for()` yields 6-tuples `(code,name,type,is_memo,parent_code,is_group)`; `seed_data` inserts in two passes (create all → wire `parent_id`). Posting is restricted to active leaf accounts. The three `_coa_for` consumers (`seed_data`, `seed_demo._ensure_coa`, settings model-switch) all do this two-pass wiring. |
| `auth.py` | JWT encoding/decoding, bcrypt password hashing |
| `routers/` | 40+ domain routers (accounts, invoices, bills, payments, users, telecom, reports, credit_notes, debit_notes, advances, assets, budgets, purchase_orders, analytic_accounts, deferred_revenue, commissions, promo_rules, permissions, …) |
| `routers/admin.py` | Demo-data management: seed all 5 demo tenants on demand / purge them (admin+). Backs the **Settings → Sample / Demo Data** card. |
| `routers/product_categories.py` | `ProductCategory` CRUD — 2-level taxonomy (parent category → sub-category). Delete blocked while sub-categories or products exist. |
| `routers/commissions.py` | `CommissionPlan` CRUD + `GET /api/commissions/staff` (users eligible for commissions) + `GET /api/commissions/ledger` + `POST /compute` (period commission calculation) + `POST /ledger/{id}/approve` + `POST /ledger/{id}/post` (creates `Dr Commission Expense / Cr Commissions Payable` GL entry). |
| `routers/promo_rules.py` | `PromoRule` CRUD + `POST /api/promo-rules/check` — given a list of invoice lines returns applicable discount suggestions; "Apply Promos" button on InvoiceForm applies them. |
| `routers/permissions.py` | Granular access control — `GET /api/permissions/me` (current user's rights), `GET /api/permissions/resources` (60-resource registry), `GET /api/permissions/users/{id}`, `PUT /api/permissions/users/{id}` (admin matrix update), `PATCH /api/permissions/users/{id}/my-data-only`. |
| `routers/customers.py` | Customer CRUD + `GET /api/customers/{id}/statement?from_date=&to_date=` — opening balance (pre-period payments), period invoices with per-line outstanding, period payments, closing balance. |
| `routers/vendors.py` | Vendor CRUD + `GET /api/vendors/{id}/statement?from_date=&to_date=` — AP mirror of customer statement (bills + bill-payments). |
| `routers/reports.py` | Contains the General Ledger endpoint (`/api/reports/ledger`) which returns **Opening Balance** and **Closing Balance** per account when `start`/`end` query params are supplied. Opening = net balance of all JEs before `start`; Closing = `opening + Σdebits − Σcredits` in period (sign follows account-type convention). New endpoints: `/api/reports/product-ledger` (each movement carries its resolved store `location`), `/api/reports/inventory-performance`, `/api/reports/customer-performance`, and `/api/reports/product-coa` (Main→Sub→Item closing-stock valuation tree grouped by product category, with rolled-up subtotals + an Uncategorized bucket; backs the **Tree** view toggle on the Products page). **Hierarchical statements (v2.5):** single-period `/trial-balance` → `{tree, totals}`, `/balance-sheet` → `{assets, liabilities, equity, totals}` (RE-CUR synthetic equity line), `/income-statement` → `{revenue, expenses, totals}` + `net_profit` — nested trees rolled up via `services/account_tree.py`; comparison mode (`compare_end`/`compare_start`) stays flat `{current, comparison}`. |
| `routers/report_builder.py` | Dynamic report builder — `/api/report-builder/sources` (list whitelisted data sources), `/api/report-builder/run` (execute a `ReportConfig`), `/api/report-builder/reports` CRUD (save/load/delete named reports), `/api/report-builder/export` (CSV/XLSX download, formula-injection-safe). All queries are tenant-scoped and column references are resolved exclusively through the whitelist in `services/report_sources/`. |
| `services/report_sources/__init__.py` | Declarative data-source **registry** (the security boundary): 9 whitelisted sources (`invoices`, `bills`, `journal_lines`, `payments_received`, `payments_made`, `products`, `stock_movements`, `customers`, `vendors`), each listing exact SQLAlchemy columns users may query. Unknown field keys → HTTP 400, never a query. |
| `services/report_engine.py` | Pure query builder — `ReportConfig` Pydantic schema + `run_report()`: resolves field keys through the registry, injects `tenant_id` unconditionally, builds a tenant-safe `select()` with filters, group-by, aggregates, and pagination. |
| `services/account_tree.py` | **Hierarchical roll-up engine** — `build_account_tree(accounts, values_by_account_id, field_names, *, prune_zero=True)`: builds the parent→child account tree, parent value = own + Σ descendant leaves, prunes zero subtrees. Backs the hierarchical Trial Balance / Balance Sheet / P&L. Generic over field set (`["debit","credit"]` or `["balance"]`/`["amount"]`). |
| `services/deferred.py` | **Deferred-revenue origination (#47)** — `plan_deferral`, `resolve_deferred_account`, `create_schedules`, `has_any_recognition`, `reverse_schedules`. Called by both `create_invoice` and `update_invoice` so create/edit can't diverge: `product.is_deferred` lines credit Deferred Revenue (2300) + originate a `DeferredRevenueSchedule`; edit blocks-if-recognized else reverses+rebuilds. |
| `services/permissions.py` | `perm_dep(resource_key, level)` factory — returns a FastAPI dependency injected into 35+ routers; resolves the effective right for `(tenant_id, user_id, resource_key)` by merging RBAC role defaults with `UserPermission` sparse overrides; `apply_own_filter(query, model, user)` adds `created_by_id == user.id` filter when `my_data_only=True`; `PERMISSION_RESOURCES` is the 60-resource registry used by the admin matrix. |
| `services/` | Pure-logic modules — `posting.py` is the only GL writer; also `account_tree.py`, `deferred.py`, `depreciation.py`, `pdf.py`, `email.py`, `permissions.py` |
| `scripts/seed_demo.py` | Idempotent rich mock-data seeder (50+ per entity type). Exercises current features: data spans **two fiscal years**, transactions carry **voucher types** (SL/PU/CR/CP/CN/DN), the services tenant demonstrates **deferred-revenue origination with partial recognition**, and each tenant has **multiple users** (owner/accountant/clerk) with varied Audit-Log attribution. |
| `scripts/autoseed_demo.py` | First-run demo loader: skips if any user already exists (brand-new empty DB only); no-ops when `SEED_DEMO=false` |

**Database:** SQLite (`backend/database.db`) in dev; PostgreSQL via `DATABASE_URL` in production. Dev still bootstraps via `SQLModel.metadata.create_all()`, but **Alembic migrations are now the source of truth** for schema changes (`backend/alembic/versions/`, revisions through `0022_promo_rules`). New columns/tables: add to `models.py`, then `uv run alembic revision --autogenerate -m "..."` and `uv run alembic upgrade head`. **SQLite caveat:** Alembic can't `ADD CONSTRAINT` via ALTER — generated migrations adding FKs need the FK line removed and an existence guard added (see migrations 0016/0017 for the pattern). New tables get a `bind.dialect.has_table(...)` guard so they coexist with `create_all()`.

**Seeding:** On startup, `db.py` creates:
- A default `Tenant`, seeds a Chart of Accounts, and optionally creates an admin user from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` env vars
- Five pre-seeded demo tenants (one per business model) with placeholder users for immediate testing
- Delete `backend/database.db` to reset to seeded state

**Script installers run `alembic upgrade head` on every launch** (`install-and-run.*` and `run_packaged.py`) so updating to a newer version migrates the existing database forward in place — new columns/tables are added, existing data preserved.

**Installers auto-rebuild the frontend** when the current `git rev-parse HEAD` differs from the hash recorded in `frontend/.next/.built-commit`. This means any code update (via `update.sh`/`update.bat` or a plain re-run after a `git pull`) will recompile the UI — a stale build can never hide new features. Pass `--rebuild` (sh) / `-Rebuild` (ps1) to force a rebuild regardless.

**Update scripts:** `update.sh` (macOS/Linux), `update.bat` / `update.ps1` (Windows) — `git pull` then re-run `install-and-run.*`. Data directory (`~/.easy-books` / `%USERPROFILE%\.easy-books`) is never touched.

**Demo Tenants:**

| Context | Behaviour |
|---------|-----------|
| Dev / cloud (`dev.sh`) | Auto-created on first run; auto-populated with 50+ records per tenant each time `dev.sh` runs |
| Standalone *script* installers (`install-and-run.*`) | **Auto-load** the 5 fully-populated demo companies on first install (`SEED_DEMO=true` default, ~20–30 s one-time). Set `SEED_DEMO=false` for a clean install with no demo data. Mechanism: after `alembic upgrade head`, the installer runs `scripts.autoseed_demo` (guarded — any user already present → skip; also skips when `SEED_DEMO=false`). Updating an existing install is **migrate-only** — no demo data is added. |
| Desktop (Electron) | **Also auto-loads** the 5 demo companies on first install (`SEED_DEMO=true` default; `run_packaged.py` runs the guarded auto-seed before serving; the Electron shell shows a "Starting up… first-time setup may take ~30 seconds" splash during the one-time seed). Set `SEED_DEMO=false` for a clean desktop install. Updating an existing install is **migrate-only** — no demo data is added. |

Demo data is also loadable/removable at any time via **Settings → Sample / Demo Data** regardless of install type.

All five demo tenants use password `demo1234`:

| Email | Model |
|-------|-------|
| `demo.simple@easy-books.app` | Simple |
| `demo.services@easy-books.app` | Services |
| `demo.trader@easy-books.app` | Trader |
| `demo.manufacturing@easy-books.app` | Manufacturing |
| `demo.telecom@easy-books.app` | Telecom Franchise |

To run the rich mock-data seeder manually:
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
- `block_negative_stock` — when `true`, `consume_stock(block_negative=True)` raises HTTP 400 if a sale would drive `stock_qty` below 0 (default `false`; purchases are never blocked)

**Company Branding:** Users customize their branding via `/dashboard/settings`:
- Company name appears in `Header` + `PrintHeader`
- Business tagline appears below company name in header and all printed documents
- All settings are persisted per-tenant via `/api/settings` PATCH endpoint

**Inventory nav section:** the sidebar exposes a dedicated **Inventory** group containing routes for Products (`/products` — has a **List / Tree** view toggle; Tree shows the Main→Sub→Item closing-stock valuation via `/api/reports/product-coa`), Product Categories (`/products/categories`), Product Ledger (`/products/ledger` — has a Location column and accepts `?product=<id>` to pre-select), and Inventory Performance (`/inventory/performance` — product names link into the ledger).

**Section Hub Pages:** each major sidebar section has a command-centre hub page:
- `/receivable` — AR aging summary + top overdue customers (`AgingBand`)
- `/payable` — AP aging summary + top overdue vendors (`AgingBand`)
- `/inventory` — low-stock alerts + on-hand value (`LowStockBand`)
- `/banking` — live bank-account balances from the GL (`AccountListBand`)
- Generic renderer: `components/hub/HubPage.tsx` driven by `lib/hubConfigs.ts` (`HubConfig` objects with `title`, `bands[]`). Sidebar section headers navigate to the hub via `TITLE_MAP` in `(dashboard)/layout.tsx`.

**Collapsible sidebar (`components/Sidebar.tsx`):**
- 3-state behaviour: **collapsed** (icon strip) / **open** (labels) / **pinned** (always open) stored in `localStorage` key `eb.sidebar.pinned` (`"1"` / `"0"`) and `eb.sidebar.open`.
- Hover over the collapsed strip opens a floating panel with full nav labels; leaving closes it.
- Auto-pins on wide screens (`window.innerWidth >= 1280`).
- Backdrop `div` starts at `top-12` (below the header) to avoid covering it; `z-index` layering: header `z-50`, sidebar `z-40`, backdrop `z-30`.

**3-mode voucher form (`app/(dashboard)/journal/new/page.tsx`):**
- Mode selector at top: **Journal** (JV) / **Payment** (CP cash, BP bank) / **Receipt** (CR cash, BR bank).
- Payment mode: GL picker pre-filters to Cash/Bank accounts for the instrument side; payee field shown.
- Receipt mode: mirror of Payment with reversed Dr/Cr orientation.
- JV prefix auto-sets per mode (CP-YYYY-seq, BP-YYYY-seq, CR-YYYY-seq, BR-YYYY-seq, JV-YYYY-seq).
- Distinct print templates: PV (Payment Voucher) for CP/BP, RV (Receipt Voucher) for CR/BR, standard JV template for JV.

**Print system:**
- **`PrintHeader` (`components/PrintHeader.tsx`):** accepts `orientation?: "portrait" | "landscape"`. When `"landscape"`, a `useEffect` dynamically injects `<style data-print-landscape>@media print { @page { size: A4 landscape; margin: 12mm 15mm; } }</style>` and removes it on unmount. Portrait is the default via `globals.css` (`@page { size: A4 portrait; }`). **Do NOT use CSS classes to control `@page` size** — they have no effect in standard CSS.
- **Orientation rules:** landscape for wide tables (aging, performance reports, product ledger, journal list, invoices/bills list, customer/vendor ledgers); portrait for all other pages (GL, cash/bank book, statements, trial balance, balance sheet, P&L, cash flow, voucher prints, CoA).
- **Date formatting (always use these — never `toLocaleDateString()` or raw ISO strings):**
  - `fmtDate(str: string)` in `src/lib/utils.ts` — converts ISO `"YYYY-MM-DD"` or datetime string → `"dd-mm-yy"`. Splits on `"T"` first to handle datetimes.
  - `fmtDateJs(date: Date)` — converts a JS `Date` object → `"dd-mm-yy"`.
- **Print hygiene classes:**
  - `print:hidden` — hides filter controls, pagination, sort handles, toolbar buttons, action columns, checkbox columns.
  - `@media print { td span, th span { ... } }` in `globals.css` flattens any badge pills to plain text.
- **Column alignment in report tables:** add `whitespace-nowrap` to Date and JV#/Doc# `<td>` cells; do NOT add `max-w-xs` to description cells (let the table manage remaining width naturally).
- **Voucher type badges:** do NOT add inline type badges (`<span>` pills) next to JV numbers in any report table. The JV number prefix already encodes the type (CP = Cash Payment, SL = Sales, BR = Bank Receipt, etc.).
- **Amount formatting:** negative amounts display as `(1,234.56)` via the `fmt()` helper from `useFmt()`; currency code appears once in the column header, not in each cell.

**In-app update check (`desktop/` + `UpdateModal`):**
- `desktop/preload.js` — exposes `window.easybooks.checkForUpdates()`, `onUpdateAvailable(cb)`, `onUpdateDownloaded(cb)`, and `installUpdate()` to the renderer via Electron's context bridge
- `desktop/main.js` `wireAutoUpdater()` — hooks `electron-updater`'s `autoUpdater` events to the IPC channel; checks the GitHub releases feed on launch
- `frontend/src/components/UpdateModal.tsx` — **Settings → Check for Updates** modal; calls the bridge methods on Electron, falls back to showing the `update.bat` / `update.sh` CLI command on script/web installs; data is preserved in both paths

**react-grid-layout (dashboard grid):** Import from `react-grid-layout/legacy` (v2 API, self-typed). Do NOT add `@types/react-grid-layout` — v2 ships its own types. v1 is unusable under React 19 (`findDOMNode` removed). `Layout` = array, `LayoutItem` = single item.

**Dashboard layout store:** Schema v3 `{version:3, layouts:{lg:GridItem[], sm?:GridItem[], xs?:GridItem[]}}` — `lg` is canonical; `sm`/`xs` are sparse overrides created only on first drag/resize at that width. `BP_COLS={lg:4,sm:2,xs:1}` exported from `hooks/useDashboardLayout.ts`. Migration chain in `resolveLayout` handles v1/v2/v3/garbage. `onDragStop`/`onResizeStop` alone call `markCustomized` — `onLayoutChange` updates but never creates overrides.

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
- **Migrations via Alembic** — for schema changes run `uv run alembic revision --autogenerate` then `uv run alembic upgrade head`. `create_all()` still runs in dev for zero-setup boot, so new-table migrations must guard with `bind.dialect.has_table(...)`. SQLite cannot `ADD CONSTRAINT`, so strip auto-generated FK lines on ALTER (app-level tenant checks enforce integrity).
- **WSL2 npm issue** — `dev.sh` resolves the Linux node binary automatically; never invoke Windows `npm` inside WSL2 paths.
- **Date display** — always use `fmtDate()` / `fmtDateJs()` from `src/lib/utils.ts`; never use `toLocaleDateString()` or render raw ISO strings in the UI. Output format is `dd-mm-yy`.
- **Print orientation** — set `orientation="landscape"` on `<PrintHeader>` only for wide multi-column tables; leave it unset (portrait) for everything else. The prop works via dynamic `<style>` injection in `useEffect` — CSS classes cannot control `@page` size.
- **No voucher-type badges in tables** — the JV number prefix (CP / SL / BR / JV etc.) already identifies the type. Adding a separate badge span is redundant and was intentionally removed.

---

## Adding Common Features

**New report:**
1. Add FastAPI endpoint in the appropriate `backend/routers/` file (or `routers/reports.py`) using `select()` with tenant filter.
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

**New printable report page:**
1. Add `<PrintHeader title="..." subtitle={fmtDate(date)} orientation="landscape" />` at the top of the page (set `orientation` only if the table is wider than ~6 columns).
2. Import `fmtDate` from `@/lib/utils` and apply to every date cell — never render raw ISO strings.
3. Wrap all toolbar / filter / pagination UI in `print:hidden` or the `<div className="print:hidden">` pattern.
4. In report tables: add `whitespace-nowrap` to Date and JV#/Doc# `<td>` cells; let Description cells have no `max-w-*` so they absorb remaining width.
5. Do not add amount currency symbols per-cell; put the currency code in the `<th>` header once.
6. Use the `fmt()` helper from `useFmt()` for all amounts — it handles parenthesis-negative and decimal places automatically.

**New section hub page:**
1. Add a `HubConfig` entry in `frontend/src/lib/hubConfigs.ts` with `{ id, title, bands[] }`.
2. Each band is one of `AgingBand`, `LowStockBand`, `AccountListBand` from `components/hub/`.
3. Create `frontend/src/app/(dashboard)/[section]/page.tsx` rendering `<HubPage config={myConfig} />`.
4. Add an entry to `TITLE_MAP` in `frontend/src/app/(dashboard)/layout.tsx` so the breadcrumb and page title resolve.
5. Make the sidebar section header `<Link href="/[section]">` so clicking it navigates to the hub.
