"use client"

import React from "react"
import { Responsive, WidthProvider, type Layout, type LayoutItem } from "react-grid-layout/legacy"
import "react-grid-layout/css/styles.css"
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
  const rglLayout: LayoutItem[] = items.map(i => {
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
      onLayoutChange={(l: Layout) => { if (editing) applyLayout(l) }}
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
