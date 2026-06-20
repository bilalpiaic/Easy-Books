# Easy-Books User Guide

> A comprehensive guide to using Easy-Books for double-entry accounting, compliant with **IAS/IFRS standards**.

**Last updated:** 2026-06-20 · **Version:** 2.7

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Company Setup & Branding](#2-company-setup--branding)
3. [Accounting Fundamentals](#3-accounting-fundamentals)
4. [Sales Workflow (AR)](#4-sales-workflow-ar)
5. [Purchase Workflow (AP)](#5-purchase-workflow-ap)
6. [Payments & Allocations](#6-payments--allocations)
7. [Inventory Management](#7-inventory-management)
8. [Bank Reconciliation](#8-bank-reconciliation)
9. [Financial Reporting](#9-financial-reporting)
   - 9.1 [Dashboard Quick Actions & KPIs](#91-dashboard-quick-actions--kpis)
   - 9.7 [Customizing Your Dashboard](#97-customizing-your-dashboard)
10. [Period Close](#10-period-close)
11. [Recurring Journal Entries](#11-recurring-journal-entries)
12. [Bulk Actions](#12-bulk-actions)
13. [Customer & Vendor Statements](#13-customer--vendor-statements)
14. [Team & User Management](#14-team--user-management)
15. [Keyboard Shortcuts & UX Tips](#15-keyboard-shortcuts--ux-tips)
16. [Best Practices & FAQ](#16-best-practices--faq)
17. [New Modules & Compliance Features (Sprint 7–12)](#17-new-modules--compliance-features-sprint-712)
18. [Tenant-Specific Guides](#18-tenant-specific-guides)
19. [Sales Commissions](#19-sales-commissions)
20. [Promotional Price Discounts](#20-promotional-price-discounts)
21. [Granular User Permissions (Access Control)](#21-granular-user-permissions-access-control)
22. [Section Hub Pages](#22-section-hub-pages)
23. [3-Mode Voucher Entry](#23-3-mode-voucher-entry)
24. [Printing & Report Formats](#24-printing--report-formats)

---

## 1. GETTING STARTED

### 1.1 First-Time Login

Easy-Books provides **5 pre-seeded demo tenants** for immediate exploration:

| Email | Password | Business Model |
|-------|----------|---|
| `demo.simple@easy-books.app` | `demo1234` | Simple invoicing + billing |
| `demo.services@easy-books.app` | `demo1234` | Services (recurring revenue, time-based billing) |
| `demo.trader@easy-books.app` | `demo1234` | Trading company (buy/resell, inventory) |
| `demo.manufacturing@easy-books.app` | `demo1234` | Manufacturing (BoMs, production orders) |
| `demo.telecom@easy-books.app` | `demo1234` | Telecom Franchise (Tracker, RSO chain, FCA, SIM) |

**Rich mock data included (full year coverage):**
- Each tenant has **100 invoices, 100 bills, 70 payments received, 70 bill payments**
- **25 customers, 25 vendors, 3 bank accounts, 4 payment terms, 6 recurring templates**
- **60+ manual journal entries** covering all COA accounts (rent, salaries, depreciation, GST settlement) spread across the past 365 days
- All invoices and bills have notes, payment terms, and realistic status distributions
- Manufacturing tenant: 50 BoMs, 50 GRNs, 50 production orders, 50 rate plans
- Telecom tenant: full RSO chain, SIM activations, FCA events, franchise agreement

### 1.2 Sample / Demo Data (standalone and desktop installs)

**Both standalone script installs** (`install-and-run.bat` / `.sh`) **and the desktop (Electron) app** come **pre-loaded with the 5 demo companies on first install** — log straight in with password `demo1234`, no setup required:

| Email | Business Model |
|-------|---------------|
| `demo.simple@easy-books.app` | Simple |
| `demo.services@easy-books.app` | Services |
| `demo.trader@easy-books.app` | Trader |
| `demo.manufacturing@easy-books.app` | Manufacturing |
| `demo.telecom@easy-books.app` | Telecom Franchise |

The first install takes an extra ~20–30 seconds while the demo data loads; subsequent starts are fast. **Updating an existing install does not add demo data** — the database is migrated forward in place and your data is left untouched. To install without demo data (clean slate), set `SEED_DEMO=false` before running the installer or launching the desktop app.

The **Settings → Sample / Demo Data** card lets you **Load** or **Remove** the demo companies at any time, regardless of how the app was first installed. (Admin/owner only.)

> **Cloud / dev installs** — demo tenants are pre-seeded automatically; the Settings card is not required.

### 1.3 Create Your Own Business (signup)

1. Go to `/signup`
2. Enter: full name, email, password (≥ 8 characters), company name
3. Select **Business Model** — this determines your Chart of Accounts:
   - **Simple** — core backbone (Cash, AR, AP, Revenue, Expenses)
   - **Services** — + recurring revenue, deferred revenue, subcontractor costs
   - **Trader** — + inventory, COGS, GST input/output
   - **Manufacturing** — + Raw Materials, WIP, Finished Goods, direct labour, overhead
   - **Telecom Franchise** — 56-account franchise template
4. Click **Start Free Trial**

Easy-Books creates your isolated tenant, seeds the COA, and logs you in as `owner`.

---

## 2. COMPANY SETUP & BRANDING

### 2.1 Company Profile

Go to **Settings → Company Profile** to configure your business identity:

| Field | Example | Impact |
|-------|---------|--------|
| Company Name | "Garment Loop Ltd." | Header, all reports, print documents |
| Business Tagline | "Premium Textiles" | Subtitle below company name |
| Address Line 1 | "12 Main Street" | Printed on invoices |
| City | "Lahore" | Printed on invoices |
| Country | "Pakistan" | Printed on invoices |
| Phone | "+92-42-12345678" | Printed on invoices |
| Website | "www.garmentloop.pk" | Printed on invoices |
| Tax ID / NTN | "12-3456789" | Printed on invoices and tax reports |
| Base Currency | PKR / USD / EUR | All transactions denominated in this currency |
| Fiscal Year Start | January / April / July / October | Determines financial year boundaries |

All fields auto-save via `/api/settings` PATCH.

### 2.2 Logo Upload

In **Settings → Company Profile**, click **Upload Logo**:
- Accepted: PNG, JPEG, GIF, WebP (≤ 5 MB)
- Logo appears on all printed documents (invoices, bills, statements)
- Stored per-tenant under `UPLOAD_ROOT/<tenant_id>/`

### 2.3 Document Numbering

In **Settings → Number Formats**, configure format strings:

| Token | Replaced with | Example |
|-------|--------------|---------|
| `{prefix}` | Invoice/Bill prefix from settings | `INV` |
| `{YYYY}` | Current 4-digit year | `2026` |
| `{MM}` | Current 2-digit month | `05` |
| `{seq:04d}` | Zero-padded sequence | `0001` |

Example: `{prefix}-{YYYY}-{seq:04d}` → `INV-2026-0001`

A live preview updates as you type. Number sequences are **tenant-scoped** and **atomic** — concurrent invoices never get the same number.

### 2.4 Payment Terms

In **Settings → Payment Terms**, manage standard terms:

| Code | Name | Days | Usage |
|------|------|------|-------|
| DOR | Due on Receipt | 0 | Immediate payment |
| NET15 | Net 15 Days | 15 | Due in 15 days |
| NET30 | Net 30 Days | 30 | Standard commercial |
| NET60 | Net 60 Days | 60 | Extended credit |

Click **+ Add Term** to create custom terms (e.g., "Net 45 Days").

Assign terms to **customers** and **vendors** — invoices and bills will auto-inherit the term and calculate `due_date = issue_date + days`.

### 2.5 Default GL Accounts

In **Settings → Default GL Accounts**, override the hardcoded posting defaults:

| Account | Default code | Usage |
|---------|-------------|-------|
| AR Account | 1100 | Debited on invoice post |
| AP Account | 2000 | Credited on bill post |
| Revenue Account | 4000 | Credited on invoice post |
| COGS Account | 5010 | Debited on stock sale |

Select accounts from the dropdown — only accounts of the matching type are shown.

---

## 3. ACCOUNTING FUNDAMENTALS

### 3.1 The Double-Entry Rule

Every transaction must balance: **∑Debit = ∑Credit**

Easy-Books enforces this at the database level via `services/posting.py`:
- Unbalanced JVs are rejected before any DB write
- Negative amounts are rejected
- Both-sided rows (Dr > 0 AND Cr > 0) are rejected
- Posting into locked periods is rejected

### 3.2 Chart of Accounts

Go to **Chart of Accounts** (`/coa`) to view and manage your accounts.

| Account code range | Type | Normal balance |
|-------------------|------|---------------|
| 1xxx | Asset | Debit |
| 2xxx | Liability | Credit |
| 3xxx | Equity | Credit |
| 4xxx | Revenue | Credit |
| 5xxx | Expense / COGS | Debit |

Click any account code throughout the app to drill into its ledger.

**Multi-level accounts.** Your Chart of Accounts is organised as a tree: **group/header accounts** (e.g. *Assets → Current Assets*) contain child accounts beneath them. You post only to the **leaf** accounts at the bottom of the tree — group accounts can't take entries; their balances roll up automatically from their children. On the Chart-of-Accounts page you can expand/collapse groups and add a new account under any parent. The financial statements use this same hierarchy to show subtotals (see §9).

### 3.3 Manual Journal Entry

Go to **New Entry** (`/entry`) to post a manual JV:

1. Enter a description
2. Add lines (account, debit amount or credit amount — one per line)
3. Verify the running Dr/Cr totals are equal
4. Click **Post**

The system assigns the next JV number from the tenant's sequence counter.

### 3.4 General Ledger & Journal

- **Journal** (`/journal`) — all posted transactions with date, JV number, description, total. Click any row to see its lines and source documents.
- **General Ledger** (`/ledger`) — all accounts with running balance. Filter by account and date range. When a **date range** is applied, the ledger shows an **Opening Balance** (the net balance of that account from all activity before the start date) and a **Closing Balance** (`Opening + debits − credits` for the period, following each account's normal-balance convention). Without a date filter the ledger shows the all-time running balance.
- **Journal Entry detail** (`/journal/:id`) — lines with account codes hyperlinked to their ledger, source-document links (invoice, bill, payment).

---

## 4. SALES WORKFLOW (AR)

**Compliance:** IAS 18 / IFRS 15 — Revenue recognised when control of goods passes to the customer.

### 4.1 Manage Customers

Go to **Customers** (`/customers`):
- **+ Add Customer** — name, email, phone, address, payment term
- Customer list shows balance outstanding for each customer
- Click a customer name to open their **AR Ledger** (all invoices + payments + running balance)

### 4.2 Create an Invoice

1. Go to **Invoices** → **New Invoice** (or press `N`)
2. Select customer (balance hint shown if they have outstanding)
3. Select **Payment Term** — `due_date` auto-calculates
4. Add line items: product/description, qty, rate
   - Each line can have its own **Tax Code** for per-line GST
5. Add **Notes** (printed on the invoice) and **Internal Memo** (staff-only)
6. Click **Post Invoice**

**GL posted:**
```
Dr 1100  Accounts Receivable    1,170.00
  Cr 4000  Revenue               1,000.00
  Cr 2200  GST Payable             170.00
```

**Invoice statuses (auto-derived):**
| Status | Meaning |
|--------|---------|
| `draft` | Not yet posted — can be edited |
| `posted` | JV posted, awaiting payment |
| `partial` | Part payment received |
| `paid` | Fully settled |
| `overdue` | Past due date, unpaid — auto-flagged |
| `reversed` | JV reversed, balance zeroed |
| `void` | Administratively voided |

### 4.3 Edit a Draft Invoice

If the invoice status is `draft`, a **Edit** button appears in the toolbar. Clicking it opens the create modal pre-filled with existing data. On save, lines are replaced and the JV is re-posted.

**Editing a posted invoice.** You can also edit an invoice *after* it's posted (not just drafts): the system reverses the original entries and re-posts from your changes. This is blocked once the invoice has a payment against it or its date falls in a closed period, and — if the invoice has overselling protection on — an edit that would drive stock negative is rejected too.

**Deferred-revenue products.** If a product is marked **Deferred revenue** (on the product form, with a recognition period in months), its invoice lines don't hit Sales Revenue immediately — they post to **Deferred Revenue** and create a recognition schedule that releases the income over the term. See the **Deferred Revenue** screen to view schedules and run recognition. Editing such an invoice rebuilds its schedule, but is blocked once any period has been recognised.

### 4.4 Reverse an Invoice

Click **Reverse** in the invoice toolbar (only available when a JV has been posted and status ≠ `reversed`). A mirror JV is posted immediately, stock is returned to inventory, and the COGS sub-JV is reversed.

### 4.5 AR Aging

At the bottom of **Invoices**, an **AR Aging Analysis** panel shows:
- Buckets: Current, 1–30, 31–60, 61–90, 90+ days overdue
- A table of the 10 most overdue invoices with days-past
- Amounts are **net of partial payments** (IAS 1.35)

---

## 5. PURCHASE WORKFLOW (AP)

**Compliance:** IAS 2.11 — Purchase recognition when risk of ownership transfers.

### 5.1 Manage Vendors

Go to **Vendors** (`/vendors`):
- **+ Add Vendor** — name, email, phone, address, payment term
- Click a vendor name to open their **AP Ledger** (credit-normal: positive = "we owe")

### 5.2 Record a Bill

1. Go to **Bills** → **+ Record Bill** (or press `N`)
2. Select vendor
3. Select Payment Term — `due_date` auto-calculates
4. Add line items with optional per-line tax code
5. Add notes and internal memo
6. Click **Record**

**GL posted (expense purchase, 17% GST):**
```
Dr 5000  Expense               1,000.00
Dr 1250  GST Input               170.00
  Cr 2000  Accounts Payable      1,170.00
```

**For stock purchases** (product with inventory tracking):
```
Dr 1200  Inventory             1,000.00
Dr 1250  GST Input               170.00
  Cr 2000  Accounts Payable      1,170.00
```

### 5.3 AP Aging

Below the bills list, **AP Aging Analysis** shows outstanding payables by age bucket — use this for cash-flow planning.

---

## 6. PAYMENTS & ALLOCATIONS

### 6.1 Receive a Payment (AR)

1. Go to **Payments Received** → **+ New Payment** (or press `N`)
2. Select customer and payment date
3. A table shows all **open invoices** with their outstanding balance
4. Enter an "Amount to Apply" against each invoice row you want to settle
5. The running total must match the payment amount (warning shown if they differ)
6. Click **Save**

**GL posted:**
```
Dr 1010  Bank               1,170.00
  Cr 1100  Accounts Receivable   1,170.00
```

One payment can settle **multiple invoices** in one step.

### 6.2 Pay a Bill (AP)

1. Go to **Bill Payments** → **+ New Payment** (or press `N`)
2. Select vendor
3. A table shows all open bills — allocate amounts
4. Click **Save**

**GL posted:**
```
Dr 2000  Accounts Payable   1,170.00
  Cr 1010  Bank                 1,170.00
```

---

## 7. INVENTORY MANAGEMENT

**Compliance:** IAS 2.19 — Inventory valued at **Weighted-Average cost**.

### 7.1 Inventory Section

The sidebar has a dedicated **Inventory** section containing:
- **Products** — full product catalogue with category filter
- **Product Categories** (`/products/categories`) — 2-level category manager
- **Product Ledger** (`/products/ledger`) — stock movements per product with running quantity
- **Inventory Performance** (`/inventory/performance`) — on-hand value, low-stock flag, COGS, and sales stats per product

### 7.2 Add a Product

Go to **Products** → **+ Add Product** (or press `N`):
- SKU (unique per tenant)
- Name
- Type: `stock` (tracked inventory) or `service` (no stock)
- Unit (ea, kg, m, hr, etc.)
- Sale price / cost price
- Reorder level — rows highlighted amber when `stock_qty ≤ reorder_level`
- **Category** — pick a parent then a sub-category from the 2-level picker

### 7.3 Product Categories

Stock products support a **2-level taxonomy**: a parent category (e.g., "Electronics") and a sub-category under it (e.g., "Accessories"). Go to **Inventory → Product Categories** (`/products/categories`) to manage them:

- **+ Add Category** — creates a top-level (parent) category
- **+ Add Sub-category** — creates a category under an existing parent
- **Delete** — blocked while a category still has sub-categories or products assigned to it

New tenants receive a small starter set of generic categories seeded for their business model (editable in-app at any time).

**On the product form** (`/products/new` or edit), use the parent → sub-category picker to assign a category. The **Products list** has a category filter dropdown so you can view all products in a given category or sub-category.

### 7.3a On-hand Display & Block Overselling

Invoice and bill line items show **On hand: N** next to stock products so you can see available quantity while entering a sale.

**Settings → Inventory → Block overselling (prevent negative stock on sales)** (`block_negative_stock`, default **off**): when turned on, a sale that would drive a product's stock below zero is rejected with a clear error. Purchases are never blocked regardless of this setting. Turn this on if you want strict stock discipline; leave it off for flexibility (e.g., when you ship before recording a purchase).

### 7.4 Low-Stock Filter

Click the **Low Stock** badge on the dashboard or add `?low_stock=true` to the products URL to filter the list to items at or below reorder level.

### 7.5 Stock Card

Click a product → **Stock Card** (`/products/:id/stock-card`):
- Chronological list of all receipts and issues
- Running quantity and Weighted-Average cost per event
- Current stock value = qty × WAvg cost

### 7.6 COGS posting

When an invoice includes stock items, the system automatically posts a COGS sub-JV:
```
Dr 5010  Cost of Goods Sold     23.76  ← 2 units × WAvg cost
  Cr 1200  Inventory              23.76
```

---

## 8. BANK RECONCILIATION

**Compliance:** IAS 7 — Cash flow statement derived from bank balance reconciliation.

### 8.1 Bank Accounts

Go to **Bank Accounts** → **+ Add Account**:
- Account name, bank name, account number
- Select the GL account code (e.g., 1010 Bank)
- GL balance is always the live balance (no separate ledger)

### 8.2 Import Bank Statement

1. Select a bank account
2. Click **Import Statement**
3. Upload a CSV with 5 columns: `date, description, debit, credit, balance`
4. Easy-Books de-duplicates by SHA-256 hash — re-uploading the same file is safe

### 8.3 Auto-Match & Manual Match

- **Auto-match** tries to link each statement line to a GL transaction by amount + ±3-day date window
- Matched rows show green; unmatched show orange
- Click any unmatched row to manually link it to a transaction

### 8.4 Lock & Close Period

Once all lines are matched, click **Lock & Close** — verifies GL balance = statement balance, locks the period, materialises account balances.

---

## 9. FINANCIAL REPORTING

All reports are **live from the GL** — always current, no batch jobs.

**Hierarchical statements.** Trial Balance, Balance Sheet, and P&L are displayed as an **expandable tree** that mirrors your Chart of Accounts: each group shows a rolled-up subtotal, and you can expand ▸ / collapse ▾ any group to show or hide its child accounts. Click a **leaf account line** to drill straight into its ledger, and from there into the underlying voucher. Turn on **Compare** (period selector) on the Balance Sheet or P&L to show a prior period side-by-side.

| Report | Path | IAS ref |
|--------|------|---------|
| Trial Balance | `/trial-balance` | IAS 1.35 |
| Income Statement (P&L) | `/pl` | IAS 1.99 |
| Balance Sheet | `/balance` | IAS 1.54 |
| Cash Flow | `/cashflow` | IAS 7.20 |
| Tax Summary (GST) | `/tax` | Local tax law |
| AR Aging | `/aging/receivable` | IAS 1.60 |
| AP Aging | `/aging/payable` | IAS 1.60 |
| General Ledger | `/ledger` | IAS 1.45 |
| Customer Ledger | `/customers/:id/ledger` | ISA 230 |
| Vendor Ledger | `/vendors/:id/ledger` | ISA 230 |
| Stock Card | `/products/:id/stock-card` | IAS 2.36(d) |
| Customer Performance | `/customer-performance` | IAS 1 |
| Product Ledger | `/products/ledger` | IAS 2.36(d) |
| Inventory Performance | `/inventory/performance` | IAS 2.36 |

> **Cash Flow tie-out (v2.5+)** — The Cash Flow Statement (**Reports → Cash Flow**) now shows a **reconciling row** at the bottom. If the classified cash movements do not fully account for the change in bank balance, the unclassified amount is highlighted in amber. A ✓ indicator appears when the statement is fully reconciled (per IAS 7).

### 9.2 AR Aging & AP Aging (dedicated pages)

**AR Aging** (`/aging/receivable`) and **AP Aging** (`/aging/payable`) show outstanding balances split into **Current / 1–30 / 31–60 / 61–90 / 90+ days** buckets. Click a customer or vendor row to drill directly to their ledger. (Under **Reports**.)

### 9.3 Product Ledger

**Product Ledger** (`/products/ledger`) shows all stock movements for a selected product with a running quantity after each event. Filter by a single store or choose **Consolidated** to see all stores combined. (Under **Inventory**.)

### 9.4 Inventory Performance

**Inventory Performance** (`/inventory/performance`) provides a per-product summary: on-hand quantity, on-hand value (qty × average cost), a low-stock flag, the date of the last movement, and units sold + COGS over a selected period. (Under **Inventory**.)

### 9.5 Customer Performance

**Customer Performance** (`/customer-performance`) ranks customers by: total revenue billed, number of invoices, outstanding AR balance, and average days to pay. Use this to identify your best-paying and highest-value accounts. (Under **Reports**.)

### 9.6 Report Builder

**Report Builder** (`/reports/builder`) lets you build ad-hoc reports over any whitelisted data source without writing code. Find it under **Reports → Report Builder** in the sidebar.

**Choosing a source** — use the source dropdown at the top of the page to select the dataset you want to query: Invoices, Bills, Journal Entry Lines, Payments Received, Payments Made, Products, Stock Movements, Customers, or Vendors.

**Picking columns** — click **+ Columns** to open the column chooser and tick the fields you want to see. Your selection is applied immediately.

**Click-to-filter** — click any cell in the results table to add an instant equality filter for that value. Active filters appear as removable chips; combine multiple filters for precise slices.

**Manual filters** — use the filter bar to add more precise conditions: choose a field, an operator (equals, contains, gte, in, between, etc.), and a value. The operator list is automatically restricted to those valid for the field's data type.

**Grouping and totals** — choose a **Group by** field from the picker to collapse rows by that dimension. Money and quantity fields that support aggregation will be summed automatically; the totals row appears in the table footer.

**Saving reports** — click **Saved ▾ → + Save current…**, enter a name, and choose **Private** (visible only to you) or **Shared** (visible to everyone in your organisation). Load any saved report from the same menu; delete reports you own with the ✕ button.

**Exporting** — click **Export ▾** to download the current view as **CSV** or **Excel (XLSX)**. Up to 10 000 rows are exported. Use **Print** to send the on-screen table to your printer or save it as a PDF.

### 9.1 Dashboard Quick Actions & KPIs

**Quick Actions** is a horizontal toolbar displayed at the **top of the Dashboard** (directly below the page title). It provides one-click shortcuts to the most common workflows — New Invoice, New Bill, Record Payment, New Journal Entry, and more — without navigating away from the overview.

The dashboard also shows the following KPIs:
- **Net Profit** — revenue minus expenses YTD
- **Cash & Bank** — sum of all bank/cash GL accounts
- **AR Outstanding** — total unpaid invoices
- **AP Due This Week** — bills due within 7 days
- **Overdue Invoices** — count with link to filtered list
- **Low Stock Items** — count with link to low-stock filter
- **AR Aging Chart** — 5-bucket mini-chart
- **Recent Transactions** — last 10 JVs

### 9.7 Customizing Your Dashboard

**(v2.5+)** The Dashboard is fully customizable — rearrange, resize, add, and remove widgets to suit your workflow. Each user's layout is saved independently, so your arrangement does not affect other users' dashboards.

#### Entering and Exiting Customize Mode

Click the **pencil / customize icon** (top-right of the Dashboard) to enter customize mode. A toolbar appears at the top of the page. When you are done:

- Click **Done** to save all changes.
- Click **Cancel** to discard all changes and revert to the previous layout.

#### Rearranging and Resizing Widgets

While in customize mode:
- **Drag** a widget by its header to move it to a new position in the grid.
- **Drag a corner** of a widget to resize it.
- Click the **× button** on a widget to remove it from the dashboard.

#### Per-Breakpoint Layouts

The dashboard maintains **separate layouts for Desktop, Tablet, and Phone**. The customize toolbar displays which breakpoint you are currently editing — **"Desktop layout"**, **"Tablet layout"**, or **"Phone layout"**. To edit the tablet or phone layout, narrow your browser window until the toolbar label changes, then rearrange widgets in that view. Layouts for each breakpoint are saved independently.

#### Adding Widgets

Click **+ Add widget** in the customize toolbar to open the **Add panel**. The panel has two tabs:

| Tab | Contents |
|-----|----------|
| **Widgets** | Data widgets: Bank Balances, Top Products, Inventory Summary |
| **Shortcuts** | Any navigation page pinned as a quick-access tile |

Click any item in the panel to add it to the dashboard.

**Data widgets available:**

| Widget | What it shows |
|--------|--------------|
| **Bank Balances** | Live balances across all your bank accounts at a glance |
| **Top Products** | Your 5 best-selling products by revenue |
| **Inventory Summary** | Total stock value and total on-hand quantity |

#### Shortcut Tiles

Pin any navigation page (Invoices, Bills, Bank Accounts, Products, etc.) as a tile directly on your dashboard. Where applicable, shortcut tiles display a **live metric badge** — for example, "12 overdue" on the Invoices tile, or "£5,420 total" on the Bank Accounts tile. Badges update automatically each time the dashboard loads.

#### Resetting to Defaults

Click **Reset all** in the customize toolbar to remove all customization and restore the default grid layout for every breakpoint.

> **Note** — layouts are tied to your user account. Resetting affects only your own dashboard, not your colleagues'.

---

## 10. PERIOD CLOSE

**Compliance:** IAS 1.49 — Consistent period reporting; reversal-proof once closed.

### 10.1 Create a Period

Settings → **Accounting Periods** → **+ New Period** — enter name and date range.

### 10.2 Close a Period

Select a period → **Close Period**:
- Posts a **Closing JV** (Revenue/Expense → Retained Earnings)
- Locks the period (no further GL writes allowed)
- Materialises account balances into `AccountBalance` for fast reporting

### 10.3 Reopen a Period (Admin only)

Select a period → **Reopen** — reverses the closing JV, clears materialised balances.

---

## 11. RECURRING JOURNAL ENTRIES

Go to **Recurring** (`/recurring`) to manage recurring templates.

### 11.1 Create a Template

Click **+ New Recurring** (or press `N`):
- Name and description
- **Frequency**: daily, weekly, monthly, quarterly, yearly
- **Next Run** date — when the first run fires
- **Journal Lines** — accounts with debit/credit amounts (must balance)

Example: Monthly office rent `Dr Rent Expense 50,000 / Cr Bank 50,000`

### 11.2 Run Templates

Templates with `next_run ≤ today` are highlighted in red.
- Click **Run Now** to fire a single template immediately
- Or POST `/api/recurring/run-due` to fire all due templates at once (use via scheduler / cron)

After each run, `next_run` advances by one period and `last_run` is recorded.

### 11.3 Deactivate / Reactivate

Toggle the active switch in the row — inactive templates are skipped by the run-due sweep.

---

## 12. BULK ACTIONS

### 12.1 Invoice / Bill Bulk Actions

On the Invoices or Bills list page:
1. Check the checkbox column for each row (or check the header to select all)
2. The **floating Bulk Action bar** appears at the bottom showing count
3. Available actions:
   - **Mark Sent** — changes `draft` invoices to `sent` status
   - **Void** — marks selected as `void` (non-reversible administrative action)
   - **Delete** — permanently deletes `draft` invoices/bills (confirms before action)

### 12.2 Customer / Vendor Bulk Export

On the Customers or Vendors list, check rows then use the **Export CSV** button to download selected records.

---

## 13. CUSTOMER & VENDOR STATEMENTS

### 13.1 Customer Statement

1. Go to **Customers** → click a customer → **Customer Ledger**
2. Click **Print Statement** in the toolbar
3. Select a **date range** (defaults to current year)
4. The statement shows:
   - Customer info (name, email, phone)
   - Opening balance
   - All invoices in the period (number, date, due, status, total, outstanding)
   - All payments received
   - Closing balance
5. Click **Print** for a browser print-to-PDF output

### 13.2 Vendor Statement

Same flow via **Vendors** → vendor → **Vendor Ledger** → **Print Statement**.

Shows bills instead of invoices, and "Payments Made" instead of "Payments Received".

---

## 14. TEAM & USER MANAGEMENT

### 14.1 User Roles

| Role | Create/Edit | Settings | Manage Users |
|------|------------|----------|-------------|
| Viewer | — | — | — |
| Accountant | ✓ | — | — |
| Admin | ✓ | ✓ | ✓ |
| Owner | ✓ | ✓ | ✓ |

### 14.2 Add a Team Member

Go to **Team** (`/team`) → **+ Add User**:
- Enter email, full name, role
- Set a temporary password (user is forced to change on first login)
- Or use **Invite Link** — generates a tokenized URL (7-day expiry) that the user clicks to set their own password

### 14.3 Manage Members

From the Team page:
- **Change role** — select from the dropdown (owner can change any role; you can't change your own role)
- **Deactivate** — revokes access immediately (token stops working on next request)
- **Reset password** — generates a new temporary password
- **Last active owner** cannot be deactivated or demoted

### 14.4 My Profile

Go to **Profile** (`/profile`):
- **Avatar** — upload PNG/JPEG/GIF/WebP ≤ 5 MB
- **Personal details** — full name, phone
- **Change password** — current password required
- **Account info** — role, organisation, join date, last login

---

## 15. KEYBOARD SHORTCUTS & UX TIPS

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `N` | Open the "New" modal on any list page (invoices, bills, customers, vendors, products, journal, bank accounts) |
| `Ctrl+P` / `Cmd+P` | Print the current document (on detail/print pages) |

`N` is ignored when focus is inside any input, textarea, select, or contenteditable element.

### Breadcrumbs

All detail pages show a breadcrumb at the top:
```
Invoices › INV-0042
```
Click the first crumb to return to the list. Uses `<Link href>` — works even when navigating directly to a URL.

### Browser Tab Titles

Each page sets a descriptive `document.title`:
- List pages: `Invoices — Easy-Books`
- Detail pages: `Invoices — Easy-Books` (route prefix match)
- Special pages: `Dashboard`, `My Profile`, `Settings`, etc.

### Empty States

All list pages show an icon + message + **gold action button** when empty:
- No customers → "No customers yet" + **+ Add Customer**
- No invoices → "No invoices yet" + **+ Create Invoice**
- etc.

### Filter & Sort

All major list pages (invoices, bills, customers, vendors, products) support:
- **Search** — by name, number, or description
- **Status filter** — multi-select status dropdown
- **Date range** — from/to date pickers
- **Sortable columns** — click any column header to sort; click again to reverse

### Audit Log

Go to **Settings → Audit Log**. Tabs:
- **Timeline** — all entries grouped by day
- **By User** — grouped by who made the change
- **By Entity** — grouped by entity type (Invoice, Bill, Customer, etc.)
- **Export CSV** — download filtered log

---

## 16. BEST PRACTICES & FAQ

### Accounting Hygiene

1. **Reconcile bank monthly** — lock period once balanced
2. **Review AR aging weekly** — follow up on 30+ day overdue invoices
3. **Run trial balance daily** — catch posting errors early; ∑Dr must = ∑Cr
4. **Reverse, don't delete** — deleting posted records loses audit trail
5. **Close periods annually** — prevents accidental backdated edits
6. **Use payment terms** — auto-calculates due dates and feeds the AP-due-this-week tile

### IAS/IFRS Compliance

| Standard | What Easy-Books does |
|----------|---------------------|
| IAS 1.49 | Company name, address, Tax ID printed on all documents |
| IAS 1.60 | Overdue invoices auto-flagged; AR/AP aging net of partial payments |
| IAS 2.19 | Weighted-Average cost (never FIFO or LIFO) |
| IAS 7.20 | Cash flow computed by indirect method from GL |
| IAS 18 / IFRS 15 | Revenue recognised on invoice post |
| IAS 21 | FX rate snapshot at transaction date |
| ISA 230 | Every GL line traceable to source document via clickable links |
| ISA 315 | Double-entry invariants enforced; period-lock; audit trail |

### FAQ

**Q: Can I edit a posted invoice?**  
A: Only `draft` invoices can be edited via the Edit button. Posted invoices must be reversed and re-created, which preserves the full audit trail.

**Q: How does per-line tax work?**  
A: In the invoice/bill create modal, each line can select a tax code from the catalog. The system posts a separate GST JV line per tax code applied.

**Q: Why is my trial balance not balanced?**  
A: All posted transactions are guaranteed balanced by the posting service. If you see a discrepancy, check for manually-entered account adjustments or contact support.

**Q: Can I use multiple currencies?**  
A: Yes. Set base currency in Settings. Each invoice/bill stores the transaction currency and an exchange rate snapshot. Reports convert to base currency at the stored rate.

**Q: How do I set up recurring rent?**  
A: Go to Recurring → New Recurring. Set frequency to `monthly`, next_run to the 1st of next month, and add two lines: Dr Rent Expense / Cr Bank. The system will auto-post this JV each month.

**Q: What does "void" vs "reverse" mean?**  
A: **Reverse** posts a mirror JV (accounting-correct, full audit trail). **Void** is an administrative mark that suppresses the document without touching the GL — use only for documents that were never paid or sent.

**Q: Can I export data?**  
A: Yes — most list pages have an **Export CSV** button. The audit log also has CSV export. Invoices can be downloaded as a **server-generated PDF** (Download PDF button on the invoice detail), and print pages also print to PDF via the browser.

---

## 17. NEW MODULES & COMPLIANCE FEATURES (Sprint 7–12)

These features were added to align Easy-Books with IAS/IFRS and reach parity with Odoo, QuickBooks, and Manager.io.

### 17.1 Credit Notes (ISA 240)

Reduce a customer's balance without editing a posted invoice.
- **Credit Notes** (Receivable section) → **New Credit Note**
- Select customer, optionally link the original invoice, enter line items
- Posts **Dr 4000 Sales Revenue / Cr 1100 Accounts Receivable** — the reverse of an invoice
- Uses a separate `CN-` number sequence; status `draft → posted → applied`

### 17.2 Fixed Assets & Depreciation (IAS 16)

- **Fixed Assets** (Reports section) → **New Asset**
- Enter acquisition cost, salvage value, useful life (months), and method (straight-line or reducing-balance)
- Click **Run Depreciation** each period → posts **Dr 5050 Depreciation Expense / Cr 1090 Accumulated Depreciation**
- Book value updates automatically and depreciation stops at salvage value

### 17.3 Purchase Orders (IAS 2.11)

Pre-approval workflow for purchases (shown for Trader / Manufacturing / Telecom models).
- Raise a PO with vendor + line items → **Approve** (admin+) → **Convert to Bill** when goods arrive
- Conversion creates a `BILL-` document and posts **Dr Expense / Cr 2000 Accounts Payable**

### 17.4 Analytic Accounts / Cost Centers (IAS 1)

- **Analytic Accounts** — create cost-centers, projects, or departments
- Tag journal/invoice/bill lines with an analytic account (optional everywhere)
- **Reports → Analytic P&L** shows revenue and expenses for a single dimension

### 17.5 Deferred Revenue (IFRS 15) — Services model

- Flag a product as deferred with a recognition period
- Invoicing posts to **2300 Deferred Revenue** instead of Revenue
- **Run Recognition** each period moves a slice **Dr 2300 Deferred Revenue / Cr Revenue**

### 17.6 Budgets & Variance (IAS 1)

- **Budgets** — set monthly amounts per account for the fiscal year
- **Budget vs Actual** report shows budget, actual, variance, and variance % (colour-coded)

### 17.7 FIFO Inventory Option (IAS 2.25)

- **Settings → Inventory Cost Method** — choose Weighted-Average (default) or FIFO
- Tenant-wide for IAS 2 consistency; FIFO charges COGS from each layer's own unit cost

### 17.8 Comparative Periods (IAS 1.38)

- On the **Income Statement** and **Balance Sheet**, tick **Compare with prior period**
- A second column shows the prior period side-by-side

### 17.9 FX Revaluation (IAS 21.23)

- Revalues open foreign-currency receivables to the closing rate at period end
- Posts the unrealised gain/loss to **4901 Unrealised FX Gain/Loss**

### 17.10 Bank Reconciliation Zero-Difference (IAS 7.48)

- A reconciliation can no longer be closed while a difference remains — post an adjustment (bank fee, interest) and match it first.

### 17.11 Online Payment Links & Email

- **Payment Link** button on an invoice creates a Stripe Checkout session; the webhook marks the invoice paid automatically (requires `STRIPE_SECRET_KEY`)
- Marking an invoice **Sent** emails the customer, and team invites are emailed (requires SMTP env vars; silently skipped if unset)

### 17.12 Sales Returns (Credit Notes with stock)

A **Credit Note** can double as a sales return. On the Credit Note form, pick a **stock product** on a line:
- The value side posts **Dr Sales Revenue (+ Dr GST Payable) / Cr Accounts Receivable**
- The stock side restocks inventory and posts **Dr Inventory / Cr COGS** — quantity *and* value return to stock (IAS 2)
- Enter a **GST to reverse** amount to unwind output tax on the return

### 17.13 Purchase Returns (Debit Notes)

Go to **Debit Notes** (Payable section) to return goods to a vendor:
- Select the vendor, then the **original bill** the goods came from
- Enter the returned quantity per line; stock is removed at the bill's **original layer cost**
- Posts **Dr Accounts Payable / Cr Inventory (+ Cr GST Input)** — reduces both the payable and inventory
- The return must not exceed the un-sold quantity remaining from that bill

### 17.14 Customer & Vendor Advances

Go to **Advances** to record and apply prepayments:
- **From Customers** — record (**Dr Bank / Cr 2310 Customer Advances**), then *Apply to invoice* (**Dr 2310 / Cr AR**)
- **To Vendors** — record (**Dr 1260 Advances to Vendors / Cr Bank**), then *Apply to bill* (**Dr AP / Cr 1260**)
- Each advance shows its remaining balance and can be applied across multiple documents; applying updates the invoice/bill status automatically

### 17.15 Period Close (Reports → Period Close)

Close accounting periods at the cadence you need:
- **Create a period** with the Monthly / Quarterly / Fiscal-Year presets (fiscal start comes from your Settings).
- **Soft Close** (use for months/quarters) — locks the period against further edits and snapshots balances, but does **not** zero P&L. Within-year income statements stay cumulative and comparable.
- **Year-End Close** — posts the closing journal **Dr Revenue / Cr Expense / Cr-or-Dr Retained Earnings** (net income → RE) and locks. Use only at fiscal year-end.
- **Preview** shows the net income that will roll into Retained Earnings before you commit.
- Balance-sheet accounts **carry forward automatically** — Easy-Books computes balances live from the all-time ledger, so the new period opens with the prior closing balances (no opening-balance journal needed). IAS 1.
- **Reopen** unlocks a period (year-end reopen also reverses the closing JV).

### 17.16 Check for Updates

**Settings → Check for Updates** opens a modal that compares the running version against the latest release on GitHub.

- **Desktop (Electron) app** — if a newer release is available, the update is downloaded and installed automatically via `electron-updater`. Click **Restart to apply** when prompted; your data is preserved.
- **Script / web installs** — the modal shows the `update.bat` (Windows) or `update.sh` (macOS/Linux) command to run in order to pull and apply the update. Data in `~/.easy-books` is never modified by the update process.

In both cases, the database is migrated forward automatically on the next launch (`alembic upgrade head` runs before the servers start), so existing records and settings are preserved.

### 17.18 Drill-down everywhere

Account names, document numbers, and balances are clickable throughout: P&L / Balance Sheet / Cash Flow account rows, Bank Accounts, Telecom KPI tiles, and Recurring template lines all open the **General Ledger** for that account; Fixed Assets open a **Fixed Assets Register** with the full depreciation schedule; Credit/Debit Notes open their detail with links back to the source invoice/bill (ISA 230/315 audit trail).

---

## 18. TENANT-SPECIFIC GUIDES

The in-app **User Guide** (`/guide`) and **Transaction Workflow** (`/workflow`) now adapt to your **business model** — you only see the sections relevant to how your business operates:

| Section | Simple | Services | Trader | Manufacturing | Telecom |
|---------|:------:|:--------:|:------:|:-------------:|:-------:|
| Invoicing, Billing, Credit Notes / Sales Returns, Payments, Journal | ✓ | ✓ | ✓ | ✓ | ✓ |
| Fixed Assets, Budgets, Cost Centers, Tax, Multi-Currency, Reports, Advances, Period Close | ✓ | ✓ | ✓ | ✓ | ✓ |
| Products & Inventory, Purchase Orders, Purchase Returns (Debit Notes) | — | — | ✓ | ✓ | ✓ |
| Deferred Revenue | — | ✓ | — | — | — |
| Manufacturing (BoM, GRN, Production Orders) | — | — | — | ✓ | — |
| Telecom Franchise (Tracker, RSO, FCA, SIM) | — | — | — | — | ✓ |

The model is read from your tenant at login; switching business model (admin API) re-tailors both pages automatically.

---

## 19. SALES COMMISSIONS

Track and post commissions for your sales staff without spreadsheets.

### 19.1 Commission Plans

Go to **Commissions** (`/commissions`) → **Plans** tab → **+ New Plan**:

| Field | Meaning |
|-------|---------|
| **Staff member** | Any user in your tenant |
| **Rate (%)** | Percentage of invoice value earned as commission |
| **Sales target** | Monthly sales threshold (optional) |
| **Recovery target** | Minimum collections threshold (optional) |
| **Target bonus** | Flat bonus paid when both targets are met |
| **Effective from / to** | Plan validity window |

A user can have at most one active plan at a time. Plans can overlap in time (only the latest effective plan is used for computation in that period).

### 19.2 Computing Commissions

Click **Compute** (or `POST /api/commissions/compute`) to run the calculation for a given month:
- Sums all **posted invoices** for each staff member's customers in that period.
- Multiplies by their plan rate.
- Adds the target bonus if both sales and recovery targets are met.
- Creates a `CommissionLedger` entry per user (status: `pending`).

### 19.3 Approve & Post

Review computed entries in the **Ledger** tab:
- **Approve** — marks the entry reviewed and ready to post.
- **Post** — posts the GL entry:

```
Dr Commission Expense (your chosen GL account)
  Cr Commissions Payable   (your chosen GL account)
```

Posted commissions appear in the General Ledger and factor into period-end P&L.

---

## 20. PROMOTIONAL PRICE DISCOUNTS

Automate line-item discounts based on product and quantity rules.

### 20.1 Manage Promo Rules

Go to **Promo Discounts** (`/promo-discounts`) → **+ New Rule**:

| Field | Meaning |
|-------|---------|
| **Name** | Label shown in the "Apply Promos" results |
| **Product** | The product this rule applies to (leave blank to match all) |
| **Min qty** | Minimum units on a line for the rule to apply |
| **Discount %** | Percentage discount applied to `qty × rate` |
| **Valid from / to** | Optional date window |
| **Active** | Toggle on/off without deleting the rule |

### 20.2 Applying Discounts on an Invoice

On the **New Invoice** or **Edit Invoice** form:
1. Add your line items as usual.
2. Click **Apply Promos** (appears above the line-items table).
3. Easy-Books calls `/api/promo-rules/check` and applies matching discounts to each line.
4. Discount percentages appear in the **Disc%** column (highlighted green when > 0).
5. The line amount recalculates as `qty × rate × (1 − discount_pct / 100)`.

You can also manually type a discount % in the **Disc%** column on any line — this overrides the rule suggestion.

### 20.3 GL Impact

Promo discounts reduce the invoice **subtotal** before GST is applied. The posted journal entry reflects the discounted net:

```
Dr  Accounts Receivable     (net × 1.17 with 17% GST)
  Cr  Sales Revenue           (discounted net)
  Cr  GST Payable              (net × 0.17)
```

No separate "discount expense" account is used — the lower revenue is the correct IAS/IFRS treatment for trade discounts per IAS 18.10.

---

## 21. GRANULAR USER PERMISSIONS (ACCESS CONTROL)

Beyond the four RBAC roles (owner / admin / accountant / viewer), **User Permissions** lets you fine-tune exactly what each team member can see and do, down to individual modules.

### 21.1 Enable the Module

Go to **Settings → Permissions** and turn on **"Granular user access control"**. Once on:
- The admin permissions matrix becomes visible.
- Permissions are evaluated **per-user, per-resource** (role is still the base; permissions can only restrict, not elevate beyond the role).

### 21.2 The Permissions Matrix

Go to **Settings → Permissions** → **Manage Permissions** (`/settings/permissions`):
- A grid of 60 resources (Invoices, Bills, Customers, Vendors, Products, Payments, Reports, etc.) × team members.
- For each cell pick: **Default** (inherits role), **View** (read-only), **Edit** (full write), or **None** (blocked).
- Save per-user with the **Save** button on that user's row.

### 21.3 My Data Only

Toggle **"My data only"** for a user to restrict their list views to records they personally created:
- Invoices list shows only invoices created by them.
- Bills, customers, vendors, products, etc. follow the same filter.
- Individual record access is still controlled by the access-level setting.

Useful for sales teams where each rep should see only their own accounts.

### 21.4 Effect on the UI

When a user accesses a page they're not permitted to view, a **No Access** banner is shown in place of the page content. Sidebar links they can't access are still visible but return the banner on navigation (they do not disappear — hiding links can be confusing because the URL still works from bookmarks).

### 21.5 API

- `GET /api/permissions/me` — current user's effective permission set.
- `GET /api/permissions/users/{id}` — admin view of another user's permissions.
- `PUT /api/permissions/users/{id}` — set overrides for a user.
- `PATCH /api/permissions/users/{id}/my-data-only` — toggle the my-data-only flag.

---

## 22. SECTION HUB PAGES

Each major sidebar section now opens a **command-centre hub** before drilling into sub-pages. Access them via the sidebar section headers.

| URL | Hub name | What you see |
|-----|----------|--------------|
| `/receivable` | Receivables Overview | Aging summary (Current / 1–30 / 31–60 / 61–90 / 90+), top overdue customers |
| `/payable` | Payables Overview | AP aging buckets, top overdue vendors |
| `/inventory` | Inventory Overview | Low-stock alerts list, total on-hand value, item counts |
| `/banking` | Banking Overview | Live bank account balances derived from the GL |

### 22.1 Navigating to a Hub

Click any sidebar **section header** (e.g. "Receivable", "Inventory") — the header itself is a link to the hub. From the hub you can drill further into aging detail pages, customer/vendor ledgers, or individual bank accounts.

### 22.2 Collapsible Sidebar

The sidebar has three states:

| State | How to enter |
|-------|-------------|
| **Collapsed** (icon-only strip) | Click the ← collapse button in the sidebar header |
| **Open** (full labels) | Click the → expand button, or hover over the collapsed strip |
| **Pinned** (always open) | On a wide screen the sidebar auto-pins; you can also pin/unpin manually |

Hover over the collapsed sidebar to see a floating panel with full nav labels and sub-items. State is remembered per browser via `localStorage`.

---

## 23. 3-MODE VOUCHER ENTRY

The **New Entry** form (`/journal/new`) supports three distinct modes selectable at the top:

| Mode | Voucher prefix | Use case |
|------|---------------|----------|
| **Journal** | JV | General-purpose double-entry — pick any GL accounts |
| **Payment** | CP (cash) / BP (bank) | Record a payment made; select Cash or Bank account + payee |
| **Receipt** | CR (cash) / BR (bank) | Record money received; select Cash or Bank account + payer |

### 23.1 Journal Mode

Both debit and credit account pickers show the full Chart of Accounts. Use for inter-account transfers, depreciation, accruals, opening balances, and any entry that doesn't fit the standard AR/AP workflows.

### 23.2 Payment Mode

1. Choose **Cash** or **Bank** from the top selector — this sets the instrument account (e.g. Petty Cash or HBL Current).
2. The debit side defaults to the chosen cash/bank account (money going out).
3. Pick the expense or liability account on the credit side.
4. Enter a **Payee** name (optional but recommended for reporting).
5. The JV prefix auto-sets to **CP** (Cash Payment) or **BP** (Bank Payment).

### 23.3 Receipt Mode

Mirror of Payment mode — the chosen cash/bank account appears on the credit side (money coming in). Prefix auto-sets to **CR** or **BR**.

> **Tip:** For settling AR/AP balances, use the dedicated **Payments Received** and **Bill Payments** screens instead of the Receipt/Payment voucher form — they allocate against specific invoices/bills and update outstanding balances.

---

## 24. PRINTING & REPORT FORMATS

### 24.1 How to Print

Every report and list page has a **Print** button (printer icon) in the toolbar. Clicking it triggers the browser's native print dialog. The page automatically:
- Hides all UI controls (filters, pagination, sort handles, action buttons, checkboxes).
- Applies the correct paper orientation for the content.
- Renders in black-and-white dot-matrix style (no coloured backgrounds or fills).

### 24.2 Page Orientations

| Orientation | Pages |
|-------------|-------|
| **Portrait** | General Ledger, Cash Book, Bank Book, Balance Sheet, Income Statement, Trial Balance, Cash Flow, Tax Summary, Customer/Vendor Statements, Payments lists, Chart of Accounts, all voucher detail pages |
| **Landscape** | AR/AP Aging, Customer Performance, Inventory Performance, Product Ledger, Journal list, Invoices list, Bills list, Products list, Customer/Vendor Ledgers, Stock Card |

Orientation is applied automatically — no manual page-setup is required.

### 24.3 Date Format

All dates are displayed as **`dd-mm-yy`** (e.g. `20-06-26` for 20 June 2026) across the entire system — both on-screen and in print. This applies to table cells, report subtitles, print headers, statement period labels, and CSV exports.

### 24.4 Amount Display

- **Negative amounts** appear as `(1,234.56)` — parentheses instead of a minus sign, matching accounting convention.
- **Currency code** is shown once in the column header (e.g. "Debit (PKR)") — individual cells contain bare numbers without repetition.
- **Zero sides** in debit/credit columns show `—` instead of `0.00`.

### 24.5 Voucher Numbers in Reports

JV numbers carry their type as a prefix (e.g. `CP-2026-001` = Cash Payment, `SL-2026-042` = Sales Invoice). There are no separate "type" badge labels in report tables — the prefix is the type indicator.
- `GET /api/permissions/resources` — full list of 60 protected resource keys.
