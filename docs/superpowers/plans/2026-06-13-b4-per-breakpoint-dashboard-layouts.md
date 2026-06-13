# B4: Per-Breakpoint Dashboard Layouts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the dashboard layout schema from v2 (single flat item array) to v3 (per-breakpoint sparse overrides) so desktop/tablet/phone each remember their own arrangements without overwriting each other.

**Architecture:** Schema v3 is `{version:3, layouts:{lg: GridItem[], sm?: GridItem[], xs?: GridItem[]}}`. `lg` is canonical (defines membership); `sm`/`xs` exist only after the user drags/resizes at that width. Migration is pure in `resolveLayout` — backend stays untouched (opaque JSON store). `DashboardGrid` tracks active breakpoint; `onDragStop`/`onResizeStop` alone create overrides via `markCustomized`; `onLayoutChange` updates existing overrides but never creates new ones.

**Tech Stack:** TypeScript, React 19, react-grid-layout v2 (`react-grid-layout/legacy`), Next.js App Router, existing FastAPI backend (zero changes).

---

## Files

| File | Change |
|------|--------|
| `frontend/src/hooks/useDashboardLayout.ts` | Modify — new v3 types, `resolveLayout` v3 path, hook state/API |
| `frontend/src/components/dashboard/DashboardGrid.tsx` | Modify — breakpoint tracking, drag/resize stop handlers, toolbar label |
| `frontend/src/components/dashboard/AddWidgetPanel.tsx` | Modify — prop type `items: GridItem[]` → `items: Set<string>` (minor) |

No new files. Backend unchanged.

---

## Task 1: Add v3 types and update `resolveLayout`

**Files:**
- Modify: `frontend/src/hooks/useDashboardLayout.ts`

- [ ] **Step 1.1 — Add `Breakpoint` type and `GridLayoutV3`**

Open `frontend/src/hooks/useDashboardLayout.ts`. After the `GridLayoutV2` interface (line 10), add:

```ts
export type Breakpoint = "lg" | "sm" | "xs"
export const BP_COLS: Record<Breakpoint, number> = { lg: 4, sm: 2, xs: 1 }

export interface ResolvedLayouts {
  lg: GridItem[]
  sm?: GridItem[]
  xs?: GridItem[]
}

export interface GridLayoutV3 {
  version: 3
  layouts: ResolvedLayouts
}
```

- [ ] **Step 1.2 — Update `SavedAny` union to include v3**

Change:
```ts
type SavedAny = GridLayoutV2 | StoredLayoutV1 | Record<string, unknown> | null
```
to:
```ts
type SavedAny = GridLayoutV3 | GridLayoutV2 | StoredLayoutV1 | Record<string, unknown> | null
```

- [ ] **Step 1.3 — Add `validateBreakpoint` helper**

After `validateV2` (around line 69), add:

```ts
function validateBreakpoint(
  items: GridItem[],
  meta: Meta,
  lgIds: Set<string>,
  cols: number,
): GridItem[] {
  const seen = new Set<string>()
  const out: GridItem[] = []
  for (let it of items) {
    if (!it || typeof it.id !== "string" || seen.has(it.id)) continue
    if (!lgIds.has(it.id)) continue  // shared-membership invariant
    if (isShortcutId(it.id)) {
      if (!resolveShortcut(it.id, meta.model, meta.role)) continue
    } else {
      const def = registryById.get(it.id)
      if (!def || def.pinned) continue
      const minW = Math.min(def.minSize.w, cols)
      const minH = def.minSize.h
      if (it.w < minW) it = { ...it, w: minW }
      if (it.h < minH) it = { ...it, h: minH }
    }
    const maxW = cols
    if (it.w > maxW) it = { ...it, w: maxW }
    seen.add(it.id)
    out.push(it)
  }
  return out
}
```

- [ ] **Step 1.4 — Update `resolveLayout` to handle v3**

Replace the current `resolveLayout` function with:

```ts
export function resolveLayout(saved: SavedAny, meta: Meta): ResolvedLayouts {
  if (!saved || typeof saved !== "object") return { lg: defaultGrid() }
  const v = (saved as { version?: number }).version

  if (v === 3) {
    const s = saved as GridLayoutV3
    if (!Array.isArray(s.layouts?.lg)) return { lg: defaultGrid() }
    const lg = validateV2(s.layouts.lg, meta)
    if (lg.length === 0) return { lg: defaultGrid() }
    const lgIds = new Set(lg.map(i => i.id))
    const result: ResolvedLayouts = { lg }
    for (const bp of ["sm", "xs"] as const) {
      const raw = s.layouts[bp]
      if (!Array.isArray(raw)) continue
      const validated = validateBreakpoint(raw, meta, lgIds, BP_COLS[bp])
      if (validated.length > 0) result[bp] = validated
    }
    return result
  }

  if (v === 2 && Array.isArray((saved as GridLayoutV2).items)) {
    return { lg: validateV2((saved as GridLayoutV2).items, meta) }
  }
  if (v === 1 && Array.isArray((saved as StoredLayoutV1).widgets)) {
    return { lg: migrateV1toV2(saved as StoredLayoutV1) }
  }
  return { lg: defaultGrid() }
}
```

