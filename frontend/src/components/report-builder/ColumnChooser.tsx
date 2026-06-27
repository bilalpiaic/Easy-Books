"use client"
import type { SourceMeta } from "@/lib/reportTypes"

interface Props { source: SourceMeta; columns: string[]; onChange: (cols: string[]) => void }

export default function ColumnChooser({ source, columns, onChange }: Props) {
  const toggle = (key: string) =>
    onChange(columns.includes(key) ? columns.filter(c => c !== key) : [...columns, key])
  return (
    <details className="relative">
      <summary className="px-3 py-2 text-sm border border-[var(--border)] rounded-lg cursor-pointer bg-white">+ Columns</summary>
      <div className="absolute z-10 mt-1 w-56 bg-white border border-[var(--border)] rounded-lg shadow-lg p-2 max-h-72 overflow-auto">
        {source.fields.map(f => (
          <label key={f.key} className="flex items-center gap-2 px-2 py-1 text-sm hover:bg-[var(--bg-page)] rounded cursor-pointer">
            <input type="checkbox" checked={columns.includes(f.key)} onChange={() => toggle(f.key)} />
            {f.label}
          </label>
        ))}
      </div>
    </details>
  )
}
