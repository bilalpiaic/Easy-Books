# Voucher-Type Selector on New Entry (#52 §4) — Design

_Date: 2026-06-09 · Branch: `feature/issue52-voucher-lov-entry` · Base: `main` @ v2.5.0_

## Problem

The manual New-Entry / Journal-Voucher form (`frontend/src/app/(dashboard)/entry/page.tsx`)
posts to `POST /api/transactions`, which currently calls `post_transaction` **without** a
`voucher_type` — so every hand-keyed entry defaults to `"JV"`. Voucher series (#44) added
typed vouchers and per-type number series, but the manual form can't pick a type. This
adds a voucher-type selector that drives the number-series classification.

## Scope (decided)

- **In:** add `voucher_type` to the create-transaction request + thread it to
  `post_transaction`; add a voucher-type `<select>` (full catalog, default JV) to the
  manual entry form and send it in the payload.
- **Out (future, per roadmap):** per-type entry layouts and per-type posting logic — the
  selector affects *number-series classification only*.

## Decisions (locked during brainstorming)

1. **Full catalog, default JV** — the selector offers all `VOUCHER_TYPES` from
   `lib/voucherTypes.ts`; default selection is `JV`.
2. **Backend stays lenient** — no strict enum validation on `voucher_type` (the value
   comes from the selector; consistent with current behaviour and the seeder).
3. **Reuse the existing number-series logic** — `post_transaction` already assigns the
   correct per-type `jv_number`; no numbering code changes.

## §1 · Backend

`backend/routers/transactions.py`:
- Add `voucher_type: Optional[str] = "JV"` to the `TransactionCreate` Pydantic schema.
- In `create_transaction`, pass it through:
  `post_transaction(..., voucher_type=tx_data.voucher_type or "JV")`.

`post_transaction` already accepts `voucher_type` and applies the matching per-type number
series, so no other backend change is needed. Omitting the field keeps the prior default
(`"JV"`), so existing callers/tests are unaffected.

## §2 · Frontend (`entry/page.tsx`)

- Add `voucherType` state initialised to `"JV"`.
- Add a labelled `<select>` next to the Date field, options built from `VOUCHER_TYPES`
  (`code → label`), following the form's existing input styling.
- Include `voucher_type: voucherType` in the `POST /api/transactions` request body.

## §3 · Testing

- **Backend (pytest):** `POST /api/transactions` with `voucher_type="CP"` → the created
  transaction has `voucher_type == "CP"` and a CP-series `jv_number`; a request that omits
  `voucher_type` still yields `"JV"` (back-compat). This is the correctness gate.
- **Frontend:** `npm run lint` clean (no new errors in `entry/page.tsx`) + manual smoke
  (selector renders, defaults to JV, posting a chosen type creates a correctly-typed
  voucher).

## Success criteria

On the New-Entry form a user can pick a voucher type (default JV); the posted transaction
carries that type and the correct per-type voucher number. Omitting the field preserves
the JV default. No changes to per-type posting logic (future scope).
