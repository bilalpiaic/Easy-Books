# Easy-Books

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Easy-Books** is a multi-tenant double-entry bookkeeping SaaS for SMEs. It supports five business models: **Simple**, **Services**, **Trader**, **Manufacturing**, and **Telecom Franchise** — all with IAS/IFRS-aligned accounting, an enforced ∑Dr = ∑Cr invariant, and live reports computed directly from the General Ledger.

Stack: FastAPI + SQLModel (backend) · Next.js 16 + React 19 + Tailwind v4 (frontend) · SQLite for dev/local, PostgreSQL for production.

---

## Feature highlights

**Accounting core**
- Double-entry GL with `services/posting.py` as the single, invariant-enforcing write path
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
- Invoicing and bills with draft editing, bulk actions (mark-sent, void, delete)
- Sales Returns via Credit Notes (restocks inventory, reverses COGS — IAS 2 / ISA 240)
- Purchase Returns via Debit Notes (returns stock at original cost — IAS 2.11)
- Customer & vendor advances; apply against invoices/bills through the allocation flow
- Customer and vendor statements (printable, any date range)
- Per-document notes (customer-facing) and internal memo (staff-only)

**Inventory & stock**
- 2-level product categories; low-stock threshold with dashboard alert and list filter
- Per-product stock card with running qty and value; drill-down from every GL line
- Stock reserved/available tracking on sales; COGS sub-JV posted at shipment

**Banking**
- Bank account balances derived live from the GL
- CSV statement import with SHA-256 de-duplication and auto-match to existing JVs
- Per-period bank reconciliation with line matching and lock-on-close

**Reports (all live from the GL)**
- Trial Balance, General Ledger, Income Statement, Balance Sheet, Cash Flow (indirect)
- Comparative-period P&L and Balance Sheet (IAS 1.38)
- AR/AP Aging (5 buckets), Customer/Vendor sub-ledgers, Stock Card
- Tax Summary (GST output/input), Analytic P&L (cost-centre dimension)
- Budget vs Actual with monthly per-account variance

**Advanced features**
- Fixed Assets register + straight-line/reducing-balance depreciation (IAS 16)
- Purchase Orders (raise → approve → convert-to-bill, 3-way match)
- Deferred revenue recognition schedules (IFRS 15)
- Server-side PDF invoices (WeasyPrint); Stripe payment links; SMTP email notifications

**Settings & customisation**
- Company profile: name, tagline, address, logo — all printed via `PrintHeader`
- Document number formats with `{prefix}`, `{YYYY}`, `{MM}`, `{seq:04d}` tokens and live preview
- Default GL accounts per tenant (AR, AP, Revenue, COGS overrides)
- Onboarding checklist, audit log (timeline / by-user / by-entity, CSV export)

**Multi-tenant SaaS**
- RBAC: `owner | admin | accountant | viewer`; team management with invite links
- Tenant isolation at the data layer — every query filters by `tenant_id`
- JWT + HttpOnly cookie; CSRF double-submit; login throttle; idempotency keys

**Business-model tracks**
- **Manufacturing (V2):** multi-location inventory, Bills of Material, Rate Plans, GRN, Production Order lifecycle (draft→started→completed→delivered→billed) with full GL postings
- **Telecom Franchise (V3):** 56-account franchise CoA, Tracker wallet & load orders, MSR→RSO→Retail chain, SIM inventory, FCA targets, Mobile Money agency, Postpaid billing, Commission reconciliation, 9 telecom reports

---

## Two ways to run

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

A fresh install boots **empty** — no demo data. Sign up to create the first owner account. See [§ Demo / sample data](#demo--sample-data) to load sample companies on demand.

Pass `--rebuild` (sh) / `-Rebuild` (ps1) to force a fresh frontend build after a source update.

#### Electron desktop app

A bundled Electron desktop app (Phase 2) packages the FastAPI backend as a PyInstaller binary and the Next.js standalone server with a bundled Node into a signed Windows `.exe` / macOS `.dmg` installer — no terminal, no internet fetch. See [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md#phase-2--bundled-desktop-installer-build--release) for build and release details.

---

### ② Developer mode

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

`dev.sh` auto-seeds five demo tenants with rich mock data on each run (idempotent).

---

## Demo / sample data

**Standalone installs** boot **clean** — no demo data is loaded automatically. To explore the app with pre-populated books:

1. Log into your owner account and go to **Settings → Sample / Demo Data**.
2. Click **Load demo companies** — this creates five ready-made tenants.
3. Log out and sign in as one of the demo accounts (password `demo1234` for all):

| Email | Business model |
|---|---|
| `demo.simple@easy-books.app` | Simple invoicing |
| `demo.services@easy-books.app` | Services / recurring revenue |
| `demo.trader@easy-books.app` | Inventory / buy-and-resell |
| `demo.manufacturing@easy-books.app` | Manufacturing / value-addition |
| `demo.telecom@easy-books.app` | Telecom Franchise |

Each demo tenant contains 100 invoices, 100 bills, 70 payments received, 70 bill payments, 25 customers, 25 vendors, 3 bank accounts, 6 recurring templates, and 60+ manual journal entries spread across the past 365 days. Remove them any time from the same settings card.

In **developer mode**, `dev.sh` seeds these tenants automatically on every run. To seed manually:

```bash
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
```

---

## Updating & data safety

### Your data is always safe

User data (the SQLite database, uploaded files, and the per-install JWT secret) lives in `~/.easy-books` / `%USERPROFILE%\.easy-books` — **completely outside the app folder**. Updating or reinstalling Easy-Books never touches this directory.

### Database migrations run automatically on launch

Both install paths run `alembic upgrade head` before starting the servers:

- **Script installers** (`install-and-run.sh` / `install-and-run.bat`) — migrate before boot
- **Desktop app** — `backend/run_packaged.py` migrates before uvicorn starts

Your schema is updated in place; existing rows are preserved and new features are available immediately after an update.

### Updating a script install

```bash
# macOS / Linux
./update.sh

# Windows
update.bat          # double-click in Explorer
```

`update.sh` / `update.bat` runs `git pull` then calls the installer to rebuild and relaunch.

### Updating the desktop app

The Electron desktop app uses `electron-updater` and checks for a new release on every launch. When an update is available you will be prompted to restart — the next launch re-runs `alembic upgrade head`.

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
