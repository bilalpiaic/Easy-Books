# Purchase/Store Module — Phase 3+4: Store Issue + Vendor Performance (#137)

**Date:** 2026-07-10
**Status:** Approved design
**Prior art:** Phase 1 (merged, PR #139) — Demand/Comparative/PO. Phase 2 (merged `864fbcd`) — Gate Inward. Phase 2b (merged `1e7106a`) — Gate Outward. Specs: `2026-07-03-purchase-demand-comparative-design.md`, `2026-07-05-purchase-store-phase2-design.md`, `2026-07-06-purchase-store-phase2b-gate-outward-design.md`.

## Scope

Combined cycle (user decision: Phase 4's seeder needs Phase 3's data anyway,
so no value in a separate spec/plan/branch for it). Closes out the original
#137 phasing:

- **Phase 3** — `StoreIssue`: the last leg of the procure-to-pay chain,
  general departmental/cost-center consumption out of the store, with real
  GL posting and stock relief. Plus the `/purchases` hub page.
- **Phase 4** — vendor performance report, demo-seeder extension, docs delta.

## Key design decisions (locked)

1. **`StoreIssue` stays separate from `ProductionOrder`.** Manufacturing
   already has its own raw-material consumption path
   (`production_orders.py`, its own `consume_stock` calls). `StoreIssue` is
   the "everything else" — issuing stock to a department/cost-center/project
   that is *not* a production order. No `production_order_id` field; no
   shared code path. Avoids two competing writers into the same
   `StockMovement` ledger for what would otherwise be the same physical
   event modeled twice.

2. **Debit account is user-picked, not hardcoded.** Unlike scrap's Gate
   Outward (`5901 Scrap Disposal Expense` hardcoded via
   `get_or_create_account`), Store Issue's whole point is departmental
   attribution — the consuming department could hit Production Consumables,
   Office Supplies, Maintenance Expense, etc. The form has a standard
   account picker (same component Journal/Payment forms already use)
   filtered to Expense-type accounts; `analytic_account_id` tags the
   cost-center dimension as a second, independent axis.

3. **No draft→approve gate.** Scrap requires dual-control because it's a
   disposal/revenue event with no other originating document. Store Issue
   is routine day-to-day consumption — `block_negative_stock` (existing
   tenant setting) is the control that matters here, not a second
   approver. Create posts GL and relieves stock atomically in the same
   request/transaction. No `status` field on the model — there is nothing
   to transition.

4. **"Rejection rate" (from the original issue's Phase 4 wish list) is not
   directly trackable.** Neither `GateInwardLine` nor `BillLine` (the two
   models that actually feed the existing 3-way-match, `purchase_reports.py:53-90`
   — the *originally-filed issue's own text incorrectly named `GRNLine`
   here; `GoodsReceiptNote`/`GRNLine` is an unrelated Manufacturing model
   for customer-custodial tolling material, not part of the PO chain at
   all, see decision #6 below) carry an accepted/rejected qty split — only
   a single received/billed qty. The vendor performance report
   approximates rejection rate by reusing the existing 3-way-match
   variance calculation (PO ordered qty vs Σ GateInward received qty)
   rather than inventing a new field this phase doesn't otherwise need.

5. **Stock Tie-out is product-level, not per-location.** `consume_stock`
   (`services/inventory.py:168`) has no `location_id` parameter — it drains
   whichever `InventoryLayer` rows exist oldest-first and tags the
   resulting `StockMovement` with *whatever location that layer happens to
   belong to*, not a location the caller chooses. A Store Issue against
   `from_location_id=A` could, in principle, drain a layer actually
   received at location B — there is no enforced per-location consumption
   fidelity anywhere in the codebase today (Gate Outward's scrap flow has
   the identical property). Building a true per-location tie-out report on
   top of that would silently misreport. `from_location_id` on `StoreIssue`
   stays as a real, validated field (descriptive/audit value — which
   store's staff issued this — and useful for the Issue Register), but
   Stock Tie-out is scoped down to per-product, tenant-wide: Σ Bill-received
   qty − Σ Store-Issue-out qty vs. `Product.stock_qty`. Adding real
   location-aware consumption is a `consume_stock` change with a much
   wider blast radius (every existing call site) and is out of scope here.

6. **`GoodsReceiptNote`/`GRNLine` is not part of the PO chain.** The
   original issue text (and the `MODULE_REGISTRY` description quoted in
   its Motivation section) assumed GRN was the vendor-receipt step —
   it isn't. In this codebase, `GoodsReceiptNote` (`models.py:663`) is a
   Manufacturing-only model for **customer-supplied material held in
   custody** (`customer_id`, `customer_custodial`-type `StockLocation`,
   an off-balance-sheet memo JE) — unrelated to `PurchaseOrder`. The real
   receipt event for a purchased-from-vendor PO is **Bill creation**:
   `record_purchase` (`services/inventory.py`) runs when a Bill is
   created/converted from the PO, tagging the resulting `StockMovement`
   rows `source_doc_type="bill"` (`routers/bills.py:301,530`). The
   existing 3-way-match report already reflects this correctly (PO vs
   `gi_coverage` vs `po.bill_id`/`BillLine` — no `GoodsReceiptNote`
   anywhere in it, `purchase_reports.py:53-90`). Stock Tie-out and the
   hub page's bands are written against this reality, not the original
   issue text's incorrect assumption.

## Data model (new Alembic migration `0032_store_issue.py`, `has_table` guard)

### `StoreIssue`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `tenant_id` | FK tenant, indexed | |
| `number` | str, indexed | `SI-YYYY-seq` via `SequenceCounter`/`next_number`; unique per tenant |
| `issue_date` | str (ISO date) | |
| `from_location_id` | FK `stocklocation.id` | reuses the existing Manufacturing multi-location model |
| `analytic_account_id` | FK `analyticaccount.id`, optional | cost-center/department/project tag |
| `debit_account_id` | FK `account.id` | user-picked Expense-type account |
| `notes` | str, optional | |
| `transaction_id` | FK `transaction.id`, optional | the posted JV |
| `created_by_id` | FK user | |
| `created_at` | datetime | |

### `StoreIssueLine`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `store_issue_id` | FK, cascade delete | |
| `product_id` | FK product | |
| `qty` | Money | CheckConstraint qty > 0 |
| `unit_cost` | Money, default 0 | snapshot of the cost `consume_stock` actually charged (wavg/FIFO per `Tenant.cost_method`) — written after posting, not user-input |

## Rules & flow

1. **Create** (`POST /api/store-issues`) — single request, atomic:
   - Validate `from_location_id`, `analytic_account_id` (if given), and
     `debit_account_id` belong to the tenant; `debit_account_id` must
     resolve to an `Account` with `type == "Expense"` (the only types are
     `Asset|Liability|Equity|Revenue|Expense`, CHECK-enforced — there's no
     separate WIP type in this schema, so WIP consumption would just be
     modeled as an Expense account like any other; 400 otherwise).
   - For each line: `consume_stock(session, tenant_id=..., product_id=...,
     qty=..., block_negative=settings.block_negative_stock,
     source_doc_id=issue.id, source_doc_type="store_issue")`. Sum returned
     cost into `total_cost`; write it back onto the line as `unit_cost =
     cost / qty`.
   - Post one balanced JV via `post_transaction`: `Dr debit_account_id
     (analytic_account_id=X) / Cr Inventory` for `total_cost`, matching the
     existing Inventory-account resolution used in `debit_notes.py`/scrap's
     cost leg (not re-implemented — same helper).
   - `voucher_type="JV"`, `audit_entity_type="store_issue"`.
   - No GL/stock changes if all lines net to zero qty (shouldn't happen —
     line qty is CheckConstraint > 0 — but the create endpoint 400s on an
     empty `lines` array up front, same convention as Demand/Quotation).
2. **No edit, no cancel.** Once created, a Store Issue is a posted fact —
   same "issued instead of editing" convention as `CreditNote`/approved
   scrap. A mistake needs a correcting Store Issue in the other direction
   (return-to-store), which is explicitly out of scope this phase (there is
   no existing "return to store" document type to hang it on).
3. **List/detail** are read-only views; no state machine beyond
   existence.

## Permissions

New resource `store.issue`, category **Store** (same category as
`store.gate_outward`). `routers/store_issues.py` guarded by
`perm_dep("store.issue", "edit")` on create, `perm_dep("store.issue")` on
list/detail; `apply_own_filter` on the list endpoint (`my_data_only`
scoped to `created_by_id`, matching every other Purchases/Store resource).

## API surface

`routers/store_issues.py` (mounted `/api/store-issues`):
- `GET /` — list; filters `from_location_id`, `analytic_account_id`,
  `start`/`end` date range; own-filter applied
- `GET /{id}` — detail with lines, resolved location/analytic/account
  names
- `POST /` — create (rules above)

`routers/store_reports.py` (existing file, created in Phase 2b for
Gate-Outward's register + reconciliation — Issue Register and Stock
Tie-out are store-side, not purchase-specific, so they belong here rather
than in `purchase_reports.py`, matching the precedent that put Gate
Outward's own reports in this file instead of alongside Gate Inward's)
gains:
- `GET /issue-register?start=&end=&analytic_account_id=&q=` — one row per
  Store Issue: number, date, location, analytic account, debit account,
  total cost; `q` matches issue number or notes
- `GET /stock-tie-out?start=&end=&product_id=` — one row per product,
  tenant-wide (see decision #5 — not location-scoped): opening qty (stock
  qty as of `start`, derived by walking `StockMovement` before that date),
  Σ Bill-received qty (`StockMovement` rows with `direction="RECEIPT"`,
  `source_doc_type="bill"`, per decision #6), Σ Store-Issue-out qty
  (`direction="SHIPMENT"`, `source_doc_type="store_issue"`), expected
  closing (opening + in − out), actual closing (`Product.stock_qty` right
  now), variance flagged
  if non-zero

`routers/purchase_reports.py` (existing file — vendor performance is
purchasing analytics, alongside the gate-register + 3-way-match endpoints
already there) gains:
- `GET /vendor-performance?start=&end=&vendor_id=` — one row per vendor:
  avg delivery lead time in days (`AVG(GateInward.gate_date −
  PurchaseOrder.order_date)` across POs with at least one linked GI), rate trend
  (per-item rate on this vendor's quotations over time — reuses
  `VendorQuotationLine` data already collected in Phase 1), and a
  short-receipt-rate proxy (Σ variance from the existing 3-way-match calc
  ÷ Σ ordered qty, expressed as a %) in place of true rejection rate (see
  decision #4 above — documented inline in the endpoint's docstring so a
  future reader doesn't mistake the proxy for the real thing).

## Frontend

Extends the existing **Store** nav section (`forModule: "purchase_store"`)
with Store Issue, alongside Gate Outward — landing there rather than under
Purchases since it's the store-side consumption leg, matching Gate
Outward's placement:
- `/store/issues` — list (SI#, date, location, analytic account, debit
  account, cost)
- `/store/issues/new` — full-page form: location picker, line items
  (product picker showing on-hand qty at the selected location — reuses
  the existing stock-lookup pattern from Invoice/BOM forms), analytic
  account dropdown, debit account picker (filtered client-side to
  Expense type, same filtering convention as the Payment mode's
  Cash/Bank pre-filter on the 3-mode voucher form)
- `/store/issues/[id]` — detail + portrait print (voucher-prefix-only, no
  type badge, per CLAUDE.md convention)

New **`/purchases`** hub page (`HubConfig` pattern,
`frontend/src/lib/hubConfigs.ts`). Corrected against the real component
contract (`components/hub/HubPage.tsx:35-44`): a `HubConfig` has exactly 4
`kpis`, exactly **one** `band` from the closed set `"aging"|"low-stock"|
"account-list"|"payroll-runs"` (no arbitrary multi-band list — the
original draft of this spec assumed otherwise), and 4–8 `actions`:

- **KPIs (4):** Pending Demands (count of `PurchaseDemand` with
  `status IN ("draft","approved")`), POs Awaiting Billing (count of
  `PurchaseOrder` with `bill_id IS NULL` and `status="approved"`), Gate
  Entries Awaiting Billing (count of `GateInward` with `status="open"`),
  Low-Stock Items (count, same calc as the Inventory hub's own KPI —
  `reused`, not reimplemented).
- **Band:** `"low-stock"`, reusing the exact same
  `/api/reports/inventory-performance` fetch + `bandData` mapping already
  written for `INVENTORY_CONFIG` (`hubConfigs.ts:134-184`) verbatim — this
  hub doesn't need its own low-stock query, just the existing one surfaced
  a second time where purchasing staff will actually see it.
- **Actions (6):** New Demand, Comparatives, Gate Inward, Purchase Orders,
  Store Issues, Vendor Performance.
- **Fetch:** `Promise.all([...])` combining `GET /api/purchase-demands`,
  `GET /api/purchase-orders`, `GET /api/gate-inwards`,
  `GET /api/reports/inventory-performance` — same multi-source pattern
  `RECEIVABLE_CONFIG` already uses (`hubConfigs.ts:23-27`).

New report pages: `/store/issue-register`, `/store/stock-tie-out`
(Store nav section, alongside Gate Outward's register/reconciliation
pages) and `/purchases/vendor-performance` (Purchases nav section,
alongside Gate Register/3-Way-Match) — all landscape, `.table-freeze`,
matching their siblings' existing page shape exactly.

Sidebar/nav registration: `NAV`, `SUB_NAV`/`TOP_NAV`, `SECTION_PREFIXES`,
`getSectionHref` — the standing 7-edit checklist from Phase 2b's spec,
since `/purchases` is a new hub route and Store Issue is a new sub-section
under an existing top-level section.

## Testing

`tests/test_store_issues.py`:
- Create with one line: `consume_stock` called with correct
  `source_doc_type="store_issue"`; `Product.stock_qty` decreases; JV
  balanced (`Dr debit_account == Cr Inventory`); `analytic_account_id`
  present on the debit leg
- Create with `block_negative_stock=true` and insufficient stock → 400,
  no partial GL/stock mutation (matches `consume_stock`'s existing
  all-or-nothing contract)
- `debit_account_id` must be Expense type → 400 for e.g. an Asset
  account
- Multi-line issue: cost sums correctly across lines with different
  products/cost methods
- Permission: `store.issue` view-only user blocked from create;
  `my_data_only` scoping on list
- Tenant isolation on every query (location, analytic account, debit
  account, product all validated as belonging to the tenant)
- Reports: issue register filters; stock tie-out variance = 0 for a
  product whose only movements are the test's own bill-receipt/Store-Issue-out,
  non-zero when a movement is deliberately excluded from the calc window
  in the test fixture

`tests/test_vendor_performance.py`:
- Lead-time calc correct for a vendor with 2+ POs each with a linked GI
- Rate trend returns per-item quotation history ordered by date
- Short-receipt proxy matches the existing 3-way-match variance for the
  same PO set (cross-check against `purchase_reports.py`'s own calc,
  not re-derived independently — guards against the two silently
  diverging later)

## Demo seeder + docs (Phase 4)

- Extend `_seed_purchase_store_chain` (manufacturing tenant) with Store
  Issues across 3–4 `AnalyticAccount` cost centers and a mix of Expense
  debit accounts, so Issue Register/Stock Tie-out/Vendor Performance all
  have data on first login.
- CLAUDE.md/README/BLUEPRINT/USER_GUIDE delta, same pattern as the
  Phase 2/2b docs passes (`bb58e75`, `89f890e`).

## Out of scope (later work)

- Return-to-store (reversal of a Store Issue) — no existing document type
  to model it on; would need its own design
- `production_order_id` on `StoreIssue` (rejected per decision #1)
- True rejection-rate tracking (would need a new accepted/rejected qty
  field on `GateInwardLine`/`BillLine` — schema change beyond this phase)
- `_gate_required`/`_chain_required` dedup (still pending from Phase 2,
  no new instance added here)
