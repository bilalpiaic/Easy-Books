# B1 — Dashboard smart tiles (live metrics on shortcuts) · Design

**Date:** 2026-06-13
**Builds on:** #52 §3 Phase 2 (resizable grid + shortcut tiles, merge `b9f961d`).
**Backlog item:** ROADMAP "Forward backlog" B1. **Effort:** S (frontend-only).

## §1 · Goal & scope

Let a dashboard shortcut tile show a relevant **live figure** at a glance, so a tile is both
a quick-launch and a status read (e.g. the *Invoices* tile shows AR outstanding + an overdue
badge). No new backend, no new request, no layout-schema change.

**Locked decisions (brainstorming 2026-06-13, design approved):**

1. **Automatic when available:** a shortcut whose route has a known metric shows it
   automatically; routes with no mapped metric stay plain navigation tiles. No per-tile toggle,
   no UI to opt in/out (YAGNI).
2. **Summary-only, zero backend:** metrics come exclusively from the `DashboardSummary` the page
   already fetches (`/api/reports/dashboard`). No new endpoints, no new fetch, no new tests
   backend-side.

**Out of scope (YAGNI):** per-tile metric on/off toggle; metrics needing new endpoints
(per-bank-account balance, customer/vendor counts, today's sales — that's backlog B2); a layout
schema change / per-item `mode` field; polling/auto-refresh beyond the dashboard's own load.

## §2 · Architecture

Three frontend files; everything flows from the summary already in `ctx`.

```
page.tsx  (ctx: WidgetContext — already has `s: DashboardSummary | undefined` + `fmt`)
   └─ <DashboardGrid ... ctx>
         └─ renderItem(item, ctx, meta, editing)
               └─ shortcut item → resolveTileMetric(shortcutHref(id), ctx.s, ctx.fmt)
                                     ├─ mapped + summary present → { value, badge?, tone? }
                                     └─ unmapped / summary null → null
               └─ <ShortcutTile ... metric={resolved | undefined} />
```

### Unit A — `frontend/src/lib/dashboardTileMetrics.ts` (new, pure)

The single source of truth for which routes are "smart" and how each reads the summary.

```ts
import type { DashboardSummary } from "@/lib/dashboardWidgets"

export type MetricTone = "normal" | "warn" | "danger"
export interface TileMetric { value: string; badge?: string; tone?: MetricTone }

type Fmt = (n: number) => string
type Resolver = (s: DashboardSummary, fmt: Fmt) => TileMetric

// href → resolver. Unlisted routes have no metric (plain shortcut).
const TILE_METRICS: Record<string, Resolver> = {
  "/invoices": (s, fmt) => ({
    value: fmt(s.ar_outstanding),
    badge: s.overdue_invoices > 0 ? `${s.overdue_invoices} overdue` : undefined,
    tone: s.overdue_invoices > 0 ? "danger" : "normal",
  }),
  "/bills": (s, fmt) => ({
    value: fmt(s.ap_outstanding),
    badge: s.unpaid_bills > 0 ? `${s.unpaid_bills} unpaid` : undefined,
    tone: s.unpaid_bills > 0 ? "warn" : "normal",
  }),
  "/products": (s) => ({
    value: `${s.low_stock_items}`,
    badge: s.low_stock_items > 0 ? "low stock" : undefined,
    tone: s.low_stock_items > 0 ? "warn" : "normal",
  }),
  "/bank-accounts": (s, fmt) => ({ value: fmt(s.cash_balance) }),
  "/cash-book": (s, fmt) => ({ value: fmt(s.cash_balance) }),
  "/aging/receivable": (s, fmt) => ({
    value: fmt(s.ar_outstanding),
    badge: s.overdue_invoices > 0 ? `${s.overdue_invoices} overdue` : undefined,
    tone: s.overdue_invoices > 0 ? "danger" : "normal",
  }),
  "/aging/payable": (s, fmt) => ({ value: fmt(s.ap_outstanding) }),
}

/** Resolve the metric for a shortcut href, or null if the route has no mapped
 *  metric or the summary hasn't loaded yet. */
export function resolveTileMetric(
  href: string, summary: DashboardSummary | undefined, fmt: Fmt,
): TileMetric | null {
  if (!summary) return null
  const resolver = TILE_METRICS[href]
  return resolver ? resolver(summary, fmt) : null
}
```

