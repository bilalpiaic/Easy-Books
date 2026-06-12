# #52 §3 Phase 2 — Resizable Dashboard Grid + Shortcut Tiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the dashboard into a draggable, resizable per-user grid where every widget — existing analytical blocks and new shortcut tiles to any form/report — can be placed and sized freely.

**Architecture:** Replace the Phase-1 single-column `@dnd-kit` sortable with a `react-grid-layout` free grid. The per-user backend store is unchanged (opaque JSON); the layout blob evolves to schema v2 (`{version:2, items:[{id,x,y,w,h}]}`) with a pure v1→v2 migration. Shortcut tiles reference the existing `NAV` catalog (model/role filtered). Onboarding + Alerts render as a fixed strip above the grid.

**Tech Stack:** Next.js 16 / React 19.2 / TypeScript; `react-grid-layout`. No backend changes.

**Spec:** `docs/superpowers/specs/2026-06-12-issue52-3-phase2-dashboard-grid-design.md`

**Gate:** No JS unit runner — every task ends with `npm run build` green and `npm run lint` at the repo baseline (**2 errors / 14 warnings**, all in pre-existing unrelated files). Backend suite must stay green (369) but is unchanged by this work.

---

## File Structure

**New:**
- `frontend/src/lib/dashboardShortcuts.ts` — shortcut id helpers + NAV catalog filter + resolve
- `frontend/src/components/dashboard/DashboardGrid.tsx` — react-grid-layout grid (view + edit)
- `frontend/src/components/dashboard/ShortcutTile.tsx` — generic shortcut renderer
- `frontend/src/components/dashboard/AddWidgetPanel.tsx` — add-widget picker

**Modified:**
- `frontend/src/lib/dashboardWidgets.tsx` — `WidgetDef` gains `defaultSize`/`minSize`/`pinned`; per-widget sizes; `pinned:true` on onboarding+alerts; chart render fns fill cell height
- `frontend/src/hooks/useDashboardLayout.ts` — v2 schema, `packItems`/`defaultGrid`/`migrateV1toV2`/`resolveLayout`, grid mutators
- `frontend/src/app/(dashboard)/dashboard/page.tsx` — notices strip + `<DashboardGrid>`
- `frontend/package.json` — add `react-grid-layout`; remove `@dnd-kit/*`

**Removed:**
- `frontend/src/components/dashboard/DashboardCanvas.tsx`
- `frontend/src/components/dashboard/CustomizeBar.tsx`

---

## Task 1: Install react-grid-layout (verify React 19 compat)

**Files:** Modify `frontend/package.json`

- [ ] **Step 1: Install (runtime + types)**

Run: `cd frontend && npm install react-grid-layout && npm install -D @types/react-grid-layout`
`react-grid-layout` does NOT bundle TypeScript types — `@types/react-grid-layout` (DefinitelyTyped) is required or the `import { ..., type Layout } from "react-grid-layout"` will fail to type-check.
If npm errors with an unmet React peer dependency (react-grid-layout may declare `react <19`), retry each with `--legacy-peer-deps`: `npm install react-grid-layout --legacy-peer-deps` then `npm install -D @types/react-grid-layout --legacy-peer-deps`.

- [ ] **Step 2: Smoke-verify it loads under React 19**

Create a throwaway check — add to the TOP of `frontend/src/app/(dashboard)/dashboard/page.tsx` (temporarily) the import line `import { Responsive, WidthProvider } from "react-grid-layout"` and a no-op `void WidthProvider; void Responsive`. Run `cd frontend && npm run build`.
Expected: build succeeds (module resolves, no type/runtime import error).
Then REMOVE the temporary lines.

If the build fails specifically because `react-grid-layout` is incompatible with React 19 at the type/runtime level (not merely a peer-dep warning), STOP and report `BLOCKED` with the exact error — the spec's fallback is `gridstack` and that decision needs escalation before continuing.

- [ ] **Step 3: Remove the retired @dnd-kit deps**

Run: `cd frontend && npm uninstall @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`
(These backed the Phase-1 `CustomizeBar`, which this plan removes. The removal compiles only after Task 5 deletes `CustomizeBar.tsx`; if `npm run build` is run between now and Task 5 it will still pass because `CustomizeBar.tsx` still imports them until then — so do this uninstall but do NOT run build again until Task 5. If you prefer, defer this single command to Task 5 Step 4. Either is fine.)

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "build(dashboard): add react-grid-layout for resizable grid (#52 §3 P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Widget size metadata + chart cell-fill

**Files:** Modify `frontend/src/lib/dashboardWidgets.tsx`

- [ ] **Step 1: Extend `WidgetDef` with size + pinned fields**

Replace the existing `WidgetDef` interface (it currently has `id/title/defaultVisible/conditional?/render`) with:

```tsx
export interface WidgetSize { w: number; h: number }
export interface WidgetDef {
  id: string
  title: string
  defaultVisible: boolean        // retained from Phase 1; unused by the grid but harmless
  defaultSize: WidgetSize        // cells on the 4-col desktop grid
  minSize: WidgetSize
  pinned?: boolean               // rendered in the fixed notices strip, NOT a grid item
  conditional?: boolean          // render() may return null (e.g. ar_aging when no data)
  render: (ctx: WidgetContext) => React.ReactNode
}
```

