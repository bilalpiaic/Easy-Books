import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { loadBootstrap } from "@/lib/bootstrap"
import { getCurrentUser } from "@/lib/auth"
import { useModules } from "@/context/ModuleContext"
import type { DashboardView } from "@/lib/dashboardHome"
import {
  BP_COLS,
  defaultGrid,
  migrateToV4,
  toV4Payload,
  validateBreakpoint,
  registryById,
  type Breakpoint,
  type DashboardSlice,
  type GridItem,
  type Meta,
  type ResolvedLayouts,
  type SavedAny,
} from "@/lib/dashboardLayoutLogic"

export {
  GRID_COLS, BP_COLS, packItems, defaultGrid, migrateV1toV2, resolveLayout,
} from "@/lib/dashboardLayoutLogic"
export type {
  GridItem, GridLayoutV2, GridLayoutV3, ResolvedLayouts, Breakpoint,
} from "@/lib/dashboardLayoutLogic"

export interface UseDashboardLayout {
  view: DashboardView
  layouts: ResolvedLayouts
  meta: Meta
  loading: boolean
  dirty: boolean
  quickActions: string[]
  applyLayout: (bp: Breakpoint, allLayouts: Record<string, readonly { i: string; x: number; y: number; w: number; h: number }[]>) => void
  markCustomized: (bp: Breakpoint) => void
  addWidget: (id: string) => void
  removeWidget: (id: string) => void
  reset: () => void
  reload: () => void
  save: () => Promise<void>
  updateQuickActions: (ids: string[]) => Promise<void>
}

function updateSlice(
  slices: { financial: DashboardSlice; operations: DashboardSlice },
  view: DashboardView,
  patch: Partial<DashboardSlice>,
): { financial: DashboardSlice; operations: DashboardSlice } {
  return { ...slices, [view]: { ...slices[view], ...patch } }
}

