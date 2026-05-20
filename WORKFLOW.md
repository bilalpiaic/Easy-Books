# Easy-Books — Workflow & Architecture Guide

> Multi-tenant double-entry accounting SaaS
> FastAPI + SQLModel + Alembic (backend) · Next.js 16 + React 19 + Tailwind v4 (frontend)
> SQLite for dev, PostgreSQL-ready for prod · JWT + HttpOnly cookie auth · RBAC · CSRF · idempotency · multi-currency

---

## TABLE OF CONTENTS

1. [Snapshot](#1-snapshot)
2. [Architecture](#2-architecture)
3. [Data Model](#3-data-model)
4. [The Six Accounting Cycles](#4-the-six-accounting-cycles)
   - 4.1 [Sales / Receivables](#41-sales--receivables)
   - 4.2 [Purchase / Payables](#42-purchase--payables)
   - 4.3 [Inventory (Weighted-Average)](#43-inventory-weighted-average)
   - 4.4 [Banking & Reconciliation](#44-banking--reconciliation)
   - 4.5 [Manual Journal Entries](#45-manual-journal-entries)
   - 4.6 [Period-End Close](#46-period-end-close)
5. [Cross-Cutting Features](#5-cross-cutting-features)
   - 5.1 [Multi-Currency & FX](#51-multi-currency--fx)
   - 5.2 [Tax Codes](#52-tax-codes)
   - 5.3 [Payment Allocations](#53-payment-allocations)
   - 5.4 [Recurring Entries](#54-recurring-entries)
   - 5.5 [Bank Statement Import](#55-bank-statement-import)
   - 5.6 [Reversal Semantics](#56-reversal-semantics)
6. [GL Posting Reference](#6-gl-posting-reference)
7. [Report Catalog](#7-report-catalog)
8. [API Endpoint Catalog](#8-api-endpoint-catalog)
9. [Security Model](#9-security-model)
   - 9.1 [Multi-Tenant Isolation](#91-multi-tenant-isolation)
   - 9.2 [RBAC](#92-rbac)
   - 9.3 [Auth: JWT + HttpOnly Cookie](#93-auth-jwt--httponly-cookie)
   - 9.4 [CSRF (Double-Submit-Cookie)](#94-csrf-double-submit-cookie)
   - 9.5 [Login Throttle](#95-login-throttle)
   - 9.6 [Period Lock](#96-period-lock)
   - 9.7 [Idempotency Keys](#97-idempotency-keys)
10. [Engineered Invariants](#10-engineered-invariants)
11. [Verification & Smoke Tests](#11-verification--smoke-tests)
12. [Default Chart of Accounts](#12-default-chart-of-accounts)
13. [Migration History](#13-migration-history)

---

## 1. SNAPSHOT

| Aspect | Detail |
|---|---|
| Purpose | Multi-tenant double-entry accounting — GL, invoicing, billing, inventory, banking, multi-currency, tax, period close |
| Accounting compliance | ∑Dr = ∑Cr exact (Decimal), IAS 2 / ASC 330 inventory at WAvg, GST output/input separated, period-lock enforced at the posting service |
| Multi-tenancy | One `Tenant` per business; every record carries `tenant_id`; queries scope to it; central posting service double-checks account ownership |
| Auth | JWT bearer **and** HttpOnly cookie; CSRF on cookie path; bcrypt password hashing |
| Roles | `owner | admin | accountant | viewer` (CHECK-constrained at DB) |
| Storage | SQLite (dev) → Postgres (prod) via SQLModel; Alembic migrations 0001 → 0009 |
| Reports | Live from `JournalEntry`; closed periods read materialised `AccountBalance` |
| API surface | 80+ endpoints, mounted twice at `/api/*` and `/api/v1/*` |

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
├── alembic.ini · alembic/versions/
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
```

**Read it as:** every business is a `Tenant`. Every operational document (invoice, bill, payment, manual JV) ultimately writes a `Transaction` (the JV header) with 2+ `JournalEntry` rows. Reports aggregate `JournalEntry` directly.

---

## 4. THE SIX ACCOUNTING CYCLES

### 4.1 SALES / RECEIVABLES

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

| # | Action | Page | Endpoint | DB writes | GL impact |
|---|---|---|---|---|---|
| 1 | Add customer | `/customers` | `POST /api/customers` | `Customer` | — |
| 2 | Issue invoice | `/invoices` | `POST /api/invoices` | `Invoice` + lines + `Transaction` + JEs (+ COGS sub-JV for stock) | **Dr AR · Cr Revenue · Cr GST Payable (Output)** |
| 3 | Receive payment | `/payments-received` | `POST /api/payments-received` | `PaymentReceived` + `Transaction` + JEs + `PaymentAllocation[]` | **Dr Cash/Bank · Cr AR** |
| 4 | View aging | `/invoices` (aging panel) | `GET /api/invoices/aging` | — | Buckets net of allocations |

**Invoice GL — service sale, 1000 + 17% GST, base currency:**
```
                              DEBIT       CREDIT
1100 Accounts Receivable     1,170.00
4000 Sales Revenue                       1,000.00
2200 GST Payable (Output)                  170.00
                             ─────────   ─────────
                             1,170.00    1,170.00 ✓
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

A single payment can settle multiple invoices/bills with partial amounts:

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

## 6. GL POSTING REFERENCE

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
| Ledger | `GET /api/reports/ledger?account_id=…` | JEs grouped by account, running balance per row |
| Trial Balance | `GET /api/reports/trial-balance?start=…&end=…` | `SUM(debit), SUM(credit)` per account; verifies ∑Dr = ∑Cr |
| Income Statement | `GET /api/reports/income-statement` | Revenue (4xxx) − Expense (5xxx) for date range |
| Balance Sheet | `GET /api/reports/balance-sheet` | Assets = Liabilities + Equity (incl. current-period retained earnings) |
| Cash Flow | `GET /api/reports/cash-flow` | Indirect method: Net Income + non-cash + Δ working capital |
| Tax Summary | `GET /api/reports/tax-summary` | Output GST (2200) − Input GST (1250) = Net GST Payable; income-tax slab estimate |
| AR Aging | `GET /api/invoices/aging` | Buckets 0–30/31–60/61–90/90+ of **outstanding** (gross − sum(allocations)) |
| AP Aging | `GET /api/bills/aging` | Same for bills |
| Dashboard KPIs | `GET /api/reports/dashboard` | Revenue, expense, AR/AP outstanding (net of allocations), overdue counts, low stock |
| Dashboard charts | `GET /api/reports/dashboard/charts?months=12` | 12-month series for chart components |

---

## 8. API ENDPOINT CATALOG

Every route is mounted twice: at `/api/*` (legacy) and `/api/v1/*` (versioned alias). Future breaking changes ship under `/api/v2/`.

### 8.1 Auth & settings
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/signup` | Create tenant + seed CoA + `owner` user (password ≥ 8) |
| POST | `/api/auth/login` | OAuth2 password → JWT + HttpOnly cookie + CSRF cookie + body `{access_token, role, csrf_token}` |
| POST | `/api/auth/logout` | Clears both cookies |
| GET | `/api/auth/me` | Current user (email, full_name, role) |
| GET/PATCH | `/api/settings` | Company name, fiscal year start, currency display, document prefixes |

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
| GET | `/api/transactions/{id}` | JV detail with all JEs |
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
| GET | `/api/reports/dashboard/charts?months=12` | Chart series |

### 8.8 CSV bulk import (master data)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/import/{entity}/sample` | Blank CSV template |
| POST | `/api/import/accounts` \| `customers` \| `vendors` \| `products` \| `transactions` | Bulk create; per-row error collection; partial-success OK |

---

## 9. SECURITY MODEL

### 9.1 Multi-tenant isolation

Every query in every endpoint filters by `tenant_id` from the JWT. Cross-tenant lookups return **404, not 403**, to prevent enumeration. The central posting service `services.posting._check_accounts_belong_to_tenant` is a belt-and-braces check that no JV can post into another tenant's chart of accounts.

### 9.2 RBAC

| Role | Reads | Writes | Period close / lock | Account delete |
|---|---|---|---|---|
| `viewer` | ✔ | — | — | — |
| `accountant` | ✔ | ✔ | — | — |
| `admin` | ✔ | ✔ | ✔ | ✔ |
| `owner` | ✔ | ✔ | ✔ | ✔ |

DB-level `CHECK role IN ('owner','admin','accountant','viewer')`. First user of a tenant becomes `owner` at signup. Dependencies in `routers/common.py`:
- `CurrentUserDep` — any authenticated user
- `WriteUserDep` — `accountant+`
- `AdminUserDep` — `admin+`

`require_min_role(role)` factory generates more if needed.

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
- **Migrations idempotent** — each Alembic file checks the inspector before creating tables/columns.

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

Test suite: 63 pytest tests across `backend/tests/`. Run: `cd backend && .venv/bin/python -m pytest`.

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

All migrations are idempotent (check inspector before `create_table` / `add_column`), so they can safely be re-run on a fresh-baseline DB.

---

> **Last updated:** 2026-05-20
> **Branch:** `saas-transition-foundation`
> **Live demo:** `./dev.sh` (backend :8000, frontend :3000)
> **Repository:** https://github.com/bilalpiaic/Easy-Books
