# GEMINI.md — Easy-Books Project Context

This file provides foundational context, architecture, and development guidelines for Easy-Books.

## Project Overview

**Easy-Books** is a multi-tenant double-entry accounting SaaS for SMEs. It enforces bookkeeping invariants at the database level (∑Dr = ∑Cr, no negative amounts, no posting into locked periods), keeps inventory at Weighted-Average cost, and derives every financial report live from the General Ledger.

**Recent (v2.5.0):** the Chart of Accounts is **multi-level** (group parents + leaf accounts; posting to leaves only) and the **financial statements are hierarchical** — Trial Balance / Balance Sheet / P&L roll up over the CoA tree with expand/collapse + drill-down (`services/account_tree.py`). **Deferred-revenue origination** (`services/deferred.py`): `product.is_deferred` lines post to Deferred Revenue (2300) and originate recognition schedules. Posted invoices/bills are editable (reverse-and-repost), and transactions carry voucher types (SL/PU/CR/CP/JV/CN/DN).

Five business models are supported, each with a tailored Chart of Accounts and adaptive UI:

| Model | Key features |
|---|---|
| `simple` | Invoicing + billing + manual JVs |
| `services` | Recurring revenue, service products |
| `trader` | Stock inventory (Weighted-Average FIFO), buy/resell |
| `manufacturing` | BoMs, production orders, custodial GRNs, rate plans |
| `telecom_franchise` | Tracker wallet, RSO chain, SIM activations, FCA targets, mobile money, postpaid, commissions, franchise admin |

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | **FastAPI** + **SQLModel** (SQLAlchemy + Pydantic), Python 3.11+ |
| Database (dev) | **SQLite** (`backend/database.db`) — `create_all()` bootstraps schema |
| Database (prod) | **PostgreSQL** via `DATABASE_URL` env var |
| Auth | **JWT HS256** + bcrypt + HttpOnly cookie + CSRF double-submit |
| Frontend | **Next.js 16** (App Router) + **React 19** + **TypeScript** + Tailwind CSS v4 |
| Icons | `lucide-react` only |
| Charts | `react-chartjs-2` |

**Alembic migrations** are the source of truth (`backend/alembic/versions/`, through 0019). Dev still uses `create_all()` for zero-setup boot, so new-table migrations guard with `bind.dialect.has_table(...)` and SQLite FK ADD-CONSTRAINT lines are stripped (app-level tenant checks enforce integrity). Delete `backend/database.db` to get a fresh seeded DB.

---

## Repository Layout

```
/
├── backend/
│   ├── main.py              # FastAPI bootstrap — middleware + router mounts (~80 lines)
│   ├── models.py            # SQLModel tables (core)
│   ├── models_telecom.py    # 23 tc_* tables for telecom_franchise
│   ├── db.py                # Engine, create_all, seed 5 demo tenants + CoA
│   ├── auth.py              # JWT + bcrypt
│   ├── routers/             # 37+ domain routers (credit_notes, debit_notes, advances, assets, budgets, purchase_orders, analytic_accounts, deferred_revenue, …)
│   │   ├── admin.py         # Demo-data seed/purge (admin+) — backs Settings → Sample/Demo Data
│   │   ├── product_categories.py  # ProductCategory CRUD — 2-level taxonomy (parent → sub-category)
│   │   └── reports.py       # GL opening/closing, product-ledger, inventory-performance, customer-performance
│   ├── services/
│   │   ├── posting.py       # THE only GL writer — enforces all invariants
│   │   ├── inventory.py     # Weighted-Average cost, FIFO layer relief
│   │   ├── tracker_posting.py   # Telecom: tracker/load/RSO/SIM/FCA JVs
│   │   ├── franchise_posting.py # Telecom: mobile-money/postpaid/commission/franchise JVs
│   │   ├── fx.py            # Exchange-rate lookup + inverse fallback
│   │   ├── money.py         # Decimal helpers, ROUND_HALF_EVEN
│   │   ├── csrf.py          # Double-submit CSRF middleware
│   │   └── idempotency.py   # Response-cache middleware
│   ├── scripts/
│   │   └── seed_demo.py     # Idempotent mock-data seeder — 50+ per entity type
│   └── tests/               # pytest suite
├── frontend/
│   └── src/
│       ├── app/login/  signup/       # Public routes
│       ├── app/(dashboard)/          # 29+ auth-gated pages
│       │   ├── telecom/              # Telecom Franchise section (9 sub-pages)
│       │   ├── manufacturing/        # Manufacturing section (5 sub-pages)
│       │   ├── products/categories/  # ProductCategory 2-level taxonomy UI
│       │   ├── products/ledger/      # Product Ledger report
│       │   ├── inventory/performance/ # Inventory Performance report
│       │   ├── team/  profile/       # Multi-user + self-service profile
│       │   └── …                     # Invoices, bills, reports, CoA, banking, …
│       ├── app/accept-invite/        # Public — tokenized invite accept
│       ├── components/
│       │   ├── Sidebar.tsx           # Adaptive sidebar — Inventory nav group: Products, Categories, Product Ledger, Inventory Performance
│       │   ├── UpdateModal.tsx       # Settings → Check for Updates (electron-updater on desktop; CLI command on script/web installs)
│       │   ├── telecom/ActionForm.tsx # Schema-driven JV poster for telecom ops
│       │   ├── DocLink.tsx           # Central drill-down resolver
│       │   └── PrintHeader.tsx       # Branded A4 print output
│       ├── context/SettingsContext.tsx # Company branding + preferences (incl. block_negative_stock over-sell guard), app-wide
│       └── lib/api.ts                # apiFetch — auto-injects Bearer token
├── dev.sh                   # Start both servers; auto-seeds demo data; handles WSL2 node/npm
├── public/                  # Legacy Express/vanilla JS reference (do not touch)
└── server.js                # Legacy Express backend (do not touch)
```