- [ ] **Step 2: Add `defaultSize`/`minSize` (and `pinned`) to every `WIDGET_REGISTRY` entry**

Add these fields to each entry (keep `id`/`title`/`defaultVisible`/`conditional`/`render` exactly as they are). Use these values:

| id | add fields |
|----|-----------|
| `quick_actions` | `defaultSize: { w: 4, h: 1 }, minSize: { w: 2, h: 1 }` |
| `onboarding` | `defaultSize: { w: 4, h: 2 }, minSize: { w: 4, h: 1 }, pinned: true` |
| `primary_kpis` | `defaultSize: { w: 4, h: 2 }, minSize: { w: 2, h: 2 }` |
| `secondary_kpis` | `defaultSize: { w: 4, h: 2 }, minSize: { w: 2, h: 2 }` |
| `ar_aging` | `defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 }` |
| `alerts` | `defaultSize: { w: 4, h: 1 }, minSize: { w: 4, h: 1 }, pinned: true` |
| `monthly_rev_exp` | `defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 }` |
| `net_profit_trend` | `defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 }` |
| `expense_breakdown` | `defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 }` |
| `top_customers` | `defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 }` |
| `recent_transactions` | `defaultSize: { w: 4, h: 3 }, minSize: { w: 2, h: 2 }` |

Example (the `primary_kpis` entry becomes):

```tsx
  {
    id: "primary_kpis", title: "Key Figures", defaultVisible: true,
    defaultSize: { w: 4, h: 2 }, minSize: { w: 2, h: 2 },
    render: (ctx) => { /* unchanged */ },
  },
```

- [ ] **Step 3: Make the chart widgets fill their grid cell height**

The grid gives each cell a pixel height. For charts to scale, their outer card must be a full-height flex column and the chart container must flex to fill. Apply these EXACT class edits inside the render fns (only the class strings change; all other JSX identical):

1. `ar_aging` render — its outer element is `<div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">`. Change to `<div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm h-full flex flex-col">`. Its chart container `<div className="h-36">` → `<div className="flex-1 min-h-0">`.
2. `monthly_rev_exp` render — outer `<div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">` → add ` h-full flex flex-col`. Chart container `<div className="h-48 sm:h-56">` → `<div className="flex-1 min-h-0">`.
3. `net_profit_trend` render — same outer add ` h-full flex flex-col`; `<div className="h-48 sm:h-56">` → `<div className="flex-1 min-h-0">`.
4. `expense_breakdown` render — same outer add ` h-full flex flex-col`; `<div className="h-52">` → `<div className="flex-1 min-h-0">`.
5. `top_customers` render — same outer add ` h-full flex flex-col`; `<div className="h-52">` → `<div className="flex-1 min-h-0">`.

For `monthly_rev_exp`/`net_profit_trend`/`expense_breakdown`/`top_customers`, the header `<div>`/`<p>` line stays as the first flex child; the chart container is the second (now `flex-1 min-h-0`). For `recent_transactions`, `primary_kpis`, `secondary_kpis`, `quick_actions` — NO change (they size naturally; the grid cell will be tall enough at their default `h`).

- [ ] **Step 4: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline (2 errors / 14 warnings). Nothing in `dashboardWidgets.tsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/dashboardWidgets.tsx
git commit -m "feat(dashboard): per-widget grid sizes + chart cell-fill (#52 §3 P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Shortcut catalog helpers (pure)

**Files:** Create `frontend/src/lib/dashboardShortcuts.ts`

- [ ] **Step 1: Create the file with EXACTLY:**

```ts
import { NAV, type NavItem } from "@/lib/nav"

const SHORTCUT_PREFIX = "shortcut:"

export const isShortcutId = (id: string) => id.startsWith(SHORTCUT_PREFIX)
export const shortcutHref = (id: string) => id.slice(SHORTCUT_PREFIX.length)
export const shortcutId = (href: string) => `${SHORTCUT_PREFIX}${href}`

/** Same visibility rule the sidebar uses (lib/nav consumers). */
function available(item: NavItem, model: string | undefined, role: string): boolean {
  const isAdmin = role === "admin" || role === "owner"
  return (!item.forModel || item.forModel === model) && (!item.adminOnly || isAdmin)
}

/** NAV items the user may add as shortcut tiles (excludes the Dashboard itself),
 *  filtered to the user's business model + role. */
export function shortcutCatalog(model: string | undefined, role: string): NavItem[] {
  return NAV.filter(i => i.href !== "/dashboard" && available(i, model, role))
}

/** Resolve a shortcut id to its NAV item, or null if it's no longer available
 *  to this user (e.g. their business model changed and the route is gone). */
