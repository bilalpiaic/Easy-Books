# Easy-Books User Guide

> A comprehensive guide to using Easy-Books for double-entry accounting, compliant with **IAS/IFRS standards**.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Company Setup & Branding](#2-company-setup--branding)
3. [Accounting Fundamentals](#3-accounting-fundamentals)
4. [Sales Workflow (AR)](#4-sales-workflow-ar)
5. [Purchase Workflow (AP)](#5-purchase-workflow-ap)
6. [Inventory Management](#6-inventory-management)
7. [Bank Reconciliation](#7-bank-reconciliation)
8. [Financial Reporting](#8-financial-reporting)
9. [Period Close](#9-period-close)
10. [Multi-Tenant Administration](#10-multi-tenant-administration)

---

## 1. GETTING STARTED

### 1.1 First-Time Login

Easy-Books provides **5 pre-seeded demo tenants** for immediate exploration:

| Email | Password | Business Model |
|-------|----------|---|
| `demo.simple@easy-books.app` | `demo1234` | Micro-business (invoicing + billing only) |
| `demo.services@easy-books.app` | `demo1234` | Service firm (recurring revenue, time tracking) |
| `demo.trader@easy-books.app` | `demo1234` | Trading company (buy/resell, inventory) |
| `demo.manufacturing@easy-books.app` | `demo1234` | Manufacturing (BoMs, production orders) |
| `demo.telecom@easy-books.app` | `demo1234` | Telecom Franchise (Tracker, RSO chain, FCA, SIM) |

**Rich mock data included:**
- Each tenant has **50+ customers, 50+ vendors, 50+ invoices, 50+ bills, 50+ manual journal entries**
- Manufacturing tenant: 50 BoMs, 50 GRNs, 50 production orders, 50 rate plans
- Telecom tenant: 50 SIM activations, 50 FCA events, full RSO chain & franchise agreement
- `dev.sh` seeds automatically on every start — no manual step needed

### 1.2 Custom Business Setup

To create your own business:

1. Go to `/signup`
2. Enter your details:
   - Full name
   - Email
   - Password (≥ 8 characters)
   - Company name
   - Business model (Simple / Services / Trader / Manufacturing / Telecom Franchise)
3. Click **Start Free Trial**

Easy-Books will:
- ✓ Create your tenant (isolated business entity)
- ✓ Seed a Chart of Accounts matching your model
- ✓ Create your admin user account
- ✓ Log you in automatically

---

## 2. COMPANY SETUP & BRANDING

### 2.1 Configure Company Information

Go to `/dashboard/settings` to customize your business:

| Setting | Example | Impact | IAS Ref |
|---------|---------|--------|---------|
| **Company Name** | "Garment Loop" | Appears in header + all reports | **IAS 1.49** |
| **Business Tagline** | "Premium Textiles Manufacturing" | Subtitle below company name | **IAS 1.45** |
| **Tax ID** | "12-3456789" | Printed on invoices/reports | **IAS 1.49** |
| **Base Currency** | PKR / USD / EUR / etc. | All transactions in this currency | **IAS 21.8** |
| **Fiscal Year Start** | January / April / July / October | Determines financial year | **IAS 1.49** |

**Result in Header:**
```
Garment Loop
Premium Textiles Manufacturing
```

All settings are auto-saved to the database via `/api/settings` PATCH endpoint.

### 2.2 Document Numbering

Configure invoice and bill prefixes:

| Setting | Default | Usage |
|---------|---------|-------|
| Invoice Prefix | `INV` | Auto-generates INV-0001, INV-0002, etc. |
| Bill Prefix | `BILL` | Auto-generates BILL-0001, BILL-0002, etc. |

Number sequences are **tenant-scoped** and **atomic** — concurrent invoices never get the same number.

---

## 3. ACCOUNTING FUNDAMENTALS

### 3.1 The Double-Entry Rule

Every transaction must balance: **∑Debit = ∑Credit**

Easy-Books **enforces this at the database level**:
- No transaction is posted unless debits exactly equal credits
- The system prevents:
  - ✓ Unbalanced journal entries
  - ✓ Negative amounts
  - ✓ Both-sided rows (Dr > 0 AND Cr > 0 simultaneously)
  - ✓ Posting into locked periods

**Compliance:** IAS 1.44 — every balanced statement demonstrates reliability.

### 3.2 Chart of Accounts

Your Chart of Accounts (CoA) is pre-seeded based on your business model **selected at signup**:

| Model | Accounts | Purpose |
|-------|----------|---------|
| Simple | 22 | Core backbone (Cash, AR, AP, Revenue, Expenses) |
| Services | 27 | + Recurring revenue, deferred revenue |
| Trader | 30 | + Inventory, COGS, GST input/output |
| Manufacturing | 35+ | + Raw materials, WIP, FG, labor, overhead |

Each account has:
- **Code** (e.g., 1100, 4000, 5010) — unique per tenant
- **Name** (e.g., "Accounts Receivable")
- **Type** (Asset / Liability / Equity / Revenue / Expense)

**Note:** Business model is set at signup and cannot be changed through the UI. If you need to switch models, contact your administrator or use the API endpoint `PATCH /api/settings/business-model` (which adds any missing CoA accounts but never deletes existing ones).

**To add a new account:** Go to `/dashboard/coa`, click **+ New Account**, and save.

### 3.3 Account Types & Normal Balances

| Type | Normal Balance | Purpose | IAS Class |
|------|---|---|---|
| **Asset** | Debit | Cash, receivables, inventory | **IAS 32.9** |
| **Liability** | Credit | Payables, loan, GST owed | **IAS 32.9** |
| **Equity** | Credit | Owner capital, retained earnings | **IAS 32.9** |
| **Revenue** | Credit | Sales, interest income | **IAS 18** |
| **Expense** | Debit | Cost of goods, rent, utilities | **IAS 8** |

Easy-Books displays these intelligently in reports — e.g., AP shows as **credit-normal** (positive = "we owe").

---

## 4. SALES WORKFLOW (AR)

**Compliance:** IAS 18 / IFRS 15 — Revenue recognized when control of goods passes to customer.

### 4.1 Create a Customer

1. Go to `/dashboard/customers`
2. Click **+ New Customer**
3. Enter:
   - Name (e.g., "Alpha Retail Group")
   - Email (for contact)
   - Phone (optional)
4. Click **Save**

### 4.2 Issue an Invoice

1. Go to `/dashboard/invoices`
2. Click **+ New Invoice**
3. Select **Customer** (dropdown)
4. Enter line items:
   - Product / description
   - Quantity
   - Unit price
   - (Tax will auto-calculate if tax code assigned)
5. Click **Issue**

**GL Impact (service sale, 1000 + 17% GST):**
```
Dr 1100 (AR)         1,170.00
  Cr 4000 (Revenue)            1,000.00
  Cr 2200 (GST Out)               170.00
                     ─────────  ─────────
                     1,170.00    1,170.00 ✓
```

**Invoice Status:** Auto-derived from payments
- `issued` — no payments received
- `partial` — some payment received
- `paid` — fully paid
- `overdue` — due date passed, unpaid

### 4.3 Receive a Payment

1. Go to `/dashboard/payments-received`
2. Click **+ New Payment**
3. Select customer, amount, payment date
4. Choose invoices to allocate against (click rows to select)
5. Click **Save**

**GL Impact (cash payment):**
```
Dr 1010 (Bank)       1,170.00
  Cr 1100 (AR)                 1,170.00
```

**Payment can settle multiple invoices** — allocations preserve audit trail.

### 4.4 View Customer Aging

Go to `/dashboard/invoices` → **Aging** tab:
- Shows outstanding AR by aging bucket (0–30 days, 30–60, 60–90, 90+ days)
- **Net of allocations** — partial payments reduce outstanding amount

---

## 5. PURCHASE WORKFLOW (AP)

**Compliance:** IAS 2.11 — Purchase recognition when risk of ownership transfers.

### 5.1 Create a Vendor

1. Go to `/dashboard/vendors`
2. Click **+ New Vendor**
3. Enter name, contact details
4. Click **Save**

### 5.2 Record a Bill

1. Go to `/dashboard/bills`
2. Click **+ New Bill**
3. Select **Vendor**
4. Enter line items (description, amount, tax code)
5. Click **Record**

**GL Impact (expense purchase, 1000 + 17% GST):**
```
Dr 5000 (Expense)      1,000.00
Dr 1250 (GST Input)       170.00
  Cr 2000 (AP)                    1,170.00
```

If **stock purchase** (product has inventory tracking):
```
Dr 1200 (Inventory)      1,000.00
Dr 1250 (GST Input)         170.00
  Cr 2000 (AP)                     1,170.00
```

### 5.3 Pay a Bill

1. Go to `/dashboard/bill-payments`
2. Click **+ New Payment**
3. Select vendor, amount, payment date
4. Allocate to bills
5. Click **Save**

**GL Impact:**
```
Dr 2000 (AP)         1,170.00
  Cr 1010 (Bank)               1,170.00
```

---

## 6. INVENTORY MANAGEMENT

**Compliance:** IAS 2.19 — Inventory valued at **Weighted-Average cost**, not FIFO or LIFO.

### 6.1 Add Products

1. Go to `/dashboard/products`
2. Click **+ New Product**
3. Enter:
   - SKU (unique code, e.g., "SKU-A1")
   - Name (e.g., "Premium Cotton Shirt")
   - Type: `stock` or `service`
   - Unit (ea, kg, m, hr, etc.)
   - Cost (used for COGS calculations)
4. Click **Save**

### 6.2 Stock Receipt (Purchase)

When you receive stock from a vendor, a bill automatically:
- Appends an **InventoryLayer** (cost, qty, date)
- Recomputes running **Weighted-Average cost**

**Example:** 3 units @ 50 each (cost 15 each)
- Previous WAvg: 12/unit (50 units in stock)
- New receipt: 3 units @ 15 = 45 in layer total
- **New WAvg:** (50 × 12 + 3 × 15) / (50 + 3) = **11.88/unit**

### 6.3 Stock Consumption (Invoice)

When you issue an invoice with stock items:
- System relieves stock at the **running WAvg cost**
- **Oldest layers deplete first** (FIFO depletion)
- A separate **COGS sub-JV** posts automatically

**Example:** Sell 2 units @ 100 each (WAvg = 11.88)
```
JV #1 (Sale):
Dr 1100 (AR)           200.00
  Cr 4000 (Revenue)             200.00

JV #2 (COGS, separate JV):
Dr 5010 (COGS)          23.76    ← 2 × 11.88
  Cr 1200 (Inventory)            23.76
```

### 6.4 View Stock Card

Go to `/dashboard/products` → Click product name → **Stock Card**

Shows:
- Receipt date, qty, cost per unit → **Running balance**
- Consumption date, qty, cost → **Running WAvg**
- **Stock value at-hand** (qty × WAvg cost)

**Compliance:** IAS 2.36(d) — Carrying amount disclosed per inventory class.

---

## 7. BANK RECONCILIATION

**Compliance:** IAS 7 — Cash flow statement derived from bank balance reconciliation.

### 7.1 Import Bank Statement

1. Go to `/dashboard/bank-accounts`
2. Select account
3. Click **Import Statement**
4. Upload CSV (5 columns: date, description, debit, credit, balance)
5. Click **Upload**

Easy-Books de-duplicates by **SHA-256 file hash** — re-uploading same file twice doesn't duplicate rows.

### 7.2 Auto-Match Transactions

System attempts to **match statement lines to GL transactions** by:
- Amount equality
- ±3-day date window
- Automatic allocation if unique

Matched lines show **green checkmark**; unmatched show **orange flag**.

### 7.3 Manual Matching

For unmatched lines:
1. Click **Unmatched** tab
2. Select statement line
3. Choose GL transaction to match
4. Click **Link**

### 7.4 Period Reconciliation Lock

Once reconciled:
1. Select all matched lines
2. Click **Lock & Close Period**

This:
- ✓ Verifies GL balance = statement balance
- ✓ Locks the period (no edits allowed)
- ✓ Materialises account balances for fast reporting

---

## 8. FINANCIAL REPORTING

All reports are **live from the General Ledger** — no batch jobs, always current.

### 8.1 Trial Balance

Go to `/dashboard/trial-balance`

Shows:
- Account code, name, type
- **Debit & Credit totals** (Σ Dr should = Σ Cr)
- **Warning if imbalanced** (indicates posting error)

**Compliance:** IAS 1.35 — Basis for all financial statements.

### 8.2 Income Statement (P&L)

Go to `/dashboard/pl`

Shows:
- **Revenue** (credit balance)
- **Less: Expenses** (debit balance)
- **Net Income** (bottom line)

Formatted per **IAS 1.99** (consistent presentation, revenue first).

### 8.3 Balance Sheet

Go to `/dashboard/balance`

Shows:
- **Assets** (debit balance)
- **Liabilities** (credit balance)
- **Equity** (credit balance)

Equation: **Assets = Liabilities + Equity** ✓

### 8.4 Cash Flow (Indirect Method)

Go to `/dashboard/cashflow`

Derives cash movement from:
- Net income
- Working capital changes (AR, AP, inventory)
- Investing activities (if configured)
- Financing activities (if configured)

**Compliance:** IAS 7.20 — Indirect method (GL-based).

### 8.5 Tax Summary

Go to `/dashboard/tax`

Shows:
- **GST Output** (tax owed on sales)
- **GST Input** (tax recoverable on purchases)
- **Net GST Due** (output - input)

By tax code and period, supporting tax returns.

---

## 9. PERIOD CLOSE

**Compliance:** IAS 1.49 — Consistent period reporting; reversal-proof once closed.

### 9.1 Create Accounting Period

1. Go to `/dashboard/settings` → **Accounting Periods**
2. Click **+ New Period**
3. Enter name (e.g., "FY 2026 Q1") and date range
4. Click **Save**

### 9.2 Close a Period

1. Select period
2. Click **Close Period**

Easy-Books will:
- ✓ Post a **Closing JV** (Revenue/Expense → Retained Earnings)
- ✓ Lock the period (no further edits allowed)
- ✓ Materialise account balances into **AccountBalance** table (for fast reporting)

### 9.3 Reopen a Period (Admin Only)

If you need to post corrections:
1. Select period
2. Click **Reopen**

Reverses the closing JV, clears materialised balances. Period is now editable again.

---

## 10. MULTI-TENANT ADMINISTRATION

### 10.1 User Roles & Permissions

| Role | Invoice | Bill | JV | Settings | Users |
|------|---------|------|----|-|-|
| **Viewer** | View | View | View | — | — |
| **Accountant** | Create/Edit | Create/Edit | Create/Edit | — | — |
| **Admin** | ✓ | ✓ | ✓ | Edit | Manage |
| **Owner** | ✓ | ✓ | ✓ | ✓ | ✓ |

First user of a tenant is **Owner** by default.

### 10.2 Add Users (Owner/Admin Only)

1. Go to `/dashboard/settings` → **Users**
2. Click **+ Invite User**
3. Enter email, select role
4. Click **Send Invite**

User receives email with login link.

### 10.3 Audit Trail

Go to `/dashboard/settings` → **Audit Log**

Shows:
- User (email)
- Action (CREATE, UPDATE, DELETE)
- Entity type (Invoice, Bill, Account, etc.)
- Timestamp
- Before/after JSON (what changed)

Every transaction is logged — **ISA 230** compliance (audit documentation).

---

## Best Practices

### ✓ Accounting Hygiene

1. **Reconcile bank monthly** — lock period once balanced
2. **Review aging reports weekly** — follow up on overdue AR
3. **Run trial balance daily** — catch posting errors early
4. **Reverse, don't delete** — preserves audit trail
5. **Lock periods annually** — prevent accidental edits

### ✓ International Standards

- **IAS 1** — Consistent company name + branding in all outputs
- **IAS 2** — Use Weighted-Average inventory method (system default)
- **IAS 18 / IFRS 15** — Recognize revenue on invoice issue (not cash receipt)
- **ISA 230** — Every GL line traces to source document (click to verify)
- **IAS 21** — FX rates snapshot at transaction date (no retroactive revaluation)

### ✓ Security

- Change password quarterly
- Use strong passwords (≥12 characters, mixed case + numbers)
- Revoke user access immediately on departure
- Review audit log for suspicious activity
- Enable 2FA if available (coming in V2)

---

## FAQ

**Q: Can I change the accounting year?**  
A: Yes, in Settings → Fiscal Year Start. Affects future periods only; existing periods unchanged.

**Q: What if I need to edit an old invoice?**  
A: If period is open, click invoice → Edit → Save. If period is locked, create a reversal (Invoice → Reverse) + new corrected invoice.

**Q: How does COGS work?**  
A: When you sell stock, the system auto-posts COGS at Weighted-Average cost + a separate JV. Two JVs per stock sale (one for revenue, one for COGS).

**Q: Why does my trial balance not balance?**  
A: Check for unposted transactions (drafts). Click **Try Balance** to verify; it shows first error.

**Q: Can I use multiple currencies?**  
A: Yes. Set base currency in Settings; create invoices/bills in other currencies. FX rates from `/dashboard/exchange-rates` lookup table.

---

**Last updated:** 2026-05-23  
**Version:** 1.0 (IAS/IFRS compliant)
