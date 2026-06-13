# Easy-Books — Development Roadmap

_Last reviewed: 2026-06-12 (against `main` @ merge `b9f961d`)._

## Status summary

**All six open GitHub issues are implemented and on `main`.** The tracker is stale — every
open issue has shipped; the table below reconciles each to its delivery. The forward work is
a small **future-scope backlog** (no open issue yet), outlined at the bottom.

| Issue | Title | Status | Delivered by |
|-------|-------|--------|--------------|
| **#40** | Full-page data-entry forms | ✅ Shipped | v2.6.0 — 7 New/Edit flows converted modal→route (invoices, bills, payments-received, bill-payments, products, customers, vendors) |
| **#41** | Configurable columns for Recent Transactions | ✅ Shipped | v2.5.0 — `RecentTransactions` widget: "Columns ▾" dropdown with per-column checkboxes, persisted in `localStorage`; voucher-type filter, sort, search, click-to-open |
| **#42** | Telecom Stock & Issuance table | ✅ Shipped | merge `d433cf8` — `GET /api/telecom/reports/stock-issuance` (per-RSO aggregation + franchise FCA footer) + table on `telecom/page.tsx`; 3 tests |
| **#47** | Rebuild deferred-revenue schedule on invoice edit | ✅ Shipped | v2.5.0 — `services/deferred.py`; `update_invoice` blocks edit once recognised, else reverses + rebuilds the schedule (origination + edit path unified) |
| **#52** | COA Management & Dashboard bundle | ✅ Shipped | §1/§2/§5 → #53/#41/#40; **§3** customizable dashboard (P1 `8e6a896` reorder/show-hide + P2 `b9f961d` resizable grid + shortcut tiles); **§4** voucher-type selector on New Entry; **§6** standard nav (breadcrumbs + always-on Home) |
| **#53** | Flexible Multi-Level Chart of Accounts | ✅ Shipped | Phase 1 v2.4.0 (multi-level CoA, `parent_id`/`is_group`, post-to-leaf) + Phase 2 v2.5.0 (hierarchical TB / Balance Sheet / P&L roll-up + drill-to-ledger via `services/account_tree.py`) |

**Recommended action:** close #40, #41, #42, #47, #52, #53 with a comment citing the delivery
above. (See "Issue closure" below.)

---

## Shipped history (condensed)

v2.1.0 → v2.6.0 + post-v2.6.0:
- **Reporting & GL:** #43 (financial/inventory/sales reports), #45 (consolidated/sub-ledger GL), #44 (voucher series P1+P2), hierarchical TB/BS/P&L (#53 P2), report-builder, audit log.
- **Accounting correctness:** #50 (selling/cost price), #51 (posted-doc editing), #48 (`block_negative_stock` on edit), #47 (deferred-revenue origination + edit rebuild).
- **Chart of Accounts:** #53 multi-level CoA (P1 structure + P2 hierarchical reporting); default CoA is hierarchical for every tenant (group skeleton + parented leaves in `db.py`).
- **UX:** #40 full-page forms; #41 Recent Transactions widget; #52 §4 voucher selector; #52 §6 nav controls (breadcrumbs + Home); **#52 §3 customizable dashboard** (per-user reorder/show-hide → resizable `react-grid-layout` grid + form/report shortcut tiles).
- **Telecom:** #42 Stock & Issuance per-RSO report + dashboard table.
- **Infra:** Alembic migrations source-of-truth; per-tenant demo seeding; desktop/script installers with in-app update check; standalone evaluation build auto-loads demo data.

Full per-merge detail lives in `docs/superpowers/specs/` and `docs/superpowers/plans/`.

---

## Forward backlog (no open issue — future scope, build outlines)

These are the genuinely-remaining ideas, all previously deferred under YAGNI. None is blocking;
each would follow the standard brainstorm → spec → plan → subagent-execution flow. Listed in
rough priority order.

### B1. Dashboard "smart tiles" — live metrics on shortcuts · ✅ **SHIPPED** (merge `9aced3a`)
- Automatic, summary-only: `lib/dashboardTileMetrics.ts` maps 7 routes (invoices→AR, bills→AP,
  products→low-stock, bank/cash→cash, aging→AR/AP) to a `{value, badge?, tone?}` read from the
  already-loaded `DashboardSummary`; `ShortcutTile` renders it; `DashboardGrid.renderItem` resolves
  it. Zero backend / schema change. Spec `2026-06-13-dashboard-smart-tiles-design.md`.

### B2. Dashboard data widgets — Bank Balances / Top Products / Inventory summary · ✅ **SHIPPED** (merge `963cce2`)
- Three opt-in self-fetching widgets reusing existing endpoints (zero backend): Bank Balances ←
  `/api/bank-accounts`; Top Products (best sellers, top 5) + Inventory Summary (stock value / items /
  low-stock) ← `/api/reports/inventory-performance`. New `WidgetDef.defaultOnGrid:false` keeps them
  off the default dashboard; the Add-widget panel surfaces them automatically. Pure helpers in
  `lib/inventorySummary.ts`. Spec `2026-06-13-dashboard-data-widgets-design.md`.

### B3. Cash Flow statement — reconciliation tie-out · ✅ **SHIPPED** (merge `581be22`)
- Discovery: comparison mode was **already** implemented (backend + frontend); the real gap was that
  the classifier could silently fail to tie out. Added `unclassified = (ending − beginning) −
  net_cash_change` to `/cash-flow`'s `_compute` (so both single + comparison get it); frontend shows a
  reconciling row (when non-zero) + a ✓-Reconciled/amber indicator and the reconciled net change.
  Classifier untouched. 3 tests (372 suite). Spec `2026-06-13-cashflow-reconciliation-tieout-design.md`.

### B4. Per-breakpoint dashboard layouts · ✅ **SHIPPED** (merge `57b9b3e`)
- **Why:** Phase 2 stores one desktop layout; tablet/mobile derive by stacking. Power users on
  multiple screen sizes may want distinct arrangements.
- **Build outline:** extend layout schema to v3 (`{version:3, layouts:{lg,sm,xs}}`) with a v2→v3
  migration in `resolveLayout`; capture per-breakpoint from react-grid-layout's `onLayoutChange`
  `allLayouts`. Backend store unchanged. **Shipped:** v3 schema migrations, multi-breakpoint state
  management in `useDashboardState`, per-breakpoint capture in `DashboardGrid`, v2→v3 auto-migration.

---

## Issue closure (recommended)

Close all six open issues as delivered:

| Issue | Suggested closing comment |
|-------|---------------------------|
| #40 | Shipped in v2.6.0 — all 7 New/Edit flows now full-page routes. |
| #41 | Shipped in v2.5.0 — Recent Transactions has a Columns ▾ selector (per-column checkboxes, persisted) + filter/sort/search. |
| #42 | Shipped — `GET /api/telecom/reports/stock-issuance` + per-RSO table on the telecom dashboard (merge `d433cf8`). |
| #47 | Shipped in v2.5.0 — `update_invoice` rebuilds the deferred-revenue schedule (block-if-recognised, else reverse + rebuild). |
| #52 | Shipped — §3 customizable dashboard (P1 reorder/show-hide + P2 resizable grid + shortcut tiles), §4 voucher selector, §6 nav controls; §1/§2/§5 delivered via #53/#41/#40. |
| #53 | Shipped — multi-level CoA (P1 v2.4.0) + hierarchical TB/BS/P&L reporting with drill-to-ledger (P2 v2.5.0). |
