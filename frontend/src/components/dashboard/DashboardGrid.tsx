"use client"

import React, { useState } from "react"
import { Responsive, WidthProvider, type Layout, type LayoutItem } from "react-grid-layout/legacy"
import "react-grid-layout/css/styles.css"
import { X, Check, RotateCcw, Plus } from "lucide-react"
import { WIDGET_REGISTRY, type WidgetContext, type WidgetDef } from "@/lib/dashboardWidgets"
import { isShortcutId, shortcutHref } from "@/lib/dashboardShortcuts"
import { resolveTileMetric } from "@/lib/dashboardTileMetrics"
import ShortcutTile from "@/components/dashboard/ShortcutTile"
import AddWidgetPanel from "@/components/dashboard/AddWidgetPanel"
import type { GridItem, UseDashboardLayout } from "@/hooks/useDashboardLayout"
import { BP_COLS, type Breakpoint } from "@/hooks/useDashboardLayout"

const ResponsiveGridLayout = WidthProvider(Responsive)
const registryById = new Map<string, WidgetDef>(WIDGET_REGISTRY.map(w => [w.id, w]))

function renderItem(item: GridItem, ctx: WidgetContext, meta: { model: string | undefined; role: string }, editing: boolean): React.ReactNode {
  if (isShortcutId(item.id)) {
    const metric = resolveTileMetric(shortcutHref(item.id), ctx.s, ctx.fmt)
    return <ShortcutTile id={item.id} model={meta.model} role={meta.role} editing={editing} metric={metric ?? undefined} />
  }
  const def = registryById.get(item.id)
  return def ? def.render(ctx) : null
}

export default function DashboardGrid({ layout, ctx, editing, onExitEditing }: {
  layout: UseDashboardLayout
  ctx: WidgetContext
  editing: boolean
  onExitEditing: () => void
}) {
  const [saving, setSaving] = useState(false)
  const [adding, setAdding] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [activeBp, setActiveBp] = useState<Breakpoint>("lg")

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
          <span className="text-[11px] text-[#b8943f]/70 font-semibold">
            {activeBp === "lg" ? "Desktop layout" : activeBp === "sm" ? "Tablet layout" : "Phone layout"}
          </span>
          <span className="text-[11px] text-[#1a1814]/45">Drag to move · drag a corner to resize · × to remove</span>
          <div className="ml-auto flex items-center gap-2">
            <button onClick={() => setAdding(a => !a)} className="inline-flex items-center gap-1 text-xs font-semibold text-[#b8943f] hover:text-[#a07f33] px-2 py-1">
              <Plus className="w-3.5 h-3.5" /> Add widget
            </button>
            <button onClick={reset} title="Resets layout for all screen sizes" className="inline-flex items-center gap-1 text-xs text-[#1a1814]/60 hover:text-[#1a1814] px-2 py-1">
              <RotateCcw className="w-3.5 h-3.5" /> Reset all
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

      {editing && adding && (
        <AddWidgetPanel
          items={layouts.lg} meta={meta}
          onAdd={(id) => { addWidget(id); setAdding(false) }}
          onClose={() => setAdding(false)}
        />
      )}

      {err && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-2 text-sm text-red-700">{err}</div>}

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
        // activeBp may lag one render on bp-change; hook ignores the bp arg and derives targets from allLayouts keys + prev state.
        onLayoutChange={(_l: Layout, all: Partial<Record<string, Layout>>) => {
          if (editing) applyLayout(activeBp, all as Record<string, Layout>)
        }}
        onDragStop={() => { markCustomized(activeBp) }}
        onResizeStop={() => { markCustomized(activeBp) }}
        draggableCancel=".no-drag"
      >
        {layouts.lg.map(i => (
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
              {renderItem(i, ctx, meta, editing)}
            </div>
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  )
}
