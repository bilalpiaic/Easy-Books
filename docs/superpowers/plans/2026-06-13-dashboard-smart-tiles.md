# B1 — Dashboard Smart Tiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a live figure (e.g. AR outstanding + overdue count) on dashboard shortcut tiles whose route has a known metric, sourced entirely from the already-loaded `DashboardSummary`.

**Architecture:** A new pure `resolveTileMetric(href, summary, fmt)` maps 7 routes to a `{value, badge?, tone?}` read from `ctx.s`. `ShortcutTile` gains an optional `metric` prop and renders it; `DashboardGrid.renderItem` resolves the metric for shortcut items and passes it in. No backend, no layout-schema change, no new fetch.

**Tech Stack:** Next.js 16 / React 19 / TypeScript. Frontend-only.

**Spec:** `docs/superpowers/specs/2026-06-13-dashboard-smart-tiles-design.md`

**Gate:** No JS unit runner — every task ends with `npm run build` green and `npm run lint` at the repo baseline (**2 errors / 14 warnings**, all pre-existing/unrelated). Backend is untouched.

---

## File Structure

**New:**
- `frontend/src/lib/dashboardTileMetrics.ts` — `TileMetric`/`MetricTone` types, `TILE_METRICS` map, pure `resolveTileMetric`.

**Modified:**
- `frontend/src/components/dashboard/ShortcutTile.tsx` — optional `metric` prop + render of value/badge.
- `frontend/src/components/dashboard/DashboardGrid.tsx` — `renderItem` resolves + passes the metric.

---

## Task 1: Pure metric resolver

**Files:** Create `frontend/src/lib/dashboardTileMetrics.ts`

- [ ] **Step 1: Create the file with EXACTLY:**

```ts
import type { DashboardSummary } from "@/lib/dashboardWidgets"

export type MetricTone = "normal" | "warn" | "danger"
export interface TileMetric { value: string; badge?: string; tone?: MetricTone }

type Fmt = (n: number) => string
type Resolver = (s: DashboardSummary, fmt: Fmt) => TileMetric

// href → resolver. Routes not listed here have no metric (plain shortcut tile).
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
 *  metric or the summary hasn't loaded yet. Pure. */
export function resolveTileMetric(
  href: string, summary: DashboardSummary | undefined, fmt: Fmt,
): TileMetric | null {
  if (!summary) return null
  const resolver = TILE_METRICS[href]
  return resolver ? resolver(summary, fmt) : null
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: green. `DashboardSummary` is an exported interface in `frontend/src/lib/dashboardWidgets.tsx` (fields include `ar_outstanding`, `ap_outstanding`, `overdue_invoices`, `unpaid_bills`, `low_stock_items`, `cash_balance`) — the import resolves and the field reads type-check. The file is not consumed yet.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/dashboardTileMetrics.ts
git commit -m "feat(dashboard): pure tile-metric resolver from summary (#52 §3 B1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: ShortcutTile renders an optional metric

**Files:** Modify `frontend/src/components/dashboard/ShortcutTile.tsx`

The current file (for reference) is:

```tsx
"use client"

import React from "react"
import Link from "next/link"
import { resolveShortcut, shortcutHref } from "@/lib/dashboardShortcuts"

export default function ShortcutTile({ id, model, role, editing }: {
  id: string; model: string | undefined; role: string; editing: boolean
}) {
  const item = resolveShortcut(id, model, role)
  if (!item) {
    return (
      <div className="h-full flex items-center justify-center bg-white border border-[#ede9e2] rounded-xl text-[10px] text-[#1a1814]/40 text-center p-2">
        Unavailable
      </div>
    )
  }
  const Icon = item.icon
  const inner = (
    <div className="h-full flex flex-col items-center justify-center gap-1.5 bg-white border border-[#ede9e2] rounded-xl p-2 text-center hover:border-[#b8943f]/50 transition-colors">
      <Icon className="w-6 h-6 text-[#b8943f]" />
      <span className="text-[11px] font-medium text-[#1a1814]/80 leading-tight">{item.label}</span>
    </div>
  )
  // In edit mode the cell handles dragging; suppress navigation.
  if (editing) return inner
  return <Link href={shortcutHref(id)} className="block h-full">{inner}</Link>
}
```

- [ ] **Step 1: Replace the file ENTIRELY with:**

```tsx
"use client"