- [ ] **Step 1.5 — Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep useDashboardLayout
```

Expected: no errors from this file (other pre-existing errors are OK).

- [ ] **Step 1.6 — Commit**

```bash
git add frontend/src/hooks/useDashboardLayout.ts
git commit -m "feat(dashboard): v3 layout schema types + resolveLayout migration

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Update hook state and public API

**Files:**
- Modify: `frontend/src/hooks/useDashboardLayout.ts`

- [ ] **Step 2.1 — Update `UseDashboardLayout` interface**

Replace the existing `UseDashboardLayout` interface with:

```ts
export interface UseDashboardLayout {
  layouts: ResolvedLayouts
  meta: Meta
  loading: boolean
  dirty: boolean
  applyLayout: (bp: Breakpoint, allLayouts: Record<string, readonly { i: string; x: number; y: number; w: number; h: number }[]>) => void
  markCustomized: (bp: Breakpoint) => void
  addWidget: (id: string) => void
  removeWidget: (id: string) => void
  reset: () => void
  reload: () => void
  save: () => Promise<void>
}
```

- [ ] **Step 2.2 — Rewrite `useDashboardLayout` hook body**

Replace the entire `useDashboardLayout` function with:

```ts
export function useDashboardLayout(): UseDashboardLayout {
  const [layouts, setLayouts] = useState<ResolvedLayouts>(() => ({ lg: defaultGrid() }))
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
      setLayouts(resolveLayout(lay.layout, m))
    }).finally(() => setLoading(false))
  }, [])

  const applyLayout = (bp: Breakpoint, allLayouts: Record<string, readonly { i: string; x: number; y: number; w: number; h: number }[]>) => {
    setLayouts(prev => {
      const next = { ...prev }
      for (const key of Object.keys(allLayouts) as Breakpoint[]) {
        const arr = allLayouts[key]
        if (!arr) continue
        const mapped = arr.map(l => ({ id: l.i, x: l.x, y: l.y, w: l.w, h: l.h }))
        if (key === "lg") { next.lg = mapped; continue }
        if (prev[key]) next[key] = mapped  // only update if override already exists
      }
      return next
    })
  }

  const markCustomized = (bp: Breakpoint) => {
    if (bp === "lg") return  // lg is always present
    setLayouts(prev => {
      if (prev[bp]) return prev  // already an override, nothing to do
      // Promote: derive from lg with column clamping
      const cols = BP_COLS[bp]
      const lgIds = new Set(prev.lg.map(i => i.id))
      const derived = validateBreakpoint(prev.lg, meta, lgIds, cols)
      return { ...prev, [bp]: derived }
    })
  }

  const addWidget = (id: string) => setLayouts(prev => {
    if (prev.lg.some(i => i.id === id)) return prev
    const def = registryById.get(id)
    const size = def ? def.defaultSize : { w: 1, h: 1 }
    const newLg: GridItem[] = [
      ...prev.lg,
      { id, x: 0, y: prev.lg.reduce((m, i) => Math.max(m, i.y + i.h), 0), w: size.w, h: size.h }
    ]
    const next: ResolvedLayouts = { lg: newLg }
    for (const bp of ["sm", "xs"] as const) {
      if (!prev[bp]) continue
      const cols = BP_COLS[bp]
      const w = Math.min(size.w, cols)
      const y = prev[bp]!.reduce((m, i) => Math.max(m, i.y + i.h), 0)
      next[bp] = [...prev[bp]!, { id, x: 0, y, w, h: size.h }]
    }
    return next
  })

  const removeWidget = (id: string) => setLayouts(prev => {
    const next: ResolvedLayouts = { lg: prev.lg.filter(i => i.id !== id) }
    for (const bp of ["sm", "xs"] as const) {
      if (prev[bp]) next[bp] = prev[bp]!.filter(i => i.id !== id)
    }
    return next
  })

  const reset = () => setLayouts({ lg: defaultGrid() })
  const reload = () => setLayouts(resolveLayout(saved, meta))

  const save = async () => {
    const payload: GridLayoutV3 = { version: 3, layouts }
    await apiFetch("/api/dashboard/layout", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout: payload }),
    })
    setSaved(payload)
  }

  const baseline = resolveLayout(saved, meta)
  const dirty = JSON.stringify(layouts) !== JSON.stringify(baseline)

  return { layouts, meta, loading, dirty, applyLayout, markCustomized, addWidget, removeWidget, reset, reload, save }
}
```

