import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { getCurrentUser } from "@/lib/auth"
import { WIDGET_REGISTRY, type WidgetDef } from "@/lib/dashboardWidgets"
import { isShortcutId, resolveShortcut } from "@/lib/dashboardShortcuts"

export const GRID_COLS = 4

export interface GridItem { id: string; x: number; y: number; w: number; h: number }
export interface GridLayoutV2 { version: 2; items: GridItem[] }

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

// Phase-1 shapes (for migration only)
interface StoredWidgetV1 { id: string; visible: boolean }
interface StoredLayoutV1 { version: 1; widgets: StoredWidgetV1[] }

type Meta = { model: string | undefined; role: string }
type SavedAny = GridLayoutV3 | GridLayoutV2 | StoredLayoutV1 | Record<string, unknown> | null

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
  return packItems(
    gridDefs
      .filter(d => d.defaultOnGrid !== false)
      .map(d => ({ id: d.id, w: d.defaultSize.w, h: d.defaultSize.h })),
  )
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

/** Resolve a saved blob (null | v1 | v2 | v3) into validated layouts by breakpoint. */
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

function serialize(items: GridItem[]): string {
  return JSON.stringify(items.map(i => ({ id: i.id, x: i.x, y: i.y, w: i.w, h: i.h })))
}

export interface UseDashboardLayout {
  items: GridItem[]
  meta: Meta
  loading: boolean
  dirty: boolean
  applyLayout: (layout: readonly { i: string; x: number; y: number; w: number; h: number }[]) => void
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

  const applyLayout = (layout: readonly { i: string; x: number; y: number; w: number; h: number }[]) =>
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