import React from "react"
import Link from "next/link"
import { resolveShortcut, shortcutHref } from "@/lib/dashboardShortcuts"
import type { TileMetric } from "@/lib/dashboardTileMetrics"

export default function ShortcutTile({ id, model, role, editing, metric }: {
  id: string; model: string | undefined; role: string; editing: boolean
  metric?: TileMetric | null
}) {
  const item = resolveShortcut(id, model, role)
  if (!item) {
    return (
      <div className="h-full flex items-center justify-center bg-white border border-[#ede9e2] rounded-xl text-[10px] text-[#1a1814]/40 text-center p-2">
        Unavailable
      </div>
    )
  }
  const Icon = item.icon
  const toneClass =
    metric?.tone === "danger" ? "bg-red-100 text-red-700"
    : metric?.tone === "warn" ? "bg-amber-100 text-amber-700"
    : "bg-[#faf6ec] text-[#b8943f]"
  const inner = (
    <div className="h-full flex flex-col items-center justify-center gap-1.5 bg-white border border-[#ede9e2] rounded-xl p-2 text-center hover:border-[#b8943f]/50 transition-colors">
      <Icon className="w-6 h-6 text-[#b8943f]" />
      <span className="text-[11px] font-medium text-[#1a1814]/80 leading-tight">{item.label}</span>
      {metric && <span className="text-sm font-bold text-[#1a1814] leading-none truncate max-w-full">{metric.value}</span>}
      {metric?.badge && (
        <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${toneClass}`}>{metric.badge}</span>
      )}
    </div>
  )
  // In edit mode the cell handles dragging; suppress navigation.
  if (editing) return inner
  return <Link href={shortcutHref(id)} className="block h-full">{inner}</Link>
}
```

(The only changes vs. the original: the `TileMetric` type import, the optional `metric` prop, the `toneClass`, and the two new conditional `<span>`s. Tiles rendered **without** a `metric` are pixel-identical to before — the original icon + label are untouched.)

- [ ] **Step 2: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline (2 errors / 14 warnings). Nothing new in `ShortcutTile.tsx`. (Not yet passed a `metric` by any caller — Task 3 wires it — so behavior is unchanged at this checkpoint.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/ShortcutTile.tsx
git commit -m "feat(dashboard): ShortcutTile optional metric (value + tone badge) (#52 §3 B1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Wire the metric into the grid

**Files:** Modify `frontend/src/components/dashboard/DashboardGrid.tsx`

The current `renderItem` (lines ~17-23) and its import (line ~8) are:

```tsx
import { isShortcutId } from "@/lib/dashboardShortcuts"
```
```tsx
function renderItem(item: GridItem, ctx: WidgetContext, meta: { model: string | undefined; role: string }, editing: boolean): React.ReactNode {
  if (isShortcutId(item.id)) {
    return <ShortcutTile id={item.id} model={meta.model} role={meta.role} editing={editing} />
  }
  const def = registryById.get(item.id)
  return def ? def.render(ctx) : null
}
```

- [ ] **Step 1: Add `shortcutHref` to the dashboardShortcuts import**

Change the import line:
```tsx
import { isShortcutId } from "@/lib/dashboardShortcuts"
```
to:
```tsx
import { isShortcutId, shortcutHref } from "@/lib/dashboardShortcuts"
```

- [ ] **Step 2: Add the metric resolver import**

Add this import alongside the other `@/lib` imports near the top of the file (e.g. right after the dashboardShortcuts import):
```tsx
import { resolveTileMetric } from "@/lib/dashboardTileMetrics"
```

- [ ] **Step 3: Resolve + pass the metric in `renderItem`**

Replace the `renderItem` function with:
```tsx
function renderItem(item: GridItem, ctx: WidgetContext, meta: { model: string | undefined; role: string }, editing: boolean): React.ReactNode {
  if (isShortcutId(item.id)) {
    const metric = resolveTileMetric(shortcutHref(item.id), ctx.s, ctx.fmt)
    return <ShortcutTile id={item.id} model={meta.model} role={meta.role} editing={editing} metric={metric ?? undefined} />
  }
  const def = registryById.get(item.id)
  return def ? def.render(ctx) : null
}
```

(`ctx.s` is the `DashboardSummary | undefined`; `ctx.fmt` is the currency formatter — both are existing fields of `WidgetContext` and `renderItem` already receives `ctx`. No call-site change needed: the `.map` already calls `renderItem(i, ctx, meta, editing)`.)

- [ ] **Step 4: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline (2 errors / 14 warnings); nothing new in `DashboardGrid.tsx`. Report exact counts.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/DashboardGrid.tsx
git commit -m "feat(dashboard): smart tiles — resolve metric for shortcut items (#52 §3 B1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Final verification

- [ ] **Step 1: Frontend build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline (2 errors / 14 warnings, all pre-existing/unrelated).

- [ ] **Step 2: Confirm backend untouched**

Run: `cd /home/mbilal71/projects/Easy-Books && git diff --name-only main...HEAD | grep -c '^backend/' || true`
Expected: `0` (no backend files changed by this feature).

- [ ] **Step 3: Manual smoke (describe; do not automate)**

With `dev.sh` running, logged in, on `/dashboard`:
- Customize → Add widget → Shortcuts → add **Invoices**: the tile shows AR outstanding; if there are overdue invoices, a red "{n} overdue" pill appears. **Done** → reload → metric persists (layout unchanged; metric is derived).
- Add **Products**: shows the low-stock count with an amber "low stock" pill when > 0.
- Add a route with no mapping (e.g. **Settings**): plain icon+label tile, no metric.
- Change the dashboard date range → money metrics (AR/AP/cash) update to the new range.
- Resize a metric tile to 2×1 → value reads comfortably.

---

## Self-review (completed at write time)

- **Spec coverage:** §2 Unit A (resolver + map) → Task 1; Unit B (ShortcutTile metric prop) → Task 2; Unit C (renderItem wiring) → Task 3. §3 data flow (metric from `ctx.s`, refreshes with date range) → Task 3 (uses `ctx.s`/`ctx.fmt`) + Task 4 smoke. §4 edge cases: unmapped → null (Task 1 `resolver ? ... : null`); summary null → null (Task 1 `if (!summary) return null`); value 0 shows / badge only when count>0 (Task 1 conditional badges); Unavailable precedence (Task 2 — the `!item` early return is before any metric render); edit-mode nav suppressed (Task 2 unchanged `if (editing) return inner`). §5 testing (pure resolver + build/lint + smoke) → Tasks 1/4. §6 file inventory = Tasks 1-3 exactly.
- **Type consistency:** `TileMetric`/`MetricTone` defined in Task 1, imported by Task 2 (`metric?: TileMetric | null`) and produced by `resolveTileMetric` in Task 3. `resolveTileMetric(href, summary, fmt)` signature identical across Task 1 (def) and Task 3 (call with `shortcutHref(item.id), ctx.s, ctx.fmt`). `ctx.s` is `DashboardSummary | undefined` matching the resolver's `summary` param.
- **No placeholders:** full verbatim for the new file and the entire rewritten `ShortcutTile.tsx`; precise import + function replacements for `DashboardGrid.tsx`.
- **No backend / schema change:** layout v2, the hook, the store, and `dashboardWidgets.tsx` (imported only for the `DashboardSummary` type) are untouched. Plain (non-metric) tiles render identically to before.
