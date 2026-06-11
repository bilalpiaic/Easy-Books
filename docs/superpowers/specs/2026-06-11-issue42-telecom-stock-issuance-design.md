# Design — #42 Telecom Stock & Issuance Table

**Date:** 2026-06-11
**Issue:** #42 (Telecom Franchise dashboard — Stock & Issuance report)
**Effort:** M

## Goal

Add a per-RSO **Stock & Issuance** report to the Telecom Franchise dashboard: one row per RSO agent showing stock/load/SIM issuance, bank deposits, and two closing balances, with a franchise-level totals footer that also carries FCA figures (which are not attributable per-RSO).

## Business workflow context (the "why")

The telecom-franchise load/stock distribution chain (confirmed by the franchise owner):
1. **Bank → Operator's Tracker** — franchise funds a prepaid float (Tracker) with the operator.
2. **Tracker → MSR** — recharge (e-Load) into the franchise's Master Sales Rep float; physical stock (scratch cards, SIMs/HLR, bundles) issued to the franchise.
3. **MSR → RSO/DSO/WIC** — Load **and** Stock issued down to the field-channel agents. ← **this table starts here**
4. **RSO/DSO/WIC → Bank** — agents deposit cash to clear their Load & Stock outstandings. ← `bank_deposits`
5. **Stock → FCA campaign** — some stock is consumed by First-Call-Activation campaigns; this is the franchise's **terminal cost**. ← franchise-level `fca_hits`

This report covers the **MSR→channel→bank** segment (steps 3–4) with FCA (step 5) as the franchise's closing cost. The two closings express the unsettled positions at the channel tier: `HLR+Load−Deposits` = monetary receivable still owed by channels; `SIM Issued−FCA` = SIM units issued but not yet consumed by activation campaigns. The channel tier (RSO/DSO/WIC) is modelled entirely as `tc_rso_agent` rows (no separate DSO/WIC tables), so one row per `RsoAgent` covers all three channel types.

## Locked decisions (from brainstorming)

1. **Row granularity = per RSO agent** (`tc_rso_agent`). Stock/load/deposit data attributes cleanly per RSO.
2. **FCA handling = franchise total in footer.** `tc_fca_event` has no `rso_id` (only `sim_id` + `source_channel`, and rolls up to operator via `kpi_target`). So per-RSO `fca_hits` and `closing_sim_fca` are `null`; the **totals footer** shows the franchise-wide FCA count and the franchise `SIM Issued − FCA`.
3. **Column → source mapping** (disjoint issuance categories) confirmed — see table below.
4. **Helper columns kept visible:** `SIM Issued (qty)` and `Bank Deposits` are shown as columns (inputs to the two closings) for auditability. Final table = 10 columns.

## Architecture

### Unit 1 — Backend endpoint `GET /api/telecom/reports/stock-issuance`
New handler in `backend/routers/telecom_reports.py` (router prefix is already `/api/telecom/reports`). Query params: `start: Optional[str] = None`, `end: Optional[str] = None` (ISO `YYYY-MM-DD`; both optional; default = all-time, consistent with `/rso-ledger`). Tenant-scoped via `user.tenant_id`.

**Per-RSO aggregation** — loop **all** `RsoAgent` rows for the tenant (no `is_active` filter — matches `/rso-ledger`, so an RSO later deactivated still shows its historical activity); for each `r`, compute (each Σ is `func.coalesce(func.sum(...), 0)`, period-filtered on the noted date column when `start`/`end` supplied):

| Output field | Source query |
|---|---|
| `stock_issuance` | Σ `RsoStockIssue.face_value` where `rso_id=r.id`, `stock_type='scratch_card'`, `issue_date` in range |
| `load_issued` | Σ `LoadTransfer.amount` where `to_type='rso'`, `to_ref_id=r.id`, `transfer_date` in range |
| `hlr_issued` | Σ `RsoStockIssue.face_value` where `rso_id=r.id`, `stock_type IN ('sim_batch','imsi')`, `issue_date` in range |
| `sim_issued_qty` | Σ `RsoStockIssue.qty_issued` where `rso_id=r.id`, `stock_type IN ('sim_batch','imsi')`, `issue_date` in range |
| `other_stock` | Σ `RsoStockIssue.face_value` where `rso_id=r.id`, `stock_type='bundle'`, `issue_date` in range |
| `bank_deposits` | Σ `RsoDailyCollection.total_deposited` where `rso_id=r.id`, `collection_date` in range |
| `closing_hlr_load_dep` | `hlr_issued + load_issued − bank_deposits` (computed) |
| `fca_hits` | `null` (not attributable per-RSO) |
| `closing_sim_fca` | `null` (not attributable per-RSO) |

Each item also carries `rso_id`, `name`, `territory`.