`DashboardSummary` is already exported from `lib/dashboardWidgets.tsx` (fields:
`total_revenue, total_expense, transaction_count, ar_outstanding, ap_outstanding,
overdue_invoices, unpaid_bills, low_stock_items, cash_balance, ar_aging, ap_due_week`).

### Unit B — `ShortcutTile.tsx` (modify)

Add an optional `metric?: TileMetric` prop. Stays presentational — the grid resolves and passes
it. Render:
- **No metric** (`undefined`/`null`): exactly today's icon + label tile (unchanged path).
- **With metric:** icon + label + the `value` prominently; if `badge`, a small pill below, colored
  by `tone` (`danger` → red, `warn` → amber, `normal` → neutral/gold). In edit mode, navigation is
  suppressed exactly as today (the metric is display-only).
- The "Unavailable" placeholder path (when `resolveShortcut` returns null) is unchanged and takes
  precedence over metric rendering.

### Unit C — `DashboardGrid.tsx` (modify `renderItem`)

For a shortcut id, compute `const metric = resolveTileMetric(shortcutHref(item.id), ctx.s, ctx.fmt)`
and pass `metric={metric ?? undefined}` to `<ShortcutTile>`. Block widgets and the registry path
are unchanged. `ctx` is already a parameter of `renderItem`.

## §3 · Data flow & refresh

Metrics derive from `ctx.s`, which the page sets from `/api/reports/dashboard?start&end`. So:
- Tiles reflect the **dashboard's current date range** and update when it loads or the range
  changes — same as-of as the KPI blocks. No separate request, no polling.
- While `ctx.s` is `undefined` (initial load / refetch), `resolveTileMetric` returns `null` →
  tiles render label-only, then the figure appears when data arrives. No layout shift beyond the
  value text appearing.

## §4 · Edge cases

| Case | Behavior |
|------|----------|
| Route has no mapping | `resolveTileMetric` → null → plain shortcut tile (today's behavior). |
| Summary not loaded yet | null → label-only tile; metric appears on load. |
| Metric value is 0 (e.g. AR = 0) | Value still shown (`fmt(0)`); badge omitted (badge only when count > 0). |
| Shortcut route unavailable to user (`resolveShortcut` null) | "Unavailable" placeholder — unchanged, takes precedence (metric never computed for it). |
| Edit mode | Metric renders but navigation suppressed (same as plain shortcut in edit mode). |
| 1×1 tile cramped with a figure | Default stays 1×1; user can resize to 2×1 (grid already supports it). Text uses small/tight sizing + truncation. |

## §5 · Testing

No JS unit runner — gate is `npm run build` + `npm run lint` at the repo baseline
(2 errors / 14 warnings, all pre-existing/unrelated).
- `resolveTileMetric` is **pure + exported** (the only logic) — obvious and future-testable.
- Manual smoke: add an *Invoices* shortcut → tile shows AR outstanding; with overdue invoices a red
  "{n} overdue" pill appears. Add *Products* → low-stock count with amber pill when > 0. Add a route
  with no mapping (e.g. *Settings*) → plain tile, no metric. Change the dashboard date range → money
  metrics update. Resize a metric tile to 2×1 → reads comfortably. Reload → unchanged (no layout
  schema change; existing saved layouts render identically, now with metrics where applicable).

## §6 · File inventory

**New:**
- `frontend/src/lib/dashboardTileMetrics.ts` — `TileMetric`/`MetricTone` types, `TILE_METRICS` map, `resolveTileMetric`.

**Modified:**
- `frontend/src/components/dashboard/ShortcutTile.tsx` — optional `metric` prop + render.
- `frontend/src/components/dashboard/DashboardGrid.tsx` — `renderItem` resolves + passes the metric.

**Unchanged:** all backend; layout schema v2 + hook; `AddWidgetPanel`; `dashboardShortcuts.ts`;
`dashboardWidgets.tsx` (only imported for the `DashboardSummary` type).

## §7 · Implementation order (for the plan)

1. Create `dashboardTileMetrics.ts` (pure map + `resolveTileMetric`); build green (unconsumed).
2. Add the optional `metric` prop + rendering to `ShortcutTile.tsx`; build green.
3. Wire `resolveTileMetric` into `DashboardGrid.renderItem`; build + lint at baseline.
4. Verify: `npm run build` + `npm run lint`; manual smoke per §5. Backend untouched.
