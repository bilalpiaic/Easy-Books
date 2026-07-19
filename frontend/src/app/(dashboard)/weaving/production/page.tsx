"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { weightTriple } from "@/lib/weavingUnits"

type Contract = { id: number; number: string; contract_meters: number; weaving_rate: number }
type Master = { id: number; code: string; name: string }
type Row = {
  id: number
  number: string
  contract_id: number
  date: string
  warp_yarn_kg: number
  weft_yarn_kg: number
  total_yarn_kg: number
  total_yarn_lbs: number
  total_yarn_bags: number
  grey_meters: number
  efficiency_pct: number
  weaving_charges: number
}

const today = () => new Date().toISOString().slice(0, 10)

export default function ProductionPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [looms, setLooms] = useState<Master[]>([])
  const [shifts, setShifts] = useState<Master[]>([])
  const [operators, setOperators] = useState<Master[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    contract_id: "", loom_id: "", shift_id: "", operator_id: "", date: today(),
    warp_yarn_kg: "", weft_yarn_kg: "", grey_meters: "", efficiency_pct: "", weaving_charges: "",
  })

  const load = useCallback(() => {
    apiFetch<Row[]>("/api/weaving/productions").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    Promise.all([
      apiFetch<Contract[]>("/api/weaving/contracts").catch(() => []),
      apiFetch<Master[]>("/api/weaving/looms").catch(() => []),
      apiFetch<Master[]>("/api/weaving/shifts").catch(() => []),
      apiFetch<Master[]>("/api/weaving/operators").catch(() => []),
    ]).then(([c, l, s, o]) => {
      setContracts(Array.isArray(c) ? c : [])
      setLooms(Array.isArray(l) ? l : [])
      setShifts(Array.isArray(s) ? s : [])
      setOperators(Array.isArray(o) ? o : [])
    })
  }, [load])

  const warp = parseFloat(form.warp_yarn_kg) || 0
  const weft = parseFloat(form.weft_yarn_kg) || 0
  const total = warp + weft
  const grey = parseFloat(form.grey_meters) || 0
  const selected = contracts.find(c => String(c.id) === form.contract_id)
  const previewEff = selected?.contract_meters
    ? (grey / selected.contract_meters) * 100
    : 0

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/weaving/productions", {
        method: "POST",
        body: JSON.stringify({
          contract_id: Number(form.contract_id),
          loom_id: form.loom_id ? Number(form.loom_id) : null,
          shift_id: form.shift_id ? Number(form.shift_id) : null,
          operator_id: form.operator_id ? Number(form.operator_id) : null,
          date: form.date,
          warp_yarn_kg: warp,
          weft_yarn_kg: weft,
          grey_meters: grey,
          efficiency_pct: form.efficiency_pct !== "" ? parseFloat(form.efficiency_pct) : null,
          weaving_charges: form.weaving_charges !== "" ? parseFloat(form.weaving_charges) : null,
        }),
      })
      setShowForm(false)
      setForm({
        contract_id: "", loom_id: "", shift_id: "", operator_id: "", date: today(),
        warp_yarn_kg: "", weft_yarn_kg: "", grey_meters: "", efficiency_pct: "", weaving_charges: "",
      })
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const cmap = Object.fromEntries(contracts.map(c => [c.id, c.number]))

  return (
    <div className="p-4 space-y-4">
      <div className="flex justify-end print:hidden">
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Production
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">WP #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Contract</th>
              <th className="px-3 py-2">Yarn used</th>
              <th className="px-3 py-2 text-right">Grey m</th>
              <th className="px-3 py-2 text-right">Eff %</th>
              <th className="px-3 py-2 text-right">Charges</th>
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
                <td className="px-3 py-2">
                  <WeightTripleDisplay kg={r.total_yarn_kg} lbs={r.total_yarn_lbs} bags={r.total_yarn_bags} />
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.grey_meters)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.efficiency_pct)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.weaving_charges)}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-[var(--text-muted)]">No production entries yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold">New Production</h2>
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
                <label className="text-xs text-[var(--text-muted)]">Date *</label>
                <input type="date" required value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Loom</label>
                <select value={form.loom_id} onChange={e => setForm(f => ({ ...f, loom_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {looms.map(l => <option key={l.id} value={l.id}>{l.code} — {l.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Shift</label>
                <select value={form.shift_id} onChange={e => setForm(f => ({ ...f, shift_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {shifts.map(s => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Operator</label>
                <select value={form.operator_id} onChange={e => setForm(f => ({ ...f, operator_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {operators.map(o => <option key={o.id} value={o.id}>{o.code} — {o.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Warp yarn kg</label>
                <input type="number" step="any" value={form.warp_yarn_kg} onChange={e => setForm(f => ({ ...f, warp_yarn_kg: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Weft yarn kg</label>
                <input type="number" step="any" value={form.weft_yarn_kg} onChange={e => setForm(f => ({ ...f, weft_yarn_kg: e.target.value }))} className={input} />
              </div>
              <div className="col-span-2 text-xs text-[var(--text-muted)]">
                Total yarn: {weightTriple(total).kg.toFixed(2)} kg · {weightTriple(total).lbs.toFixed(2)} lb · {weightTriple(total).bags.toFixed(2)} bags
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Grey meters *</label>
                <input type="number" step="any" required value={form.grey_meters} onChange={e => setForm(f => ({ ...f, grey_meters: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Efficiency % (blank = auto)</label>
                <input type="number" step="any" value={form.efficiency_pct} onChange={e => setForm(f => ({ ...f, efficiency_pct: e.target.value }))} className={input} />
                <p className="text-xs text-[var(--text-muted)] mt-1">Preview: {previewEff.toFixed(2)}%</p>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Weaving charges (blank = meters × rate)</label>
                <input type="number" step="any" value={form.weaving_charges} onChange={e => setForm(f => ({ ...f, weaving_charges: e.target.value }))} className={input} />
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
