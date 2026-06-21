# Easy-Books — Complete Project Blueprint

> A single document covering **every major and minor detail** of the system:
> architecture, data model, every API endpoint, every business flow, every
> security mechanism, every cross-cutting concern. Read this if you want the
> full picture of how the system works end-to-end.
>
> Companion docs:
> - [`README.md`](./README.md) — quick tour + getting started.
> - [`WORKFLOW.md`](./WORKFLOW.md) — narrative walkthroughs of each cycle.
> - In-app `/guide` and `/workflow` — interactive equivalents.
>
> **Last updated:** 2026-06-21 · **Branch:** `main`

---

## TABLE OF CONTENTS

1. [Vision & Scope](#1-vision--scope)
2. [Tech Stack](#2-tech-stack)
3. [Repository Layout](#3-repository-layout)
4. [Architecture Overview](#4-architecture-overview)
5. [Data Model — Every Table](#5-data-model--every-table)
6. [Business Models & Adaptive UX](#6-business-models--adaptive-ux)
7. [Chart of Accounts Templates](#7-chart-of-accounts-templates)
8. [API Catalogue — Every Endpoint](#8-api-catalogue--every-endpoint)
9. [Accounting Cycles & GL Postings](#9-accounting-cycles--gl-postings)
10. [Manufacturing Track (V2)](#10-manufacturing-track-v2)
10A. [Telecom Franchise Track (V3)](#10a-telecom-franchise-track-v3)
11. [Reports](#11-reports)
12. [Security Model](#12-security-model)
13. [Cross-Cutting Concerns](#13-cross-cutting-concerns)
14. [Frontend Architecture](#14-frontend-architecture)
15. [Migrations](#15-migrations)
16. [Engineering Invariants](#16-engineering-invariants)
17. [Testing](#17-testing)
18. [Deployment](#18-deployment)
19. [Open Items & Roadmap](#19-open-items--roadmap)

---

## 1. VISION & SCOPE

**Easy-Books** is a multi-tenant, double-entry accounting SaaS for SMEs. It is built for businesses that need rigorous bookkeeping (locked periods, audited reversals, balanced JVs) without a steep learning curve. Each customer (a *tenant*) gets:

- A self-contained ledger (Chart of Accounts, journal, financial statements).
- Operational documents (invoices, bills, payments, manual JVs) that auto-post to the GL.
- Multi-currency support with FX-rate-snapshot semantics.
- A per-period close that materialises balances and locks the books.
- An optional **manufacturing track** for tenants that do value-addition on customer-supplied goods (textiles, contract manufacturing, processing).

The system is designed so every financial number on every screen is **derived live from the GL** — there are no batch jobs to compute "balances" out-of-band that could drift from the journal.

### Design tenets

| Tenet | What it means in code |
|---|---|
| **One writer for the GL** | Every JV goes through `services/posting.py`. Invariants (Σdr=Σcr, single-sided rows, period-lock, tenant-ownership) live in one place. |
| **Decimal money** | All amounts are `Decimal` stored as `NUMERIC(18,4)`, banker's rounding. Float arithmetic is forbidden in financial paths. |
| **Multi-tenant by default** | Every table has `tenant_id`. Every query filters by it. Cross-tenant access returns 404 (not 403 — no enumeration). |
| **Reversibility** | No physical deletes for journal-affecting rows. Reversal posts a mirror JV and unwinds derived state (inventory layers, allocations). |
| **Versioning over editing** | BoMs and RatePlans bump a version on change rather than in-place mutation, so historical documents stay reproducible. |
| **Adaptive surface** | The UI subtracts itself by business_model — a "simple" tenant doesn't see manufacturing chrome, a "trader" doesn't see services chrome. |
| **Guidance everywhere** | Every page that could confuse a first-time user ships with a `HelpCallout` (the *why*) and `EmptyStateGuide` (the *next step*). |

---

## 2. TECH STACK

| Layer | Choice | Why |
|---|---|---|
| Backend framework | **FastAPI** | Async-friendly, OpenAPI for free, dependency-injection ergonomics |
| ORM | **SQLModel** (Pydantic + SQLAlchemy) | Same model is the wire schema and the table |
| DB (dev) | **SQLite** | Zero-setup local dev; honoured by `SCHEMA_BOOTSTRAP=create_all` |
| DB (prod) | **PostgreSQL** | Row-level locks (`SELECT FOR UPDATE`) for atomic numbering and avg-cost updates |
| Migrations | **None (create_all)** | `SQLModel.metadata.create_all()` on startup; manual `ALTER TABLE` for existing DBs |
| Auth | **JWT (HS256) + bcrypt + HttpOnly cookie + CSRF** | Same backend supports SDK Bearer clients and browser cookie clients |
| Frontend | **Next.js 16 (App Router)** + React 19 | Server components for the shell, client components for forms |
| Styling | **Tailwind v4** (+ `tailwind-merge`) | Per-token theming; brand palette `#f6f3ee / #b8943f / #1a1814` |
| Charts | **react-chartjs-2** | Dashboard KPIs |
| Icons | **lucide-react** | Consistent line-icon set across UI |
| Python deps | **uv** | Fast resolver; `uv run pytest` is the test runner |
| JS deps | **npm** | Lockfile at `frontend/package-lock.json` |

---

## 3. REPOSITORY LAYOUT

```
Easy-Books/
├── README.md, BLUEPRINT.md, WORKFLOW.md, DEPLOYMENT.md, CLAUDE.md
├── server.js, public/        ← legacy reference implementation (Express)
├── dev.sh                    ← one-shot launcher (backend :8000 + frontend :3000)
├── backend/
│   ├── main.py               ← FastAPI bootstrap, middleware, router wiring, /api/v1 aliases
│   ├── models.py             ← 32 SQLModel tables
│   ├── auth.py               ← JWT encode/decode + bcrypt password hash + secret hardening
│   ├── db.py                 ← engine, seed_data, per-model CoA templates
│   ├── scripts/seed_demo.py     ← idempotent mock-data seeder (50+ per entity type)
│   ├── routers/
│   │   ├── common.py            SessionDep, CurrentUserDep, WriteUserDep, RBAC, next_number, log_audit
│   │   ├── auth.py              signup, login (+throttle), logout, /me, profile (name/phone/password/avatar), accept-invite
│   │   ├── users.py             (V3.6) team management (admin+): create/invite/role/activate/reset-password
│   │   ├── settings.py          tenant settings + /business-model + /modules
│   │   ├── accounts.py          CoA CRUD
│   │   ├── customers.py · vendors.py · products.py
│   │   ├── invoices.py · bills.py
│   │   ├── payments.py          PaymentReceived + BillPayment + allocations
│   │   ├── transactions.py      manual JV + reverse + read
│   │   ├── periods.py           lock/close/reopen
│   │   ├── tax_codes.py · exchange_rates.py · recurring.py
│   │   ├── bank_accounts.py · bank_imports.py · reconciliations.py
│   │   ├── stock_locations.py   (V2.2) StockLocation + movements + custody
│   │   ├── bom.py               (V2.3) BomHeader + BomLine
│   │   ├── rate_plans.py        (V2.3) RatePlan + CustomerRatePlan
│   │   ├── grn.py               (V2.4) GoodsReceiptNote (custodial intake)
│   │   ├── production_orders.py (V2.4) PO state machine
│   │   ├── manufacturing_reports.py  (V2.5) dashboard + aging + custody
│   │   ├── reports.py · aging.py · audit.py · imports.py
│   ├── services/
│   │   ├── posting.py           THE central GL writer
│   │   ├── inventory.py         WAvg cost + record_purchase/consume_stock/reverse
│   │   ├── fx.py                ExchangeRate lookup with inverse fallback
│   │   ├── money.py             D() · money() · ROUND_HALF_EVEN
│   │   ├── csrf.py              double-submit-cookie middleware
│   │   └── idempotency.py       response-cache middleware
│   └── tests/                   122 tests
└── frontend/
    └── src/
        ├── app/
        │   ├── login/ · signup/             2-step wizard with business-model picker
        │   └── (dashboard)/                 auth-gated, layout wraps all
        │       ├── dashboard/               KPI cards + 12-month charts
        │       ├── entry/                   manual JV with live Dr/Cr tally
        │       ├── journal/ · ledger/       read-only GL views
        │       ├── trial-balance/ · pl/ · balance/ · cashflow/ · tax/
        │       ├── invoices/ · bills/ · payments-received/ · bill-payments/
        │       ├── customers/ · vendors/ · products/ · coa/
        │       ├── bank-accounts/ · reconciliations/
        │       ├── manufacturing/           V2: sidebar-gated section
        │       │   ├── page.tsx             Production Floor dashboard
        │       │   ├── boms/                Bills of Material
        │       │   ├── rate-plans/          Rate plans
        │       │   ├── grn/                 Goods receipts
        │       │   └── production-orders/   PO list + one-click advance
        │       ├── settings/ · workflow/ · guide/
        ├── components/
        │   ├── Sidebar.tsx                  adaptive; hides Mfg unless business_model='manufacturing'
        │   ├── BusinessModelPicker.tsx      signup wizard step 1
        │   ├── guidance/                    HelpCallout, FieldHint, EmptyStateGuide
        │   └── …                            Header, modals, charts, CsvImportButton, …
        ├── context/SettingsContext.tsx      currency + company-name from /api/settings
        └── lib/
            ├── api.ts                       apiFetch (auto Authorization header)
            ├── auth.ts                      token storage, isAuthenticated
            └── utils.ts                     cn(), formatters
```

---

## 4. ARCHITECTURE OVERVIEW

### 4.1 Request lifecycle (server-side)

```
USER ACTION (browser POST / SDK call)
    │
    ▼
┌──────────────────────────────────────────────┐
│ FastAPI middleware stack                     │
│  1. CsrfMiddleware                           │
│  2. IdempotencyMiddleware                    │
│  3. CORSMiddleware                           │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│ Dependency resolution                        │
│  • SessionDep                                │
│  • CurrentUserDep / WriteUserDep / AdminDep  │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│ Endpoint handler                             │
│  1. Pydantic validates body                  │
│  2. tenant_id filter on every SELECT         │
│  3. Business logic                           │
│  4. services.posting.post_transaction(...)   │
│  5. log_audit(...)                           │
│  6. session.commit()                         │
└──────────────────────────────────────────────┘
    │
    ▼ JSON response (cached if Idempotency-Key was supplied)
```

### 4.2 Request lifecycle (client-side)

```
User submits form
    │
    ▼ apiFetch(path, options)
       • Reads localStorage 'access_token'
       • Injects Authorization: Bearer <token>
       • Hits NEXT_PUBLIC_API_URL (default http://localhost:8000)
    │
    ▼ Response
       • Parses JSON
       • Throws Error(detail) on non-2xx so .catch() works in callers
```

---

## 5. DATA MODEL — EVERY TABLE

All tables include `id PK`, `tenant_id` (except cross-tenant tables like `User.email` unique). Money columns are `NUMERIC(18,4)` non-null. Timestamps default to `datetime.utcnow`.

### 5.1 Core

| Table | Notes |
|---|---|
| `tenant` | `name`, `base_currency`, **`business_model`** (`simple/services/trader/manufacturing/telecom_franchise` CHECK), `enabled_modules` (JSON array string), `created_at` |
| `user` | `email` (unique), `hashed_password` (bcrypt), `full_name`, `phone`, `avatar_url`, `is_active`, `must_change_password`, `role` (`owner/admin/accountant/viewer` CHECK), `tenant_id`, **`created_by_id?`** (set on create), `created_at`, `last_login_at` |
| `userinvite` | Pending tenant invite — `email`, `role` (CHECK), `token` (unique), `invited_by_id`, `expires_at`, `accepted_at`. Consumed by `POST /api/auth/accept-invite` |
| `userpermission` | Granular access override — `(tenant_id, user_id, resource_key)` unique; `access_level` (`none/view/edit`); `my_data_only` bool. Sparse — only rows with non-default access exist; missing row = role default. Module-gated by `settings.user_rights_enabled` |
| `settings` | KV per tenant — `company_name`, fiscal year, number prefixes, **`user_rights_enabled`** (module toggle for granular permissions) |
| `account` | `code`, `name`, `type` (`Asset/Liability/Equity/Revenue/Expense` CHECK), **`parent_id` + `is_group`** (V2.4/V2.5 — multi-level hierarchy; the default CoA is now hierarchical and posting is restricted to active **leaf** accounts, parent balances roll up), `is_active`, **`is_memo`** (V2.1 — excludes from formal A=L+E totals) |
| `deferredrevenueschedule` | IFRS 15 — `invoice_id`, `total_amount`, `recognised_amount`, `start_date`, `end_date`, `frequency`, `next_recognition_date`, `status`, `deferred_revenue_account_id`, `revenue_account_id`. Originated by `create_invoice` for `is_deferred` product lines; released by the recognition run |
| `accountingperiod` | `period_start`, `period_end`, `is_locked`, `name` |
| `transaction` | `jv_number` (unique per tenant), `date`, `description`, `is_reversed`, `reversed_by_id`, `created_at` |
| `journalentry` | `transaction_id` (CASCADE), `account_id`, `debit`, `credit`. DB CHECK: `debit≥0 ∧ credit≥0 ∧ ¬(debit>0 ∧ credit>0) ∧ (debit>0 ∨ credit>0)` |
| `sequencecounter` | `(tenant_id, name)` unique; `next_value`. Used with `SELECT FOR UPDATE` for atomic invoice/bill/grn/po numbers |
| `auditlog` | One row per mutation: `user_id`, `action`, `entity_type`, `entity_id`, `detail` (JSON) |
| `commissionplan` | Sales commission plan per user — `user_id`, `rate` (%), `sales_target?`, `recovery_target?`, `target_bonus?`, `effective_from`, `effective_to?`, `active`. One active plan per user per period |
| `commissionledger` | Computed commission entry — `plan_id`, `period` (YYYY-MM), `invoiced_amount`, `commission_amount`, `bonus_amount?`, `status` (`pending/approved/posted`), `transaction_id?` (set on post) |
| `promorule` | Price discount rule — `name`, `product_id?`, `min_qty`, `discount_pct`, `valid_from?`, `valid_to?`, `is_active`. Checked via `POST /api/promo-rules/check` at invoice entry |

### 5.2 AR / AP

| Table | Notes |
|---|---|
| `customer` | name, contact, `opening_balance`, `is_active` |
| `vendor` | mirror of customer |
| `invoice` | `number` (per-tenant atomic), `customer_id`, dates, `subtotal/gst_rate/gst_amount/total` (document currency), `currency`, `exchange_rate` (snapshot at issue), `status` (`draft/posted/partial/paid`), `ar_account_id`, `revenue_account_id`, `transaction_id` |
| `invoiceline` | `invoice_id` (CASCADE), `product_id?`, `description`, `qty`, `unit?`, `rate`, **`discount_pct`** (0 when no promo), **`promo_rule_id?`** (FK → `promorule`), `amount` = `qty × rate × (1 − discount_pct/100)` |
| `bill` | mirror of invoice on the payable side; ap/expense account FKs |
| `billline` | (same shape as invoiceline) |
| `paymentreceived` | `invoice_id?`, `payment_date`, `amount`, `method`, `cash_account_id`, `transaction_id` |
| `billpayment` | mirror |
| `paymentallocation` | `payment_id?` ⊕ `billpayment_id?` linked to `invoice_id?` ⊕ `bill_id?`; `amount > 0`; used to derive partial/paid status |

### 5.3 Inventory (V2.2 + base)

| Table | Notes |
|---|---|
| `product` | `code?`, `name`, `unit`, `product_type` (`stock` ⊕ `service`), `default_rate`, `stock_qty`, `avg_cost` (WAvg), `reorder_level`, **`category_id?`** (FK → `productcategory`), default GL FKs |
| `productcategory` | 2-level taxonomy: `name`, `parent_id?` (self-FK; `null` = top-level category). Delete blocked while subcategories or assigned products exist. Tenant-scoped. |
| `stocklocation` (V2.2) | `code`, `name`, `type` (`own/customer_custodial/wip` CHECK), `is_active`. Unique `(tenant_id, code)` |
| `inventorylayer` | One row per receipt; `product_id`, **`location_id?`** (V2.2), **`owner_customer_id?`** (V2.2 — set for custodial layers), **`lot_no?`**, `qty_received`, `qty_remaining`, `unit_cost`, `source_doc` |
| `stockmovement` (V2.2) | Event log; `direction` ∈ {`RECEIPT, CUSTODIAL_RECEIPT, ISSUE, CUSTODIAL_ISSUE, COMPLETION, CUSTODIAL_COMPLETION, DELIVERY, SHIPMENT, ADJUSTMENT`} (CHECK), qty>0 (CHECK), from/to location, lot, owner, unit_cost, total_cost, source_doc_type/id, transaction_id, `posted_to_gl` (False for custodial-only movements), notes |

**Over-sell guard:** tenant setting `block_negative_stock` (default `false`). When `true`, `consume_stock(block_negative=True)` raises HTTP 400 if a sale would drive `stock_qty < 0`. Purchases (`record_purchase`) are never blocked.

### 5.4 Manufacturing (V2.3 + V2.4)

| Table | Notes |
|---|---|
| `bomheader` (V2.3) | `output_product_id`, `output_qty`, `version`, `is_active`, `description`, `notes`. Unique `(tenant_id, output_product_id, version)` |
| `bomline` (V2.3) | `bom_id` (CASCADE), `component_product_id`, `qty_per_output > 0` (CHECK), `source` ∈ {`own_stock, customer_supplied`} (CHECK), `default_location_id?`, `is_optional`, `notes` |
| `rateplan` (V2.3) | `code`, `name`, `output_product_id?`, `per_unit_rate ≥ 0`, `includes_materials_at_cost`, `overhead_pct ≥ 0`, `margin_pct ≥ 0`, `version`, `is_active`, `valid_from/to`. Unique `(tenant_id, code, version)` |
| `customerrateplan` (V2.3) | `customer_id` ↔ `rate_plan_id`, `is_active`, `assigned_at`. Unique `(tenant_id, customer_id, rate_plan_id)` |
| `goodsreceiptnote` (V2.4) | `number` (per-tenant atomic), `customer_id`, `received_date`, `location_id` (must be `customer_custodial`), `declared_value`, `transaction_id?` (set only when memo JE posted) |
| `grnline` (V2.4) | `grn_id` (CASCADE), `product_id`, `qty > 0` (CHECK), `lot_no?`, `declared_value`, `notes` |
| `productionorder` (V2.4) | `number` (per-tenant atomic), `bom_id`, `customer_id`, `rate_plan_id?`, `output_qty > 0` (CHECK), `state` ∈ {`draft/started/completed/delivered/billed/cancelled`} (CHECK), `own_material_cost` (snapshot at start), `output_unit_cost` (snapshot at complete), `invoice_id?` (set at bill), per-stage timestamps |

### 5.5 Banking

| Table | Notes |
|---|---|
| `bankaccount` | `name`, `bank_name?`, `account_number?`, `coa_account_id`, `is_active` |
| `bankstatementimport` | `bank_account_id`, `file_hash` unique (SHA-256), `imported_at`, `row_count`, source filename |
| `statementline` | `import_id` (CASCADE), `date`, `description`, `debit`, `credit`, `balance?`, `matched_transaction_id?` |
| `reconciliation` | `bank_account_id`, period bounds, `statement_balance`, `status` |
| `reconciliationline` | `reconciliation_id`, `journal_entry_id`, `is_matched` |

### 5.6 Cross-cutting

| Table | Notes |
|---|---|
| `taxcode` | `code`, `name`, `rate`, `type` (`output/input` CHECK), `gl_account_id` |
| `exchangerate` | `(date, from_currency, to_currency, rate)`; lookups walk back to nearest date and try inverse fallback |
| `recurringtemplate` | `name`, `frequency` (`daily/weekly/monthly/quarterly/yearly`), `next_run`, `entries_json` (template JV) |
| `idempotencykey` | `(tenant_id, key)` unique; cached body + status |
| `loginattempt` | `ip`, `attempted_at`; sliding-window DB throttle |
| `accountbalance` | Materialised per-account closing balance for locked periods (read-fast trial balance) |

### 5.7 HRM Data Model

**Migrations:** `0023_employees`, `0024_payroll`, `0025_attendance` — 7 new tables; no breaking changes to existing tables.

```
Employee
  - tenant_id, employee_code (EMP-seq), name, department, designation
  - join_date, cnic, bank_account, bank_name, is_active, created_by_id

SalaryComponent
  - code, name, component_type (earnings|deductions|statutory)
  - is_taxable, is_fixed, gl_account_id → Account

EmployeeSalaryStructure
  - employee_id → Employee, component_id → SalaryComponent
  - amount (fixed) or pct_of_basic; effective_from/to

PayrollRun
  - period_start, period_end, pay_date, status (draft→approved→posted→void)
  - jv_number (PR-YYYY-seq), transaction_id → Transaction

PayrollLine (one per employee per run)
  - payroll_run_id → PayrollRun, employee_id → Employee
  - gross_earnings, total_deductions, net_pay

PayrollLineDetail (one per component per line)
  - payroll_line_id → PayrollLine, component_id → SalaryComponent
  - amount, is_override

AttendanceRecord
  - employee_id → Employee, date, time_in (HH:MM), time_out (HH:MM)
  - hours_worked (auto-computed from time_in/time_out), notes
  - status: present | absent | half_day | leave | holiday | off
  - source: manual | biometric
  - raw_data (JSON — biometric device payload; stored verbatim for audit)
```

**Payroll GL posting** (`routers/payroll.py`):

```
Dr  Salary Expense (5xxx — per SalaryComponent.gl_account_id)
  Cr  Salaries Payable (2xxx — net pay)
  Cr  Income Tax Payable
  Cr  EOBI Payable
  ─────────────────────────────
  ∑Dr = ∑Cr  ✓   (enforced by services/posting.py)
```

One `Transaction` is created per `PayrollRun` post; component amounts are aggregated into `JournalEntry` rows per GL account. Void creates a reversing JV. Voucher type `PR` with sequence `PR-YYYY-seq`.

**HRM API endpoints:**

| Endpoint | Notes |
|----------|-------|
| `GET/POST /api/employees` | Employee list (filter active/all) + create; code auto-generated |
| `GET/PUT/DELETE /api/employees/{id}` | Detail, update, soft-delete |
| `GET/PUT /api/employees/{id}/salary-structure` | Replace salary structure atomically |
| `GET/POST/PUT/DELETE /api/payroll/components` | `SalaryComponent` catalog CRUD |
| `POST /api/payroll/runs` | Create run; auto-computes lines from salary structures |
| `POST /api/payroll/runs/{id}/approve` | Mark approved |
| `POST /api/payroll/runs/{id}/post` | Post to GL: `Dr Salary Expense / Cr Salaries Payable + deductions`; PR-YYYY-seq |
| `POST /api/payroll/runs/{id}/void` | Reverse posted run (reversing JV) |
| `GET /api/payroll/runs/{id}/payslip/{eid}` | Structured payslip data |
| `GET/POST /api/attendance` | List with filters (employee, month, status); create with hours auto-compute; duplicate guard |
| `GET /api/attendance/summary` | Per-employee monthly totals |
| `PUT/DELETE /api/attendance/{id}` | Update (recomputes hours); delete blocked for biometric records |
| `POST /api/attendance/bulk` | Upsert batch attendance records |
| `POST /api/attendance/import/biometric` | Match by employee_code, store raw_data, source=biometric |

---

## 6. BUSINESS MODELS & ADAPTIVE UX

`Tenant.business_model` is one of:

| Model | Use case | Extras |
|---|---|---|
| `simple` | Solo / micro-business | Just the universal CoA backbone |
| `services` | Service firms (consulting, agencies) | + Consulting Revenue, Recurring Service Revenue, Deferred Revenue, Subcontractor Costs |
| `trader` | Goods buy-resell | + Finished Goods Inventory, COGS, Freight In, Storage, Inventory Adjustments, GST Receivable |
| `manufacturing` | Value-addition / contract mfg | + RM/WIP/FG inventory, Customer Goods on Hand (memo 1210), Customer Goods Liability (memo 2150), Direct Labour, Manufacturing Overhead, Indirect Materials, Service Revenue (Value-Add) |
| `telecom_franchise` | Mobile-operator franchise | + 56-account franchise CoA: Tracker Deposit `1210`, Load Float `1211`, RSO/Retail load receivables `1212/1213`, MM float `1214`, SIM/IMSI/device inventory `1200–1204`, Commission Receivable `1110`, Franchise Intangible `1300`; Operator Payable `2010`, MM Float Liability `2100`, Postpaid Collections Payable `2110`, Royalty Payable `2120`; revenue `4000–4061` (3% load uplift `4020`, FCA target `4060`); fee amortisation `5030`, royalty `5040`, variance `5070`, penalty `5090`. See WORKFLOW §4.8 |

`Tenant.enabled_modules` is a JSON-serialised list. Derived from `business_model` at signup, but admins can override via `PATCH /api/settings/modules`. Frontend uses it to gate UI sections.

`MODULES_BY_MODEL`:

```python
"simple":        ["invoicing","billing","manual_jv"]
"services":      ["invoicing","billing","manual_jv","service_catalogue"]
"trader":        ["invoicing","billing","manual_jv","inventory"]
"manufacturing": ["invoicing","billing","manual_jv","inventory",
                  "stores","bom","production","customer_goods"]
"telecom_franchise": ["invoicing","billing","manual_jv","inventory",
                  "tracker","sim_airtime","mobile_money","device_sales",
                  "postpaid_billing","commission_tracking","rso_channel","franchise_admin"]
```

The sidebar reads `/api/auth/me` → `tenant.business_model` and filters its NAV array; sections with no visible items are hidden entirely.

---

## 7. CHART OF ACCOUNTS TEMPLATES

`db.py::_coa_for(business_model)` composes the CoA from a common backbone plus a model-specific layer. Codes overlap on the backbone so reports keep working regardless of which model.

**Multi-level hierarchy (V2.5).** The template is now hierarchical: a shared **group skeleton** lives in `_COA_GROUPS` (`1` Assets → `11` Current / `12` Non-Current; `2` Liabilities → `21` Current; `3` Equity; `4` Revenue → `41` Operating / `49` Other Income; `5` Expenses → `51` Cost of Sales / `52` Operating / `59` Other) and every leaf account carries a `parent_code` pointing at one of those groups. Leaf codes are unchanged (so the auto-posting defaults 1100/2200/4000/5010/1200 still resolve). `seed_data` inserts the template in two passes (create all, then wire `parent_id`); the group rows are `is_group=True` and non-postable. Group balances are computed by roll-up (`services/account_tree.py`).

### Common backbone (every tenant)
1000 Cash · 1010 Bank · 1100 AR · 2000 AP · 2200 GST Payable · 3000 Owner Capital · 3010 Drawings · 3100 Retained Earnings · 4000 Sales Revenue · 4900 Other Income · 5000 General Expenses · 5050 Depreciation · 5900 Other Expenses

### Services extra
4010 Consulting Revenue · 4020 Recurring Service Revenue · 2300 Deferred Revenue · 5110 Subcontractor Costs

### Trader extra
1200 Finished Goods Inventory · 1250 GST Receivable · 5010 COGS · 5020 Freight In · 5030 Storage · 5040 Inventory Adjustments

### Manufacturing extra
1200 Raw Material Inventory · 1201 Work-in-Progress · 1202 Finished Goods Inventory · **1210 Customer Goods on Hand (memo)** · 1250 GST Receivable · **2150 Customer Goods Liability (memo)** · 4010 Service Revenue (Value-Add) · 5010 COGS · 5100 Direct Labour · 5110 Subcontractor Costs · 5200 Manufacturing Overhead · 5210 Indirect Materials

### Telecom franchise extra (`_COA_TELECOM_FRANCHISE_EXTRA`, 56 accounts)
1110 Commission Receivable · 1120 RSO Receivables · 1130 Postpaid Customer Receivable · 1200 SIM Card Inventory · 1201 Scratch/PIN · 1202 Device Inventory · 1204 IMSI Inventory · **1210 Tracker Deposit Balance** · **1211 Load Float Asset (MSR)** · 1212 RSO Load Receivable · 1213 Retail Load Receivable · 1214 Mobile Money Float Asset · 1250 GST Receivable · 1300 Franchise Intangible · 1301 Accum. Amortisation · 2010 Operator Payable · 2100 MM Float Liability · 2110 Postpaid Collections Payable · 2120 Royalty Payable · 2300 Advance from Operator · 4000 Airtime/Recharge · 4010 SIM Activation · **4020 Load Uplift Commission (3%)** · 4021 Recharge Commission · 4022 Mobile Money Commission · 4023 Bundle Commission · 4030 SIM Sale · 4031 Device Sales · 4040 Postpaid Billing · 4050 RSO Channel · **4060 FCA Target Commission** · 4061 Franchise Incentive · 5010/5011/5012 COGS (devices/SIMs/scratch) · 5020 RSO Incentives · 5021 Retail Incentives · 5030 Fee Amortisation · 5040 Royalty · 5060 MM Transaction Costs · 5070 Tracker/Float Variance · 5080 Bad Debt-RSO · 5090 Target Shortfall Penalty

Business model is selected at signup. Switching later via `PATCH /api/settings/business-model` *(admin-only API; not exposed in the UI)* adds the new template's accounts that don't already exist (never deletes existing ones).

---

## 8. API CATALOGUE — EVERY ENDPOINT

All endpoints are mounted at `/api/*` and (transparently) at `/api/v1/*` for SDK stability.

### Auth & profile (`/api/auth`)
- `POST /signup` — body: `{email, password, full_name, company_name, business_model?}` → creates Tenant + User (role=owner) + seeds CoA + locations + sequence counters.
- `POST /login` — OAuth2-form (`username` + `password`) → returns `access_token` + `must_change_password` and sets `eb_access` (HttpOnly) + `eb_csrf` cookies. Rejects inactive users (403); stamps `last_login_at`.
- `POST /logout` — clears cookies.
- `GET /me` — returns the full user (id, email, full_name, phone, avatar_url, role, must_change_password, created_at, last_login_at) + `tenant: {id, name, base_currency, business_model, enabled_modules}`.
- `PATCH /me` — update own `full_name` / `phone`.
- `POST /change-password` — verify current → set new (≥ 8); clears `must_change_password`.
- `POST` / `DELETE /me/avatar`, `GET /users/{id}/avatar` — avatar upload/remove/serve (tenant-scoped, ≤ 5 MB image).
- `GET /invite/{token}` (public) — inspect a pending invite; `POST /accept-invite` (public) — activate the User from a token.

### Team / users (`/api/users`, admin+)
- `GET /` list · `POST /` create (temp password, returned once) · `PATCH /{id}` role/active/name · `POST /{id}/reset-password` · `DELETE /{id}` deactivate.
- `GET`/`POST /invites`, `DELETE /invites/{id}` — tokenized invitations (7-day expiry).
- Guards: no self-role-change / self-deactivation; owner role is owner-grantable only; last active owner protected.

### Settings (`/api/settings`)
- `GET /` — KV map. Includes:
  - `company_name` — displayed in header and reports
  - `business_tagline` — shown below company name (e.g., "Easy-Books · Double-Entry Accounting")
  - `currency` — base currency for all transactions
  - `tax_id` — business tax/EIN identifier
  - `fiscal_year_start` — accounting year start month
  - `financial_statement_date` — reporting period preference
  - `invoice_prefix` / `bill_prefix` — document numbering prefixes
  - `email_notifications` — notification preference
  - `block_negative_stock` — when `true`, sales that would drive stock below 0 are rejected (HTTP 400)
- `PATCH /` — upsert KV pairs (all fields optional, only provided fields updated).
- `PATCH /business-model` *(admin)* — switches model, adds missing CoA accounts.
- `PATCH /modules` *(admin)* — overrides `enabled_modules` independently.

### Accounts (`/api/accounts`)
- CRUD + list. Tenant-scoped.

### Customers / Vendors / Products (`/api/customers`, `/api/vendors`, `/api/products`)
- CRUD. `Product.type` ∈ `stock|service`; stock products carry running `avg_cost` + `stock_qty`.
- `/api/product-categories` — CRUD for the 2-level taxonomy (parent → sub-category). `DELETE /{id}` returns 400 while any subcategory or product is assigned.

### Invoices (`/api/invoices`)
- `POST /` — creates Invoice + lines + posts JE (Dr AR / Cr Revenue + Cr GST). If a line has `product_id` referencing a stock product, also relieves stock at WAvg and posts a separate COGS sub-JV. **Deferred revenue (IFRS 15):** if a line's product is `is_deferred`, its net is credited to Deferred Revenue (2300) instead of Revenue and a `DeferredRevenueSchedule` is originated (`services/deferred.py`); the deferred GL credit is clamped to subtotal so multi-currency invoices stay balanced.
- `GET /` — list with status filter + aging join.
- `GET /{id}` — single + lines.
- `PUT /{id}` — **edit a posted invoice** (reverse-and-repost): blocked if paid or in a locked period; honours the `block_negative_stock` guard on the re-consume; for deferred invoices, rebuilds the schedule (or blocks once recognition has begun).
- `DELETE /{id}` — only when no payment allocated.

### Bills (`/api/bills`)
- `POST /` — Bill + lines + JE (Dr Expense + Dr GST / Cr AP). Stock-line purchases call `record_purchase` (appends layer, recomputes avg_cost).
- Mirrors invoice endpoints.

### Payments (`/api/payments`)
- `POST /received` — `PaymentReceived` + allocations. JE: Dr Cash/Bank / Cr AR.
- `POST /made` — `BillPayment` + allocations. JE: Dr AP / Cr Cash/Bank.
- `POST /allocate` — re-allocate an existing payment.

### Transactions (`/api/transactions`)
- `POST /` — manual JV (`entries: [{account_id, debit, credit}]`); validated by `services/posting.py`.
- `POST /{id}/reverse` — posts mirror JV. Unwinds derived state: drops PaymentAllocations + recomputes statuses; reverses stock purchase or consumption; cannot reverse a reversal.
- `GET /` — list.
- `GET /{id}` — header + lines **+ `source_docs[]`** (reverse-resolves Invoice / Bill / Payment / GRN that posted this JV) **+ `is_reversed` + `reversed_by_id`** (audit trail per ISA 230 §A6).

### Periods (`/api/periods`)
- CRUD + `POST /{id}/lock`, `POST /{id}/close`, `POST /{id}/reopen`. Close posts the closing JV (Revenue/Expense → Retained Earnings) and materialises `AccountBalance` rows.

### Tax codes (`/api/tax-codes`)
- CRUD.

### Exchange rates (`/api/exchange-rates`)
- CRUD; lookups fall back to inverse (`EUR→USD` resolves a `USD→EUR` entry) and to the nearest prior date.

### Recurring (`/api/recurring`)
- CRUD + `POST /run-due` — materialises templates whose `next_run ≤ today`; idempotent per `(template, next_run)`.

### Bank
- `POST /api/bank-accounts` + CRUD + `GET /{id}/balance` (derived from GL).
- `POST /api/bank-imports/upload` — multipart CSV; dedupes by SHA-256.
- `POST /api/bank-imports/{import_id}/auto-match` — matches StatementLines to JVs by amount ± 3-day window.
- `POST /api/reconciliations` — CRUD + close.

### Stock locations & movements (V2.2) (`/api/stock-locations`)
- `GET /` · `POST /` · `PATCH /{id}` · `DELETE /{id}` — CRUD.
- `GET /movements` — filterable event log (`direction`, `product_id`, `location_id`, `date_from/to`).
- `GET /custody` — per-(customer, product) summary computed from custodial layers.
- `GET /{id}/stock` — per-location qty + value across lots.

### Bills of Material (V2.3) (`/api/bom`)
- `GET /` — list (optional `output_product_id`, `active_only`).
- `GET /{id}` — header + lines.
- `POST /` — creates new version (auto-deactivates prior versions for the same output product).
- `PATCH /{id}/deactivate` — soft-archive.

### Rate plans (V2.3) (`/api/rate-plans`)
- `GET /` · `POST /` (auto-version) · `PUT /{id}` (in-place edit).
- `POST /assign` — body `{customer_id, rate_plan_id}` — deactivates customer's other active plans; reactivates existing pair if previously assigned.
- `GET /customer/{customer_id}` — full assignment history with active flag.

### Goods Receipt (V2.4) (`/api/grn`)
- `GET /` · `GET /{id}` · `POST /`. Creation:
  1. Validates customer + location (must be `customer_custodial`) + every product belongs to tenant.
  2. Mints `GRN-NNNN` via SequenceCounter.
  3. Appends one InventoryLayer per line (owner_customer_id set, unit_cost=0).
  4. Emits `CUSTODIAL_RECEIPT` StockMovement per line (posted_to_gl=False).
  5. If `sum(declared_value) > 0`: posts memo JV `Dr 1210 / Cr 2150` (forces `is_memo=True` on auto-resolved accounts).

### Production Orders (V2.4) (`/api/production-orders`)
- `GET /` (filter by `state`, `customer_id`) · `GET /{id}` · `POST /` (create draft).
- `POST /{id}/start` — for each BoM line:
  - own_stock: pulls FIFO across own-stock layers, decrements `product.stock_qty`, emits ISSUE movement at WAvg cost; aggregates `own_material_cost`.
  - customer_supplied: pulls FIFO across that customer's custodial layers, emits CUSTODIAL_ISSUE.
  - Posts `Dr WIP / Cr Raw Material` for the aggregated own_material_cost (no JE for customer_supplied).
  - Stores `own_material_cost` on PO; transitions state → `started`.
- `POST /{id}/complete` —
  - Computes `output_unit_cost = own_material_cost / output_qty`.
  - Calls `record_purchase` to create a finished-goods InventoryLayer at unit_cost; reclassifies the resulting movement to `COMPLETION` (from=WIP, to=MAIN).
  - Posts `Dr Finished Goods / Cr WIP` for `own_material_cost`.
  - Transitions state → `completed`.
- `POST /{id}/deliver` —
  - Calls `consume_stock` to relieve FG; reclassifies the resulting movement to `DELIVERY`.
  - Posts `Dr COGS / Cr Finished Goods` for the relieved cost.
  - Releases custodial memo balance: for every GRN of this customer where all custodial layers are drained, sums up the declared_value and posts `Dr 2150 / Cr 1210`; zeroes `GoodsReceiptNote.declared_value` so the same GRN isn't released twice.
  - Transitions state → `delivered`.
- `POST /{id}/bill` —
  - Computes the invoice total via the RatePlan formula.
  - Mints `INV-NNNN` + creates Invoice + InvoiceLines (one per component: value-add, materials, overhead, margin — only those that are non-zero).
  - Posts `Dr AR / Cr 4010 Service Revenue (Value-Add)` for the net total.
  - Sets `ProductionOrder.invoice_id`; transitions state → `billed`.
- `POST /{id}/cancel` — only legal from `draft`. Later states require manual JV reversal.

### Manufacturing reports (V2.5) (`/api/manufacturing`)
- `GET /dashboard` — pipeline counts + WIP/FG/custodial totals.
- `GET /wip-aging` — open POs bucketed `0-7d / 8-14d / 15-30d / 30d+`.
- `GET /production-summary` — POs by state, with optional date range.
- `GET /customer-custody` — per-(customer, product) custody view + unreleased declared values.

### Reports (`/api/reports`)
- `/journal`, `/trial-balance`, `/income-statement`, `/balance-sheet`, `/cash-flow`, `/tax-summary`, `/dashboard`, `/aging`.
- **Hierarchical statements (V2.5).** Single-period `/trial-balance`, `/balance-sheet`, and `/income-statement` return a **nested tree** rolled up over the multi-level CoA (`services/account_tree.py`, parent = own + Σ descendant leaves, zero subtrees pruned): TB → `{tree, totals}`; BS → `{assets, liabilities, equity, totals}` (with the RE-CUR synthetic current-earnings equity line); P&L → `{revenue, expenses, totals}` + `net_profit`. **Comparison mode** (`compare_end` / `compare_start`+`compare_end`) keeps the prior flat `{current, comparison}` shape. The frontend `<AccountTree>` renders expand/collapse with leaf drill-down to the ledger and on to the voucher.
- `/ledger?account_id=…&start=…&end=…` — running balance per row; when `start`/`end` supplied also returns `opening_balance` (net of all JEs before `start`) and `closing_balance` (`opening + Σdebits − Σcredits`), following per-account-type sign convention.
- `/product-ledger?product_id=…&start=…&end=…` — stock movements + running qty; supports per-location or consolidated view.
- `/inventory-performance` — on-hand qty/value, low-stock, slow-movers, units sold + COGS.
- `/customer-performance` — revenue, invoice count, outstanding AR, avg days-to-pay per customer.

### Sub-ledgers & Statements (drill-down layer)
- `GET /api/customers/{id}/ledger?start=…&end=…` — per-customer AR sub-ledger. Opening balance, period activity (date, JV no., document, qty_out, Dr, Cr, running balance), closing balance. Aggregates `JournalEntry` rows that touch AR (`account.code = 1100`) where the source `Invoice` or `PaymentReceived` belongs to the customer. Maps to **IFRS 7.7** "information that enables users to evaluate the significance of financial instruments".
- `GET /api/customers/{id}/statement?from_date=&to_date=` — account statement: JSON `{customer, period, opening_balance, invoices[], payments[], closing_balance}`. Opening balance = `customer.opening_balance + Σ(pre-period invoices − pre-period payments against those invoices)`. Closing = `opening + period_inv_total − period_paid_total`. Frontend page at `/customers/[id]/statement`.
- `GET /api/vendors/{id}/ledger?start=…&end=…` — per-vendor AP sub-ledger, credit-normal (`Σ credit − Σ debit`, positive = amount owed). Same shape, AP-side. Maps to **IAS 1.78(b)** "trade and other payables".
- `GET /api/vendors/{id}/statement?from_date=&to_date=` — AP mirror of the customer statement, using bills + bill-payments. Frontend page at `/vendors/[id]/statement`.
- `GET /api/products/{id}/stock-card?start=…&end=…` — per-product stock card driven by the `StockMovement` event log (the source of truth — `Product.stock_qty` is a derived projection). Opening qty + value, per-row `qty_in / qty_out / unit_cost / running_qty / running_value`. Maps to **IAS 2.36(d)** "the carrying amount of inventories carried at fair value less costs to sell" and IAS 2.36(g) movement breakdown.

### Commissions (`/api/commissions`)
- `GET /plans` · `POST /plans` · `PUT /plans/{id}` · `DELETE /plans/{id}` — commission plan CRUD.
- `GET /staff` — users who have any commission plan.
- `GET /ledger` — computed commission entries with status (`pending/approved/posted`).
- `POST /compute` — body `{period: "YYYY-MM", user_ids?: [...]}` — computes and creates `CommissionLedger` entries.
- `POST /ledger/{id}/approve` — marks entry approved.
- `POST /ledger/{id}/post` — body `{expense_account_id, payable_account_id, date}` — posts `Dr Commission Expense / Cr Commissions Payable`.

### Promotional Discounts (`/api/promo-rules`)
- `GET /` · `POST /` · `PUT /{id}` · `DELETE /{id}` — promo rule CRUD.
- `POST /check` — body `{lines: [{product_id, qty, rate}]}` — returns `{suggestions: [{line_index, rule_id, discount_pct, name}]}`. The `InvoiceForm` "Apply Promos" button calls this and patches discount_pct onto matching lines.

### User Permissions (`/api/permissions`)
- `GET /me` — returns `{permissions: {resource: access_level}, my_data_only, module_enabled}` for the calling user.
- `GET /resources` — full list of 60 resource keys with display names.
- `GET /users/{id}` *(admin)* — effective permissions for another user.
- `PUT /users/{id}` *(admin)* — set permission overrides (body: `{resource_key, access_level}[]`; `access_level="default"` removes the override row).
- `PATCH /users/{id}/my-data-only` *(admin)* — toggle `{my_data_only: bool}`.

### Audit (`/api/audit`)
- `GET /` — filterable list of `AuditLog` rows.

### Imports (`/api/imports`)
- CSV upload for Products, Customers, Vendors, Accounts. Validates required columns; row-level error reporting.

### Admin (`/api/admin`)
- `POST /demo/seed` *(admin+)* — load all 5 demo tenants with full mock data. `DELETE /demo/seed` — remove demo data.

---

## 9. ACCOUNTING CYCLES & GL POSTINGS

### 9.1 Sales / AR
```
Invoice posted:    Dr 1100 AR / Cr 4000 Revenue (+ Cr 2200 GST if any)
Stock-item line:   Dr 5010 COGS / Cr 1200 Inventory (separate sub-JV)
Payment received:  Dr 1000 Cash / Cr 1100 AR  (allocations decide which invoice)
```

### 9.2 Purchases / AP
```
Bill posted:    Dr 5xxx Expense / Cr 2000 AP  (+ Dr 1250 GST if any)
Stock receipt:  appends InventoryLayer, recomputes Product.avg_cost (WAvg)
Bill payment:   Dr 2000 AP / Cr 1000 Cash
```

### 9.3 Manual JV
```
User submits {entries}. services.posting.post_transaction validates:
  Σdr == Σcr (exact Decimal equality)
  no entry has both debit and credit > 0
  no entry is zero on both sides
  none of the accounts is locked into a closed period
  every account belongs to the caller's tenant
Then it writes one Transaction header + N JournalEntry rows + AuditLog row.
```

### 9.4 Period close
```
1. Aggregate net balances of Revenue + Expense accounts in period.
2. Post closing JV:
     Dr Revenue (net Cr)
     Cr Expense (net Dr)
     Cr/Dr Retained Earnings (plug)
3. Materialise AccountBalance per account for fast TB reads.
4. Period.is_locked = True (posting service refuses future writes in this date range).
```

### 9.5 Reversal — IAS 8.42 (correction of prior-period errors)
```
POST /transactions/{id}/reverse:
  1. Refuses if already reversed.
  2. Posts mirror JV (swap each entry's debit/credit).
  3. Unwinds derived state:
     - PaymentReceived/BillPayment: deletes allocations + recomputes invoice/bill status.
     - Invoice with stock line: calls reverse_consumption (restores qty at COGS unit cost).
     - Bill with stock line: calls reverse_purchase (drops the layer + recomputes avg_cost).
  4. Links original and mirror via reversed_by_id.
```

### 9.6 Manufacturing (see §10)

### 9.7 Sub-Ledgers & Audit-Trail Drill-Down
```
Trial Balance ── click account code ──▶ /ledger?account={name}
                                              │
                                              ▼
                              Account ledger (running balance per JV)
                                              │ click JV no.
                                              ▼
                                       /journal/{id}  (JV detail)
                                              │
                                source_docs[] ─┴── reversed_by_id
                                              │
                                              ▼
                              /invoices/{id} | /bills/{id} | /payments-received/{id} | /grn/{id}
                                              │
                                  click party ▼
                                              ▼
                              /customers/{id}/ledger | /vendors/{id}/ledger
                                              │
                                              ▼
                                       (back to JV)
```

**Architectural primitives:**
- `<DocLink type={kind} id={id} label={text} />` (frontend/src/components/DocLink.tsx) — single resolver for 11 entity kinds. No page constructs hrefs inline.
- Source-doc resolver in `routers/transactions.py` checks `Invoice / Bill / PaymentReceived / BillPayment / GoodsReceiptNote` for `transaction_id == jv.id` plus the COGS sub-JV link via `Transaction.parent_transaction_id`.
- Sub-ledger SQL aggregates GL postings filtered by the AR/AP account code AND by source-document tenancy — never crosses tenant boundary.

**Standards alignment:**
| Need | Standard | Mechanism |
|---|---|---|
| Audit reperformability | ISA 230 §A6 | `GET /transactions/{id}.source_docs[]` + cyclic link graph (no dead ends) |
| Internal control traceability | ISA 315.A82 | Every code/JV-no/doc-no/party-name in every list page is a `<DocLink>` |
| Consistency of presentation | IAS 1.45 | Single resolver = single set of URL conventions across all reports |
| Receivable / payable disclosure | IFRS 7.7, IAS 1.78(b) | AR / AP sub-ledgers with opening, period activity, closing |
| Inventory carrying amount + movement | IAS 2.36(d), 2.36(g) | Stock card with running qty + value driven by StockMovement event log |
| Change history | ISA 240, SOC 2 CC7.3 | `AuditLog` row per mutation — viewable at `/api/audit-log` |

---

## 10. MANUFACTURING TRACK (V2)

> **Premise.** A manufacturing tenant in Easy-Books typically does **value-addition on customer-supplied goods**: the customer brings raw material (fabric, components), you process it (cut, stitch, assemble), then deliver finished product and bill them per processed unit. The challenge is that the customer's material is **never your asset** — yet you need to track its custody, integrate it into a production process, and bill rationally.

### 10.1 Components

```
                          ┌───────────────────────────┐
   CUSTOMER (Brand Co.)   │                           │
   brings fabric          │  Easy-Books Tenant         │
        │                 │  (business_model =        │
        │ GRN             │  'manufacturing')         │
        ▼                 │                           │
   ┌──────────────┐       │   • CoA seeded with        │
   │  GODOWN      │       │     1210/2150 memo pair   │
   │  (customer_  │       │   • Stock locations seeded │
   │   custodial) │       │     MAIN, GODOWN, WIP     │
   └──────┬───────┘       │   • BoMs + Rate Plans      │
          │ CUSTODIAL_    │     define recipe + price │
          │ ISSUE          │                           │
          ▼               │                           │
   ┌──────────────┐       │                           │
   │     WIP       │ ◀────┤   Production Order        │
   │     (wip)     │      │   walks state machine     │
   └──────┬───────┘       │                           │
          │ COMPLETION    │                           │
          ▼               │                           │
   ┌──────────────┐       │                           │
   │     MAIN     │       │                           │
   │     (own)    │       │                           │
   └──────┬───────┘       │                           │
          │ DELIVERY      │                           │
          ▼               └───────────────────────────┘
   CUSTOMER receives finished goods + invoice via RatePlan
```

### 10.2 Invariants

1. **Customer goods are off-balance-sheet.** They live only in custodial `InventoryLayer` rows (owner_customer_id set, unit_cost=0), in the optional memo pair 1210/2150, and in the stock movement log with `posted_to_gl=False`.
2. **No state skip.** A PO can only `start` from `draft`, only `complete` from `started`, etc. Endpoints return 400 otherwise.
3. **Cost flow through WIP.** Per user directive 8.3.8: every own-stock cost that becomes part of an output unit flows `Raw Material → WIP → Finished Goods → COGS`. Customer-supplied components are off-ledger.
4. **Memo release atomicity.** When the last custodial layer of a GRN is drained, that GRN's full `declared_value` is released in one go on the next deliver call. `declared_value` is then zeroed to prevent double-release.
5. **Loss is absorbed.** Per user directive 8.3.6: damages in WIP/FG are expensed, never billed back to the customer. (Manual JV currently — automation is on roadmap.)
6. **Partial delivery is allowed.** A PO that delivers fewer output_qty than completed produces a smaller COGS write-down; the remainder stays in FG. (V2.4 implements only full-quantity delivery; partial-deliver endpoint is on the V2.6 list.)

### 10.3 Worked example

```
Setup:
  Customer: Brand Co. (has an active "STITCH" rate plan: $10/unit, materials at cost,
                       5% overhead, 10% margin)
  Products: WIDGET (output), BUTTON (own_stock), FABRIC (customer_supplied)
  BoM v1:   1 WIDGET = 2 BUTTON (own_stock) + 1 FABRIC (customer_supplied)
  Purchase: 100 BUTTON @ $1  →  Product.avg_cost(BUTTON) = $1, MAIN layer 100/$1

GRN-0001 from Brand Co.: 30 FABRIC, lot L-001, declared_value $300
  → GODOWN layer 30/$0 (owner=Brand)
  → CUSTODIAL_RECEIPT movement, posted_to_gl=False
  → JE:  Dr 1210 Customer Goods on Hand  300
         Cr 2150 Customer Goods Liability 300

PO-0001: produce 10 WIDGET for Brand Co.
  → draft

POST /production-orders/1/start
  → consume 20 BUTTON from MAIN at $1 each = $20
       MAIN layer 100 → 80, Product.stock_qty 100 → 80
       ISSUE movement: 20 BUTTON, MAIN→WIP
       JE:  Dr 1201 WIP            20
            Cr 1200 Raw Material   20
  → consume 10 FABRIC from GODOWN
       GODOWN layer 30 → 20
       CUSTODIAL_ISSUE movement, posted_to_gl=False
  → state = started, own_material_cost = $20

POST /production-orders/1/complete
  → unit_cost = $20 / 10 = $2
  → record_purchase(WIDGET, 10, $2) → MAIN layer of 10 WIDGET at $2
       Movement reclassified to COMPLETION (from=WIP, to=MAIN)
       JE:  Dr 1202 Finished Goods 20
            Cr 1201 WIP            20
  → state = completed, output_unit_cost = $2

POST /production-orders/1/deliver
  → consume_stock(WIDGET, 10) at avg_cost $2 → COGS $20
       FG layer drained 10 → 0
       Movement reclassified to DELIVERY
       JE:  Dr 5010 COGS           20
            Cr 1202 Finished Goods 20
  → GODOWN layer for FABRIC: 20 remaining → memo NOT released yet
  → state = delivered

POST /production-orders/1/bill
  → RatePlan formula:
       base       = 10 × $10 = $100
       materials  = $20  (includes_materials_at_cost=True)
       subtotal_pre = $120
       overhead   = 5% × $120 = $6
       subtotal   = $126
       margin     = 10% × $126 = $12.60
       total      = $138.60
  → Invoice INV-0001 created with 4 lines:
       value-add  ($100)
       materials  ($20)
       overhead   ($6)
       margin     ($12.60)
  → JE:  Dr 1100 AR                       138.60
         Cr 4010 Service Revenue          138.60
  → state = billed, invoice_id = 1

Later, when the remaining 20 FABRIC are consumed by another PO and that PO
delivers, the memo balance for GRN-0001 is released:
  → JE:  Dr 2150 Customer Goods Liability 300
         Cr 1210 Customer Goods on Hand   300
```

### 10.4 Why per-stage JVs (not one big one)

Each transition is its own `Transaction`. Benefits:
- A reversal of one stage doesn't unintentionally undo another.
- The journal report shows the operational story (issue → capitalise → deliver → bill) instead of an opaque mega-JV.
- Period-close logic that operates on completed-but-not-delivered POs sees the right snapshot (FG carries cost, AR hasn't been hit yet).

---

## 10A. TELECOM FRANCHISE TRACK (V3)

Applies to `business_model == 'telecom_franchise'`. 23 `tc_*` tables (`models_telecom.py`); GL writes flow through `services/tracker_posting.py` + `services/franchise_posting.py`, which call the same central `services/posting.py`. Routes in `routers/telecom.py` (40+ endpoints) and `routers/telecom_reports.py` (9 reports). Frontend in `src/app/(dashboard)/telecom/` (dashboard + 9 pages) built on `components/telecom/ActionForm` + `primitives`.

### 10A.1 Entities (`tc_*`)
Operator · TrackerAccount (deposit/load balances) · TrackerTransaction · SimBatch · SimActivation · AirtimeStock · AirtimeSale · LoadTransfer · RetailOutlet · RsoAgent · RsoStockIssue · RsoDailyCollection · RsoTarget · FcaEvent · KpiTarget · MobileMoneyAccount · MobileMoneyTransaction · DeviceImei · PostpaidConnection · PostpaidBillCycle · CommissionStatement · CommissionLine · FranchiseAgreement.

### 10A.2 The operational cycle
1. **Fund** — tracker deposit (`Dr 1210 / Cr Bank`), then load order with 3% uplift (`Dr 1211 ×1.03 / Cr 1210 / Cr 4020 ×0.03`).
2. **Procure** — SIM/IMSI stock debit (`Dr 1200 / Cr 1210`, creates a batch).
3. **Distribute** — MSR→RSO (`Dr 1212 / Cr 1211`), RSO→Retail (`Dr 1213 / Cr 1212`).
4. **Sell/activate** — counter sale + COGS; activation → accrue commission (`Dr 1110 / Cr 4020`).
5. **Collect** — RSO daily collection (`Dr Bank / Cr 1212 / Cr 1120`, variance → `5070`/`4900`).
6. **Targets** — FCA events counted; monthly settlement pays `4060` or penalises `5090`.
7. **Adjacent revenue** — mobile money (`1214`/`2100`/`4022`), postpaid bill/collect/remit (`1130`/`2110`/`4040`).
8. **Reconcile & amortise** — settle commission statements against `1110`; capitalise fee `1300`, amortise `5030`, royalty `5040`/`2120`.

### 10A.3 Invariants
`tc_tracker_account.deposit_balance == GL 1210` · `tc_tracker_account.load_balance == GL 1211` · load order balances exactly · FCA events are counted, never journalised per event · trial balance nets to zero. Full Dr/Cr table in WORKFLOW §4.8.

---

## 11. REPORTS

| Endpoint | Source | Notes |
|---|---|---|
| `GET /api/reports/journal` | `Transaction` + `JournalEntry` | Date-range + skip/limit |
| `GET /api/reports/ledger?account_id=…&start=…&end=…` | `JournalEntry` | Running balance per row; `start`/`end` params add `opening_balance` (net of pre-period JEs) + `closing_balance` (`opening + Σdr − Σcr`, sign follows account-type convention) |
| `GET /api/reports/trial-balance` | `JournalEntry` (live) or `AccountBalance` (locked periods) | Excludes `is_memo` from totals |
| `GET /api/reports/income-statement` | Revenue + Expense accounts | Closed periods exclude reversed JVs |
| `GET /api/reports/balance-sheet` | Asset/Liability/Equity accounts | Memo accounts shown in separate Custodial section |
| `GET /api/reports/cash-flow` | Indirect method | Operating activities derived from net income + non-cash adjustments |
| `GET /api/reports/tax-summary` | GST output + input + income-tax estimate | Per-period |
| `GET /api/reports/aging` | Invoice/Bill + PaymentAllocation | **Outstanding** balance (net of partial payments), aged bucket; AR/AP aging pages drill into customer/vendor sub-ledger |
| `GET /api/reports/dashboard` | Aggregates | KPI tiles |
| `GET /api/reports/product-ledger` | `StockMovement` | Stock movements + running qty; per-location or consolidated |
| `GET /api/reports/inventory-performance` | `Product` + `StockMovement` + `InventoryLayer` | On-hand qty/value, low-stock, slow-movers, units sold + COGS |
| `GET /api/reports/customer-performance` | `Invoice` + `PaymentReceived` | Revenue, invoice count, outstanding AR, avg days-to-pay per customer |
| `GET /api/manufacturing/dashboard` | ProductionOrder + InventoryLayer | Pipeline + WIP/FG/custodial |
| `GET /api/manufacturing/wip-aging` | ProductionOrder | Days since `started_at` |
| `GET /api/manufacturing/production-summary` | ProductionOrder | By state |
| `GET /api/manufacturing/customer-custody` | InventoryLayer + GoodsReceiptNote | Per-(customer, product) |

---

## 12. SECURITY MODEL

### 12.1 Multi-tenant isolation
- Every domain table has `tenant_id`.
- Every router query starts with `Model.tenant_id == user.tenant_id`.
- `services/posting.py` re-validates that referenced account IDs belong to the caller's tenant.
- Cross-tenant access returns 404 (never 403 — prevents enumeration).

### 12.2 RBAC
- Roles: `viewer < accountant < admin < owner` (rank in `_ROLE_ORDER`).
- `WriteUserDep` requires `accountant+` (most mutations).
- `AdminUserDep` requires `admin+` (settings, business-model switch, modules, **all of `/api/users`**).
- DB CHECK enforces role values; first user of a tenant is `owner`.
- **Active check:** `get_current_user` rejects `is_active=false` users on every request (403) — deactivation is instant, not deferred to token expiry.
- **Member management guards:** no self-role-change or self-deactivation; only an owner grants/edits the `owner` role; the last active owner can't be demoted or deactivated.

### 12.3 Auth
- **JWT (HS256)** signed with `JWT_SECRET_KEY`. Payload: `{sub: email, tenant_id, exp}`. Auth middleware decodes from either:
  - `Authorization: Bearer <token>` (SDK / curl / mobile clients), OR
  - `eb_access` HttpOnly cookie (browser SPA).
- Login returns both — caller picks.
- `JWT_SECRET_KEY` is mandatory in production (startup fails on insecure default).

### 12.4 CSRF
- Double-submit cookie. On login the backend sets both `eb_access` (HttpOnly) and `eb_csrf` (JS-readable).
- The CsrfMiddleware enforces, for any mutating method with cookie auth, that `X-CSRF-Token` header equals `eb_csrf` cookie. Mismatch → 403.
- Bearer-token clients are exempt (no ambient browser authority to exploit).
- Auth endpoints (signup/login/logout) are exempt — they set the cookies.

### 12.5 Login throttle
- DB-backed `LoginAttempt(ip, attempted_at)`. Sliding window: 10 attempts per IP per 60 s.
- Survives uvicorn worker restarts and is shared across workers (unlike an in-memory counter).

### 12.6 Period lock
- A locked `AccountingPeriod` rejects writes whose `date` falls within `[period_start, period_end]`.
- Enforced inside `services/posting.py::_check_period_locked` — every write path goes through it.

### 12.7 Idempotency keys
- Mutating endpoints support `Idempotency-Key: <uuid>` header. The middleware caches the response (status + body) keyed by `(tenant_id, key)`.
- Retries return the cached response with `Idempotency-Replay: true`. TTL is a configurable horizon.

### 12.8 Atomic numbering
- Invoice/Bill/GRN/PO numbers come from per-tenant `SequenceCounter` rows.
- `next_number(session, tenant_id, name, prefix)` does `SELECT … FOR UPDATE` so concurrent POSTs serialise. The increment is part of the same DB transaction as the document — rollback releases the consumed value.

---

## 13. CROSS-CUTTING CONCERNS

### 13.1 Money
- `services/money.py::D(x)` coerces to `Decimal` from str/float/int.
- `money(x)` rounds to 4 places using `ROUND_HALF_EVEN` (banker's rounding).
- `ZERO = D(0)`. Avoid float arithmetic in any financial path.

### 13.2 Multi-currency
- `Tenant.base_currency` (e.g. "USD") is the GL currency.
- Invoices/Bills carry `currency` + `exchange_rate` (snapshot at issue).
- `services/fx.py::rate_to_base(date, from, to_base)` walks back to the nearest prior `ExchangeRate` row. If the (from→to) entry doesn't exist, it tries `1 / rate(to→from)`.
- GL is always posted in base currency; the document keeps original-currency amounts for printing.

### 13.3 Audit log
- Every `log_audit(session, user, action, entity_type, entity_id, detail)` writes one row.
- `entity_type` values: `account, customer, vendor, invoice, bill, payment, transaction, period, grn, production_order, rate_plan, bom, ...`.
- `detail` is a JSON blob — caller decides what context to record.

### 13.4 Idempotent migrations
- Schema bootstrapped via `SQLModel.metadata.create_all()`. No Alembic. New columns require manual `ALTER TABLE` or DB reset.
- V2.2's `0011_stock_locations` uses `op.execute("ALTER TABLE … ADD COLUMN …")` instead of `batch_alter_table` because the legacy `SQLModel.metadata.create_all` baseline had anonymous constraints that batch-mode couldn't rename. SQLite + Postgres both support `ADD COLUMN` without table reconstruction.

### 13.5 Guidance components
- `HelpCallout` — expandable in-page panel, three tones (tip/warning/success). Use at the top of forms and pages to explain WHAT + WHY.
- `FieldHint` — small inline hint below a form field.
- `EmptyStateGuide` — full empty-list state with numbered steps + primary/secondary actions. Use on every list page when there are zero records.

---

## 14. FRONTEND ARCHITECTURE

### 14.1 Routing
- Next.js 16 App Router. `(dashboard)` route group wraps all authenticated pages.
- `DashboardLayout` checks `isAuthenticated()` and redirects to `/login` if missing.

### 14.2 API layer
- `src/lib/api.ts::apiFetch(path, options)` — auto-injects `Authorization: Bearer` from `localStorage['access_token']`. Throws `Error(detail)` on non-2xx.

### 14.3 State
- `SettingsContext` (mounted at the dashboard layout) fetches `/api/settings` on init, provides `{currency, company_name}` app-wide. No external state library.
- Local component state (`useState`) for forms.

### 14.4 Adaptive Sidebar
- `Sidebar.tsx` fetches `/api/auth/me` on mount.
- `NAV` items can carry `forModel: "manufacturing"`. Filtered out unless tenant's business_model matches.
- `SECTIONS` is filtered to those with at least one visible item — sections with no items disappear.
- **3-state collapsible** (v2.7): collapsed (icon strip, 196 px wide) / open (labels visible) / pinned (always open); state stored in `localStorage` (`eb.sidebar.pinned`, `eb.sidebar.open`). Hover over the collapsed strip shows a floating tooltip nav panel. Auto-pins at `window.innerWidth >= 1280`. Sidebar section headers link to their hub page.

### 14.5 Dashboard grid (react-grid-layout)
- Import as `import ReactGridLayout from 'react-grid-layout/legacy'` — this is the **v2 API** (React 19 compatible, self-typed). Do **not** import from `'react-grid-layout'` (v1 API) and do **not** install `@types/react-grid-layout` (types incompatible with v2, will cause TS errors).
- Layout schema v3: `{version:3, layouts:{lg, sm?, xs?}}` with `BP_COLS = {lg:4, sm:2, xs:1}` and `rowHeight=96`.

### 14.6 Brand
- Background: `#f6f3ee` (cream)
- Accent: `#b8943f` (gold)
- Text: `#1a1814` (charcoal)
- Fonts: DM Sans (UI), DM Serif Display (headings)
- Icons: `lucide-react` only.

### 14.7 Theme System (v2.7)

`src/context/ThemeContext.tsx` — provides `{mode, setMode, color, setColor}` app-wide.

**Display modes (3):** `light` | `dark` | `system` (follows `prefers-color-scheme`). Stored in `localStorage` key `eb.theme`. The header theme icon cycles Light → Dark → System. The `layout.tsx` shell includes an anti-flash inline script that reads `eb.theme` and sets `[data-theme]` on `<html>` before hydration to prevent a flash of wrong color scheme.

**Color themes (5):** `gold` (default) | `emerald` | `sapphire` | `rose` | `slate`. Stored in `localStorage` key `eb.color`. Applied as `[data-color="<name>"]` on `<html>`; Tailwind CSS custom properties per-theme control the accent palette. Color swatches are in **Settings → Appearance**.

**CSS implementation:** `globals.css` uses `[data-theme="dark"]` selectors to invert backgrounds and text; no `dark:` Tailwind prefix is used so the theme applies to both JS-rendered and server-rendered markup consistently.

### 14.8 Internationalisation (v2.7)

`src/i18n/config.ts` — `react-i18next` + `i18next` initialised client-side only (no SSR restructure). `I18nextProvider` wraps the dashboard layout.

`src/context/LocaleContext.tsx` — provides `{locale, setLocale}`. Switching locale calls `i18next.changeLanguage(code)`, updates `localStorage` (`eb.lang`), and PATCHes `app_language` to `/api/settings` so the preference persists server-side.

**Supported languages:**

| Code | Name | Script | Direction |
|------|------|--------|-----------|
| `en` | English | Latin | LTR |
| `ur` | Urdu (اردو) | Noto Nastaliq Urdu | RTL — `<html dir="rtl">` applied automatically |
| `zh` | Chinese (中文) | Simplified Han | LTR |

**Translation keys:** 314 keys across 10 namespaces — `nav.*`, `section.*`, `common.*`, `status.*`, `dashboard.*`, `hub.*`, `auth.*`, `settings.*`, `col.*`, `page.*`. Translation files live in `src/i18n/locales/{en,ur,zh}/`. 134 pages and components are translated.

**RTL support:** when `locale === "ur"`, the layout sets `document.dir = "rtl"` and loads Noto Nastaliq Urdu from `next/font/google`.

### 14.9 Mobile Responsiveness (v2.7)

All 54 authenticated pages were updated to apply responsive Tailwind breakpoints:

| Element | Before | After |
|---------|--------|-------|
| Page titles | `text-3xl` | `text-xl sm:text-3xl` |
| Stats grids | `grid-cols-3` / `grid-cols-4` | `grid-cols-2 sm:grid-cols-3` / `sm:grid-cols-4` |
| Aging grids | `grid-cols-2 md:grid-cols-5` | `grid-cols-2 sm:grid-cols-3 md:grid-cols-5` |
| Form grids | 2–3 col fixed | stack on phones via `sm:grid-cols-2` |
| Button toolbars | fixed row | `flex-wrap` so buttons wrap on narrow screens |
| Line-item tables | overflow clips | `overflow-x-auto` + `min-w-[640px]` on the inner table |
| Sidebar | 220 px | 196 px (more compact) |

61 files updated; 0 TypeScript errors introduced.

---

## 15. MIGRATIONS

| Revision | Tracks | Added |
|---|---|---|
| `0001_baseline` | core | 22 baseline tables |
| `0002_user_role` | P2 | `User.role` + CHECK |
| `0003_p3_tax_alloc_recurring` | P3 | TaxCode, PaymentAllocation, RecurringTemplate |
| `0004_idempotency_keys` | P4 | IdempotencyKey |
| `0005_multi_currency` | P5 | Tenant.base_currency, Invoice/Bill currency+exchange_rate, ExchangeRate |
| `0006_bank_imports` | P6 | BankStatementImport, StatementLine |
| `0007_account_balance` | P7 | AccountBalance |
| `0008_sequence_counter` | B | SequenceCounter (backfills `max+1` per tenant) |
| `0009_login_attempts` | C | LoginAttempt |
| `0010_business_model` | V2.1 | Tenant.business_model + enabled_modules; Account.is_memo |
| `0011_stock_locations` | V2.2 | StockLocation, StockMovement; InventoryLayer.location_id/owner_customer_id/lot_no; seeds MAIN per tenant + GODOWN/WIP for manufacturing |
| `0012_bom_rate_plans` | V2.3 | BomHeader, BomLine, RatePlan, CustomerRatePlan |
| `0013_grn_production_order` | V2.4 | GoodsReceiptNote, GRNLine, ProductionOrder (with state-machine CHECK) |
| Various (named) | G-02…G-16 | CreditNote, FixedAsset, PurchaseOrder, AnalyticAccount, DeferredRevenueSchedule, Tenant.cost_method, Budget, Invoice.payment_link_url, DebitNote, CustomerAdvance, VendorAdvance |
| `0020_user_rights` | #70 | `UserPermission` (tenant/user/resource/access_level/my_data_only); `User.created_by_id`; `User.my_data_only` |
| `0021_commissions` | #71 | `CommissionPlan`, `CommissionLedger` |
| `0022_promo_rules` | #72 | `PromoRule`, `InvoiceLine.discount_pct`, `InvoiceLine.promo_rule_id` |

---

## 16. ENGINEERING INVARIANTS

These are the rules that **must not** be violated. Tests fail if they are.

1. **Σdr = Σcr** for every Transaction, by exact Decimal equality. Never use `abs(diff) < 0.01`.
2. **Single-sided rule** — no JournalEntry has both `debit > 0` and `credit > 0`. DB CHECK enforces.
3. **Stock qty ≥ 0** — `consume_stock` refuses to over-issue. Manufacturing's `start_po` re-checks per line.
4. **`Account.is_memo = True`** for `1210` and `2150`. Auto-resolution paths force this flag.
5. **Period lock** — every write goes through `_check_period_locked`.
6. **Tenant ownership of accounts** — every JV double-checks that referenced account IDs belong to caller's tenant.
7. **Atomic numbering** — invoice/bill/grn/po numbers come from `SequenceCounter` with `SELECT FOR UPDATE`.
8. **BoM/RatePlan versioning** — POSTing a new version deactivates priors; PUT edits in place but versioning is the documented escape hatch.
9. **PO state machine** — transitions are strictly ordered; skipping returns 400.
10. **Customer goods off-balance-sheet** — owner_customer_id-tagged layers, unit_cost=0, memo accounts only.

---

## 17. TESTING

- **404 backend tests** (pytest). Cover: posting invariants, RBAC, multi-tenant isolation, multi-currency math, FX inverse fallback, period close, payment allocations, idempotency, CSRF, login throttle, sequence counters, stock locations + movements, BoM versioning, RatePlan + assignment, GRN custodial flow, PO full lifecycle, manufacturing reports, user rights/permissions, commissions, promo rules, customer/vendor statement balance arithmetic.
- **Frontend type-check:** `cd frontend && npx tsc --noEmit` is the canonical type gate.
- **E2E:** Playwright is on roadmap.

Run:
```bash
cd backend && PYTHONPATH=. uv run pytest         # full suite
cd backend && PYTHONPATH=. uv run pytest -k bom  # specific
cd frontend && npx tsc --noEmit                  # type-check
```

---

## 18. DEPLOYMENT

See [`DEPLOYMENT.md`](./DEPLOYMENT.md). Quick form:

- Backend → Vercel serverless function (or any ASGI host).
- Frontend → Vercel static + edge functions.
- DB → Vercel Postgres / Neon / Supabase.
- Env vars to set in production: `DATABASE_URL`, `JWT_SECRET_KEY`, `APP_ENV=production`, `FRONTEND_ORIGIN`, `NEXT_PUBLIC_API_URL`.

---

## 18.1. DEMO DATA & SEEDING

**Automatic Demo Tenants (on first run):**
- On database init (`db.py`), five demo tenants are auto-created, one per business model. `dev.sh` seeds each with 50+ records per entity type:
  - `demo.simple@easy-books.app` (Simple model)
  - `demo.services@easy-books.app` (Services model)
  - `demo.trader@easy-books.app` (Trader model)
  - `demo.manufacturing@easy-books.app` (Manufacturing model)
  - All use password: `demo1234`
- Each demo tenant has a Chart of Accounts, sequence counters, and stock locations pre-seeded.

**Rich Mock Data Population:**
- Run `scripts/seed_demo.py` to populate demo tenants with realistic transactional data:
  ```bash
  cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
  ```
- Each demo tenant receives:
  - 25 Customers + 25 Vendors with full contact details
  - 100 Invoices + 100 Bills spread across the past 365 days (never future-dated)
  - 70 Payments Received + 70 Bill Payments with multi-invoice allocations
  - 3 Bank Accounts (Current, Savings, Payroll) with reconciliation-ready balances
  - 4 Payment Terms (Due on Receipt, Net 15, Net 30, Net 60)
  - 6 Recurring Templates across all frequencies (daily → yearly)
  - 60+ Manual Journal Entries cycling through every COA account
  - Manufacturing-specific: 12 BOMs, 12 Rate Plans, 12 GRNs, 12 Production Orders (manufacturing tenant only)
- Script is **idempotent**: re-running it will reuse existing demo tenants and skip entities already present.

**Use cases:**
- QA / regression testing: fresh dataset with known state.
- Live demo: customers can log in to a pre-loaded, fully-populated business.
- Onboarding: new users see realistic data structures before entering their own.

---

## 19. OPEN ITEMS & ROADMAP

### Sprint 1–6 Shipped ✅

| Sprint | Feature | Status |
|--------|---------|--------|
| 1.2 | Multi-invoice payment allocation UI (AR/AP linking) | ✅ Shipped |
| 1.4 | Dashboard cash tile + AP-due-this-week tile | ✅ Shipped |
| 1.5 | Column sorting + advanced filters on list pages | ✅ Shipped |
| 1.6 | Overdue invoice/bill auto-flag on list fetch | ✅ Shipped |
| 2.1 | Inline notes + internal memo on invoices/bills | ✅ Shipped |
| 2.2 | Company logo upload + address in Settings | ✅ Shipped |
| 2.3 | Payment terms (Net 30 etc.) + auto due-date | ✅ Shipped |
| 3.1 | Bulk actions (mark-sent, void, delete) on list pages | ✅ Shipped |
| 3.2 | Recurring journal template UI | ✅ Shipped |
| 3.3 | Low-stock filter link from dashboard | ✅ Shipped |
| 3.4 | Customer + Vendor Statement pages | ✅ Shipped |
| 5.1 | Onboarding checklist on dashboard | ✅ Shipped |
| 5.2 | Audit log tabs (Timeline / By User / Export CSV) | ✅ Shipped |
| 5.3 | Document number format with `{YYYY}` / `{MM}` tokens | ✅ Shipped |
| 6.1 | Browser tab `<title>` via pathname mapping | ✅ Shipped |
| 6.2 | Empty-state CTAs with icon + button on all list pages | ✅ Shipped |
| 6.3 | Breadcrumb nav on all detail pages | ✅ Shipped |
| 6.4 | Keyboard shortcut `N` for New on all list pages | ✅ Shipped |
| Seed | Demo data upgrade: 100 invoices, 100 bills, full-year spread | ✅ Shipped |

### Sprint 7–12 Shipped ✅ (Improvement Roadmap — IAS/IFRS + product parity)

| Gap | Feature | Standard | Backend | Frontend |
|-----|---------|----------|---------|----------|
| G-01 | Bank reconciliation **zero-difference** enforcement on close | IAS 7.48 | `routers/reconciliations.py` | recon page |
| G-02 | **Credit Notes** (`CN-` sequence; Dr Revenue / Cr AR) | ISA 240 | `routers/credit_notes.py` | `/credit-notes` |
| G-03 | **Comparative period** columns on P&L + Balance Sheet | IAS 1.38 | `routers/reports.py` | `/pl`, `/balance` |
| G-04 | **Multi-currency** wired to invoice/bill forms + `useFmt()` | IAS 21.21 | (already present) | invoices, bills, all pages |
| G-05 | **Fixed Assets** register + straight-line / reducing-balance depreciation | IAS 16 | `routers/assets.py`, `services/depreciation.py` | `/assets` |
| G-06 | **Purchase Orders** with approve + convert-to-bill | IAS 2.11 | `routers/purchase_orders.py` | (guide/workflow) |
| G-07 | **Analytic accounts** (cost-center/project P&L) | IAS 1 | `routers/analytic_accounts.py` | (guide/workflow) |
| G-08 | **Deferred revenue** recognition schedule | IFRS 15.31 | `routers/deferred_revenue.py` | (services model) |
| G-09 | **FIFO** inventory cost flow (tenant-level) | IAS 2.25 | `services/inventory.py` | Settings toggle |
| G-10 | **Budget vs Actual** variance report | IAS 1 | `routers/budgets.py` | (guide/workflow) |
| G-12 | **Stripe** Checkout payment links + webhook | — | `routers/invoices.py`, `main.py` | invoice detail |
| G-13 | **Alembic** migrations adopted (replaces ad-hoc `create_all`) | — | `alembic/versions/` (0014–0019) | — |
| G-14 | **Server-side PDF** (WeasyPrint + Jinja2) | — | `services/pdf.py`, `templates/invoice.html` | invoice detail |
| G-15 | **FX revaluation** at period end (unrealised gain/loss → `4901`) | IAS 21.23 | `routers/reports.py` | — |
| G-16 | **Email** notifications (SMTP) — invoice send + team invite | — | `services/email.py` | — |

### Sprint 13 Shipped ✅ (Returns & Advances)

| Feature | Standard | Backend | Frontend | GL |
|---------|----------|---------|----------|----|
| **Sales Return** (enhanced Credit Note: restock + COGS reversal + GST output) | IAS 2 / ISA 240 | `routers/credit_notes.py`, `services/inventory.py::reverse_consumption` | `/credit-notes` | Dr Revenue (+Dr GST) / Cr AR · Dr Inventory / Cr COGS |
| **Purchase Return** (Debit Note, bill-linked, original cost) | IAS 2.11 | `routers/debit_notes.py`, `services/inventory.py::return_to_vendor` | `/debit-notes` | Dr AP / Cr Inventory (+ Cr GST Input) |
| **Advance from Customer** (record + apply) | — | `routers/advances.py` | `/advances` | Dr Bank / Cr 2310 → apply Dr 2310 / Cr AR |
| **Advance to Vendor** (record + apply) | — | `routers/advances.py` | `/advances` | Dr 1260 / Cr Bank → apply Dr AP / Cr 1260 |

New common-CoA accounts: **1260** Advances to Vendors (Asset), **2310** Customer Advances (Liability).
New tables: `DebitNote`, `DebitNoteLine`, `CustomerAdvance`, `VendorAdvance` (Alembic 0020). Advances
apply through the existing `PaymentReceived`/`BillPayment` + `PaymentAllocation` path so invoice/bill
status derives automatically.

New common-CoA accounts (Sprint 7–12): **1090** Accumulated Depreciation (contra-asset), **4901** Unrealised FX Gain/Loss.
Tenant gains a **`cost_method`** field (`wavg`/`fifo`). The **guide and workflow pages are now
tenant-model-aware** — each business model sees only the sections relevant to its features.

### Sprint 14 Shipped ✅ (Drill-down links + Periodic Closing)

- **Period Close modes** — `POST /api/periods/{id}/close?mode=soft|year_end`. `soft` locks + snapshots `AccountBalance` (P&L not zeroed — for monthly/quarterly); `year_end` posts the P&L→Retained-Earnings closing JV then locks (IAS 1). `GET /api/periods/{id}/close-preview` returns net income before posting. New **Period Close** page (Reports) with Monthly/Quarterly/Yearly presets. Balance-sheet accounts carry forward via live-from-GL continuity (no opening JV).
- **Drill-down links** — `DocLink` gains `credit_note` / `debit_note` / `fixed_asset` kinds. New detail pages: `assets/[id]` (Fixed Assets Register with depreciation schedule), `debit-notes/[id]`, `credit-notes/[id]`. Account rows on P&L / Balance Sheet / Cash Flow / Bank Accounts / Telecom tiles / Recurring lines now link to the General Ledger (ISA 230/315).
- **Seeding fix** — `_ensure_coa()` convergently adds missing common-backbone accounts to existing demo tenants, so customer/vendor advances (and assets/FX) seed correctly on re-run.

### Sprint 15–16 Shipped ✅ (Dashboard Customization Arc)

#### Sprint 15 — Per-user customizable dashboard (#52 §3)

**Phase 1 — Reorder / show-hide (per-user layout)**

| Item | Detail |
|---|---|
| Backend | New KV table `UserDashboardLayout` (`tenant_id`, `user_id`, layout JSON — opaque store). `GET`/`PUT /api/dashboard/layout` endpoints. |
| Widget registry | `lib/dashboardWidgets.tsx` — 11 widget definitions, each carrying `id`, `title`, `render`, `pinned`, `defaultOnGrid`, `defaultSize`, `minSize`. |
| Hook | `useDashboardLayout` — loads/persists layout, drives show/hide + reorder via `@dnd-kit` sortable. |

**Phase 2 — Resizable 2-D grid + shortcut tiles**

| Item | Detail |
|---|---|
| Grid library | Replaced `@dnd-kit` with `react-grid-layout` v2. **Import via `'react-grid-layout/legacy'`** (v2 API, self-typed; do NOT install `@types/react-grid-layout` — incompatible with v2 and React 19). |
| Layout schema | v2: `{version:2, items:[{id,x,y,w,h}]}`. 4-col desktop grid, `rowHeight=96`. |
| Migration | `resolveLayout` handles v1→v2 migration client-side; opaque JSON store means no backend change. |
| Shortcut tiles | Any NAV item (model/role-filtered) added as `shortcut:<href>` widget via `AddWidgetPanel`. |
| Pinned widgets | Onboarding checklist + Alert banner float above the grid (not in layout). |
| New files | `lib/dashboardShortcuts.ts`, `components/dashboard/{DashboardGrid,ShortcutTile,AddWidgetPanel}.tsx`. Removed: `DashboardCanvas.tsx`, `CustomizeBar.tsx`. |

#### Sprint 15 — B1 Smart Tile Metrics

Live metric badges on shortcut tiles — no new backend endpoints.

- `lib/dashboardTileMetrics.ts` — `resolveTileMetric(href)`: 7-route map (invoices, bills, products, customers, vendors, assets, bank-accounts → count/total from summary APIs).
- `ShortcutTile` gains optional `metric` prop (value + tone badge: `success`/`warning`/`neutral`).
- `DashboardGrid.renderItem` wires the resolver automatically.

#### Sprint 15 — B2 Data Widgets (opt-in)

Three self-fetching widgets, `defaultOnGrid:false` (hidden by default; discoverable via Add panel):

| Widget | Data source |
|---|---|
| **Bank Balances** | `GET /api/bank-accounts` — balance per account |
| **Top Products** | `GET /api/reports/inventory-performance` — top 5 by revenue |
| **Inventory Summary** | `GET /api/reports/inventory-performance` — total value/qty |

New `WidgetDef.defaultOnGrid: boolean` field gates Add-panel discoverability. Helper: `lib/inventorySummary.ts`.

#### Sprint 15 — B3 Cash-Flow Reconciliation Tie-out

- New `unclassified` field on `/api/reports/cash-flow`: `unclassified = (ending_balance − beginning_balance) − net_cash_change` (IAS 7 reconciling amount for unbucketed GL movements).
- Frontend: reconciling row below the cash-flow statement; green ✓ badge when `unclassified = 0`, amber badge when not.
- 3 new backend tests; suite at 372.

#### Sprint 16 — B4 Per-Breakpoint Dashboard Layouts

| Item | Detail |
|---|---|
| Layout schema | v3: `{version:3, layouts:{lg: GridItem[], sm?: GridItem[], xs?: GridItem[]}}`. |
| Sparse overrides | `lg` is canonical (defines widget membership); `sm`/`xs` only exist after a real user gesture at that width. `markCustomized(bp)` is called only from `onDragStop`/`onResizeStop`. |
| Columns | `BP_COLS = {lg:4, sm:2, xs:1}`. `validateBreakpoint` enforces shared-membership invariant + per-col width clamping. |
| Migration chain | `resolveLayout`: v3→validate, v2→`{lg:items}`, v1→migrate+wrap, garbage→`{lg:defaultGrid()}`. |
| Toolbar | Active breakpoint label ("Desktop / Tablet / Phone layout"); "Reset all" clears all overrides. Backend unchanged. |

### Sprint 17 Shipped ✅ (User Rights, Commissions, Promo Discounts, Statements)

| Feature | Status | Notes |
|---------|--------|-------|
| **User Rights** (#70) — granular per-resource access control | ✅ | `UserPermission`, `perm_dep()` injected into 35 routers, 60-resource registry, `my_data_only` filter, admin matrix UI, 12 tests |
| **Sales Commissions** (#71) — plan + compute + post GL | ✅ | `CommissionPlan`, `CommissionLedger`, compute endpoint, approve/post flow, `/commissions` page |
| **Promotional Discounts** (#72) — promo rules + Apply Promos button | ✅ | `PromoRule`, `InvoiceLine.discount_pct`, `/api/promo-rules/check`, "Apply Promos" in InvoiceForm, `/promo-discounts` page |
| **Customer & Vendor Statements** (#77 P2) | ✅ | `GET /api/customers/{id}/statement`, `GET /api/vendors/{id}/statement`; date-aware opening balance; 4 tests |

### Sprint 18 Shipped ✅ (Section Hubs, Sidebar, 3-mode Form, Print System)

| Feature | Notes |
|---------|-------|
| **Section Hub Pages** | `/receivable`, `/payable`, `/inventory`, `/banking` — generic `HubPage` renderer driven by `hubConfigs`; band components `AgingBand`, `LowStockBand`, `AccountListBand`; sidebar section headers navigate to hub; `TITLE_MAP` in `(dashboard)/layout.tsx` |
| **Collapsible sidebar** | 3-state (collapsed / open / pinned) via `localStorage`; hover expands with tooltip nav panel; auto-pin on wide screens; backdrop excludes `top-12` header; z-index layering corrected |
| **3-mode voucher form** | New Entry supports Journal / Payment (CP/BP) / Receipt (CR/BR); mode-specific Cash/Bank GL pickers; JV prefix auto-applies per mode; distinct PV/RV print templates |
| **Print system overhaul** | Dot-matrix B&W format; `dd-mm-yy` date format via `fmtDate()`/`fmtDateJs()` across 37+ files; dynamic `@page { size: A4 landscape }` injection in `PrintHeader` via `useEffect`; print hygiene (filter UI, pagination, sort, action cols, checkboxes all `print:hidden`); currency prefix in column headers only; negative amounts as `(1,234.56)`; `whitespace-nowrap` on Date/JV# cells; voucher type badges removed |

### Still Pending

**Manufacturing track (V2 follow-ups)**
- Production-order **reversal helper** (currently requires manual JE reversal).
- **Overhead / labour absorption** at PO start.
- **Partial delivery** endpoint (currently one delivery = full output_qty).
- **Damage / scrap** endpoint for inventory write-off.
- **Multi-output BoMs** (joint-product manufacturing).
- **By-product handling** with separate cost allocation.

**Core platform**
- **Multi-currency on payments** (currently invoice currency is snapshot at issue; payments assumed in base currency).
- **Daily overdue sweep cron** (`Invoice.status = 'overdue'` is written on each list fetch but not via a scheduled task).
- **E2E tests** (Playwright) — login, signup wizard, full PO lifecycle in the UI.
- **Payroll module** (IAS 19) — currently manual JV only.
- **Overdue email reminders** — `services/email.py` exists; automated aging reminders not yet wired.

**Developer ergonomics**
- **Storybook** for guidance components + form patterns.

---

> **Document maintenance.** Every shipped commit that adds or removes a model, endpoint, or invariant should update this blueprint *and* `WORKFLOW.md`. Keep `README.md` light (the elevator pitch); push detail down here.
