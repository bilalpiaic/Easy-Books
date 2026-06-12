# B3 — Cash Flow reconciliation tie-out · Design

**Date:** 2026-06-13
**Backlog item:** ROADMAP "Forward backlog" B3. **Effort:** S.

## §1 · Goal & scope

Make the Cash Flow statement **provably tie out**. The statement already renders the full
indirect-method statement (operating / investing / financing, beginning & ending cash) **with
comparison mode** (both backend `/cash-flow` and `cashflow/page.tsx`). The one gap: the
activity sections are derived by classification (account name/code matching), and nothing checks
that the classified total equals the actual cash movement — so the statement can silently fail to
reconcile. We add an explicit **reconciling difference** so it always ties, and surface it as a
data-quality signal.

**Locked decision (brainstorming 2026-06-13, design approved):** reconciliation tie-out **only** —
no classifier rewrite, no schema change, no new endpoint.

**Out of scope (YAGNI):** changing how operating/investing/financing are classified; per-account
drill-down; cash-flow hierarchical tree.

## §2 · The invariant

```
net_cash_change = operating_cash + investing_cash + financing_cash      (classified total, unchanged)
actual_cash_change = ending_balance − beginning_balance                 (real movement of cash accounts)
unclassified = actual_cash_change − net_cash_change                     (the reconciling gap, NEW)
```

By construction `net_cash_change + unclassified == ending_balance − beginning_balance`, so the
statement reconciles to actual cash by definition. `unclassified ≈ 0` ⇒ classification covered
everything; non-zero ⇒ exactly that much cash movement wasn't bucketed.

## §3 · Backend (`backend/routers/reports.py`, `/cash-flow`)

In the shared inner `_compute(s, e)` function, after `net_cash_change`, `beginning_balance`, and
`ending_balance` are computed, add one field to the returned dict:

```python
unclassified = (ending_balance - beginning_balance) - net_cash_change
...
return {
    ...                                   # all existing fields unchanged
    "unclassified": unclassified,
}
```

Because `_compute` is shared by single-period and comparison modes, both responses carry
`unclassified` automatically. No classification logic changes; no other field changes.

## §4 · Frontend (`frontend/src/app/(dashboard)/cashflow/page.tsx`)

- Add `unclassified: number` to the `CashFlowData` interface.
- Render a **"Unclassified / reconciling"** `Row` immediately after the Financing section, shown
  **only when `Math.abs(unclassified) >= 0.005`** (half-cent tolerance) — clean statements stay
  clean. The existing `Row` component already supports a `comparison` value, so the comparison
  column renders it too (`comparison?.unclassified`).
- Near the **"Net change in cash"** total, show a tie-out indicator:
  - within tolerance → a small green **"✓ Reconciled"**;
  - otherwise → a subtle amber note (e.g. "Includes unclassified cash movement").
- The "Net change in cash" figure shown is `net_cash_change + unclassified` (≡ `ending −
  beginning`), so beginning + net change = ending always holds on screen. (If the page currently
  prints `net_cash_change` alone for that line, switch it to the reconciled sum.)

No other page changes; date range, compare toggle, and the operating/investing/financing sections
are untouched.

## §5 · Edge cases

| Case | Behavior |
|------|----------|
| Classification complete | `unclassified ≈ 0` → reconciling row hidden, "✓ Reconciled" shown. |
| Unbucketed cash movement | `unclassified ≠ 0` → reconciling row visible; net change still ties to ending − beginning. |
| Rounding (sub-cent) | `abs(unclassified) < 0.005` treated as reconciled (tolerance). |
| Comparison mode | reconciling row + indicator computed per column from each period's `unclassified`. |
| Empty period (no cash movement) | all zeros; reconciled. |

## §6 · Testing

**Backend** — new `backend/tests/test_reports_cashflow.py` (run with `PYTHONPATH=. uv run pytest`):
1. **Tie-out invariant:** for a seeded tenant with mixed transactions,
   `net_cash_change + unclassified == ending_balance − beginning_balance` (exact, via `Decimal`).
2. **Clean data:** a tenant whose cash moves only via classifiable accounts (e.g. cash↔revenue,
   cash↔fixed-asset) → `abs(unclassified) < 0.005`.
3. **Unclassified gap:** a cash movement against an account in no bucket → `unclassified != 0`
   while invariant (1) still holds.

Tests follow the repo's in-memory-engine fixture pattern (`tests/conftest.py` `client` /
`admin_headers`, or a self-contained engine fixture). Money compared with `Decimal` (the
endpoint returns non-quantized values).

**Frontend** — no JS unit runner: `npm run build` + `npm run lint` at baseline (2 errors / 14
warnings). Manual smoke: a tying tenant shows "✓ Reconciled" with no extra row; an unbalanced one
shows the reconciling row and the amber note; comparison mode renders both columns.

## §7 · File inventory

**Modified:**
- `backend/routers/reports.py` — `_compute` returns `unclassified`.
- `frontend/src/app/(dashboard)/cashflow/page.tsx` — interface field + reconciling row + tie-out indicator.

**New:**
- `backend/tests/test_reports_cashflow.py` — 3 tests.

**Unchanged:** classifier logic; comparison mechanism; schema; all other endpoints/pages.

## §8 · Implementation order (for the plan)

1. Backend (TDD): write `test_reports_cashflow.py` (3 tests, fail) → add `unclassified` to `_compute`
   → tests pass → full suite green (372).
2. Frontend: `CashFlowData.unclassified` + reconciling row + tie-out indicator; build + lint baseline.
3. Verify: full backend suite + frontend build/lint; manual smoke.
