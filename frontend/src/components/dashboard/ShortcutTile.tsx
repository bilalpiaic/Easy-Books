"use client"

import React from "react"
import Link from "next/link"
import { resolveShortcut, shortcutHref } from "@/lib/dashboardShortcuts"

export default function ShortcutTile({ id, model, role, editing }: {
  id: string; model: string | undefined; role: string; editing: boolean
}) {
  const item = resolveShortcut(id, model, role)
  if (!item) {
    return (
      <div className="h-full flex items-center justify-center bg-white border border-[#ede9e2] rounded-xl text-[10px] text-[#1a1814]/40 text-center p-2">
        Unavailable
      </div>
    )
  }
  const Icon = item.icon
  const inner = (
    <div className="h-full flex flex-col items-center justify-center gap-1.5 bg-white border border-[#ede9e2] rounded-xl p-2 text-center hover:border-[#b8943f]/50 transition-colors">
      <Icon className="w-6 h-6 text-[#b8943f]" />
      <span className="text-[11px] font-medium text-[#1a1814]/80 leading-tight">{item.label}</span>
    </div>
  )
  // In edit mode the cell handles dragging; suppress navigation.
  if (editing) return inner
  return <Link href={shortcutHref(id)} className="block h-full">{inner}</Link>
}
