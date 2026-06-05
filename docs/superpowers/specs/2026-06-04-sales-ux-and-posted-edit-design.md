# Design: Sales/Inventory UX + Posted-Document Editing

**Date:** 2026-06-04
**Status:** Approved (user approved full design; Feature 5 guard = block-if-paid)

## Overview

Five largely-independent features requested by the product owner, sequenced
"quick wins first". All work targets the **modern stack** (`backend/` FastAPI +
`frontend/` Next.js 16). No new tables are required; the only model-payload
addition is surfacing `customer_id` on the Record-Payment flow (the column
already exists on `PaymentReceived`).

Decisions locked during brainstorming:

| Decision | Choice |
|----------|--------|
| Source of "Cost Price" (Products column + report GP/COGS) | Live `Product.avg_cost` (weighted-average, read-only) |
| Editing posted invoices/bills | Reverse & re-post (reuse existing reversal engine) |
| "Last price" shown while invoicing/billing | Per-customer, with global fallback |
| Build order | Quick wins first |
| Posted-edit guard when payments exist | **Block-if-paid** (unallocate first) |

### Key existing machinery to reuse (do NOT rebuild)

- **Reversal engine already exists.** `routers/invoices.py:441-460` reverses the
  prior GL `Transaction` and posts a correction when a *draft* that was already
  GL-posted is updated. `Transaction.is_reversed` / `reversed_by_id` track the
  audit chain. Feature 5 mostly relaxes the status gate and adds stock reversal.
- **Period locking is real.** `Period.is_locked` + `PATCH /api/periods/{id}/lock`;
  `services/posting._check_period_locked()` already raises on locked dates.
- **`StockMovement` is a full event log** (`unit_cost`, `total_cost`, `direction`,
  `occurred_at`, `owner_customer_id`, `source_doc_type/id`, `transaction_id`).
  Opening/Purchased/Sold/Closing per product over any window is derivable from it.
- **`Invoice`/`Bill` already carry `customer_id`** alongside free-text
  `customer_name`. `InvoiceLine`/`BillLine` carry `product_id` + `rate`.

---

## Feature 1 — Compulsory Customer Dropdown

**Problem:** `frontend/src/app/(dashboard)/payments-received/page.tsx:286` uses a
free-text customer name. Free text fragments a single customer across spellings
and breaks every per-customer report.

**Backend** (`routers/payments.py`):
- Accept `customer_id` on the create-payment payload. Resolve the canonical
  `customer_name` server-side from the `Customer` row (tenant-scoped). Keep
  writing `customer_name` for back-compat with existing displays.

**Frontend:**
- Replace the free-text `<input>` with a searchable `<select>` bound to
  `customer_id`, populated from `GET /api/customers`. Required: the
  "Record Payment" button stays disabled until a customer is selected.
- Audit other free-text customer/vendor entry points and convert them in the
  same pass for consistency (invoice create = customers, bill create = vendors).

