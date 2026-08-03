"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"

const STAGES = ["opening", "carding", "drawing", "roving", "spinning", "winding"]

type Master = { id: number; code: string; name: string }
type Lot = { id: number; number: string }
type Row = {
  id: number
  number: string
  spin_lot_id: number
  stage: string
  date: string
  input_kg: number
  output_kg: number
  waste_kg: number
  yield_pct: number
  status: string
}

const today = () => new Date().toISOString().slice(0, 10)

export default function StagesPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [lots, setLots] = useState<Lot[]>([])
  const [machines, setMachines] = useState<Master[]>([])
  const [shifts, setShifts] = useState<Master[]>([])
  const [operators, setOperators] = useState<Master[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    spin_lot_id: "", stage: "opening", date: today(),
    input_kg: "", output_kg: "", waste_kg: "0",
    machine_id: "", shift_id: "", operator_id: "",
    labour_cost: "0", overhead_cost: "0", notes: "",
  })

  const load = useCallback(() => {
    apiFetch<Row[]>("/api/spinning/stages").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    Promise.all([
      apiFetch<Lot[]>("/api/spinning/lots").catch(() => []),
      apiFetch<Master[]>("/api/spinning/machines?active_only=true").catch(() => []),
      apiFetch<Master[]>("/api/spinning/shifts?active_only=true").catch(() => []),
      apiFetch<Master[]>("/api/spinning/operators?active_only=true").catch(() => []),
    ]).then(([l, m, s, o]) => {
      setLots(Array.isArray(l) ? l : [])
      setMachines(Array.isArray(m) ? m : [])
      setShifts(Array.isArray(s) ? s : [])
      setOperators(Array.isArray(o) ? o : [])
    })
  }, [load])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/spinning/stages", {
        method: "POST",
        body: JSON.stringify({
          spin_lot_id: Number(form.spin_lot_id),
          stage: form.stage,
          date: form.date,
          input_kg: parseFloat(form.input_kg) || 0,
          output_kg: parseFloat(form.output_kg) || 0,
          waste_kg: parseFloat(form.waste_kg) || 0,
          machine_id: form.machine_id ? Number(form.machine_id) : null,
          shift_id: form.shift_id ? Number(form.shift_id) : null,
          operator_id: form.operator_id ? Number(form.operator_id) : null,
          labour_cost: parseFloat(form.labour_cost) || 0,
          overhead_cost: parseFloat(form.overhead_cost) || 0,
          notes: form.notes || null,
        }),
      })
      setShowForm(false)
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const lmap = Object.fromEntries(lots.map(l => [l.id, l.number]))

  return (
    <div className="p-4 space-y-4">
      <div className="flex justify-end print:hidden">
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Stage Entry
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">SE #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Lot</th>
              <th className="px-3 py-2">Stage</th>
              <th className="px-3 py-2 text-right">Input kg</th>
              <th className="px-3 py-2 text-right">Output kg</th>
              <th className="px-3 py-2 text-right">Yield %</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(r => (
              <tr key={r.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap font-medium">{r.number}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="px-3 py-2">
                  <Link href={`/spinning/lots/${r.spin_lot_id}`} className="text-[var(--primary)]">
                    {lmap[r.spin_lot_id] || `#${r.spin_lot_id}`}
                  </Link>
                </td>
                <td className="px-3 py-2 capitalize">{r.stage}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.input_kg)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.output_kg)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.yield_pct)}</td>
                <td className="px-3 py-2 capitalize">{r.status}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-[var(--text-muted)]">No stage entries yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold">New Stage Entry</h2>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Spin lot *</label>
                <select required value={form.spin_lot_id} onChange={e => setForm(f => ({ ...f, spin_lot_id: e.target.value }))} className={input}>
                  <option value="">Select…</option>
                  {lots.map(l => <option key={l.id} value={l.id}>{l.number}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Stage *</label>
                <select required value={form.stage} onChange={e => setForm(f => ({ ...f, stage: e.target.value }))} className={input}>
                  {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Date *</label>
                <input type="date" required value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Input kg *</label>
                <input type="number" step="any" required value={form.input_kg} onChange={e => setForm(f => ({ ...f, input_kg: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Output kg *</label>
                <input type="number" step="any" required value={form.output_kg} onChange={e => setForm(f => ({ ...f, output_kg: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Waste kg</label>
                <input type="number" step="any" value={form.waste_kg} onChange={e => setForm(f => ({ ...f, waste_kg: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Machine</label>
                <select value={form.machine_id} onChange={e => setForm(f => ({ ...f, machine_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {machines.map(m => <option key={m.id} value={m.id}>{m.code}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Shift</label>
                <select value={form.shift_id} onChange={e => setForm(f => ({ ...f, shift_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {shifts.map(s => <option key={s.id} value={s.id}>{s.code}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Operator</label>
                <select value={form.operator_id} onChange={e => setForm(f => ({ ...f, operator_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {operators.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
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
