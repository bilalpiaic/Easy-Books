"use client"

import React from "react"
import Link from "next/link"
import { resolveShortcut, shortcutHref } from "@/lib/dashboardShortcuts"
import type { TileMetric } from "@/lib/dashboardTileMetrics"
import { useTranslation } from "react-i18next"
import { useModules } from "@/context/ModuleContext"

export default function ShortcutTile({ id, model, role, editing, metric }: {
  id: string; model: string | undefined; role: string; editing: boolean
  metric?: TileMetric | null
}) {
  const { t } = useTranslation()
  const { installedModules } = useModules()

  const item = resolveShortcut(id, installedModules, role)
  if (!item) {
    return (
      <div className="h-full flex items-center justify-center bg-white border border-[#ede9e2] rounded-xl text-[10px] text-[#1a1814]/40 text-center p-2">
        Unavailable
      </div>
    )
  }
  const Icon = item.icon
  const toneClass =
    metric?.tone === "danger" ? "bg-red-100 text-red-700"
    : metric?.tone === "warn" ? "bg-amber-100 text-amber-700"
    : "bg-[#faf6ec] text-[#b8943f]"
  const inner = (
    <div className="h-full flex flex-col items-center justify-center gap-1.5 bg-white border border-[#ede9e2] rounded-xl p-2 text-center hover:border-[#b8943f]/50 transition-colors">
      <Icon className="w-6 h-6 text-[#b8943f]" />
      <span className="text-[11px] font-medium text-[#1a1814]/80 leading-tight">{item.label}</span>
      {metric && <span className="text-sm font-bold text-[#1a1814] leading-none truncate max-w-full">{metric.value}</span>}
      {metric?.badge && (
        <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${toneClass}`}>{metric.badge}</span>
      )}
    </div>
  )
  // In edit mode the cell handles dragging; suppress navigation.
  if (editing) return inner
  return <Link href={shortcutHref(id)} className="block h-full">{inner}</Link>
}
