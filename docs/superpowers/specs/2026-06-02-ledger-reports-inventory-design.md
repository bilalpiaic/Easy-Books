# Ledger Fix, Reports & Inventory Polish — Design

**Date:** 2026-06-02
**Status:** Draft for review
**Scope:** Nine requested items, grouped into 4 phases — a General-Ledger correctness fix, surfacing/reorg of existing product features, an inventory-posting safety check, and four new reports.

---

## Locked decisions (from brainstorming)
- Build **all 4 phases in order A → B → C → D** (one spec, one staged plan).
- **Over-sell check:** always show on-hand qty on invoice/bill lines; add a per-tenant setting **`block_negative_stock`** (default **false** = soft warning). When **true**, a *sale* that would drive stock negative is hard-blocked.
- **Reports:** the proposed default KPI sets (below).

## Triage note (what's already done)
- **Product Category** is fully built (model, `/api/product-categories`, product-form picker, `/products/categories` manager) — it just has **no sidebar link** and no starter categories for "Simple" tenants. Phase A surfaces it; it is **not** rebuilt.
- **Quick Actions** is already a top toolbar on the dashboard (`dashboard/page.tsx`). Phase A only *verifies* this; a stale build is the only reason it would appear at the bottom.

---

## Phase A — Surface & polish

**A1 · Sidebar: dedicated Products/Inventory section.** In `frontend/src/components/Sidebar.tsx`, move `Products` out of the `Payable` section into a new **`Inventory`** section (added to `ALL_SECTIONS` after `Payable`, with a `SECTION_COLORS` entry). Populate it with: **Products** (`/products`), **Product Categories** (`/products/categories`), and — as Phase D lands — **Product Ledger** (`/products/ledger`) and **Inventory Report** (`/inventory/performance`). This single change resolves items 2 and 6.

**A2 · Category usability.** Extend `db.py` `STARTER_CATEGORIES` so every model (incl. `simple`) gets a minimal starter set (e.g. `simple → {"General": ["Products", "Services"]}`); existing tenants reach the now-linked manager to add their own.

**A3 · Quick Actions.** Verify the top toolbar in `dashboard/page.tsx` (already implemented). No code change expected; if a regression is found, restore the top placement.

**A4 · Cursor on product description (item 9).** In `products/page.tsx`, the description cell gets `cursor-pointer` + a `title` tooltip (full text on hover); clicking it opens the product's edit modal (consistent with row affordance).

## Phase B — General Ledger opening balance (item 1)

**Bug:** `routers/reports.py` `get_ledger` seeds each account's `running_balance` at `0` and only sums entries **within** `[start, end]`, so on a date filter `closing ≠ opening + Σ(dr−cr)`. Opening is silently dropped.

**Fix (mirror the correct `subledger.py` pattern):**
- When `start` is given, compute **opening balance per account** = Σ over journal entries with `Transaction.date < start` of `(debit − credit)` for `Asset`/`Expense` accounts and `(credit − debit)` otherwise (one grouped query, not per-row).
- Seed `running_balance` with that opening; accumulate the in-range entries on top.
- Add `opening_balance` and `closing_balance` to each account object in the response (`closing = opening + Σ period movements`).

**Frontend (`/ledger`):** render an **Opening Balance** row at the top of each account's entry list and a **Closing Balance** row at the bottom, using the new fields. No `start` filter → opening `0`, closing = all-time balance (unchanged behaviour).

## Phase C — Inventory posting: on-hand + over-sell guard (item 8)

**Setting:** add `block_negative_stock` to the Settings system (key in `routers/settings.py` `SettingsUpdate`, default `"false"`; toggle in `settings/page.tsx`; exposed via `/api/settings`).

**Backend enforcement:** in the invoice-posting path (which consumes stock via `services/inventory.py`), when `block_negative_stock` is true and a stock line's qty exceeds the product's on-hand `stock_qty`, raise `400` with a clear message (`"Insufficient stock for <product>: on hand X, sale Y"`) **before** any GL/stock write. Purchases (bills) increase stock and are never blocked.

**Frontend:** on invoice and bill line rows, when a **stock** product is selected, show **"On hand: N"** beside the qty field. If the entered qty exceeds on-hand, show an amber inline warning (always, regardless of the setting). The hard block is enforced server-side only when the setting is on.

## Phase D — New reports (items 3, 4, 5, 7)

All are read-only endpoints (live from the GL / stock tables, tenant-filtered) + a dashboard page using `apiFetch` and the existing report-page styling; nav links added under **Reports** (or **Inventory** for stock-centric ones).

