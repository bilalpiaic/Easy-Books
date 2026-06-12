"use client"

import React, { useMemo, useState } from "react"
import { Plus, X } from "lucide-react"
import { WIDGET_REGISTRY } from "@/lib/dashboardWidgets"
import { shortcutCatalog, shortcutId } from "@/lib/dashboardShortcuts"
import { ALL_SECTIONS } from "@/lib/nav"
import type { GridItem } from "@/hooks/useDashboardLayout"

export default function AddWidgetPanel({ items, meta, onAdd, onClose }: {
  items: GridItem[]
  meta: { model: string | undefined; role: string }
  onAdd: (id: string) => void
  onClose: () => void
}) {
  const [tab, setTab] = useState<"widgets" | "shortcuts">("widgets")
  const present = useMemo(() => new Set(items.map(i => i.id)), [items])

  const coreWidgets = WIDGET_REGISTRY.filter(w => !w.pinned && !present.has(w.id))
  const catalog = useMemo(() => shortcutCatalog(meta.model, meta.role), [meta.model, meta.role])

  return (
    <div className="bg-white border border-[#ede9e2] rounded-xl p-3 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex items-center gap-1 text-xs">
          <button onClick={() => setTab("widgets")} className={`px-2.5 py-1 rounded-lg font-semibold ${tab === "widgets" ? "bg-[#faf6ec] text-[#b8943f]" : "text-[#1a1814]/55"}`}>Widgets</button>
          <button onClick={() => setTab("shortcuts")} className={`px-2.5 py-1 rounded-lg font-semibold ${tab === "shortcuts" ? "bg-[#faf6ec] text-[#b8943f]" : "text-[#1a1814]/55"}`}>Shortcuts</button>
        </div>
        <button onClick={onClose} className="ml-auto text-[#1a1814]/40 hover:text-[#1a1814]/70" aria-label="Close add-widget panel">
          <X className="w-4 h-4" />
        </button>
      </div>

      {tab === "widgets" && (
        <div className="flex flex-wrap gap-2">
          {coreWidgets.length === 0 && <p className="text-xs text-[#1a1814]/45">All widgets are on the dashboard.</p>}
          {coreWidgets.map(w => (
            <button key={w.id} onClick={() => onAdd(w.id)}
              className="inline-flex items-center gap-1 text-xs border border-[#ede9e2] rounded-lg px-2.5 py-1.5 hover:border-[#b8943f]/40 text-[#1a1814]/70">
              <Plus className="w-3.5 h-3.5 text-[#b8943f]" /> {w.title}
            </button>
          ))}
        </div>
      )}

      {tab === "shortcuts" && (
        <div className="space-y-3 max-h-72 overflow-y-auto">
          {ALL_SECTIONS.map(section => {
            const inSection = catalog.filter(i => i.section === section)
            if (inSection.length === 0) return null
            return (
              <div key={section}>
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/45 mb-1.5">{section}</p>
                <div className="flex flex-wrap gap-2">
                  {inSection.map(i => {
                    const id = shortcutId(i.href)
                    const added = present.has(id)
                    const Icon = i.icon
                    return (
                      <button key={i.href} disabled={added} onClick={() => onAdd(id)}
                        className={`inline-flex items-center gap-1 text-xs border rounded-lg px-2.5 py-1.5 ${added ? "border-[#ede9e2] text-[#1a1814]/30 cursor-default" : "border-[#ede9e2] text-[#1a1814]/70 hover:border-[#b8943f]/40"}`}>
                        <Icon className="w-3.5 h-3.5 text-[#b8943f]" /> {i.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
