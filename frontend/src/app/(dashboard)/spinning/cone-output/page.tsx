"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"

type Lot = { id: number; number: string }
type Row = {
  id: number
  number: string
  spin_lot_id: number
  date: string
  cones_count: number
  net_kg: number
  net_lbs: number
  quality_grade?: string | null
  status: string
  unit_cost: number
  total_cost: number
}

const today = () => new Date().toISOString().slice(0, 10)

export default function ConeOutputPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [lots, setLots] = useState<Lot[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    spin_lot_id: "", date: today(), cones_count: "", net_kg: "",
    quality_grade: "", lot_no: "", notes: "",
  })

  const load = useCallback(() => {
    apiFetch<Row[]>("/api/spinning/cone-outputs").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    apiFetch<Lot[]>("/api/spinning/lots").then(l => setLots(Array.isArray(l) ? l : [])).catch(() => setLots([]))
  }, [load])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/spinning/cone-outputs", {
        method: "POST",
        body: JSON.stringify({
          spin_lot_id: Number(form.spin_lot_id),
          date: form.date,
          cones_count: parseInt(form.cones_count, 10) || 0,
          net_kg: parseFloat(form.net_kg) || 0,
          quality_grade: form.quality_grade || null,
          lot_no: form.lot_no || null,
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

  async function approve(id: number) {
    try {
      await apiFetch(`/api/spinning/cone-outputs/${id}/approve`, { method: "PATCH" })
      load()
    } catch { /* ignore */ }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const lmap = Object.fromEntries(lots.map(l => [l.id, l.number]))

  return (
    <div className="p-4 space-y-4">
      <div className="flex justify-end print:hidden">
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Cone Output
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">CO #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Lot</th>
              <th className="px-3 py-2 text-right">Cones</th>
              <th className="px-3 py-2">Net weight</th>
              <th className="px-3 py-2">Grade</th>
              <th className="px-3 py-2 text-right">Total cost</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 print:hidden"></th>
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
                <td className="px-3 py-2 text-right tabular-nums">{r.cones_count}</td>
                <td className="px-3 py-2"><WeightTripleDisplay kg={r.net_kg} lbs={r.net_lbs} /></td>
                <td className="px-3 py-2">{r.quality_grade || "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.total_cost)}</td>
                <td className="px-3 py-2 capitalize">{r.status}</td>
                <td className="px-3 py-2 print:hidden">
                  {r.status === "draft" && (
                    <button onClick={() => approve(r.id)} className="text-xs text-[var(--primary)]">Approve</button>
                  )}
                </td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={9} className="px-3 py-8 text-center text-[var(--text-muted)]">No cone outputs yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">New Cone Output</h2>
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
                <label className="text-xs text-[var(--text-muted)]">Date *</label>
                <input type="date" required value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Cones *</label>
                <input type="number" required value={form.cones_count} onChange={e => setForm(f => ({ ...f, cones_count: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Net kg *</label>
                <input type="number" step="any" required value={form.net_kg} onChange={e => setForm(f => ({ ...f, net_kg: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Quality grade</label>
                <input value={form.quality_grade} onChange={e => setForm(f => ({ ...f, quality_grade: e.target.value }))} className={input} />
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