**Totals footer** (`totals` object): sum every numeric per-RSO field across all RSOs, **plus**:
- `fca_hits` = `count(FcaEvent)` for the tenant with `event_date` in range (franchise-wide; no source_channel filter).
- `closing_sim_fca` = `Σ sim_issued_qty (all RSOs) − fca_hits`.
- `closing_hlr_load_dep` = `Σ hlr_issued + Σ load_issued − Σ bank_deposits`.

**Serialization:** money fields as strings via `str(D(value))` (matches existing telecom reports, e.g. `/rso-ledger`); `sim_issued_qty` and `fca_hits` as integers. Response shape:
```json
{
  "items": [
    { "rso_id": 1, "name": "Ahmed", "territory": "North",
      "stock_issuance": "12000.00", "load_issued": "8000.00",
      "hlr_issued": "5000.00", "sim_issued_qty": 50, "other_stock": "1200.00",
      "bank_deposits": "9800.00", "closing_hlr_load_dep": "3200.00",
      "fca_hits": null, "closing_sim_fca": null }
  ],
  "totals": {
    "stock_issuance": "21500.00", "load_issued": "14200.00",
    "hlr_issued": "8000.00", "sim_issued_qty": 80, "other_stock": "1200.00",
    "bank_deposits": "16000.00", "closing_hlr_load_dep": "6200.00",
    "fca_hits": 62, "closing_sim_fca": 18 },
  "period": { "start": null, "end": null }
}
```

Period filter is applied as `Model.<date_col> >= start` and/or `<= end` only when the param is provided (string comparison works for ISO `YYYY-MM-DD`, matching how other handlers treat these `str` date columns).

### Unit 2 — Frontend: Stock & Issuance section on `telecom/page.tsx`
Add a new card below the existing telecom dashboard sections. Contents:
- **Date range filter:** two `<input type="date">` (start, end) + the values drive a refetch. Default empty (all-time). Mirror existing telecom page fetch style (`apiFetch`, `useFmt`).
- **Table** (landscape, horizontally scrollable like other dense telecom tables), 10 columns:
  `Name · Stock Issuance · Load Issued · HLR Issued · Other Stock · SIM Issued · Bank Deposits · FCA Hits · Closing (SIM−FCA) · Closing (HLR+Load−Dep)`.
  - Money columns rendered with `fmt(...)`; `SIM Issued` and `FCA Hits` as plain integers.
  - Per-RSO `FCA Hits` and `Closing (SIM−FCA)` cells render `—` (since `null`).
  - A bold **TOTAL** footer row renders `totals` — including the franchise `fca_hits` and `closing_sim_fca`.
- Empty state: "No RSO activity for this period."

TypeScript interfaces mirror the response (`StockIssuanceRow`, `StockIssuanceTotals`). The section is only meaningful for telecom-franchise tenants; it lives on the telecom page which is already gated to that model.

## Data flow
`start/end` → endpoint → (loop RSOs → per-RSO aggregate queries) + (FcaEvent count + cross-RSO sums) → `{ items, totals, period }` → table rows + TOTAL footer. Pure read; **no GL writes**.

## Error / edge handling
- **No RSOs / no data:** `items: []`, `totals` all zero, `fca_hits: 0`. Frontend shows the empty state.
- **Only one of start/end given:** apply the open-ended bound (≥ start, or ≤ end).
- **Tenant isolation:** every query filters `tenant_id == user.tenant_id` (RSO loop, all aggregates, and the FcaEvent count).
- **Negative closing values** are legitimate (e.g. deposits exceed issuance) and shown as-is.

## Testing (TDD)
Backend test `backend/tests/test_telecom_stock_issuance.py` (follows existing telecom report test patterns):
1. Seed a telecom tenant, 2 RSO agents, and for each: `RsoStockIssue` rows across `scratch_card`/`sim_batch`/`bundle`, `LoadTransfer` (msr→rso), `RsoDailyCollection`. Seed N `FcaEvent` rows.
2. Assert per-RSO `stock_issuance`/`load_issued`/`hlr_issued`/`sim_issued_qty`/`other_stock`/`bank_deposits` equal the seeded sums, and `closing_hlr_load_dep = hlr + load − deposits`.
3. Assert per-RSO `fca_hits` and `closing_sim_fca` are `null`.
4. Assert `totals` column sums, `totals.fca_hits == N`, `totals.closing_sim_fca == Σsim_qty − N`.
5. Assert period filtering: an out-of-range issue/transfer/collection/FCA is excluded when `start`/`end` narrow the window.
6. Assert tenant isolation: a second tenant's RSO/stock/FCA never appears.

Frontend has no unit-test runner; gate is `cd frontend && npm run build` + `npm run lint` (changed files clean).

## Out of scope (YAGNI)
- Per-RSO FCA attribution (would need an `rso_id` on `tc_fca_event` + capture-side changes) — deferred; footer total suffices now.
- CSV/print export of this table — can be added later if requested.
- Drill-down from a row into the RSO ledger — the existing `/rso-ledger` already covers per-RSO detail.
