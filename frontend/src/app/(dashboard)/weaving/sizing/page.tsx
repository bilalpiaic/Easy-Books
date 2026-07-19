"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { weightTriple } from "@/lib/weavingUnits"

type Contract = { id: number; number: string }
type Vendor = { id: number; name: string }
type Row = {
  id: number
  number: string
  contract_id: number
  vendor_id?: number | null
  date: string
  input_kg: number
  input_lbs: number
  input_bags: number
  output_kg: number
  output_lbs: number
  output_bags: number
  gain_shrink_pct: number
  sizing_cost: number
}

const today = () => new Date().toISOString().slice(0, 10)

export default function SizingPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    contract_id: "", vendor_id: "", date: today(),
    input_kg: "", output_kg: "", sizing_cost: "",
  })

  const load = useCallback(() => {
    apiFetch<Row[]>("/api/weaving/sizings").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    Promise.all([
      apiFetch<Contract[]>("/api/weaving/contracts").catch(() => []),
      apiFetch<{ items: Vendor[] }>("/api/vendors?limit=500").catch(() => ({ items: [] })),
    ]).then(([c, v]) => {
      setContracts(Array.isArray(c) ? c : [])
      setVendors(v.items ?? [])
    })
  }, [load])

  const inputKg = parseFloat(form.input_kg) || 0
  const outputKg = parseFloat(form.output_kg) || 0
  const gainPct = inputKg ? ((outputKg - inputKg) / inputKg) * 100 : 0

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/weaving/sizings", {
        method: "POST",
        body: JSON.stringify({
          contract_id: Number(form.contract_id),
          vendor_id: form.vendor_id ? Number(form.vendor_id) : null,
          date: form.date,
          input_kg: inputKg,
          output_kg: outputKg,
          sizing_cost: parseFloat(form.sizing_cost) || 0,
        }),
      })
      setShowForm(false)
      setForm({ contract_id: "", vendor_id: "", date: today(), input_kg: "", output_kg: "", sizing_cost: "" })
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const cmap = Object.fromEntries(contracts.map(c => [c.id, c.number]))
  const vmap = Object.fromEntries(vendors.map(v => [v.id, v.name]))

  return (
    <div className="p-4 space-y-4">
      <div className="flex justify-end print:hidden">
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Sizing
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">SZ #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Contract</th>
              <th className="px-3 py-2">Vendor</th>
              <th className="px-3 py-2">Input</th>
              <th className="px-3 py-2">Output</th>
              <th className="px-3 py-2 text-right">Gain/shrink %</th>
              <th className="px-3 py-2 text-right">Cost</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(r => (
              <tr key={r.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap font-medium">{r.number}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="px-3 py-2">
                  <Link href={`/weaving/contracts/${r.contract_id}`} className="text-[var(--primary)]">
                    {cmap[r.contract_id] || `#${r.contract_id}`}
                  </Link>
                </td>
                <td className="px-3 py-2">{r.vendor_id ? (vmap[r.vendor_id] || `#${r.vendor_id}`) : "—"}</td>
                <td className="px-3 py-2"><WeightTripleDisplay kg={r.input_kg} lbs={r.input_lbs} bags={r.input_bags} /></td>
                <td className="px-3 py-2"><WeightTripleDisplay kg={r.output_kg} lbs={r.output_lbs} bags={r.output_bags} /></td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.gain_shrink_pct)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.sizing_cost)}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-[var(--text-muted)]">No sizing entries yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">New Sizing</h2>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Contract *</label>
                <select required value={form.contract_id} onChange={e => setForm(f => ({ ...f, contract_id: e.target.value }))} className={input}>
                  <option value="">Select…</option>
                  {contracts.map(c => <option key={c.id} value={c.id}>{c.number}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Sizing vendor</label>
                <select value={form.vendor_id} onChange={e => setForm(f => ({ ...f, vendor_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Date *</label>
                <input type="date" required value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Input kg *</label>
                <input type="number" step="any" required value={form.input_kg} onChange={e => setForm(f => ({ ...f, input_kg: e.target.value }))} className={input} />
                <p className="text-xs text-[var(--text-muted)] mt-1">{weightTriple(inputKg).lbs.toFixed(2)} lb</p>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Output kg *</label>
                <input type="number" step="any" required value={form.output_kg} onChange={e => setForm(f => ({ ...f, output_kg: e.target.value }))} className={input} />
                <p className="text-xs text-[var(--text-muted)] mt-1">Gain/shrink: {gainPct.toFixed(2)}%</p>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Sizing cost</label>
                <input type="number" step="any" value={form.sizing_cost} onChange={e => setForm(f => ({ ...f, sizing_cost: e.target.value }))} className={input} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowForm(false)} className="px-3 py-2 text-sm rounded-lg border border-[var(--border)]">Cancel</button>
              <button type="submit" disabled={saving} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50">
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
