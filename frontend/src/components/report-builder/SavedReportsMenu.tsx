"use client"
import type { SavedReport } from "@/lib/reportTypes"

interface Props {
  saved: SavedReport[]
  onLoad: (r: SavedReport) => void
  onSave: () => void
  onDelete: (id: number) => void
}

export default function SavedReportsMenu({ saved, onLoad, onSave, onDelete }: Props) {
  return (
    <details className="relative">
      <summary className="px-3 py-2 text-sm border border-[var(--border)] rounded-lg cursor-pointer bg-white">Saved ▾</summary>
      <div className="absolute z-10 mt-1 right-0 w-64 bg-white border border-[var(--border)] rounded-lg shadow-lg p-2">
        <button onClick={onSave} className="w-full text-left px-2 py-1 text-sm font-bold text-[var(--primary)]">+ Save current…</button>
        <div className="border-t border-[var(--border)] my-1" />
        {saved.length === 0 && <p className="px-2 py-1 text-xs text-[var(--text-muted)]">No saved reports</p>}
        {saved.map(r => (
          <div key={r.id} className="flex items-center justify-between px-2 py-1 text-sm hover:bg-[var(--bg-page)] rounded">
            <button onClick={() => onLoad(r)} className="text-left flex-1 truncate">{r.name}
              {r.visibility === "shared" && <span className="ml-1 text-xs text-[var(--text-muted)]">· shared</span>}</button>
            <button onClick={() => onDelete(r.id)} className="text-xs text-red-600 ml-2">✕</button>
          </div>
        ))}
      </div>
    </details>
  )
}
