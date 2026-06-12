import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { WIDGET_REGISTRY, type WidgetDef } from "@/lib/dashboardWidgets"

export interface StoredWidget { id: string; visible: boolean }
export interface StoredLayout { version: number; widgets: StoredWidget[] }
export interface ResolvedWidget { def: WidgetDef; visible: boolean }

/** Merge a saved layout against the registry:
 *  - keep saved order, dropping unknown/duplicate ids
 *  - append any registry widget missing from saved (forward-compat) */
export function resolveLayout(registry: WidgetDef[], saved: StoredLayout | null): ResolvedWidget[] {
  const byId = new Map(registry.map(w => [w.id, w]))
  const result: ResolvedWidget[] = []
  const seen = new Set<string>()
  for (const sw of saved?.widgets ?? []) {
    const def = byId.get(sw.id)
    if (!def || seen.has(sw.id)) continue
    result.push({ def, visible: sw.visible })
    seen.add(sw.id)
  }
  for (const def of registry) {
    if (!seen.has(def.id)) result.push({ def, visible: def.defaultVisible })
  }
  return result
}

function toStored(list: ResolvedWidget[]): StoredLayout {
  return { version: 1, widgets: list.map(w => ({ id: w.def.id, visible: w.visible })) }
}

export interface UseDashboardLayout {
  widgets: ResolvedWidget[]
  loading: boolean
  dirty: boolean
  setOrder: (orderedIds: string[]) => void
  toggle: (id: string) => void
  reset: () => void
  reload: () => void
  save: () => Promise<void>
}

export function useDashboardLayout(): UseDashboardLayout {
  const [widgets, setWidgets] = useState<ResolvedWidget[]>(() => resolveLayout(WIDGET_REGISTRY, null))
  const [saved, setSaved] = useState<StoredLayout | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<{ layout: StoredLayout | null }>("/api/dashboard/layout")
      .then(r => { setSaved(r.layout); setWidgets(resolveLayout(WIDGET_REGISTRY, r.layout)) })
      .catch(() => {})            // keep registry default on failure
      .finally(() => setLoading(false))
  }, [])

  const setOrder = (orderedIds: string[]) => setWidgets(prev => {
    const byId = new Map(prev.map(w => [w.def.id, w]))
    return orderedIds.map(id => byId.get(id)).filter((w): w is ResolvedWidget => Boolean(w))
  })
  const toggle = (id: string) => setWidgets(prev => prev.map(w => w.def.id === id ? { ...w, visible: !w.visible } : w))
  const reset = () => setWidgets(resolveLayout(WIDGET_REGISTRY, null))
  const reload = () => setWidgets(resolveLayout(WIDGET_REGISTRY, saved))

  const save = async () => {
    const stored = toStored(widgets)
    await apiFetch("/api/dashboard/layout", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout: stored }),
    })
    setSaved(stored)
  }

  const baseline = saved ?? toStored(resolveLayout(WIDGET_REGISTRY, null))
  const dirty = JSON.stringify(toStored(widgets)) !== JSON.stringify(baseline)

  return { widgets, loading, dirty, setOrder, toggle, reset, reload, save }
}
