# Comparative Financial Statements (#43 §1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). Backend tests: `cd backend && PYTHONPATH=. uv run pytest <file> -v` (PYTHONPATH=. REQUIRED).

**Goal:** Add Cash-Flow comparative reporting (matching Income Statement / Balance Sheet) and a consistency + print pass so all three statements show aligned Current | Comparative columns.

**Branch:** `feature/issue43-comparative-statements` (off main / v2.2.0). **Spec:** `docs/superpowers/specs/2026-06-06-comparative-statements-design.md`.

---

### Task 1 — Backend: Cash-Flow comparative (mirror Income Statement)

**Files:** `backend/routers/reports.py` (`cash_flow_statement` ~line 825), `backend/tests/test_cashflow_comparative.py`

- [ ] **Step 1 (test):**
```python
# backend/tests/test_cashflow_comparative.py
def test_cashflow_no_compare_is_flat(client, admin_headers):
    r = client.get("/api/reports/cash-flow?start=2026-01-01&end=2026-01-31", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    # back-compat: flat shape (has net_cash_change at top level, not nested current/comparison)
    assert "net_cash_change" in body
    assert "comparison" not in body

def test_cashflow_with_compare_returns_current_and_comparison(client, admin_headers):
    r = client.get(
        "/api/reports/cash-flow?start=2026-02-01&end=2026-02-28"
        "&compare_start=2026-01-01&compare_end=2026-01-31",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "current" in body and "comparison" in body
    for side in (body["current"], body["comparison"]):
        # each side reconciles: net = operating + investing + financing
        assert side["net_cash_change"] == side["operating_cash"] + side["investing_cash"] + side["financing_cash"]
        assert "beginning_balance" in side and "ending_balance" in side
```
(Optionally seed some posted activity in each window for non-trivial numbers — reuse an invoice/payment helper — but the reconciliation + shape assertions hold even at zero.)
- [ ] **Step 2:** run → fail (`comparison` never present; compare params unknown).
- [ ] **Step 3 (refactor + wrap):** in `reports.py`, extract the entire current body of `cash_flow_statement` (from the `accounts = …` fetch through the final `return {…}`) into an inner `def _compute(start, end) -> dict:` that returns the existing dict. Keep the `start`/`end` default resolution OUTSIDE/before. Add params `compare_start: Optional[str] = None, compare_end: Optional[str] = None`. Then:
```python
    current = _compute(start, end)
    if compare_start and compare_end:
        return {"current": current, "comparison": _compute(compare_start, compare_end)}
    return current
```
Mirror `income_statement`'s structure exactly (`reports.py:430-431`). No change to the computation logic.
- [ ] **Step 4:** run → pass. `PYTHONPATH=. uv run pytest tests/test_cashflow_comparative.py -v`.
- [ ] **Step 5:** regression: `PYTHONPATH=. uv run pytest -k "cash or report" -q` then full `PYTHONPATH=. uv run pytest -q` — keep green. If an existing cash-flow test asserted the flat shape, it still passes (no-compare path unchanged).
- [ ] **Step 6:** commit `feat(reports): cash-flow comparative period (current + comparison)`.

---

### Task 2 — Frontend: cashflow comparative + 3-statement consistency/print

**Files:** `frontend/src/app/(dashboard)/cashflow/page.tsx`; light touches to `frontend/src/app/(dashboard)/pl/page.tsx` and `balance/page.tsx` for column alignment only.

- [ ] **Step 1 (read the pattern):** read `frontend/src/app/(dashboard)/pl/page.tsx` fully — note its comparative-period control (state, the compare date inputs / toggle), how it calls `?compare_start=&compare_end=`, and how it renders the `{current, comparison}` shape into two aligned columns. Heed `frontend/AGENTS.md` (Next 16).
- [ ] **Step 2 (cashflow comparative):** in `cashflow/page.tsx`, add the SAME comparative control (mirror `/pl`). Fetch `/api/reports/cash-flow` with the compare params when a comparison period is set; handle BOTH response shapes (flat when no compare; `{current, comparison}` when compare). Render the cash-flow lines with a `Current Period` and (when present) `Comparative Period` money column, in the issue's order: Operating (net income, AR change, AP change → operating cash), Investing (items + total), Financing (items + total), Net increase/(decrease) in cash, Opening cash (`beginning_balance`), Closing cash (`ending_balance`). Right-align money columns; use `ui-*` density classes; reuse the page's existing section/heading styling.
- [ ] **Step 3 (consistency pass):** across `pl`, `balance`, `cashflow` — make the Current/Comparative money columns equal-width and right-aligned consistently (shared Tailwind widths / `ui-td` text-right), and headings/subtotals/totals styled consistently. Change only what's needed for alignment — do NOT re-layout.
- [ ] **Step 4 (print check):** print-preview each of the three with a comparison selected; confirm the two columns render within the page (no squeeze/overflow), figures right-aligned, `PrintHeader` intact. Tweak only the shared print/width classes if alignment is off.
- [ ] **Step 5:** `cd frontend && npm run lint && npm run build` clean — pre-existing lint errors in unrelated files (telecom/commissions, assets/[id], bills/page, invoices/page, payments-received, inventory/performance) are fine; add NONE new in the three statement pages.
- [ ] **Step 6:** commit `feat(reports-ui): cash-flow comparative columns + aligned statement presentation`.

---

### Task 3 — Verification

- [ ] **Step 1:** full backend suite green: `cd backend && PYTHONPATH=. uv run pytest -q`.
- [ ] **Step 2:** `cd frontend && npm run lint && npm run build` clean.
- [ ] **Step 3:** Manual: each statement (P&L, Balance Sheet, Cash Flow) shows aligned Current + Comparative columns when a comparison period is selected, and a clean single column when not; print preview of all three is clean.
- [ ] **Step 4:** commit any final tweaks; PR body: "Closes #43 §1 — Cash-Flow comparative + aligned statement presentation. #43 fully addressed."

---

## Self-Review Notes
- The cash-flow refactor is a pure extraction (no logic change) + a current/comparison wrapper mirroring `income_statement` — low risk; tests assert both shapes + per-period reconciliation.
- Frontend reuses the `/pl` comparative pattern (consistency, no new UX) per the locked decision.
- Execution-time verification: the exact `/pl` comparative control shape (Task 2 Step 1) — read it and mirror, don't invent.
- Out of scope: variance columns, trial-balance comparative, re-layout.
