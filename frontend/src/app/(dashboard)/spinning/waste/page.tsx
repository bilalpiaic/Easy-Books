"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"

const STAGES = ["opening", "carding", "drawing", "roving", "spinning", "winding"]

type Lot = { id: number; number: string }
type WasteType = { id: number; code: string; name: string }
type Row = {
  id: number
  number: string
  spin_lot_id: number
  stage: string
  waste_type_id: number
  date: string
  qty_kg: number
  cost_value: number
  status: string
}

const today = () => new Date().toISOString().slice(0, 10)

export default function WastePage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [lots, setLots] = useState<Lot[]>([])
  const [wasteTypes, setWasteTypes] = useState<WasteType[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    spin_lot_id: "", stage: "carding", waste_type_id: "", date: today(),
    qty_kg: "", cost_value: "0", notes: "",
  })

  const load = useCallback(() => {
    apiFetch<Row[]>("/api/spinning/waste-logs").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    Promise.all([
      apiFetch<Lot[]>("/api/spinning/lots").catch(() => []),
      apiFetch<WasteType[]>("/api/spinning/waste-types?active_only=true").catch(() => []),
    ]).then(([l, w]) => {
      setLots(Array.isArray(l) ? l : [])
      setWasteTypes(Array.isArray(w) ? w : [])
    })
  }, [load])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/spinning/waste-logs", {
        method: "POST",
        body: JSON.stringify({
          spin_lot_id: Number(form.spin_lot_id),
          stage: form.stage,
          waste_type_id: Number(form.waste_type_id),
          date: form.date,
          qty_kg: parseFloat(form.qty_kg) || 0,
          cost_value: parseFloat(form.cost_value) || 0,
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
  const wmap = Object.fromEntries(wasteTypes.map(w => [w.id, w.name]))

  return (
    <div className="p-4 space-y-4">
      <div className="flex justify-end print:hidden">
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Waste Log
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">WL #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Lot</th>
              <th className="px-3 py-2">Stage</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2 text-right">Qty kg</th>
              <th className="px-3 py-2 text-right">Cost</th>
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
                <td className="px-3 py-2">{wmap[r.waste_type_id] || `#${r.waste_type_id}`}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.qty_kg)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.cost_value)}</td>
                <td className="px-3 py-2 capitalize">{r.status}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-[var(--text-muted)]">No waste logs yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">New Waste Log</h2>
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
                <label className="text-xs text-[var(--text-muted)]">Waste type *</label>
                <select required value={form.waste_type_id} onChange={e => setForm(f => ({ ...f, waste_type_id: e.target.value }))} className={input}>
                  <option value="">Select…</option>
                  {wasteTypes.map(w => <option key={w.id} value={w.id}>{w.code} — {w.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Date *</label>
                <input type="date" required value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Qty kg *</label>
                <input type="number" step="any" required value={form.qty_kg} onChange={e => setForm(f => ({ ...f, qty_kg: e.target.value }))} className={input} />
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
