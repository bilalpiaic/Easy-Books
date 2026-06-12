# B3 — Cash Flow Reconciliation Tie-out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Cash Flow statement provably tie out by adding an explicit `unclassified` reconciling field (`(ending − beginning) − net_cash_change`) and surfacing it on the statement.

**Architecture:** One new field in the shared `_compute` of `/cash-flow` (so single-period and comparison modes both get it); the frontend renders a reconciling row (only when non-zero) plus a tie-out indicator, and shows the reconciled net change (`net_cash_change + unclassified`, which equals `ending − beginning`). No classifier change, no schema change.

**Tech Stack:** FastAPI / SQLModel (backend), Next.js 16 / React 19 / TypeScript (frontend).

**Spec:** `docs/superpowers/specs/2026-06-13-cashflow-reconciliation-tieout-design.md`

**Gate:** Backend `PYTHONPATH=. uv run pytest` green (369 + 3 = 372). Frontend `npm run build` + `npm run lint` at baseline (2 errors / 14 warnings).

---

## File Structure

**Modified:**
- `backend/routers/reports.py` — `_compute` (inside `/cash-flow`) returns `unclassified`.
- `frontend/src/app/(dashboard)/cashflow/page.tsx` — `CashFlowData.unclassified` + reconciling row + tie-out indicator + reconciled net-change figure.

**New:**
- `backend/tests/test_reports_cashflow.py` — 3 tie-out tests.

---

## Task 1: Backend — `unclassified` reconciling field (TDD)

**Files:**
- Test: `backend/tests/test_reports_cashflow.py` (new)
- Modify: `backend/routers/reports.py` (`cash_flow_statement` → inner `_compute`)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_reports_cashflow.py`:

```python
"""B3 — cash-flow reconciliation tie-out.

The statement must always satisfy:
    net_cash_change + unclassified == ending_balance - beginning_balance
where unclassified = (ending - beginning) - net_cash_change surfaces any cash
movement the operating/investing/financing classifier didn't bucket.

Default CoA (`_COA_COMMON`) accounts used:
  1000 Cash in Hand (a cash account)
  4000 Sales Revenue (classifiable → operating, via net income)
  1260 Advances to Vendors (Asset, name has "advance" → excluded from investing,
        not AR/revenue/financing → UNBUCKETED, creates an unclassified gap)
"""

PERIOD = "start=2026-01-01&end=2026-12-31"


def _post_jv(client, headers, date, debit_code, credit_code, amount):
    accts = client.get("/api/accounts?limit=500", headers=headers).json()["items"]
    by_code = {a["code"]: a["id"] for a in accts}
    r = client.post("/api/transactions", headers=headers, json={
        "date": date, "description": "cf-tieout test",
        "entries": [
            {"account_id": by_code[debit_code], "debit": amount, "credit": 0},
            {"account_id": by_code[credit_code], "debit": 0, "credit": amount},
        ],
    })
    assert r.status_code in (200, 201), r.text


def test_cashflow_clean_data_zero_unclassified(client, admin_headers):
    # Cash sale: Dr Cash / Cr Sales Revenue → fully classified (operating).
    _post_jv(client, admin_headers, "2026-03-15", "1000", "4000", 100)
    body = client.get(f"/api/reports/cash-flow?{PERIOD}", headers=admin_headers).json()
    assert "unclassified" in body
    assert abs(float(body["unclassified"])) < 0.005


def test_cashflow_unclassified_gap(client, admin_headers):
    # Dr Cash / Cr Advances to Vendors → cash moves against an unbucketed account.
    _post_jv(client, admin_headers, "2026-03-15", "1000", "1260", 100)
    body = client.get(f"/api/reports/cash-flow?{PERIOD}", headers=admin_headers).json()
    unclassified = float(body["unclassified"])
    assert abs(unclassified) > 0.005  # a real gap was surfaced
    # invariant still holds
    nc = float(body["net_cash_change"])
    beg = float(body["beginning_balance"])
    end = float(body["ending_balance"])
    assert abs((nc + unclassified) - (end - beg)) < 0.005


