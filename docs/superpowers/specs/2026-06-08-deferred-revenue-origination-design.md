# Deferred Revenue Origination (#47) — Design

_Date: 2026-06-08 · Branch: `feature/issue47-deferred-revenue-origination`_

## Problem

The deferred-revenue feature is **half-built**. The data model
(`DeferredRevenueSchedule`), the recognition engine
(`POST /api/deferred-revenue/run-recognition`), the schedule-list screen, and the
`Product.is_deferred` / `recognition_months` flags all exist — but **nothing
originates a schedule from real activity**. The only place a
`DeferredRevenueSchedule` is constructed is `scripts/seed_demo.py`.
`create_invoice` never reads `product.is_deferred` and never posts to Deferred
Revenue. So IFRS-15-style deferral cannot actually be used by a tenant.

The roadmap originally framed #47 as "rebuild the schedule on edit" — but there
is nothing to rebuild because origination was never built. This spec covers
**origination**: invoice → correct GL split + schedule creation, plus the edit
lifecycle.

## Scope (decided)

- **In:** origination from `create_invoice`; schedule create; correct GL posting
  (split revenue vs deferred); edit lifecycle (block-if-recognized, else rebuild).
- **Out (future):** automatic/scheduled recognition, recognition-preview UI,
  proration of partial first months. Recognition stays **manual** via the
  existing `run-recognition` endpoint, reused as-is.

## Decisions (locked during brainstorming)

1. **Origination only** — reuse the existing recognition engine unchanged.
2. **One schedule per deferred line** — each deferred invoice line gets its own
   schedule, honoring that product's `recognition_months` and `revenue_account_id`.
3. **Edit policy: block-if-recognized, else rebuild** — if any month has been
   recognized on any of the invoice's schedules, block the edit with `400`;
   otherwise reverse + rebuild from the edited lines (mirrors block-if-paid).
4. **GST immediate, defer net only** — tax point is the invoice date; output GST
   posts to GST Payable (2200) immediately. Only the **net** line amount is
   deferred to Deferred Revenue (2300).

## §1 · Data model — no schema change / no migration

Everything required already exists:

- `Product.is_deferred: bool`, `Product.recognition_months: int = 12`,
  `Product.revenue_account_id` (`models.py`).
- `DeferredRevenueSchedule` (`models.py:714`) with `invoice_id` (a **non-unique**
  FK), `total_amount`, `recognised_amount`, `start_date`, `end_date`,
  `frequency`, `next_recognition_date`, `status`,
  `deferred_revenue_account_id`, `revenue_account_id`.

"One schedule per deferred line" = write N schedule rows sharing the same
`invoice_id`. Reversal keys off `invoice_id` (stable across edits), so **no
`invoice_line_id` column is needed**. **Zero Alembic work.**

## §2 · `services/deferred.py` — new shared module

