# Easy-Books — Complete Workflow Brochure

> **A multi-tenant double-entry accounting platform**
> Stack: FastAPI + SQLModel + SQLite (backend) · Next.js 16 App Router + React 19 + Tailwind v4 (frontend)
> Auth: JWT (multi-tenant isolation via `tenant_id`)
> Currency: PKR (Pakistani Rupee) · Compliance baseline: GST + ITO 2001

---

## TABLE OF CONTENTS

1. [Project Snapshot](#1-project-snapshot)
2. [System Architecture](#2-system-architecture)
3. [Entity-Relationship Map](#3-entity-relationship-map)
4. [The Five Accounting Cycles](#4-the-five-accounting-cycles)
   - 4.1 [Sales / Receivables Cycle](#41-sales--receivables-cycle)
   - 4.2 [Purchase / Payables Cycle](#42-purchase--payables-cycle)
   - 4.3 [Inventory Cycle](#43-inventory-cycle)
   - 4.4 [Banking / Cash Cycle](#44-banking--cash-cycle)
   - 4.5 [Manual Journal Entry Cycle](#45-manual-journal-entry-cycle)
5. [GL Posting Reference (Dr / Cr Map)](#5-gl-posting-reference-dr--cr-map)
6. [Report Linking Matrix](#6-report-linking-matrix)
7. [Frontend Hyperlink Navigation Map](#7-frontend-hyperlink-navigation-map)
8. [CSV Bulk Import Flow](#8-csv-bulk-import-flow)
9. [API Endpoint Catalog](#9-api-endpoint-catalog)
10. [Multi-Tenant & Security Model](#10-multi-tenant--security-model)
11. [Engineered Best Practices](#11-engineered-best-practices)
12. [Verification Workflow](#12-verification-workflow)

---

## 1. PROJECT SNAPSHOT

| Aspect | Detail |
|---|---|
| Purpose | Cloud accounting SaaS for small businesses — full GL, invoicing, billing, inventory, banking, tax |
| Compliance | Double-entry bookkeeping (∑Dr = ∑Cr enforced), GST output/input separation, ITO 2001 income-tax slabs |
| Multi-tenancy | Every business is a `Tenant`; every record carries `tenant_id`; tenant-scoped queries enforced on every endpoint |
| Auth | JWT bearer; token payload = `{sub, tenant_id, full_name}` |
| Reports | Real-time from GL — no snapshots, no batch jobs |
| Storage | SQLite (dev) → Postgres (prod-ready via SQLModel) |

```
┌─────────────────────────────────────────────────────────────┐
│                     EASY-BOOKS PLATFORM                     │
├─────────────────────────────────────────────────────────────┤
│  Browser (Next.js)  ◀──► REST API (FastAPI)  ◀──► SQLite    │
│  JWT in localStorage     OAuth2 password flow    SQLModel   │
│  React 19 + Tailwind     Pydantic v2 validation  Migrations │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Request Lifecycle (every page load)

```
USER ACTION (click "Save Invoice")
    │
    ▼
┌────────────────────────────────────────┐
│ Frontend (React)                       │
│  apiFetch('/api/invoices', POST, body) │
│  ↳ adds JWT bearer header              │
│  ↳ resolves NEXT_PUBLIC_API_URL        │
└────────────────────────────────────────┘
    │
    ▼ HTTP POST
┌────────────────────────────────────────┐
│ FastAPI Middleware                     │
│  1. CORS check (FRONTEND_ORIGIN)       │
│  2. JWT decode → CurrentUser           │
│  3. Inject SessionDep (DB connection)  │
└────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────┐
│ Endpoint Handler                       │
│  1. Pydantic validates body            │
│  2. tenant_id filter on every query    │
│  3. Business logic + GL posting        │
│  4. session.commit()                   │
│  5. audit_log() entry written          │
└────────────────────────────────────────┘
    │
    ▼ JSON response
┌────────────────────────────────────────┐
│ Frontend updates state                 │
│  setState → React re-render            │
└────────────────────────────────────────┘
```

### 2.2 Folder Map

```
Easy-Books/
├── backend/
│   ├── main.py             ← all routes (~1800 lines)
│   ├── models.py           ← SQLModel tables (20 entities)
│   ├── auth.py             ← JWT + password hashing
│   ├── db.py               ← engine, seed data, default CoA
│   └── database.db         ← SQLite (git-ignored)
└── frontend/src/
    ├── app/(dashboard)/    ← 23 pages (auth-gated)
    ├── components/         ← Sidebar, Header, modals, charts
    └── lib/                ← apiFetch, auth, utils
```

---

## 3. ENTITY-RELATIONSHIP MAP

```
                           ┌──────────┐
                           │  Tenant  │ (Business)
                           └─────┬────┘
                                 │
        ┌──────────┬─────────────┼─────────────┬──────────┐
        │          │             │             │          │
   ┌────▼───┐ ┌────▼────┐  ┌─────▼────┐  ┌─────▼────┐ ┌───▼────┐
   │  User  │ │ Account │  │ Customer │  │  Vendor  │ │Product │
   │ (login)│ │  (CoA)  │  │   (AR)   │  │   (AP)   │ │ (stock)│
   └────────┘ └────┬────┘  └─────┬────┘  └─────┬────┘ └───┬────┘
                   │             │              │         │
                   │       ┌─────▼────┐   ┌─────▼────┐    │
                   │       │ Invoice  │   │   Bill   │    │
                   │       │ (sale)   │   │(purchase)│    │
                   │       └─────┬────┘   └─────┬────┘    │
                   │             │              │         │
                   │       ┌─────▼─────┐  ┌─────▼─────┐   │
                   │       │InvoiceLine│  │ BillLine  │◀──┘
                   │       │ qty×rate  │  │ qty×rate  │
                   │       └─────┬─────┘  └─────┬─────┘
                   │             │              │
                   │       ┌─────▼────┐   ┌─────▼────┐
                   │       │ Payment  │   │   Bill   │
                   │       │ Received │   │ Payment  │
                   │       └─────┬────┘   └─────┬────┘
                   │             │              │
                   │             └──────┬───────┘
                   │                    ▼
                   │            ┌───────────────┐
                   └───────────▶│ Transaction   │ JV-00001
                                │ (header)      │
                                └───────┬───────┘
                                        │ 1..N
                                        ▼
                                ┌───────────────┐
                                │ JournalEntry  │ debit / credit
                                │ (line)        │ tied to Account
                                └───────────────┘

  Banking branch:                  Reconciliation branch:
  Account ◀─── BankAccount    Transaction ◀── ReconciliationLine
                                                    │
                                                    ▼
                                            Reconciliation
```

**Read this as:** every business has its own CoA, customers, vendors, products. Every operational document (invoice/bill/payment) ultimately writes a `Transaction` (the JV) which holds 2+ `JournalEntry` rows — one debit, one credit — both linked to `Account`s. Reports are aggregations over `JournalEntry`.

---

## 4. THE FIVE ACCOUNTING CYCLES

Every transaction in Easy-Books belongs to one of five cycles. Each cycle has a frontend entry page, a backend endpoint, and a deterministic GL impact.

---

### 4.1 SALES / RECEIVABLES CYCLE

```
  CREATE CUSTOMER          ISSUE INVOICE              RECEIVE PAYMENT
  ───────────────          ─────────────              ───────────────
  /customers   ────▶       /invoices       ────▶      /payments-received
       │                        │                            │
       │ POST                   │ POST                       │ POST
       ▼                        ▼                            ▼
  Customer row            Invoice + N lines            PaymentReceived
                          + Transaction (JV)           + Transaction (JV)
                          + JournalEntry × 3+          + JournalEntry × 2
                          + Audit log                  + Audit log
                                                       + Invoice.status="paid"
```

#### 4.1.1 Step-by-Step Flow

| # | Action | Frontend Page | Endpoint | DB Writes | GL Impact |
|---|---|---|---|---|---|
| 1 | Add customer | `/customers` | `POST /api/customers` | `Customer` | None (master data only) |
| 2 | Create invoice with line items | `/invoices` | `POST /api/invoices` | `Invoice`, `InvoiceLine[]`, `Transaction`, `JournalEntry[]` | **Dr AR · Cr Revenue · Cr GST Payable** |
| 3 | Receive customer payment | `/payments-received` | `POST /api/payments-received` | `PaymentReceived`, `Transaction`, `JournalEntry[]`, `Invoice.status` | **Dr Cash/Bank · Cr AR** |
| 4 | Track outstanding | `/invoices` (Aging tab) | `GET /api/invoices/aging` | (read-only) | 0–30, 31–60, 61–90, 90+ buckets |

#### 4.1.2 GL Posting Detail — Invoice (sale of services + 17% GST)

```
                             DEBIT          CREDIT
1200 Accounts Receivable    11,700                  ← what customer owes us
4000 Revenue                              10,000    ← income earned
2200 GST Payable                           1,700    ← tax owed to govt
                            ──────         ──────
                            11,700         11,700   ✓ balanced
```

#### 4.1.3 GL Posting Detail — Payment Received

```
                             DEBIT          CREDIT
1000 Cash in Hand           11,700                  ← cash received
1200 Accounts Receivable                  11,700    ← AR cleared
                            ──────         ──────
                            11,700         11,700   ✓ balanced
```

#### 4.1.4 What changes after each step

```
Before Invoice:     AR = 0,      Revenue = 0,    GST Pay = 0,    Cash = 0
After Invoice:      AR = 11,700, Revenue = 10000,GST Pay = 1700, Cash = 0
After Payment:      AR = 0,      Revenue = 10000,GST Pay = 1700, Cash = 11700
```

---

### 4.2 PURCHASE / PAYABLES CYCLE

```
  CREATE VENDOR             RECEIVE BILL                PAY BILL
  ─────────────             ────────────                ────────
  /vendors    ─────▶        /bills        ─────▶       /bill-payments
       │                        │                            │
       │ POST                   │ POST                       │ POST
       ▼                        ▼                            ▼
   Vendor row             Bill + N lines               BillPayment
                          + Transaction (JV)           + Transaction (JV)
                          + JournalEntry × 2+          + JournalEntry × 2
                          + (Product.stock_qty +=)     + Bill.status="paid"
```

#### 4.2.1 Step-by-Step Flow

| # | Action | Frontend Page | Endpoint | DB Writes | GL Impact |
|---|---|---|---|---|---|
| 1 | Add vendor | `/vendors` | `POST /api/vendors` | `Vendor` | None |
| 2 | Receive bill with line items | `/bills` | `POST /api/bills` | `Bill`, `BillLine[]`, `Transaction`, `JournalEntry[]` | **Dr Expense or Inventory · Cr AP** |
| 3 | Pay vendor | `/bill-payments` | `POST /api/bill-payments` | `BillPayment`, `Transaction`, `JournalEntry[]`, `Bill.status` | **Dr AP · Cr Cash/Bank** |
| 4 | Track payables | `/bills` (Aging tab) | `GET /api/bills/aging` | (read-only) | Same 0–30/31–60/61–90/90+ buckets |

#### 4.2.2 GL Posting Detail — Bill (service expense)

```
                             DEBIT          CREDIT
5000 Office Expense          5,000                  ← P&L expense
2000 Accounts Payable                      5,000    ← what we owe
                            ──────         ──────
                             5,000          5,000   ✓ balanced
```

#### 4.2.3 GL Posting Detail — Bill (stock purchase, e.g. 10 units @ 500)

```
                             DEBIT          CREDIT
1200 Inventory               5,000                  ← asset on balance sheet
2000 Accounts Payable                      5,000    ← liability to vendor

Plus: Product.stock_qty += 10  (real-time stock balance update)
```

#### 4.2.4 GL Posting Detail — Bill Payment

```
                             DEBIT          CREDIT
2000 Accounts Payable        5,000                  ← liability cleared
1010 Bank                                  5,000    ← cash leaves
                            ──────         ──────
                             5,000          5,000   ✓ balanced
```

---

### 4.3 INVENTORY CYCLE (cross-cutting)

Inventory is not a standalone cycle — it rides on top of Bills (inflow) and Invoices (outflow). The Product master maintains running `stock_qty` updated in real time.

```
┌──────────────────────────────────────────────────────────────────┐
│                       INVENTORY MOVEMENT                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Add product (Service / Stock type)                             │
│        /products → POST /api/products                            │
│        │                                                         │
│        ▼                                                         │
│   ┌────────────────────────┐                                     │
│   │ Product.stock_qty = 0  │  initial state                      │
│   └────────────────────────┘                                     │
│                                                                  │
│   ──── Inflow (purchase) ────                                    │
│        Create bill line { product_id, qty: 10, rate: 500 }       │
│        Bill commit:                                              │
│          • InvoiceLine.amount = qty × rate = 5,000               │
│          • Product.stock_qty += 10  ← REAL-TIME UPDATE           │
│          • GL: Dr Inventory 5,000 / Cr AP 5,000                  │
│                                                                  │
│   ──── Outflow (sale) ────                                       │
│        Create invoice line { product_id, qty: 3, rate: 800 }     │
│        Invoice commit:                                           │
│          • InvoiceLine.amount = qty × rate = 2,400               │
│          • Product.stock_qty -= 3  ← REAL-TIME UPDATE            │
│          • GL: Dr AR 2,808 / Cr Revenue 2,400 / Cr GST 408       │
│                                                                  │
│   ──── Visibility ────                                           │
│        /products page shows:                                     │
│          • current stock_qty                                     │
│          • reorder_level flag (amber if qty ≤ reorder_level)     │
│          • out-of-stock badge (red if qty ≤ 0)                   │
│        /api/products/stock-summary → all stock-type products     │
└──────────────────────────────────────────────────────────────────┘
```

**Rule:** Only `product_type = "stock"` products affect `stock_qty`. `product_type = "service"` products bypass inventory math (e.g. labor hours, consulting).

---

### 4.4 BANKING / CASH CYCLE

```
  CREATE BANK ACCOUNT      RECONCILE PERIOD
  ───────────────────      ────────────────
  /bank-accounts ────▶    /reconciliations
        │                       │
        │ POST                  │ POST → period_start, period_end
        ▼                       ▼
   BankAccount             Reconciliation
   (linked to CoA          + ReconciliationLine[] from JEs in period
    account, e.g.            │
    1010 Bank)               ▼ user matches lines
                          PATCH /api/reconciliations/{id}/lines/{id}
                            │
                            ▼ all matched
                          POST /api/reconciliations/{id}/close
                            → Reconciliation.is_closed = true
```

#### 4.4.1 Bank Account Setup

| Action | Endpoint | Description |
|---|---|---|
| Add bank account | `POST /api/bank-accounts` | Links to CoA Asset account (e.g. `1010 HBL Bank`) |
| Balance derived | `GET /api/bank-accounts` | Sum of all journal entries on the linked account |
| Edit | `PUT /api/bank-accounts/{id}` | Rename or relink |
| Deactivate | `DELETE /api/bank-accounts/{id}` | Soft delete (`is_active = false`) |

#### 4.4.2 Reconciliation Lifecycle

```
1. CREATE PERIOD          → status: open
   POST /api/reconciliations
   { bank_account_id, period_start, period_end }
   Server fetches all JournalEntries on the bank account
   in that date range → ReconciliationLine[] (unmatched)

2. USER MATCHES LINES     → status: open, lines marked matched
   PATCH /api/reconciliations/{id}/lines/{line_id}
   { is_matched: true }

3. CLOSE PERIOD           → status: closed (locked)
   POST /api/reconciliations/{id}/close
   • Only allowed when all lines matched
   • Locks the period — future edits blocked
```

---

### 4.5 MANUAL JOURNAL ENTRY CYCLE

Used for adjustments, opening balances, depreciation, accruals, prepayments, corrections.

```
  CAPTURE JV              JOURNAL                      REVERSE (if error)
  ──────────              ───────                      ──────────────────
  /entry      ────▶       /journal       ────▶        POST /api/transactions
       │                      │                            /{id}/reverse
       │ POST                 │ GET                        │
       ▼                      ▼                            ▼
  Transaction          paginated list             new Transaction created:
  + N journal lines    of all JVs                 "Reversal of JV-00042"
  Dr = Cr enforced     (filterable               with opposite Dr/Cr
  Audit logged         by date/account)          Original.is_reversed = true
```

#### 4.5.1 Entry Form Behavior (`/entry` page)

```
[ Date ]  [ Description ]  [ Reference # ]
┌──────────────────────────────────────────┐
│ Account         │ Debit       │ Credit   │
├──────────────────────────────────────────┤
│ 1000 Cash    ▼  │  10,000     │     -    │
│ 4000 Revenue ▼  │      -      │  10,000  │
├──────────────────────────────────────────┤
│ + Add row                                │
└──────────────────────────────────────────┘
                  Total Dr: 10,000
                  Total Cr: 10,000  ✓ balanced
                                    [ Save ]

→ POST /api/transactions
  Validates: Dr == Cr (±0.01 rounding)
  Validates: txn.date NOT in any locked AccountingPeriod
  Writes: Transaction (JV-NNNNN auto-numbered) + N JournalEntry rows + AuditLog
```

#### 4.5.2 JV Numbering (race-free)

```python
# Inside endpoint, all 6 transaction-creating call sites use this pattern:
txn = Transaction(tenant_id=..., jv_number="__TMP__", ...)
session.add(txn)
session.flush()                         # DB assigns txn.id atomically
txn.jv_number = f"JV-{txn.id:05d}"      # e.g. "JV-00042"
session.add(txn)
# ...continue with journal entries
session.commit()
```
This **eliminates the race condition** that would happen with `COUNT(*)+1` numbering under concurrent writes.

#### 4.5.3 Reversal Mechanics

Reversing JV-00042 creates **a new JV** (e.g. JV-00043) with:
- Description: `"Reversal of JV-00042"`
- Same accounts, but Dr/Cr swapped
- Both rows linked: `JV-00042.is_reversed = true`, `JV-00042.reversed_by_id = 43`
- Original is **never deleted** — preserves audit trail.

---

## 5. GL POSTING REFERENCE (Dr / Cr Map)

| Business Event | Debit Account | Credit Account | Side Effects |
|---|---|---|---|
| Invoice (service) | 1200 Accounts Receivable | 4000 Revenue + 2200 GST Payable | — |
| Invoice (stock product) | 1200 Accounts Receivable | 4000 Revenue + 2200 GST Payable | `product.stock_qty -= qty` |
| Payment received | 1000 Cash / 1010 Bank | 1200 Accounts Receivable | `invoice.status = paid` |
| Bill (service expense) | 5xxx Expense (configurable) | 2000 Accounts Payable | — |
| Bill (stock purchase) | 1200 Inventory | 2000 Accounts Payable | `product.stock_qty += qty` |
| Bill payment | 2000 Accounts Payable | 1000 Cash / 1010 Bank | `bill.status = paid` |
| Opening balance (Asset) | Asset account | 3000 Owner's Equity | One-time |
| Depreciation | 5050 Depreciation Exp | 1510 Accumulated Depreciation | Monthly |
| Bad debt write-off | 5060 Bad Debt | 1200 AR | When uncollectible |
| Owner draw | 3010 Drawings | 1000 Cash | Reduces equity |
| Owner capital | 1000 Cash | 3000 Owner's Equity | Increases equity |

**Universal rule:** ∑ Debit = ∑ Credit on every transaction. Backend enforces; UI displays warning if user attempts unbalanced JV.

---

## 6. REPORT LINKING MATRIX

This is **how every transaction flows into every report**, in real time, no batch jobs.

```
                          ┌────────────────────┐
                          │   JournalEntry     │  (source of truth)
                          │   table            │
                          └─────────┬──────────┘
                                    │
        ┌──────────┬─────────┬──────┴──────┬──────────┬──────────┬─────────┐
        ▼          ▼         ▼             ▼          ▼          ▼         ▼
   ┌─────────┐┌────────┐┌──────────┐┌──────────┐┌─────────┐┌──────────┐┌────────┐
   │ Journal ││ Ledger ││  Trial   ││  Income  ││ Balance ││Cash Flow ││  Tax   │
   │  list   ││ per a/c││ Balance  ││ Stmt P&L ││  Sheet  ││ (indirect││Summary │
   │  view   ││ +running││ (Dr/Cr   ││ (Rev -   ││(A=L+E)  ││ method)  ││(GST    │
   │         ││balance ││  per a/c)││  Exp)    ││         ││          ││ +tax)  │
   └─────────┘└────────┘└──────────┘└──────────┘└─────────┘└──────────┘└────────┘
       /journal /ledger /trial-balance /pl       /balance   /cashflow   /tax
```

### 6.1 Per-Report Calculation Rules

| Report | URL | Calculation |
|---|---|---|
| **Journal** | `/journal` | Flat list of every `JournalEntry` joined with `Transaction` and `Account`, paginated, filterable by date/account |
| **General Ledger** | `/ledger?account=Cash` | Same data, **grouped by account**, with running balance per row (cumulative Dr − cumulative Cr per account type) |
| **Trial Balance** | `/trial-balance` | `SUM(debit) per account`, `SUM(credit) per account` — verifies ∑Dr = ∑Cr across the entire book |
| **Income Statement (P&L)** | `/pl` | Revenue accounts (4xxx) − Expense accounts (5xxx) = Net Profit, within date range |
| **Balance Sheet** | `/balance` | Assets (1xxx) = Liabilities (2xxx) + Equity (3xxx + Retained Earnings = current-period Net Income) |
| **Cash Flow** | `/cashflow` | Indirect method: Net Income + non-cash adjustments + Δ working capital (ΔAR, ΔAP, ΔInventory) |
| **Tax Summary** | `/tax` | Output GST (from Invoice JEs to 2200) − Input GST (from Bill JEs) = Net GST Payable; Net Income → ITO 2001 slab estimate |
| **AR Aging** | `/invoices` (aging panel) | Unpaid invoices bucketed by `due_date` age: 0–30 / 31–60 / 61–90 / 90+ |
| **AP Aging** | `/bills` (aging panel) | Same buckets for unpaid bills |
| **Dashboard KPIs** | `/dashboard` | Total Revenue / Expense / Profit / Cash Balance — computed live |
| **Dashboard Charts** | `/dashboard` | Monthly Rev vs Exp bars · Net Profit line · Top 8 expenses doughnut · Top 5 customers bar |

### 6.2 Example: Trace ONE invoice across ALL reports

```
You post Invoice INV-001 dated 2026-05-19 for PKR 11,700 (incl GST):

┌─ Posting creates ──────────────────────────────────────────────────────────┐
│  JV-00050  date=2026-05-19                                                 │
│   ├ JE: account=1200 AR,         debit=11,700,  credit=0                   │
│   ├ JE: account=4000 Revenue,    debit=0,       credit=10,000              │
│   └ JE: account=2200 GST Pay,    debit=0,       credit=1,700               │
└────────────────────────────────────────────────────────────────────────────┘

Now appears in:
  /journal           → 1 row showing JV-00050, total 11,700, link to ledger
  /ledger?account=1200 AR    → +11,700 line, balance increases
  /ledger?account=4000       → +10,000 line on credit side
  /ledger?account=2200       → +1,700 line on credit side
  /trial-balance     → 1200 Dr increases by 11,700; 4000 + 2200 Cr by 11,700
  /pl                → Revenue total goes up by 10,000 → Net Profit +10,000
  /balance           → Assets ↑ 11,700 (AR), Liab ↑ 1,700 (GST), Equity ↑ 10,000 (RE)
  /cashflow          → ΔAR (working cap) goes up — reduces Operating CF
  /tax               → Output GST goes up by 1,700
  /invoices/aging    → INV-001 lands in 0-30 day bucket
  /dashboard         → Revenue KPI ↑, monthly chart bar grows
```

---

## 7. FRONTEND HYPERLINK NAVIGATION MAP

Every record name in the UI is clickable and leads to its source or related view:

```
ON CLICKING ↓                              YOU LAND ON ↓
────────────────────────────────────────────────────────────────────
"John & Sons" in /invoices       ─────▶   /customers (master record)
"Acme Supplies" in /bills        ─────▶   /vendors (master record)
"Acme Supplies" in /bill-payments─────▶   /vendors
"John & Sons" in /payments-recd  ─────▶   /customers
"Cash in Hand" in /journal       ─────▶   /ledger?account=Cash in Hand
"Cash in Hand" in /trial-balance ─────▶   /ledger?account=Cash in Hand
"INV-005" in /payments-received  ─────▶   /invoices (find by number)
"BILL-012" in /bill-payments     ─────▶   /bills
"JV-00050" in /dashboard         ─────▶   /journal?jv=JV-00050
```

### 7.1 Sidebar Sections (left rail / mobile drawer)

```
OVERVIEW         LEDGER              RECEIVABLE        PAYABLE
─ Dashboard      ─ New Entry         ─ Invoices        ─ Bills
                 ─ Journal           ─ Customers       ─ Vendors
                 ─ General Ledger    ─ Payments Recd   ─ Bill Payments
                 ─ Chart of Accts                      ─ Products

BANKING          REPORTS             SYSTEM
─ Bank Accounts  ─ Trial Balance     ─ Workflow      ← visual flowcharts
─ Reconcil.      ─ Income Stmt       ─ User Guide    ← 8-tab guide
                 ─ Balance Sheet     ─ Settings
                 ─ Cash Flow
                 ─ Tax Reports
```

---

## 8. CSV BULK IMPORT FLOW

For onboarding existing books or bulk-creating records:

```
┌──────────────────────────────────────────────────────────────┐
│ 1. DOWNLOAD SAMPLE                                           │
│    User clicks "Sample CSV" on /customers (or other page)    │
│    GET /api/import/customers/sample                          │
│    → returns CSV with correct headers + 2 example rows       │
├──────────────────────────────────────────────────────────────┤
│ 2. EDIT LOCALLY                                              │
│    User opens in Excel / Sheets, adds rows                   │
├──────────────────────────────────────────────────────────────┤
│ 3. DRAG-AND-DROP UPLOAD                                      │
│    User drops file on import zone in CsvImportButton modal   │
│    → JS parses, shows 5-row preview table                    │
├──────────────────────────────────────────────────────────────┤
│ 4. SUBMIT                                                    │
│    POST /api/import/customers (multipart)                    │
│    Server iterates rows:                                     │
│      • Validates required fields                             │
│      • Validates enums (account type, product type, unit)    │
│      • For transactions: groups by date+description,         │
│        validates Σ Dr = Σ Cr per group                       │
│      • Per-row error collection — partial success OK         │
├──────────────────────────────────────────────────────────────┤
│ 5. RESPONSE                                                  │
│    { imported: 47, errors: [{row: 12, message: "..."}] }     │
│    Modal shows green count + red error rows for review       │
└──────────────────────────────────────────────────────────────┘
```

**Supported entities:** transactions, accounts, customers, vendors, products. Each has its own field schema documented in the modal.

---

## 9. API ENDPOINT CATALOG

### 9.1 Auth & Settings
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/signup` | Create tenant + admin user |
| POST | `/api/auth/login` | Issue JWT |
| GET | `/api/auth/me` | Current user details |
| GET | `/api/settings` | Read company settings |
| PATCH | `/api/settings` | Update settings (company name, fiscal year, currency, prefixes) |

### 9.2 Master Data
| Method | Path | Purpose |
|---|---|---|
| GET/POST/PUT/DELETE | `/api/customers` (+ `/{id}`) | Customer CRUD |
| GET/POST/PUT/DELETE | `/api/vendors` (+ `/{id}`) | Vendor CRUD |
| GET/POST/PUT/DELETE | `/api/products` (+ `/{id}`) | Product catalog |
| GET | `/api/products/stock-summary` | All stock-type products + qty |
| GET/POST/PUT/DELETE | `/api/accounts` (+ `/{id}`) | Chart of Accounts |
| GET/POST/PUT/DELETE | `/api/bank-accounts` (+ `/{id}`) | Bank accounts |

### 9.3 Transactional
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/invoices` | List / create invoice (auto GL) |
| PATCH | `/api/invoices/{id}/status` | Mark paid/void/sent |
| GET | `/api/invoices/aging` | AR aging report |
| GET/POST | `/api/bills` | List / create bill (auto GL) |
| PATCH | `/api/bills/{id}/status` | Mark paid/void/received |
| GET | `/api/bills/aging` | AP aging report |
| GET/POST | `/api/payments-received` | List / receive payment (auto GL) |
| GET/POST | `/api/bill-payments` | List / pay bill (auto GL) |
| POST | `/api/transactions` | Manual JV |
| GET | `/api/transactions/{id}` | JV detail |
| POST | `/api/transactions/{id}/reverse` | Generate reversal JV |

### 9.4 Reports
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/reports/journal` | All JEs with filters |
| GET | `/api/reports/ledger` | Grouped per-account with running balance |
| GET | `/api/reports/trial-balance` | Dr/Cr totals per account |
| GET | `/api/reports/income-statement` | P&L for period |
| GET | `/api/reports/balance-sheet` | Position with current-period retained earnings |
| GET | `/api/reports/cash-flow` | Indirect method, 3 sections |
| GET | `/api/reports/tax-summary` | GST + ITO 2001 slabs |
| GET | `/api/reports/dashboard` | KPIs |
| GET | `/api/reports/dashboard/charts?months=12` | Chart datasets |

### 9.5 Period & Audit
| Method | Path | Purpose |
|---|---|---|
| GET/POST/DELETE | `/api/periods` (+ `/{id}`) | Manage fiscal periods |
| PATCH | `/api/periods/{id}/lock` | Lock/unlock period (blocks edits) |
| GET | `/api/audit-log` | All mutation history (entity, action, before/after) |

### 9.6 Reconciliation
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/reconciliations` (+ `/{id}`) | Period reconciliation |
| PATCH | `/api/reconciliations/{id}/lines/{lid}` | Match/unmatch line |
| POST | `/api/reconciliations/{id}/close` | Lock period |

### 9.7 Bulk Import
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/import/{entity}/sample` | Download blank CSV template |
| POST | `/api/import/accounts` | Bulk create CoA |
| POST | `/api/import/customers` | Bulk create customers |
| POST | `/api/import/vendors` | Bulk create vendors |
| POST | `/api/import/products` | Bulk create products |
| POST | `/api/import/transactions` | Bulk create JVs (Dr=Cr validated per group) |

---

## 10. MULTI-TENANT & SECURITY MODEL

### 10.1 Tenant Isolation

```
EVERY query in EVERY endpoint follows this pattern:

  session.exec(
    select(Customer)
      .where(Customer.id == customer_id)
      .where(Customer.tenant_id == user.tenant_id)   ← MANDATORY
  ).first()

If the lookup fails because the row belongs to another tenant,
the endpoint returns 404 — never 403 — to prevent enumeration.
```

### 10.2 Auth Token Structure

```
JWT payload:
{
  "sub": "owner@business.com",
  "tenant_id": 7,
  "full_name": "Bilal Mughal",
  "exp": 1747824000
}

Stored in: localStorage on the client
Sent as: Authorization: Bearer <token> on every API call
Decoded: server-side via auth.py (HS256)
```

### 10.3 Defense Layers

| Layer | Mechanism |
|---|---|
| Transport | HTTPS (in production); CORS restricted to `FRONTEND_ORIGIN` env var |
| Auth | JWT with secret from `JWT_SECRET_KEY` env var (warns if default) |
| Authorization | Every query filters by `tenant_id` from token |
| Input | Pydantic validates every body; ID-based lookups parameterized via SQLModel |
| Audit | Every mutation logged with user_id, action, old/new JSON |
| Period lock | Mutations in locked periods rejected at endpoint level |
| Race safety | JV numbers from DB auto-increment (no COUNT) |

---

## 11. ENGINEERED BEST PRACTICES

This project bakes in industry accounting + software norms:

### 11.1 Accounting
- ✅ **Double-entry enforced** — every transaction must balance (∑Dr = ∑Cr ±0.01)
- ✅ **Accrual basis** — revenue recognized at invoice, expense at bill (not at cash)
- ✅ **GST separation** — output and input GST tracked in distinct accounts (2200, 1300)
- ✅ **No deletes on posted JVs** — corrections via reversal entries only
- ✅ **Period locking** — closed months protected against backdated edits
- ✅ **Audit trail** — every mutation has user + timestamp + before/after JSON
- ✅ **Running balance** in ledger view (cumulative per account)
- ✅ **AR/AP aging** by due date in standard buckets

### 11.2 Software
- ✅ **Multi-tenant isolation** at the data layer (no cross-tenant leaks)
- ✅ **ID-flush JV numbering** (race-free under concurrent writes)
- ✅ **Real-time reports** — no batch jobs, no stale snapshots
- ✅ **Server-side pagination** + search on all list pages
- ✅ **Server-driven currency formatting** (settings-aware)
- ✅ **CSV partial-success import** — one bad row doesn't block 100 good ones
- ✅ **Hyperlinked records** — every name is a navigable link to source
- ✅ **Mobile-responsive** — 60px icon rail (md), 256px expanded (xl), bottom nav (mobile)

### 11.3 Code Hygiene
- ✅ TypeScript strict mode — `npx tsc --noEmit` clean
- ✅ Single-file SQLite for dev; SQLModel makes Postgres a swap
- ✅ Environment variables for all secrets (`.env.example` provided)
- ✅ Git history clean of binaries (filter-branch purged 114MB venv)
- ✅ `.gitignore` covers venv, __pycache__, .next, .db, .env

---

## 12. VERIFICATION WORKFLOW

After any change, verify the books still tie out:

```
┌─────────────────────────────────────────────────────────────────┐
│  END-TO-END SMOKE TEST                                          │
├─────────────────────────────────────────────────────────────────┤
│  1. Create customer    → POST /api/customers                    │
│  2. Create invoice     → POST /api/invoices (3 lines)           │
│  3. Receive payment    → POST /api/payments-received            │
│  4. Open /journal      → JV-NNNNN appears, Dr = Cr              │
│  5. Open /ledger?account=1200 AR → +11700 then −11700, net 0    │
│  6. Open /trial-balance → ∑Dr = ∑Cr (warning banner hidden)     │
│  7. Open /balance      → Assets = Liabilities + Equity ±0.01    │
│  8. Open /pl           → Revenue total reflects invoice amount  │
│  9. Open /cashflow     → Operating CF reflects cash inflow      │
│ 10. Open /tax          → Output GST captured                    │
└─────────────────────────────────────────────────────────────────┘

If steps 5–9 reconcile, the books are healthy.
```

---

## 13. ROAD MAP (post-current-build)

The remaining tasks in the project plan (#8–#24) cover:
- Hierarchical Chart of Accounts (parent / sub-accounts)
- Multi-currency support
- Recurring invoices/bills
- Email send (invoices, statements, reminders)
- E-signature on invoices
- PDF generation server-side
- Stripe/Razorpay payment links
- Mobile app (React Native, sharing the same API)

---

## APPENDIX — DEFAULT CHART OF ACCOUNTS (auto-seeded per tenant)

| Code | Name | Type | Used by |
|---|---|---|---|
| 1000 | Cash in Hand | Asset | default cash receipts |
| 1010 | Bank | Asset | bank payments/receipts |
| 1200 | Accounts Receivable | Asset | invoices → AR |
| 1200 | Inventory (Raw Material) | Asset | stock-type bill purchases |
| 1201 | Finished Goods Inventory | Asset | manufactured stock |
| 2000 | Accounts Payable | Liability | bills → AP |
| 2200 | GST Payable (Output) | Liability | invoice GST collected |
| 1300 | GST Receivable (Input) | Asset | bill GST paid |
| 3000 | Owner's Equity | Equity | capital injections |
| 3010 | Drawings | Equity | owner withdrawals |
| 4000 | Sales Revenue | Revenue | invoice line revenue |
| 5000 | Office Expense | Expense | bill expense default |
| 5010 | Cost of Goods Sold | Expense | inventory cost on sale |
| 5050 | Depreciation Expense | Expense | manual JV |

---

> **Last updated:** 2026-05-19
> **Branch:** `saas-transition-foundation` (= `main` after merge)
> **Live demo:** `npm run dev` (frontend :3000) + `uvicorn main:app --reload` (backend :8000)
> **Repository:** https://github.com/bilalpiaic/Easy-Books
