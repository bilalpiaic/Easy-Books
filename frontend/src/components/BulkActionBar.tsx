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
    <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-50 flex flex-wrap items-center justify-center gap-2 sm:gap-3 px-3 sm:px-4 py-2.5 sm:py-3 max-w-[calc(100vw-1.5rem)] bg-[var(--text-primary)] text-white rounded-xl shadow-2xl border border-white/10">
      <span className="text-sm font-semibold whitespace-nowrap">
        {count} selected
      </span>
      <div className="w-px h-5 bg-white/20 hidden sm:block" />
      {actions.map(action => (
        <button
          key={action.label}
          onClick={action.onClick}
          className={`px-2.5 sm:px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
            action.variant === "danger"
              ? "bg-red-500/20 hover:bg-red-500/40 text-red-300"
              : "bg-white/10 hover:bg-white/20 text-white"
          }`}
        >
          {action.label}
        </button>
      ))}
      <div className="w-px h-5 bg-white/20 hidden sm:block" />
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