Pure-logic, no HTTP, unit-testable. Mirrors the existing service layer
(`services/posting.py`, `services/depreciation.py`). Called by **both**
`create_invoice` and `update_invoice` so the two paths cannot diverge (this is
the structural fix for the create/update drift that caused #48).

Interface:

- `plan_deferral(session, tenant_id, lines, fx_rate) -> DeferralPlan`
  - Classifies each line: if its product has `is_deferred=True`, record a
    per-line spec `{net_base, recognition_months, revenue_account_id}`
    (`net_base = money(qty * rate * fx_rate)`, `recognition_months =
    max(1, product.recognition_months)`; skip zero-net lines).
  - Returns `{deferred_lines: [...], deferred_net_base: Σ deferred net}`. The
    **caller derives** `revenue_net_base = subtotal_base − deferred_net_base`
    (not an independent sum) so the split always balances the AR debit
    regardless of per-line rounding. Non-deferred / product-less lines are
    ignored here — they remain normal revenue.
- `resolve_deferred_account(session, tenant_id) -> Account`
  - `get_default_account(session, tenant_id, "default_deferred_revenue_account",
    "2300", "Deferred Revenue", "Liability")`.
- `create_schedules(session, user, invoice, plan) -> list[DeferredRevenueSchedule]`
  - One row per deferred spec (skip zero-net): `total_amount = net_base`,
    `recognised_amount = 0`, `start_date = invoice.issue_date`,
    `end_date = _add_months(issue_date, recognition_months)`,
    `next_recognition_date = issue_date`, `frequency = "monthly"`,
    `status = "active"`, `revenue_account_id = spec.revenue_account_id or default
    4000`, `deferred_revenue_account_id = resolved 2300`.
- `has_any_recognition(session, tenant_id, invoice_id) -> bool`
  - True if any schedule for the invoice has `recognised_amount > 0`.
- `reverse_schedules(session, tenant_id, invoice_id) -> None`
  - Delete the invoice's (un-recognized) schedule rows.

`_add_months` already exists in `routers/deferred_revenue.py`; lift it into a
shared location (e.g. `services/deferred.py` or `services/money.py`) and import
from both.

## §3 · `create_invoice` GL change

Replace the single revenue credit with a split (net, base currency):

```
Dr  Accounts Receivable (1100)   total_base
  Cr Sales Revenue (4xxx)          revenue_net_base    # if > 0
  Cr Deferred Revenue (2300)       deferred_net_base   # if > 0
  Cr GST Payable (2200)            gst_base            # unchanged
```

Implementation: while building lines, call `plan_deferral`. Build the revenue
side from the split instead of crediting `rev_acc` for the whole `subtotal_base`.
After the invoice + main txn exist (so `invoice.id` is set), call
`create_schedules`. The per-line-tax branch keeps its tax accounts; only the
**revenue** credit is split.

## §4 · `update_invoice` (edit) — block-if-recognized, else rebuild

- **Early guard** (alongside `assert_doc_editable`): if
  `has_any_recognition(invoice_id)` →
  `HTTPException(400, "Cannot edit: revenue already recognized for this
  invoice's deferred schedule. Void and reissue instead.")`.
- **Rebuild path:** the deferred credit lives **inside the main invoice JV**,
  which the edit flow already fully reverses — so the 2300 credit unwinds for
  free. We only `reverse_schedules` (delete un-recognized rows) and then re-run
  `create_schedules` from the edited lines. **No separate deferred-reversal JV.**

## §5 · Edge cases & rules

- Mixed invoices (deferred + normal) → split handles it; omit either credit when
  its total is 0.
- `recognition_months` floored at `max(1, …)`; zero-net deferred line → no schedule.
- Schedule amounts stored in **base currency** (recognition posts GL in base; the
  existing engine does not re-apply FX).
- **Telecom CoA caveat:** code 2300 = "Advance from Operator" in the telecom CoA
  (`db.py:268`). The settings-backed `default_deferred_revenue_account` lets such
  a tenant point elsewhere; documented as a known caveat. Deferred products are a
  service/subscription concept, so collision is unlikely in practice.

## §6 · Testing (TDD)

Unit (`tests/test_deferred_service.py`):
- `plan_deferral` classification + split math (all-deferred, mixed, none).
- `resolve_deferred_account` returns 2300 / honors settings override.

Integration (API):
- Single deferred line → main JV credits **2300** (net), not 4000; one schedule
  row with correct window + accounts; GST still to 2200.
- Mixed invoice → revenue/deferred split correct; schedules only for deferred lines.
- Edit pre-recognition → schedules replaced, GL re-split.
- Edit post-recognition → `400`; schedule untouched.
- Existing `run-recognition` recognizes an **originated** schedule end-to-end
  (Dr 2300 / Cr revenue), `recognised_amount` advances.
- **Regression:** a non-deferred invoice posts exactly as before (single revenue
  credit, no schedule).

## §7 · Frontend (minimal — origination scope)

- Verify the Product form exposes `is_deferred` + `recognition_months`; add inputs
  only if missing.
- Optional: a small "Deferred" badge on deferred invoice lines.
- Schedule-list + recognition screens already exist and are reused unchanged.

## Success criteria

A tenant can flag a product deferred, invoice it, and see: (a) the net amount
credited to Deferred Revenue rather than Revenue, with GST posted immediately;
(b) a schedule created per deferred line; (c) the existing recognition engine
move it to revenue over the window; (d) edits rebuild before recognition and are
blocked after. Non-deferred invoices are byte-for-byte unchanged.
