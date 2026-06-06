# Design: Comparative Financial Statements (#43 §1)

**Date:** 2026-06-06
**Status:** Approved
**GitHub issue:** #43 (section 1 — the last open piece)

## Overview

Bring the **Cash Flow statement** to parity with the Income Statement and Balance
Sheet by adding comparative-period reporting, and do a light **consistency +
print** pass so all three statements present aligned `Current | Comparative`
columns cleanly on screen and in PDF. Closes the remaining §1 ask of issue #43.

**Branch:** `feature/issue43-comparative-statements`, off `main` (v2.2.0).

### Locked decisions
| Decision | Choice |
|----------|--------|
| Scope | Cash-Flow comparative (backend + frontend) **+** consistency/print pass on all three statements |
| Columns | **Current + Comparative only** — no variance/Δ% column (matches the issue's proposed format) |
| Comparative-period control | **Mirror the existing `/pl` page's** comparative control (do not invent a new UX) |

## Key facts (verified)
- **Income Statement** `/income-statement` already takes `compare_start`/`compare_end`
  and returns `{current, comparison}` (`reports.py:430-431`); the `/pl` page renders it.
- **Balance Sheet** `/balance-sheet` already takes `compare_end` → `{current, comparison}`
  (`reports.py:817-818`); the `/balance` page renders it.
- **Cash Flow** `/cash-flow` (`reports.py:825`) takes only `start`/`end` and returns a
  flat dict — **no comparative**; the `/cashflow` page has zero comparison handling.
  This is the single backend gap.
- The cash-flow computation is entirely a function of `(start, end)`: it computes
  `net_income`, operating adjustments (`ar_change`/`ap_change`), `operating_cash`,
  `investing_items`/`investing_cash`, `financing_items`/`financing_cash`,
  `net_cash_change`, `beginning_balance`, `ending_balance`, and returns them in one
  dict (`reports.py:925-937`). It can be wrapped without logic change.

## Architecture

### Backend — Cash Flow comparative (mirror Income Statement)
Refactor the existing `cash_flow_statement` body into an inner pure function
`_cash_flow_compute(session, user, start, end) -> dict` (the current dict, no logic
change). The endpoint then:
- resolves `start`/`end` defaults as today;
- adds `compare_start: Optional[str] = None`, `compare_end: Optional[str] = None`;
- if BOTH compare params are present → `return {"current": _compute(start,end), "comparison": _compute(compare_start, compare_end)}`;
- otherwise → `return _compute(start, end)` (unchanged flat shape — back-compat).

This is the exact contract `/income-statement` uses, so the frontend pattern is reusable. No change to BS or P&L endpoints.

### Frontend
- **`/cashflow` page:** add the SAME comparative-period control the `/pl` page
  already uses (read `pl/page.tsx` and mirror its compare state + inputs + the
  `{current, comparison}` fetch handling). Render the cash-flow lines in the
  issue's proposed format with a `Current Period` and `Comparative Period` column:
  Operating activities (net income + AR/AP adjustments → operating cash),
  Investing activities (items + total), Financing activities (items + total),
  Net increase/(decrease) in cash, Opening (beginning) cash, Closing (ending) cash.
  When no comparison is selected, render the single current column as today.
- **Consistency + print pass — `/pl`, `/balance`, `/cashflow`:**
  - Comparative columns aligned and equal-width (shared `ui-*` / consistent
    `text-right` money columns); headings/subtotals/totals styled consistently
    across the three.
  - Verify the two-column comparative renders cleanly in print/PDF via the existing
    `PrintHeader` + `@media print` styling (no column overflow/squeeze; right-aligned
    figures; repeating headers). Adjust shared classes only where alignment is off —
    not a re-layout.

## Components / boundaries
- `reports.py`: extract `_cash_flow_compute(...)`; endpoint becomes a thin
  current/comparison wrapper (mirrors `income_statement`).
- `frontend/.../cashflow/page.tsx`: comparative control + two-column render
  (pattern copied from `pl/page.tsx`).
- Light shared-styling touches on the three statement pages for column alignment +
  print; no new shared component unless trivially warranted.

## Testing
- **Backend:** `/cash-flow?compare_start=&compare_end=` returns `{current, comparison}`
  with each side computed correctly (seed activity in two windows; assert
  `operating_cash`, `investing_cash`, `financing_cash`, `net_cash_change`,
  `beginning_balance`, `ending_balance` per side; assert
  `net_cash_change == operating+investing+financing` each period). A no-compare call
  returns the existing flat shape (back-compat) — keep any existing cash-flow test green.
- **Frontend:** build + lint clean; manual check that all three statements render
  aligned Current/Comparative columns on screen and in print/PDF, and that selecting
  no comparison shows a clean single column.

## Out of scope
Variance/Δ and Δ% columns; trial-balance comparative; statement re-architecture
beyond column alignment + print polish.
