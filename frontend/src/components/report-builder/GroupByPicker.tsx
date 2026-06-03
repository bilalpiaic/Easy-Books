"use client"
import type { SourceMeta } from "@/lib/reportTypes"

interface Props { source: SourceMeta; groupBy: string[]; onChange: (g: string[]) => void }

export default function GroupByPicker({ source, groupBy, onChange }: Props) {
  const val = groupBy[0] ?? ""
  return (
    <select value={val} onChange={e => onChange(e.target.value ? [e.target.value] : [])}
      className="text-sm border border-[#ede9e2] rounded-lg px-3 py-2 bg-white">
      <option value="">No grouping</option>
      {source.fields.filter(f => f.groupable).map(f => <option key={f.key} value={f.key}>Group by {f.label}</option>)}
    </select>
  )
}
