/**
 * Pure layout helpers for the dual-home dashboard (v4).
 * Kept free of React so vitest can cover migration / defaults.
 */
import { ALL_QUICK_ACTIONS, WIDGET_REGISTRY, type WidgetDef } from "@/lib/dashboardWidgets"
import { isShortcutId, resolveShortcut } from "@/lib/dashboardShortcuts"
import {
  type DashboardView,
  DEFAULT_FINANCIAL_QUICK_ACTIONS,
  DEFAULT_OPS_QUICK_ACTIONS,
} from "@/lib/dashboardHome"

export const GRID_COLS = 4
export type Breakpoint = "lg" | "sm" | "xs"
export const BP_COLS: Record<Breakpoint, number> = { lg: 4, sm: 2, xs: 1 }

export interface GridItem { id: string; x: number; y: number; w: number; h: number }

export interface ResolvedLayouts {
  lg: GridItem[]
  sm?: GridItem[]
  xs?: GridItem[]
}

export interface DashboardSlice {
  layouts: ResolvedLayouts
  dismissed: string[]
  quickActions: string[]
}

export interface GridLayoutV3 {
  version: 3
  layouts: ResolvedLayouts
  dismissed?: string[]
  quickActions?: string[]
}

export interface GridLayoutV2 { version: 2; items: GridItem[] }

export interface GridLayoutV4 {
  version: 4
  activeView?: DashboardView
  dashboards: {
    financial: {
      layouts: ResolvedLayouts
      dismissed?: string[]
      quickActions?: string[]
    }
    operations: {
      layouts: ResolvedLayouts
      dismissed?: string[]
      quickActions?: string[]
    }
  }
}

interface StoredWidgetV1 { id: string; visible: boolean }
interface StoredLayoutV1 { version: 1; widgets: StoredWidgetV1[] }

export type Meta = { model: string | undefined; role: string; installedModules: Set<string> }
export type SavedAny = GridLayoutV4 | GridLayoutV3 | GridLayoutV2 | StoredLayoutV1 | Record<string, unknown> | null

const registryById = new Map<string, WidgetDef>(WIDGET_REGISTRY.map(w => [w.id, w]))

function widgetHome(def: WidgetDef): DashboardView | "both" {
  return def.home ?? "financial"
}

function matchesView(def: WidgetDef, view: DashboardView): boolean {
  const h = widgetHome(def)
  return h === "both" || h === view
}

function gridDefsFor(view: DashboardView): WidgetDef[] {
  return WIDGET_REGISTRY.filter(w => !w.pinned && matchesView(w, view))
}

/** Shelf-pack {id,w,h} entries into a BP_COLS.lg-wide layout (left→right, wrap). */
export function packItems(sized: { id: string; w: number; h: number }[]): GridItem[] {
  const items: GridItem[] = []
  let x = 0, y = 0, rowH = 0
  for (const s of sized) {
    const w = Math.min(s.w, BP_COLS.lg)
    if (x + w > BP_COLS.lg) { x = 0; y += rowH; rowH = 0 }
    items.push({ id: s.id, x, y, w, h: s.h })
    x += w; rowH = Math.max(rowH, s.h)
  }
  return items
}

export function defaultQuickActions(view: DashboardView): string[] {
  return view === "operations"
    ? [...DEFAULT_OPS_QUICK_ACTIONS]
    : [...DEFAULT_FINANCIAL_QUICK_ACTIONS]
}

