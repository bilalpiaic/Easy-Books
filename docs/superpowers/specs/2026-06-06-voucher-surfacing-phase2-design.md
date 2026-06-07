# Design: Voucher Surfacing Phase 2 (#44 Phase 2)

**Date:** 2026-06-06
**Status:** Approved
**GitHub issue:** #44 (Phase 2 — broader surfacing)

## Overview

Extend voucher-type visibility (shipped in #44 Phase 1 for Journal + General Ledger)
to the remaining ledger views: **customer & vendor sub-ledgers** (badge + filter),
and **new Cash Book / Bank Book** pages built as voucher-aware GL-ledger views.
Trial-Balance drill-down already lands on `/ledger` (voucher badges from Phase 1) —
verify only.

**Branch:** `feature/issue44-phase2-voucher-surfacing`, off `main` (v2.3.0).

### Locked decisions
| Decision | Choice |
|----------|--------|
| Customer/vendor ledger | voucher-type **badge per row + voucher-type filter** (client-side; small single-party row sets) |
| Cash Book / Bank Book | **New ledger-based views** reusing `/api/reports/ledger` (already returns `voucher_type` + running balance) |
| Bank Book with multiple banks | **default to first bank account + a selector** (not aggregated) |
| TB drill-down | already done (lands on `/ledger` with badges) — verify only |
| Cash/Bank Book format | ledger-view form (NOT classic two-column receipts/payments) |

## Key facts (verified)
- `/api/reports/ledger` returns per-account `entries`, each with `voucher_type`,
  `jv_number`, `transaction_id`, debit/credit, and a running `balance` (Phase 1
  added `voucher_type`). It accepts `account_id` / `account_code` / `search`,
  `start`, `end`. The `/ledger` page renders the voucher badge already.
- `subledger.py` `customer_ledger` / `vendor_ledger` build rows from source
  documents; each row has `doc_type` + `doc_id` (invoice / payment_received /
  bill / bill_payment) but NO `voucher_type`. The underlying documents carry a
  `transaction_id` whose `Transaction.voucher_type` is the value to surface.
- Cash vs bank: an account is *bank* iff referenced by a `BankAccount.coa_account_id`
  for the tenant (else *cash*) — same rule as `services/vouchers.classify_cash_account`.
- `lib/voucherTypes.ts` is the single TS catalog (labels + `voucherTypeBadgeClass`).
- Sidebar **Banking** section has Bank Accounts + Reconciliations (no Cash/Bank Book).

## Architecture

### A. Customer & Vendor ledger — voucher badge + filter
- **Backend (`subledger.py`):** add `voucher_type` to each ledger row. The row's
  source document has a `transaction_id`; resolve `Transaction.voucher_type` for
  it. Implement a small shared resolver (e.g. batch-load the relevant transactions'
  `{id: voucher_type}` once per request, tenant-scoped, and attach to each row) so
  both `customer_ledger` and `vendor_ledger` use one code path (DRY). Rows whose
  document has no transaction (edge) → `voucher_type: None`.
- **Frontend (`customers/[id]/ledger`, `vendors/[id]/ledger`):** render a
  voucher-type badge next to each row (reuse `lib/voucherTypes.ts`); add a
  voucher-type `<select>` filter that filters the already-loaded rows **client-side**
  (these are bounded single-party lists). Match the Journal/GL badge styling +
  `ui-*` density classes.

### B. Cash Book + Bank Book — new ledger-based pages
Both reuse the existing `/api/reports/ledger` engine (entries already carry
`voucher_type` + running balance):
- **Cash Book** (`frontend/.../cash-book/page.tsx`): resolve the tenant's **cash**
  accounts = Asset GL accounts whose code looks like cash/bank (`10%`) and are NOT
  linked to a `BankAccount` (i.e. cash, e.g. `1000 Cash in Hand`). If exactly one,
  show it; if several, a small account selector. Fetch `/api/reports/ledger?account_code=…&start=&end=`
  and render date / voucher badge / description / debit / credit / running balance,
  plus a client-side voucher-type filter and date range.
- **Bank Book** (`frontend/.../bank-book/page.tsx`): a **bank-account selector**
  populated from `/api/bank-accounts` (each has `coa_account_id`); default to the
  first. Fetch the selected bank GL account's ledger via
  `/api/reports/ledger?account_id={coa_account_id}&start=&end=` and render the same
  way (badge, running balance, voucher filter, date range).
- Both pages are thin views over the ledger engine — **no new backend endpoint**.
  Add nav entries under the **Banking** section in `Sidebar.tsx`.
- **Cash-account identification helper (backend, optional):** if the frontend needs
  to know which accounts are "cash" vs "bank", add a tiny read endpoint or reuse
  existing data: `/api/accounts` (list) + `/api/bank-accounts` (→ which coa_account_ids
  are bank) lets the page compute cash = code-`10%` Asset accounts minus bank-linked
  ones. Prefer composing existing endpoints over a new one; add one only if the
  composition is awkward.

### C. Trial-Balance drill-down
Verify the existing `/trial-balance` → `/ledger?account=CODE` drill shows voucher
badges (it should, via Phase 1). No code expected; add a note if a gap is found.

## Components / boundaries
- `backend/routers/subledger.py`: `voucher_type` on customer/vendor ledger rows
  (shared resolver).
- `frontend/.../customers/[id]/ledger/page.tsx`, `.../vendors/[id]/ledger/page.tsx`:
  badge + client-side voucher filter.
- `frontend/.../cash-book/page.tsx`, `.../bank-book/page.tsx`: new ledger-view pages
  + `Sidebar.tsx` nav entries.

## Testing
- **Backend:** customer ledger rows carry the correct `voucher_type` per source doc
  (invoice→SL, payment-received→CR/BR by cash/bank, etc.); vendor ledger likewise
  (bill→PR, bill-payment→CP/BP); tenant-scoped; row with no transaction → None.
- **Frontend:** badges render on both ledgers; voucher filter narrows; Cash Book
  loads the cash account ledger; Bank Book loads the selected bank account (defaults
  to first; selector switches); both show badges + running balance; build/lint clean.

## Out of scope
Classic two-column receipts/payments Cash/Bank Book format; aggregating multiple
banks into one book; any change to the TB→GL drill (already works); a voucher-type
filter param on the `/ledger` backend (client-side filtering suffices for these
focused views).
