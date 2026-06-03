# Easy-Books — Realistic Improvement Roadmap

> **Methodology:** This document is grounded in three inputs: (1) a line-by-line audit of the
> current codebase (backend/routers, services, models, frontend), (2) verification against
> IAS/IFRS requirements and ISA audit standards, and (3) feature-by-feature parity checks
> against Odoo 17, QuickBooks Online, Manager.io, and Bookkeeper. Items already correctly
> implemented are not listed. Every gap references the exact file or model that must change.
>
> **Last audited:** 2026-05-28

---

## What Is Already Solid (Do Not Regress)

Before listing gaps, these are the areas where Easy-Books already meets or exceeds reference products:

| Area | Strength | Standard Met |
|---|---|---|
| Double-entry GL | `services/posting.py` — single writer, exact Decimal Σdr=Σcr | IAS 1, ISA 315 |
| Audit trail | `AuditLog` + `GET /transactions/{id}.source_docs[]` full drill-down | ISA 230 §A6 |
| Period lock | Enforced inside posting service; locked periods reject writes | IAS 8.42 |
| Reversal | Mirror JV with state unwind (allocations, stock layers) | IAS 8.42 |
| Multi-tenancy | Every query filtered by `tenant_id`; 404 on cross-tenant | SOC 2 CC6.3 |
| Custodial stock | Off-balance-sheet customer goods (memo 1210/2150) | IAS 2.6 |
| Sub-ledger drill-down | Customer/Vendor/Product sub-ledgers with running balance | IFRS 7.7, IAS 1.78(b) |
| RBAC | 4-tier role hierarchy enforced at dependency level | SOC 2 CC6.2 |
| Login throttle | DB-backed sliding-window per IP; survives worker restart | OWASP A07 |
| Idempotency | `Idempotency-Key` middleware prevents duplicate posts | SOC 2 CC6.1 |

---

## GAP ANALYSIS — Prioritised

### Priority 0 — Compliance Blockers (Fix Before Any Audit)

---

#### G-01 · Bank Reconciliation Can Close on Non-Zero Difference
**Standard:** IAS 7.48 — requires cash and cash equivalents be reconcilable to opening/closing balances.
**Manager.io / QuickBooks:** Both enforce zero difference at close.
**Current state:** `routers/reconciliations.py` — the `POST /{id}/close` endpoint sets `status='closed'` without validating `statement_balance == computed_gl_balance`. A reconciliation report showing a non-zero difference is a control failure.
**Fix:**
- In `routers/reconciliations.py`, before setting `status = "closed"`, compute:
  `uncleared_total = sum of JournalEntry amounts for bank account in period NOT matched`
  Reject with `HTTP 422` if `statement_balance - (opening_gl + matched_total) != 0`.
- Add a "Post Adjustment" shortcut on the reconciliation screen in `frontend/src/app/(dashboard)/reconciliations/` that opens a quick JV form (bank fees, interest) pre-filled with the difference, so users can close cleanly without leaving the workflow.

---

#### G-02 · Invoice/Bill Remain Editable After GL Impact
**Standard:** ISA 240 §35 — fraud risk controls require posted documents to be immutable; adjustments must go through reversing entries.
**Odoo / QuickBooks / Manager.io:** All three lock posted documents. Corrections are made via Credit Note or Debit Note.
**Current state:** `routers/invoices.py` — no edit/update endpoint exists currently, but `DELETE /{id}` is allowed even when a payment allocation exists (currently guarded only for invoices with `no payment allocated`). Bills have the same gap. More critically, there is no Credit Note or Debit Note document type — the only correction path is reversal of the entire JV.
**Fix (two parts):**
1. **Enforce delete guard** — verify `DELETE` is blocked whenever any `PaymentAllocation` row references the invoice/bill (currently partially done; verify this is complete and covers partial payments).
2. **Add Credit Note / Debit Note as first-class documents:**
   - New model: `CreditNote` (mirrors `Invoice`; posts `Dr Revenue / Cr AR` — the reverse of an invoice line).
   - New model: `DebitNote` (mirrors `Bill`; posts `Dr AP / Cr Expense`).
   - Status flow: `Invoice` transitions to `credited` when a full CN is applied.
   - This is how Odoo, QuickBooks, and Manager.io handle adjustments without voiding history.

---

