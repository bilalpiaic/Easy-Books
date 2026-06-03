"use client"
import { useState } from "react"
import { X } from "lucide-react"
import type { SourceMeta, FilterClause } from "@/lib/reportTypes"
import { OPS_BY_TYPE } from "@/lib/reportTypes"

interface Props { source: SourceMeta; filters: FilterClause[]; onChange: (f: FilterClause[]) => void }

function fieldInputType(type: string): string {
  if (type === "date") return "date"
  if (type === "money" || type === "number") return "number"
  return "text"
}

export default function FilterBar({ source, filters, onChange }: Props) {
  const [field, setField] = useState(source.fields[0]?.key ?? "")
  const meta = source.fields.find(f => f.key === field)
  const ops = meta ? OPS_BY_TYPE[meta.type] : []
  const [op, setOp] = useState(ops[0] ?? "equals")
  const [value, setValue] = useState("")
  const [valueLo, setValueLo] = useState("")
  const [valueHi, setValueHi] = useState("")

  const isBetween = op === "between" && meta?.type !== "enum"

  const add = () => {
    if (!field) return
    if (isBetween) {
      onChange([...filters, { field, op, value: [valueLo, valueHi] }])
      setValueLo(""); setValueHi("")
    } else {
      onChange([...filters, { field, op, value }])
      setValue("")
    }
  }

  const inputCls = "text-sm border border-[#ede9e2] rounded px-2 py-1"

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select value={field} onChange={e => setField(e.target.value)} className={inputCls}>
        {source.fields.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
      </select>
      <select value={op} onChange={e => setOp(e.target.value)} className={inputCls}>
        {ops.map(o => <option key={o} value={o}>{o}</option>)}
      </select>

      {/* Value input(s) */}
      {meta?.type === "enum" ? (
        <select value={value} onChange={e => setValue(e.target.value)} className={inputCls}>
          <option value="">—</option>
          {(meta.enum_values ?? []).map(v => <option key={v} value={v}>{v}</option>)}
        </select>
      ) : isBetween ? (
        <>
          <input value={valueLo} onChange={e => setValueLo(e.target.value)}
            type={fieldInputType(meta?.type ?? "text")}
            className={inputCls} placeholder="from" />
          <span className="text-sm text-black/50">–</span>
          <input value={valueHi} onChange={e => setValueHi(e.target.value)}
            type={fieldInputType(meta?.type ?? "text")}
            className={inputCls} placeholder="to" />
        </>
      ) : (
        <input value={value} onChange={e => setValue(e.target.value)}
          type={fieldInputType(meta?.type ?? "text")}
          className={inputCls} placeholder="value" />
      )}

      <button onClick={add} className="text-sm px-3 py-1 border border-[#b8943f] text-[#b8943f] rounded">+ Filter</button>

      {filters.map((f, i) => (
        <span key={i} className="inline-flex items-center gap-1 text-xs bg-[#f6f3ee] border border-[#ede9e2] rounded-full px-3 py-1">
          {f.field} {f.op} {String(Array.isArray(f.value) ? f.value.join(" – ") : f.value)}
          <X size={12} className="cursor-pointer" onClick={() => onChange(filters.filter((_, j) => j !== i))} />
        </span>
      ))}
    </div>
  )
}