- **D1 · Aging — Receivable & Payable.** Extend `routers/aging.py` with per-party detail: `GET /api/reports/aging/receivable` and `/payable` returning, as of a date, each customer/vendor's outstanding split into **current / 1-30 / 31-60 / 61-90 / 90+** plus totals. Pages `/aging/receivable` and `/aging/payable`; party rows drill to the existing `/customers/[id]/ledger` / `/vendors/[id]/ledger`.
- **D2 · Product Ledger (by store or consolidated).** `GET /api/reports/product-ledger?product_id=&location_id=&start=&end=` returning `StockMovement` rows (in/out, reference doc) with a **running quantity**, filterable by a single store (`location_id`) or **consolidated** (all stores). Page `/products/ledger` with product + store pickers.
- **D3 · Inventory Performance.** `GET /api/reports/inventory-performance?start=&end=` → per stock product: on-hand qty + **value (qty × avg_cost)**, low-stock flag (`stock_qty ≤ reorder_level`), last-movement date (slow/no-movers), **units sold + COGS** over the period. Page `/inventory/performance` with period picker + sortable columns.
- **D4 · Customer Performance.** `GET /api/reports/customer-performance?start=&end=` → per customer: **revenue** (invoiced in period), **# invoices**, **outstanding AR**, **avg days-to-pay** (paid invoices), ranked; top-N highlighted. Page `/customer-performance`.

## Phase E — Demo data for the new features

Extend `scripts/seed_demo.py` (and the `db.py` starter categories) so the demo tenants showcase everything above, keeping the seeder idempotent and re-runnable:
- **Categories:** ensure the per-model category tree exists and **assign each seeded product to a sub-category**, so the products filter/grouping and Inventory report are populated.
- **Stock movements:** the seeder already records purchases/consumption — ensure enough spread that the **Product Ledger** has real history (per-store + consolidated) and **Inventory Performance** shows a mix of fast-, slow-, and no-movers (leave a few products unsold).
- **Aging / Customer Performance:** invoices already span the year; ensure a realistic mix of **paid** (varied payment dates → meaningful avg days-to-pay) and **outstanding/overdue** (→ non-empty aging buckets). Only adjust variety if a report comes out empty.

Runs through the existing `autoseed_demo` / Settings "Load sample data" paths, so a fresh install demonstrates the new features out of the box.

## Phase F — Documentation

- **`USER_GUIDE.md`:** GL opening/closing balances on date filters; managing & assigning Product Categories; the new **Inventory** sidebar section; on-hand display + the `block_negative_stock` setting; the four new reports and how to read them.
- **`WORKFLOW.md`:** add the new reports to the reporting workflow; note the over-sell setting in the sales/inventory flow.
- **`CLAUDE.md`:** new report endpoints (`/api/reports/aging/*`, `/product-ledger`, `/inventory-performance`, `/customer-performance`), the GL opening-balance behaviour, the `block_negative_stock` setting, and the Inventory nav section.
- **`README.md`:** refresh feature highlights (categories, the four reports, inventory safeguards) to match the app.

---

## Sequencing & isolation
A → B → C → D → **E (demo data)** → **F (docs + README)**. Phase A is pure frontend + a tiny seed tweak (fast, surfaces existing work). B is a self-contained backend fix + a ledger-page tweak. C adds one setting + one guard + line-level UI. D is four independent report units (each its own endpoint + page + nav link), buildable in parallel within the phase. Each report endpoint is a focused function; no shared mutable state.

## Testing
- **B:** unit tests — opening balance with/without `start`; `closing == opening + Σ(dr−cr)` per account type; no-filter parity with current totals.
- **C:** setting on → over-sell sale rejected (400) and no GL/stock write; setting off → allowed; purchases never blocked; on-hand value returned for the UI.
- **D:** per-report endpoint tests — aging bucket boundaries (e.g. exactly 30 days), product-ledger running qty by store vs consolidated, inventory value = qty×avg_cost, customer avg-days-to-pay math; all tenant-isolated.
- **E:** after a fresh seed, each new report is non-empty for a demo tenant (aging buckets populated, product-ledger history present, inventory shows fast/slow/no-movers, customer metrics computed); re-running the seeder stays idempotent.
- Full `uv run pytest` stays green; `npm run build` compiles.

## Risks / notes
- Aging/performance reports compute live from the GL — fine at SME scale; if a tenant has very large history, add date bounds (already parameterised).
- The over-sell guard must run **before** posting writes (atomicity) — enforce in the endpoint/inventory service prior to commit.
- `avg_cost`-based valuation assumes the existing weighted-average cost on `Product`; no costing-method change is in scope.
