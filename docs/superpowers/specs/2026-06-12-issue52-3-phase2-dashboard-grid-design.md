# #52 §3 Phase 2 — Resizable dashboard grid + shortcut tiles · Design

**Date:** 2026-06-12
**Builds on:** Phase 1 (`2026-06-12-issue52-3-customizable-dashboard-design.md`, shipped in merge `8e6a896`).
**Effort:** L · **Priority:** follows directly from the Phase-1 ship, per user direction.

## §1 · Goal & scope

Turn the dashboard into a **personal quick-access workspace**: every widget — the
existing analytical blocks AND new shortcut tiles to any form/report — lives in a
single **draggable, resizable grid**, with each tile sized to the user's need
(1×1, 1×2, 2×2, 2×3, 3×2 …). The layout is saved per user (the Phase-1 store,
unchanged).

**Locked decisions (brainstorming 2026-06-12):**

1. **Grid model:** free draggable + resizable grid via **`react-grid-layout`**
   (replaces the Phase-1 single-column `@dnd-kit` sortable). 4 columns desktop /
   2 tablet / 1 mobile; fixed row height.
2. **Shortcut tiles:** a tile can be any item from the **`NAV` catalog**
   (`lib/nav.ts`), auto-filtered to the user's business model + role. A shortcut
   tile is icon + label and **navigates** on click (pure quick-access — no new
   backend).
