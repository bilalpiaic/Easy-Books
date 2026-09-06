# Easy-Books User Guide

> A comprehensive guide to using Easy-Books for double-entry accounting, compliant with **IAS/IFRS standards**.

**Last updated:** 2026-09-06 · **Version:** 5.2.0

---

## Table of Contents

1. [Getting Started](#1-getting-started)
   - 1.4 [Keeping Easy-Books Up to Date](#14-keeping-easy-books-up-to-date)
2. [Company Setup & Branding](#2-company-setup--branding)
3. [Accounting Fundamentals](#3-accounting-fundamentals)
4. [Sales Workflow (AR)](#4-sales-workflow-ar)
5. [Purchase Workflow (AP)](#5-purchase-workflow-ap)
6. [Payments & Allocations](#6-payments--allocations)
7. [Inventory Management](#7-inventory-management)
8. [Bank Reconciliation](#8-bank-reconciliation)
9. [Financial Reporting](#9-financial-reporting)
   - 9.1 [Dual Home Dashboards (Financial | Operations)](#91-dual-home-dashboards-financial--operations)
   - 9.2 [Dashboard Quick Actions & KPIs](#92-dashboard-quick-actions--kpis)
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
25. [UI Preferences — Theme, Language & Layout](#25-ui-preferences--theme-language--layout)
26. [Payroll](#26-payroll)
27. [Attendance Register](#27-attendance-register)
28. [PRA e-Invoice (Pakistan)](#28-pra-e-invoice-pakistan)
28a. [Saudi ZATCA e-Invoice](#28a-saudi-zatca-e-invoice)
28b. [Peppol / EU VAT e-Invoice](#28b-peppol--eu-vat-e-invoice)
28c. [India GST](#28c-india-gst)
28d. [Withholding Tax & CIT Worksheet](#28d-withholding-tax--cit-worksheet)
29. [Modules & the Add-ons Page](#29-modules--the-add-ons-page)
    - 29.5 [Marketplace](#295-marketplace)
    - 29.6 [Settings Studio](#296-settings-studio)
30. [Healthcare Module](#30-healthcare-module)
31. [Universal Search (Ctrl+K)](#31-universal-search-ctrlk)
32. [In-app Update Notifications](#32-in-app-update-notifications)
33. [Sidebar Navigation (Auto-hide)](#33-sidebar-navigation-auto-hide)
34. [Purchases & Store — Procure-to-Pay & Dispatch Control](#34-purchases--store--procure-to-pay--dispatch-control)
35. [AI Financial Assistant](#35-ai-financial-assistant)
36. [Calculator](#36-calculator)
37. [IFRS 16 Leases](#37-ifrs-16-leases)
38. [Group Consolidation (IFRS 10)](#38-group-consolidation-ifrs-10)
38a. [Intercompany Documents](#38a-intercompany-documents)
39. [Inventory Valuation Depth](#39-inventory-valuation-depth)
40. [Save PDF troubleshooting](#40-save-pdf-troubleshooting)
41. [Weighbridge (mill Marketplace listing)](#41-weighbridge-mill-marketplace-listing)

---

## 1. GETTING STARTED

### 1.1 First-Time Login

Easy-Books provides **9 pre-seeded demo tenants** for immediate exploration:

| Email | Password | Business Model |
|-------|----------|---|
| `demo.simple@easy-books.app` | `demo1234` | Simple invoicing + billing |
| `demo.services@easy-books.app` | `demo1234` | Services (recurring revenue, time-based billing) |
| `demo.trader@easy-books.app` | `demo1234` | Trading company (buy/resell, inventory) |
| `demo.manufacturing@easy-books.app` | `demo1234` | Manufacturing (BoMs, production orders; Marketplace **Weighbridge**) |
| `demo.telecom@easy-books.app` | `demo1234` | Telecom Franchise (Tracker, RSO chain, FCA, SIM) |
| `demo.pra@easy-books.app` | `demo1234` | PRA e-Invoice — Pakistani retail (PKR, NTN/CNIC, PCT codes, FINs) |
| `demo.hospital@easy-books.app` | `demo1234` | Healthcare — hospital/clinic (OPD, IPD, Lab, Procedures, Store) |
| `demo.spinning@easy-books.app` | `demo1234` | Yarn Spinning Mill (bale receipt, lots, stages, cones, dispatch; Marketplace **Weighbridge**) |
| `demo.processing@easy-books.app` | `demo1234` | Textile Processing Unit (grey inward / processing floor) |

**Rich mock data included (full year coverage):**
- Each tenant has **100 invoices, 100 bills, 70 payments received, 70 bill payments**
- **25 customers, 25 vendors, 3 bank accounts, 4 payment terms, 6 recurring templates**
- **60+ manual journal entries** covering all COA accounts (rent, salaries, depreciation, GST settlement) spread across the past 365 days
- All invoices and bills have notes, payment terms, and realistic status distributions
- Manufacturing tenant: 50 BoMs, 50 GRNs, 50 production orders, 50 rate plans
- Telecom tenant: full RSO chain, SIM activations, FCA events, franchise agreement
- PRA tenant: invoices with FINs, PKR currency, NTN/CNIC on customers, PCT codes on products, and a PRA submission-log audit trail
- Promo rules, commission plans + a 3-month commission ledger (draft/approved/posted), accounting periods (incl. a locked prior year), bank reconciliations, and an imported bank statement per tenant
- **Hospital tenant: 5 doctors, 4 wards (38 beds), 50 patients, ~200 OPD tokens/visits, 20 admissions, 80 lab orders, 25 procedure orders**
- **v5 IFRS / tax demos (seeded):** analytic dimensions + multi-slot JE tags; services tenant — SSP multi-element invoice + open contract asset; manufacturing↔trader IC invoice/bill mirrors + consolidation graph; asset components + impairment + one disposal; WHT tax code + CIT adjustments; localization modules on selected demos (ZATCA on manufacturing, India GST on trader, Peppol on services) with sample settings + submission-log rows

### 1.2 Sample / Demo Data (standalone and desktop installs)

**Both standalone script installs** (`install-and-run.bat` / `.sh`) **and the desktop (Electron) app** come **pre-loaded with the 9 demo companies on first install** — log straight in with password `demo1234`, no setup required:

| Email | Business Model |
|-------|---------------|
| `demo.simple@easy-books.app` | Simple |
| `demo.services@easy-books.app` | Services |
| `demo.trader@easy-books.app` | Trader |
| `demo.manufacturing@easy-books.app` | Manufacturing |
| `demo.telecom@easy-books.app` | Telecom Franchise |
| `demo.pra@easy-books.app` | PRA e-Invoice |
| `demo.hospital@easy-books.app` | Healthcare / Hospital |
| `demo.spinning@easy-books.app` | Yarn Spinning Mill |
| `demo.processing@easy-books.app` | Textile Processing |

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
   - **PRA e-Invoice** — Pakistani retail (PKR, PRA eIMS real-time submission, FIN printing)
4. Click **Start Free Trial**

Easy-Books creates your isolated tenant, seeds the COA, and logs you in as `owner`.

### 1.4 Keeping Easy-Books Up to Date

Your accounting data is never deleted during an update — migrations run automatically and add new columns/tables while leaving existing data in place.

**Script install (Windows):** Double-click `update.bat` in the Easy-Books folder.

**Script install (macOS / Linux):** Run `./update.sh` in the Easy-Books folder.

Both scripts run `git pull` then re-invoke the installer, which rebuilds the frontend when the code has changed and runs `alembic upgrade head` before restarting. Your data in `~/.easy-books` (or `%USERPROFILE%\.easy-books`) is never touched.

**Desktop app:** The app checks for updates on every launch. When a newer release is available you will see an in-app prompt — click **Download** then **Restart** to apply. You can also check manually via **Settings → Check for Updates**.

**Developer mode:**
```bash
git pull
cd backend && uv sync && uv run alembic upgrade head
cd ../frontend && npm install
# Restart both servers
```

**Version:** You can always check the running version at **Settings → About** or by calling `GET /api/version`.

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
| Fiscal Year Start | January / April / July / October | Determines financial year boundaries; drives the report Fiscal Year/Quarter presets (§9, Report Period Filter) |
| Week Starts On | Monday / Sunday | Drives the report This Week / Last Week presets (§9, Report Period Filter) |

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

### 2.6 Overdue Reminders

In **Settings → Preferences**, under **Email Notifications**:

1. Toggle **Email Notifications** on.
2. A new field appears: **Overdue Reminder Interval** — how many days to wait between reminder emails per overdue customer (default 7).

When enabled, Easy-Books runs a daily background check that:
- Flips any invoice that's past its due date and still unpaid to **Overdue** status (this also happens automatically whenever you view the invoice list, but the background check catches it even if nobody opens the app that day).
- Sends **one email per customer** listing every overdue invoice they owe and the total balance due — not one email per invoice, so a customer with three overdue invoices gets a single consolidated reminder.
- Respects the interval you set: a customer who was already emailed within the last N days isn't emailed again on the next check.

Reminders require a customer to have an email address on file and require SMTP to be configured on the server (`SMTP_HOST` env var) — without SMTP configured, the checks still run and update invoice statuses, but no email is actually sent.

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

> **Need requisition → quotation → approval controls before a bill is even created?** That's the **Purchases & Store** module — see §34 for the full Demand → Comparative → PO → Gate Inward chain, plus outbound dispatch control (Gate Outward) for sales, returns, and scrap.

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

**Report Period Filter.** Every report's date filter opens with a **Period** dropdown offering the same 26 presets QuickBooks uses — Today, This Week / Last Week / Next Week, This Month / Last Month, This Fiscal Quarter / Last Fiscal Quarter / Next Fiscal Quarter, This Fiscal Year / Last Fiscal Year / Next Fiscal Year, plus year-to-date and quarter-to-date variants, and **Custom** for a manual range. Choosing a preset fills the From/To fields for you and locks them (grey out) so you can't accidentally edit a preset range by hand; choosing **Custom** unlocks them again. The Fiscal Year/Quarter presets follow your **Fiscal Year Start** setting (§2.1) and the Week presets follow your **Week Starts On** setting — so if your fiscal year starts in July, "This Fiscal Quarter" always means the right three months for your business, not the calendar quarter.

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

### 9.1 Dual Home Dashboards (Financial | Operations)

The home page supports **two separately maintained dashboards**:

| Home | Route | Audience | Contents |
|------|-------|----------|----------|
| **Financial** | `/dashboard` (or `/dashboard?view=financial`) | Financial managers & management P&amp;L review | Revenue, expenses, net profit, cash &amp; bank, AR/AP, aging, trends, day book |
| **Operations** | `/dashboard/operations` | Operations & production visibility | Module-aware KPIs — spinning lots/yield, manufacturing WIP, weaving efficiency, healthcare census, telecom tracker floats, purchase pipeline, textile processing |

**How to open Operations**

1. Log in as a mill / industry tenant (e.g. `demo.spinning@easy-books.app` / `demo1234`, or manufacturing, hospital, telecom).
2. Click **Dashboard** in the top nav — the tab becomes a menu when a purpose module is installed — then **Operations**.
3. Or use the **Operations** item in the Dashboard SubNav rail, or press Ctrl+K and type `operations dashboard`.

The **Financial | Operations** segmented control under the page title also switches homes. Both the nav item and the toggle appear only when a purpose module is installed (production, spinning, weaving, healthcare, telecom, purchase_store, textile_processing). Pure Base / Services tenants stay Financial-only.

**Default landing by tenant segment**

| Business model / pack | Default home |
|-----------------------|--------------|
| simple, services, trader (no purchase_store) | Financial |
| manufacturing, yarn_spinning, textile_processing, hospital, telecom_franchise | Operations |
| PRA portal mode | `/pra-dashboard` (unchanged) |

Set your preferred login home under **Settings → Advanced → Home dashboard** (`localStorage` key `eb.home_dashboard` = `financial` \| `operations` \| `pra`). Staff Rights (when enabled) expose **Dashboard → Financial Dashboard** and **Dashboard → Operations Dashboard**.

### 9.2 Dashboard Quick Actions & KPIs

**Quick Actions** sit at the top of each home. Financial defaults: New Invoice, New Bill, New Entry, Products…. Operations defaults swap in module shortcuts (New Demand, Spin Lots, OPD, Tracker…) filtered by installed modules.

**Financial KPIs include:**
- **Net Profit** — revenue minus expenses YTD
- **Cash & Bank** — sum of all bank/cash GL accounts
- **AR Outstanding** — total unpaid invoices
- **AP Due This Week** — bills due within 7 days
- **Overdue Invoices** — count with link to filtered list
- **Low Stock Items** — count with link to low-stock filter
- **AR Aging Chart** — 5-bucket mini-chart
- **Recent Transactions** — last 10 JVs

**Operations KPIs** vary by installed pack (open lots / yield %, WIP cost, bed occupancy, load float, open demands…). Each tile deep-links into the module dashboard (e.g. `/spinning/dashboard`, `/healthcare`).

### 9.7 Customizing Your Dashboard

**(v2.5+ / dual-home v4)** Each home is fully customizable — rearrange, resize, add, and remove widgets. Financial and Operations layouts are saved **independently** per user (schema v4 under `/api/dashboard/layout`).

#### Entering and Exiting Customize Mode

1. Switch to the home you want to edit (Financial or Operations).
2. Click **Customize** (top-right). The toolbar labels which home you are editing.
3. Click **Done** to save that home, or **Cancel** to discard.

#### Rearranging and Resizing Widgets

While in customize mode:
- **Drag** a widget by its header to move it to a new position in the grid.
- **Drag a corner** of a widget to resize it.
- Click the **× button** on a widget to remove it from the active home.

#### Per-Breakpoint Layouts

Each home maintains **separate layouts for Desktop, Tablet, and Phone**. The customize toolbar displays which breakpoint you are currently editing — **"Desktop layout"**, **"Tablet layout"**, or **"Phone layout"**.

#### Adding Widgets

Click **+ Add widget** — the panel is filtered to the active home:

| Home | Example widgets |
|------|-----------------|
| **Financial** | Bank Balances, Top Products, Inventory Summary, HRM & Payroll, trend charts |
| **Operations** | Ops KPIs, pipeline, alerts, Spinning / Weaving / Production / Healthcare / Telecom / Purchases / Processing summaries |
| **Shortcuts** (both) | Any navigation page pinned as a quick-access tile |

#### Resetting to Defaults

Click **Reset all** to restore the default grid for the **active home** across breakpoints.

> **Note** — layouts are tied to your user account. Resetting Financial never clears Operations (and vice versa).

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
- **Authenticator 2FA** — set up TOTP; on production (`REQUIRE_OWNER_TOTP=true`) owners are sent here after login until 2FA is on, and they cannot disable it
- **Account info** — role, organisation, join date, last login

---

## 15. KEYBOARD SHORTCUTS & UX TIPS

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `N` | Open the "New" modal on any list page (invoices, bills, customers, vendors, products, journal, bank accounts) |
| `Ctrl+P` / `Cmd+P` | Print the current document (on detail/print pages) |

`N` is ignored when focus is inside any input, textarea, select, or contenteditable element.

The floating **Calculator** widget (§36) also responds to the keyboard — digits, `+ - * /`, `Enter`/`=`, `Backspace`, `Escape`/`Delete`, `%` — while it's open, with the same guard against stealing keystrokes from other fields.

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

### 17.2 Fixed Assets & Depreciation (IAS 16 / IAS 36)

- **Fixed Assets** (Accounting) → **New Asset**
- Enter acquisition cost, salvage value, useful life (months), and method (straight-line or reducing-balance)
- Optional **parent** asset: register components with their own lives under a roll-up parent (parents are not depreciated)
- Click **Run Depreciation** each period → posts **Dr 5050 Depreciation Expense / Cr 1090 Accumulated Depreciation**
- **Impair / Reverse** (asset detail): recoverable amount vs carrying → posts impairment loss (**5061**) against accum. depreciation; reversals capped at cumulative impairment (IAS 36 simplified)
- **Dispose** (sale or scrap): full GL derecognition with gain (**4904**) / loss (**5062**) and proceeds to a bank/cash account
- Book value = cost − accum. depreciation − accum. impairment; depreciation stops at salvage
- **Asset Rollforward** (`/assets/rollforward`) — opening / additions / disposals / dep / impairment / closing for a date range (landscape print)

### 17.3 Purchase Orders (IAS 2.11)

Pre-approval workflow for purchases (shown for Trader / Manufacturing / Telecom models).
- Raise a PO with vendor + line items → **Approve** (admin+) → **Convert to Bill** when goods arrive
- Conversion creates a `BILL-` document and posts **Dr Expense / Cr 2000 Accounts Payable**

### 17.4 Analytic Accounts / Cost Centers (IAS 1) + Dimensions (#260)

- **Dimensions** — define up to **3** analytic dimension types (e.g. Cost Center / Project / Location) under Analytic Accounts. Mark one as **required** to force tagging on JE / invoice / bill lines.
- **Analytic values** — create cost-centers, projects, or departments under a dimension (legacy flat `type` still works)
- Tag documents with up to three slots (`analytic_account_id`, `analytic_2_id`, `analytic_3_id`)
- **Reports → Analytic P&L** and **Dimensional P&L** show revenue and expenses sliced by dimension

### 17.5 Deferred Revenue (IFRS 15) — Services model

- Flag a product as deferred with a recognition period
- Invoicing posts to **2300 Deferred Revenue** instead of Revenue
- **Run Recognition** each period moves a slice **Dr 2300 Deferred Revenue / Cr Revenue**
- **Standalone Selling Price (SSP)** on a product (or per invoice line) drives relative allocation when an invoice has two or more SSP-tagged lines — line amounts are reallocated so they sum to the transaction price; an audit trail is stored on the invoice
- **Contract Balances** (Accounting → Contract Balances) shows unearned liability (remaining deferred schedules) and unbilled **contract assets** by customer. Use **Certify unbilled** to post **Dr 1140 Contract Asset / Cr Revenue** when a performance obligation is satisfied before billing; settle those assets on a later invoice via `contract_asset_ids` so the invoice credits 1140 instead of Revenue again

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

| Section | Simple | Services | Trader | Manufacturing | Telecom | PRA | Spinning | Hospital | Processing |
|---------|:------:|:--------:|:------:|:-------------:|:-------:|:---:|:--------:|:--------:|:----------:|
| Invoicing, Billing, Credit Notes / Sales Returns, Payments, Journal | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Fixed Assets, Budgets, Cost Centers, Tax, Multi-Currency, Reports, Advances, Period Close | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Products & Inventory, Purchase Orders, Purchase Returns (Debit Notes) | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Purchases & Store (Demand→Comparative→PO→Gate Inward, Gate Outward) — §34 | — | — | — | ✓ | — | — | ✓ | — | ✓ |
| Deferred Revenue | — | ✓ | — | — | — | — | — | — | — |
| Manufacturing (BoM, GRN, Production Orders) | — | — | — | ✓ | — | — | — | — | — |
| Telecom Franchise (Tracker, RSO, FCA, SIM) | — | — | — | — | ✓ | — | — | — | — |
| PRA e-Invoice (FIN, NTN/CNIC, PCT codes, pra_status) | — | — | — | — | — | ✓ | — | — | — |
| Yarn Spinning (lots, bale receipt, stages, cones, dispatch) — §30A | — | — | — | — | — | — | ✓ | — | — |
| Healthcare (OPD/IPD/Lab) | — | — | — | — | — | — | — | ✓ | — |
| Textile Processing (grey lots, PPC stages) | — | — | — | — | — | — | — | — | ✓ |
| **Operations home dashboard** (dual-home toggle) | — | — | ◐* | ✓ | ✓ | — | ✓ | ✓ | ✓ |

\* Trader shows Operations when `purchase_store` is installed.

**Default home after login:** Financial for simple/services/trader; Operations for manufacturing, spinning, hospital, telecom, textile processing (see §9.1).

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

---

## 25. UI PREFERENCES — THEME, LANGUAGE & LAYOUT

### 25.1 Dark Mode

Easy-Books supports three display modes that you can cycle through by clicking the **theme icon** (sun/moon) in the top-right header:

| Mode | Behaviour |
|------|-----------|
| **Light** | Always light background regardless of OS setting |
| **Dark** | Always dark background and inverted text colours |
| **System** | Follows your operating system's light/dark preference automatically |

The active mode is stored in your browser (`localStorage` key `eb.theme`) and remembered across sessions. It applies per-browser — other users in the same tenant are not affected.

### 25.2 Color Themes

Five color themes are available under **Settings → Appearance**:

| Theme | Accent color |
|-------|-------------|
| **Gold** (default) | `#b8943f` — the classic Easy-Books gold palette |
| **Emerald** | Green accent |
| **Sapphire** | Blue accent |
| **Rose** | Pink/red accent |
| **Slate** | Neutral grey accent |

Click a color swatch in the Appearance card to switch instantly. The preference is stored in `localStorage` (`eb.color`) and persists across sessions. It is per-browser and does not affect other users.

### 25.3 Language

Click the **globe icon** in the top-right header to open the language dropdown:

| Language | Script | Direction |
|----------|--------|-----------|
| **English** | Latin | LTR |
| **Urdu** (اردو) | Nastaliq | RTL — the entire layout mirrors right-to-left automatically |
| **Chinese** (中文) | Simplified Han | LTR |

Switching language re-renders all 134 translated pages and components immediately — no page reload required. The preference is saved in `localStorage` (`eb.lang`) and synced to your account settings (`app_language`) so it persists when you log in from a different browser.

**Coverage:** 314 translation keys across 10 namespaces: navigation labels, section titles, common action buttons (Save / Cancel / Print / Export CSV), status badges (Draft / Posted / Paid / Partial / Overdue), table column headers, page titles, dashboard KPI labels, hub page text, auth screens, and all settings labels.

**RTL note:** When Urdu is selected, the sidebar appears on the right, page padding mirrors, and the Noto Nastaliq Urdu font is loaded automatically for correct Nastaliq calligraphy rendering.

### 25.4 Mobile Layout

All pages are fully usable on phone-sized screens. Key adaptations:
- **Page titles** scale down on small screens (`text-xl` on phones, `text-3xl` on desktop).
- **Stats grids** stack 2-per-row on phones rather than showing 3 or 4 columns side-by-side.
- **Form grids** collapse to single-column on narrow screens (invoice form, bill form, payment forms, product form).
- **Button toolbars** wrap so Export / Print / New buttons don't overflow.
- **Line-item tables** gain horizontal scroll (`overflow-x-auto`) so you can swipe to see all columns.
- **Sidebar** collapses to icon-strip by default on narrow screens; tap to expand.

---

## 26. PAYROLL

Manage your full payroll cycle — from setting up salary components and employee structures to running, approving, posting to the GL, and printing payslips.

### 26.1 Setting Up Salary Components

Go to **Payroll → Salary Components** (`/payroll/components`):

- Click a row to edit it inline, or use **+ Add Component** to create a new one.
- Fill in:

| Field | Description |
|-------|-------------|
| **Code** | Short identifier (e.g. `BASIC`, `HRA`, `INCOME_TAX`) |
| **Name** | Display name shown on payslips |
| **Type** | `earnings` / `deductions` / `statutory` |
| **GL Account** | The ledger account this component posts to (e.g. 5200 Salary Expense, 2300 Salaries Payable) |
| **Is Fixed** | When on, amount is a flat amount; when off, amount is treated as % of basic salary |
| **Is Taxable** | Marks whether the component is subject to income tax |

Salary components are a shared catalog across your organisation — each employee's structure then specifies the amounts.

### 26.2 Adding Employees

Go to **Employees** (`/employees`) → **+ New Employee**:

- **Employee code** is auto-generated (EMP-0001 sequence).
- Fill in: full name, department, designation, join date, CNIC, bank account, bank name.
- Toggle **Active** to control whether the employee appears in payroll runs.

Click **Save** to create the employee. Soft-deleted employees (`is_active = false`) are hidden from new runs but their historical payslips are preserved.

### 26.3 Configuring an Employee's Salary Structure

Open an employee → **Salary Structure** tab (`/employees/[id]/edit`):

1. Click **+ Add Component** to select a component from the catalog.
2. Enter either a flat **Amount** or a **% of Basic** depending on the component's `is_fixed` flag.
3. Set an optional **Effective From / To** date range.
4. Repeat for each earning, deduction, and statutory component.
5. Click **Save Structure** — this replaces the employee's entire structure atomically.

The structure is used when a payroll run is created to auto-compute each employee's gross earnings, deductions, and net pay.

### 26.4 Running Payroll

Go to **Payroll → New Payroll Run** (`/payroll/new`):

1. Enter **Period Start** and **Period End** (e.g. 01-06-26 to 30-06-26).
2. Set the **Pay Date**.
3. Click **Create Run** — the system fetches every active employee's salary structure and auto-computes:
   - Gross earnings (sum of all `earnings` components)
   - Total deductions (sum of all `deductions` + `statutory` components)
   - Net pay (gross − deductions)
4. Review the computed lines in the run detail page (`/payroll/[id]`). In **Draft** status you can edit individual line amounts inline if an override is needed.

### 26.5 Approve and Post to GL

From the run detail page:

**Approve** — marks the run `Approved`. No GL entry yet; this step is a human review gate.

**Post to GL** — changes status to `Posted` and creates a balanced Transaction (voucher type `PR`, numbered PR-YYYY-seq):

```
Dr  Salary Expense (5xxx — per component GL account)   5,200.00
  Cr  Salaries Payable (2xxx — net pay)                4,100.00
  Cr  Income Tax Payable                                  600.00
  Cr  EOBI Payable                                        500.00
  ────────────────────────────────────────────────────────────
  ∑Dr = ∑Cr = 5,200.00  ✓
```

The posted JV appears in the General Ledger and factors into the period's P&L and Balance Sheet.

### 26.6 Void a Payroll Run

From the run detail page, click **Void**. This:
- Creates a reversing JV (same lines, debits and credits swapped).
- Sets the run status to `Void`.
- Restores the Salaries Payable balance as if the run had never been posted.

Use void rather than delete to preserve the audit trail.

### 26.7 Paying Employees

Posting the payroll run creates the liability (`Cr Salaries Payable`). To clear it:
1. Go to **New Entry** (`/journal/new`) → **Payment** mode.
2. Select the **Bank** instrument account.
3. Credit side: pick account **Salaries Payable** (2xxx).
4. Enter the net pay amount and payee name.
5. Post — this creates a `BP-` Bank Payment voucher.

### 26.8 Printing Payslips

From the run detail page, each employee row has a **Payslip** link. Clicking it opens `/payroll/[id]/payslip/[eid]` — a portrait-format printable payslip showing:
- Employee details (name, code, department, designation)
- Pay period and pay date
- Earnings table (component name, amount)
- Deductions table (component name, amount)
- Net pay box (gross − deductions)

Use **Ctrl+P** / **Cmd+P** or the **Print** button to print or save as PDF.

---

## 27. ATTENDANCE REGISTER

Track daily employee attendance, working hours, and generate monthly summaries.

### 27.1 Monthly Grid View

Go to **Attendance** (`/attendance`):

- The grid shows **employees as rows** and **days 1–31 as columns** for the selected month.
- Navigate months with the **← →** arrows at the top.
- Each cell shows a colour-coded status badge:

| Colour | Status | Code |
|--------|--------|------|
| Green | Present | P |
| Red | Absent | A |
| Amber | Half Day | H |
| Blue | Leave | L |
| Purple | Holiday | Ho |
| Grey | Off | O |

- **Summary KPI cards** at the top show: total present days, absent days, leave days, and average hours worked for the selected month.
- Click any cell to open a popover showing time-in, time-out, hours worked, and an **Edit** link.

### 27.2 Adding a Single Record

Click **Add Record** (or click a cell → **Edit**) to open `/attendance/record`:

- Fields: **Employee**, **Date**, **Status**.
- For `present` and `half_day` statuses, **Time In** and **Time Out** fields appear.
- **Hours Worked** is shown as a live preview (auto-computed from time_in and time_out).
- Pre-fill via query params: `/attendance/record?employee_id=5&date=2026-06-15`.
- Click **Save** — a duplicate guard prevents two records for the same employee on the same date.

### 27.3 Bulk Entry

Go to **Attendance → Bulk Entry** (`/attendance/bulk`):

1. Select the month.
2. A grid of `<select>` dropdowns appears: one per employee per day.
3. Set the status for each cell.
4. Click **Save All** — the system performs a bulk upsert (creates new records or updates existing ones).

Useful for entering a full month's attendance from a paper register or HR report in one step.

### 27.4 Attendance Report

Go to **Attendance → Report** (`/attendance/report`):

- Filter by **Employee** and/or **Date Range**.
- The report shows all records for the period with per-employee subtotals (present count, absent count, leave count, total hours).
- Click **Export CSV** to download the filtered data.
- The report is landscape-printable: click **Print** for a formatted paper copy.

### 27.5 Biometric Import

Go to **Attendance → Import** (`/attendance/import`):

**CSV upload (manual fallback):**
1. Click **Download Template** to get a sample CSV with the correct column layout.
2. Fill in: `employee_code`, `date`, `time_in`, `time_out`, `status`.
3. Upload the CSV — the page parses it client-side and shows a preview table.
4. Click **Import** — records are matched by `employee_code`, hours are auto-computed, and source is set to `manual`.

**Biometric device endpoint (`POST /api/attendance/import/biometric`):**
- Accepts a JSON payload from a hardware time-attendance device.
- Matches records to employees by `employee_code`.
- Sets `source = biometric` and stores the raw device payload in `raw_data` (JSON field).
- Delete is blocked for biometric records to preserve device audit integrity.

**Future device integration:** ZKTeco / FingerTec devices can push records via TCP/IP or WebSocket. The `raw_data` field is pre-designed to store the device's native payload so no data is lost during the transition from polling to push.

---

## 28. PRA e-Invoice (Pakistan)

Businesses registered with the **Punjab Revenue Authority (PRA)** are required to submit every sales invoice to the PRA eIMS system in real-time. Easy-Books integrates with the PRA API so this happens automatically in the background — you keep working without waiting for a PRA response.

### 28.1 What is a Fiscal Invoice Number (FIN)?

When PRA accepts your invoice it returns a **Fiscal Invoice Number (FIN)** — e.g. `100001FFPK5137899`. This number must be printed on every issued invoice as proof of compliance. Easy-Books stores it and prints it automatically.

### 28.2 Enable PRA e-Invoice

Go to **Settings → PRA e-Invoice (Pakistan)**:

| Field | What to enter |
|-------|--------------|
| **Enable PRA e-Invoice** | Toggle ON to activate real-time submission |
| **PNTN / NTN** | Your 7-digit business NTN (e.g. `1234567-8`) |
| **POS ID** | 6-digit POS ID from the PRA portal (e.g. `100001`) |
| **API Token** | Bearer token from the PRA eIMS portal (paste and hide with the eye icon) |
| **Sandbox mode** | ON = use the PRA test environment; OFF = live production submission |

Click **Test Connection** to verify your credentials before going live. A green "Connected" response (code 102 is normal — it means credentials are valid but no items were sent in the test ping) confirms the token and POS ID are correct.

### 28.3 Add Customer NTN / CNIC

Open any customer and click **Edit**. Scroll to the **PRA e-Invoice** section at the bottom of the form:

- **NTN** — Business buyer NTN (7 digits, e.g. `1234567-8`). Required for B2B invoices to unlock GST input credit for your customer.
- **CNIC** — Consumer 13-digit ID card number. Required for B2C invoices above the PRA threshold.

Leave both blank for customers who are not registered (Easy-Books will still submit; PRA marks it as unregistered buyer).

### 28.4 Add PCT Code to Products

Open any product and click **Edit**. The **PCT Code** field (8-digit PRA product classification code) appears next to the HS Code field. PRA uses this to categorise each line item in the submitted invoice.

Common PCT codes:
| Product | PCT Code |
|---------|----------|
| Basmati Rice | `10063000` |
| Sugar | `17011200` |
| Cooking Oil | `15071000` |
| Tea | `09021000` |

If a product has no PCT code, Easy-Books sends `00000000` (unclassified) which PRA accepts.

### 28.5 Create an Invoice — Payment Mode

On the **New Invoice** form, the **Payment Mode** field (labelled *PRA e-Invoice*) tells PRA how the buyer paid:

| Code | Mode |
|------|------|
| 1 | Cash |
| 2 | Card / Bank Transfer |
| 3 | Gift Voucher |
| 4 | Loyalty Card |
| 5 | Mixed |
| 6 | Cheque |

Default is Cash. Change it before saving if the customer pays by card or cheque.

### 28.6 Submission Flow

When you **Save & Post** an invoice:

1. Easy-Books posts the GL entry and saves the invoice immediately (the UI confirms in under a second).
2. In the background, the PRA payload is built from the invoice lines, customer NTN/CNIC, product PCT codes, POS ID, and payment mode.
3. The payload is submitted to the PRA API with your Bearer token.
4. On success (PRA code `100`), the FIN is stored and the invoice status changes to **PRA Submitted** (green badge).
5. On failure, the status changes to **PRA Failed** (red badge) — click **Retry** on the invoice detail page to re-submit.

The submission always uses your invoice number as the USIN (Unique Serial Invoice Number), which makes retries safe — PRA is idempotent on USIN.

### 28.7 Reading the PRA Status Badge

On the invoice detail page, a badge appears below the main status:

| Badge | Meaning |
|-------|---------|
| (hidden) | PRA is not enabled for this tenant |
| 🟡 **PRA Pending** | Submission queued / in progress |
| 🟢 **PRA Submitted** | FIN received; invoice is compliant |
| 🔴 **PRA Failed** | Submission failed; Retry button visible |

When submitted, the FIN is shown below the badge: **FIN: 100001FFPK5137899**.

### 28.8 Printed Invoice

Every printed invoice automatically includes the FIN below the invoice number when one has been assigned:

```
Invoice No:   INV-0042
PRA Fiscal Invoice No: 100001FFPK5137899
```

No extra setup is needed — the print template reads the stored FIN.

### 28.9 Submission Log

Go to **Settings → PRA e-Invoice** or use the API at `/api/pra/logs` to view every submission attempt: timestamp, endpoint (sandbox vs production), HTTP status, PRA response code, and the full request/response JSON for auditing.

### 28.10 Sandbox vs Production

- **Sandbox** (`pra_sandbox_mode = true`): Points to `ims.pral.com.pk/ims/sandbox/…`. Use this during setup and testing. The sandbox token is `24d8fab3-f2e9-398f-ae17-b387125ec4a2` (shared/public).
- **Production** (`pra_sandbox_mode = false`): Points to `ims.pral.com.pk/ims/production/…`. Requires your real per-tenant Bearer token from the PRA portal.

Switch Sandbox OFF only after a successful Test Connection with your real production token.

### 28.11 Demo Tenant

Log in as `demo.pra@easy-books.app` / `demo1234` to explore a pre-configured Pakistani retail business (*Lahore Retail Traders*) with:
- PKR currency, POS ID 100001, NTN 1234567-8
- 25 customers — half with NTN/CNIC (B2B), half without (B2C)
- 8 retail products with PCT codes (rice, sugar, oil, flour, tea, milk powder, soap, detergent)
- 90 invoices already submitted with sample FINs and varied payment modes

### 28.12 Portal Mode (admin / owner only)

PRA-enabled tenants have a dedicated **Portal Mode** that presents a clean, PRA-focused interface without the full accounting sidebar.

**Toggling portal mode:**
- Admin and owner users see a toggle button at the bottom of the sidebar labelled **Portal View** (or **Full View** when already in portal mode).
- Clicking it switches the view immediately. Preferences live in `localStorage`:
  - `eb.pra_portal_mode` = `1` \| `0`
  - `eb.home_dashboard` = `pra` \| `financial` \| `operations` \| `accounting` (legacy synonym for financial)
- Leaving portal mode restores the dual Financial / Operations accounting home (`/dashboard`).
- Non-admin / non-owner users always land in Portal mode and cannot switch to Full Accounting view.
- Switching on one device does not affect other sessions — the toggle is local.
- You can also pick **PRA Sales** under **Settings → Advanced → Home dashboard**.

**Portal sidebar (7 items):**

| Item | Destination |
|------|-------------|
| New Invoice | `/invoices/new` |
| Invoice Queue | `/invoices` (PRA queue filter) |
| Credit Notes | `/credit-notes` |
| Customers | `/customers` |
| Products | `/products` |
| Submission Logs | `/pra/logs` |
| Settings | `/settings` |

**Portal home page (`/pra-dashboard`):**

The portal home replaces the standard dashboard for portal-mode users. It shows:
- **Today's Sales** — total invoice value created today
- **PRA Submitted** — count of invoices with `pra_status = "submitted"` today
- **Failed / Pending** — count needing attention (click to filter the queue)
- **Cash / Card split** — breakdown by payment mode
- A **today's invoice table** with invoice number, customer, amount, payment mode, and PRA status badge

Drill into any invoice from the table to retry a failed submission or view the FIN.

---

## 28a. Saudi ZATCA e-Invoice

> Requires: **Saudi ZATCA e-Invoice** module from **System → Add-ons** (category Localization).

### Setup

1. Install **Saudi ZATCA e-Invoice** from Add-ons (optionally seed sample settings).
2. Open **Settings → Saudi ZATCA e-Invoice** and confirm:
   - **Enable** is ON
   - **VAT Registration Number** is set
   - **Sandbox** is ON for testing (default)
   - Optional: CR number, Device/EGS ID, CSID token (write-only)
3. Click **Test Connection** to verify the sandbox endpoint is reachable (`ZATCA_SANDBOX_URL` env overrides the default Fatoora developer URL).

### Submit an invoice

Open any sales invoice → **Submit to ZATCA**. The badge shows `cleared` (B2B with buyer VAT) or `reported` (simplified / B2C). UUID, hash, and Phase-1 TLV QR are stored on the invoice. Every attempt is logged under **System → ZATCA Logs** (`/zatca/logs`).

---

## 28b. Peppol / EU VAT e-Invoice

> Requires: **Peppol / EU VAT e-Invoice** module from **System → Add-ons** (category Localization).

### Access Point (AP) credentials setup

1. Choose a Peppol **Access Point** provider (or your tax authority’s certified AP) and create a sandbox account.
2. From the AP portal, copy:
   - **Participant ID** — scheme + identifier, e.g. `0088:<GLN>` (GLN) or `9930:<VAT>` (German VAT scheme). This identifies your company on the Peppol network.
   - **Send / submit URL** — HTTPS endpoint that accepts UBL Invoice XML (often documented as “AS4 send”, “REST send”, or “sandbox invoice”).
   - **API key / Bearer token** — write-only in Easy-Books (`peppol_api_key`); never returned by `GET /api/settings`.
3. Install **Peppol / EU VAT e-Invoice** from Add-ons (optionally seed sample settings).
4. Open **Settings → Peppol / EU VAT e-Invoice** and set:
   - **Enable** ON
   - **Participant ID**
   - **Access Point URL** (sandbox URL for testing)
   - **AP API key** (paste once; leave blank to keep an existing secret)
   - **Sandbox** ON while testing (default)
5. Click **Test Connection**. Any HTTP response from the AP proves reachability (401 still counts as “reachable”). Override the default sandbox URL with env `PEPPOL_AP_URL` only when the settings AP URL is empty and sandbox mode is on.

Company **tax ID**, **country**, and **currency** (Settings → Company) feed the UBL supplier party and document currency (typically `EUR`).

### Export / submit an invoice

- **Export UBL XML** — downloads a Peppol BIS Billing 3.0 (UBL 2.1) Invoice with `CustomizationID` for EN 16931 / Peppol Billing 3.0. Use this to validate against your AP’s schematron or an offline validator before go-live.
- **Submit to Peppol** — POSTs the same XML to the configured AP URL with `Authorization: Bearer <api_key>` and `X-Peppol-Participant-ID`. Status becomes `accepted` on HTTP 2xx (document id stored), or `rejected` / `error` otherwise. Every attempt is logged under **System → Peppol Logs** (`/peppol/logs`).

VAT category mapping: standard rate → `S`, zero rate → `Z`, cross-border B2B with buyer VAT ID and 0% → reverse charge `AE`.

---

## 28c. India GST

> Requires: **India GST** module from **System → Add-ons** (category Localization).

### Setup

1. Install **India GST** from Add-ons (optionally seed sample settings — creates CGST/SGST/IGST tax codes + CoA leaves).
2. Open **Settings → India GST** and set:
   - **Enable** ON
   - **GSTIN** (15-character)
   - **State code** (place of supply default for the seller)
3. On customers/vendors, fill **GSTIN** and **State code** when known.

### Invoicing

- Place of supply is derived from buyer vs seller state: **intra-state** → CGST + SGST; **inter-state** → IGST.
- Use **Reports → GSTR-1 / GSTR-3B** (under tax / India GST nav) for period summaries suitable for portal filing drafts.

### Demo

The **Demo Trading Co.** tenant (`demo.trader@easy-books.app`) ships with `in_gst` enabled and sample GSTIN settings so the tax codes and GSTR screens are immediately browsable.

---

## 28d. Withholding Tax & CIT Worksheet

### Withholding tax on vendor payments (#267)

1. Create (or use seeded) a tax code with **Withholding** flagged — posts to **2265 Withholding Tax Payable**.
2. On the vendor master, set **WHT tax code** and optional **WHT rate %**.
3. When recording a **Bill Payment**, enter **WHT amount**. The payment posts:
   - **Dr AP** (gross applied)
   - **Cr Cash/Bank** (net paid)
   - **Cr 2265** (withholding withheld)

### Corporate income tax worksheet

- Open **Reports → CIT Worksheet** (or Tax → CIT).
- Accounting profit comes from the GL; add **addback** / **deduction** rows (`CitAdjustment`) for permanent differences.
- Demo tenants include sample CIT adjustments for the current fiscal year.

---

## 29. MODULES & THE ADD-ONS PAGE

Easy-Books uses an installable module system — similar to Odoo — so every tenant only sees the features they actually need.

### 29.1 What is a module?

A module is a bundle of related features and sidebar sections. The installable set is:

| Module | What it enables | Always active? |
|--------|----------------|---------------|
| **Base Accounting** | GL, Chart of Accounts, invoicing, AR/AP, banking, all reports | Yes (cannot be removed) |
| **Inventory** | Products, stock, warehouses, product categories, inventory reports | No |
| **Manufacturing** | BOM, production orders, manufacturing workflows | No — requires Inventory |
| **Purchases & Store** | Demand → comparative → PO → gate inward/outward, store issues | No — requires Inventory |
| **Weaving** | Loom/yarn unit-control memos (ops only) | No |
| **Yarn Spinning** | Spinning mill production with full GL costing | No — requires Inventory + Purchases & Store |
| **HRM & Payroll** | Employees, salary structures, payroll runs, attendance register | No |
| **Telecom Franchise** | Full telecom module: trackers, RSOs, MSR, MFS, FCA workflow | No — requires Inventory |
| **Healthcare** | OPD/IPD/Lab/Procedures/Pharmacy | No |
| **AI Assistant** | Agentic financial chat (multi-provider) | No |
| **PRA e-Invoice** | PRA e-invoice submission, fiscal invoice numbers, submission logs | No |
| **Saudi ZATCA e-Invoice** | KSA Phase 2 sandbox clear/report, TLV QR, submission logs | No |
| **India GST** | Place of supply, CGST/SGST/IGST, GSTR-1/3B | No |
| **Peppol / EU VAT e-Invoice** | BIS Billing 3.0 UBL export, Access Point submit, submission logs | No |
| **UAE VAT e-Invoice** | UAE 5% VAT codes, CoA leaves, FTA sandbox stub | No |

### 29.2 The Add-ons page

Go to **System → Add-ons** (`/apps`, admin and owner only) to browse modules. Tabs:

| Tab | What it shows |
|-----|----------------|
| **Default** | Always-on Base Accounting |
| **Recommended** | Industry packs for a quick start |
| **Optional** | First-party modules one at a time |
| **Marketplace** | Curated partner listings (declarative manifests; no partner code) |

Each first-party card shows name, description, category (Core / Operations / HR / Industry / Intelligence / **Localization**), dependencies, install state, and **Install** / **Uninstall**.

**Installing** a module also installs its dependencies automatically. For example, installing Manufacturing also installs Inventory if it is not already active.

**Uninstalling** is blocked if another installed module depends on the one you want to remove (you must remove the dependent first). The Base module cannot be uninstalled.

If your company is a mill (manufacturing or yarn spinning) **and Yarn Spinning is not installed**, Add-ons opens **Recommended** so the Yarn Spinning pack is visible. After Spinning is installed, mill Add-ons opens **Marketplace** when a **For you** listing such as Weighbridge is available. You can also go to `/apps?tab=recommended` or `/apps?tab=marketplace`, or press **Ctrl+K** and type `spinning` / `weighbridge`. See [§30A Yarn Spinning](#30a-yarn-spinning-module) and [§41 Weighbridge](#41-weighbridge-mill-marketplace-listing).

### 29.3 First-time onboarding

Public signup starts with **Base Accounting** only. Industry and localization packs are installed later from **System → Add-ons** (or via the welcome Add-ons page). Demo tenants already have their model-default modules (and localization demos where seeded).

### 29.4 After changing modules

Sidebar sections appear and disappear immediately when modules are installed or uninstalled — no page reload is required. Reports and data that were created while a module was active remain in the database even after the module is uninstalled; reinstalling the module makes them visible again.

### 29.5 Marketplace

Marketplace is a **catalog of products**, not tenants. Cards are filtered **on the server** (`GET /api/marketplace/catalog`):

| Audience | Who sees the card |
|----------|-------------------|
| **public** | Every signed-in tenant |
| **entitled** | Tenants that have that module entitled or installed |
| **private** | Mill models (manufacturing / yarn spinning), ops grants, or an env overlay |

Private mill cards show a **For you** badge and topical tags (for example `spinning`, `private`). Hospital and simple companies never receive mill-only listing ids.

**Install never runs partner code.** A listing may apply a **Studio bundle** (custom fields + form ticks). Uninstall archives those fields; values already saved on documents stay readable.

Full sandbox rules: [docs/MARKETPLACE.md](docs/MARKETPLACE.md).

### 29.6 Settings Studio

**Settings → Studio** (`/settings/studio`, admin/owner) has three tabs:

| Tab | Purpose |
|-----|---------|
| **Fields** | Define extra `x.*` columns on invoice, bill, customer, product, or vendor (cap 12 per entity) |
| **Form layout** | Hide / require / show core and custom fields on the shipped forms |
| **Print** | Clone or pick a print template |

**How to open Studio**

1. Log in as admin or owner (demo: `demo.spinning@easy-books.app` / `demo1234`).
2. **System ▾ → Studio** (immediately under Settings), or the **Studio** tab on the Settings page, or **Settings → Advanced → Open Studio**.
3. Ctrl+K → `studio`, or go to `/settings/studio`.

Clerk / viewer roles do not see the nav item. Custom field values live on the document JSON. They **never post to the General Ledger** — Dr/Cr still balance the same way. Marketplace listings such as Weighbridge can fill Studio for you; you can still edit the resulting fields here.

---

## 30. HEALTHCARE MODULE

> Requires: **Base**, **HRM**, **Inventory** modules installed.  
> Demo tenant: `demo.hospital@easy-books.app` / `demo1234`

The Healthcare module transforms Easy-Books into a full hospital/clinic management system while keeping every financial event wired to the same double-entry GL used by all other modules.

### 30.1 Patient Registry (`/healthcare/patients`)

Every patient gets:
- A unique **MR number** (MR-YYYYNNNN, auto-generated)
- A linked **Customer record** — so AR aging, customer statements, and payment allocation all work without modification
- Demographics: gender, date of birth, blood group, CNIC, emergency contact, allergies

**New Patient** opens a modal; fill name + phone minimum. The Customer record is created silently in the background.

### 30.2 OPD — Outpatient Department (`/healthcare/opd`)

1. **Select a doctor** using the button row at the top. Each doctor button shows their specialization.
2. **Token Queue tab**: issue a token (registered patient or walk-in name). Token numbers reset daily per doctor. Call the next token with the **Call** button.
3. **Record Visit tab**: select patient, doctor, date, visit type (first/follow-up), enter chief complaint, diagnosis, and advice. Submit → the system auto-creates the OPD visit and posts the consultation fee:
   - `Dr 1100 Accounts Receivable / Cr 4100 OPD Consultation Revenue`
4. After the visit is saved a prescription can be written inline (medicine name, dosage, frequency, duration).
5. **Today's Visits** panel (right side) shows all visits recorded for the selected doctor on the selected date.

### 30.3 IPD — Inpatient Department (`/healthcare/ipd`)

**Ward cards** at the top show each ward (type, available/occupied bed counts). Click a ward to load its bed grid.

**Bed grid**: green = available (click to admit), red = occupied (click does nothing), grey = maintenance.

**Admit Patient** modal (opens on clicking an available bed):
- Select patient, doctor, admission type (planned/emergency/referred), admission date, and deposit amount
- The system posts the deposit: `Dr 1000 Cash / Cr 2310 Patient Advances`
- The bed status flips to Occupied

**Active admissions table** lists all currently admitted patients with a **View Details** link.

#### Admission Detail page (`/healthcare/ipd/[id]`)

Three tabs:
- **Daily Charges** — accumulate ward/nursing/procedure/lab/pharmacy charges with **Add Charge** button; no individual GL post (IPD cost-accumulation pattern)
- **Lab Orders** — lab orders linked to this admission
- **Procedures** — procedure orders linked to this admission

**Discharge** button (top-right, active admissions only):
1. Rolls up all `hc_admission_charge` rows into a single consolidated invoice
2. Settles the deposit: `Dr 2310 Patient Advances / Cr 1100 AR`
3. Posts remaining balance to AR: `Dr 1100 AR / Cr 4121 Ward Charges + 4100–4120 per charge type`
4. Frees the bed (status → available)

### 30.4 Laboratory (`/healthcare/lab`)

**Status filters**: All / ordered / sample_collected / processing / resulted / delivered

**New Order** modal:
- Select patient, date, source (walk-in/OPD/IPD/Collection Centre)
- Tick the tests from the catalogue (grouped by category with fees shown)
- Walk-in orders are auto-billed on creation: `Dr 1100 AR / Cr 4110 Lab Revenue`

**Collect** button (on *ordered* rows): records sample collection (point, specimen type, barcode)  
**Deliver** button (on *resulted* rows): marks results delivered to patient

#### Lab Test Catalogue (`/healthcare/lab/tests`)

Grouped by category (Hematology / Biochemistry / Microbiology / Radiology / Other). Inline row editing for name, normal range, unit, and fee. Toggle active/inactive with the checkbox. **Add Test** button opens a modal.

### 30.5 Procedures (`/healthcare/procedures`)

Two sections:
- **Procedure Catalogue**: code, name, category, fee; **Add Procedure** and **Order** buttons per row
- **Recent Procedure Orders**: date, fee, status; **Mark Performed** action on ordered rows

Walk-in/OPD procedures are billed immediately: `Dr 1100 AR / Cr 4120 Procedure Revenue`  
IPD procedure orders are added to `hc_admission_charge` instead (no individual invoice).

### 30.6 Hospital Store (`/healthcare/store`)

Two tabs:
- **Stock Issues**: create internal stock transfers from a store location (Main Store → Lab/Pharmacy/Ward); items can be flagged *Charge to Patient* with a markup amount which adds to the admission charges
- **Pending Dispense**: prescription items awaiting pharmacy dispensing; one-click dispense records the dispensing and decrements the pharmacy stock location

The store integrates with the existing **Inventory** module — the same `Product`, `StockLocation`, and `StockMovement` tables are used. Any product in inventory can be issued from any location.

### 30.7 HC Reports (`/healthcare/reports`)

Date-range picker at top. Five tabs:

| Tab | Content |
|-----|---------|
| Revenue by Type | GL credits to accounts 4100–4121 broken down by account |
| OPD Summary | Tokens issued, visits recorded, revenue by date range |
| Doctor Collections | Visits, billed amount, estimated revenue per doctor |
| Lab Summary | Orders by status and by source; total lab revenue |
| IPD Census | Ward-level admissions, discharges, avg length of stay, bed utilisation |

### 30.8 GL Accounts (Healthcare)

| Code | Name | Type |
|------|------|------|
| 2310 | Patient Advance / Deposit | Liability |
| 4100 | OPD Consultation Revenue | Revenue |
| 4110 | Laboratory Revenue | Revenue |
| 4120 | Surgical / Procedure Revenue | Revenue |
| 4121 | Ward / Bed Charges Revenue | Revenue |

### 30.9 Demo Hospital Tenant

Login: `demo.hospital@easy-books.app` / `demo1234`

Pre-seeded data:
- **5 doctors** (Cardiology, Gynecology, General Surgery, Pediatrics, ENT)
- **4 wards** (Male General × 12 beds, Female General × 12 beds, Private Suite × 8 beds, ICU × 6 beds)
- **50 patients** (Pakistani names with MR numbers)
- **~200 OPD tokens** and **~160 OPD visits** over the past 90 days with diagnoses and prescriptions
- **20 IPD admissions** (15 discharged with charges, 5 currently admitted)
- **80 lab orders** with results entered for most; sample collection records for non-walk-in orders
- **25 procedure orders** (most marked performed)

---

## 30A. YARN SPINNING MODULE

> Requires: **Base**, **Inventory**, **Purchases & Store**, **Yarn Spinning** modules installed.  
> Demo tenant: `demo.spinning@easy-books.app` / `demo1234`

The Yarn Spinning module tracks cotton/fiber intake through multi-stage mill production to finished yarn dispatch — with **full double-entry GL** on every approve/post (unlike the Weaving module, which is memo-only).

**How to open it**

1. Log in as `demo.spinning@easy-books.app` / `demo1234` (not the hospital / simple / manufacturing demos).
2. Use the **Spinning** top-nav tab (next to Store). On a narrow window it may sit under **More**.
3. Or press **Ctrl+K** and type `spinning`.
4. To install on another company: **System → Add-ons → Recommended** → **Yarn Spinning** pack (Optional tab also lists the `spinning` module). Marketplace **Weighbridge** is a different product (invoice Gate pass fields only).

### 30A.1 Setup (`/spinning/setup`)

Configure master data before recording production:

| Master | Purpose |
|--------|---------|
| **Yarn Specs** | Count (Ne/Nm), twist direction, cotton/poly blend %; links to a finished-yarn `Product` |
| **Fiber Grades** | Staple length, micronaire, grade code for incoming cotton |
| **Machines** | Carding/drawing/spinning machines with spindle count |
| **Shifts & Operators** | Production shift roster |
| **Waste Types** | Hard waste, soft waste/noil, pneumafil, moisture loss — each mapped to GL `5901`–`5904` |
| **Recipes** | Blend ratios per yarn spec (fiber grade × percentage) |

### 30A.2 Production Plans (`/spinning/plans`)

Create monthly targets (PP-YYYY-seq) by yarn spec and target kg. Approve a plan to lock it. Plans give the dashboard something to compare actual output against.

### 30A.3 Spin Lots (`/spinning/lots`)

A spin lot (SL-YYYY-seq) is the cost container for one production run:

1. **Draft** — create with yarn spec, target kg, optional recipe
2. **Start** — opens the lot for bale receipts and stage entries
3. **Complete** — freezes further production input
4. **Close** — finalises cost-per-kg

The lot detail page shows accumulated material, labour, overhead, and waste costs with a live cost-per-kg figure.

### 30A.4 Bale Receipt (`/spinning/bale-receipts`)

Record incoming cotton bales (BR-YYYY-seq):

- Enter gross weight, tare, and derived net kg (Lbs/Bags shown automatically)
- Link to a spin lot, vendor, and optionally a Purchase Order, Gate Inward, or Bill
- **Approve** posts GL: `Dr 1200 Raw Cotton / Cr AP` (if bill-linked) or `Cr Cash`, plus stock into the **RAW** location

### 30A.5 Stage Entries (`/spinning/stages`)

Record each processing stage against a lot:

| Stage | WIP Account | Typical flow |
|-------|-------------|--------------|
| Opening / Carding | 1201 | `Dr 1201 / Cr 1200` (RM → WIP) |
| Drawing / Roving | 1202 | `Dr 1202 / Cr 1201` (WIP transfer) |
| Spinning / Winding | 1203 | `Dr 1203 / Cr 1202` (WIP transfer) |

Enter input kg, output kg, labour cost, and overhead cost per entry. **Post** creates the balanced JV.

### 30A.6 Cone Output (`/spinning/cone-output`)

Record finished yarn cones (CO-YYYY-seq) against a lot. **Approve** transfers cost from WIP to Finished Yarn (`Dr 1204 / Cr 1203`) and adds stock to the **FG-YARN** location.

### 30A.7 Waste Log (`/spinning/waste`)

Log hard waste, noil, pneumafil, or moisture loss. **Post** debits the mapped waste expense account (`5901`–`5904`) and credits WIP.

### 30A.8 Yarn Dispatch (`/spinning/dispatch`)

Ship finished yarn to customers (YD-YYYY-seq). **Approve** posts COGS (`Dr 5010 / Cr 1204`) and relieves FG stock.

### 30A.9 Reports & Calculators

| Screen | What it shows |
|--------|---------------|
| **Dashboard** (`/spinning/dashboard`) | KPIs: lots open, kg in WIP, cones today, waste % |
| **Daily Register** | Stage entries and output by date |
| **Lot Control** | Per-lot input/output balance and variance |
| **Waste Summary** | Waste by type and stage |
| **Yield Calculator** | Expected vs actual yield from input kg |
| **Blend Calculator** | Recipe mix validation |
| **Spindle Calculator** | Production rate from spindle count |

### 30A.10 Demo Spinning Tenant

Login: `demo.spinning@easy-books.app` / `demo1234`

Pre-seeded with yarn specs, fiber grades, machines, shifts, operators, waste types, recipes, open and completed spin lots, approved bale receipts, posted stage entries, cone output, waste logs, and yarn dispatches — every Spinning screen and report is populated on first login.

---

## 31. Universal Search (Ctrl+K)

Press **Ctrl+K** (Windows/Linux) or **⌘K** (Mac) anywhere in the app to open the command palette. You can also click the **Search** icon in the top navigation bar.

### 31.1 What you can search

The palette searches three layers simultaneously:

| Layer | Speed | What it finds |
|-------|-------|---------------|
| Open tabs | Instant | Currently open browser tabs by title or URL |
| Navigation & forms | Instant | All pages, reports, and quick-action forms |
| Live data | ~150 ms | Customers, vendors, invoices, bills, accounts, products, employees, transactions |

**Data search columns:**

| Entity | Fields searched |
|--------|----------------|
| Invoices | Number, customer name, description, notes, status, date |
| Bills | Number, vendor name, description, notes, status, date |
| Customers | Name, email, phone, address, NTN, CNIC |
| Vendors | Name, email, phone, address |
| Accounts | Code, name, type |
| Products | Name, code, unit, type |
| Employees | Name, code, department, designation, CNIC |
| Transactions | JV number, description, party, reference, date, voucher type |

### 31.2 Prefix filter syntax

Type a prefix before your query to restrict results to one category:

| Prefix | Searches |
|--------|----------|
| `inv:` | Invoices only |
| `bill:` | Bills only |
| `cust:` | Customers only |
| `vend:` | Vendors only |
| `acc:` | Chart of Accounts |
| `prod:` | Products |
| `emp:` | Employees |
| `jv:` | Journal transactions |
| `tab:` | Open browser tabs only |
| `rpt:` | Report pages only |
| `new:` | Quick-action "New…" forms only |

**Example:** Type `inv: ahmed` to find all invoices with "ahmed" in the customer name or description.

### 31.3 Nav index keywords

The navigation index understands keyword aliases — you don't need exact page names:

| Type | What to type | Opens |
|------|-------------|-------|
| Report alias | `tb` or `trial` | Trial Balance |
| Report alias | `p&l` or `profit` | Income Statement |
| Report alias | `bs` or `balance` | Balance Sheet |
| Report alias | `gst` or `tax` | Tax Reports |
| Report alias | `cash flow` | Cash Flow Statement |
| Quick action | `new invoice` | New Invoice form |
| Quick action | `grn` | New Goods Receipt form |
| Quick action | `payroll` | New Payroll Run form |

### 31.4 Keyboard navigation

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move focus up / down through results |
| `↵` Enter | Open the focused result |
| `Esc` | Close the palette |

### 31.5 Recent searches

The palette remembers your last 5 searches and shows them as clickable chips when the input is empty. Click any chip to re-run that search instantly.

---

## 32. In-app Update Notifications

Easy-Books admin and owner users see automatic update notifications — no need to manually check for new versions.

### 32.1 Automatic check on login

Every time an admin or owner signs in, Easy-Books silently checks GitHub for newer commits. If one is found, an **Update Available** popup appears at the bottom of the screen.

### 32.2 Update actions

| Action | Effect |
|--------|--------|
| **Update Now** | Starts the update immediately (see §32.3) |
| **Later** | Dismisses the popup for this login session only |
| **Skip version** | Permanently dismisses for this specific commit (until a newer one is pushed) |

### 32.3 Update progress screen

When you click **Update Now**, a full-screen animated progress overlay appears showing four phases:

1. **Pull** — downloading the latest code from GitHub
2. **Compile** — running database migrations
3. **Bundle** — rebuilding the frontend
4. **Start** — restarting the server

The progress bar advances over ~2 minutes. Once the server restarts, the app automatically reloads.

### 32.4 Post-update greeting

After the app reloads following a successful update, a toast notification appears showing the old and new commit hashes and a "What's New" summary of the changes included in the update.

### 32.5 Manual check

Go to **Settings → Updates** to see the current version, the latest available version, and trigger a manual update check or start an update at any time.

---

## 33. Sidebar Navigation (Auto-hide)

The section sub-menu on the left side of the screen collapses automatically to save screen space.

### 33.1 Collapsed mode (default)

By default the sidebar shows **icons only** (52 px wide). Hover over any icon to see its label as a tooltip. The sidebar expands smoothly when you hover over it.

### 33.2 Expanded mode (hover)

Hovering over the icon strip expands the sidebar to show full labels (200 px). Moving the mouse away collapses it again automatically.

### 33.3 Pinned mode

Click the **›** (right chevron) button at the bottom of the sidebar to **pin it open**. The button changes to **‹** (left chevron). The pinned state is remembered between sessions (stored in your browser). Click **‹** to unpin and return to auto-hide behaviour.

### 33.4 No sidebar sections

Pages that have no sub-items (Dashboard, Report Builder, etc.) show no sidebar at all — giving maximum working space.

---

## 34. PURCHASES & STORE — PROCURE-TO-PAY & DISPATCH CONTROL

**Compliance:** IAS 2 (inventory), ISA 240 (segregation of duties — internal controls against fraud).

This module strengthens procurement and dispatch with a full internal-controls chain: nobody can single-handedly demand, buy, receive, and consume stock, or dispatch goods without a record. It installs as **Purchases & Store** (Settings → Add-ons, or automatically for Manufacturing companies) and adds two sidebar sections: **Purchases** (Demands, Comparatives, Gate Inward, reports) and **Store** (Gate Outward, reports).

The chain has two directions:

```
INWARD  (goods arriving):  Demand → Vendor Quotations → Comparative Statement
                            → Purchase Order → Gate Inward → Bill
OUTWARD (goods leaving):   Sales Invoice ─┐
                            Purchase Return ┼→ Gate Outward (memo record)
                            Scrap Disposal ─┘  (the one path that posts to the GL)
```

### 34.1 Installing the Module

Go to **System → Add-ons** (`/apps`, admin/owner only) and install **Purchases & Store** (Operations category). It depends on **Inventory**, which installs automatically alongside it if not already present. Manufacturing-model companies have it installed from day one.

Once installed, two new sidebar sections appear: **Purchases** and **Store**. Two Settings toggles also appear (see §34.10) — both default **on**.

### 34.2 Raising a Purchase Demand

A Demand is a **quantity-only** requisition — the person raising it never sets a price. That's the control: pricing is decided later, by someone else, through competitive quotations.

Go to **Purchases → Demands** (`/purchases/demands`) → **+ New Demand**:

| Field | Description |
|-------|-------------|
| **Demand Date** | Defaults to today |
| **Required By** | When the goods are needed |
| **Purpose** | Free text — why this is being requested |
| **Lines** | Product (optional — free text also accepted), Description, Quantity, Unit — **no rate field exists on this form** |

Click **Save Draft**. The demand is numbered `PD-YYYY-0001` and starts in **Draft** status — editable, not yet actionable by the purchasing team.

**Output:** the demand appears in the Demands list with status **Draft**. Nothing else happens yet — no quotations can be raised against a draft demand.

### 34.3 Approving a Demand

Open the demand (`/purchases/demands/[id]`) and click **Approve**.

- **Who can approve:** admin or owner role.
- **The one rule that matters:** you cannot approve your own demand. If you raised it, someone else with admin/owner rights must approve it — the system rejects a self-approval attempt with an error.
- On approval, the demand's status becomes **Approved** and it becomes eligible for vendor quotations.

A demand can also be **Cancelled** (from Draft or Approved) or, later, **Closed** (once fully converted).

### 34.4 Entering Vendor Quotations

Once a demand is **Approved**, the purchasing team collects pricing from vendors — one entry per vendor.

Go to the demand's detail page → **+ New Quotation** (or `/purchases/demands/[id]/quotations/new`):

| Field | Description |
|-------|-------------|
| **Vendor** | Pick from your vendor list |
| **Quote Date** | When the vendor's offer was received |
| **Valid Until** | Optional expiry |
| **Delivery Terms / Payment Terms** | Free text |
| **Lines** | Pre-filled with the demand's lines (quantity is fixed from the demand); enter the **Rate** per line — amount computes automatically |

Repeat for each vendor quoting on this demand — you need **at least two** to avoid the justification requirement later (see §34.5).

**Output:** each quotation is numbered `VQ-YYYY-0001` and listed against the demand. Quotations can be edited or deleted freely **until** the demand's Comparative Statement is approved or converted — after that, quotation writes are frozen (400 error) so nobody can quietly change a price after the decision is made.

### 34.5 Building & Approving the Comparative Statement

The Comparative Statement is the side-by-side decision record — Odoo calls this a "call for tender" comparison.

Go to the demand's detail page (a Comparative Statement is auto-created once the first quotation exists), or **Purchases → Comparatives** (`/purchases/comparatives`):

1. The **matrix** shows every demand line as a row and every vendor's quotation as a column, with the **lowest rate per row highlighted**.
2. Click a vendor's column to **select them as the winner**.
3. If your selection is **not** the lowest total, or there are **fewer than two quotations** on the demand, a **Justification** text box appears and is required — e.g. "Vendor offers 3-day delivery vs. the lower bidder's 10-day lead time."
4. Click **Save Selection**.

Then click **Approve** on the comparative:

- **Who can approve:** admin or owner, and **not** the person who created the comparative (same self-approval block as demands).
- **Completeness check:** approval is rejected if the winning vendor's quotation doesn't price every line on the demand — no partial-price conversions.
- **Lowest-or-justify enforcement:** approval is rejected if a justification was required (per step 3) but left blank.

**Output:** the comparative's status becomes **Approved**, and a **Convert to PO** button appears.

### 34.6 Converting to a Purchase Order

From an approved Comparative Statement, click **Convert to PO**. This:
- Creates a new **Purchase Order** carrying every line from the winning quotation (same products, quantities, and rates).
- Sets the demand's status to **Converted** and the comparative's status to **Converted**.
- The new PO starts in **Draft** — approve it from the Purchase Orders page (`/manufacturing/purchase-orders` under Purchases once the module is installed) the same way you approve any PO.

**Enforcement:** once the module is installed, `require_purchase_chain` (on by default — see §34.10) blocks creating a **bare** PO with no comparative behind it. If you need to raise an occasional PO outside the formal chain (an emergency purchase, for instance), turn that setting off in Settings first.

### 34.7 Recording Gate Inward (Goods Receipt Control)

When the vendor's truck arrives, someone at the gate — security, storekeeper, whoever physically checks the delivery — records what actually came in, separately from what the PO says was ordered.

From an **approved** PO's detail page, click **Record Gate Inward** (or **Purchases → Gate Inward → + New Entry**, `/purchases/gate-inward/new?po=<id>`):

| Field | Description |
|-------|-------------|
| **Purchase Order** | Pick the approved PO this delivery is against |
| **Gate Date / Time In** | When the vehicle arrived |
| **Vehicle No. / Challan No.** | For the gate register and later lookup |
| **Lines** | Pre-filled per PO line with the ordered quantity and however much has already been received; enter the quantity **actually received this time** |

Click **Save**. The entry is numbered `GI-YYYY-0001`.

**What happens to the PO:**
- If this is the **first** delivery and it's **partial**, the PO stays **Approved** — still waiting on more stock.
- Once the **cumulative** received quantity across all Gate Inward entries reaches the full ordered quantity, the PO automatically flips to **Received**.
- A delivery can never be recorded beyond what's left to receive — the form rejects a quantity that would push the total over the ordered amount.

**Correcting a mistake:** a Gate Inward entry can be **cancelled** (with a required reason — e.g. "wrong vehicle number logged") as long as the PO hasn't been billed yet. Cancelling one drops the PO's coverage — if that takes it below 100%, the PO reverts from Received back to Approved, and you simply record a fresh, correct entry. There is no edit button — corrections are always a cancel-and-re-enter, so the original mistake stays in the audit trail rather than being silently overwritten.

### 34.8 Converting the PO to a Bill (the Billing Gate)

Go to the PO's detail page and click **Convert to Bill**, same as any other PO.

**The gate:** if `require_gate_inward` is on (default — see §34.10) and the PO isn't yet fully covered by Gate Inward entries, the button is disabled with a tooltip explaining why, and the API rejects the attempt with a 400 error. You must record the missing Gate Inward entries first.

Once conversion succeeds:
- A **Bill** is created for the ordered amount, posted `Dr Expense / Cr Accounts Payable`.
- Every open Gate Inward entry on that PO flips to **Billed** status — permanently locking them (a billed Gate Inward can never be cancelled).

### 34.9 Gate Register & 3-Way Match Reports

**Gate Register** (`/purchases/gate-register`) — every Gate Inward entry, searchable by vehicle or challan number, filterable by date. Use this as the physical security log: "what came through the gate this week."

**3-Way Match** (`/purchases/three-way-match`) — the audit report. One row per PO line, comparing:

| Column | Meaning |
|--------|---------|
| **PO Qty / Rate / Amount** | What was ordered |
| **GI Qty** | What was actually received (summed across all Gate Inward entries) |
| **Bill Qty / Amount** | What was billed |
| **Qty Var / Amt Var** | The differences — highlighted when non-zero |

A flagged row means something doesn't line up: a short delivery that got billed in full, an over-billed amount, or — the most valuable catch on an older company's books — a PO that was billed with **no Gate Inward record at all**, meaning nobody ever confirmed the goods arrived.

Both reports (and every other register in this section — Gate Outward Register, Dispatch Reconciliation, Store Issue's Issue Register) page results 50 at a time once your company has enough activity, with page-navigation controls at the bottom of the table; the search box filters server-side, so it works across the whole register, not just the currently-visible page.

### 34.10 Settings: Chain & Gate Enforcement Toggles

Go to **Settings** (`/settings`) — two toggles appear once Purchases & Store is installed:

| Setting | Default | Effect when ON |
|---------|---------|-----------------|
| **Require purchase chain** | On | A bare Purchase Order (no Comparative Statement behind it) cannot be created |
| **Require gate inward** | On | A Purchase Order cannot be converted to a Bill until every line has full Gate Inward coverage |

Turn either off for smaller companies that don't need the full control chain, or for one-off exceptions — both can be re-enabled at any time and don't affect documents already in progress.

### 34.11 Gate Outward — Dispatching a Sales Invoice

Every gate exit — sales dispatch, purchase return, or scrap — is recorded in one place: **Store → Gate Outward** (`/store/gate-outward`).

To record a dispatch against an invoice you've already created, click **+ New Gate Outward** (`/store/gate-outward/new`):

1. Choose source type **Invoice**.
2. Pick the invoice from the dropdown (any non-void invoice — even one still in Draft status, since the goods behind it already left inventory the moment the invoice was created).
3. Lines pre-fill from the invoice; enter vehicle/challan details.
4. Click **Save**.

**Output:** the entry is numbered `GO-YYYY-0001` and lands **immediately in Approved status** — there's no separate approval step for this type. This is a **memo record only**: no GL posting, no stock movement (the invoice already did both when it was created). Its purpose is purely the paper trail — proving the goods physically left — and feeding the Dispatch Reconciliation report (§34.14).

You can record multiple Gate Outward entries against the same invoice (a large order shipped in batches) — there's no quantity cap, since this is a reconciliation record, not a control gate.

### 34.12 Gate Outward — Purchase Return Exit

When goods are physically handed back to a vendor (following a Debit Note you've already posted), record the same way:

1. **+ New Gate Outward** → source type **Debit Note**.
2. Pick the debit note (must be posted — a draft debit note has no stock movement behind it yet, so it isn't offered).
3. Lines pre-fill from the debit note; enter vehicle/challan details; **Save**.

Same as the invoice path: immediately **Approved**, memo-only, no GL or stock effect (the debit note already handled both when it posted).

### 34.13 Gate Outward — Scrap Disposal

Scrap is different from the other two: there's no earlier document to point to, so the Gate Outward entry **is** the transaction — and it's the one case that goes through a real approval workflow before anything hits the books.

**Recording scrap:**
1. **+ New Gate Outward** → source type **Scrap**.
2. Pick the product and enter the **quantity** being disposed of.
3. Enter **Unit Cost** (defaults to the product's current average cost) and **Unit Value** (what you expect to recover selling it as scrap — 0 if it's a pure write-off).
4. Click **Save**. The entry is created in **Draft** — nothing has happened to your stock or GL yet.

**Approving scrap:** open the entry and click **Approve**.

- **Who can approve:** admin or owner, and **not** the person who created the entry.
- On approval:
  - Stock is relieved at the entered quantity, at the product's actual cost.
  - If you entered a Unit Value greater than zero, a journal posts `Dr Cash in Hand / Cr Scrap Sales` for the value collected.
  - A second, separate journal always posts `Dr Scrap Disposal Expense / Cr Inventory` for the cost relieved.
  - The entry becomes **Approved** — permanently. There's no cancel button once approved; if you made a mistake, it needs a correcting entry, the same way a posted invoice is corrected with a Credit Note rather than an edit.

**Fixing a mistake before approval:** a **Draft** scrap entry can be freely cancelled (with a reason) — since nothing has touched your books yet, cancelling costs nothing.

### 34.14 Gate Outward Register & Dispatch Reconciliation Reports

**Gate Outward Register** (`/store/gate-outward-register`) — every outward gate entry (invoice, debit note, and scrap), searchable by vehicle/challan, filterable by type and date. The outbound mirror of the Gate Register.

**Dispatch Reconciliation** (`/store/dispatch-reconciliation`) — one row per posted invoice or debit note, showing whether a Gate Outward entry exists for it yet. Rows with **no gate exit** are highlighted — this is how you catch invoices that were created and (on paper) shipped, but never actually logged leaving the building. It's a flag for follow-up, not a block — invoice creation and posting are never held up by this report. Search by invoice/debit-note number or customer/vendor name to jump straight to a specific document.

### 34.15 Permissions for This Module

Four permission resources appear in the admin matrix (**System → Permissions**, `/settings/permissions`) once the module is installed:

| Resource | Covers |
|----------|--------|
| **Purchase Demands** | Raising and approving demands |
| **Comparative Statements** | Quotations and comparative approval/conversion |
| **Gate Inward** | Recording and cancelling goods-receipt entries |
| **Gate Outward** | Recording, approving, and cancelling dispatch entries |

Each can be set to **None / View / Edit** per user, and each supports **My Data Only** — a storekeeper flagged this way sees only the gate entries they personally recorded, on both the list pages and the register reports. Approving a demand, comparative, or scrap Gate Outward always requires admin or owner rights regardless of the granular permission level, and always blocks the creator from approving their own document.

**A gate-only user doesn't need Purchase Order access.** Give someone **Edit** on **Gate Inward** but leave their **Purchase Orders** permission at **None**, and they can still pick a purchase order and record goods receipt against it — the gate screens show a stripped-down view of the PO (description, quantity, unit) with no pricing, so a receiving clerk can do their job without ever seeing what anything costs.

---

## 35. AI FINANCIAL ASSISTANT

Ask plain-language questions about your books — "What's my revenue this month?", "Which invoices are overdue?", "What do I owe vendors?" — and get an answer grounded in your actual data, formatted as a proper report with tables and headings.

The assistant covers every part of the app you have installed: core accounting (receivables, payables, P&L, balance sheet, trial balance, cash flow, tax, budgets), sales and customer analysis, and — when the matching module is installed — inventory and stock, payroll and attendance, hospital operations (OPD/IPD/lab), the telecom franchise chain, purchasing and store registers, and manufacturing. It can also answer one-off questions that no standard report covers ("list my five biggest unpaid invoices from March") by querying the same data sources the Report Builder uses.

### 35.1 Opening the Assistant

Two ways in, both showing the same conversation history:

- **Sparkles button** — bottom-right on every page (once the module is installed). Opens a small chat popup you can drag anywhere and minimize, the same way as the Calculator.
- **Full page** — the **AI Assistant** entry, or go directly to `/agent`, for a two-column view with a session sidebar (new chat, rename, delete).

If you don't see the Sparkles button at all, the module isn't installed yet — go to **System → Add-ons** and install **AI Financial Assistant** (admin/owner only).

### 35.2 Asking a Question

Type your question and press Enter, or tap one of the quick-prompt suggestions on a new chat ("What's my revenue this month?", "Which invoices are overdue?", "Show me my P&L summary", "What's my cash balance?"). While it's working you'll see a short status line change a few times — "Routing your question…", then something like "Receivables Agent is looking into this…" — before the answer streams in.

**Output:** a formatted reply — tables for anything with multiple rows (overdue invoices, top customers), headings and bold labels for structure, using the exact figures from your books.

### 35.3 How a Question Gets Answered

Behind the scenes, every question runs through four quick steps instead of one:

1. **Routing** — figures out which topic your question is about and hands it to the right specialist agent. There's a specialist for each area — receivables, payables, financial reports, sales, and (when installed) inventory, payroll, healthcare, telecom, purchasing, and manufacturing — plus a general assistant for everything else.
2. **Analysis** — that specialist looks up the real numbers from your accounting data — it can only *read*, never create, post, or change anything.
3. **Review** — a separate checking pass ("Reviewing figures…" in the status line) verifies every number in the draft answer against the raw data it was based on, correcting anything that doesn't match before you ever see it.
4. **Drafting** — a final pass turns the verified findings into the clean report you actually see.

This is why a longer answer (like an aging table with several invoices) may take a few seconds and show its progress along the way — it's doing real work in stages, not just typing.

### 35.4 Setting Up a Model & API Key

Click the model row at the top of the chat (it reads the current model name, or **"No AI model configured"** if nothing's set up yet) to open the **Model & API Key** window:

- **Model** — pick from whichever providers/models are already configured. Anyone can do this.
- **API Key** — admins and owners can paste a key for Anthropic (Claude), OpenAI (GPT), or Google (Gemini) right here and click **Save**; existing keys show a masked status (`••••1234`) so you can tell one's already set without ever seeing it again. **Clear** removes a key. A link at the bottom, **More AI settings (Ollama, rate limit) →**, goes to the full Settings page for self-hosted Ollama setup and the hourly rate-limit field.
- If you're not an admin or owner, this section shows a note instead of input fields — ask an admin or owner to add a key.

Saving or clearing a key updates the model list immediately, with nothing to reload.

### 35.5 Chat Sessions

On the full-page view (`/agent`), the left sidebar lists your past conversations. **+ New chat** starts a fresh one; hover a chat to reveal rename (pencil) and delete (trash) buttons. A session automatically takes its title from your first message in it. Chat history is private per user — even another admin on the same company can't see your conversations.

### 35.6 Limits & Safeguards

- Messages are capped at 4,000 characters.
- There's an hourly limit on how many questions you can ask (configurable in Settings → AI, default 20/hour) — you'll see a friendly "try again in a few minutes" message if you hit it.
- The assistant is **strictly read-only** — no matter what you ask, it cannot create an invoice, post a journal entry, or change anything in your books.

---

## 36. CALCULATOR

A globally available calculator widget — no module install needed, available on every page.

### 36.1 Opening It

Click the calculator icon button, stacked just above the AI Assistant's Sparkles button on the right edge of every page. It opens as a small floating window styled like a classic desk calculator, with a green-tinted display.

### 36.2 Using It

- **Mouse** — click any key, same as a physical calculator: digits, `+ − × ÷`, `%`, `±` (sign toggle), `√` (square root), `00`, `.`, `C` (clear), and the backspace key (⌫) to correct the last digit.
- **Keyboard** — type directly: number keys, `+ - * /`, `Enter` or `=` for equals, `Backspace` to correct, `Escape` or `Delete` to clear, `%` for percent. This only responds while the calculator window is open (and not minimized), and it automatically steps aside if you're typing into an invoice field, a search box, or any other field elsewhere on the page — it won't steal your keystrokes.

**Percent works the way you'd expect at a business:** `200 + 10%` gives you `220` (10% of 200, added on), and this is consistent no matter which operator you're using — `×`, `÷`, `+`, or `−`.

### 36.3 Reading the Display

The display has two lines: a small line above showing your running calculation (e.g. `123+456+789+`), and the large main result below. Once you press `=`, the top line finalizes to the full expression (e.g. `200+300=`) and the bottom shows the answer. Starting a new calculation clears the top line automatically.

### 36.4 Moving & Minimizing It

Drag the header bar to move the calculator anywhere on screen — it remembers where you left it (per browser) the next time you open it. Click the minus button to collapse it to just its header without losing whatever you were calculating; click again (or the restore icon) to bring it back.

---

## 37. IFRS 16 LEASES

Lessee accounting for office / equipment leases — Right-of-use (RoU) asset + lease liability with a full amortisation schedule.

### 37.1 Enable & navigate

- Settings → Accounting (or Advanced): leave **IFRS 16 leases** on (`leases_enabled`, default on).
- Open **Leases** (`/leases`) from Accounting / Fixed Assets area.

### 37.2 Create & activate

1. **+ New lease** — name, lessor, commencement date, term (months), payment amount, annual discount rate (%), payment timing (arrears / advance), optional initial direct costs, payment (bank/cash) account.
2. Preview shows the computed PV and schedule before save.
3. Save as draft, then **Activate** — posts `Dr RoU (1510) / Cr Lease liability (2510)` (+ IDC if any). Schedule lines are generated automatically.

Demo tenants (Services / Manufacturing) include an active **Head-office rent** lease after Sample Data seed.

### 37.3 Period post & terminate

- On the lease detail page, **Post period** runs interest expense, payment (credit bank), and RoU depreciation for the next open schedule line via the normal GL writer.
- **Terminate** posts a simplified early-exit settlement (remaining liability vs RoU NBV).
- **Maturity disclosure** buckets remaining undiscounted payments for notes to the accounts.

CoA leaves used: **1510** RoU, **1511** Accum. depr. RoU, **2510** Lease liability, **5125** Lease interest (plus depreciation expense).

---

## 38. GROUP CONSOLIDATION (IFRS 10)

Build a holding-company entity graph and produce a consolidated worksheet package — eliminations never post to member GLs.

### 38.1 Entity graph

1. Sign in on the **holding** tenant (demo: Manufacturing owner also has viewer membership on Trading).
2. Open **Consolidation** (`/consolidation`).
3. Add members: parent (100%), subsidiaries (ownership %), optional associates (equity-method line). Set IC AR/AP account codes for proposed eliminations.

### 38.2 Worksheet run

1. **New run** — name + period start/end.
2. **Propose** — aggregates member trial balances by account code; proposes IC AR/AP and NCI eliminations.
3. Review eliminations; adjust if needed. **Post** freezes an immutable consolidated BS/P&L package on the holding tenant only.

Locked-period post may require an owner/admin override. Associates appear as a single equity-method line, not line-by-line consolidation.

---

## 38a. Intercompany Documents

Companion to consolidation (#261) — mark sales/purchases between sister entities so each side has a matching document for recon.

1. On an invoice or bill, tick **Intercompany** and pick the **counterparty tenant** (must be in the same consolidation group).
2. On save, Easy-Books creates a **draft mirror** on the counterparty (no GL until that entity posts it) — invoice → mirror bill, bill → mirror invoice.
3. Open **Intercompany → Reconciliation** (`/intercompany/recon`) for a paginated match of IC docs across the group (amounts, mirror links, unmatched flags).

Demo seed: Manufacturing ↔ Trading IC invoice with a draft mirror bill after the consolidation graph is built. CoA leaves **1180** Due from Affiliates / **2180** Due to Affiliates support IC AR/AP presentation.

---

## 39. INVENTORY VALUATION DEPTH

IAS 2 depth beyond average cost — landed cost, lot/serial, and NRV write-downs (trader / manufacturing).

### 39.1 Landed cost

- From **Inventory → Valuation** (or landed-cost entry), allocate freight/duty onto receipt layers (`value` or `qty` method).
- Draft → allocate → posts into inventory layers; demo seed leaves a draft **LC** row to walk through.

### 39.2 Lot / serial

- On a product, enable **Track lot** / **Track serial**. Receipts and layers can carry `lot_no`; product ledger and valuation respect tracking flags.

### 39.3 NRV write-down

- Set **NRV per unit** on products where recoverable amount is below cost.
- Create an **NRV run** — draft lines show write-down amounts; post uses the allowance (or direct write-down) path. Demo traders/manufacturers get a draft NRV review after seed.

---

## 40. SAVE PDF TROUBLESHOOTING

**Save PDF** on invoices, bills, lab reports, and the customer/vendor portal downloads a server-rendered PDF (WeasyPrint).

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Message about **PDF engine unavailable** / 503 | WeasyPrint or system libs (Pango/Cairo) missing or crashing | **Debian/Ubuntu/WSL2:** `sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi8 shared-mime-info fonts-dejavu-core` then restart the backend. **Windows:** install the [tschoonj GTK3 runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) (or re-run `install-and-run.ps1`, which installs it) then restart the backend. Avoid the older winget `GtkD.GtkPlusRuntime` package — its Pango is too old for WeasyPrint 68+. Docker images include the Linux libs in `backend/Dockerfile`. Check the backend log; retry |
| **Cannot reach the API** / connection refused | Backend not running or wrong `NEXT_PUBLIC_API_URL` | Start the API (`python main.py` / installer); confirm the frontend points at the same host:port |
| Generic **PDF download failed** with HTTP detail | Auth expired, document missing, or permission | Re-login; confirm the document exists and you have view rights |

The UI surfaces the server `detail` when available instead of a bare browser “Failed to fetch”.

---

## 41. WEIGHBRIDGE (MILL MARKETPLACE LISTING)

Weighbridge is **not** a separate truck-scale module and **not** an Optional first-party pack. It is a **private Marketplace listing** (`partner.easybooks.weighbridge`) that installs a Studio bundle on **invoices**: a required **Gate pass** and an optional **Lot ref**. Those values are stored on the invoice; they **do not** change the GL (∑Dr = ∑Cr is unchanged).

Hospital, simple, trader, and other non-mill tenants **do not** see this card.

### 41.1 Who can see it

| Company | Sees Weighbridge? |
|---------|-------------------|
| Yarn spinning mill (`demo.spinning@easy-books.app`) | Yes — **For you** |
| Manufacturing mill (`demo.manufacturing@easy-books.app`) | Yes — **For you** |
| Any tenant with the **Yarn Spinning** module installed | Yes |
| Hospital / clinic demo | No |
| New public signup (Base Accounting only) | No until the company is a mill or ops grants the listing |

Password for every demo: `demo1234`.

### 41.2 Install (admin / owner)

1. Log in as a mill user.
2. Open **System → Add-ons**, or press **Ctrl+K** and type `weighbridge`, or go to `/apps?tab=marketplace`.
3. On the **Marketplace** tab, find **Weighbridge** (scale icon, tags `spinning` + `private`, badge **For you**).
4. Click **Install**. Confirm the sandbox note: install never downloads or executes partner code.
5. The card switches to **Installed**. Settings → Studio → Fields now lists **Gate pass** (`x.gate_pass_no`) and **Lot ref** (`x.lot_ref`) on **invoice**.

### 41.3 Day-to-day: mill sales invoice

1. **Sales → Invoices → New** (or Ctrl+K → new invoice).
2. Fill customer, lines, dates as usual.
3. Fill **Gate pass** (required). Example: the slip number from the mill weighbridge, `GP-2026-0142`.
4. Optionally fill **Lot ref** (yarn/lot number). This field is form-only — it does not print by default.
5. Save / post. The invoice GL is the same as before (typically Dr AR / Cr Revenue ± tax/COGS). Gate pass and lot stay on `custom_fields`.
6. **Print** the invoice: **Gate pass** appears on the document (`show_on_print`). **Lot ref** does not unless you turn print on in Studio.
7. Invoice **lists** can show Gate pass (`show_on_list`).

This overlay is for **sales invoices**, not spinning bale receipts or gate inward. Production still uses Spinning / Purchases & Store screens; Weighbridge only annotates the customer invoice.

### 41.4 Change or remove the overlay

| Goal | Where |
|------|--------|
| Rename labels, make Lot ref required, or print Lot ref | **Settings → Studio** → Fields / Form layout / Print |
| Stop using the overlay | Add-ons → Marketplace → **Uninstall**. Field **definitions** are archived; values already saved on old invoices remain readable |
| Grant the card to a non-mill tenant | Ops: `PUT /api/ops/tenants/{id}/marketplace-private` with `extension_ids: ["partner.easybooks.weighbridge"]` |

### 41.5 What Weighbridge is not

- Not a weighbridge ticket register, truck in/out log, or live scale integration.
- Not a GL account or inventory movement.
- Not visible under Optional / Recommended as a first-party module.
- Not shown to hospital or other ungranted tenants (catalog JSON omits the id; install returns 404).

Visual mill cycle (install → invoice → print) is also on **System → Workflow** for manufacturing and spinning companies, and on **System → User Guide** (Weighbridge tab).