#### G-03 · No Comparative Period in Financial Statements (IAS 1.38 Violation)
**Standard:** IAS 1.38 — *"An entity shall present, as a minimum, two statements of financial position, two statements of profit or loss..."* A single-column P&L is non-compliant for any entity claiming IFRS preparation.
**Manager.io / Odoo / QuickBooks:** All produce a prior-period comparison column.
**Current state:** `routers/reports.py` — `income-statement`, `balance-sheet`, and `cash-flow` accept a single `start`/`end` date range. No prior-period data is returned.
**Fix:**
- Add optional query params `compare_start` / `compare_end` to the three financial statement endpoints.
- Return a `comparison: {accounts: [...]}` alongside the primary period data.
- Frontend: `frontend/src/app/(dashboard)/pl/`, `balance/`, `cashflow/` — add a "Compare with prior period" toggle that auto-fills the prior year/quarter range and renders a second column.

---

### Priority 1 — High Business Impact (Missing Core Features)

---

#### G-04 · Multi-Currency Frontend Not Wired (IAS 21 Gap)
**Standard:** IAS 21.21 — foreign-currency transactions must be translated at the spot rate at the date of the transaction.
**Current state:** Backend is fully implemented — `Invoice.currency`, `Invoice.exchange_rate`, `services/fx.py`, `ExchangeRate` model, and `/api/exchange-rates` all exist and work correctly. The gap is entirely in the frontend:
- `frontend/src/lib/utils.ts` — `fmtPKR()` hardcodes PKR formatting.
- `frontend/src/app/(dashboard)/invoices/page.tsx` — no currency/exchange_rate field on the new invoice form.
- `frontend/src/app/(dashboard)/bills/page.tsx` — same.
- `SettingsContext` already carries `currency` (base currency) but doesn't expose a per-document FX rate.
**Fix:**
- Rename `fmtPKR` → `fmtAmount(amt, currency?)` using `Intl.NumberFormat` with `currency` option; replace all 18 usages.
- Add `currency` (dropdown of ISO codes) + `exchange_rate` (auto-fetched from `/api/exchange-rates?date=…&from=…` on date change) fields to invoice and bill forms.
- Show original-currency amount + base-currency equivalent on invoice/bill detail pages.
- This requires no backend changes — it's purely a frontend wiring task.

---

#### G-05 · Fixed Assets & Depreciation Entirely Missing (IAS 16)
**Standard:** IAS 16 — property, plant and equipment must be measured at cost less accumulated depreciation; depreciation charge must be systematic over useful life.
**All four reference products** (Odoo, QuickBooks, Manager.io, Bookkeeper) have a fixed asset register.
**Current state:** Account `5050 Depreciation` exists in the CoA backbone but there is no `Asset` model, no depreciation schedule, and no automation. Users must post a manual JV each period.
**Fix (phased):**
- **Phase A — Asset Register (minimum viable):**
  - New model: `FixedAsset(tenant_id, name, code, account_id, acquisition_date, acquisition_cost, salvage_value, useful_life_months, method: Enum['straight_line','reducing_balance'], accumulated_depreciation, is_disposed)`
  - New model: `DepreciationEntry(asset_id, period_id, depreciation_amount, transaction_id)`
  - New endpoint: `POST /api/assets/{id}/run-depreciation` — computes charge for current period and posts `Dr 5050 Depreciation / Cr Accumulated Depreciation (contra-asset)`.
  - Accumulated Depreciation account should be added to the CoA backbone as a contra-asset (code `1090` or similar).
- **Phase B — Automation:**
  - `POST /api/assets/run-all-depreciation` — processes all active assets; idempotent per `(asset_id, period_id)`.
  - Asset register page in frontend with acquisition form + depreciation schedule table.

---

#### G-06 · No Purchase Order / 3-Way Matching (Non-Manufacturing Tenants)
**Standard:** IAS 2.11, internal control best practice — goods receipts should be matched to POs and invoices before payment (3-way match).
**Odoo / QuickBooks / Manager.io:** All support PO → GRN → Bill matching.
**Current state:** Manufacturing tenants have GRN + Production Orders but non-manufacturing tenants (`simple`, `services`, `trader`) have no PO concept. Bills are created directly with no upstream PO approval step.
**Fix:**
- New model: `PurchaseOrder(tenant_id, number, vendor_id, date, status: Enum['draft','approved','received','billed'], total)`
- New model: `PurchaseOrderLine(po_id, product_id, description, qty, rate, amount)`
- `POST /api/bills` — accept optional `purchase_order_id`; auto-populate lines from the PO; mark PO as `billed`.
- Frontend: Add PO list page under `frontend/src/app/(dashboard)/` (gated to `trader`+ models via sidebar `forModel` filter).
- This does not require changes to the GL posting logic — it's a pre-bill approval workflow.

