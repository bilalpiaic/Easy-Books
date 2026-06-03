"use client"
import { useState } from "react"
import { X } from "lucide-react"
import type { SourceMeta, FilterClause } from "@/lib/reportTypes"
import { OPS_BY_TYPE } from "@/lib/reportTypes"

interface Props { source: SourceMeta; filters: FilterClause[]; onChange: (f: FilterClause[]) => void }

export default function FilterBar({ source, filters, onChange }: Props) {
  const [field, setField] = useState(source.fields[0]?.key ?? "")
  const meta = source.fields.find(f => f.key === field)
  const ops = meta ? OPS_BY_TYPE[meta.type] : []
  const [op, setOp] = useState(ops[0] ?? "equals")
  const [value, setValue] = useState("")

  const add = () => {
    if (!field) return
    onChange([...filters, { field, op, value }])
    setValue("")
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select value={field} onChange={e => setField(e.target.value)} className="text-sm border border-[#ede9e2] rounded px-2 py-1">
        {source.fields.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
      </select>
      <select value={op} onChange={e => setOp(e.target.value)} className="text-sm border border-[#ede9e2] rounded px-2 py-1">
        {ops.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      {meta?.type === "enum"
        ? <select value={value} onChange={e => setValue(e.target.value)} className="text-sm border border-[#ede9e2] rounded px-2 py-1">
            <option value="">—</option>{(meta.enum_values ?? []).map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        : <input value={value} onChange={e => setValue(e.target.value)}
            type={meta?.type === "date" ? "date" : meta?.type === "money" || meta?.type === "number" ? "number" : "text"}
            className="text-sm border border-[#ede9e2] rounded px-2 py-1" placeholder="value" />}
      <button onClick={add} className="text-sm px-3 py-1 border border-[#b8943f] text-[#b8943f] rounded">+ Filter</button>
      {filters.map((f, i) => (
        <span key={i} className="inline-flex items-center gap-1 text-xs bg-[#f6f3ee] border border-[#ede9e2] rounded-full px-3 py-1">
          {f.field} {f.op} {String(Array.isArray(f.value) ? f.value.join(",") : f.value)}
          <X size={12} className="cursor-pointer" onClick={() => onChange(filters.filter((_, j) => j !== i))} />
        </span>
      ))}
    </div>
  )
}
