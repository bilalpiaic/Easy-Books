"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import type { WeightTriple } from "@/lib/spinningUnits"

type Lot = {
  id: number
  number: string
  yarn_spec_id: number
  start_date: string
  target_output_kg: number
  target_weight: WeightTriple
  output_kg: number
  output_weight: WeightTriple
  status: string
  cost_per_kg: number
}

type YarnSpec = { id: number; code: string; name: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function LotsListPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Lot[] | null>(null)
  const [specs, setSpecs] = useState<Record<number, string>>({})
  const [status, setStatus] = useState("")
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({ yarn_spec_id: "", start_date: today(), target_output_kg: "", notes: "" })

  function load() {
    const qs = status ? `?status=${status}` : ""
    apiFetch<Lot[]>(`/api/spinning/lots${qs}`).then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }

  useEffect(() => {
    load()
    apiFetch<YarnSpec[]>("/api/spinning/yarn-specs?active_only=true").then(s => {
      const map: Record<number, string> = {}
      for (const x of Array.isArray(s) ? s : []) map[x.id] = `${x.code} — ${x.name}`
      setSpecs(map)
    }).catch(() => setSpecs({}))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/spinning/lots", {
        method: "POST",
        body: JSON.stringify({
          yarn_spec_id: Number(form.yarn_spec_id),
          start_date: form.start_date,
          target_output_kg: parseFloat(form.target_output_kg) || 0,
          notes: form.notes || null,
        }),
      })
      setShowForm(false)
      setForm({ yarn_spec_id: "", start_date: today(), target_output_kg: "", notes: "" })
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const yarnSpecs = Object.entries(specs).map(([id, name]) => ({ id: Number(id), name }))

  return (
    <div className="p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <select value={status} onChange={e => setStatus(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--border)] rounded-lg">
          <option value="">All statuses</option>
          {["draft", "in_process", "completed", "closed"].map(s => (
            <option key={s} value={s}>{s.replace("_", " ")}</option>
          ))}
        </select>
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Lot
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Lot #</th>
              <th className="px-3 py-2">Start</th>
              <th className="px-3 py-2">Yarn spec</th>
              <th className="px-3 py-2">Target</th>
              <th className="px-3 py-2">Output</th>
              <th className="px-3 py-2 text-right">Cost/kg</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(l => (
              <tr key={l.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/spinning/lots/${l.id}`} className="text-[var(--primary)] font-medium">{l.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(l.start_date)}</td>
                <td className="px-3 py-2">{specs[l.yarn_spec_id] || `#${l.yarn_spec_id}`}</td>
                <td className="px-3 py-2"><WeightTripleDisplay triple={l.target_weight} /></td>
                <td className="px-3 py-2"><WeightTripleDisplay triple={l.output_weight} /></td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(l.cost_per_kg)}</td>
                <td className="px-3 py-2 capitalize">{l.status.replace("_", " ")}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-[var(--text-muted)]">No spin lots yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">New Spin Lot</h2>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[var(--text-muted)]">Yarn spec *</label>
                <select required value={form.yarn_spec_id} onChange={e => setForm(f => ({ ...f, yarn_spec_id: e.target.value }))} className={input}>
                  <option value="">Select…</option>
                  {yarnSpecs.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-[var(--text-muted)]">Start date *</label>
                  <input type="date" required value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} className={input} />
                </div>
                <div>
                  <label className="text-xs text-[var(--text-muted)]">Target output kg *</label>
                  <input type="number" step="any" required value={form.target_output_kg} onChange={e => setForm(f => ({ ...f, target_output_kg: e.target.value }))} className={input} />
                </div>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Notes</label>
                <input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className={input} />
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