export function useDashboardLayout(view: DashboardView = "financial"): UseDashboardLayout {
  const { installedModules } = useModules()
  const [meta, setMeta] = useState<Meta>({
    model: undefined,
    role: getCurrentUser()?.role ?? "viewer",
    installedModules,
  })
  const [slices, setSlices] = useState<{ financial: DashboardSlice; operations: DashboardSlice }>(() => {
    const m: Meta = { model: undefined, role: "viewer", installedModules }
    const migrated = migrateToV4(null, m)
    return { financial: migrated.financial, operations: migrated.operations }
  })
  const [savedPayload, setSavedPayload] = useState<SavedAny>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      apiFetch<{ layout: SavedAny }>("/api/dashboard/layout").catch(() => ({ layout: null })),
      loadBootstrap().catch(() => null),
    ]).then(([lay, boot]) => {
      const me = boot?.me
      const m: Meta = {
        model: me?.tenant?.business_model,
        role: me?.role ?? getCurrentUser()?.role ?? "viewer",
        installedModules,
      }
      setMeta(m)
      setSavedPayload(lay.layout)
      const migrated = migrateToV4(lay.layout, m)
      setSlices({ financial: migrated.financial, operations: migrated.operations })
    }).finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot load matches prior behaviour
  }, [])

  const active = slices[view]

  const setActive = (updater: (prev: DashboardSlice) => DashboardSlice) => {
    setSlices(prev => ({ ...prev, [view]: updater(prev[view]) }))
  }

  const applyLayout = (
    _bp: Breakpoint,
    allLayouts: Record<string, readonly { i: string; x: number; y: number; w: number; h: number }[]>,
  ) => {
    setActive(prev => {
      const nextLayouts = { ...prev.layouts }
      for (const key of Object.keys(allLayouts) as Breakpoint[]) {
        const arr = allLayouts[key]
        if (!arr) continue
        const mapped = arr.map(l => ({ id: l.i, x: l.x, y: l.y, w: l.w, h: l.h }))
        if (key === "lg") { nextLayouts.lg = mapped; continue }
        if (prev.layouts[key]) nextLayouts[key] = mapped
      }
      return { ...prev, layouts: nextLayouts }
    })
  }

  const markCustomized = (bp: Breakpoint) => {
    if (bp === "lg") return
    setActive(prev => {
      if (prev.layouts[bp]) return prev
      const cols = BP_COLS[bp]
      const lgIds = new Set(prev.layouts.lg.map(i => i.id))
      const derived = validateBreakpoint(prev.layouts.lg, meta, lgIds, cols, view)
      return { ...prev, layouts: { ...prev.layouts, [bp]: derived } }
    })
  }

  const addWidget = (id: string) => {
    setActive(prev => {
      const dismissed = prev.dismissed.filter(d => d !== id)
      if (prev.layouts.lg.some(i => i.id === id)) return { ...prev, dismissed }
      const def = registryById.get(id)
      const size = def ? def.defaultSize : { w: 1, h: 1 }
      const newLg: GridItem[] = [
        ...prev.layouts.lg,
        { id, x: 0, y: prev.layouts.lg.reduce((m, i) => Math.max(m, i.y + i.h), 0), w: size.w, h: size.h },
      ]
      const nextLayouts: ResolvedLayouts = { lg: newLg }
      for (const bp of ["sm", "xs"] as const) {
        if (!prev.layouts[bp]) continue
        const cols = BP_COLS[bp]
        const w = Math.min(size.w, cols)
        const y = prev.layouts[bp]!.reduce((m, i) => Math.max(m, i.y + i.h), 0)
        nextLayouts[bp] = [...prev.layouts[bp]!, { id, x: 0, y, w, h: size.h }]
      }
      return { ...prev, dismissed, layouts: nextLayouts }
    })
  }

  const removeWidget = (id: string) => {
    setActive(prev => {
      const dismissed = prev.dismissed.includes(id) ? prev.dismissed : [...prev.dismissed, id]
      const nextLayouts: ResolvedLayouts = { lg: prev.layouts.lg.filter(i => i.id !== id) }
      for (const bp of ["sm", "xs"] as const) {
        if (prev.layouts[bp]) nextLayouts[bp] = prev.layouts[bp]!.filter(i => i.id !== id)
      }
      return { ...prev, dismissed, layouts: nextLayouts }
    })
  }

  const reset = () => {
    const fresh = migrateToV4(null, meta)[view]
    setActive(() => ({
      layouts: { lg: defaultGrid(view, meta.installedModules) },
      dismissed: [],
      quickActions: fresh.quickActions,
    }))
  }

  const reload = () => {
    const migrated = migrateToV4(savedPayload, meta)
    setSlices({ financial: migrated.financial, operations: migrated.operations })
  }

  const persist = async (
    nextSlices: { financial: DashboardSlice; operations: DashboardSlice },
  ) => {
    const payload = toV4Payload(nextSlices.financial, nextSlices.operations, view)
    await apiFetch("/api/dashboard/layout", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout: payload }),
    })
    setSavedPayload(payload)
  }

  const save = async () => {
    await persist(slices)
  }

  const updateQuickActions = async (ids: string[]) => {
    const next = updateSlice(slices, view, { quickActions: ids })
    setSlices(next)
    await persist(next)
  }

  const baseline = migrateToV4(savedPayload, meta)[view]
  const dirty = JSON.stringify(active.layouts) !== JSON.stringify(baseline.layouts)
    || JSON.stringify(active.dismissed) !== JSON.stringify(baseline.dismissed)
    || JSON.stringify(active.quickActions) !== JSON.stringify(baseline.quickActions)

  return {
    view,
    layouts: active.layouts,
    meta,
    loading,
    dirty,
    quickActions: active.quickActions,
    applyLayout,
    markCustomized,
    addWidget,
    removeWidget,
    reset,
    reload,
    save,
    updateQuickActions,
  }
}