---

#### G-07 · No Analytic Accounts / Cost Centers
**Standard:** IAS 1 (management information); required by most IFRS-reporting entities for segment reporting.
**Odoo / QuickBooks (class tracking) / Manager.io:** All support cost-center tagging.
**Current state:** No dimension table, no tagging on `JournalEntry`. All P&L is single-dimension.
**Fix:**
- New model: `AnalyticAccount(tenant_id, code, name, type: Enum['cost_center','project','department'], is_active)`
- Add optional `analytic_account_id` to `JournalEntry`.
- Add analytic tagging fields to invoice lines, bill lines, and manual JV rows.
- New report: `GET /api/reports/analytic-pl?analytic_account_id=…&start=…&end=…` — revenue/expense breakdown by cost center.
- Frontend: Analytic selector on JV entry, invoice/bill forms; analytic P&L report page.
- **Do not** make this mandatory — it must remain optional so existing workflows are unaffected.

---

#### G-08 · IFRS 15 Deferred Revenue Has No Recognition Engine
**Standard:** IFRS 15.31 — revenue is recognised when (or as) performance obligations are satisfied, not when cash is received.
**Current state:** Account `2300 Deferred Revenue` exists in the services CoA. But there is no model for tracking performance obligations, no schedule for recognising deferred amounts over time, and `recurringtemplate` (which posts JVs on a schedule) is not wired to deferred revenue accounts automatically.
**Fix:**
- New model: `DeferredRevenueSchedule(tenant_id, invoice_id, total_amount, recognised_amount, start_date, end_date, frequency, next_recognition_date)`
- On invoice post for a service item: if the product has `recognition_method = 'deferred'`, post `Dr AR / Cr Deferred Revenue` instead of `Dr AR / Cr Revenue`.
- New endpoint: `POST /api/deferred-revenue/run-recognition` — for each due schedule, posts `Dr Deferred Revenue / Cr Revenue` and advances `next_recognition_date`.
- Integrate with `recurring/run-due` so it runs automatically.

---

### Priority 2 — Product Parity Gaps

---

#### G-09 · FIFO Inventory Cost Flow Option Missing (IAS 2.25)
**Standard:** IAS 2.25 — entities must use either FIFO or weighted-average for cost measurement; LIFO is prohibited under IFRS.
**Manager.io / Odoo:** Both support FIFO and WAvg toggling per product or globally.
**Current state:** `services/inventory.py` — weighted-average is the only method. The `InventoryLayer` model already uses a FIFO-compatible data structure (separate layers with `qty_remaining`). The `consume_stock` function currently just pulls the oldest layer first (which is already FIFO consumption) but reports cost at WAvg.
**Fix:**
- Add `cost_method: Enum['wavg','fifo']` to `Product` (default `wavg` for backward compatibility).
- In `services/inventory.py::consume_stock`, when `product.cost_method == 'fifo'`, use each layer's own `unit_cost` rather than `product.avg_cost`.
- This is a relatively contained change since the layer structure already supports it — only the cost-read logic differs.
- Add stock-card display of `unit_cost per layer` when FIFO is selected.

---

#### G-10 · Budget vs. Actual Reporting Missing
**Standard:** IAS 1 management commentary best practice; required for meaningful operating review.
**QuickBooks / Odoo / Manager.io:** All support monthly budgets per account with variance reporting.
**Current state:** No `Budget` model exists. No budget entry UI. No budget vs actual report.
**Fix:**
- New model: `Budget(tenant_id, name, fiscal_year, account_id, period_month: int[1-12], amount)`
- New endpoint: `GET /api/reports/budget-vs-actual?year=…` — joins `Budget` with live GL balances, returns `[{account, month, budget, actual, variance, variance_pct}]`.
- Frontend: Budget entry page (spreadsheet-style grid, one row per account, 12 monthly columns); Budget vs Actual report page with colour-coded variance column.

