# B2 — Dashboard data widgets (Bank Balances / Top Products / Inventory Summary) · Design

**Date:** 2026-06-13
**Builds on:** #52 §3 dashboard grid (merge `b9f961d`) + B1 smart tiles (`9aced3a`).
**Backlog item:** ROADMAP "Forward backlog" B2. **Effort:** S-M (frontend-only).

## §1 · Goal & scope

Add three new dashboard widgets — **Bank Balances**, **Top Products**, **Inventory Summary** —
that users can place on the customizable grid. Each is a self-contained, self-fetching widget
reusing an existing endpoint; **no backend changes**.

**Locked decisions (brainstorming 2026-06-13, design approved):**

1. **Reuse existing endpoints (zero backend):** Bank Balances ← `GET /api/bank-accounts`
   (already returns each account with its GL `balance`); Top Products + Inventory Summary ←
   `GET /api/reports/inventory-performance` (per-product `stock_value`/`units_sold`/`low_stock`),
   aggregated/sorted client-side.
2. **Top Products ranks by `units_sold`** (best sellers), top 5.
3. **Opt-in via the Add-widget panel** (not on the default dashboard): a new
   `WidgetDef.defaultOnGrid?: boolean` (default `true`); the three widgets set it `false`, so
   they're excluded from `defaultGrid()` but appear automatically in Customize → Add widget →
   Widgets.

**Out of scope (YAGNI):** purpose-built trimmed endpoints; coupling these widgets to the
dashboard date range (they self-fetch all-time/point-in-time, like `RecentTransactions`); paging
/ sortable columns inside the widgets; new backend tests (no backend change).

## §2 · Architecture

Three new self-fetching components + a tiny pure aggregation helper + registry wiring. The
"self-fetching widget" pattern already exists (`RecentTransactions`): a `WIDGET_REGISTRY` entry
whose `render` returns a component that owns its own `useState`/`useEffect` fetch — hooks live in
the component, never in a `render(ctx)` body.

```
WIDGET_REGISTRY (dashboardWidgets.tsx)
  ├─ bank_balances      render: () => <BankBalancesWidget />
  ├─ top_products       render: () => <TopProductsWidget />
  └─ inventory_summary  render: () => <InventorySummaryWidget />   (all defaultOnGrid:false)

BankBalancesWidget   → GET /api/bank-accounts            → list name+balance (+ total)
TopProductsWidget    → GET /api/reports/inventory-performance → sort units_sold desc, top 5
InventorySummaryWidget → GET /api/reports/inventory-performance → summarizeInventory(items)
                                                              → { totalValue, itemCount, lowStock }
```

### Unit A — `lib/inventorySummary.ts` (new, pure)

The only non-presentational logic, isolated + exported for clarity:

```ts
export interface InventoryPerfItem {
  id: number; name: string; code: string
  on_hand: number; stock_value: number; low_stock: boolean; units_sold: number
}
export interface InventoryTotals { totalValue: number; itemCount: number; lowStock: number }

export function summarizeInventory(items: InventoryPerfItem[]): InventoryTotals {
  return {
    totalValue: items.reduce((sum, i) => sum + Number(i.stock_value), 0),
    itemCount: items.length,
    lowStock: items.filter(i => i.low_stock).length,
  }
}

export function topByUnitsSold(items: InventoryPerfItem[], n: number): InventoryPerfItem[] {
  return [...items].sort((a, b) => Number(b.units_sold) - Number(a.units_sold)).slice(0, n)
}
```

(`stock_value` is money-formatted to 2dp string by the endpoint; `Number(...)` parses it. `units_sold`
is a Decimal-ish number. Both compare cleanly via `Number`.)

### Unit B — `components/dashboard/widgets/BankBalancesWidget.tsx` (new)

Fetches `GET /api/bank-accounts` on mount. Renders a card titled "Bank Balances": one row per
account (display name → `fmt(balance)`), a total footer (`fmt(Σ balance)`), `h-full` so it fills
its grid cell with an inner scroll area. Loading → skeleton; error → small inline message; no
accounts → empty state. Money via `useFmt()`.

### Unit C — `components/dashboard/widgets/TopProductsWidget.tsx` (new)

Fetches `GET /api/reports/inventory-performance`, applies `topByUnitsSold(items, 5)`, renders a
card titled "Top Products": rank · name · `units_sold`. Loading/error/empty states as above.

### Unit D — `components/dashboard/widgets/InventorySummaryWidget.tsx` (new)