export function resolveShortcut(id: string, model: string | undefined, role: string): NavItem | null {
  if (!isShortcutId(id)) return null
  const item = NAV.find(i => i.href === shortcutHref(id))
  return item && available(item, model, role) ? item : null
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: green (file is pure; not yet consumed).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/dashboardShortcuts.ts
git commit -m "feat(dashboard): shortcut catalog helpers from NAV (#52 §3 P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Layout hook v2 (schema, migration, mutators)

**Files:** Rewrite `frontend/src/hooks/useDashboardLayout.ts`

- [ ] **Step 1: Replace the file ENTIRELY with:**

```ts
import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { getCurrentUser } from "@/lib/auth"
import { WIDGET_REGISTRY, type WidgetDef } from "@/lib/dashboardWidgets"
import { isShortcutId, resolveShortcut } from "@/lib/dashboardShortcuts"

export const GRID_COLS = 4

export interface GridItem { id: string; x: number; y: number; w: number; h: number }
export interface GridLayoutV2 { version: 2; items: GridItem[] }

// Phase-1 shapes (for migration only)
interface StoredWidgetV1 { id: string; visible: boolean }
interface StoredLayoutV1 { version: 1; widgets: StoredWidgetV1[] }

type Meta = { model: string | undefined; role: string }
type SavedAny = GridLayoutV2 | StoredLayoutV1 | Record<string, unknown> | null

const registryById = new Map<string, WidgetDef>(WIDGET_REGISTRY.map(w => [w.id, w]))
const gridDefs = WIDGET_REGISTRY.filter(w => !w.pinned)

/** Shelf-pack {id,w,h} entries into a GRID_COLS-wide layout (left→right, wrap). */
export function packItems(sized: { id: string; w: number; h: number }[]): GridItem[] {
  const items: GridItem[] = []
  let x = 0, y = 0, rowH = 0
  for (const s of sized) {
    const w = Math.min(s.w, GRID_COLS)
    if (x + w > GRID_COLS) { x = 0; y += rowH; rowH = 0 }
    items.push({ id: s.id, x, y, w, h: s.h })
    x += w; rowH = Math.max(rowH, s.h)
  }
  return items
}

export function defaultGrid(): GridItem[] {
  return packItems(gridDefs.map(d => ({ id: d.id, w: d.defaultSize.w, h: d.defaultSize.h })))
}

export function migrateV1toV2(v1: StoredLayoutV1): GridItem[] {
  const sized = v1.widgets
    .filter(w => w.visible)
    .map(w => registryById.get(w.id))
    .filter((d): d is WidgetDef => Boolean(d) && !d!.pinned)
    .map(d => ({ id: d.id, w: d.defaultSize.w, h: d.defaultSize.h }))
  return packItems(sized)
}

function validateV2(items: GridItem[], meta: Meta): GridItem[] {
  const seen = new Set<string>()
  const out: GridItem[] = []
  for (let it of items) {
    if (!it || typeof it.id !== "string" || seen.has(it.id)) continue
    if (isShortcutId(it.id)) {
      if (!resolveShortcut(it.id, meta.model, meta.role)) continue
    } else {
      const def = registryById.get(it.id)
      if (!def || def.pinned) continue
      if (it.w < def.minSize.w) it = { ...it, w: def.minSize.w }
      if (it.h < def.minSize.h) it = { ...it, h: def.minSize.h }
    }
    seen.add(it.id)
    out.push(it)
  }
  return out
}

/** Resolve a saved blob (null | v1 | v2) into validated grid items. */
export function resolveLayout(saved: SavedAny, meta: Meta): GridItem[] {
  if (!saved || typeof saved !== "object") return defaultGrid()
  const v = (saved as { version?: number }).version
  if (v === 2 && Array.isArray((saved as GridLayoutV2).items)) {
    return validateV2((saved as GridLayoutV2).items, meta)
  }
  if (v === 1 && Array.isArray((saved as StoredLayoutV1).widgets)) {
    return migrateV1toV2(saved as StoredLayoutV1)
  }
  return defaultGrid()
}

function serialize(items: GridItem[]): string {
  return JSON.stringify(items.map(i => ({ id: i.id, x: i.x, y: i.y, w: i.w, h: i.h })))
}

export interface UseDashboardLayout {
  items: GridItem[]
  meta: Meta
  loading: boolean
  dirty: boolean
  applyLayout: (layout: { i: string; x: number; y: number; w: number; h: number }[]) => void
  addWidget: (id: string) => void
  removeWidget: (id: string) => void
  reset: () => void
  reload: () => void
  save: () => Promise<void>
}

export function useDashboardLayout(): UseDashboardLayout {
  const [items, setItems] = useState<GridItem[]>(() => defaultGrid())
  const [saved, setSaved] = useState<SavedAny>(null)
  const [meta, setMeta] = useState<Meta>({ model: undefined, role: getCurrentUser()?.role ?? "viewer" })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      apiFetch<{ layout: SavedAny }>("/api/dashboard/layout").catch(() => ({ layout: null })),
      apiFetch<{ role?: string; tenant?: { business_model?: string } }>("/api/auth/me").catch(() => ({} as { role?: string; tenant?: { business_model?: string } })),
    ]).then(([lay, me]) => {
      const m: Meta = { model: me?.tenant?.business_model, role: me?.role ?? getCurrentUser()?.role ?? "viewer" }
      setMeta(m)
      setSaved(lay.layout)
      setItems(resolveLayout(lay.layout, m))
    }).finally(() => setLoading(false))
  }, [])

  const applyLayout = (layout: { i: string; x: number; y: number; w: number; h: number }[]) =>
    setItems(layout.map(l => ({ id: l.i, x: l.x, y: l.y, w: l.w, h: l.h })))

  const addWidget = (id: string) => setItems(prev => {
    if (prev.some(i => i.id === id)) return prev
    const def = registryById.get(id)
    const size = def ? def.defaultSize : { w: 1, h: 1 }   // shortcut default 1x1
    const y = prev.reduce((m, i) => Math.max(m, i.y + i.h), 0)
    return [...prev, { id, x: 0, y, w: size.w, h: size.h }]
  })

  const removeWidget = (id: string) => setItems(prev => prev.filter(i => i.id !== id))
  const reset = () => setItems(defaultGrid())
  const reload = () => setItems(resolveLayout(saved, meta))

  const save = async () => {
    const payload: GridLayoutV2 = { version: 2, items }
    await apiFetch("/api/dashboard/layout", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout: payload }),
    })
    setSaved(payload)
  }

  const baseline = saved ? resolveLayout(saved, meta) : defaultGrid()
  const dirty = serialize(items) !== serialize(baseline)

  return { items, meta, loading, dirty, applyLayout, addWidget, removeWidget, reset, reload, save }
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: green. (The old `DashboardCanvas`/`CustomizeBar` still import the OLD hook exports `widgets`/`setOrder`/`toggle` — those exports are GONE now, so those two files will FAIL to type-check. That is expected and resolved in Task 5, which deletes them. If build fails ONLY due to `DashboardCanvas.tsx`/`CustomizeBar.tsx`/`page.tsx` referencing removed hook members, proceed — Task 5 fixes it. Confirm there are no OTHER errors.)

If you want a clean build at this checkpoint, you may proceed directly into Task 5 before committing; otherwise commit now (the repo is mid-refactor between commits, which is acceptable on a feature branch).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useDashboardLayout.ts
git commit -m "feat(dashboard): layout hook v2 — grid items, v1→v2 migration (#52 §3 P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: DashboardGrid (view) + page wiring; remove DashboardCanvas

**Files:**
- Create `frontend/src/components/dashboard/DashboardGrid.tsx`
- Modify `frontend/src/app/(dashboard)/dashboard/page.tsx`
- Delete `frontend/src/components/dashboard/DashboardCanvas.tsx`

- [ ] **Step 1: Create `DashboardGrid.tsx` (view + edit-ready; edit UI added in Task 6)**

```tsx
"use client"

import React from "react"
import { Responsive, WidthProvider, type Layout } from "react-grid-layout"
import "react-grid-layout/css/styles.css"
import "react-resizable/css/styles.css"
import { WIDGET_REGISTRY, type WidgetContext, type WidgetDef } from "@/lib/dashboardWidgets"
import { isShortcutId } from "@/lib/dashboardShortcuts"
import type { GridItem, UseDashboardLayout } from "@/hooks/useDashboardLayout"
import { GRID_COLS } from "@/hooks/useDashboardLayout"

const ResponsiveGridLayout = WidthProvider(Responsive)

const registryById = new Map<string, WidgetDef>(WIDGET_REGISTRY.map(w => [w.id, w]))

function renderItem(item: GridItem, ctx: WidgetContext): React.ReactNode {
  if (isShortcutId(item.id)) return null   // ShortcutTile added in Task 7
  const def = registryById.get(item.id)
  return def ? def.render(ctx) : null
}

export default function DashboardGrid({ layout, ctx, editing }: {
  layout: UseDashboardLayout
  ctx: WidgetContext
  editing: boolean
}) {
  const { items, applyLayout } = layout
  const rglLayout: Layout[] = items.map(i => {
    const def = registryById.get(i.id)
    return {
      i: i.id, x: i.x, y: i.y, w: i.w, h: i.h,
      minW: def?.minSize.w ?? 1, minH: def?.minSize.h ?? 1,
    }
  })

  return (
    <ResponsiveGridLayout
      className="layout"
      layouts={{ lg: rglLayout, sm: rglLayout, xs: rglLayout }}
      breakpoints={{ lg: 1024, sm: 640, xs: 0 }}
      cols={{ lg: GRID_COLS, sm: 2, xs: 1 }}
      rowHeight={96}
      margin={[12, 12]}
      compactType="vertical"
      isDraggable={editing}
      isResizable={editing}
      onLayoutChange={(l: Layout[]) => { if (editing) applyLayout(l) }}
      draggableCancel=".no-drag"
    >
      {items.map(i => (
        <div key={i.id} className="overflow-hidden">
          {renderItem(i, ctx)}
        </div>
      ))}
    </ResponsiveGridLayout>
  )
}
```

- [ ] **Step 2: Rewrite `page.tsx` — notices strip + grid (no Customize button yet; added in Task 6)**

Read the current `frontend/src/app/(dashboard)/dashboard/page.tsx`. Keep ALL the data-fetch + chart-config + `ctx` construction EXACTLY as-is. Change only the imports and the returned JSX body.

Replace the import line:
```tsx
import DashboardCanvas from "@/components/dashboard/DashboardCanvas"
```
with:
```tsx
import DashboardGrid from "@/components/dashboard/DashboardGrid"
import { WIDGET_REGISTRY } from "@/lib/dashboardWidgets"
```
(Keep `useDashboardLayout` import. The page still calls `const layout = useDashboardLayout()`.)

Just BEFORE the `return (`, add a lookup of the two pinned notice widgets:
```tsx
  const onboardingWidget = WIDGET_REGISTRY.find(w => w.id === "onboarding")
  const alertsWidget = WIDGET_REGISTRY.find(w => w.id === "alerts")
```

Replace the body's render of the canvas. The current body ends with (from the Phase-1/grid-merge state):
```tsx
      {error && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>}

      <DashboardCanvas widgets={layout.widgets} ctx={ctx} />
    </div>
  )
```
Replace those lines with:
```tsx
      {error && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>}

      {/* Pinned notices (not part of the customizable grid) */}
      {onboardingWidget?.render(ctx)}
      {alertsWidget?.render(ctx)}

      <DashboardGrid layout={layout} ctx={ctx} editing={false} />
    </div>
  )