def test_cashflow_tieout_invariant_with_compare(client, admin_headers):
    # Mixed activity across two periods; invariant must hold on BOTH sides.
    _post_jv(client, admin_headers, "2026-02-10", "1000", "4000", 250)   # classified
    _post_jv(client, admin_headers, "2026-05-10", "1000", "1260", 70)    # unclassified
    body = client.get(
        "/api/reports/cash-flow?start=2026-04-01&end=2026-06-30"
        "&compare_start=2026-01-01&compare_end=2026-03-31",
        headers=admin_headers,
    ).json()
    assert "current" in body and "comparison" in body
    for side in (body["current"], body["comparison"]):
        nc = float(side["net_cash_change"])
        unc = float(side["unclassified"])
        beg = float(side["beginning_balance"])
        end = float(side["ending_balance"])
        assert abs((nc + unc) - (end - beg)) < 0.005
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_reports_cashflow.py -q`
Expected: FAIL — `KeyError: 'unclassified'` (the field doesn't exist yet) / assertion on `"unclassified" in body`.

- [ ] **Step 3: Add the `unclassified` field to `_compute`**

In `backend/routers/reports.py`, inside `cash_flow_statement`'s inner `_compute(s, e)`, the end currently is:

```python
        beginning_balance = sum((balance_at(a, day_before) for a in cash_accounts), ZERO)
        ending_balance = sum((balance_at(a, e) for a in cash_accounts), ZERO)
        net_cash_change = operating_cash + investing_cash + financing_cash

        return {
            "period": {"start": s, "end": e},
            "net_income": net_income,
            "operating_adjustments": {"ar_change": ar_change, "ap_change": ap_change},
            "operating_cash": operating_cash,
            "investing_items": investing_items,
            "investing_cash": investing_cash,
            "financing_items": financing_items,
            "financing_cash": financing_cash,
            "net_cash_change": net_cash_change,
            "beginning_balance": beginning_balance,
            "ending_balance": ending_balance,
        }
```

Add `unclassified` (computed) and include it in the returned dict:

```python
        beginning_balance = sum((balance_at(a, day_before) for a in cash_accounts), ZERO)
        ending_balance = sum((balance_at(a, e) for a in cash_accounts), ZERO)
        net_cash_change = operating_cash + investing_cash + financing_cash
        # Reconciling difference: any actual cash movement the classifier didn't
        # bucket. By construction net_cash_change + unclassified == ending - beginning,
        # so the statement always ties out to real cash.
        unclassified = (ending_balance - beginning_balance) - net_cash_change

        return {
            "period": {"start": s, "end": e},
            "net_income": net_income,
            "operating_adjustments": {"ar_change": ar_change, "ap_change": ap_change},
            "operating_cash": operating_cash,
            "investing_items": investing_items,
            "investing_cash": investing_cash,
            "financing_items": financing_items,
            "financing_cash": financing_cash,
            "net_cash_change": net_cash_change,
            "unclassified": unclassified,
            "beginning_balance": beginning_balance,
            "ending_balance": ending_balance,
        }
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_reports_cashflow.py -q`
Expected: 3 passed.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && PYTHONPATH=. uv run pytest -q`
Expected: all pass (372 = 369 + 3). The existing `test_cashflow_comparative.py` still passes (it only asserts `net_cash_change == operating + investing + financing`, which is unchanged). Report the exact count.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_reports_cashflow.py
git commit -m "feat(reports): cash-flow unclassified reconciling field (B3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Frontend — reconciling row + tie-out indicator

**Files:** Modify `frontend/src/app/(dashboard)/cashflow/page.tsx`

- [ ] **Step 1: Add `unclassified` to the `CashFlowData` interface**

The interface currently is:

```tsx
interface CashFlowData {
  period: { start: string; end: string }
  net_income: number
  operating_adjustments: { ar_change: number; ap_change: number }
  operating_cash: number
  investing_items: { name: string; amount: number }[]
  investing_cash: number
  financing_items: { name: string; amount: number }[]
  financing_cash: number
  net_cash_change: number
  beginning_balance: number
  ending_balance: number
}
```

Add `unclassified: number` after `net_cash_change`:

```tsx
  net_cash_change: number
  unclassified: number
  beginning_balance: number
  ending_balance: number
```

- [ ] **Step 2: Add the reconciling row after the Financing section**

The Financing block ends with this (then the Summary `<div className="bg-[#f6f3ee] ...">` begins):

```tsx
            <Row label="Net Cash from Financing" current={data.financing_cash} comparison={comparison?.financing_cash} showCmp={showCmp} bold fmt={fmt} />
          </div>

          {/* Summary */}
          <div className="bg-[#f6f3ee] p-6 rounded-xl space-y-3">
```

Insert a reconciling block between the Financing `</div>` and the `{/* Summary */}` block — shown only when the gap is material in either column:

```tsx
            <Row label="Net Cash from Financing" current={data.financing_cash} comparison={comparison?.financing_cash} showCmp={showCmp} bold fmt={fmt} />
          </div>

          {/* Reconciling difference (only when classification didn't fully tie out) */}
          {(Math.abs(data.unclassified) >= 0.005 || (!!comparison && Math.abs(comparison.unclassified) >= 0.005)) && (
            <div>
              <Row label="Unclassified / reconciling" current={data.unclassified}
                comparison={comparison?.unclassified ?? null} showCmp={showCmp} indent fmt={fmt} />
            </div>
          )}

          {/* Summary */}
          <div className="bg-[#f6f3ee] p-6 rounded-xl space-y-3">
```

- [ ] **Step 3: Show the reconciled net change + a tie-out indicator**

The "Net Change in Cash" summary line currently is:

