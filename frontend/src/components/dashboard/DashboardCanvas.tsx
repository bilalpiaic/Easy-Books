"use client"

import React from "react"
import type { WidgetContext } from "@/lib/dashboardWidgets"
import type { ResolvedWidget } from "@/hooks/useDashboardLayout"

export default function DashboardCanvas({ widgets, ctx }: {
  widgets: ResolvedWidget[]
  ctx: WidgetContext
}) {
  return (
    <div className="space-y-4">
      {widgets.filter(w => w.visible).map(w => (
        <React.Fragment key={w.def.id}>{w.def.render(ctx)}</React.Fragment>
      ))}
    </div>
  )
}
