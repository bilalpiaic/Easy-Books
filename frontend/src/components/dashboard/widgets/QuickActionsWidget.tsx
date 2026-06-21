"use client"

import { useState } from "react"
import Link from "next/link"
import { Pencil, Check, X } from "lucide-react"
import { ALL_QUICK_ACTIONS } from "@/lib/dashboardWidgets"

interface Props {
  quickActions: string[]
  updateQuickActions: (ids: string[]) => Promise<void>
}

export default function QuickActionsWidget({ quickActions, updateQuickActions }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  const activeActions = quickActions
    .map(id => ALL_QUICK_ACTIONS.find(a => a.id === id))
    .filter(Boolean) as typeof ALL_QUICK_ACTIONS

  const startEdit = () => {
    setDraft([...quickActions])
    setEditing(true)
  }

  const toggle = (id: string) =>
    setDraft(prev => prev.includes(id) ? prev.filter(d => d !== id) : [...prev, id])

  const handleSave = async () => {
    setSaving(true)
    try { await updateQuickActions(draft) } finally { setSaving(false) }
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="bg-white border border-[#b8943f]/40 rounded-xl shadow-sm px-3 py-2.5">
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">
            Customize Quick Actions
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setEditing(false)}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs text-[#1a1814]/50 hover:bg-[#faf8f4] transition-colors"
            >
              <X className="w-3 h-3" /> Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || draft.length === 0}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-[#b8943f] text-white hover:bg-[#a07830] disabled:opacity-50 transition-colors"
            >
              <Check className="w-3 h-3" /> {saving ? "Saving…" : "Done"}
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {ALL_QUICK_ACTIONS.map(action => {
            const active = draft.includes(action.id)
            return (
              <button
                key={action.id}
                onClick={() => toggle(action.id)}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium transition-all ${
                  active
                    ? "bg-[#b8943f]/10 border-[#b8943f]/50 text-[#1a1814]"
                    : "bg-white border-[#ede9e2] text-[#1a1814]/45 hover:border-[#b8943f]/30 hover:text-[#1a1814]/70"
                }`}
              >
                <action.icon className={`w-3.5 h-3.5 ${active ? action.color : "text-[#1a1814]/30"}`} />
                {action.label}
                {active && <Check className="w-3 h-3 text-[#b8943f]" />}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white border border-[#ede9e2] rounded-xl shadow-sm px-3 py-2 flex items-center gap-1 group">
      <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/45 mr-1 shrink-0">
        Quick Actions
      </span>
      <div className="flex flex-wrap items-center gap-1 flex-1 min-w-0">
        {activeActions.map(action => (
          <Link
            key={action.id}
            href={action.href}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-transparent hover:bg-[#faf8f4] hover:border-[#b8943f]/30 transition-all"
          >
            <action.icon className={`w-4 h-4 ${action.color}`} />
            <span className="text-sm font-medium text-[#1a1814]/80">{action.label}</span>
          </Link>
        ))}
      </div>
      <button
        onClick={startEdit}
        title="Customize quick actions"
        className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-md text-[#1a1814]/30 hover:text-[#b8943f] hover:bg-[#faf8f4]"
      >
        <Pencil className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}
