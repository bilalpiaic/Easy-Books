# Design: Voucher Series & Transaction Types (#44, Phase 1)

**Date:** 2026-06-06
**Status:** Approved
**GitHub issue:** #44

## Overview

Replace the single generic `JV-{id}` numbering with **typed voucher series** — each
transaction type gets its own running sequence (SL-000001, CP-000001, BP-000001…),
assigned automatically by the nature of the posting, and surfaced in the Journal,
General Ledger, Day Book and the transaction listing (with a voucher-type filter).

**Branch:** `feature/issue44-voucher-series`, based on
`feature/sales-ux-density-and-posted-edit` (v2.2.0). Parallel to the issue-43
finisher and issue-45 sub-ledger branches. Rebases onto `main` after #46 merges.

### Locked decisions
| Decision | Choice |
|----------|--------|
| Assignment | **Explicit per source** (each `post_transaction` caller declares its type) |
| Existing data | **Backfill / renumber**, preserving the original number in `legacy_jv_number` |
| Phase-1 surfacing | Typed numbering everywhere + show type/number in Journal, Day Book, General Ledger + voucher-type filter on the transaction/journal listing |
| COGS sub-entry of a sale | **JV** (avoids two SL numbers per invoice) |

## Key facts (verified)
- `Transaction.jv_number` is the only number; it's generated in ONE place —
  `services/posting.py:148`, `jv_number = f"JV-{txn.id:05d}"`. `post_transaction`
  (`posting.py:112`) is the sole GL writer, called from ~18 routers/services.
- Per-type sequences are cheap: `next_number(session, tenant_id, name, prefix, *, width, fmt)`
  (`routers/common.py:136`) + `SequenceCounter` (`models.py:976`) are atomic
  (`SELECT … FOR UPDATE`), already used for invoice/bill numbering.
- Source→transaction back-refs exist for backfill: `Invoice.transaction_id` +
  `Invoice.cogs_transaction_id`, `Bill.transaction_id`, `PaymentReceived.transaction_id`
  (+ `cash_account_id`), `BillPayment.transaction_id` (+ `cash_account_id`),
  credit/debit notes, advances, assets, GRN, deferred-revenue, production orders.
- Reversals: `Transaction.is_reversed` / `reversed_by_id`.
- Bank vs cash: an account is *bank* if it is referenced by a `BankAccount.coa_account_id`
  for the tenant; otherwise *cash* (e.g. 1000 Cash in Hand).

## Voucher type catalog
`JV` Journal · `CP` Cash Payment · `CR` Cash Receipt · `BP` Bank Payment ·
`BR` Bank Receipt · `SL` Sales Invoice · `SR` Sales Return · `PR` Purchase Invoice ·
`PV` Purchase Return · `CO` Contra (cash↔bank) · `DN` Debit Note · `CN` Credit Note.

Defined as a single source-of-truth constant (e.g. `services/vouchers.py: VOUCHER_TYPES`),
so the catalog, labels and validation live in one place.

## Assignment map (explicit, per source)
| Posting site | Type |
|---|---|
| `invoices.py` create/edit (sales) | `SL` |
| `invoices.py` COGS sub-entry | `JV` |
| `credit_notes.py` | `CN` |
| `bills.py` (purchase) | `PR` |
| `debit_notes.py` | `DN` |
| Sales return (if a distinct flow exists) | `SR` |
| Purchase return | `PV` |
| `payments.py` receipt | `CR` if `cash_account` is cash, `BR` if bank |
| `payments.py` payment-made | `CP` if cash, `BP` if bank |
| Contra / cash↔bank transfer | `CO` |
| `transactions.py` manual JV; advances/assets/GRN/deferred/production/recurring/imports/reports; anything unmapped | `JV` |
| Reversal of a txn | inherits the reversed txn's `voucher_type` |

Implementation: `post_transaction(..., voucher_type: str = "JV")`. Each caller passes
its type; the payment routers compute CR/BR/CP/BP from the cash/bank classification
of `cash_account_id`. A small helper `classify_cash_account(session, tenant_id, account_id) -> "cash"|"bank"` centralises the rule.