- [ ] **Step 2.3 — Remove the now-unused `serialize` helper** (it was only used for the old `dirty` comparison)

Delete these lines:
```ts
function serialize(items: GridItem[]): string {
  return JSON.stringify(items.map(i => ({ id: i.id, x: i.x, y: i.y, w: i.w, h: i.h })))
}
```

- [ ] **Step 2.4 — Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "useDashboardLayout|GridItem|ResolvedLayouts"
```

Expected: no errors from this file.

- [ ] **Step 2.5 — Commit**

```bash
git add frontend/src/hooks/useDashboardLayout.ts
git commit -m "feat(dashboard): per-breakpoint hook state + API (applyLayout/markCustomized)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Update `DashboardGrid` for breakpoint tracking

**Files:**
- Modify: `frontend/src/components/dashboard/DashboardGrid.tsx`

- [ ] **Step 3.1 — Import new types and update imports**

Change the import from `useDashboardLayout`:
```ts
import type { GridItem, UseDashboardLayout } from "@/hooks/useDashboardLayout"
import { GRID_COLS } from "@/hooks/useDashboardLayout"
```
to:
```ts
import type { UseDashboardLayout } from "@/hooks/useDashboardLayout"
import { GRID_COLS, BP_COLS, type Breakpoint } from "@/hooks/useDashboardLayout"
```

- [ ] **Step 3.2 — Add `activeBp` state, derive `rglLayouts`**

Inside `DashboardGrid`, add state for the active breakpoint after the existing `useState` calls:

```ts
const [activeBp, setActiveBp] = useState<Breakpoint>("lg")
```

Replace the existing `rglLayout` derivation:
```ts
const rglLayout: LayoutItem[] = items.map(i => {
  const def = registryById.get(i.id)
  return { i: i.id, x: i.x, y: i.y, w: i.w, h: i.h, minW: def?.minSize.w ?? 1, minH: def?.minSize.h ?? 1 }
})
```
with:
```ts
const { layouts, meta, applyLayout, markCustomized, addWidget, removeWidget, reset, reload, save } = layout

function toRglItems(items: readonly { id: string; x: number; y: number; w: number; h: number }[], cols: number): LayoutItem[] {
  return items.map(i => {
    const def = registryById.get(i.id)
    const minW = Math.min(def?.minSize.w ?? 1, cols)
    const minH = def?.minSize.h ?? 1
    return { i: i.id, x: i.x, y: i.y, w: i.w, h: i.h, minW, minH }
  })
}

const rglLayouts: Record<string, LayoutItem[]> = {
  lg: toRglItems(layouts.lg, BP_COLS.lg),
  ...(layouts.sm ? { sm: toRglItems(layouts.sm, BP_COLS.sm) } : {}),
  ...(layouts.xs ? { xs: toRglItems(layouts.xs, BP_COLS.xs) } : {}),
}
```

- [ ] **Step 3.3 — Remove the old destructuring of `layout`**

Remove:
```ts
const { items, meta, applyLayout, addWidget, removeWidget, reset, reload, save } = layout
```

This is now handled in step 3.2 above (but with `layouts` instead of `items`).

- [ ] **Step 3.4 — Update `AddWidgetPanel` call**

The `items` prop currently passes `items`. Change it to pass `layouts.lg`:
```tsx
<AddWidgetPanel
  items={layouts.lg} meta={meta}
  onAdd={(id) => { addWidget(id); setAdding(false) }}
  onClose={() => setAdding(false)}
/>
```

- [ ] **Step 3.5 — Update `ResponsiveGridLayout` props + add handlers**

Replace the `<ResponsiveGridLayout ...>` opening tag with:

```tsx
<ResponsiveGridLayout
  className="layout"
  layouts={rglLayouts}
  breakpoints={{ lg: 1024, sm: 640, xs: 0 }}
  cols={{ lg: BP_COLS.lg, sm: BP_COLS.sm, xs: BP_COLS.xs }}
  rowHeight={96}
  margin={[12, 12]}
  compactType="vertical"
  isDraggable={editing}
  isResizable={editing}
  onBreakpointChange={(bp: string) => setActiveBp(bp as Breakpoint)}
  onLayoutChange={(_l: Layout, all: Record<string, Layout>) => {
    if (editing) applyLayout(activeBp, all)
  }}
  onDragStop={(_l: Layout, _o: LayoutItem, _n: LayoutItem, _p: LayoutItem, _e: MouseEvent, _el: HTMLElement, all: Record<string, Layout>) => {
    markCustomized(activeBp)
    applyLayout(activeBp, all)
  }}
  onResizeStop={(_l: Layout, _o: LayoutItem, _n: LayoutItem, _p: LayoutItem, _e: MouseEvent, _el: HTMLElement, all: Record<string, Layout>) => {
    markCustomized(activeBp)
    applyLayout(activeBp, all)
  }}
  draggableCancel=".no-drag"
>
```