---

## Running Locally

```bash
# One command starts everything (seeds demo data automatically)
./dev.sh

# Backend only
cd backend && .venv/bin/python main.py   # → http://localhost:8000 (Swagger at /docs)

# Frontend only (WSL2: use the Linux node, not Windows npm)
cd frontend && node node_modules/next/dist/bin/next dev   # → http://localhost:3000

# Re-seed demo data
cd backend && PYTHONPATH=. .venv/bin/python -m scripts.seed_demo
```

---

## Demo Tenants

Auto-created on first run; seeded with 50+ records per entity type by `dev.sh`. Standalone script installers (`install-and-run.*`) and the Desktop (Electron) build **auto-load** the 5 demo companies on first install (`SEED_DEMO=true` default; set `SEED_DEMO=false` for a clean install). Demo data is also loadable/removable at any time via **Settings → Sample / Demo Data**.

| Email | Password | Model |
|---|---|---|
| `demo.simple@easy-books.app` | `demo1234` | simple |
| `demo.services@easy-books.app` | `demo1234` | services |
| `demo.trader@easy-books.app` | `demo1234` | trader |
| `demo.manufacturing@easy-books.app` | `demo1234` | manufacturing |
| `demo.telecom@easy-books.app` | `demo1234` | telecom_franchise |

---

## Key Invariants

- **∑Dr = ∑Cr** — enforced in `services/posting.py` before any DB write.
- **Tenant isolation** — every table has `tenant_id`; every query filters by it; cross-tenant access returns 404 (not 403).
- **No raw GL writes** — all journal entries go through `services/posting.py`.
- **Decimal money** — `NUMERIC(18,4)`, `ROUND_HALF_EVEN`, no floats in financial paths.
- **Locked periods** — posting into a closed period is rejected.
- **Atomic numbering** — invoice/bill/JV numbers from `SequenceCounter` with `SELECT FOR UPDATE`.
- **Over-sell guard** — `block_negative_stock` setting (default `false`): when `true`, `consume_stock(block_negative=True)` raises HTTP 400 if a sale would drive `stock_qty` below 0; purchases are never blocked.
- **GL opening/closing balance** — `/api/reports/ledger` with `start`/`end` params returns Opening Balance (net of all JEs before `start`) and Closing Balance (`opening + Σdebits − Σcredits`).
- **Product Categories** — `ProductCategory` is a 2-level taxonomy (parent → sub-category); delete is blocked while sub-categories or products reference the category.

---

## Environment Variables

**Backend** (`backend/.env`):
```
DATABASE_URL=              # PostgreSQL URL (omit for SQLite)
JWT_SECRET_KEY=            # openssl rand -hex 32 (required in production)
FRONTEND_ORIGIN=http://localhost:3000
SEED_ADMIN_EMAIL=
SEED_ADMIN_PASSWORD=
SEED_COMPANY_NAME=
UPLOAD_ROOT=uploads        # Filesystem root for avatars + attachments
```

**Frontend** (`frontend/.env.local`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Further Reading

- [`README.md`](./README.md) — full feature set, getting started, architecture tree.
- [`BLUEPRINT.md`](./BLUEPRINT.md) — every model, endpoint, and business flow.
- [`WORKFLOW.md`](./WORKFLOW.md) — GL Dr/Cr maps, accounting cycles, security model.
- [`CLAUDE.md`](./CLAUDE.md) / [`GEMINI.md`](./GEMINI.md) — AI assistant context.
- [`DEPLOYMENT.md`](./DEPLOYMENT.md) — Vercel deployment guide.
- **In-app update check:** `desktop/preload.js` exposes `window.easybooks.checkForUpdates()` / `onUpdateAvailable` / `installUpdate()` via Electron's context bridge; `desktop/main.js` `wireAutoUpdater()` hooks `electron-updater` events to IPC; `frontend/src/components/UpdateModal.tsx` provides the Settings → Check for Updates UI (falls back to `update.bat`/`update.sh` on script/web installs).
