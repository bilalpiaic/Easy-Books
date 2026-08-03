"use client"

import { useCallback, useEffect, useState } from "react"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import type { WeightTriple } from "@/lib/spinningUnits"

type Plan = {
  id: number
  number: string
  plan_date: string
  yarn_spec_id: number
  target_kg: number
  target_weight: WeightTriple
  status: string
  customer_id?: number | null
  notes?: string | null
}

type YarnSpec = { id: number; code: string; name: string }
type Customer = { id: number; name: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function PlansPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Plan[] | null>(null)
  const [specs, setSpecs] = useState<YarnSpec[]>([])
  const [customers, setCustomers] = useState<Record<number, string>>({})
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({ plan_date: today(), yarn_spec_id: "", target_kg: "", customer_id: "", notes: "" })

  const load = useCallback(() => {
    apiFetch<Plan[]>("/api/spinning/plans").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    Promise.all([
      apiFetch<YarnSpec[]>("/api/spinning/yarn-specs?active_only=true").catch(() => []),
      apiFetch<{ items: Customer[] }>("/api/customers?limit=500").catch(() => ({ items: [] })),
    ]).then(([s, c]) => {
      setSpecs(Array.isArray(s) ? s : [])
      const map: Record<number, string> = {}
      for (const x of c.items ?? []) map[x.id] = x.name
      setCustomers(map)
    })
  }, [load])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/spinning/plans", {
        method: "POST",
        body: JSON.stringify({
          plan_date: form.plan_date,
          yarn_spec_id: Number(form.yarn_spec_id),
          target_kg: parseFloat(form.target_kg) || 0,
          customer_id: form.customer_id ? Number(form.customer_id) : null,
          notes: form.notes || null,
        }),
      })
      setShowForm(false)
      setForm({ plan_date: today(), yarn_spec_id: "", target_kg: "", customer_id: "", notes: "" })
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  async function approve(id: number) {
    try {
      await apiFetch(`/api/spinning/plans/${id}/approve`, { method: "PATCH" })
      load()
    } catch { /* ignore */ }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const specMap = Object.fromEntries(specs.map(s => [s.id, `${s.code} — ${s.name}`]))

  return (
    <div className="p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">Production Plans</h1>
          <p className="text-sm text-[var(--text-muted)]">Planned yarn output by spec and date</p>
        </div>
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Plan
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Plan #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Yarn spec</th>
              <th className="px-3 py-2">Target weight</th>
              <th className="px-3 py-2">Customer</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right print:hidden">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(r => (
              <tr key={r.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap font-medium">{r.number}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.plan_date)}</td>
                <td className="px-3 py-2">{specMap[r.yarn_spec_id] || `#${r.yarn_spec_id}`}</td>
                <td className="px-3 py-2"><WeightTripleDisplay triple={r.target_weight} /></td>
                <td className="px-3 py-2">{r.customer_id ? (customers[r.customer_id] || `#${r.customer_id}`) : "—"}</td>
                <td className="px-3 py-2 capitalize">{r.status}</td>
                <td className="px-3 py-2 text-right print:hidden">
                  {r.status === "draft" && (
                    <button onClick={() => approve(r.id)} className="text-xs text-[var(--primary)]">Approve</button>
                  )}
                </td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-[var(--text-muted)]">No plans yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">New Production Plan</h2>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-[var(--text-muted)]">Plan date *</label>
                <input type="date" required value={form.plan_date} onChange={e => setForm(f => ({ ...f, plan_date: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Target kg *</label>
                <input type="number" step="any" required value={form.target_kg} onChange={e => setForm(f => ({ ...f, target_kg: e.target.value }))} className={input} />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Yarn spec *</label>
                <select required value={form.yarn_spec_id} onChange={e => setForm(f => ({ ...f, yarn_spec_id: e.target.value }))} className={input}>
                  <option value="">Select…</option>
                  {specs.map(s => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Customer</label>
                <select value={form.customer_id} onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {Object.entries(customers).map(([id, name]) => (
                    <option key={id} value={id}>{name}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
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
