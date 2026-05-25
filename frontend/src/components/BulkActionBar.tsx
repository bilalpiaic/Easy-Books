"use client"

import { X } from "lucide-react"

interface BulkAction {
  label: string
  onClick: () => void
  variant?: "default" | "danger"
}

interface BulkActionBarProps {
  count: number
  actions: BulkAction[]
  onClear: () => void
}

export default function BulkActionBar({ count, actions, onClear }: BulkActionBarProps) {
  if (count === 0) return null
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-3 bg-[#1a1814] text-white rounded-xl shadow-2xl border border-white/10">
      <span className="text-sm font-semibold whitespace-nowrap">
        {count} selected
      </span>
      <div className="w-px h-5 bg-white/20" />
      {actions.map(action => (
        <button
          key={action.label}
          onClick={action.onClick}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            action.variant === "danger"
              ? "bg-red-500/20 hover:bg-red-500/40 text-red-300"
              : "bg-white/10 hover:bg-white/20 text-white"
          }`}
        >
          {action.label}
        </button>
      ))}
      <div className="w-px h-5 bg-white/20" />
      <button
        onClick={onClear}
        className="p-1 hover:bg-white/10 rounded-lg transition-colors"
        title="Clear selection"
      >
        <X className="w-4 h-4 text-white/60" />
      </button>
    </div>
  )
}