---

#### G-11 · No Expense Claims / Employee Advances
**Standard:** IAS 37 — employee reimbursement obligations should be recognised as liabilities.
**Manager.io / Odoo / QuickBooks:** All have expense/reimbursement workflows.
**Current state:** Expense claims must be entered as manual JVs. No dedicated workflow, no approval step.
**Fix:**
- New model: `ExpenseClaim(tenant_id, user_id, date, description, total, status: Enum['draft','submitted','approved','paid'], transaction_id?)`
- New model: `ExpenseClaimLine(claim_id, account_id, description, amount, receipt_url?)`
- Approval: `PATCH /api/expense-claims/{id}/approve` (admin+); `POST /api/expense-claims/{id}/pay` — posts `Dr Expense / Cr Cash` JV.
- This reuses the existing RBAC (`WriteUserDep` for submit, `AdminDep` for approve) and audit log.

---

#### G-12 · Payment Link / Online Payment Integration Missing
**Standard:** Practical business need; standard in all four reference products.
**Current state:** `BLUEPRINT.md §19` lists "Stripe / Razorpay payment-link integration" as open.
**Fix:**
- Add `payment_link_url` and `payment_link_status` fields to `Invoice`.
- New endpoint: `POST /api/invoices/{id}/payment-link` — calls Stripe Checkout session API, stores the link.
- On Stripe webhook `checkout.session.completed` → auto-post a `PaymentReceived` and allocate.
- Environment variable: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.
- Frontend: "Send Payment Link" button on invoice detail; link status badge (`unpaid/paid`).

---

### Priority 3 — Platform Maturity & Developer Ergonomics

---

#### G-13 · Schema Managed by `create_all()` — Production Risk
**Current state:** `BLUEPRINT.md §15` — "No Alembic. New columns require manual `ALTER TABLE`."
**Risk:** In production, a new column added to `models.py` will silently be absent from an existing database; `create_all()` only creates missing tables, it does not alter existing ones. This has already caused at least two manual migrations (documented in `dev.sh` history for `0011_stock_locations` and the V2.2 column additions).
**Fix:**
- Introduce Alembic alongside the existing `create_all()` bootstrap:
  - `alembic init backend/alembic`
  - Set `target_metadata = SQLModel.metadata` in `env.py`.
  - Generate the baseline migration from the current live schema (`alembic revision --autogenerate -m "baseline"`).
  - In `db.py`, replace `SQLModel.metadata.create_all(engine)` with `alembic upgrade head`.
  - New column additions then use `alembic revision --autogenerate` — no more manual ALTER.
- This is a one-time investment that prevents production schema drift permanently.

---

#### G-14 · Server-Side PDF Generation Not Implemented
**Current state:** `BLUEPRINT.md §19` — "browser print-to-PDF currently works; server-side adds download button."
**QuickBooks / Odoo / Manager.io:** All produce server-side PDFs for invoices, statements, and reports.
**Fix:**
- Add `weasyprint` to `backend/pyproject.toml`.
- New endpoint: `GET /api/invoices/{id}/pdf` — renders an HTML template (Jinja2) with invoice data, passes through WeasyPrint, returns `Content-Type: application/pdf`.
- Reuse the existing invoice print layout from the frontend as the HTML template — extract it to a shared template file.
- Frontend: "Download PDF" button on invoice/bill detail; "Export PDF" on report pages.

---

#### G-15 · FX Revaluation at Period End Missing (IAS 21.23)
**Standard:** IAS 21.23 — monetary items denominated in foreign currencies must be retranslated at the closing rate at each reporting date; unrealised gains/losses go to P&L.
**Odoo / QuickBooks:** Both have end-of-period FX revaluation wizards.
**Current state:** `services/fx.py` is complete. `Invoice` stores `currency` and `exchange_rate` (snapshot). But there is no process that re-rates open AR/AP at period-end closing rates to compute unrealised gains/losses.
**Fix:**
- New endpoint: `POST /api/reports/fx-revaluation?period_id=…` — for each open foreign-currency invoice/bill, computes `(closing_rate - original_rate) × outstanding_amount` and posts `Dr/Cr Unrealised FX Gain/Loss (4901) / Cr/Dr AR or AP`.
- Add `4901 Unrealised FX Gain/Loss` to the common CoA backbone.
- Store revaluation JVs linked to the period so they can be reversed when the position closes (IAS 21.28 requires reversal of revaluation on settlement).

