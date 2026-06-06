# Design: Consolidated ↔ Sub-Ledger General Ledger View (#45)

**Date:** 2026-06-06
**Status:** Approved
**GitHub issue:** #45

## Overview

Add a **Consolidated ↔ Sub-Ledger** view toggle to the General Ledger (`/ledger`).
Consolidated shows balances at main-account level (the current behaviour). In
Sub-Ledger mode, control accounts (AR, AP, Bank/Cash) expand to show their
constituent sub-entities (customers, vendors, individual bank/cash accounts) with
opening / debit / credit / closing, each linking to its existing detailed ledger
for voucher-level drill-down.

**Branch:** `feature/issue45-subledger`, based on
`feature/sales-ux-density-and-posted-edit` (v2.2.0 — needs the density system).
Parallel to the issue-43 finisher. Rebases onto `main` after #46 merges.

### Locked decisions
| Decision | Choice |
|----------|--------|
| Control accounts in v1 | **AR + AP + Bank** (Stock deferred) |
| Where | **Toggle on existing `/ledger` page** |
| Drill-down | **Inline expand of sub-entity summary rows + each links to its existing detailed ledger** |
| Bank treatment | Each cash/bank **GL account** is a sub-entity of a "Cash & Bank" group (they are already separate GL accounts — no document reconstruction) |

## Key facts (verified)
- `Account` has `parent_id` (hierarchy) and `type` ∈ Asset/Liability/Equity/Revenue/Expense.
- **AR/AP have no per-party GL accounts.** GL holds only the aggregate on the
  control account (`default_ar_account`=1100, `default_ap_account`=2000 from
  settings). Per-party detail is reconstructed from documents in
  `routers/subledger.py` (`customer_ledger`, `vendor_ledger` already exist,
  per single id, returning opening + chronological events + running balance).
- **Bank/Cash are real GL accounts** (payments reference `cash_account_id` →
  `account.id`); their per-account opening/Dr/Cr/closing is already computed by
  the existing `/api/reports/ledger` per-account logic.
- Existing `/api/reports/ledger` returns per-account groups with
  opening/entries/running/closing and each entry's `jv_number`+`transaction_id`
  (voucher drill-down). Unchanged by this feature.

## Architecture

### Backend — new endpoint
`GET /api/reports/ledger/subledger?control=ar|ap|bank&start=&end=`
→ `{ control: {id, code, name}, items: [{ id, name, link, opening, debit, credit, closing }], control_balance, sub_total, reconciles: bool }`

- **ar** — control = tenant `default_ar_account`. Per customer with AR activity:
  opening (AR before `start`), period debit (invoices), period credit
  (payments received), closing. `link = /customers/{id}/ledger`.
- **ap** — control = `default_ap_account`. Per vendor from bills/payments-made.
  `link = /vendors/{id}/ledger`.
- **bank** — sub-entities = the tenant's cash/bank GL accounts. Per account
  opening/Dr/Cr/closing straight from `JournalEntry` (reuse the `/ledger`
  per-account computation). `link = /ledger?account_id={id}`.

**DRY:** factor the per-party opening + period-movement reconstruction out of
`subledger.py customer_ledger`/`vendor_ledger` into a shared helper
(`_party_ar_movement` / `_party_ap_movement` or a parameterised one) used by both
the single-party ledger endpoints and this summary. Do not duplicate the logic.

**Bank-account identification:** the set of GL accounts that are cash/bank. Source
of truth to confirm at implementation: GL accounts referenced as
`PaymentReceived.cash_account_id` / `BillPayment.cash_account_id`, unioned with any
`BankAccount`→GL link and the seeded cash/bank accounts (e.g. 1000 Cash, bank
codes). Pick the most reliable signal found in code; document it in the plan.

### Reconciliation invariant
`sub_total (Σ sub-entity closing) == control_balance (control account GL closing)`,
exposed as `reconciles`. Holds for **document-driven activity**. **Known caveat:**
customer/vendor pre-system **opening balances** (`Customer.opening_balance`,
`Vendor.opening_balance`) reconcile to the control account only if they were
journalised to it at setup; where they weren't, `reconciles` may be false by the
opening-balance delta. Tests assert the invariant for document-driven scenarios
and treat the opening-balance case explicitly (don't assert a false invariant).

### Frontend — `/ledger` page
- A `Consolidated | Sub-Ledger` toggle (same control pattern as the Products
  List/Tree toggle).
- **Consolidated:** unchanged account-level rows.
- **Sub-Ledger:** AR/AP/Bank control rows render an expand chevron; on expand,
  lazy-fetch `/ledger/subledger?control=…` and render sub-entity rows
  (name, opening, Dr, Cr, closing) using `ui-th`/`ui-td`. A small badge on the
  control row shows `reconciles ✓` or `⚠ off by X`. Each sub-entity name links to
  its detailed ledger (customers/vendors `[id]/ledger`, or `/ledger?account_id=`
  for bank). Non-control accounts behave as today.

## Components / boundaries
- `routers/reports.py`: new `ledger_subledger` endpoint (thin; delegates).
- `routers/subledger.py` or a small `services/` helper: shared per-party movement
  computation (the reusable unit).
- `frontend/.../ledger/page.tsx`: toggle + expandable control rows.

## Testing
- AR summary: 2 customers with invoices/payments → correct per-customer
  opening/Dr/Cr/closing; `sub_total == control_balance` (document-driven).
- AP summary: analogous with vendors/bills.
- Bank summary: payments into 2 bank GL accounts → per-account balances match GL;
  `reconciles` true.
- Opening-balance caveat: a customer with a non-journalised `opening_balance`
  surfaces `reconciles=false` (or is handled per the documented policy) — assert
  the documented behaviour, not a false invariant.
- Tenant isolation; empty control account (no sub-entities) returns `items: []`.
- Frontend: toggle switches modes; expanding a control row fetches + renders
  sub-entities; links resolve; lint/build clean.

## Out of scope (v1)
Stock/inventory sub-ledger (per-product). The toggle and endpoint are structured
so a `control=stock` mode can be added later without rework.