## Schema + numbering
- New columns on `Transaction`: `voucher_type: str = Field(default="JV", index=True)`
  and `legacy_jv_number: Optional[str] = None`.
- `post_transaction` numbers via
  `next_number(session, tenant_id, name=f"voucher:{vtype}", prefix=vtype, width=6, fmt="{prefix}-{seq:06d}")`
  → `SL-000001`. (Replaces the `JV-{id}` line.)
- Alembic migration adds both columns (nullable add; SQLite-safe; existence-guarded
  per the project's migration pattern). `create_all` dev boot also gets them via the model.

## Backfill (one-time, idempotent data migration)
Runs as part of the Alembic migration (or a guarded startup step) AFTER the columns exist:
1. **Infer type** for every existing `Transaction` via the source back-refs:
   build maps `{txn_id → type}` from `Invoice.transaction_id→SL`,
   `Invoice.cogs_transaction_id→JV`, `Bill.transaction_id→PR`,
   `PaymentReceived.transaction_id→CR/BR` (by cash/bank), `BillPayment→CP/BP`,
   credit-note→CN, debit-note→DN, contra→CO; reversal txns inherit their parent's
   type (`reversed_by_id`); everything unmatched → `JV`.
2. **Preserve**: copy current `jv_number` → `legacy_jv_number`.
3. **Renumber** per type in deterministic chronological order (`date`, then `id`):
   assign `TYPE-000001…`, and seed each tenant's `SequenceCounter` (`voucher:{TYPE}`)
   `next_value` to one past the highest assigned, so newly posted vouchers continue
   the series without collision.
4. **Unique-constraint safety**: the renumber writes through a temporary unique
   placeholder first (e.g. `__MIG__{id}`), then the final typed number, so the
   `unique(tenant_id, jv_number)` constraint is never violated mid-update.
5. **Idempotency**: guard on `legacy_jv_number IS NULL` (un-backfilled) so re-running
   the migration is a no-op; per-tenant scoping throughout.

The legacy number remains queryable and is shown in the UI (tooltip / detail) so
audit trails and printed documents stay resolvable.

## Surfacing (Phase 1 core)
- **Journal** (`/journal`) + **Day Book**: show `voucher_type` (badge) alongside the
  voucher number; the listing/transactions endpoint returns `voucher_type` +
  `legacy_jv_number`.
- **General Ledger** (`/ledger`): each entry already shows `jv_number`; show the
  typed number (it now IS the typed number) + the type.
- **Filter**: voucher-type dropdown (+ voucher-number search) on the transaction/
  journal listing endpoint and page.

## Components / boundaries
- `services/vouchers.py`: catalog constant, `classify_cash_account`, and the
  `voucher_number(session, tenant_id, vtype)` helper (wraps `next_number`).
- `services/posting.py`: `post_transaction` gains `voucher_type`; numbering via the
  helper.
- `alembic/versions/xxxx_voucher_series.py`: columns + backfill.
- Call sites: pass the right `voucher_type` (mechanical, ~18 sites; most → JV).
- Frontend: journal/ledger pages show type; listing filter.

## Testing
- **Assignment:** each source posts the correct type and a correctly-formatted,
  per-type-sequenced number; payment cash/bank split correct; reversal inherits
  parent type; manual JV → JV. Double-entry invariant unaffected.
- **Numbering:** sequences are independent and monotonic; two posts of the same
  type get consecutive numbers (atomicity).
- **Backfill:** on a seeded multi-source DB, types are inferred from back-refs;
  renumber is chronological + unique; `legacy_jv_number` preserved; idempotent
  (second run no-ops); `SequenceCounter` continues for new posts (post-backfill a
  new SL continues after the highest backfilled SL).
- **Surfacing:** listing returns voucher_type; filter narrows correctly; journal/
  ledger render type.
- **Migration:** `alembic upgrade head` clean; fresh `create_all` DB has columns.

## Out of scope (Phase 2)
Voucher type/filter in customer & vendor ledgers, cash book, bank book, and
trial-balance drill-down. The catalog/columns/numbering are structured so Phase 2
is pure surfacing with no schema change.