---

#### G-16 · Email Notifications Wired to Nothing
**Current state:** `settings.py` — `email_notifications` key exists in `Settings`, persisted, readable. But no email is ever sent. SMTP credentials are not documented. No send path exists in any router.
**Fix:**
- Add to `backend/.env` template: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`.
- New service: `services/email.py` — `send_email(to, subject, html_body)` using `smtplib`/`aiosmtplib`.
- Wire to two immediate use-cases where email adds clear value:
  1. Invoice sent → email PDF to customer (trigger from `PATCH /api/invoices/{id}` when status → `sent`).
  2. Team invite → email the invite link (trigger from `POST /api/users/invites`).
- Guard all sends behind `settings.email_notifications == True` so tenants that haven't configured SMTP aren't broken.

---

#### G-17 · No Payroll Module (Minor Gap vs Bookkeeper / Manager.io)
**Standard:** IAS 19 — employee benefits, including wages, must be recognised as a liability until paid.
**Bookkeeper / Manager.io:** Both have basic payroll (salary entry, deductions, payslip).
**Current state:** Payroll must be entered as manual JVs (`Dr Salaries Expense / Cr Cash or Salaries Payable`).
**Assessment:** This is a *lower-priority* gap. Payroll is complex (jurisdiction-specific tax tables, SLAs, compliance filings), and most SME customers of Easy-Books segment size would use a dedicated payroll tool or manual JVs. A minimal "payroll journal" feature (not full PAYE/SUI calculation) would satisfy parity:
- New model: `PayrollRun(tenant_id, period, total_gross, total_deductions, total_net, transaction_id)`
- New model: `PayrollLine(run_id, employee_name, gross, deductions_json, net)`
- `POST /api/payroll/run` — validates totals, posts `Dr Salaries Expense / Cr Salaries Payable`, then `Dr Salaries Payable / Cr Cash` when paid.
- **Recommendation:** Defer to a future phase unless the target market has payroll as a stated requirement.

---

## Compliance Matrix Summary

| IAS / IFRS | Requirement | Current State | Gap | Priority |
|---|---|---|---|---|
| IAS 1.38 | Comparative financial statements | Single period only | Missing prior-period column | P0 |
| IAS 1.78(b) | AP disclosure | AR/AP sub-ledgers present | ✅ Met | — |
| IAS 2.25 | FIFO or WAvg (no LIFO) | WAvg only | FIFO option missing | P2 |
| IAS 7.48 | Cash reconcilability | Bank recon exists | Non-zero close allowed | P0 |
| IAS 16 | Fixed assets + depreciation | Manual JV only | No asset model or depreciation | P1 |
| IAS 19 | Employee benefits | Manual JV | No payroll module | P3 |
| IAS 21.21 | FX transaction translation | Backend complete | Frontend not wired | P1 |
| IAS 21.23 | FX revaluation at period end | FX service exists | No revaluation endpoint | P3 |
| IAS 8.42 | Error correction via reversal | Mirror JV present | ✅ Met | — |
| IFRS 7.7 | Financial instrument disclosure | Customer/vendor sub-ledgers | ✅ Met | — |
| IFRS 9 | ECL provisioning | Aging report present | No allowance mechanism | P2 |
| IFRS 15.31 | Revenue recognition at POB | Deferred Revenue account | No recognition schedule | P1 |
| ISA 230 | Audit reperformability | Full drill-down present | ✅ Met | — |
| ISA 240 | Fraud risk — document immutability | No edit endpoint, but no CN | No Credit/Debit Note | P0 |
| ISA 315 | Internal control traceability | DocLink across all pages | ✅ Met | — |

---

## Product Parity Matrix

| Feature | Odoo 17 | QuickBooks | Manager.io | Bookkeeper | Easy-Books | Gap |
|---|---|---|---|---|---|---|
| Double-entry GL | ✅ | ✅ | ✅ | ✅ | ✅ | None |
| Multi-currency backend | ✅ | ✅ | ✅ | Partial | ✅ | Frontend only (G-04) |
| Fixed assets | ✅ | ✅ | ✅ | ✅ | ❌ | G-05 |
| Credit / Debit Notes | ✅ | ✅ | ✅ | ✅ | ❌ | G-02 |
| Purchase Orders | ✅ | ✅ | ✅ | ✅ | Mfg only | G-06 |
| Analytic / Cost Centers | ✅ | ✅ Class | ✅ | ❌ | ❌ | G-07 |
| Budget vs. Actual | ✅ | ✅ | ✅ | ❌ | ❌ | G-10 |
| Bank reconciliation | ✅ | ✅ | ✅ | ✅ | Partial | G-01 |
| Comparative statements | ✅ | ✅ | ✅ | Partial | ❌ | G-03 |
| FIFO inventory | ✅ | ✅ | ✅ | ❌ | ❌ | G-09 |
| Deferred revenue schedule | ✅ | ✅ | Partial | ❌ | ❌ | G-08 |
| Manufacturing track | ✅ | ❌ | Partial | ❌ | ✅ | Ahead |
| Telecom franchise | ❌ | ❌ | ❌ | ❌ | ✅ | Unique |
| Server-side PDF | ✅ | ✅ | ✅ | ✅ | Browser only | G-14 |
| Expense claims | ✅ | ✅ | ✅ | ✅ | ❌ | G-11 |
| Online payment links | ✅ | ✅ | Partial | ❌ | ❌ | G-12 |
| Payroll | ✅ | ✅ | ✅ | ✅ | ❌ | G-17 |
| Alembic migrations | ✅ | N/A | N/A | N/A | ❌ | G-13 |

---

## Suggested Implementation Sequence

```
Sprint 7 (Compliance baseline)
  G-01  Bank reconciliation zero-difference enforcement
  G-03  Comparative period column on financial statements
  G-04  Multi-currency frontend wiring (backend already done)

