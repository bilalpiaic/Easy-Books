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
> **Last updated:** 2026-09-06 · **Branch:** `main`

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
10B. [PRA e-Invoice Track (Pakistan)](#10b-pra-e-invoice-track-pakistan)
10C. [Healthcare / Hospital Track (V4)](#10c-healthcare--hospital-track-v4)
10D. [Yarn Spinning Track](#10d-yarn-spinning-track)
10E. [Marketplace, Studio & Weighbridge](#10e-marketplace-studio--weighbridge)
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
| DB (dev) | **SQLite** | Zero-setup local dev; `SCHEMA_BOOTSTRAP=create_all` still boots a fresh file, then Alembic is the schema source of truth |
| DB (prod) | **PostgreSQL** | Row-level locks (`SELECT FOR UPDATE`) for atomic numbering and avg-cost updates |
| Migrations | **Alembic** | `backend/alembic/versions/`; installers run `alembic upgrade head` on launch. New tables need `has_table` guards (coexist with `create_all()`). SQLite cannot `ADD CONSTRAINT` — strip auto-generated FK lines on ALTER |
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
        │       ├── apps/                    Module store (install/uninstall; admin only)
        │       └── onboarding/              First-run module selection (no sidebar)
        ├── components/
        │   ├── Sidebar.tsx                  adaptive; filters NAV by installedModules (forModule gate)
        │   ├── OnboardingGuard.tsx          redirects fresh accounts to /onboarding
        │   ├── BusinessModelPicker.tsx      signup wizard step 1
        │   ├── guidance/                    HelpCallout, FieldHint, EmptyStateGuide
        │   └── …                            Header, modals, charts, CsvImportButton, …
        ├── context/
        │   ├── SettingsContext.tsx          currency + company-name from /api/settings
        │   └── ModuleContext.tsx            installedModules Set + install/uninstall/refresh
        └── lib/
            ├── api.ts                       apiFetch (auto Authorization header)
            ├── auth.ts                      token storage, isAuthenticated
            ├── nav.ts                       NAV array; forModule field gates sidebar items
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
| `tenant` | `name`, `base_currency`, **`business_model`** (`simple/services/trader/manufacturing/telecom_franchise/pra_einvoice` CHECK), `enabled_modules` (JSON array of module IDs — see §6), **`module_meta`** (JSON dict: `{module_id: {tier, installed_at, expires_at}}` — billing metadata), `created_at` |
| `user` | `email` (unique), `hashed_password` (bcrypt), `full_name`, `phone`, `avatar_url`, `is_active`, `must_change_password`, `role` (`owner/admin/accountant/viewer` CHECK), `tenant_id`, **`created_by_id?`** (set on create), `created_at`, `last_login_at` |
| `userinvite` | Pending tenant invite — `email`, `role` (CHECK), `token` (unique), `invited_by_id`, `expires_at`, `accepted_at`. Consumed by `POST /api/auth/accept-invite` |
| `userpermission` | Granular access override — `(tenant_id, user_id, resource_key)` unique; `access_level` (`none/view/edit`); `my_data_only` bool. Sparse — only rows with non-default access exist; missing row = role default. Module-gated by `settings.user_rights_enabled` |
| `settings` | KV per tenant — `company_name`, fiscal year, number prefixes, **`user_rights_enabled`** (module toggle for granular permissions) |
| `account` | `code`, `name`, `type` (`Asset/Liability/Equity/Revenue/Expense` CHECK), **`parent_id` + `is_group`** (V2.4/V2.5 — multi-level hierarchy; the default CoA is now hierarchical and posting is restricted to active **leaf** accounts, parent balances roll up), `is_active`, **`is_memo`** (V2.1 — excludes from formal A=L+E totals) |
| `deferredrevenueschedule` | IFRS 15 — `invoice_id`, `total_amount`, `recognised_amount`, `start_date`, `end_date`, `frequency`, `next_recognition_date`, `status`, `deferred_revenue_account_id`, `revenue_account_id`. Originated by `create_invoice` for `is_deferred` product lines; released by the recognition run |
| `revenueallocationaudit` / `contractasset` | IFRS 15 remaining (#259) — relative-SSP allocation audit + unbilled contract assets (1140); `GET /api/reports/contract-balances` |
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

### 5.8 Healthcare Data Model

**Migrations:** `0027_healthcare` (19 `hc_*` tables) + `0028_tenant_hospital_model` (adds `'hospital'` to the `business_model` CHECK).

```
HcPatient
  - tenant_id, mr_number (MR-YYYYNNNN auto), customer_id → Customer (auto-linked on create)
  - name, dob, gender, blood_group, phone, address, notes

HcDoctor
  - tenant_id, name, specialization, phone, email, is_active

HcWard
  - tenant_id, name, ward_type (general|private|icu|maternity), capacity

HcBed
  - ward_id → HcWard, bed_number
  - status: available | occupied | maintenance   (state machine via PUT /beds/{id})

HcProcedureCatalog
  - tenant_id, code, name, procedure_type, base_rate, revenue_account_id

HcOpdToken
  - tenant_id, token_number (OPD-YYYYNNNN), patient_id → HcPatient, doctor_id → HcDoctor
  - visit_date, queue_number, status (waiting|in_progress|completed|cancelled)
  - fee, transaction_id (set on fee posting)

HcOpdVisit
  - opd_token_id → HcOpdToken; chief_complaint, diagnosis, notes, vital_signs (JSON)

HcPrescription
  - opd_visit_id → HcOpdVisit; notes
HcPrescriptionItem
  - prescription_id → HcPrescription; drug_name, dosage, frequency, duration, instructions

HcAdmission
  - tenant_id, admission_number (ADM-YYYYNNNN), patient_id, ward_id, bed_id, admitting_doctor_id
  - admission_date, discharge_date?, diagnosis, deposit_amount, deposit_transaction_id
  - discharge_invoice_id (Invoice FK — set at discharge), status (admitted|discharged)

HcAdmissionCharge
  - admission_id → HcAdmission; charge_date, description, amount, charge_type
  - (charges accumulate; no per-charge GL post — one consolidated invoice at discharge)

HcLabTest
  - tenant_id, code, name, category, sample_type, normal_range, unit, turnaround_hours, rate

HcLabOrder (LO-YYYYNNNN)
  - tenant_id, order_number, patient_id, requesting_doctor_id, order_date
  - status (pending|collected|resulted|delivered), transaction_id (set on billing)

HcLabOrderItem
  - lab_order_id → HcLabOrder, lab_test_id → HcLabTest; result_value, result_notes, is_abnormal

HcSampleCollection
  - lab_order_id → HcLabOrder; collected_at, collected_by, sample_notes

HcProcedureOrder
  - tenant_id, patient_id, doctor_id, procedure_id → HcProcedureCatalog
  - scheduled_at, performed_at?, status, notes, transaction_id (set on posting)

HcStoreIssue / HcStoreIssueItem
  - Pharmacy / store dispense linked to a patient; product_id → Product; qty, unit_cost

HcProcedureConsumable
  - procedure_order_id → HcProcedureOrder; product_id → Product; qty
```

**Healthcare GL postings** (all route through `services/healthcare_posting.py`):

```
OPD visit fee:
  Dr 1100 AR         / Cr 4100 OPD Revenue

IPD deposit received:
  Dr 1000 Cash/Bank  / Cr 2350 Patient Deposit Liability

IPD discharge (consolidated invoice):
  Dr 1100 AR         / Cr 4110 IPD Ward Revenue
  Dr 1100 AR         / Cr 4112 Nursing/Misc Charges
  Dr 2350 Patient Deposit / Cr AR  (settle deposit)

Lab order billing:
  Dr 1100 AR         / Cr 4115 Lab Revenue

Procedure billing:
  Dr 1100 AR         / Cr 4120 Procedure Revenue

Pharmacy dispense:
  Dr 5010 COGS       / Cr 1200 Drug/Supply Inventory  (via consume_stock)
```

---

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

### 6.1 Business Model (CoA template)

`Tenant.business_model` is set once at signup and seeds the Chart of Accounts. It is **structural and irreversible** — switching later adds accounts but never removes them.

| Model | Use case | Extras |
|---|---|---|
| `simple` | Solo / micro-business | Just the universal CoA backbone |
| `services` | Service firms (consulting, agencies) | + Consulting Revenue, Recurring Service Revenue, Deferred Revenue, Subcontractor Costs |
| `trader` | Goods buy-resell | + Finished Goods Inventory, COGS, Freight In, Storage, Inventory Adjustments, GST Receivable |
| `manufacturing` | Value-addition / contract mfg | + RM/WIP/FG inventory, Customer Goods on Hand (memo 1210), Customer Goods Liability (memo 2150), Direct Labour, Manufacturing Overhead, Indirect Materials, Service Revenue (Value-Add) |
| `telecom_franchise` | Mobile-operator franchise | + 56-account franchise CoA: Tracker Deposit `1210`, Load Float `1211`, RSO/Retail load receivables `1212/1213`, MM float `1214`, SIM/IMSI/device inventory `1200–1204`, Commission Receivable `1110`, Franchise Intangible `1300`; Operator Payable `2010`, MM Float Liability `2100`, Postpaid Collections Payable `2110`, Royalty Payable `2120`; revenue `4000–4061` (3% load uplift `4020`, FCA target `4060`); fee amortisation `5030`, royalty `5040`, variance `5070`, penalty `5090`. See WORKFLOW §4.8 |
| `pra_einvoice` | Pakistani retail (PRA-registered) | Same CoA as `simple`; PRA module pre-installed |
| `hospital` | Healthcare / Hospital | + Hospital CoA: `1100` AR, `2350` Patient Deposit Liability; revenue `4100` OPD / `4110` IPD Ward / `4112` Nursing / `4115` Lab / `4120` Procedures / `4121` Pharmacy; `5010` COGS (drug/supply inventory). Healthcare module pre-installed |
| `yarn_spinning` | Yarn spinning mill | + Spinning CoA: `1200` Raw Cotton / `1201`–`1203` WIP stages / `1204` Finished Yarn / `5901`–`5904` waste / `5100` Direct Labour / `5200` Overhead / `5010` COGS. Spinning module pre-installed with `purchase_store` |

### 6.2 Module System (UI visibility & billing)

`Tenant.enabled_modules` is a JSON list of module IDs. Derived from `business_model` at signup via `MODULES_BY_MODEL`, but managed independently afterward via `GET/POST /api/modules`. This is **orthogonal to business_model** — the CoA is seeded once; modules control what the UI shows.

**`MODULE_REGISTRY`** (defined in `backend/db.py`):

| Module ID | Label | Category | Deps | Always | Gates |
|---|---|---|---|---|---|
| `base` | Base Accounting | Core | — | ✓ | Overview, Ledger, Receivable, Payable, Banking, Reports |
| `inventory` | Inventory | Operations | base | — | Inventory section |
| `production` | Manufacturing | Operations | inventory | — | Manufacturing section |
| `hrm` | HRM & Payroll | HR | base | — | Payroll section |
| `telecom` | Telecom Franchise | Industry | inventory | — | Telecom section |
| `pra` | PRA e-Invoice | Industry | base | — | PRA Logs in System section |
| `healthcare` | Healthcare | Industry | base | — | Healthcare section (OPD/IPD/Lab/Procedures/Store/Reports) |
| `ai_assistant` | AI Financial Assistant | Intelligence | base | — | Chat FAB + full-page `/agent` route + `POST /api/ai/chat` (no sidebar section) |
| `purchase_store` | Purchases & Store | Operations | inventory | — | Purchases section (Demands, Comparatives, Gate Inward, dual-homed PO/GRN, reports) + Store section (Gate Outward, reports) |
| `weaving` | Weaving | Industry | inventory | — | Weaving section (contracts, yarn inward, sizing, production, dispatch — memo/ops only) |
| `spinning` | Yarn Spinning | Industry | inventory, purchase_store | — | Spinning section (setup, plans, lots, bale receipt, stages, cone output, waste, dispatch, reports, calculators) |

**`MODULES_BY_MODEL`** (default module set assigned at signup):

```python
"simple":            ["base"]
"services":          ["base"]
"trader":            ["base", "inventory"]
"manufacturing":     ["base", "inventory", "production", "purchase_store"]
"telecom_franchise": ["base", "inventory", "telecom"]
"pra_einvoice":      ["base", "pra"]
"hospital":          ["base", "hrm", "inventory", "healthcare"]
"yarn_spinning":     ["base", "inventory", "purchase_store", "spinning"]
```

**Module rules:**
- `base` is always locked — it cannot be uninstalled.
- Installing a module auto-installs all transitive deps.
- Uninstalling is blocked if any installed module depends on the target.
- Only `admin` and `owner` roles may install or uninstall.
- `module_meta` stores `{tier, installed_at, expires_at}` per module — reserved for future SaaS per-module billing.

**Sidebar filtering:** `NAV` items carry a `forModule?: string` field. The `Sidebar` component reads `installedModules` from `ModuleContext` and hides any item whose `forModule` is not in the installed set.

### 6.3 Onboarding Flow

Fresh accounts (only `base` installed, `module_meta == {}`) are routed through `/onboarding` immediately after login:

```
POST /api/auth/login
  → onboarding_required: true   (backend flag when only base installed & module_meta empty)
  → login page redirects to /onboarding

/onboarding (standalone — no sidebar, no header)
  → user selects optional modules
  → POST /api/modules/{id}/install for each selection
  → sets localStorage["eb.onboarded.<email>"] = "1"
  → redirects to /dashboard

OnboardingGuard (inside ModuleProvider in DashboardLayout)
  → safety-net: redirects to /onboarding if user navigates directly to /dashboard
     without the localStorage flag and only base is installed
```

Demo tenants are unaffected — their `enabled_modules` is already populated, so `onboarding_required` is always `false`.

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

### Modules (`/api/modules`)
- `GET /` — list all modules in `MODULE_REGISTRY` with `installed: bool`, `installed_at`, `expires_at` for the current tenant. Stable category order: Core → Accounting → Operations → HR → Industry.
- `POST /{module_id}/install` — install a module. Resolves transitive deps and installs them first. Sets `module_meta[id].installed_at` + `tier`. Returns `{enabled_modules, installed, message}`. Admin/owner only.
- `POST /{module_id}/uninstall` — remove a module. Blocked if `module.always == True` (base). Blocked if any installed module lists this one in its deps. Returns `{enabled_modules, uninstalled, message}`. Admin/owner only.

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
- `/dashboard/net-worth?months=N` **(v3.1)** — monthly time series `{series: [{month, assets, liabilities, net_worth}], as_of}`: one grouped query fetches per-month debit/credit deltas by account type (Asset/Liability), cumulative sums produce month-end balances with gap months carried forward; `months` clamped 1–60 (default 36); tenant-scoped; empty series for fresh tenants. Powers the dashboard **Net Worth Trend** widget.
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

### Healthcare (`/api/healthcare`, `forModule: "healthcare"`)

| Method | Path | Notes |
|--------|------|-------|
| `GET/POST` | `/patients` | List (search, active filter) + create; MR-YYYYNNNN auto; auto-links to `Customer` row |
| `GET/PUT` | `/patients/{id}` | Detail + update |
| `GET` | `/patients/{id}/visits` | OPD visit history |
| `GET` | `/patients/{id}/admissions` | IPD admission history |
| `GET` | `/patients/{id}/lab-orders` | Lab order history |
| `GET/POST` | `/doctors` | Doctor list + create |
| `GET/POST` | `/wards` | Ward list + create |
| `GET` | `/beds` | All beds with status |
| `PUT` | `/beds/{id}` | Status machine: `available → occupied → available`; `maintenance` bypass |
| `GET/POST` | `/opd/tokens` | Token queue + create (posts `Dr 1100 / Cr 4100`) |
| `PUT` | `/opd/tokens/{id}` | Advance status (waiting→in_progress→completed) |
| `POST` | `/opd/tokens/{id}/visit` | Record OPD visit details + vitals |
| `POST` | `/opd/visits/{id}/prescription` | Create prescription |
| `GET/POST` | `/admissions` | IPD admission list + admit (deposit posts `Dr Cash / Cr 2350`) |
| `POST` | `/admissions/{id}/charges` | Add charge to running tab |
| `POST` | `/admissions/{id}/discharge` | Consolidated invoice for all charges + deposit settlement |
| `GET/POST` | `/lab/tests` | Lab test catalogue CRUD |
| `GET/POST` | `/lab/orders` | Lab order list + create (LO-YYYYNNNN) |
| `POST` | `/lab/orders/{id}/collect` | Record sample collection |
| `PUT` | `/lab/orders/{id}/items/{item_id}` | Enter result; sets `is_abnormal` flag |
| `POST` | `/lab/orders/{id}/deliver` | Mark delivered + bill (posts `Dr 1100 / Cr 4115`) |
| `GET/POST` | `/procedures` | Procedure catalogue CRUD |
| `POST` | `/procedure-orders` | Schedule procedure |
| `POST` | `/procedure-orders/{id}/perform` | Record performance + bill |
| `GET/POST` | `/store/issues` | Pharmacy/store dispense (calls `consume_stock`) |
| `GET` | `/store/pharmacy/dispense` | Pending pharmacy dispense queue |

### Healthcare Reports (`/api/healthcare/reports/`)

| Endpoint | Notes |
|----------|-------|
| `GET /dashboard` | KPI cards: today's OPD, occupied beds, pending labs, revenue MTD |
| `GET /opd-summary` | OPD visits by date range, doctor, status |
| `GET /doctor-collections` | Revenue collected per doctor |
| `GET /lab-summary` | Lab orders by status, turnaround time |
| `GET /ipd-census` | Active admissions, ward occupancy, average LOS |
| `GET /revenue-by-type` | GL accounts 4100–4121 breakdown |
| `GET /patient-statement/{id}` | Full financial statement for one patient |

### Admin (`/api/admin`)
- `POST /demo/seed` *(admin+)* — load all 8 demo tenants with full mock data. `DELETE /demo/seed` — remove demo data.

### AI Financial Assistant (`/api/ai`)

A 4-stage agentic pipeline (Sprint 31's 3-stage Triage→Specialist→Drafting, #171–#175; **Reviewer stage + full-spectrum agent/tool expansion in v3.8**, PRs #185–#188) on top of a multi-provider foundation (anthropic/openai/gemini/ollama, Sprint 28's #164) — superseding the original single-agent design this section used to describe.

- `POST /api/ai/chat` — body `{session_id, message, model?}`. **Async SSE endpoint** (`text/event-stream`, not a plain JSON response) running per turn: **Triage** (`_run_triage`, a one-shot non-streaming classification call on that provider's cheap/fast tier — `claude-haiku-4-5`/`gpt-4o-mini`/`gemini-flash-latest` — picking one specialist agent key from `services/ai_agents.AGENTS`, filtered to the tenant's installed modules; any failure falls back to `general` silently) → **Specialist** (`run_tool_loop()`, max 6 rounds, that agent's own narrow tool subset drawn from `services/ai_tools.TOOL_REGISTRY` — ~50 read-only tools whose executors call existing report functions directly, so tenant filters/business rules are reused, never re-implemented; its own text never streams to the client) → **Reviewer** (`_run_reviewer`, cheap-tier, non-streaming, no tools — a silent fact-check that verifies every figure in the specialist's analysis against the raw tool results and hands the corrected analysis to drafting; skipped when the turn ran no tools, falls back to the unreviewed text on any failure) → **Drafting** (`_run_drafting`, cheap-tier again, streaming, no tools, rewrites the reviewed findings + raw tool results into Markdown — this is the only text the user ever sees).
- **Agent roster (11):** base `receivables` / `payables` / `financial_reports` (statements incl. balance sheet, tax summary, budget vs actual, net worth) / `sales` (customer performance/statements) / `general` (original 7 tools + `run_custom_report` — the universal fallback), plus module-gated `inventory`, `payroll` (hrm), `healthcare`, `telecom`, `purchasing` (purchase_store), `manufacturing` (production) — offered to triage only when the module is installed. `find_*` lookup tools (customer/vendor/product/employee/patient/RSO) resolve names→ids for the ID-parameterized statement tools; `list_report_sources` + `run_custom_report` expose the report-builder engine's whitelisted sources (module-gated, 50-row cap) for ad-hoc questions no fixed tool answers.
- **Streamed SSE events:** `stage` (`{label}` — pipeline-progress text: "Routing your question…" / "`<Agent>` is looking into this…" / "Reviewing figures…" / "Drafting your report…"), `tool_start`/`tool_end` (specialist stage only), `token` (drafting stage only), `done` (`{session_id, message_id, reply}` — `reply` is the authoritative final text), `error` (mid-stream failure; provider's real error text, truncated to 300 chars, also printed server-side as `[ai_chat] ...`).
- **Sessions:** `GET/POST /api/ai/sessions`, `PATCH/DELETE /api/ai/sessions/{id}`, `GET /api/ai/sessions/{id}/messages` — server-side, per-user-private chat history (`AiChatSession`/`AiChatMessage`); a session auto-titles from its first message. `AiChatMessage.agent` (nullable) records which specialist handled each assistant reply.
- **Provider config:** `GET /api/ai/models` (configured providers + default model), `GET /api/ai/key-status` *(admin+)* — masked (`••••1234`) key tails, never raw values. Keys themselves are set via `PATCH /api/settings` (`ai_api_key_<provider>`, write-only) — reachable from **Settings → AI** or, closer to where it's needed, the **Model & API Key** button now built into the chat UI itself (#178) so a fresh install's chat panel always has a discoverable path to configuration instead of the model picker silently disappearing when nothing is set up yet.
- **Gates:** 403 when the tenant hasn't installed `ai_assistant`; 503 when no provider is configured at all; 400 for an unknown/misconfigured `model` or a message over 4,000 chars; 429 on the sliding-hour rate limit (`ai_rate_limit_per_hour`, default 20/hour, per-process in-memory, one decrement per user turn regardless of the pipeline's 4 internal model calls). History is trimmed server-side to the last 20 messages; a short 2-message tail of that also feeds Triage for topic-continuation routing.

### Purchase Chain (`/api/purchase-demands`, `/api/quotations`, `/api/comparatives`)

Odoo-style procurement control chain, gated by the `purchase_store` module (#137 Phase 1). Memo documents throughout — no GL posting until the resulting `PurchaseOrder`/`Bill` is processed through the existing PO/bill flow.

- **Purchase Demand** (`PD-YYYY-seq`) — `GET/POST /api/purchase-demands`, `GET/PUT /{id}`, `PATCH /{id}/approve|cancel|close`. Quantity-only lines (`product_id?`, `description`, `qty`, `unit`) — the requester never sets a rate; that segregation of duties is the control. `PATCH /approve` requires admin+ and rejects self-approval (`created_by_id == approver.id` → 400). Editable only while `status="draft"`. Gated by `purchase.demand` permission; list respects `apply_own_filter` for `my_data_only` users.
- **Vendor Quotation** (`VQ-YYYY-seq`) — `GET/POST /api/quotations`, `PUT/DELETE /{id}`. One row per vendor offer against an **approved** demand; each line's `demand_line_id` must belong to that demand and `rate × qty = amount` is server-computed. Writes (`POST`/`PUT`/`DELETE`) are rejected with 400 once the demand's `ComparativeStatement` reaches `approved`/`converted` — the freeze rule that stops backdating prices after a decision. Gated by `purchase.comparative` permission.
- **Comparative Statement** (`CS-YYYY-seq`) — `GET/POST /api/comparatives`, `PUT /{id}` (set `selected_quotation_id` + optional `justification`), `PATCH /{id}/approve`, `POST /{id}/convert-to-po`. Exactly one CS per demand (`UniqueConstraint(tenant_id, demand_id)`); `GET` responses include a `matrix` — demand lines × quotations, each cell `{rate, amount}` or `null` — for the comparison-grid UI. **Approve** requires admin+, rejects self-approval, requires a `selected_quotation_id`, and enforces **lowest-or-justify**: a `justification` string is mandatory when there are fewer than two quotations on the demand or the selected total isn't the lowest; approval also 400s if the winning quotation leaves any demand line unpriced (no partial-price conversions). **Convert-to-PO** copies every line of the winning quotation into a new `PurchaseOrder` (`status="draft"`, `demand_id`/`comparative_id` set) and flips the CS to `converted` and the demand to `converted`.
- **Chain enforcement on `POST /api/purchase-orders`** — when `purchase_store` is installed and the tenant setting `require_purchase_chain` isn't `"false"` (default on), a bare PO (no `comparative_id`) is rejected with 400; a PO carrying `comparative_id` must reference a `ComparativeStatement` owned by the tenant with status `approved`/`converted`, and (if `demand_id` is also supplied) the demand must match the comparative's `demand_id` — otherwise 400. Disabling `require_purchase_chain` in Settings restores unrestricted PO creation.

### Gate Inward (`/api/gate-inwards`, `/api/purchase-reports`)

Receipt control between PO approval and billing (#137 Phase 2). Architectural constraint that shaped the design: stock already arrives at **bill posting**, not at a separate goods-receipt step (no purchase GRN exists — the pre-existing `GoodsReceiptNote` is customer-*custodial* receiving for manufacturing, an unrelated flow). Gate Inward is therefore a memo document that controls *billing*, not stock: `PurchaseOrder.status` gains the previously-unused `received` value as the coverage state between `approved` and `billed`.

- **`GateInward`** (`GI-YYYY-seq`) — `GET/POST /api/gate-inwards`, `GET /{id}`, `PATCH /{id}/cancel`. Required `po_id` (must be `approved`/`received`, tenant-owned). Lines cap per-PO-line at the PO's ordered qty — Σ`qty_received` across all *non-cancelled* GIs for a line (validated per-request, so duplicate lines referencing the same `po_line_id` in one submission are summed, not evaluated independently) can never exceed it. Coverage recompute is the single source of truth for the PO's `approved`↔`received` transition, run identically after create and after cancel — full coverage flips to `received`; cancelling a GI that drops coverage below full reverts to `approved`. **Append-only**: no edit endpoint; cancel requires a non-blank `reason`, is audit-logged, and is refused once the PO is `billed`. Gated by `purchase.gate` (view router-wide, `edit` on the two mutating routes).
- **Billing gate on `POST /api/purchase-orders/{id}/convert-to-bill`** — when `purchase_store` is installed and `require_gate_inward` isn't `"false"` (Settings, default on), conversion is rejected with 400 unless every PO line is fully covered by non-cancelled GI lines. On successful conversion, every `open` GI on that PO flips to `billed` (permanently locking their cancel-eligibility).
- **Gate Register** — `GET /api/purchase-reports/gate-register?start=&end=&q=&status=` — every GI in range; `q` matches vehicle or challan number; `my_data_only` honored (mirrors the list endpoint's scoping — a review finding during Phase 2 caught this report bypassing it initially).
- **3-Way Match** — `GET /api/purchase-reports/three-way-match?start=&end=` — one row per PO line, showing ordered qty/rate/amount vs. Σ received (via `services/gate.py::gi_coverage`) vs. billed qty/amount, with computed `qty_variance`/`amount_variance` and a `flag` when either is non-zero. Surfaces both in-progress partial receipts and (valuably) any legacy PO billed with **zero** recorded Gate Inward at all — a real audit signal on data that predates the module.

### Gate Outward (`/api/gate-outwards`, `/api/store-reports`)

The dispatch-side mirror of Gate Inward (#137 Phase 2b) — covering goods leaving via sales invoice, purchase return (debit note), or scrap disposal. The load-bearing design decision: stock leaves the books at **invoice creation** (`consume_stock` runs before the `Invoice` row is even saved as `draft`), so — unlike Gate Inward — there is no later checkpoint to hang a block on without reworking when invoices post. Invoice/debit-note exits are therefore **reconciliation, not enforcement**: a memo record plus a report that flags mismatches, never a block on invoice/debit-note creation or status changes. Scrap has no prior source document at all, so its Gate Outward entry *is* the transaction — the one path in this module that posts GL on approval.

- **`GateOutward`** (`GO-YYYY-seq`, `source_doc_type` discriminator `invoice`\|`debit_note`\|`scrap`, `source_doc_id` nullable only for scrap) — `GET/POST /api/gate-outwards`, `GET /{id}`, `PATCH /{id}/approve` (scrap only), `PATCH /{id}/cancel`. Gated by `store.gate_outward` (a new **Store** category, distinct from Gate Inward's **Purchasing** — this module spans Sales/Purchases/Inventory, not one department).
  - **Invoice/debit_note exits** — created directly at `status="approved"`; no draft step, no GL, no stock effect (already happened when the source document posted). Invoice eligibility rejects only `status="void"` — a `draft` invoice is a *valid* exit source since its stock has already left, an intentional asymmetry from the debit-note path (which rejects `draft`, since debit notes only move stock once `posted`). Cancel works anytime with a reason.
  - **Scrap exits** — created at `status="draft"` (no GL/stock yet — a mistake costs nothing to fix while draft). `PATCH /{id}/approve` (admin+, blocks self-approval, row-locked with `with_for_update()` to prevent a double-approval race from double-posting) calls `consume_stock(..., source_doc_type="gate_outward")` per line and, if `Σ(qty × unit_value) > 0`, posts `Dr 1000 Cash in Hand / Cr 4902 Scrap Sales`; always (when qty > 0) posts a second, separate JV `Dr 5901 Scrap Disposal Expense / Cr Inventory` at the relieved cost — two JVs, mirroring how invoice posting splits Revenue and COGS. Once `approved`, immutable (ISA 240: corrections are new documents, not edits to posted ones) — matches this codebase's own convention on `CreditNote`.
- **Gate Outward Register** — `GET /api/store-reports/gate-outward-register?start=&end=&q=&source_doc_type=` — every exit in range with a resolved `reference` (invoice #/debit-note #/"Scrap"), vehicle/challan search, `my_data_only` honored.
- **Dispatch Reconciliation** — `GET /api/store-reports/dispatch-reconciliation?start=&end=` — one row per posted Invoice (`!= void`) and DebitNote (`!= draft`) in range, flagging `has_gate_exit: false` for any with no matching Gate Outward — the audit artifact for "did this actually ship."

### Universal Search (`/api/search`)

- `GET /api/search?q=&limit=&types=` — full-text search across 8 entity types. Returns ranked results with `label`, `sub`, `href`, `date`, `amount`, `status`. `types` is a comma-separated filter (e.g. `types=customers,invoices`); omit to search all.

**Entity types and expanded columns searched:**

| Type | Columns searched |
|------|-----------------|
| `customers` | name, contact, address, ntn, cnic |
| `vendors` | name, contact, address |
| `invoices` | number, customer_name, description, notes, status, issue_date |
| `bills` | number, vendor_name, description, notes, status, issue_date |
| `accounts` | code, name, type |
| `products` | code, name, unit, product_type |
| `employees` | name, designation, cnic, bank_name |
| `transactions` | jv_number, reference, notes, date, voucher_type |

The frontend `GlobalSearch` component calls this endpoint with a 150 ms debounce after the user pauses typing. Results from all 8 entity types are merged and ranked by relevance. The `types` param is set automatically when the user activates a prefix filter (`inv:`, `cust:`, etc.).

### System / Update (`/api/system`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/system/update/status` | Checks GitHub Commits API (`/repos/bilalpiaic/Easy-Books/commits/main`) for new commits; returns `{status, local, remote, behind}` |
| `POST` | `/api/system/update` | Runs `git pull + alembic upgrade head + npm run build`, returns `"restarting"` |
| `GET` | `/api/system/update/changelog?since=<sha>&limit=8` | `git log <since>..HEAD` formatted commits |

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
| **Group consolidation** | **IFRS 10 / IAS 27** | Entity graph (`ConsolidationMember`) on the holding tenant; worksheet run aggregates member TBs by account code, proposes IC AR/AP + NCI eliminations (`services/consolidation.py`), and posts an immutable package (consolidated BS/P&L). Eliminations never hit member GLs. Associates = equity-method one-liner. Locked-period post requires owner/admin override. UI: `/consolidation`. |
| **Leases (lessee)** | **IFRS 16** | Contract master + amortisation schedule (`LeaseContract` / `LeaseScheduleLine`); activate posts Dr RoU / Cr liability (+ IDC); period run posts interest, payment, RoU depreciation via `posting.py`; simplified early termination; maturity disclosure buckets. Settings gate: `leases_enabled`. CoA: 1510/1511/2510/5125. UI: `/leases`. |
| **Inventory depth** | **IAS 2** | Landed cost onto layers (`LandedCost`); lot/serial (`track_lot` / `track_serial`); NRV write-down runs (`NrVRun`). UI: `/inventory/valuation`. |
| **Month-end close pack** | **ISA / close controls** | `CloseChecklistItem` per period; optional lock gate via `period_close_require_checklist`; auditor ZIP export (`services/close_pack.py`). |
| **Tax rate history** | **Multi-jurisdiction** | `TaxRateHistory` effective-dated rates; documents snapshot rates at post time (#263). |
| **Saudi ZATCA e-invoice** | **KSA Phase 2** | `sa_zatca` module — sandbox clear/report via Fatoora, TLV QR, `ZatcaSubmissionLog` (#264). |
| **IFRS 15 remainder** | **IFRS 15** | Relative-SSP multi-element allocation (`RevenueAllocationAudit`); contract assets (`ContractAsset`, CoA 1140); UI `/contract-balances` (#259). |
| **Analytic dimensions** | **IAS 1 segment** | Up to 3 `AnalyticDimension`s; JE slots `analytic_account_id` / `analytic_2_id` / `analytic_3_id`; mandatory dims; dimensional P&L (#260). |
| **Intercompany** | **IFRS 10 companion** | `is_intercompany` + mirror drafts across consolidation members; recon at `/intercompany/recon` (#261). CoA 1180/2180. |
| **India GST** | **GST India** | `in_gst` module — place of supply, CGST/SGST/IGST, GSTR-1/3B (#265). |
| **Peppol / EU VAT** | **EN 16931** | `eu_peppol` module — BIS Billing 3.0 UBL export + Access Point submit, `PeppolSubmissionLog` (#266). |
| **Withholding + CIT** | **Tax reporting** | Vendor `wht_*` + `BillPayment.wht_amount` (Cr 2265); `CitAdjustment` worksheet (#267). |
| **Fixed assets depth** | **IAS 16 / 36** | Componentization (`parent_id`), impairment/reversal, disposal, rollforward report (#258). |

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

## 10B. PRA e-INVOICE TRACK (Pakistan)

Punjab Revenue Authority (PRA) requires registered businesses in Punjab, Pakistan to submit every sales invoice to the eIMS system in real-time and print the returned Fiscal Invoice Number (FIN) on all invoices.

### 10B.1 New fields

| Model | Column | Purpose |
|-------|--------|---------|
| `Invoice` | `payment_mode` | Int 1–6 (Cash/Card/GiftVoucher/Loyalty/Mixed/Cheque) sent to PRA |
| `Invoice` | `pra_usin` | User Serial Invoice Number sent to PRA (= `invoice.number`) |
| `Invoice` | `pra_fiscal_number` | FIN returned by PRA on success |
| `Invoice` | `pra_status` | `not_required` / `pending` / `submitted` / `failed` |
| `Invoice` | `pra_submitted_at` | Timestamp of successful submission |
| `Invoice` | `pra_response_raw` | Raw JSON response (audit trail) |
| `Customer` | `ntn` | 7-digit Business NTN (BuyerPNTN in PRA payload) |
| `Customer` | `cnic` | 13-digit Consumer CNIC (BuyerCNIC in PRA payload) |
| `Product` | `pct_code` | 8-digit PRA product classification code (PCTCode per line) |

**New table:** `PRASubmissionLog` — one row per API call; records endpoint, request JSON, HTTP status, PRA code, response JSON, success flag.

**New settings keys:** `pra_enabled`, `pra_ntn`, `pra_pos_id`, `pra_api_token`, `pra_sandbox_mode` — stored in the tenant `AppSettings` KV store.

### 10B.2 Submission flow

```
POST /api/invoices  →  GL post  →  invoice.pra_status = "pending"
                              ↓ (BackgroundTasks — non-blocking)
                    services/pra.py::submit_to_pra()
                              ↓
                    build_pra_payload(invoice, lines, customer, products)
                              ↓
                    POST https://ims.pral.com.pk/ims/{mode}/api/Live/PostData
                              ↓
                    Code "100" → pra_status = "submitted", pra_fiscal_number = FIN
                    other      → pra_status = "failed"
                              ↓
                    PRASubmissionLog row inserted
```

The invoice save never waits for PRA — accounting correctness is independent of tax reporting.

### 10B.3 API endpoints (`backend/routers/pra.py`)

| Method | Path | Permission | Purpose |
|--------|------|-----------|---------|
| `POST` | `/api/pra/test` | `invoices:edit` | Ping sandbox/production and return PRA code |
| `GET` | `/api/pra/invoices/{id}/status` | `invoices:view` | Return `pra_status`, FIN, USIN, submitted_at |
| `POST` | `/api/pra/invoices/{id}/submit` | `invoices:edit` | Manual retry / re-submission |
| `GET` | `/api/pra/logs` | `invoices:view` | List `PRASubmissionLog`; row-scoped via Invoice join when `my_data_only=true` |

### 10B.4 Payload mapping

| PRA field | Easy-Books source |
|-----------|------------------|
| `POSID` | `settings["pra_pos_id"]` |
| `USIN` | `invoice.number` (unique per tenant → idempotent retries) |
| `DateTime` | `invoice.issue_date + " 00:00:00"` |
| `BuyerName` | `customer.name` |
| `BuyerPNTN` | `customer.ntn` |
| `BuyerCNIC` | `customer.cnic` |
| `BuyerPhoneNumber` | `customer.phone` |
| `TotalSaleValue` | Invoice subtotal (pre-tax) |
| `TotalTaxCharged` | `invoice.gst_amount` |
| `TotalBillAmount` | `invoice.total` |
| `TotalQuantity` | Sum of all line qty values |
| `Discount` | Sum of per-line discount amounts |
| `PaymentMode` | `invoice.payment_mode` (default 1 = Cash) |
| `InvoiceType` | 1 = standard; 2 = debit note; 3 = credit note |
| `Items[].PCTCode` | `product.pct_code` or `"00000000"` |
| `Items[].TaxRate` | `tax_code.rate` or `invoice.gst_rate` |

### 10B.5 Invariants

- Invoice save is **never blocked** by PRA API latency — `BackgroundTasks` decouples the two.
- USIN = `invoice.number` (already unique per-tenant) → retries are safe and idempotent.
- Sandbox token `24d8fab3-f2e9-398f-ae17-b387125ec4a2` is static/shared — only production token is tenant-specific; **never logged**.
- `pra_status` defaults to `"not_required"` — no badge shown unless tenant has `pra_enabled = "true"`.
- Migration `0026_pra_integration` follows the SQLite-safe pattern: no `ADD CONSTRAINT` ALTER, `has_table` guard on `prasubmissionlog`.

### 10B.6 Portal Mode

PRA-enabled tenants have a dedicated portal mode that surfaces only PRA-relevant UI.

| Symbol | Details |
|--------|---------|
| `usePRAPortal()` hook | Returns `{ isPortal, canToggle, togglePortal, settled }`. `settled` is `false` until the hook has read `localStorage`, preventing an SSR/hydration redirect loop. |
| `PORTAL_NAV` | 7-item nav array defined in `Sidebar.tsx` — New Invoice / Invoice Queue / Credit Notes / Customers / Products / Submission Logs / Settings. |
| `/pra-dashboard` | Portal home page — KPI cards (Today's Sales, PRA Submitted, Failed/Pending, Cash/Card split) + today's invoice table with drill-down. |
| `localStorage` key | `eb.pra_portal_mode` = `"1"` (portal) or `"0"` (full accounting). Per-browser; does not sync across devices. |
| Admin/owner gate | Only users with role `admin` or `owner` see the toggle button and can switch to Full Accounting view. All other roles always land in Portal mode. |

---

## 10C. HEALTHCARE / HOSPITAL TRACK (V4)

Applies to `business_model == 'hospital'`. 19 `hc_*` tables (`models_healthcare.py`). Routes in `routers/healthcare.py` (25+ endpoints) and `routers/healthcare_reports.py` (7 reports). GL writes flow through `services/healthcare_posting.py` → `services/posting.py`. Frontend in `src/app/(dashboard)/healthcare/` (11 pages) using `components/healthcare/primitives`.

### 10C.1 Entities (`hc_*`)

HcPatient · HcDoctor · HcWard · HcBed · HcProcedureCatalog · HcOpdToken · HcOpdVisit · HcPrescription · HcPrescriptionItem · HcAdmission · HcAdmissionCharge · HcLabTest · HcLabOrder · HcLabOrderItem · HcSampleCollection · HcProcedureOrder · HcStoreIssue · HcStoreIssueItem · HcProcedureConsumable

### 10C.2 OPD Cycle

```
1. Token issued → queue_number assigned (OPD-YYYYNNNN)
      Dr 1100 AR  / Cr 4100 OPD Revenue

2. Patient called → token status: waiting → in_progress

3. Doctor records HcOpdVisit (diagnosis, vitals, ICD notes)
   → optional HcPrescription + HcPrescriptionItems
   → token status: completed
```

### 10C.3 IPD Cycle

```
1. Admit:
      Dr 1000 Cash / Cr 2350 Patient Deposit Liability  (deposit)
      HcBed.status → occupied

2. Accumulate charges (HcAdmissionCharge — no per-charge GL):
      Ward charges, nursing, diet, pharmacy dispenses, procedures

3. Discharge:
      Consolidated Invoice = Σ all admission charges
      Dr 1100 AR / Cr 4110 IPD Ward Revenue (and sub-lines per type)
      Dr 2350 Patient Deposit / Cr 1100 AR  (offset deposit)
      HcAdmission.status → discharged
      HcBed.status → available
```

### 10C.4 Lab Cycle

```
Order created → LO-YYYYNNNN
Sample collected → HcSampleCollection row
Results entered → HcLabOrderItem.result_value + is_abnormal flag
Delivered to requesting doctor →
      Dr 1100 AR / Cr 4115 Lab Revenue
```

### 10C.5 Pharmacy / Store Dispense

Pharmacy dispense calls `consume_stock(product_id, qty)` (the same inventory engine used by Sales). GL:
```
Dr 5010 COGS  / Cr 1200 Drug/Supply Inventory
```
Store issues are linked to a patient (`HcStoreIssue`) or a procedure order (`HcProcedureConsumable`).

### 10C.6 Demo seed

The `demo.hospital@easy-books.app` tenant is seeded with:
- 5 doctors (4 specialisations)
- 4 wards (General × 2, ICU, Maternity) with 10 beds each
- 50 patients (MR-2026-0001 … MR-2026-0050), each linked to a Customer row
- 200 OPD tokens (spread over the last 90 days) with visit records
- 20 IPD admissions (10 active, 10 discharged with invoices)
- 80 lab orders (various statuses)

---

## 10D. YARN SPINNING TRACK

Applies to `business_model == 'yarn_spinning'`. 16 `sp_*` tables (`models_spinning.py`). Routes in `routers/spinning.py` (40+ endpoints), `routers/spinning_reports.py` (6 reports), and `routers/spinning_calculators.py` (3 calculators). GL writes flow through `services/spinning_posting.py` → `services/posting.py`. Frontend in `src/app/(dashboard)/spinning/` (15 pages).

### 10D.1 Entities (`sp_*`)

Masters: `SpYarnSpec`, `SpFiberGrade`, `SpMachine`, `SpShift`, `SpOperator`, `SpWasteType`, `SpRecipe`/`SpRecipeLine`. Operations: `SpProductionPlan`, `SpSpinLot`, `SpBaleReceipt`, `SpStageEntry`, `SpConeOutput`, `SpWasteLog`, `SpYarnDispatch`, `SpCalcRun`.

### 10D.2 Production cycle

```
Setup masters → Production Plan (approve) → Spin Lot (start)
  → Bale Receipt (approve: Dr 1200 / Cr AP|Cash + stock RAW)
  → Stage Entries (post: WIP transfers 1201→1202→1203 + labour/overhead)
  → Waste Log (post: Dr 590x / Cr WIP)
  → Cone Output (approve: Dr 1204 / Cr 1203 + stock FG-YARN)
  → Yarn Dispatch (approve: Dr 5010 COGS / Cr 1204 + stock relief)
  → Lot complete → close (cost-per-kg finalised)
```

### 10D.3 Stock locations

Auto-created by `ensure_spinning_locations()`: `RAW` (raw cotton store), `WIP-CARD`, `WIP-DRAW`, `WIP-SPIN` (stage WIP), `FG-YARN` (finished yarn).

### 10D.4 Demo seed

The `demo.spinning@easy-books.app` tenant is seeded with yarn specs, fiber grades, machines, shifts, operators, waste types, recipes, open and completed spin lots, approved bale receipts, posted stage entries, cone output, waste logs, and yarn dispatches with real GL postings. The mill also sees Marketplace **Weighbridge** (see §10E).

---

## 10E. MARKETPLACE, STUDIO & WEIGHBRIDGE

Shipped on `main` (PRs #377–#383 Studio epic #369; mill listing #384; mill visibility / Add-ons discovery #387). Companion: [`docs/MARKETPLACE.md`](./docs/MARKETPLACE.md), [`USER_GUIDE.md` §41](./USER_GUIDE.md#41-weighbridge-mill-marketplace-listing).

### 10E.1 Marketplace (products, not tenants)

`GET /api/marketplace/catalog` filters curated listings **on the server**:

| `audience` | Who sees the card |
|---|---|
| `public` | Every signed-in tenant |
| `entitled` | Tenants that have `entitled_module` entitled **or** installed |
| `private` | `visible_to_tenant_ids`, ops `module_meta._marketplace_private`, mill `business_model`, spinning module, or `MARKETPLACE_PRIVATE_AUDIENCE` env |

UI: **System → Add-ons** (`/apps`) tab **Marketplace** (`?tab=marketplace`). Install **never executes partner code** (declarative manifest + optional Studio bundle). Uninstall archives bundle field defs; document JSON values remain.

### 10E.2 Settings Studio

`/settings/studio` (admin/owner): extra `x.*` columns (cap 12 per entity), form hide/require, print templates. Values live on document `custom_fields` JSON. **`x.*` is never imported in `services/posting.py`** — ∑Dr = ∑Cr is unchanged.

### 10E.3 Weighbridge (private mill listing)

Listing id `partner.easybooks.weighbridge`. **Not** a truck-scale module, Optional first-party pack, or GL writer.

| Field | Key | Required | Form | Print | List |
|---|---|---|---|---|---|
| Gate pass | `x.gate_pass_no` | yes | yes | yes | yes |
| Lot ref | `x.lot_ref` | no | yes | no | no |

**Who sees the card:** `business_model` in `{manufacturing, yarn_spinning}` (catalog `visible_to` without a seed grant), any tenant with the `spinning` module, ops `PUT /api/ops/tenants/{id}/marketplace-private`, boot backfill `_ensure_mill_weighbridge_grants`. Hospital / simple / ungranted: catalog omits the id; install returns 404.

**User path:** mill login → Add-ons → Marketplace (For you auto-opens) → Install → Sales → New Invoice (Gate pass required, Lot ref optional) → Print shows Gate pass. Overlay is on **sales invoices** only, not spinning bale receipts or gate inward.

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
| `GET /api/reports/dashboard/net-worth` | `JournalEntry` grouped by month × account type | Monthly cumulative Assets / Liabilities / Net Worth series (v3.1) |
| `GET /api/reports/product-ledger` | `StockMovement` | Stock movements + running qty; per-location or consolidated |
| `GET /api/reports/inventory-performance` | `Product` + `StockMovement` + `InventoryLayer` | On-hand qty/value, low-stock, slow-movers, units sold + COGS |
| `GET /api/reports/customer-performance` | `Invoice` + `PaymentReceived` | Revenue, invoice count, outstanding AR, avg days-to-pay per customer |
| `GET /api/manufacturing/dashboard` | ProductionOrder + InventoryLayer | Pipeline + WIP/FG/custodial |
| `GET /api/manufacturing/wip-aging` | ProductionOrder | Days since `started_at` |
| `GET /api/manufacturing/production-summary` | ProductionOrder | By state |
| `GET /api/manufacturing/customer-custody` | InventoryLayer + GoodsReceiptNote | Per-(customer, product) |
| `GET /api/healthcare/reports/dashboard` | HcOpdToken, HcAdmission, HcLabOrder, GL | Today's OPD, occupied beds, pending labs, revenue MTD |
| `GET /api/healthcare/reports/opd-summary` | HcOpdToken | Visits by date range / doctor / status |
| `GET /api/healthcare/reports/doctor-collections` | HcOpdToken + Invoice | Revenue per doctor |
| `GET /api/healthcare/reports/lab-summary` | HcLabOrder | Orders by status + turnaround |
| `GET /api/healthcare/reports/ipd-census` | HcAdmission + HcBed | Active admissions, ward occupancy, avg LOS |
| `GET /api/healthcare/reports/revenue-by-type` | JournalEntry grouped by GL 4100–4121 | OPD/IPD/Lab/Procedure/Pharmacy revenue split |
| `GET /api/healthcare/reports/patient-statement/{id}` | HcPatient + all transactions | Full financial history for one patient |
| `GET /api/spinning/reports/dashboard` | SpSpinLot + SpStageEntry + SpConeOutput | KPIs: open lots, kg in WIP, output today, waste % |
| `GET /api/spinning/reports/daily` | SpStageEntry + SpConeOutput | Daily production register |
| `GET /api/spinning/reports/lot-control/{lot_id}` | SpSpinLot + all lot documents | Input/output balance and cost breakdown |
| `GET /api/spinning/reports/waste` | SpWasteLog | Waste by type and stage |
| `GET /api/spinning/reports/cost-per-kg` | SpSpinLot | Cost-per-kg across lots |
| `GET /api/spinning/reports/dispatch` | SpYarnDispatch | Yarn dispatch register |

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

### 13.4 Schema bootstrap & Alembic
- **Alembic is the source of truth** (`backend/alembic/versions/`). Installers and packaged entrypoints run `alembic upgrade head` on every launch.
- A fresh dev SQLite file may still be created via `SQLModel.metadata.create_all()`; new-table migrations must guard with `bind.dialect.has_table(...)` so they coexist with that bootstrap. New columns on existing tables use `has_column` guards for the same reason.
- SQLite cannot `ADD CONSTRAINT` via ALTER — strip auto-generated FK lines (migrations 0016/0017 pattern). App-level tenant checks still enforce integrity.
- V2.2's `0011_stock_locations` uses `op.execute("ALTER TABLE … ADD COLUMN …")` instead of `batch_alter_table` because the legacy `create_all` baseline had anonymous constraints that batch-mode couldn't rename.

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

### 14.5 Dashboard grid (react-grid-layout) — dual-home v4
- Import as `import ReactGridLayout from 'react-grid-layout/legacy'` — this is the **v2 API** (React 19 compatible, self-typed). Do **not** import from `'react-grid-layout'` (v1 API) and do **not** install `@types/react-grid-layout` (types incompatible with v2, will cause TS errors).
- **Dual homes:** Financial \| Operations toggle on `/dashboard` (`useHomeDashboard` + `eb.home_dashboard`). Ops-capable modules from `lib/dashboardHome.ts`; ops-heavy models default to Operations.
- Layout schema **v4**: `{version:4, activeView?, dashboards:{financial:{layouts,dismissed?,quickActions?}, operations:{…}}}` with `BP_COLS = {lg:4, sm:2, xs:1}`. Pure migrate/default helpers in `lib/dashboardLayoutLogic.ts`; hook `useDashboardLayout(view)` edits one slice. v1–v3 migrate under `financial`.
- Ops aggregate API: `GET /api/dashboard/operations-summary` (`routers/dashboard_ops.py`). Staff rights: `dashboard.financial` / `dashboard.operations`.
- **`WIDGET_REGISTRY`** in `src/lib/dashboardWidgets.tsx` — widgets carry `home: "financial" | "operations" | "both"` + optional `requiredModule`; `injectMissingDefaults` adds newly shipped defaults per active home.
- **`KpiCard` (v3.1)** — all stat tiles render through the shared `components/dashboard/KpiCard.tsx` (replaced the divergent `PrimaryKpi`/`SecondaryKpi`): `tone` prop for colored-tile variants, icon top-left/title bottom-left/value bottom-right when an icon is present (title top-left otherwise), CSS theme variables for dark-mode safety, optional `href`/badge/subtext/shimmer.
- **`NetWorthTrendWidget` (v3.1)** — self-fetching combo chart (Chart.js mixed bar/line): Assets bars up, Liabilities bars down around a zero axis, Net Worth line with square markers; 3M/6M/1Y/All range pills (client-side slicing of a 36-month fetch); legend click toggles series.
- **Top-10 widgets (v3.1)** — Top Customers (backend `limit=10` in `/dashboard/charts`) and Top Products (client slice 10) show ten entries.

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

### 14.10 TopNav — Portal Dropdowns + Scrollable Tab Strip (v3.0)

`components/TopNav.tsx` manages the header tab strip and portal-based dropdowns:

- **Scrollable tab strip** — `overflow-x: auto scrollbar-hide`; a `ResizeObserver` tracks whether content overflows and shows left/right `ChevronLeft`/`ChevronRight` scroll arrows with gradient fades.
- **`More ▾` dropdown** — lives outside the scroll container so it is always reachable regardless of how many tabs are open.
- **Portal-based dropdowns** — use `ReactDOM.createPortal` + `getBoundingClientRect()` to position at `position: fixed` coordinates. This avoids the tab strip's `overflow-x` clipping that would swallow an `absolute`-positioned dropdown.
- **Search icon** — dispatches a `search:open` custom event picked up by `GlobalSearch`.
- **Theme toggle** — Sun/Moon icon calls `useTheme()` to cycle through modes.
- **Dark mode nav inversion** — CSS vars `--nav-bg`, `--nav-text`, `--nav-sub`, `--nav-dim`, `--nav-sep`, `--nav-hover`, `--nav-active` flip to cream/charcoal in `[data-theme="dark"]` so the nav bar is light-colored on dark pages (light nav on dark page).
- **Icon + label dropdown items (v3.1)** — every section-dropdown item renders `<item.icon>` + label at uniform weight/padding, using the `icon` each `SUB_NAV` `NavItem` already carries; `SECTION_OVERVIEW` rows carry their own icons (LayoutGrid for generic overviews, Stethoscope/Factory/Radio/etc. for specialized sections) and are styled as normal menu items, not headings (#132). The mobile `MoreDrawer` items get the same icon treatment.

### 14.11 GlobalSearch — Ctrl+K Command Palette (v3.0)

`components/GlobalSearch.tsx` is a portal overlay (mounted on `<body>`) opened by Ctrl+K or the TopNav search icon.

**3-tier architecture:**

| Tier | Latency | Source |
|------|---------|--------|
| Open tabs | 0 ms | `useTabs` context |
| Nav index | 0 ms | `lib/navIndex.ts` static in-memory index |
| API | 150 ms (debounced) | `GET /api/search?q=&limit=&types=` |

**`lib/navIndex.ts` — 3-layer static index:**
- **Layer 1** — All sidebar nav pages (same items as `NAV` array in `nav.ts`)
- **Layer 2** — 14 quick-action "New…" shortcuts (new invoice, new bill, new customer, new payment, etc.)
- **Layer 3** — 22 report/utility pages with keyword aliases (e.g. `"p&l"` → `/pl`, `"aged debtors"` → `/aging/receivable`)

**Prefix filter syntax:** typed before the query, limits results to one entity type:

| Prefix | Searches |
|--------|----------|
| `inv:` | Invoices |
| `cust:` | Customers |
| `tab:` | Open tabs |
| `acc:` | Accounts |
| `emp:` | Employees |
| `jv:` | Transactions |
| `rpt:` | Reports/pages |
| `new:` | Quick-action shortcuts |
| `bill:` | Bills |
| `prod:` | Products |
| `vendor:` | Vendors |

**Result shape:** `label`, `sub` (secondary line), `href`, `date`, `amount`, `status` badge (color-coded).

**Recent searches** — stored in `localStorage` key `eb.recent-searches`, max 5 entries. Displayed when the query is empty.

**Empty state** — shows quick-action chips + prefix hint bar so users discover the syntax without documentation.

**Keyboard:** Ctrl+K opens, ArrowUp/Down navigates, Enter opens the selected result, Esc closes.

### 14.12 In-App Auto-Update System (v3.0)

Two new UI components extend the update flow beyond the existing `UpdateModal.tsx`:

**`UpdateAvailablePopup.tsx`** — bottom-sheet / centered-card notification shown by `DashboardLayout` when `GET /api/system/update/status` returns a newer commit (checked on every mount for `admin`/`owner` roles):
- **Update Now** — starts the update sequence
- **Later** — session-dismissed via `localStorage` key `eb.update-later-session`
- **Skip version** — SHA-keyed persistent dismiss via `localStorage` key `eb.update-skip`

**`UpdateProgressScreen.tsx`** — fullscreen portal overlay displayed while `POST /api/system/update` executes:
- Animated SVG ring (spinning) with Zap icon in the center
- 4-phase text labels: **Pull → Compile → Bundle → Start**
- Progress bar: `Math.min((elapsed / 120) × 100, 90)%` (clamps to 90 until verified complete)
- Polls `GET /version.json` every 5 s to detect commit change; on success switches to a green ring + CheckCircle + "What's New" commit list from `/api/system/update/changelog`
- On error: AlertCircle icon + manual command instructions

**Post-update toast:** `localStorage` key `eb.just-updated` triggers a congratulations toast after the page reloads.

### 14.13 BottomNav, FAB, MoreDrawer — Mobile Navigation (v3.0)

Three new components for mobile-only navigation (hidden at `sm:` breakpoint and above):

- **`components/BottomNav.tsx`** — fixed bottom bar with 4–5 core nav items (Home, Invoices, Payments, More). Renders only on phones.
- **`components/FAB.tsx`** — floating action button (bottom-right) for quick new-entry creation. Expands on tap to show contextual "New…" options gated by installed modules.
- **`components/MoreDrawer.tsx`** — slide-up sheet triggered by the "More" tab in `BottomNav`. Renders the full nav list filtered by `installedModules`. Closes on backdrop tap or swipe-down.

### 14.14 Settings Page — 5-Tab Layout (v3.0)

`/settings` was restructured from a single scrolling page into five tabs:

| Tab | Contents |
|-----|---------|
| Company | Name, tagline, logo, address, phone, website |
| Accounting | Currency, fiscal year start, invoice/bill prefixes, tax ID, default GL accounts |
| Preferences | Dark mode, color theme, language, block negative stock |
| Advanced | User rights module toggle, PRA settings (if PRA module installed) |
| Updates | Version display, "Check for Updates" trigger, changelog viewer |

The **Updates tab** unifies version management for all install types (Electron, script, web). On Electron it calls the `electron-updater` bridge; on other installs it shows the CLI command.

### 14.15 QB UI Token System — CSS Custom Properties (v3.0)

All 155+ pages and components have been migrated from hardcoded hex colors to CSS custom properties defined in `globals.css`. Every reference to the brand palette hex codes now goes through a token variable.

**Page / card tokens:**

| Variable | Light value | Dark value |
|----------|-------------|------------|
| `--bg-page` | `#f6f3ee` (cream) | `#1a1814` (charcoal) |
| `--bg-card` | `#ffffff` | `#252219` |
| `--border` | `#e5e1d8` | `#3a3529` |
| `--text-primary` | `#1a1814` | `#f6f3ee` |
| `--text-secondary` | `#4a4540` | `#c8c4bc` |
| `--text-muted` | `#8c8880` | `#6b6760` |
| `--primary` | `#b8943f` (gold) | `#d4a84b` |
| `--primary-light` | `#f5edd5` | `#2e2510` |
| `--primary-dark` | `#8c6e2a` | `#b8943f` |

**Nav tokens** (TopNav + Sidebar — inverted in `[data-theme="dark"]` for a light-nav-on-dark-page look):

| Variable | Purpose |
|----------|---------|
| `--nav-bg` | Navigation bar background |
| `--nav-text` | Primary nav text |
| `--nav-sub` | Secondary nav labels |
| `--nav-dim` | Dimmed/inactive items |
| `--nav-sep` | Separator lines |
| `--nav-hover` | Hover state background |
| `--nav-active` | Active/selected item background |

In dark mode the nav vars flip to cream/gold on charcoal so the header and sidebar remain visually distinctive from the page background.

### 14.16 Report Freeze Panes & Print Overhaul (v3.1)

**Freeze panes** — `globals.css` FREEZE PANES block:
- `.table-freeze` on the div directly wrapping a `<table>` bounds its height (`max-height: var(--table-freeze-h, calc(100dvh - 240px))`) so the wrapper becomes the vertical scrollport and the sticky `<thead>` + sticky `<tfoot>` (totals row) actually engage. A plain `overflow-x-auto` wrapper grows with content and never scrolls vertically — sticky headers inside it are a no-op; this class is what makes them work.
- `.freeze-col` on the same wrapper additionally pins the first column (`position: sticky; left: 0`) with a boundary shadow; the top-left corner cell layers above both (z-25 > thead z-20 > col z-5).
- Rolled out to: aging AR/AP, customer/inventory performance, GL ledger, product ledger, report-builder grid, healthcare + manufacturing reports, customer/vendor statements, telecom tracker. Div-based pages (cash-book, bank-book, cashflow) render no `<table>` and are not covered.
- **Every rule is reset under `@media print`** (`position: static`, `max-height: none`) so reports paginate in full — print relies on `thead { display: table-header-group }` for per-page header repetition.

**Print overhaul** — all printouts render in **Courier New** black-and-white (dot-matrix/continuous-paper friendly); Tailwind v4 font-size CSS variables are capped in print; row spacing compressed for denser fit; GL ledger joined the landscape orientation list. Interactive UX shipped alongside: AR/AP aging bucket summary cards are **click-to-filter** (click a bucket to filter the items table, click again or "Show all" to reset). Canonical conventions live in `CLAUDE.md` (UI conventions) and `WORKFLOW.md` (print system).

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
| `0023_employees` | HRM | `Employee` |
| `0024_payroll` | HRM | `SalaryComponent`, `EmployeeSalaryStructure`, `PayrollRun`, `PayrollLine`, `PayrollLineDetail` |
| `0025_attendance` | HRM | `AttendanceRecord` |
| `0026_pra_integration` | PRA | `Invoice.pra_*` fields, `Customer.ntn/cnic`, `Product.pct_code`, `PRASubmissionLog` |
| `0027_healthcare` | V4 | 19 `hc_*` tables (HcPatient … HcProcedureConsumable); SQLite-safe `has_table` guard |
| `0028_tenant_hospital_model` | V4 | Adds `'hospital'` to `Tenant.business_model` CHECK via raw SQL recreation (SQLite) |

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

### 18.1 Release Pipeline

The CI/CD release pipeline lives at `.github/workflows/release.yml` and is triggered by any `v*` tag push.

```
Trigger: git tag vX.Y.Z && git push origin vX.Y.Z

Stage 1 (validate):
  - Reads frontend/package.json, desktop/package.json, backend/pyproject.toml
  - Fails if any version does not match the tag
  - Prevents mismatched binaries from reaching users

Stage 2a (build-windows):
  - Always runs
  - Produces .exe installer + latest.yml auto-update manifest

Stage 2b (build-macos):
  - Runs only when APPLE_ID repository secret is set
  - Produces .dmg installer + latest-mac.yml manifest
  - Skipped gracefully if secret absent; Windows-only release still publishes
  - fail-fast disabled — Windows and macOS build independently

Stage 3 (publish):
  - Single job; waits on build-windows (required) and build-macos (optional)
  - gh release create with all artifacts
  - Tags with a hyphen (e.g. v2.9.0-beta.1) are auto-flagged --prerelease
  - workflow_dispatch input allows manual re-run for any existing tag
```

**Version file sync requirement:** All three files (`frontend/package.json`, `desktop/package.json`, `backend/pyproject.toml`) must carry the same version string as the tag before pushing. The validate stage fails fast otherwise.

**Secrets:**
- `GITHUB_TOKEN` — auto-provided by Actions
- `CSC_LINK` / `CSC_KEY_PASSWORD` — Windows code-signing (optional)
- `APPLE_ID` / `APPLE_ID_PASSWORD` / `APPLE_TEAM_ID` — macOS notarization (optional)

---

## 18.1. DEMO DATA & SEEDING

**Automatic Demo Tenants (on first run):**
- On database init (`db.py`), eight demo tenants are auto-created, one per business model. `dev.sh` seeds each with 50+ records per entity type:
  - `demo.simple@easy-books.app` (Simple model)
  - `demo.services@easy-books.app` (Services model)
  - `demo.trader@easy-books.app` (Trader model)
  - `demo.manufacturing@easy-books.app` (Manufacturing model)
  - `demo.telecom@easy-books.app` (Telecom Franchise model)
  - `demo.pra@easy-books.app` (PRA e-Invoice model)
  - `demo.hospital@easy-books.app` (Healthcare / Hospital model — 50 patients, 5 doctors, 4 wards, 200 OPD tokens, 20 IPD admissions, 80 lab orders)
  - `demo.spinning@easy-books.app` (Yarn Spinning model — spin lots, bale receipts, stages, cones, waste, dispatches with GL)
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

> **2026-09-06:** Tenant Studio (#369 / PRs #377–#383) and mill Weighbridge (#384 / #387) are on `main`. Alembic is the schema source of truth. Remaining production-launch work is **ops secrets** (Stripe / Neon PITR / S3) and GitHub issue-close hygiene — not product forks. Live queue: [`docs/ROADMAP.md`](./docs/ROADMAP.md).

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
| G-05 | **Fixed Assets** register + straight-line / reducing-balance depreciation; **#258** components (`parent_id`), IAS 36 impairment/reversal, disposal gain/loss via `posting.py`, rollforward report | IAS 16 / 36 | `routers/assets.py`, `services/assets.py`, `services/depreciation.py` | `/assets`, `/assets/rollforward` |
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

### Sprint 19 Shipped ✅ (Healthcare / Hospital Track V4)

| Feature | Notes |
|---------|-------|
| **19 `hc_*` tables** | `HcPatient` (MR-YYYYNNNN, auto-linked Customer), `HcDoctor`, `HcWard`, `HcBed` (status machine), `HcProcedureCatalog`, `HcOpdToken`, `HcOpdVisit`, `HcPrescription`/`Item`, `HcAdmission` (ADM-YYYYNNNN), `HcAdmissionCharge`, `HcLabTest`, `HcLabOrder` (LO-YYYYNNNN), `HcLabOrderItem`, `HcSampleCollection`, `HcProcedureOrder`, `HcStoreIssue`/`Item`, `HcProcedureConsumable` |
| **Alembic migrations** | `0027_healthcare` (19 tables, `has_table` guard) + `0028_tenant_hospital_model` (adds `'hospital'` CHECK value via raw SQL recreation) |
| **Backend routers** | `routers/healthcare.py` (25+ endpoints, full OPD/IPD/Lab/Procedure/Store cycles), `routers/healthcare_reports.py` (7 KPI/summary reports) |
| **GL posting service** | `services/healthcare_posting.py` — all financial events flow through `services/posting.py` |
| **`healthcare` module** | Added to `MODULE_REGISTRY`; sidebar gated via `forModule: "healthcare"`; `hospital` business model pre-installs it |
| **Frontend** | 11 pages under `/healthcare/` (HC Overview, Patients with `[id]` detail, OPD, IPD with `[id]` detail, Lab, Lab Tests, Procedures, HC Store, HC Reports) + `components/healthcare/primitives.tsx` |
| **Demo tenant** | `demo.hospital@easy-books.app` — 50 patients, 5 doctors, 4 wards, 200 OPD tokens, 20 IPD admissions, 80 lab orders |

### Sprint 20 Shipped ✅ (Universal Search, Auto-Update, Mobile Navigation, QB Token System)

| Feature | Notes |
|---------|-------|
| **Universal Search — Ctrl+K command palette** | `GlobalSearch.tsx` — portal overlay, 3-tier search (open tabs → `navIndex.ts` → API, 150 ms debounce); `lib/navIndex.ts` — Layer 1: sidebar nav, Layer 2: 14 quick-actions, Layer 3: 22 report aliases; `GET /api/search` — 8 entity types with expanded column coverage; prefix filter syntax (`inv:`, `cust:`, `tab:`, `acc:`, `emp:`, `jv:`, `rpt:`, `new:`, `bill:`, `prod:`, `vendor:`); recent searches in `eb.recent-searches` localStorage; keyboard-navigable (Ctrl+K / ArrowUp/Down / Enter / Esc) |
| **In-App Auto-Update System** | `UpdateAvailablePopup.tsx` — bottom-sheet notification (Update Now / Later / Skip version); `UpdateProgressScreen.tsx` — fullscreen portal with animated SVG ring, 4-phase progress labels (Pull→Compile→Bundle→Start), polls `/version.json` every 5 s, success/error states; backend `GET/POST /api/system/update/status|update|changelog`; `DashboardLayout` auto-checks on every mount for admin/owner |
| **TopNav portal dropdowns + scrollable tab strip** | `TopNav.tsx` fully rewritten — ResizeObserver scroll arrows with gradient fades, `More ▾` always outside scroll container, portal-based `position: fixed` dropdowns (avoids overflow-x clip), dark nav inversion via `--nav-*` CSS vars |
| **Mobile navigation** | `BottomNav.tsx` (core nav bar, hidden at `sm:`), `FAB.tsx` (floating new-entry button with module-gated options), `MoreDrawer.tsx` (slide-up full nav sheet filtered by installed modules) |
| **Settings 5-tab layout** | `/settings` restructured: Company / Accounting / Preferences / Advanced / Updates tabs |
| **QB UI token system** | All 155+ pages/components migrated from hardcoded hex to CSS custom properties — `--bg-page`, `--bg-card`, `--border`, `--text-primary`, `--text-secondary`, `--text-muted`, `--primary*`, `--nav-*`; dark mode entirely token-driven; no scattered `dark:` class workarounds |

### Sprint 21 Shipped ✅ (Print Overhaul, Freeze Panes, Dashboard Upgrades — #126–#132)

| Feature | Notes |
|---------|-------|
| **Print overhaul (#126)** | Courier New dot-matrix B&W across all printouts; Tailwind v4 font-size variable caps; compressed row spacing; GL ledger landscape (`7639d4d`, `a420ddb`, `ebc174f`, `210297b`) |
| **Clickable aging buckets** | AR/AP aging bucket summary cards filter the items table on click; "Show all" resets (`210297b`) |
| **Freeze panes (#127)** | `.table-freeze` bounded scroll viewport engages sticky header + totals row; `.freeze-col` first-column lock; print-reset; rolled out across all table report views (`00cd56b`) |
| **Unified KpiCard (#128)** | Single `components/dashboard/KpiCard.tsx` with tone tokens + CSS theme vars replaces PrimaryKpi/SecondaryKpi across all 10 dashboard tiles (`8deef23`) |
| **Net Worth Trend widget (#130)** | `GET /api/reports/dashboard/net-worth` + Chart.js combo widget (diverging bars + line, range pills, legend toggles); #129 closed as duplicate (`574b105`) |
| **Top-10 widgets (#131)** | Top Customers and Top Products expanded from 5 to 10 entries (`a903127`) |
| **Uniform dropdown items (#132 + v3.1 icons)** | Section-dropdown overview rows styled as normal menu items; every top-menu dropdown item and mobile More-drawer item renders icon + label (`34c19bb` + nav-icons commit) |

### Sprint 22 Shipped ✅ (AI Financial Assistant — #112 Level 1)

| Feature | Notes |
|---------|-------|
| **AI chat endpoint** | `routers/ai_chat.py` — `POST /api/ai/chat`: Anthropic agent loop (max 6 steps) over 7 read-only report tools calling existing tenant-scoped report functions directly (`704540d`) |
| **`ai_assistant` module** | Added to `MODULE_REGISTRY` (Intelligence, pro tier, default off); gate enforced server-side (403) and in the frontend FAB (`704540d`, `eca27cf`) |
| **Chat UI** | `AIChat.tsx` portal panel (quick prompts, session-only history) + `AIChatButton.tsx` Sparkles FAB, mounted in the dashboard layout (`704540d`) |
| **Hardening (review fixes)** | Typed Anthropic error mapping (503/429/502), 4,000-char message + 20-turn history caps, `Literal` role validation, `is_error` tool results (`eca27cf`) |

**Deferred follow-ups:** async endpoint (`AsyncAnthropic`) if concurrent chat load grows; model upgrade `claude-sonnet-4-6` → `claude-sonnet-5` (needs a deliberate pass — adaptive thinking defaults on there and consumes the 2,048-token output cap).

### Sprint 23 Shipped ✅ (Purchase Demand + Comparative — #137 Phase 1)

Commit range `91635ea..HEAD`.

| Feature | Notes |
|---------|-------|
| **Models + migration** | `PurchaseDemand`/`PurchaseDemandLine`, `VendorQuotation`/`VendorQuotationLine`, `ComparativeStatement`; `PurchaseOrder.demand_id`/`comparative_id` FKs; `0029_purchase_demand_comparative` (`91635ea`) |
| **`purchase_store` module** | Added to `MODULE_REGISTRY` (Operations, free tier, deps `[inventory]`); pre-installed for `manufacturing`; `purchase.demand`/`purchase.comparative` permission resources (`6a150a4`) |
| **Demand router** | CRUD + approve/cancel/close; self-approval block; `my_data_only` via `apply_own_filter` (`62666cb`) |
| **Quotation router** | Per-vendor pricing against demand lines; freezes once the CS is approved/converted (`d56b0dc`) |
| **Comparative router** | Matrix serialization, lowest-or-justify approval, completeness check, convert-to-PO (`591df5f`) |
| **Chain enforcement** | `require_purchase_chain` setting (default on); `POST /api/purchase-orders` requires an approved comparative once `purchase_store` is installed (`e43b259`) |
| **Nav** | Dedicated Purchases section; `notForModule` dual-home gating so Manufacturing's PO/GRN entries hide once `purchase_store` takes over (`3cffcd0`) |
| **Frontend** | Demand list/detail/new/edit + print, per-vendor quotation entry, comparative matrix builder with lowest-rate highlighting + convert-to-PO (`f697a7e`, `260c393`, `9bec8af`, `f32941b`) |
| **Review-driven fixes** | Tenant ownership + CS-demand match on PO create (`8b4886a`); CS approve rejects dangling selection/partial quotations (`3446f45`); vendor validated on quotation update (`4b4f1b2`); qty predicate unified between totals and payload (`91be7f1`); matrix tie-safe justification note (`9fe4d34`) |
| **Tests** | 14 tests in `backend/tests/test_purchase_flow.py` covering module registration, permission resources, demand lifecycle/self-approval/tenant isolation, quotation validation/freeze, CS lowest-or-justify/approval/conversion, and chain enforcement with/without the module |

**Deferred to Phase 2:** uninstall-blocked-while-documents-exist for `purchase_store` — the modules router has no per-module uninstall hooks today; the generic mechanism belongs with the module's completion.

### Sprint 24 Shipped ✅ (Gate Inward — #137 Phase 2)

Commit range `d83216b..864fbcd` (merged to `main`).

| Feature | Notes |
|---------|-------|
| **Models + migration** | `GateInward`/`GateInwardLine`; `purchase.gate` permission resource; `0030_gate_inward` (`493a477`) |
| **Coverage service** | `services/gate.py` — `gi_coverage`/`po_fully_covered`, pure logic, no GL (`86edb80`) |
| **Gate Inward router** | Create/list/get/cancel; per-line qty caps (accumulated across duplicate lines in one request, closing a review-found bypass); PO approved↔received recompute on create and cancel (`3c5e7aa`, fix `c42c559`) |
| **Billing gate** | `require_gate_inward` setting; `convert-to-bill` blocked until full coverage; GIs flip to `billed` on conversion (`3bad647`) + settings UI toggle (`e2338a4`) |
| **Reports** | Gate Register + 3-Way Match endpoints (`66787bd`, fix `093cda4` for a `my_data_only` bypass) |
| **Uninstall guards** | Generic `MODULE_UNINSTALL_GUARDS` registry — `purchase_store` blocked while demands/quotations/comparatives/GIs exist (`079a9fd`) |
| **Tenant-filter hardening** | Defense-in-depth joins on Phase-1 quotation/comparative subqueries, carried over from Phase 1's final review (`dbd1b66`) |
| **Frontend** | Gate Inward list/new/detail + nav (both `NAV` and `SUB_NAV` registries — a nav-only regression from the prior PR is the reason this dual-registration is now a standing checklist item) (`74a06a6`); report pages + PO-detail coverage gate (`7c43948`) |
| **Final-review fix** | Mutating GI endpoints required only view-level `purchase.gate`; added `edit`-level dependency (`864fbcd`) |
| **Tests** | 17 tests in `backend/tests/test_gate_inward.py` |

### Sprint 25 Shipped ✅ (Gate Outward — #137 Phase 2b)

Commit range `e6e947a..1e7106a` (merged to `main`).

| Feature | Notes |
|---------|-------|
| **Models + migration** | `GateOutward`/`GateOutwardLine` (`source_doc_type` discriminator); `store.gate_outward` permission resource (new **Store** category); `0031_gate_outward` (`a0dd6ab`) |
| **`consume_stock` extension** | Optional `source_doc_type` override (default `"invoice"`, fully backward-compatible) so non-sale consumers tag their own `StockMovement` rows (`851c4b6`) |
| **Memo-exit router** | Invoice/debit-note exits create straight to `approved` — reconciliation, not enforcement, since stock already left the books at invoice creation; no checkpoint exists to block on (`1f651b9`) |
| **Scrap workflow** | Draft→approve; approval consumes stock and posts two balanced JVs (`28bceb0`); row-locked with `with_for_update()` after a final-review finding on a double-approval race (`1e7106a`) |
| **Reports** | Gate Outward Register + Dispatch Reconciliation (`792546e`, fix `2333765` for the same `my_data_only` bypass class Phase 2 hit) |
| **Permission hardening** | Edit-level `store.gate_outward` on mutating endpoints (`a82f995`) |
| **Frontend** | New **Store** top-level nav section (7 distinct `nav.ts` edits) + Gate Outward list/new/detail (`5d83e3b`); report pages (`ee14bbb`) |
| **Tests** | 14 tests in `backend/tests/test_gate_outward.py` |

**Demo data (v3.5):** `_seed_purchase_store_chain` in `scripts/seed_demo.py` (`e57acf3`) — every Phase 1/2/2b screen and report was empty in the demo tenant until this; now exercises every document status (6 demands, 3 comparatives, 4 POs across partial/full/short-received and billed/unbilled, Gate Inward including a cancel-and-re-enter, Gate Outward across all three source types including an approved scrap entry with real GL).

### Sprint 26 Shipped ✅ (Report Period Presets — #141)

Branch `feat/report-period-presets`.

| Feature | Notes |
|---------|-------|
| **`week_start_day` setting** | Backend KV setting (default `monday`) + Settings page dropdown; drives the week-based presets (`00c5814`) |
| **`datePresets.ts` resolver** | 26 QuickBooks-style presets (Today → Last Fiscal Quarter), pure functions `resolvePreset`/`matchPreset` parameterized by `{today, fiscalStartMonth, weekStartDay}`; first vitest suite in the repo (18 tests) (`1de63b2`) |
| **`DateRangePicker` preset dropdown** | Preset select ahead of From/To with unchanged prop contract — all 14 existing consumers gained presets with zero edits; preset fills + disables the inputs, "Custom" re-enables; `matchPreset` re-selects the preset when a range is restored from URL params (`eb82750`) |
| **Report page sweep** | Hand-rolled `<input type="date">` from/to pairs replaced with the shared component across core/AR/AP (statements, audit, analytic P&L, attendance report, telecom tracker — `854c146`) and purchases/store/healthcare registers (`179f495`) |

### Sprint 27 Shipped ✅ (Leftover Cleanup Batch + AI Chat Review + Seed Data Upgrade)

Four stacked leftover-cleanup PRs (#149→#150→#151→#152, each retargeted straight to `main` after GitHub auto-closed two of them when their stacked base branches were deleted mid-merge — recovered by reopening fresh PRs #154/#155 from the same branches), plus a frontend review pass and a correctness fix found while building demo data around the new overdue feature.

| PR | Feature | Notes |
|----|---------|-------|
| **#149** | FK-cycle fix + gate-permission decoupling + freeze panes | `ComparativeStatement.po_id` / `HcBed.current_admission_id` (a second, previously undocumented cycle) declared `use_alter=True`, making `sorted_tables` deterministic; demo purge nulls both back-pointers first. `GET /api/gate-inwards/pos` + `/pos/{id}` — gate-scoped, price-free PO views so a `purchase.gate`-only user never needs `purchase_orders` rights; GI serializer now carries line description/unit. `/pl` + `/balance` single-period trees gained real `<thead>` + `.table-freeze`. |
| **#150 → #154** | Report pagination | Gate Register, 3-Way Match, Gate Outward Register, Dispatch Reconciliation, Issue Register all move from bare arrays + Python-side substring filtering to `{total, items}` with `skip`/`limit` and SQL `ilike` search; Dispatch Reconciliation is a SQL `UNION ALL` of invoices + debit notes. Frontend: shared `Pagination` component (50/page) on all five report pages. |
| **#151 → #155** | Overdue automation | `services/overdue.py` — `sweep_overdue()` (cross-tenant SQL `UPDATE`) + `send_overdue_reminders()` (one email per customer, throttled via `overdue_reminder_interval_days`), wired into `main.py`'s FastAPI lifespan as a background asyncio task. New Settings field. |
| **#152 → #155** | Anthropic default model → Claude Sonnet 5 | Not a bare string swap — Sonnet 5 runs adaptive thinking ON when `thinking` is omitted (silent behavior change from 4.6) and thinking output shares the reply's fixed `max_tokens`; `routers/ai_chat.py` now sends `thinking: {"type": "disabled"}` gated to anthropic calls only. |
| **#153** | AI chat frontend review | Two real bugs: `/agent` sidebar never picked up a session's auto-generated title after its first message (no refetch wired); composer textarea had `max-h-24 overflow-y-auto` in its className but no resize JS, so it never actually grew past one line. Both fixed with a Playwright-verified round trip. |
| **#156** | `sweep_overdue` status-vocabulary bug | Found immediately while building seed data around #151: the sweep targeted `status IN ("open", "sent")`, but nothing in `routers/invoices.py` ever sets `"open"` — dead vocabulary. The real issued-but-unpaid status this app produces is `"posted"`. The merged PR's own test passed only because its test helper used the same synthetic `"open"` value. Fixed to `("posted", "sent", "open")`, deliberately still excluding `"draft"` (sweeping a draft would email a customer about an invoice they were never sent). |
| **#157** | Seed data upgrade | `email_notifications=true` for every demo tenant (was never set, so `send_overdue_reminders()` silently skipped all of them); Store Issue seeding bumped 4→60 rows so the Issue Register's new Pagination control has something to page through on first login. |
| **#160 → #161** | Permissions matrix dead-resource audit | A registered `PERMISSION_RESOURCES` entry is not self-enforcing — the admin matrix shows it as togglable regardless of whether any route checks it. Systematic `perm_dep(` call-site vs. registry diff found 22/75 dead. **#160:** `reports.py` imported `perm_dep` and never called it (12 `report.*` resources — trial balance, income statement, balance sheet, cash flow, GL, customer/inventory performance, tax, budget-vs-actual, product ledger, AR/AP aging — any authenticated user could view every financial report regardless of role/permission settings), fixed with per-route `dependencies=[perm_dep("report.xxx")]` in `reports.py`/`aging.py`; `customer_ledger`/`vendor_ledger` were unused on the `/statement` endpoints, fixed by layering the ledger resource on top of the coarser `customers`/`vendors` router-level gate (route-level + router-level dependencies stack, both must pass); `team` deleted from the registry (zero effect since `users.py` is hardcoded `AdminUserDep`). **#161:** `telecom.py`'s 54 endpoints all shared one router-level `perm_dep("telecom.tracker")` at `view` level — the other 8 `telecom.*` resources were dead, and every POST endpoint only required view access, not edit. Router-level dependency removed, replaced with 9 independently-scoped per-route resources (`telecom.tracker`/`rso`/`sim`/`fca`/`mobile_money`/`postpaid`/`commissions`/`franchise`/`devices`, view for GET / edit for POST). Registry now 74 resources (was 75). `backend/tests/test_report_permissions.py` + `backend/tests/test_telecom_permissions.py` verify each previously-dead resource now 403s on an explicit `none` override without affecting unrelated resources. |

### Sprint 28 Shipped ✅ (AI Chat Reliability + Ollama as a 4th Provider — #162–#165)

Four user-reported bugs/gaps in the AI Financial Assistant, found and fixed in sequence — #163 was only diagnosable *because* #162 shipped first.

| PR | Feature | Notes |
|----|---------|-------|
| **#162** | Mid-stream errors were silently swallowed | `stream()`'s `except Exception` block only ever let `type(exc).__name__` reach the client, and logged nothing server-side — a bad model/key/rate-limit failure was undiagnosable from either side. Now prints `[ai_chat] <Type> for model=<model>: <detail>` to stdout and sends a truncated (300 char) `str(exc)` in the SSE `error` event. |
| **#163** | `gemini-2.5-flash` dead for newer Google API keys | Google's own 404: "no longer available to new users." It was the hardcoded first (= default) entry in `PROVIDERS["gemini"]["models"]`, with no recovery path since the UI only offers models from that list. Replaced the defaults with Google's auto-updating `-latest` aliases (`gemini-flash-latest`/`gemini-pro-latest`) plus `gemini-2.0-flash`; dated `2.5-*` IDs kept selectable for keys that still have access. Settings page had its own separately-hardcoded copy of this list — updated to match. |
| **#164** | Ollama (self-hosted) as a 4th provider | Structurally different from the cloud providers: no secret key, and no fixed model catalog (a tenant runs whatever they've locally `ollama pull`led). `ollama_models()`/`ollama_base_url()` resolve tenant-specific `ai_ollama_models`/`ai_ollama_base_url` settings instead of a static list; `validate_model()` grew a 3rd return value (`api_base`, non-`None` only for ollama). `ai_chat.py` translates `ollama/<tag>` → `ollama_chat/<tag>` only at the `litellm.acompletion` call site (litellm needs that prefix for OpenAI-style tool-calling+streaming) — stored/displayed form stays `ollama/<tag>`. Settings → AI gained a server-URL input + a tag-input (Enter/`,` to add, × to remove) since there's no key field to show. |
| **#165** | Assistant reply bubble renders blank | When a model finishes a turn having only ever emitted `tool_calls` with zero content deltas (some providers skip a closing summary), the backend's fixed fallback string was computed *after* streaming ended and never sent as a `token` event — `ChatCore.tsx` committed the bubble purely from its locally-accumulated token buffer, which was empty. Fixed by riding the authoritative final text on the `done` event itself (`reply` field); `ChatCore`'s `onDone` now prefers it over the local buffer. |

### Sprint 29 Shipped ✅ (Draggable/Minimizable Floating Panels + Global Calculator v1 — #166)

| PR | Feature | Notes |
|----|---------|-------|
| **#166** | `hooks/useDraggablePanel.ts` + Calculator widget | Shared drag-anywhere + minimize state hook, extracted (not duplicated) since the AI Assistant FAB and a new Calculator widget both need the identical pointer-event state machine (drag-offset tracking, viewport clamping on move *and* resize, minimize persistence to `localStorage` as a per-browser UI preference, not tenant data). `AIChat.tsx` refactored onto it, gaining a Minimize/Restore button. New `Calculator.tsx` + `CalculatorButton.tsx` — standard 4-function calculator (+ − × ÷, %, ± , C, backspace), 12-digit cap, mounted **unconditionally** (no module gate) per "globally available." |

### Sprint 30 Shipped ✅ (Casio-Style Calculator Overhaul — #167–#170, #177)

The v1 calculator from Sprint 29 had real arithmetic bugs, caught via a TDD pass that extracted its logic into a standalone, unit-tested engine module for the first time.

| PR | Feature | Notes |
|----|---------|-------|
| **#167** | TDD bug fixes + Casio HL-122 restyle | New `frontend/src/lib/calculatorEngine.ts` — pure state-transition functions (`inputDigit`, `inputOperator`, `pressEquals`, `backspace`, `toggleSign`, `percent`, `sqrt`, `formatResult`), extracted from `Calculator.tsx`'s inline `useState` logic so it's independently testable (34 new tests). Found and fixed 3 real bugs: percent ignored the pending operator (`200+10%` computed `200.1` instead of `220`); pressing an operator twice in a row (`5 + ×`) recomputed using the same operand twice; backspacing a negative number down to a lone `-` left the display unparseable instead of resetting to `0`. Visual restyle to a silver-chassis, black-LCD-bezel, navy/maroon/teal key skin inspired by the Casio HL-122. |
| **#168** | 12-digit display fit + √/00 keys | The LCD's fixed `text-4xl` font didn't fit 12 digits — now scales down (`text-4xl`→`text-xl`) as the display string grows. Added `√` (composes with a pending operator) and `00` (thin wrapper reusing `inputDigit`'s existing leading-zero/cap logic — no new edge cases). Grid reflows to 4×6 with `0` and `=` as double-wide bottom keys. |
| **#169** | 2-line expression history | New `expression: string` field on `CalcState` — builds a running history line (`"123+456+789+"`) above the main result as you chain operations, finalizing to `"200+300="` on equals, matching a typical 2-line business calculator (MAUL MTL-600 reference). Handles operator-swap (replaces the trailing symbol, doesn't duplicate), continuing from a finished result (line restarts from that result, doesn't go stale), and percent/√ composing transparently into the final line. |
| **#170** | Percent bug #2 — inconsistent across operators | The `×`/`÷` branch of `percent()` computed a *bare fraction* (`current/100`), discarding the base entirely — since 10 is the number everyone naturally tests a percent key with, `<anything> × 10%` always displayed exactly `0.1` regardless of the first operand. Reported as "% always showing 0.1." Fixed to one rule for every operator: percent always means "the entered number, as a percentage of the pending operand" — matches the already-correct `+`/`-` behavior. |
| **#177** | Physical keyboard support | The calculator only ever handled `onClick` — a `keydown` listener now maps `0-9`, `.`, `+ - * /`, `Enter`/`=`, `Backspace`, `Delete`/`Escape`, `%` through the same tested engine functions. Guards against stealing keystrokes from the rest of the app: bails out immediately if `document.activeElement` is an input/textarea/select/contenteditable, since the calculator is a floating widget that can stay open in the background while the user fills out an unrelated form. |

### Sprint 31 Shipped ✅ (AI Chat Agentic Pipeline — Triage → Specialist → Drafting — #171–#176, #178)

Restructures the AI Financial Assistant from one large agent call per turn into a 3-stage pipeline, so an expensive model is only paid for on the one stage that needs real reasoning. See the "AI Financial Assistant" entry under `### AI Financial Assistant (/api/ai)` above for the full architecture.

| PR | Feature | Notes |
|----|---------|-------|
| **#171** | Markdown rendering + `stage` SSE frame | No markdown renderer existed anywhere in this frontend — a formatted reply would have shown literal `\| pipe \| characters \|`. New `ChatMarkdown.tsx` (`react-markdown` + `remark-gfm`) with table/heading overrides styled against the app's theme vars. New `stage` SSE frame type, wired into the existing single tool-progress label (no new UI) — dead code until the backend started emitting it in #174. |
| **#172** | `run_tool_loop()` extraction | Pure refactor: the ~130-line inline tool-calling loop becomes a reusable async generator, parameterized by tool subset + `yield_tokens` flag, so a later specialist-agent path and the original general path can share one implementation. Locked in by `test_ai_chat_stream.py` passing **unmodified**. |
| **#173** | `AiChatMessage.agent` column | Nullable column recording which specialist handled a turn, for future debugging/analytics. Migration follows the `has_column`-guard pattern (`0025_product_cost_method.py`) since dev also bootstraps via `create_all()` — an unguarded `ADD COLUMN` collided with a fresh DB that already had the column from the model, caught by the packaged-entrypoint migration test. |
| **#174** | Triage stage + agent registry | New `services/ai_agents.py` — a frozen-dataclass registry (mirrors `services/report_sources`) of 4 agents built against the existing 7 read-only tools: `receivables`, `payables`, `financial_reports`, and a `general` fallback reproducing the original single-agent behavior verbatim. New `CHEAP_TIER` mapping (`claude-haiku-4-5`/`gpt-4o-mini`/`gemini-flash-latest`) + `resolve_cheap_tier()` in `ai_providers.py` — used for a one-shot, non-streaming classification call (`max_tokens=20`) that routes each message to one agent's narrowed tool subset. Any triage failure (bad response, provider error) falls back to `general` silently — never aborts the request. |
| **#175** | Drafting stage | The specialist's tool loop flips to `yield_tokens=False` — its own text is fully accumulated but never streamed to the client. A new cheap-tier, streaming, no-tools completion (`_run_drafting`) rewrites the specialist's findings + raw tool results into polished Markdown (tables, headings, verbatim figures) — this is now the *only* text that streams to the user and gets persisted. Falls back to the specialist's raw text if drafting itself produces nothing. |
| **#176** | Docs pass | `CLAUDE.md`'s `routers/ai_chat.py`/`services/ai_providers.py` rows updated for the 3-stage pipeline; new `services/ai_agents.py` row. |
| **#178** | In-chat Model & API Key button/window | Closed a real discoverability gap: `ChatCore`'s model picker only rendered when a provider was already configured, so a fresh install's chat UI showed nothing at all — no button, no message — until the user sent a message and read a plain 503 error with no link anywhere. New `AiModelKeyPanel.tsx`, opened from a button that's now **always visible**: Model selection (all users) + API Key management (admin/owner only, same frontend gate `Settings → AI` already used) with a link out to the full Settings page for Ollama/rate-limit config. Saving a key refreshes the model list live. |

### Sprint 32 Shipped ✅ (AI Full-Spectrum Agents + Reviewer Stage — PRs #185–#188, v3.8)

Extends the agentic pipeline from 3 base domains / 7 tools to every business domain in the app (11 agents, ~50 tools), and inserts a data-accuracy Reviewer stage between Specialist and Drafting. See `### AI Financial Assistant (/api/ai)` above for the resulting architecture. Backend-only — no frontend, schema, or migration changes (the new "Reviewing figures…" stage label flows through the existing `stage` SSE frame).

| PR | Feature | Notes |
|----|---------|-------|
| **#185** | Tool registry refactor + Reviewer stage | New `services/ai_tools.py` — frozen `ToolDef` registry (mirrors `report_sources`); `ai_chat.py`'s hand-wired `TOOLS`/`OPENAI_TOOLS`/`TOOL_LABELS`/`_execute_tool` become derivations (`openai_tools`/`tool_labels`/`execute_tool`), so a new tool is one entry, not a 4-place edit. Oversized tool results truncate at 15k chars. New `_run_reviewer` — cheap-tier, non-streaming silent fact-check of the specialist's figures against raw tool results; skipped on no-tool turns; any failure falls back to the unreviewed text. Pipeline's four LLM calls stay distinguishable by unique `(stream, max_tokens)` = 30/1500/2048/4096 (test fakes depend on it). Import-time assert: every `AgentDef.tools` name must exist in `TOOL_REGISTRY`. |
| **#186** | Base-domain tools + Sales agent | 11 base tools: balance sheet, tax summary, budget vs actual, net-worth trend, customer performance, customer/vendor statements + ledgers, and `find_customer`/`find_vendor` (tenant-scoped `ilike` name→id lookups, 10-match cap — ID-requiring tools return a recoverable error naming the lookup tool). New `sales` agent (performance/analysis, hint contrasted against receivables' who-owes-money); receivables/payables/financial_reports extended. |
| **#187** | Module-gated agents for all domains | 6 agents (`inventory`, `payroll`, `healthcare`, `telecom`, `purchasing`, `manufacturing`) using the `required_module` gating wired-but-unused since Sprint 31, + ~29 tools wrapping the existing module report routers. Executors absorb the `(user, session)` arg order of hrm/healthcare functions; registers pin `skip=0, limit=50`. Runtime `filter_by_modules` re-filters specialist tool subsets by installed modules (defense in depth). `_json_safe` extended to date/datetime→ISO. Agent-key invariant (no key a substring of another — triage's fallback matcher is bidirectional-substring) now test-enforced. |
| **#188** | Generic report-builder tools | `list_report_sources` (discovery — sources filtered to installed modules, per-source field metadata) + `run_custom_report` (ad-hoc columns/filters/group-by/aggregates/sort/date-range queries over `report_engine.run_report`, which injects `tenant_id` unconditionally and whitelists every field; AI wrapper adds a source→module gate and a 50-row cap). Granted to `general` + `financial_reports` — covers the long tail no fixed tool answers. |

### Still Pending

**Manufacturing track (V2 follow-ups)**
- Production-order **reversal helper** (currently requires manual JE reversal).
- **Overhead / labour absorption** at PO start.
- **Partial delivery** endpoint (currently one delivery = full output_qty).
- ~~**Damage / scrap** endpoint for inventory write-off~~ — shipped as Gate Outward's scrap path (#137 Phase 2b, Sprint 25): draft→approve, GL posted at approval. Still open: a *production-order-specific* damage/scrap reason code (today it's a general Store-level entry, not tied to a `ProductionOrder`).
- **Multi-output BoMs** (joint-product manufacturing).
- **By-product handling** with separate cost allocation.

**Core platform**
- **Multi-currency on payments** (currently invoice currency is snapshot at issue; payments assumed in base currency).
- ~~**Daily overdue sweep cron**~~ — fixed 2026-07-14: `services/overdue.py` (`sweep_overdue` + `send_overdue_reminders`), wired into `main.py`'s FastAPI lifespan as a background asyncio task (fires on boot, then every `OVERDUE_SWEEP_INTERVAL_HOURS`, default 24; `OVERDUE_SWEEP_ENABLED=false` disables it). One email per customer with all their overdue invoices, throttled per tenant via the new `overdue_reminder_interval_days` setting (default 7 days) against an internal `overdue_last_reminder_date` KV marker.
- **E2E tests** (Playwright) — login, signup wizard, full PO lifecycle in the UI.
- ~~**Payroll module** (IAS 19)~~ — shipped (routers/payroll.py + attendance: employees, salary components, runs with GL posting `Dr Salary Expense / Cr Salaries Payable`, payslips). This line had gone stale — the module predates this edit.
- ~~**Overdue email reminders**~~ — fixed alongside the sweep cron above (same PR).
- ~~**`ComparativeStatement`↔`PurchaseOrder` FK cycle**~~ — fixed 2026-07-14 (with a second, previously undocumented `HcBed`↔`HcAdmission` cycle): the nullable back-pointers (`po_id`, `current_admission_id`) now declare `use_alter=True` so `sorted_tables` is deterministic and warning-free, and the demo purge nulls them per tenant before its reverse-order deletes (Postgres-safe).

**Purchase/Store follow-ups (#137 carry-ins)**
- ~~Concurrency: `FOR UPDATE` row lock on Gate Inward create/cancel and PO convert-to-bill~~ — fixed 2026-07-12 (`fix/purchase-store-debt`): all three sites now use the same `with_for_update()` idiom as Gate Outward's scrap approve.
- ~~Report pagination + SQL-side search on Gate Register / 3-Way Match / Gate Outward Register / Dispatch Reconciliation~~ — fixed 2026-07-14 (Issue Register included for parity): all five return `{total, items}` with `skip`/`limit` + `ilike` search in SQL; dispatch reconciliation is a SQL UNION of invoices + debit notes so paging/ordering span both.
- ~~`purchase.gate` + `purchase_orders` permission coupling~~ — fixed 2026-07-14: gate-scoped PO views `GET /api/gate-inwards/pos` + `/pos/{id}` (gated by `purchase.gate`, deliberately price-free — gate work is quantity-only) and the GI serializer now carries line description/unit; the Gate Inward pages no longer call the PO API at all.
- ~~Phase 3 (Store Issue + GL posting + `/purchases` hub page) and Phase 4 (vendor performance analysis, seeder, docs)~~ — shipped in PR #145 (2026-07-11); issue #137 closed.

**Stock Tie-out follow-ups (#145 final review)**
- ~~`reverse_purchase` (bill void/edit) mutates `stock_qty` with no `StockMovement`~~ — fixed 2026-07-12: emits `ADJUSTMENT`/`bill_void` rows; tie-out sign map extended.
- ~~`POST /api/products` + CSV import `opening_qty` bootstrap writes no `StockMovement`/`InventoryLayer`~~ — fixed 2026-07-12: both route through `record_purchase(source_doc_type="opening", posted_to_gl=False)`.
- ~~Vendor performance counts pending zero-GI POs as 100% short-receipt~~ — fixed 2026-07-12: gate-less POs excluded from the short-receipt numerator/denominator (still counted in `po_count`).
- Manual physical-count adjustments store `abs(variance)` signless, so the tie-out deliberately cannot absorb them (residual variance after a count override is the intended signal — see `_STOCK_QTY_SIGN` comment in `routers/store_reports.py`). By design for now; revisit only if a signed delta becomes a requirement.

**Developer ergonomics**
- **Storybook** for guidance components + form patterns.

---

> **Document maintenance.** Every shipped commit that adds or removes a model, endpoint, or invariant should update this blueprint *and* `WORKFLOW.md`. Keep `README.md` light (the elevator pitch); push detail down here.