```

NOTE: the current header still has the Phase-1 Customize button + `editing` state referencing `CustomizeBar`. REMOVE the `editing` state, the Customize `<button>`, and any `CustomizeBar` import for now — this task ships a view-only grid. (Task 6 reintroduces an `editing` state + Customize button wired to the grid.) After edits, the header's right side should be just the DateRangePicker wrapper:
```tsx
        <div className="bg-white border border-[#ede9e2] rounded-xl px-3 py-2 shadow-sm">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
        </div>
```
and remove the now-unused `Settings2` import and the `CustomizeBar` import.

- [ ] **Step 3: Delete the retired canvas**

Run: `cd frontend && git rm src/components/dashboard/DashboardCanvas.tsx`
(Leave `CustomizeBar.tsx` for now — Task 6 removes it. It will NOT compile against the new hook, so see Step 4.)

- [ ] **Step 4: Make CustomizeBar stop breaking the build (temporary)**

`CustomizeBar.tsx` imports removed hook members and `@dnd-kit`. Since it's no longer rendered anywhere (page.tsx no longer imports it), the simplest path is to delete it now too rather than carry dead code:

Run: `cd frontend && git rm src/components/dashboard/CustomizeBar.tsx`
And if not already done in Task 1 Step 3: `npm uninstall @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`

(Task 6 will build the edit UI directly into `DashboardGrid`, so `CustomizeBar` is not needed.)

- [ ] **Step 5: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline (2 errors / 14 warnings). The dashboard now renders a static (read-only) grid from the saved/default layout, with onboarding+alerts pinned above it.

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src/components/dashboard frontend/src/app/"(dashboard)"/dashboard/page.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(dashboard): react-grid-layout grid (view) + pinned notices; retire canvas (#52 §3 P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Grid edit mode (drag/resize/remove + Done/Cancel/Reset)

**Files:**
- Modify `frontend/src/components/dashboard/DashboardGrid.tsx`
- Modify `frontend/src/app/(dashboard)/dashboard/page.tsx`

- [ ] **Step 1: Add an edit toolbar + per-tile remove to `DashboardGrid`**

Replace `DashboardGrid.tsx` ENTIRELY with this version (adds an `onExitEditing` prop, the edit toolbar, and a remove (×) button per tile shown only while editing):

```tsx
"use client"

