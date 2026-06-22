# Easy-Books

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Easy-Books** is a multi-tenant double-entry bookkeeping SaaS for SMEs. It supports six business models: **Simple**, **Services**, **Trader**, **Manufacturing**, **Telecom Franchise**, and **PRA e-Invoice (Pakistan)** — all with IAS/IFRS-aligned accounting, an enforced ∑Dr = ∑Cr invariant, and live reports computed directly from the General Ledger.

Stack: FastAPI + SQLModel (backend) · Next.js 16 + React 19 + Tailwind v4 (frontend) · SQLite for dev/local, PostgreSQL for production.

---

## Feature highlights

**Accounting core**
- **Multi-level Chart of Accounts** — group/parent accounts with child leaves (the default CoA every tenant gets is hierarchical); posting is restricted to active leaf accounts, and parent balances roll up automatically
- Double-entry GL with `services/posting.py` as the single, invariant-enforcing write path
- **Voucher series** — typed vouchers (Sales / Purchase / Receipt / Payment / Journal / Credit-Note / Debit-Note) with per-type numbering, plus Cash Book & Bank Book views
- Decimal money throughout (`NUMERIC(18,4)`, banker's rounding) — no floating-point drift
- Weighted-Average inventory costing (IAS 2); optional FIFO per tenant
- Tax codes catalog with per-line GL posting (output vs input VAT/GST)
- Multi-currency documents with exchange-rate catalog and FX revaluation (IAS 21)
- Payment allocations: one payment settles multiple invoices/bills with partial amounts
- Payment terms (Due on Receipt, Net 15/30/60) with auto-calculated due dates
- Period close — posts closing JV (Revenue/Expense → Retained Earnings), locks the period, materialises `AccountBalance` cache; `/reopen` unlocks
- Recurring journal entries (daily/weekly/monthly/quarterly/yearly) with a run-due endpoint
- Overdue auto-flag on invoice/bill fetch; reversal unwinds allocations and COGS sub-JVs

**AR / AP**
- Invoicing and bills with draft editing **and posted-document editing** (reverse-and-repost; blocked once paid; honours the negative-stock guard on edit), bulk actions (mark-sent, void, delete)
- Sales Returns via Credit Notes (restocks inventory, reverses COGS — IAS 2 / ISA 240)
- Purchase Returns via Debit Notes (returns stock at original cost — IAS 2.11)
- Customer & vendor advances; apply against invoices/bills through the allocation flow
- Customer and vendor statements (printable, any date range)
- Per-document notes (customer-facing) and internal memo (staff-only)

**Inventory & stock**
- 2-level product categories (parent → sub-category) seeded per business model; assign on product form, filter in list
- **On hand: N** shown on invoice/bill line items; optional **Block overselling** setting prevents negative stock on sales (`block_negative_stock`, default off — purchases are never blocked)
- Per-product stock card with running qty and value; drill-down from every GL line
- Stock reserved/available tracking on sales; COGS sub-JV posted at shipment
- Dedicated **Inventory** sidebar section: Products, Product Categories, Product Ledger, Inventory Performance

**Banking**
- Bank account balances derived live from the GL
- CSV statement import with SHA-256 de-duplication and auto-match to existing JVs
- Per-period bank reconciliation with line matching and lock-on-close

**Reports (all live from the GL)**
- Trial Balance, General Ledger (with **Opening / Closing Balance** on date-filtered views), Income Statement, Balance Sheet, Cash Flow (indirect)
- **Hierarchical statements** — Trial Balance, Balance Sheet and P&L roll up over the multi-level CoA with parent subtotals, expand/collapse, and click-through drill-down from a leaf line into its ledger and on to the voucher (`services/account_tree.py`)
- Comparative-period P&L and Balance Sheet (IAS 1.38)
- **AR Aging** & **AP Aging** — dedicated pages (`/aging/receivable`, `/aging/payable`) with Current/1–30/31–60/61–90/90+ buckets and drill-down to the customer/vendor ledger
- **Product Ledger** (`/products/ledger`) — stock movements + running qty per product, single-store or consolidated
- **Inventory Performance** (`/inventory/performance`) — on-hand qty, on-hand value, low-stock flag, last movement, units sold + COGS
- **Customer Performance** (`/customer-performance`) — revenue, invoice count, outstanding AR, avg days-to-pay, ranked
- Customer/Vendor sub-ledgers, Stock Card
- Tax Summary (GST output/input), Analytic P&L (cost-centre dimension)
- Budget vs Actual with monthly per-account variance
- **Report Builder** — user-configurable reports (column chooser, click-to-filter, grouping/totals, saved views, CSV/XLSX export)

**Dashboard (v2.5+)**
- Per-user drag-to-arrange, resize, show/hide widgets — layouts saved per-user via `/api/dashboard/layout`
- Responsive 2D grid (react-grid-layout) — 4-col desktop / 2-col tablet / 1-col phone; per-breakpoint layouts saved independently
- **Shortcut tiles** — pin any nav page (invoices, bills, bank accounts, …) as a dashboard tile with live metric badge (count / total)
- **Data widgets** — opt-in Bank Balances, Top Products, Inventory Summary (self-fetching; zero additional backend queries)
- **Cash-flow tie-out** — reconciling row on the Cash Flow statement shows ✓ (balanced) or amber delta per IAS 7

**Navigation & UX (v2.7)**
- **Section Hub Pages** — `/receivable`, `/payable`, `/inventory`, `/banking` each open a command-centre view: aging summary band, low-stock alert band, or live bank-balance list; sidebar section headers navigate there directly
- **Collapsible sidebar** — 3-state behaviour (collapsed / open / pinned); hover expands with tooltip nav; auto-pins on wide screens; state persisted in `localStorage`
- **3-mode voucher form** — New Entry supports Journal, Payment (CP/BP), and Receipt (CR/BR) modes; mode-specific GL pickers pre-filter Cash/Bank accounts; voucher prefix auto-applies per mode (CP-0001 / BP-0001 / CR-0001 etc.)

**UI & Accessibility (v2.7)**
- **Dark Mode + Themes** — 3 display modes (Light / Dark / System follows OS preference) × 5 color themes (Gold / Emerald / Sapphire / Rose / Slate); theme icon in the header cycles modes; color swatches in **Settings → Appearance**; persisted in `localStorage` (`eb.theme`, `eb.color`); anti-flash script in `layout.tsx` prevents FOUC
- **Multi-language support** — English, Urdu (اردو, RTL Nastaliq script), Chinese (中文); globe icon in header opens language dropdown; preference saved in `localStorage` (`eb.lang`) and synced to `/api/settings` (`app_language`); 314 translation keys across 10 namespaces covering all pages, status badges, action buttons, and table headers; RTL layout auto-applied for Urdu; `react-i18next` + `i18next` client-side only
- **Mobile responsiveness** — sidebar width trimmed to 196 px; page titles, stats grids, aging grids, and form grids all apply responsive breakpoints so the UI stacks cleanly on phones; button toolbars wrap on narrow screens; line-item tables scroll horizontally; 61 files updated

**Print system (v2.7)**
- **Dot-matrix format** — all print output is black-and-white, no background fills; `@media print` strips UI chrome (buttons, filters, pagination, sort handles, checkbox columns, action columns)
- **Date format** — `dd-mm-yy` used everywhere (e.g. `20-06-26`); `fmtDate()` / `fmtDateJs()` helpers in `utils.ts`
- **Portrait / landscape auto-selection** — PrintHeader injects the correct `@page { size: A4 … }` rule via `useEffect`; landscape for wide tables (aging, performance, product ledger, journal list), portrait for everything else
- **Currency prefix** — amount column headers show the currency code once; individual cells contain bare numbers
- **Negative amounts** — displayed as `(1,234.56)` throughout; debit/credit columns use `—` for the zero side
- **Column alignment** — Date and JV# cells are `whitespace-nowrap`; Description absorbs remaining width via natural table flow

**Advanced features**
- Fixed Assets register + straight-line/reducing-balance depreciation (IAS 16)
- Purchase Orders (raise → approve → convert-to-bill, 3-way match)
- Deferred revenue recognition (IFRS 15) — flag a product `is_deferred` and its invoice lines post to Deferred Revenue (2300) and originate a recognition schedule; the recognition run releases revenue over the term, and editing a posted deferred invoice rebuilds the schedule (or is blocked once recognition has begun)
- Server-side PDF invoices (WeasyPrint); Stripe payment links; SMTP email notifications

**Settings & customisation**
- Company profile: name, tagline, address, logo — all printed via `PrintHeader`
- Document number formats with `{prefix}`, `{YYYY}`, `{MM}`, `{seq:04d}` tokens and live preview
- Default GL accounts per tenant (AR, AP, Revenue, COGS overrides)
- **Check for Updates** — compares running version to the latest GitHub release; on the desktop app downloads + installs via `electron-updater` (Restart to apply); on script installs shows the `update.bat`/`update.sh` command; data preserved in both paths. The `VersionBadge` in Settings shows the live running version — fetches `/api/version` in dev mode, reads `NEXT_PUBLIC_APP_VERSION` in production builds (injected by the installer at build time)
- Onboarding checklist, audit log (timeline / by-user / by-entity, CSV export)

**Sales operations**
- **Sales commissions** — define rate/target plans per staff member; compute monthly commissions; approve and post (`Dr Commission Expense / Cr Commissions Payable`) in one click
- **Promotional discounts** — create promo rules (product, min qty, discount %); "Apply Promos" on the invoice form auto-fills the Disc% column; line amounts recalculate instantly
- **Granular access control** — 60-resource permission matrix beyond the 4 RBAC roles; per-user "my data only" mode; module-level toggle in Settings

**HRM — Payroll & Attendance**
- **Employee master** — department/designation/join date/CNIC/bank details; soft-delete; auto-generated codes (EMP-0001)
- **Salary components catalog** — earnings/deductions/statutory types; GL account linkage per component; per-employee fixed or %-of-basic amounts
- **Payroll runs** — draft → approved → posted flow; auto-computes gross/deductions/net per employee from salary structures; GL posting (Dr Salary Expense / Cr Salaries Payable + Cr Tax/EOBI Payable); PR-YYYY-seq voucher; void with reversing JV; printable payslips
- **Attendance register** — manual time-in/out entry per employee per day; hours auto-computed; status codes (Present/Absent/Half Day/Leave/Holiday/Off); monthly grid view (employees × days); bulk entry grid; biometric import endpoint (matches by employee code, stores raw device payload); CSV upload as manual fallback; ZKTeco/FingerTec device integration planned

**Multi-tenant SaaS**
- RBAC: `owner | admin | accountant | viewer`; team management with invite links
- Tenant isolation at the data layer — every query filters by `tenant_id`
- JWT + HttpOnly cookie; CSRF double-submit; login throttle; idempotency keys

**Business-model tracks**
- **Manufacturing (V2):** multi-location inventory, Bills of Material, Rate Plans, GRN, Production Order lifecycle (draft→started→completed→delivered→billed) with full GL postings
- **Telecom Franchise (V3):** 56-account franchise CoA, Tracker wallet & load orders, MSR→RSO→Retail chain, SIM inventory, FCA targets, Mobile Money agency, Postpaid billing, Commission reconciliation, 9 telecom reports
- **PRA e-Invoice (Pakistan):** real-time invoice submission to Punjab Revenue Authority (PRA eIMS); FIN (Fiscal Invoice Number) returned and printed on invoices; `pra_status` badge (pending/submitted/failed) with retry; Payment Mode field; customer NTN/CNIC fields; product PCT codes; Settings card with Test Connection; non-blocking `BackgroundTasks` submission so invoice save is never delayed

---

## Three ways to run

### ① One-click standalone (recommended for end users)

No Python, Node, or terminal knowledge required. The scripts auto-install everything they need (first run fetches uv/Python and a local portable Node; later runs start in seconds).

**Windows** — double-click `install-and-run.bat` in Explorer.

**macOS / Linux:**
```bash
chmod +x install-and-run.sh
./install-and-run.sh
```

What happens automatically: installs **uv** (which provisions Python 3.12), downloads a portable Node into `./.node` if none is found, installs backend deps, builds the frontend, runs `alembic upgrade head`, and opens **http://127.0.0.1:3000**.

Your data lives **outside** the app folder:

| Platform | Location |
|---|---|
| macOS / Linux | `~/.easy-books` (override: `EB_DATA_DIR`) |
| Windows | `%USERPROFILE%\.easy-books` (override: `%EB_DATA_DIR%`) |

On first install the 6 demo companies are loaded automatically (takes ~20–30 s). Log in immediately with `demo1234` — no signup needed. Set `SEED_DEMO=false` before running the installer for a clean start. See [§ Demo / sample data](#demo--sample-data) for details.

Pass `--rebuild` (sh) / `-Rebuild` (ps1) to force a fresh frontend build after a source update.

#### Electron desktop app

A bundled Electron desktop app (Phase 2) packages the FastAPI backend as a PyInstaller binary and the Next.js standalone server with a bundled Node into a signed Windows `.exe` / macOS `.dmg` installer — no terminal, no internet fetch. Releases are published automatically to GitHub Releases by the CI pipeline (`.github/workflows/release.yml`) when a `v*` tag is pushed. See [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md#phase-2--bundled-desktop-installer-build--release) for build and release details.

---

### ② Docker — team / office network

Share one Easy-Books instance across your whole office. Any machine on the network opens a browser — no client install needed.

**Prerequisites:** [Docker Desktop](https://docs.docker.com/get-docker/) (or Docker Engine + Compose plugin on Linux).

```bash
git clone https://github.com/bilalpiaic/Easy-Books.git
cd Easy-Books
cp .env.example .env
# Edit .env — set APP_URL=http://YOUR_SERVER_IP
docker compose up -d --build
```

Open `http://YOUR_SERVER_IP` from any machine on the LAN. First build takes ~3–5 min; subsequent starts are instant. Data persists in the `eb_data` Docker volume — safe across `git pull` updates.

To update:
```bash
git pull && docker compose up -d --build
```

See [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md#docker-compose--officeteam-server) for full setup, HTTPS, PostgreSQL, and backup instructions.

---

### ③ Developer mode

```bash
git clone https://github.com/bilalpiaic/Easy-Books.git
cd Easy-Books

# One-shot: starts backend + frontend + seeds demo data
./dev.sh
```

Backend: http://localhost:8000 (Swagger UI at `/docs`) — Frontend: http://localhost:3000

Or run each service manually:

```bash
# Backend
cd backend
uv sync
python main.py

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

`dev.sh` auto-seeds six demo tenants with rich mock data on each run (idempotent).

---

## Demo / sample data

**Standalone script installs** (`install-and-run.bat` / `.sh`) **auto-load the 6 demo companies on first install** — sign in immediately with password `demo1234`, no signup required:

| Email | Business model |
|---|---|
| `demo.simple@easy-books.app` | Simple invoicing |
| `demo.services@easy-books.app` | Services / recurring revenue |
| `demo.trader@easy-books.app` | Inventory / buy-and-resell |
| `demo.manufacturing@easy-books.app` | Manufacturing / value-addition |
| `demo.telecom@easy-books.app` | Telecom Franchise |
| `demo.pra@easy-books.app` | PRA e-Invoice — Pakistani retail (PKR, NTN/CNIC, PCT codes, FINs) |

The first install takes an extra ~20–30 seconds while the seeder runs; subsequent starts are fast (the seeder is guarded — skips if any user already exists, so updating an existing install is migrate-only and no demo data is added). To opt out and start with a clean slate, set `SEED_DEMO=false` before running the installer.

The **desktop (Electron) app** also auto-loads the 6 demo companies on first install (`SEED_DEMO=true` default; a startup splash is shown during the one-time seed). Set `SEED_DEMO=false` for a clean desktop install.

The **Settings → Sample / Demo Data** card loads or removes the demo companies on demand at any time.

Each demo tenant contains 100 invoices, 100 bills, 70 payments received, 70 bill payments, 25 customers, 25 vendors, 3 bank accounts, 6 recurring templates, and 60+ manual journal entries spread across **two fiscal years** (so comparative reports have a prior period). Transactions carry their correct voucher types, the services tenant demonstrates **deferred-revenue origination with partial recognition**, and each tenant has **multiple users** (owner / accountant / clerk) so the Audit Log shows realistic attribution.

In **developer mode**, `dev.sh` seeds these tenants automatically on every run. To seed manually:

```bash
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
```

---

## Updating & data safety

### Your data is always safe

User data (the SQLite database, uploaded files, and the per-install JWT secret) lives in `~/.easy-books` / `%USERPROFILE%\.easy-books` — **completely outside the app folder**. Updating or reinstalling Easy-Books never touches this directory.

### Database migrations run automatically on launch

All three install paths run `alembic upgrade head` before starting the servers:

- **Script installers** (`install-and-run.sh` / `install-and-run.bat`) — migrate before boot
- **Desktop app** — `backend/run_packaged.py` migrates before uvicorn starts
- **Docker** — `backend/docker-entrypoint.sh` migrates before uvicorn starts

Your schema is updated in place; existing rows are preserved and new features are available immediately after an update. The auto-seed guard (`scripts/autoseed_demo.py`) skips if any user is already present, so **updating an existing install never injects demo data** — only a brand-new empty database triggers the one-time demo load.

### Updating a Docker install

```bash
git pull && docker compose up -d --build
```

### Updating a script install

```bash
# macOS / Linux
./update.sh

# Windows
update.bat          # double-click in Explorer
```

`update.sh` / `update.bat` runs `git pull` then calls the installer to rebuild and relaunch. The installer also **auto-rebuilds the frontend whenever the code has changed** since the last build (tracked via `frontend/.next/.built-commit`), so a plain re-run after any `git pull` always serves the latest UI — no stale builds.

### Updating the desktop app

The Electron desktop app checks for updates on every launch via `electron-updater`. When a newer GitHub Release with a `latest.yml` manifest is available you will see an in-app prompt. Click **Download** to fetch the installer in the background, then **Restart** to apply it. The next launch re-runs `alembic upgrade head` automatically — data is preserved. You can also trigger a manual check at any time via **Settings → Check for Updates**.

### Back up before a major update

Go to **Settings → Backup & Restore** and download a zip (database + uploads) before any significant update.

See [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md) for full details.

---

## Tech stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js 16 / React 19 / TypeScript / Tailwind CSS v4 |
| Backend | FastAPI / Python 3.11+ / SQLModel / Alembic |
| Database | SQLite (dev / local) · PostgreSQL via `DATABASE_URL` (production) |
| Auth | JWT (HS256) + bcrypt · HttpOnly cookie · CSRF double-submit |
| PDF / Email | WeasyPrint (server-side PDF) · SMTP |
| CI/CD | GitHub Actions (`.github/workflows/release.yml`) — validates 3 version files (frontend/package.json, desktop/package.json, backend/pyproject.toml), builds Windows `.exe` + macOS `.dmg` (optional), publishes to GitHub Releases |

---

## Development

### Commands

```bash
# Backend
cd backend
uv sync                                        # install deps
python main.py                                 # dev server → http://localhost:8000
PYTHONPATH=. uv run pytest                     # run all tests
PYTHONPATH=. uv run pytest -v                  # verbose
PYTHONPATH=. uv run pytest tests/test_auth.py  # single file
PYTHONPATH=. uv run pytest -k test_name        # single test by name

# Frontend
cd frontend
npm install
npm run dev    # → http://localhost:3000
npm run build
npm run lint
```

Swagger UI is available at **http://localhost:8000/docs** during development.

### Schema changes

Easy-Books uses **Alembic** as the source of truth for schema changes (migrations through revision 0019+). For new columns or tables:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

`SQLModel.metadata.create_all()` still runs on startup for zero-setup dev boot — new-table migrations must guard with `bind.dialect.has_table(...)`. SQLite cannot `ADD CONSTRAINT` via `ALTER TABLE`, so strip auto-generated FK lines from migrations (see revisions 0016/0017 for the pattern).

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | `postgresql://…` in production; omit for SQLite | `backend/database.db` |
| `JWT_SECRET_KEY` | HMAC secret — **required in production** | Insecure dev default |
| `APP_ENV` | `development` or `production` | `development` |
| `FRONTEND_ORIGIN` | Comma-separated CORS allow-list | `http://localhost:3000` |
| `UPLOAD_ROOT` | Root dir for avatars and attachments | `uploads` |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | Create an admin user on first boot | — |
| `SEED_COMPANY_NAME` | Default company name for the seeded tenant | `My Company` |

Frontend: set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`.

---

## Documentation index

| Document | Contents |
|---|---|
| [`USER_GUIDE.md`](./USER_GUIDE.md) | End-user walkthrough for every feature |
| [`WORKFLOW.md`](./WORKFLOW.md) | Accounting workflows, GL Dr/Cr maps, report-linking matrix, API catalog |
| [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md) | One-click installer, Electron desktop app, data safety, update paths |
| [`DEPLOYMENT.md`](./DEPLOYMENT.md) | Cloud / Vercel deployment for backend + frontend |
| [`BLUEPRINT.md`](./BLUEPRINT.md) | Complete project blueprint: every model, endpoint, flow, and decision |
| [`CLAUDE.md`](./CLAUDE.md) | AI-assistant instructions and architecture reference |
| [`backend/README.md`](./backend/README.md) | Backend quick-start, commands, structure, API conventions |
| [`frontend/README.md`](./frontend/README.md) | Frontend quick-start, scripts, environment variables |

The in-app **User Guide** (`/guide`) and **Workflow** (`/workflow`) pages provide interactive, tenant-aware walkthroughs directly in the browser.

---

## Legacy reference

The repo root also contains a legacy Express + vanilla-JS implementation (`server.js` + `public/`). This is a reference-only snapshot and is not actively developed. All feature work happens in the modern `backend/` (FastAPI) + `frontend/` (Next.js) stack.

---

## License

MIT.