Fetches the same endpoint, applies `summarizeInventory(items)`, renders a card titled
"Inventory Summary" with three figures: **Total Stock Value** (`fmt(totalValue)`), **Stock Items**
(`itemCount`), **Low Stock** (`lowStock`, amber when > 0). Loading/error/empty as above.

(Top Products and Inventory Summary each fetch `/inventory-performance` independently — acceptable
duplication; both are independent grid items that may not both be present. Endpoint is tenant-scoped
and already backs the Inventory Performance page.)

### Unit E — registry + default-grid wiring

- `dashboardWidgets.tsx`: add `defaultOnGrid?: boolean` to `WidgetDef`; add the three entries with
  `defaultOnGrid: false`, sensible `defaultSize`/`minSize` (bank_balances 2×3 / top_products 2×3 /
  inventory_summary 2×2; all min 2×2), `defaultVisible: true`, no `pinned`/`conditional`.
- `useDashboardLayout.ts`: `defaultGrid()` excludes `defaultOnGrid === false`
  (`gridDefs.filter(d => d.defaultOnGrid !== false)`). `validateV2` is unchanged — a non-pinned
  opt-in widget is a valid grid item once added, so saved layouts containing it resolve normally.
- `AddWidgetPanel.tsx`: **unchanged** — its Widgets tab already lists every non-pinned registry
  widget not currently on the grid, so the three appear automatically.

## §3 · Data flow

Each widget fetches its endpoint once on mount (`apiFetch` + `useState`/`useEffect`), independent
of the dashboard's data/`ctx`. They render point-in-time (bank balances, stock) or all-time
(units_sold) figures — not coupled to the dashboard date range, matching `RecentTransactions`.
Adding/removing/resizing happens through the existing grid customize flow; the per-user layout
store persists the widget id like any other.

## §4 · Edge cases

| Case | Behavior |
|------|----------|
| No bank accounts / no products | Per-widget empty state ("No bank accounts" / "No products yet"). |
| Fetch fails | Small inline error text inside the card; the rest of the dashboard is unaffected. |
| Fewer than 5 products | Top Products shows what exists. |
| `stock_value` as money string | Parsed with `Number()` in `summarizeInventory`/sort; safe for 2dp strings. |
| Widget added then business has no inventory module | Still renders (empty state); user can remove it. |
| Existing user upgrades | Default layout unchanged (opt-in widgets never auto-added); they appear in Add panel. |

## §5 · Testing

No JS unit runner — gate is `npm run build` + `npm run lint` at the repo baseline
(2 errors / 14 warnings). Backend suite must stay **369** (no backend change — confirm via empty
`backend/` diff).
- `summarizeInventory` / `topByUnitsSold` are **pure + exported** (the only logic) — obvious and
  future-testable.
- Manual smoke: Customize → Add widget → Widgets tab shows Bank Balances / Top Products /
  Inventory Summary → add each → data renders (balances list + total; top-5 by units sold;
  three inventory figures); empty/zero states sane; Done persists across reload; the **default**
  dashboard (fresh user / after Reset) does NOT include the three.

## §6 · File inventory

**New:**
- `frontend/src/lib/inventorySummary.ts` — `InventoryPerfItem`/`InventoryTotals`, `summarizeInventory`, `topByUnitsSold`.
- `frontend/src/components/dashboard/widgets/BankBalancesWidget.tsx`
- `frontend/src/components/dashboard/widgets/TopProductsWidget.tsx`
- `frontend/src/components/dashboard/widgets/InventorySummaryWidget.tsx`

**Modified:**
- `frontend/src/lib/dashboardWidgets.tsx` — `WidgetDef.defaultOnGrid?` + 3 registry entries.
- `frontend/src/hooks/useDashboardLayout.ts` — `defaultGrid()` excludes `defaultOnGrid === false`.

**Unchanged:** all backend; `AddWidgetPanel.tsx`; `DashboardGrid.tsx`; `ShortcutTile.tsx`; layout schema v2 + `resolveLayout`/`migrateV1toV2`.

## §7 · Implementation order (for the plan)

1. `lib/inventorySummary.ts` (pure helpers); build green.
2. The three widget components (each self-fetching); build green per component.
3. Registry: `defaultOnGrid` field + 3 entries; `useDashboardLayout.defaultGrid()` filter; build + lint.
4. Verify: build + lint at baseline; backend untouched; manual smoke per §5.
