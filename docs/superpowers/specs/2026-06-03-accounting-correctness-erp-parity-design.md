# Accounting Correctness & ERP Parity — Design

**Date:** 2026-06-03
**Branch:** `feature/accounting-correctness-erp-parity`
**Status:** Approved (design); pending implementation plan

## Summary

Four accounting-focused work items delivered as **one phased effort** under a shared
"accounting correctness & ERP parity" theme. Two are real code gaps, one is a
functional gap, and the documentation deliverable is genuinely new:

1. **IAS 21 FX revaluation** — extract the inline endpoint into a dedicated, testable
   service; extend to AP; fix the re-run double-count via auto-reversing entries.
2. **IAS 2 stock adjustments** — new router + service functions for inventory
   loss / gain / NRV write-down with FIFO/WAvg-aware layer accounting and GL mapping.
3. **Asset disposal GL** — `dispose_asset` currently posts nothing; add full IAS 16
   derecognition with proceeds, NBV write-off, and gain/loss.
4. **Documentation** — `docs/ACCOUNTING_RULES.md`: ledger-entry matrices + Odoo 17 /
   QuickBooks Online parity mapping.

## Grounding (current state, verified)

| Area | Reality at design time |
|------|------------------------|
| FX revaluation | Lives inline at `routers/reports.py:883` (`POST /api/reports/fx-revaluation`). **AR-only.** Posts the full `closing − booked` diff **every run** against the original booked rate → **double-counts on re-run**. Uses account `4901` + `services/fx.py:rate_to_base()`. |
| Sales return | `routers/credit_notes.py` **already** posts value reversal (Dr Revenue + Dr GST / Cr AR) **and** a restock sub-JV via `reverse_consumption` (Dr Inventory `1200` / Cr COGS `5010` at original layer cost). → **documentation only**, no code change. |
| Asset disposal | `routers/assets.py:143` flips `is_disposed=True` + writes an audit row. **No GL posting at all.** `FixedAsset` carries `asset_account_id`, `accum_depr_account_id`, `accumulated_depreciation`, `book_value`. |
| Inventory layers | `services/inventory.py` has `consume_stock`, `return_to_vendor` (FIFO depletion by `source_doc`), `record_purchase` (WAvg). `Tenant.cost_method` ∈ {wavg, fifo}. `InventoryError` raised before mutation. |
| Accounts | `4901` Unrealised FX Gain/Loss (Revenue), `4900` Other Income, `5900` Other Expenses, `5040` Inventory Adjustments, `5010` COGS, `1200` Inventory — all present in `db.py` CoA templates. |

## Key decisions (from brainstorming)

- **Deliverable:** build **and** document (both).
- **FX re-run strategy:** auto-reverse next period. Reversal dated the **first day of the
  next calendar month**. Same-date re-run voids the prior pair and re-posts (idempotent + period-aware).
- **FX scope:** revalue **both AR (Invoice) and AP (Bill)**.
- **Stock adjustment reasons:** full IAS 2 — quantity **loss**, quantity **gain**, NRV **write-down**.
- **Stock cost basis:** follows tenant `cost_method` (WAvg default, FIFO when set) — consistent with `consume_stock`.
- **Asset disposal:** full IAS 16 — proceeds + receiving cash/bank account + disposal date;
  separate gain (`4900`) / loss (`5900`).
- **Stock adjustments get a frontend page** under the Inventory sidebar group.

---

## Component A — FX Revaluation engine

**New module:** `backend/services/fx_revaluation.py` (pure logic; no FastAPI imports).

```python
@dataclass
class RevaluationResult:
    revaluation_txn_id: int | None
    reversal_txn_id: int | None
    entries_count: int
    net_gain_loss: Decimal          # + gain, − loss (base currency)
    message: str

def revalue_open_positions(
    session: Session, *, tenant_id: int, user, revaluation_date: str,
) -> RevaluationResult: ...
```

**Selection:** open `Invoice` and `Bill` rows where `currency != tenant.base_currency`,
`transaction_id is not None`, status in the open set
(invoices: draft/posted/partial/sent; bills: posted/partial), `outstanding_doc > 0`
(`outstanding_doc = total − Σ allocations`).