- [ ] **Step 3.6 — Update the items map to use `layouts.lg`**

Change `{items.map(i => (` to `{layouts.lg.map(i => (`.

- [ ] **Step 3.7 — Add breakpoint label to the editing toolbar**

Inside the `{editing && (...)}` toolbar div, after the `<span>` that says "Customizing dashboard", add:

```tsx
<span className="text-[11px] text-[#b8943f]/70 font-semibold">
  {activeBp === "lg" ? "Desktop layout" : activeBp === "sm" ? "Tablet layout" : "Phone layout"}
</span>
```

- [ ] **Step 3.8 — Verify TypeScript compiles with no new errors**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "DashboardGrid|AddWidgetPanel" | head -20
```

Expected: no new errors from these files.

- [ ] **Step 3.9 — Commit**

```bash
git add frontend/src/components/dashboard/DashboardGrid.tsx
git commit -m "feat(dashboard): per-breakpoint tracking in DashboardGrid

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Fix `AddWidgetPanel` consumer and build verification

**Files:**
- Modify: `frontend/src/components/dashboard/AddWidgetPanel.tsx`

- [ ] **Step 4.1 — The `present` set is still built from `items.map(i => i.id)` — verify no change needed**

`AddWidgetPanel` receives `items: GridItem[]` and does `items.map(i => i.id)`. Since we're passing `layouts.lg` (a `GridItem[]`), the type is unchanged. No edit needed here.

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep AddWidgetPanel
```

Expected: no errors.

- [ ] **Step 4.2 — Full build check**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds. Any errors from pre-existing lint issues are OK; no NEW errors.

- [ ] **Step 4.3 — Lint check**

```bash
cd frontend && npm run lint 2>&1 | tail -20
```

Expected: same baseline as before (2 errors / 14 warnings, all pre-existing).

- [ ] **Step 4.4 — Commit**

```bash
git add frontend/src/components/dashboard/AddWidgetPanel.tsx
git commit -m "feat(dashboard): B4 build+lint verification pass

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Manual verification + ROADMAP update

**Files:**
- Modify: `docs/ROADMAP.md`

- [ ] **Step 5.1 — Start dev servers and open the dashboard**

```bash
cd backend && python main.py &
cd frontend && npm run dev
```

Open `http://localhost:3000/dashboard`.

- [ ] **Step 5.2 — Verify v2 load (existing users)**

Existing users have a v2 blob in their stored layout. Check that the dashboard renders normally with no console errors.

- [ ] **Step 5.3 — Verify desktop-only edit does NOT create sm/xs overrides**

1. Click "Customize dashboard".
2. Drag a widget to a new position.
3. Click "Done".
4. Open browser DevTools → Network → find the PUT `/api/dashboard/layout` request.
5. Inspect the request payload — confirm it is `{version:3, layouts:{lg:[...]}}` with NO `sm` or `xs` keys.

- [ ] **Step 5.4 — Verify narrow-window drag creates an override**

1. Resize browser window to ~500px wide (tablet/sm breakpoint).
2. Click "Customize dashboard" — confirm toolbar shows "Tablet layout".
3. Drag a widget.
4. Click "Done".
5. Inspect PUT payload — confirm `sm` key is now present alongside `lg`.

- [ ] **Step 5.5 — Verify desktop re-edit leaves mobile override untouched**

1. Resize back to full width.
2. Click "Customize dashboard" and drag a widget.
3. Click "Done".
4. Inspect PUT payload — confirm `sm` override is still present and unchanged.

- [ ] **Step 5.6 — Verify add/remove propagates**

1. In customize mode, add a widget via "+ Add widget".
2. Click "Done".
3. Inspect payload — new widget id appears in `lg` and in `sm` (if override exists).

- [ ] **Step 5.7 — Verify reset clears overrides**

1. In customize mode, click "Reset".
2. Click "Done".
3. Inspect payload — should be `{version:3, layouts:{lg:[...defaultGrid...]}}` with no `sm`/`xs`.

- [ ] **Step 5.8 — Mark B4 shipped in ROADMAP**

In `docs/ROADMAP.md`, find the B4 entry and update its status marker to ✅ Shipped with today's date.

- [ ] **Step 5.9 — Final commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs(roadmap): mark B4 per-breakpoint dashboard layouts shipped

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Merge

- [ ] **Step 6.1 — Run backend tests to confirm zero regressions**

```bash
cd backend && PYTHONPATH=. uv run pytest -q 2>&1 | tail -5
```

Expected: 372 passed.

- [ ] **Step 6.2 — Invoke finishing-a-development-branch skill**

```
/finishing-a-development-branch
```