export function defaultGrid(view: DashboardView, installedModules?: Set<string>): GridItem[] {
  const mods = installedModules ?? new Set(["base"])
  return packItems(
    gridDefsFor(view)
      .filter(d => d.defaultOnGrid !== false)
      .filter(d => !d.requiredModule || mods.has(d.requiredModule))
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

function validateV2(items: GridItem[], meta: Meta, view: DashboardView): GridItem[] {
  const seen = new Set<string>()
  const out: GridItem[] = []
  for (let it of items) {
    if (!it || typeof it.id !== "string" || seen.has(it.id)) continue
    if (isShortcutId(it.id)) {
      if (!resolveShortcut(it.id, meta.installedModules, meta.role)) continue
    } else {
      const def = registryById.get(it.id)
      if (!def || def.pinned) continue
      if (!matchesView(def, view)) continue
      if (def.requiredModule && !meta.installedModules.has(def.requiredModule)) continue
      if (it.w < def.minSize.w) it = { ...it, w: def.minSize.w }
      if (it.h < def.minSize.h) it = { ...it, h: def.minSize.h }
    }
    seen.add(it.id)
    out.push(it)
  }
  return out
}

export function validateBreakpoint(
  items: GridItem[],
  meta: Meta,
  lgIds: Set<string>,
  cols: number,
  view: DashboardView,
): GridItem[] {
  const seen = new Set<string>()
  const out: GridItem[] = []
  for (let it of items) {
    if (!it || typeof it.id !== "string" || seen.has(it.id)) continue
    if (!lgIds.has(it.id)) continue
    if (isShortcutId(it.id)) {
      if (!resolveShortcut(it.id, meta.installedModules, meta.role)) continue
    } else {
      const def = registryById.get(it.id)
      if (!def || def.pinned) continue
      if (!matchesView(def, view)) continue
      if (def.requiredModule && !meta.installedModules.has(def.requiredModule)) continue
      const minW = Math.min(def.minSize.w, cols)
      const minH = def.minSize.h
      if (it.w < minW) it = { ...it, w: minW }
      if (it.h < minH) it = { ...it, h: minH }
    }
    if (it.w > cols) it = { ...it, w: cols }
    seen.add(it.id)
    out.push(it)
  }
  return out
}

function injectMissingDefaults(
  lg: GridItem[],
  dismissed: Set<string>,
  view: DashboardView,
  installedModules?: Set<string>,
): GridItem[] {
  const mods = installedModules ?? new Set(["base"])
  const present = new Set(lg.map(i => i.id))
  const missing = gridDefsFor(view).filter(
    d =>
      d.defaultOnGrid !== false &&
      !present.has(d.id) &&
      !dismissed.has(d.id) &&
      (!d.requiredModule || mods.has(d.requiredModule)),
  )
  if (missing.length === 0) return lg
  const baseY = lg.reduce((m, i) => Math.max(m, i.y + i.h), 0)
  const packed = packItems(missing.map(d => ({ id: d.id, w: d.defaultSize.w, h: d.defaultSize.h })))
  return [...lg, ...packed.map(i => ({ ...i, y: i.y + baseY }))]
}

const KPI_H1_IDS = new Set(["primary_kpis", "secondary_kpis", "quick_actions", "alerts", "ops_primary_kpis", "ops_quick_actions"])

function clampKpi(items: GridItem[]): GridItem[] {
  return items.map(i => KPI_H1_IDS.has(i.id) && i.h > 1 ? { ...i, h: 1 } : i)
}

/** Resolve a single-view layout blob (v1/v2/v3-shaped) into validated layouts. */
export function resolveSliceLayout(
  saved: { layouts?: ResolvedLayouts; items?: GridItem[]; widgets?: StoredWidgetV1[]; version?: number; dismissed?: string[] } | null | undefined,
  meta: Meta,
  view: DashboardView,
): ResolvedLayouts {
  if (!saved || typeof saved !== "object") return { lg: defaultGrid(view, meta.installedModules) }

  if (Array.isArray(saved.layouts?.lg)) {
    const dismissed = new Set<string>(Array.isArray(saved.dismissed) ? saved.dismissed : [])
    const validated = validateV2(clampKpi(saved.layouts.lg), meta, view)
    if (validated.length === 0) return { lg: defaultGrid(view, meta.installedModules) }
    const lg = injectMissingDefaults(validated, dismissed, view, meta.installedModules)
    const lgIds = new Set(lg.map(i => i.id))
    const result: ResolvedLayouts = { lg }
    for (const bp of ["sm", "xs"] as const) {
      const raw = saved.layouts?.[bp]
      if (!Array.isArray(raw)) continue
      const bpValidated = validateBreakpoint(clampKpi(raw), meta, lgIds, BP_COLS[bp], view)
      if (bpValidated.length > 0) result[bp] = bpValidated
    }
    return result
  }

  if (Array.isArray(saved.items)) {
    return { lg: validateV2(saved.items, meta, view) }
  }
  if (Array.isArray(saved.widgets)) {
    return { lg: migrateV1toV2({ version: 1, widgets: saved.widgets }) }
  }
  return { lg: defaultGrid(view, meta.installedModules) }
}

/** Legacy resolveLayout — treats blob as financial v1–v3. */
export function resolveLayout(saved: SavedAny, meta: Meta): ResolvedLayouts {
  return resolveSliceLayout(saved as GridLayoutV3 | null, meta, "financial")
}

export function emptySlice(view: DashboardView, meta: Meta): DashboardSlice {
  const qa = defaultQuickActions(view).filter(id => {
    const def = ALL_QUICK_ACTIONS.find(a => a.id === id)
    if (!def) return false
    if (!def.requiredModule) return true
    return meta.installedModules.has(def.requiredModule)
  })
  return {
    layouts: { lg: defaultGrid(view, meta.installedModules) },
    dismissed: [],
    quickActions: qa.length > 0 ? qa : defaultQuickActions("financial").slice(0, 3),
  }
}

/**
 * Migrate any saved blob to a fully resolved v4 dual-slice document.
 */
export function migrateToV4(saved: SavedAny, meta: Meta): {
  version: 4
  activeView?: DashboardView
  financial: DashboardSlice
  operations: DashboardSlice
} {
  if (saved && typeof saved === "object" && (saved as GridLayoutV4).version === 4) {
    const v4 = saved as GridLayoutV4
    const finRaw = v4.dashboards?.financial
    const opsRaw = v4.dashboards?.operations
    const financial: DashboardSlice = {
      layouts: resolveSliceLayout(finRaw ?? null, meta, "financial"),
      dismissed: Array.isArray(finRaw?.dismissed) ? finRaw!.dismissed! : [],
      quickActions:
        Array.isArray(finRaw?.quickActions) && finRaw!.quickActions!.length > 0
          ? finRaw!.quickActions!
          : defaultQuickActions("financial"),
    }
    const operations: DashboardSlice = {
      layouts: resolveSliceLayout(opsRaw ?? null, meta, "operations"),
      dismissed: Array.isArray(opsRaw?.dismissed) ? opsRaw!.dismissed! : [],
      quickActions:
        Array.isArray(opsRaw?.quickActions) && opsRaw!.quickActions!.length > 0
          ? opsRaw!.quickActions!
          : defaultQuickActions("operations"),
    }
    return { version: 4, activeView: v4.activeView, financial, operations }
  }

  // v1–v3 (or null) → wrap under financial; seed operations from defaults
  let financialLayouts: ResolvedLayouts
  let dismissed: string[] = []
  let quickActions = defaultQuickActions("financial")

  if (saved && typeof saved === "object") {
    const v = (saved as { version?: number }).version
    if (v === 3) {
      const s = saved as GridLayoutV3
      dismissed = Array.isArray(s.dismissed) ? s.dismissed : []
      if (Array.isArray(s.quickActions) && s.quickActions.length > 0) quickActions = s.quickActions
      financialLayouts = resolveSliceLayout(s, meta, "financial")
    } else if (v === 2 || v === 1) {
      financialLayouts = resolveSliceLayout(saved as GridLayoutV2 | StoredLayoutV1, meta, "financial")
    } else {
      financialLayouts = resolveLayout(saved, meta)
    }
  } else {
    financialLayouts = { lg: defaultGrid("financial", meta.installedModules) }
  }

  return {
    version: 4,
    financial: { layouts: financialLayouts, dismissed, quickActions },
    operations: emptySlice("operations", meta),
  }
}

export function toV4Payload(
  financial: DashboardSlice,
  operations: DashboardSlice,
  activeView?: DashboardView,
): GridLayoutV4 {
  return {
    version: 4,
    activeView,
    dashboards: {
      financial: {
        layouts: financial.layouts,
        dismissed: financial.dismissed,
        quickActions: financial.quickActions,
      },
      operations: {
        layouts: operations.layouts,
        dismissed: operations.dismissed,
        quickActions: operations.quickActions,
      },
    },
  }
}

export { registryById }