3. **Unified grid:** existing block widgets and shortcut tiles are all grid
   items. Each widget declares a **default size + minimum size** ("subject to
   widget need"); RGL enforces the minimum during resize.
4. **Notices pinned:** the Onboarding checklist and Action Alerts are *transient
   notifications*, not dashboard content — they render in a **fixed strip above
   the grid** (not draggable/resizable), so the grid never shows holes when they
   self-hide.
5. **One spec, phased plan:** internal order is **2a** (grid engine + adapt
   existing widgets + v2 schema/migration) then **2b** (shortcut catalog +
   add-widget picker). One branch, reviewable stages.

**Out of scope (YAGNI):** live metrics/counts on shortcut tiles (deferred —
Phase 1 of a future "smart tiles"), embedded mini-reports, per-breakpoint custom
layouts (we store one desktop layout; RGL derives smaller breakpoints),
cross-user/tenant template sharing, widget-level color theming.

## §2 · Architecture

```
dashboard/page.tsx
  ├─ fetches /api/reports/dashboard + /dashboard/charts        (UNCHANGED)
  ├─ pinned notices strip: onboarding + alerts (render fns, fixed, above grid)
  ├─ useDashboardLayout()  ──▶ GET/PUT /api/dashboard/layout   (backend UNCHANGED)
  │     └─ resolveLayout(saved, {model, role}): handles null | v1 | v2  →  GridItem[]
  │           └─ migrateV1toV2(v1)  (pure)
  └─ <DashboardGrid>  — react-grid-layout Responsive; view + edit modes
        ├─ renders each item:  block widget (WIDGET_REGISTRY[id].render(ctx))
        │                       or shortcut (ShortcutTile by href)
        └─ <AddWidgetPanel>  (edit mode) — core widgets not placed + NAV catalog
```

### Unit A — registry additions (`lib/dashboardWidgets.tsx`)

`WidgetDef` gains size + placement metadata:

```ts
export interface WidgetSize { w: number; h: number }
export interface WidgetDef {
  id: string
  title: string
  defaultSize: WidgetSize          // grid cells on the 4-col desktop grid
  minSize: WidgetSize
  pinned?: boolean                 // rendered in the fixed notices strip, NOT a grid item
  conditional?: boolean            // render() may return null (e.g. ar_aging when no data)
  render: (ctx: WidgetContext) => React.ReactNode
}
```

Representative sizes (final px tuning in the plan; `rowHeight ≈ 96px`, 4 cols):

| id | default (w×h) | min | notes |
|----|---------------|-----|-------|
| `primary_kpis` | 4×2 | 2×2 | inner card grid stays responsive |
| `secondary_kpis` | 4×2 | 2×2 | |
| `ar_aging` (conditional) | 2×3 | 2×2 | |
| `monthly_rev_exp` | 2×3 | 2×2 | chart fills cell |
| `net_profit_trend` | 2×3 | 2×2 | |
| `expense_breakdown` | 2×3 | 2×2 | |
| `top_customers` | 2×3 | 2×2 | |
| `recent_transactions` | 4×3 | 2×2 | |
| `quick_actions` | 4×1 | 2×1 | superseded by shortcuts; user may remove |
| `onboarding` (**pinned**) | — | — | fixed strip |
| `alerts` (**pinned**) | — | — | fixed strip |

**Chart cell-fill adaptation:** the four chart render fns + `ar_aging` currently
use fixed-height containers (`h-48 sm:h-56`, `h-52`, `h-36`). They change to
`h-full` inside a flex-column card so the chart scales with its grid cell.
`maintainAspectRatio:false` already set → no other chart change needed.

### Unit B — shortcuts (`lib/dashboardShortcuts.ts`, new)

```ts
const SHORTCUT_PREFIX = "shortcut:"
export const isShortcutId = (id: string) => id.startsWith(SHORTCUT_PREFIX)
export const shortcutHref = (id: string) => id.slice(SHORTCUT_PREFIX.length)
export const shortcutId = (href: string) => `${SHORTCUT_PREFIX}${href}`

/** NAV items the user may add as shortcuts, filtered by model + role,
 *  grouped by section. Reuses the same filter as the sidebar. */
export function shortcutCatalog(model: string | undefined, role: string): NavItem[]

/** Resolve a shortcut id to its NAV item, or null if no longer available
 *  (e.g. the user's model changed and the route is gone). */
export function resolveShortcut(id: string, model, role): NavItem | null
```

Default size for any shortcut: `1×1`, min `1×1` (max width 2 enforced in UI).

### Unit C — layout hook + migration (`hooks/useDashboardLayout.ts`, rewritten)

Schema **v2**:

```ts
export interface GridItem { id: string; x: number; y: number; w: number; h: number }
export interface GridLayoutV2 { version: 2; items: GridItem[] }
```

- `resolveLayout(saved, { model, role })` returns the resolved `GridItem[]` plus the
  def/render for each, handling three inputs (model+role are needed only to validate
  shortcut availability):
  - `null` → `DEFAULT_GRID` (a curated arrangement constant of the core block
    widgets at their default sizes).
  - `{version:1,…}` → `migrateV1toV2`: the Phase-1 *visible* widgets, in saved
    order, stacked full-width at their `defaultSize` (preserving each user's
    show/hide choice as a starting grid).
  - `{version:2,…}` → used as-is, then **validated**: drop block ids not in the
    registry or marked `pinned`; drop shortcut ids that no longer resolve
    (`resolveShortcut` → null); clamp each item to its `minSize`.
- `migrateV1toV2` and `resolveLayout` are **pure, exported** functions (the
  highest-risk logic; isolated so it's obvious and future-testable).
- Mutators exposed: `setItems(items)` (from RGL `onLayoutChange`),
  `addWidget(id)` (core or shortcut, placed at next free row at default size),
  `removeWidget(id)`, `reset()`, `reload()`, `save()`, plus `dirty`.
- Backend round-trip unchanged: `save()` PUTs `{layout: {version:2, items}}`.

### Unit D — grid + customize (`components/dashboard/DashboardGrid.tsx`, new)

Replaces `DashboardCanvas.tsx` and `CustomizeBar.tsx` (both removed).

- Uses `react-grid-layout`'s `Responsive` + `WidthProvider`. `breakpoints
  {lg:1024, sm:640, xs:0}` → `cols {lg:4, sm:2, xs:1}`. We store **one** layout
  (desktop `lg`); RGL derives `sm`/`xs` by stacking. `rowHeight` ≈ 96,
  `margin [12,12]`.
- **View mode:** `isDraggable={false} isResizable={false}`. Each grid cell renders
  the block widget (`WIDGET_REGISTRY[id].render(ctx)`) or a `<ShortcutTile>`.
- **Edit mode:** `isDraggable isResizable` on (desktop/tablet only; `xs` read-only).
  Each tile gets a remove (×) button and a drag affordance; `onLayoutChange` →
  `setItems`. An **"+ Add widget"** opens `<AddWidgetPanel>`. Footer: **Done**
  (save → exit), **Cancel** (reload → exit), **Reset to default**.
- `react-grid-layout/css/styles.css` + `react-resizable/css/styles.css` imported
  once (in the grid component or globals).

### Unit E — add-widget picker (`components/dashboard/AddWidgetPanel.tsx`, new)

A panel (in edit mode) with two groups:
- **Widgets** — core `WIDGET_REGISTRY` entries (non-`pinned`) not already on the
  grid; clicking adds at default size.
- **Shortcuts** — `shortcutCatalog(model, role)` grouped by section; clicking adds
  `shortcutId(href)`. A shortcut already on the grid is shown disabled (no dupes).

### Unit F — shortcut tile (`components/dashboard/ShortcutTile.tsx`, new)

Given a `href`, looks up the `NAV` item (icon + label) and renders a compact tile.
View mode: a `next/link` that navigates. Edit mode: navigation suppressed
(`pointer-events-none` on the inner content; the cell handles drag), consistent
with Phase-1's edit-preview pattern.

## §3 · page.tsx composition

```
<header>  title + DateRangePicker + Customize button </header>
{error banner}
<NoticesStrip>          // pinned: onboarding.render(ctx), alerts.render(ctx)
<DashboardGrid editing ctx layout={layout} onDoneEditing/>
```

The data-fetch + chart-config (`ctx`) logic is **unchanged** from Phase 1; only the
render target changes (grid instead of canvas) and the two pinned notices move to a
strip.

## §4 · Error handling & edge cases

| Case | Behavior |
|------|----------|
| No saved layout | `DEFAULT_GRID` (curated core arrangement). |
| Saved v1 (Phase-1 user) | `migrateV1toV2` → grid from visible widgets at default sizes. |
| Layout fetch fails | Fall back to `DEFAULT_GRID`; dashboard still works. |
| v2 item: unknown/pinned block id | Dropped by validation. |
| v2 item: shortcut to a now-unavailable route (model/role change) | Dropped (`resolveShortcut` → null). |
| Conditional block (`ar_aging`) with no data | `render` returns null → empty cell content (cell remains, no crash); acceptable. |
| Resize below min | RGL clamps to `minSize`. |
| Mobile (`xs`) | Single-column stack, read-only (no drag/resize); customization on ≥ tablet. |
| Save (PUT) fails | Inline error in edit-mode footer; stays in edit mode; local state preserved. |
| react-grid-layout React-19 peer-dep conflict | First implementation step verifies install; fallback `gridstack` (same v2 schema) — decided before building UI. |

## §5 · Testing

**Backend:** unchanged. The store is opaque, so the existing Phase-1 round-trip +
isolation tests already cover a v2-shaped blob. No new backend tests required (the
existing 5 stay green).

**Frontend** (no JS unit runner — gate = `npm run build` + `npm run lint` at the
repo baseline of 2 errors / 14 warnings):
- `migrateV1toV2` and `resolveLayout` written as **pure exported** functions; their
  branch logic (null / v1 / v2-validate / clamp) is the riskiest code — keep it
  isolated and obvious. Manual smoke verifies each branch.
- Manual smoke checklist: fresh user sees `DEFAULT_GRID`; a Phase-1 user's saved
  show/hide survives as a grid; drag + resize a chart (can't go below min); add a
  shortcut from the catalog and click it (navigates); remove a widget; Done
  persists across reload; Cancel reverts; Reset restores default; mobile stacks
  read-only.

## §6 · File inventory

**New:**
- `frontend/src/lib/dashboardShortcuts.ts`
- `frontend/src/components/dashboard/DashboardGrid.tsx`
- `frontend/src/components/dashboard/AddWidgetPanel.tsx`
- `frontend/src/components/dashboard/ShortcutTile.tsx`

**Modified:**
- `frontend/src/lib/dashboardWidgets.tsx` — `WidgetDef` size/pinned fields;
  per-widget defaults; `pinned:true` on onboarding+alerts; chart `h-full` fill.
- `frontend/src/hooks/useDashboardLayout.ts` — v2 schema, `migrateV1toV2`,
  validated `resolveLayout`, grid mutators.
- `frontend/src/app/(dashboard)/dashboard/page.tsx` — notices strip + `<DashboardGrid>`.
- `frontend/package.json` — add `react-grid-layout` (+ `react-resizable`); remove
  `@dnd-kit/*` (Phase-1 sortable retired).

**Removed:**
- `frontend/src/components/dashboard/DashboardCanvas.tsx`
- `frontend/src/components/dashboard/CustomizeBar.tsx`

**Unchanged:** backend store/endpoints/tests; both dashboard data endpoints;
`lib/nav.ts` (read as the shortcut catalog); KPI/chart sub-components.

## §7 · Implementation order (for the plan)

**Phase 2a — grid engine + existing widgets**
1. Install `react-grid-layout`; verify React-19 compatibility (fallback decision).
2. `WidgetDef` size/pinned fields + per-widget defaults + chart `h-full`.
3. v2 schema + `migrateV1toV2` + validated `resolveLayout` (pure) + hook mutators.
4. `DashboardGrid` view mode (renders block widgets in the grid from layout).
5. `page.tsx`: notices strip + grid; remove `DashboardCanvas`.
6. Grid edit mode: drag/resize/remove + Done/Cancel/Reset (save-on-Done);
   remove `CustomizeBar`.

**Phase 2b — shortcuts**
7. `lib/dashboardShortcuts.ts` (catalog filter + id helpers + resolve).
8. `ShortcutTile` + grid renders shortcut items.
9. `AddWidgetPanel` (core widgets + NAV shortcut catalog) wired into edit mode.

**Close**
10. Verify: backend suite green (unchanged), `npm run build` + `npm run lint` at
    baseline; manual smoke of the §5 checklist.