import React, { useState } from "react"
import { Responsive, WidthProvider, type Layout } from "react-grid-layout"
import "react-grid-layout/css/styles.css"
import "react-resizable/css/styles.css"
import { X, Check, RotateCcw } from "lucide-react"
import { WIDGET_REGISTRY, type WidgetContext, type WidgetDef } from "@/lib/dashboardWidgets"
import { isShortcutId } from "@/lib/dashboardShortcuts"
import type { GridItem, UseDashboardLayout } from "@/hooks/useDashboardLayout"
import { GRID_COLS } from "@/hooks/useDashboardLayout"

const ResponsiveGridLayout = WidthProvider(Responsive)
const registryById = new Map<string, WidgetDef>(WIDGET_REGISTRY.map(w => [w.id, w]))

function renderItem(item: GridItem, ctx: WidgetContext): React.ReactNode {
  if (isShortcutId(item.id)) return null   // ShortcutTile added in Task 7
  const def = registryById.get(item.id)
  return def ? def.render(ctx) : null
}

export default function DashboardGrid({ layout, ctx, editing, onExitEditing }: {
  layout: UseDashboardLayout
  ctx: WidgetContext
  editing: boolean
  onExitEditing: () => void
}) {
  const { items, applyLayout, removeWidget, reset, reload, save } = layout
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const rglLayout: Layout[] = items.map(i => {
    const def = registryById.get(i.id)
    return { i: i.id, x: i.x, y: i.y, w: i.w, h: i.h, minW: def?.minSize.w ?? 1, minH: def?.minSize.h ?? 1 }
  })

  const handleDone = async () => {
    setSaving(true); setErr(null)
    try { await save(); onExitEditing() }
    catch { setErr("Couldn't save layout. Please try again.") }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-3">
      {editing && (
        <div className="flex flex-wrap items-center gap-2 bg-[#faf6ec] border border-[#b8943f]/30 rounded-xl px-3 py-2 sticky top-2 z-20">
          <span className="text-xs font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">Customizing dashboard</span>
          <span className="text-[11px] text-[#1a1814]/45">Drag to move · drag a corner to resize · × to remove</span>
          <div className="ml-auto flex items-center gap-2">
            <button onClick={reset} className="inline-flex items-center gap-1 text-xs text-[#1a1814]/60 hover:text-[#1a1814] px-2 py-1">
              <RotateCcw className="w-3.5 h-3.5" /> Reset
            </button>
            <button onClick={() => { reload(); onExitEditing() }} className="inline-flex items-center gap-1 text-xs text-[#1a1814]/60 hover:text-[#1a1814] px-2 py-1">
              <X className="w-3.5 h-3.5" /> Cancel
            </button>
            <button onClick={handleDone} disabled={saving} className="inline-flex items-center gap-1 text-xs font-semibold text-white bg-[#b8943f] hover:bg-[#a07f33] rounded-lg px-3 py-1.5 disabled:opacity-60">
              <Check className="w-3.5 h-3.5" /> {saving ? "Saving…" : "Done"}
            </button>
          </div>
        </div>
      )}

      {err && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-2 text-sm text-red-700">{err}</div>}

      <ResponsiveGridLayout
        className="layout"
        layouts={{ lg: rglLayout, sm: rglLayout, xs: rglLayout }}
        breakpoints={{ lg: 1024, sm: 640, xs: 0 }}
        cols={{ lg: GRID_COLS, sm: 2, xs: 1 }}
        rowHeight={96}
        margin={[12, 12]}
        compactType="vertical"
        isDraggable={editing}
        isResizable={editing}
        onLayoutChange={(l: Layout[]) => { if (editing) applyLayout(l) }}
        draggableCancel=".no-drag"
      >
        {items.map(i => (
          <div key={i.id} className={`overflow-hidden ${editing ? "ring-2 ring-dashed ring-[#b8943f]/40 rounded-xl relative" : ""}`}>
            {editing && (
              <button
                onClick={() => removeWidget(i.id)}
                className="no-drag absolute top-1 right-1 z-10 bg-white/90 border border-[#ede9e2] rounded-full p-1 text-[#1a1814]/50 hover:text-red-600"
                aria-label="Remove widget"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
            <div className={editing ? "pointer-events-none select-none h-full" : "h-full"}>
              {renderItem(i, ctx)}
            </div>
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  )
}
```

- [ ] **Step 2: Reintroduce the Customize toggle in `page.tsx`**

Add back the `editing` state and a Customize button. Add the import:
```tsx
import { Settings2 } from "lucide-react"
```
Add state after `const layout = useDashboardLayout()`:
```tsx
  const [editing, setEditing] = useState(false)
```
Change the header right side from the bare DateRangePicker wrapper to a flex group with the Customize button (shown only when not editing):
```tsx
        <div className="flex items-center gap-2">
          <div className="bg-white border border-[#ede9e2] rounded-xl px-3 py-2 shadow-sm">
            <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
          </div>
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[#ede9e2] bg-white shadow-sm text-sm font-medium text-[#1a1814]/75 hover:border-[#b8943f]/40 transition-colors"
            >
              <Settings2 className="w-4 h-4 text-[#b8943f]" /> Customize
            </button>
          )}
        </div>
```
Change the grid render to pass `editing` + `onExitEditing`:
```tsx
      <DashboardGrid layout={layout} ctx={ctx} editing={editing} onExitEditing={() => setEditing(false)} />
```

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline. Customize now enables drag/resize, per-tile remove, and Done/Cancel/Reset (save-on-Done).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/DashboardGrid.tsx "frontend/src/app/(dashboard)/dashboard/page.tsx"
git commit -m "feat(dashboard): grid customize mode — drag/resize/remove, save-on-done (#52 §3 P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Shortcut tiles

**Files:**
- Create `frontend/src/components/dashboard/ShortcutTile.tsx`
- Modify `frontend/src/components/dashboard/DashboardGrid.tsx` (render shortcut items)

- [ ] **Step 1: Create `ShortcutTile.tsx`**

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

- [ ] **Step 2: Render shortcut items in `DashboardGrid`**

In `DashboardGrid.tsx`, add the import:
```tsx
import ShortcutTile from "@/components/dashboard/ShortcutTile"
```
Replace the `renderItem` helper and update the cell render to pass meta + editing. Change `renderItem` to:
```tsx
function renderItem(item: GridItem, ctx: WidgetContext, meta: { model: string | undefined; role: string }, editing: boolean): React.ReactNode {
  if (isShortcutId(item.id)) {
    return <ShortcutTile id={item.id} model={meta.model} role={meta.role} editing={editing} />
  }
  const def = registryById.get(item.id)
  return def ? def.render(ctx) : null
}
```
And in the `.map`, change `{renderItem(i, ctx)}` to `{renderItem(i, ctx, layout.meta, editing)}`. (`layout.meta` is on the hook return.)

Also: a shortcut tile is interactive even in view mode, but the chart-block `pointer-events-none` wrapper only applies in editing mode, so view-mode shortcuts navigate correctly. No further change.

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: green; baseline lint. (No shortcut items exist on any layout yet — Task 8 adds the picker — but the render path now supports them.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/ShortcutTile.tsx frontend/src/components/dashboard/DashboardGrid.tsx
git commit -m "feat(dashboard): shortcut tile renderer (#52 §3 P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Add-widget panel (core widgets + NAV shortcut catalog)

**Files:**
- Create `frontend/src/components/dashboard/AddWidgetPanel.tsx`
- Modify `frontend/src/components/dashboard/DashboardGrid.tsx` (open the panel from the edit toolbar)

- [ ] **Step 1: Create `AddWidgetPanel.tsx`**

```tsx
"use client"

import React, { useMemo, useState } from "react"
import { Plus, X } from "lucide-react"
import { WIDGET_REGISTRY } from "@/lib/dashboardWidgets"
import { shortcutCatalog, shortcutId } from "@/lib/dashboardShortcuts"
import { ALL_SECTIONS } from "@/lib/nav"
import type { GridItem } from "@/hooks/useDashboardLayout"

export default function AddWidgetPanel({ items, meta, onAdd, onClose }: {
  items: GridItem[]
  meta: { model: string | undefined; role: string }
  onAdd: (id: string) => void
  onClose: () => void
}) {
  const [tab, setTab] = useState<"widgets" | "shortcuts">("widgets")
  const present = useMemo(() => new Set(items.map(i => i.id)), [items])

  const coreWidgets = WIDGET_REGISTRY.filter(w => !w.pinned && !present.has(w.id))
  const catalog = useMemo(() => shortcutCatalog(meta.model, meta.role), [meta.model, meta.role])

  return (
    <div className="bg-white border border-[#ede9e2] rounded-xl p-3 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex items-center gap-1 text-xs">
          <button onClick={() => setTab("widgets")} className={`px-2.5 py-1 rounded-lg font-semibold ${tab === "widgets" ? "bg-[#faf6ec] text-[#b8943f]" : "text-[#1a1814]/55"}`}>Widgets</button>
          <button onClick={() => setTab("shortcuts")} className={`px-2.5 py-1 rounded-lg font-semibold ${tab === "shortcuts" ? "bg-[#faf6ec] text-[#b8943f]" : "text-[#1a1814]/55"}`}>Shortcuts</button>
        </div>
        <button onClick={onClose} className="ml-auto text-[#1a1814]/40 hover:text-[#1a1814]/70" aria-label="Close add-widget panel">
          <X className="w-4 h-4" />
        </button>
      </div>

      {tab === "widgets" && (
        <div className="flex flex-wrap gap-2">
          {coreWidgets.length === 0 && <p className="text-xs text-[#1a1814]/45">All widgets are on the dashboard.</p>}
          {coreWidgets.map(w => (
            <button key={w.id} onClick={() => onAdd(w.id)}
              className="inline-flex items-center gap-1 text-xs border border-[#ede9e2] rounded-lg px-2.5 py-1.5 hover:border-[#b8943f]/40 text-[#1a1814]/70">
              <Plus className="w-3.5 h-3.5 text-[#b8943f]" /> {w.title}
            </button>
          ))}
        </div>
      )}

      {tab === "shortcuts" && (
        <div className="space-y-3 max-h-72 overflow-y-auto">
          {ALL_SECTIONS.map(section => {
            const inSection = catalog.filter(i => i.section === section)
            if (inSection.length === 0) return null
            return (
              <div key={section}>
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/45 mb-1.5">{section}</p>
                <div className="flex flex-wrap gap-2">
                  {inSection.map(i => {
                    const id = shortcutId(i.href)
                    const added = present.has(id)
                    const Icon = i.icon
                    return (
                      <button key={i.href} disabled={added} onClick={() => onAdd(id)}
                        className={`inline-flex items-center gap-1 text-xs border rounded-lg px-2.5 py-1.5 ${added ? "border-[#ede9e2] text-[#1a1814]/30 cursor-default" : "border-[#ede9e2] text-[#1a1814]/70 hover:border-[#b8943f]/40"}`}>
                        <Icon className="w-3.5 h-3.5 text-[#b8943f]" /> {i.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Wire the panel into `DashboardGrid`'s edit toolbar**

In `DashboardGrid.tsx`:
- Add imports:
```tsx
import { Plus } from "lucide-react"
import AddWidgetPanel from "@/components/dashboard/AddWidgetPanel"
```
- Add state near the other `useState`:
```tsx
  const [adding, setAdding] = useState(false)
```
- Destructure `addWidget` and `meta` from the hook: change `const { items, applyLayout, removeWidget, reset, reload, save } = layout` to `const { items, meta, applyLayout, addWidget, removeWidget, reset, reload, save } = layout`.
- In the edit toolbar, add an "Add widget" button as the FIRST control in the `ml-auto` group (before Reset):
```tsx
            <button onClick={() => setAdding(a => !a)} className="inline-flex items-center gap-1 text-xs font-semibold text-[#b8943f] hover:text-[#a07f33] px-2 py-1">
              <Plus className="w-3.5 h-3.5" /> Add widget
            </button>
```
- Render the panel right BELOW the toolbar (inside `editing`, after the toolbar `</div>` and before the `{err && ...}` line):
```tsx
      {editing && adding && (
        <AddWidgetPanel
          items={items} meta={meta}
          onAdd={(id) => { addWidget(id); setAdding(false) }}
          onClose={() => setAdding(false)}
        />
      )}
```
- In the `.map` render, `meta` is now destructured, so change `renderItem(i, ctx, layout.meta, editing)` to `renderItem(i, ctx, meta, editing)`.

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: green; baseline lint. Customize → Add widget → pick a core widget or any form/report shortcut → it appears on the grid; Done persists.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/AddWidgetPanel.tsx frontend/src/components/dashboard/DashboardGrid.tsx
git commit -m "feat(dashboard): add-widget panel — core widgets + NAV shortcuts (#52 §3 P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Final verification

- [ ] **Step 1: Backend suite (unchanged, must stay green)**

Run: `cd backend && PYTHONPATH=. uv run pytest -q`
Expected: 369 passed (this work touches no backend code).

- [ ] **Step 2: Frontend build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline (2 errors / 14 warnings, all pre-existing/unrelated).

- [ ] **Step 3: Manual smoke (describe; do not automate)**

With `dev.sh` running, logged in, on `/dashboard`:
- Fresh user (or after Reset): default grid renders the core blocks; onboarding/alerts pinned above.
- A Phase-1 user's previously-saved show/hide survives as a grid (migration).
- Customize → drag a tile to a new spot; drag a chart's corner to resize (can't shrink below its min); remove a widget with ×.
- Add widget → Widgets tab adds a core widget; Shortcuts tab (grouped by section) adds e.g. "New Invoice" — the tile appears and, in view mode, clicking it navigates to `/invoices`.
- Done → reload page → layout persisted. Cancel → reverts. Reset → default.
- Resize the browser to mobile width → grid stacks to one column, read-only.

- [ ] **Step 4: Confirm @dnd-kit fully removed**

Run: `cd frontend && grep -r "@dnd-kit" src package.json || echo "clean"`
Expected: `clean` (no references remain).

---

## Self-review (completed at write time)

- **Spec coverage:** §2 Unit A (size/pinned) → Task 2; Unit B (shortcuts) → Task 3; Unit C (hook v2 + migration) → Task 4; Unit D (grid view+edit) → Tasks 5-6; Unit E (add panel) → Task 8; Unit F (ShortcutTile) → Task 7. §3 page composition (notices strip + grid) → Tasks 5-6. §4 edge cases: null/v1/v2/unknown/unavailable-shortcut/min-clamp → `resolveLayout`/`validateV2` (Task 4); save-fail banner → Task 6; mobile read-only → grid `isDraggable/Resizable={editing}` + xs col=1 (Tasks 5-6); RGL React-19 risk → Task 1. §5 testing: pure `resolveLayout`/`migrateV1toV2`/`packItems` (Task 4) + build/lint gate + Task 9 smoke. §6 file inventory matches Tasks 1-8. §7 phased order (2a Tasks 1-6, 2b Tasks 7-8) followed.
- **Type consistency:** `GridItem`/`GridLayoutV2`/`UseDashboardLayout`/`Meta` + `GRID_COLS` defined in Task 4 and consumed unchanged in Tasks 5-8. Hook return members used by the grid (`items, meta, applyLayout, addWidget, removeWidget, reset, reload, save, dirty`) all exist on `UseDashboardLayout` (Task 4). `WidgetDef.defaultSize/minSize/pinned` defined Task 2, read in Task 4 (`defaultGrid`/`migrate`/`validateV2`) and Task 5/6 (`minW/minH`). `isShortcutId/shortcutId/shortcutHref/resolveShortcut/shortcutCatalog` defined Task 3, used in Tasks 4/7/8. `ShortcutTile` props `{id,model,role,editing}` defined Task 7, called with those in Task 7 Step 2.
- **No placeholders in new code:** full verbatim for `dashboardShortcuts.ts`, the rewritten hook, `DashboardGrid` (both versions), `ShortcutTile`, `AddWidgetPanel`, and all page edits. The registry size additions are a complete value table + the exact chart class edits.
- **Ordering/standalone:** Task 4 leaves `DashboardCanvas`/`CustomizeBar` temporarily broken (documented) — resolved in Task 5 which deletes both. Every other task ends build-green + lint-baseline. Backend untouched throughout (Task 9 Step 1 re-confirms 369).
- **RGL specifics:** `WidthProvider(Responsive)`, `layouts`/`breakpoints`/`cols`, `onLayoutChange` guarded by `editing`, `draggableCancel=".no-drag"` so the remove button doesn't start a drag, CSS imports included. The remove button carries `no-drag`.