Sprint 8 (Document integrity)
  G-02  Credit Note / Debit Note documents
  G-13  Alembic migration introduction

Sprint 9 (Asset & Inventory)
  G-05  Fixed asset register + straight-line depreciation
  G-09  FIFO inventory cost flow option

Sprint 10 (Revenue & Forecasting)
  G-08  IFRS 15 deferred revenue recognition
  G-10  Budget vs. Actual reporting

Sprint 11 (Operational completeness)
  G-06  Purchase Orders for non-manufacturing tenants
  G-07  Analytic accounts / cost centers
  G-14  Server-side PDF generation

Sprint 12 (Integration & Automation)
  G-12  Stripe payment link integration
  G-16  Email notifications (SMTP)
  G-15  FX revaluation at period end

Future
  G-11  Expense claims
  G-17  Payroll journal (if market-validated)
```

---

## Open Architecture Decisions Required

1. **Credit Note numbering**: Should CNs share the `INV-` sequence or use a separate `CN-` prefix? Manager.io uses the same AR account but a distinct document type with negative totals. Recommend separate `CN-` prefix to avoid confusion in aging reports.

2. **FIFO scope**: Should FIFO be a tenant-level setting or a per-product setting? Odoo does it per product. IAS 2.25 requires **consistent** application across items with "similar nature and use" — so a tenant-level setting is simpler and more IAS 2-compliant.

3. **Analytic accounts — mandatory vs. optional**: Making analytic tagging mandatory on certain GL accounts (e.g., all expense accounts) is common in larger implementations but would be a breaking change for existing tenants. Recommend: optional everywhere, with a configurable "required analytic on posting" flag per account (match Odoo's behaviour).

4. **Alembic rollout strategy**: The existing DB has been built with `create_all()` and several manual `ALTER TABLE` operations. The Alembic baseline must be generated from the **live schema state** (not just the SQLModel metadata), otherwise the first `alembic upgrade head` will try to create tables that already exist. Recommend: `alembic stamp head` on existing databases after generating the baseline.

5. **Asset depreciation method for telecom intangibles**: The `1300 Franchise Intangible` + `5030 Fee Amortisation` accounts already exist in the telecom CoA. Should IAS 38 (intangible assets) amortisation use the same fixed-asset engine as IAS 16 PP&E depreciation, or be a separate model? Recommend: same engine, with a flag `asset_class: Enum['ppe','intangible']` to determine which standard applies — IAS 16 for PP&E, IAS 38 for intangibles.