**Tests:** payment create rejects missing `customer_id`; resolves name from id;
tenant isolation (cannot reference another tenant's customer).

---

## Feature 2 — Product List Polish

**On the `/products` list view** (`frontend/src/app/(dashboard)/products/page.tsx`):
- **Category column** — resolve `category_id` → `"Main › Sub"` using the flat
  category map already built at `products/page.tsx:243-249`.
- **Rename "Default Rate" → "Selling Price"** — column header (line 368) + form
  label (line 517). Label-only; the DB field stays `default_rate`.
- **Cost Price column** — show live `avg_cost` (read-only); `—` for service items.

**Backend** (`routers/products.py:72`): add `avg_cost` and `category_label` (or
`category_id` already present — resolve label client-side) to the list payload.

**Tests:** list payload includes `avg_cost`; category label resolves for parent
and sub categories and for uncategorized products.

---

## Feature 3 — Last Sale Price + Customer's Products Module

### 3a. Last-price hint while invoicing/billing

**Backend:** `GET /api/products/{id}/last-price?customer_id=&kind=sale|purchase`
- `kind=sale`: most recent `InvoiceLine.rate` for the product where the invoice's
  `customer_id` matches; if none, fall back to the most recent line to any
  customer. Return `{ rate, date, scope: "customer"|"global"|null }`.
- `kind=purchase`: same against `BillLine` / vendor.

**Frontend:** in the invoice/bill line editor, when a product is selected fetch
its last price and render an inline hint
(*"Last sold to this customer: ₨X on DD-MMM"*) with a **"Use"** button that fills
the rate. Never auto-overwrites a rate the user already typed.

### 3b. Customer's Products module

**Backend:** `GET /api/customers/{id}/products` → every product ever sold to the
customer: `{ product_id, name, code, last_rate, last_date, total_qty, invoice_count }`.

**Frontend:** a "Products" section/tab on the customer detail page; each row links
into the product ledger (`/products/ledger?product=<id>`).

**Tests:** per-customer last price beats global; global fallback when customer has
no history; customer-products aggregation totals; tenant isolation.

---

## Feature 4 — Customer Performance Report Expansion

Current endpoint (`routers/reports.py:1126`) returns only revenue / invoice_count
/ outstanding / avg_days_to_pay. Expand into a two-part report driven by a
**compulsory customer selector** (same dropdown as Feature 1) plus a date range.

### 4a. Customer Performance (per selected customer, over `start`..`end`)
- **Periodical Sales Volume** — revenue and units bucketed by month.
- **Cost of Sales & GP** — COGS = Σ(qty sold to customer × `avg_cost`);
  GP = revenue − COGS; GP %.
- **Product & Category summary of trade** — items sold to this customer grouped
  Category → Product, each with qty, revenue, COGS, GP.

Endpoint shape: extend `/api/reports/customer-performance` to accept
`customer_id` and return the breakdown when one is supplied; keep the existing
all-customers ranking when omitted (back-compat).

### 4b. Product Performance section (period inventory movement)
Derived purely from `StockMovement`. Per product:

| Column | Derivation |
|--------|-----------|
| Opening Stock Qty / Value | net qty of all movements before `start`; value at `avg_cost` |
| Qty Purchased | RECEIPT / GRN movements in period |
| Qty Sold (Net) | SHIPMENT + DELIVERY + ISSUE − returns in period |
| GP | sales revenue − COGS for the product in period |
| Closing Stock Qty / Value | opening + purchased − sold; value at `avg_cost` |

Enhances the existing `/inventory/performance` page rather than duplicating it.

**Tests:** opening/closing reconcile (opening + purchased − sold = closing); GP
math; COGS uses `avg_cost`; empty-period and no-movement products.

---

## Feature 5 — Editing Posted Invoices/Bills

**Approach:** reverse & re-post, reusing the engine at `invoices.py:441-460` and
the bill equivalent.

### Eligibility
**Allowed** when: status is posted/sent/overdue **AND** no payment/allocation
exists against the doc **AND** the doc date is not in a locked period **AND** the
doc is not already reversed.

**Blocked** (HTTP 403/400 with a clear message) when:
- any `PaymentAllocation` references the doc → *"Unallocate payments before
  editing."* (**block-if-paid**, user-confirmed)
- the doc date is in a locked `Period`
- the doc is already reversed

### On save of an eligible posted doc
1. Reverse the original GL `Transaction` (existing pattern).
2. **Reverse the original `StockMovement`s and re-apply new ones** for the edited
   lines — *this is the new piece*; current path handles GL only, not stock.
   Reversal uses each original movement's stored `unit_cost` so avg_cost drift
   from later sales does not corrupt the correction.
3. Post the corrected GL + stock at the edited values; link via `reversed_by_id`.
4. Keep the same document number; write an audit-log entry.

### Frontend
- Enable the edit button on `invoices/[id]` and `bills/[id]` for eligible posted
  docs; disabled with tooltip when blocked.
- Confirmation modal: *"This will reverse the original ledger entry and post a
  correction. Continue?"*

### Edge cases
- Partially-paid → blocked (unallocate first).
- Multi-currency → re-snapshot FX per existing create/update logic.
- Deferred-revenue invoices (`is_deferred`) → reverse + re-post deferral schedule.
- Stock since sold → reversal uses original `unit_cost` (point 2 above).

**Tests:** posted edit reverses + re-posts balanced GL; stock restored then
re-applied; block-if-paid fires; locked-period blocked; already-reversed blocked;
audit chain (`is_reversed`/`reversed_by_id`) intact; number preserved.

---

## Cross-cutting

- **Multi-tenancy:** every query filters `tenant_id`; new endpoints resolve ids
  tenant-scoped.
- **Double-entry invariant:** all re-posts validate `Σdebit == Σcredit` before
  commit (enforced by `post_transaction`).
- **Testing:** backend `pytest` per feature; frontend per `frontend/AGENTS.md`
  (read `node_modules/next/dist/docs/` before writing Next.js 16 code).
- **Migrations:** none expected. If any column is added, follow the Alembic +
  `create_all` guard pattern in CLAUDE.md.

## Build order
1. Feature 1 (customer dropdown)
2. Feature 2 (product list polish)
3. Feature 3 (last price + customer products)
4. Feature 4 (customer performance expansion)
5. Feature 5 (posted-document editing)