```tsx
            <div className="flex justify-between pb-3 border-b border-[#ede9e2]">
              <span className="font-semibold">Net Change in Cash</span>
              <div className="flex gap-8">
                <span className={`font-mono text-right w-36 inline-block font-bold text-lg ${data.net_cash_change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {data.net_cash_change >= 0 ? '+' : ''}{fmt(data.net_cash_change)}
                </span>
                {showCmp && comparison && (
                  <span className={`font-mono text-right w-36 inline-block font-bold text-lg ${(comparison.net_cash_change ?? 0) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                    {(comparison.net_cash_change ?? 0) >= 0 ? '+' : ''}{fmt(comparison.net_cash_change ?? 0)}
                  </span>
                )}
              </div>
            </div>
```

Replace it with the version below. It (a) shows the **reconciled** net change (`net_cash_change + unclassified`, which equals `ending − beginning`), and (b) adds a tie-out indicator next to the label:

```tsx
            <div className="flex justify-between pb-3 border-b border-[#ede9e2]">
              <span className="font-semibold flex items-center gap-2">
                Net Change in Cash
                {Math.abs(data.unclassified) < 0.005 ? (
                  <span className="text-[10px] text-green-600 font-bold uppercase tracking-wide">✓ Reconciled</span>
                ) : (
                  <span className="text-[10px] text-amber-600 font-bold">incl. unclassified</span>
                )}
              </span>
              <div className="flex gap-8">
                <span className={`font-mono text-right w-36 inline-block font-bold text-lg ${(data.net_cash_change + data.unclassified) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {(data.net_cash_change + data.unclassified) >= 0 ? '+' : ''}{fmt(data.net_cash_change + data.unclassified)}
                </span>
                {showCmp && comparison && (
                  <span className={`font-mono text-right w-36 inline-block font-bold text-lg ${(comparison.net_cash_change + comparison.unclassified) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                    {(comparison.net_cash_change + comparison.unclassified) >= 0 ? '+' : ''}{fmt(comparison.net_cash_change + comparison.unclassified)}
                  </span>
                )}
              </div>
            </div>
```

- [ ] **Step 4: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline **2 errors / 14 warnings** (none in `cashflow/page.tsx`). Report exact counts. (The ✓ glyph is fine for `react/no-unescaped-entities`, which only flags quotes/apostrophes.)

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(dashboard)/cashflow/page.tsx"
git commit -m "feat(reports): cash-flow reconciling row + tie-out indicator (B3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Final verification

- [ ] **Step 1: Backend suite**

Run: `cd backend && PYTHONPATH=. uv run pytest -q`
Expected: 372 passed.

- [ ] **Step 2: Frontend build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline (2 errors / 14 warnings).

- [ ] **Step 3: Manual smoke (describe; do not automate)**

With `dev.sh` running, logged in, on `/cashflow`:
- A tenant whose cash moves are fully classifiable shows **"✓ Reconciled"** next to Net Change in Cash and **no** reconciling row; Beginning + Net Change = Ending holds on screen.
- A tenant with an unclassified cash movement (e.g. cash ↔ Advances to Vendors) shows the **"Unclassified / reconciling"** row and the amber **"incl. unclassified"** note; Net Change still equals Ending − Beginning.
- Toggle **Compare** with a prior period → both columns render the reconciling row/indicator from their own `unclassified`.

---

## Self-review (completed at write time)

- **Spec coverage:** §2 invariant + §3 backend field → Task 1 (Step 3 adds `unclassified = (ending − beginning) − net_cash_change`; shared `_compute` ⇒ comparison gets it). §4 frontend (interface field, reconciling row only when `|unclassified| ≥ 0.005`, tie-out ✓/amber indicator, reconciled net-change figure) → Task 2 Steps 1-3. §5 edge cases: clean → row hidden + ✓ (Task 2 Step 2/3 conditions); gap → row shown (Task 1 `test_cashflow_unclassified_gap` + Task 2 Step 2); rounding tolerance 0.005 (Tasks 1-2); comparison per-column (Task 1 `test_..._with_compare` + Task 2 conditions). §6 testing → Task 1 (3 tests) + Task 3. §7 file inventory = Tasks 1-2 exactly.
- **Type/contract consistency:** backend returns `unclassified` (Task 1 Step 3); frontend `CashFlowData.unclassified: number` (Task 2 Step 1) consumed in Steps 2-3 and `comparison?.unclassified`. The reconciled figure `net_cash_change + unclassified` is used consistently for current and comparison. Test account codes (`1000`/`4000`/`1260`) are real `_COA_COMMON` leaves; `1260 Advances to Vendors` is genuinely unbucketed (Asset, name contains "advance" → excluded by `is_fixed_asset`, not AR/revenue/financing).
- **No placeholders:** full verbatim test file, the exact `_compute` return edit, and exact before/after frontend edits.
- **No scope creep:** classifier untouched; no schema change; no new endpoint; `net_cash_change` field semantics unchanged (still the classified sum) — `unclassified` is purely additive.