**Per-document calculation:**
```
booked_base  = outstanding_doc × booked_rate          # exchange_rate snapshot on the doc
closing_base = outstanding_doc × rate_to_base(currency, revaluation_date)
diff         = closing_base − booked_base
skip if |diff| < 0.01 or no rate available for that date
```

**GL postings (revaluation entry, dated `revaluation_date`):**

| Position | Condition | Debit | Credit |
|----------|-----------|-------|--------|
| AR (Invoice) | gain (diff > 0) | AR account | 4901 |
| AR (Invoice) | loss (diff < 0) | 4901 | AR account |
| AP (Bill) | loss (owe more, diff > 0) | 4901 | AP account |
| AP (Bill) | gain (diff < 0) | AP account | 4901 |

AR account = `inv.ar_account_id` else default `1100`. AP account = `bill.ap_account_id`
else default `2000`. (Verify exact field names against `models.py` during implementation;
fall back to code lookup.)

**Auto-reverse:** after posting the revaluation transaction, post a second transaction with
**debits and credits swapped**, dated `first_day_of_next_month(revaluation_date)`.

**Same-date idempotency:** new table
`FxRevaluationRun(id, tenant_id, revaluation_date, txn_id, reversal_txn_id, created_at)`.
Before posting, look up any prior run for `(tenant_id, revaluation_date)`; if found, void
(delete the transactions + their journal entries, or reverse) both linked transactions and
the run row, then proceed. → New table; Alembic migration with `bind.dialect.has_table(...)` guard.

**Endpoint:** `routers/reports.py` `POST /api/reports/fx-revaluation` becomes a thin wrapper
calling `revalue_open_positions(...)`. Path/signature stable; response gains `reversal_txn_id`
and AP coverage.

---

## Component B — Stock Adjustments (IAS 2)

**New model:** `StockAdjustment` header
```
id, tenant_id, product_id, reason ('loss'|'gain'|'write_down'),
qty (>0 for loss/gain; 0 for write_down), unit_cost (gain) | nrv_unit_cost (write_down),
cost_amount (signed GL value, computed), note, adjustment_date,
movement_id (-> StockMovement), transaction_id (-> Transaction), created_at
```
CHECK constraint on `reason`. Movements logged via existing `StockMovement`
(direction `ADJUSTMENT`) + `InventoryLayer`.

**`inventory.py` additions** (factor the existing layer-depletion loop out of
`consume_stock`/`return_to_vendor` into a shared helper):
- `adjust_loss(session, *, tenant_id, product_id, qty, block_negative) -> Decimal` —
  deplete remaining layers by `cost_method`, decrement `stock_qty`, return total cost.
  Raises `InventoryError` before mutation if `block_negative` and insufficient on hand.
- `adjust_gain(session, *, tenant_id, product_id, qty, unit_cost) -> Decimal` —
  add a new `InventoryLayer`, increment `stock_qty`, recompute `avg_cost`, return `qty×unit_cost`.
- `write_down(session, *, tenant_id, product_id, nrv_unit_cost) -> Decimal` —
  for each remaining layer with `unit_cost > nrv_unit_cost`, lower it to `nrv_unit_cost`;
  recompute `avg_cost`; return total write-down amount. Qty unchanged.

**GL postings** (product inventory account = product's mapped inventory account else `1200`):

| Reason | Debit | Credit |
|--------|-------|--------|
| loss | 5040 Inventory Adjustments | 1200 Inventory |
| write_down | 5040 Inventory Adjustments | 1200 Inventory |
| gain | 1200 Inventory | 5040 Inventory Adjustments |

`block_negative_stock` setting honored on `loss`.

**Endpoints:** `POST /api/stock-adjustments`, `GET /api/stock-adjustments` (tenant-filtered).
New table → guarded migration.

**Frontend:** `frontend/src/app/(dashboard)/inventory/adjustments/page.tsx` — list +
"New adjustment" form (product picker, reason, qty/cost, note). Added to the **Inventory**
sidebar group in `Sidebar.tsx`.

---

## Component C — Asset Disposal GL (IAS 16.71)

**Extend `dispose_asset`** request body:
- `proceeds: Decimal = 0` (0 = scrap/write-off)
- `proceeds_account_id: int | None` — required when `proceeds > 0` (cash/bank)
- `disposal_date: str`

**Postings:**
```
Dr  proceeds account          proceeds            (only if proceeds > 0)
Dr  accumulated-depr account  accumulated_depreciation
Cr  asset-cost account        acquisition_cost
    balancing line:
      gain (proceeds + accum_depr > cost)  -> Cr 4900   amount = proceeds − NBV
      loss (otherwise)                     -> Dr 5900   amount = NBV − proceeds
NBV = acquisition_cost − accumulated_depreciation
```
Set `is_disposed=True`, `book_value=0`. Store disposal txn link.

**Schema:** add `disposal_date`, `disposal_proceeds`, `disposal_transaction_id` to
`FixedAsset` → guarded migration.

**Frontend:** disposal modal gains proceeds + receiving-account + date fields.

**Non-goal (explicit):** depreciate-to-disposal-date catch-up. Gain/loss is computed off the
asset's current `accumulated_depreciation`. Documented as a future enhancement.

---

## Component D — Documentation: `docs/ACCOUNTING_RULES.md`

**Ledger-entry matrices** (Dr/Cr tables, one per transaction type):
- Sales Return (documents existing `credit_notes.py` behavior: value reversal + restock at original cost)
- Asset Disposal (NBV derecognition + gain/loss)
- FX Revaluation (AR & AP, gain & loss, + the auto-reversal)
- Stock Adjustments (loss / gain / write-down)

**ERP parity mapping** — model-by-model table:

| Easy-Books | Odoo 17 | QuickBooks Online |
|------------|---------|-------------------|
| `Transaction` (JV header) | `account.move` | `JournalEntry` |
| `JournalEntry` (line, debit/credit) | `account.move.line` | `JournalEntry.Line` |
| `PaymentAllocation` | `account.partial.reconcile` | `LinkedTxn` |
| `AnalyticAccount` | `account.analytic.account` | `Class` |
| subledger (AR/AP open items) | partner ledger / aged partner balance | A/R & A/P aging |
| `ExchangeRate` + reval | `res.currency.rate` + unrealized-gain wizard | Home-currency adjustment / exchange-gain-loss |

Cross-link from `BLUEPRINT.md` §11; update `CLAUDE.md` router table and `README.md`.

---

## Component E — Demo seed + tests

**Seed (`scripts/seed_demo.py`):** add a few stock adjustments (loss + write-down) and one
asset disposal; ensure at least one foreign-currency **open** invoice and bill exist
(trader/manufacturing) so FX revaluation has positions to act on.

**Tests:**
- FX: AR gain, AR loss, AP gain, AP loss; auto-reverse entry exists & is dated next-month-day-1;
  **re-run same date does not double-count** (net effect equals single run); no-rate skip; balance holds.
- Stock adjustments: loss (FIFO and WAvg), gain, write-down; GL balances; `block_negative` raises;
  layer/`stock_qty`/`avg_cost` correctness.
- Disposal: gain, loss, scrap (proceeds=0); GL balances; `is_disposed`/`book_value` set;
  tenant isolation.

---

## Implementation phasing (one plan, 5 phases)

1. **FX engine** — `fx_revaluation.py`, AP coverage, auto-reverse, `FxRevaluationRun` table + migration, endpoint refactor, tests.
2. **Stock adjustments** — model + migration, `inventory.py` functions, router, frontend page + sidebar, tests.
3. **Asset disposal** — `FixedAsset` columns + migration, endpoint posting, frontend modal, tests.
4. **Documentation** — `ACCOUNTING_RULES.md` (matrices + parity), BLUEPRINT/CLAUDE/README updates.
5. **Demo seed + green suite** — seed additions, full `uv run pytest` green.

## Out of scope

- Realized FX gain/loss on settlement (separate from unrealized revaluation).
- Multi-currency *bank* revaluation (only AR/AP monetary items this round).
- Depreciate-to-disposal-date catch-up.
- Inventory revaluation beyond NRV write-down (e.g. standard-cost variances).
