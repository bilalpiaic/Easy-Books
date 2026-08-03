"use client"

import { useCallback, useEffect, useState } from "react"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { RateKgLb, WeightTripleDisplay } from "@/components/weaving/WeightDisplays"

type Customer = { id: number; name: string }
type YarnSpec = { id: number; code: string; name: string }
type Row = {
  id: number
  number: string
  customer_id: number
  yarn_spec_id: number
  date: string
  cones_count: number
  net_kg: number
  net_lbs: number
  rate_per_kg: number
  dispatch_value: number
  status: string
}

const today = () => new Date().toISOString().slice(0, 10)

export default function DispatchPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [customers, setCustomers] = useState<Record<number, string>>({})
  const [specs, setSpecs] = useState<Record<number, string>>({})
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    customer_id: "", yarn_spec_id: "", date: today(),
    cones_count: "", net_kg: "", rate_per_kg: "", notes: "",
  })

  const load = useCallback(() => {
    apiFetch<Row[]>("/api/spinning/dispatches").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    Promise.all([
      apiFetch<{ items: Customer[] }>("/api/customers?limit=500").catch(() => ({ items: [] })),
      apiFetch<YarnSpec[]>("/api/spinning/yarn-specs?active_only=true").catch(() => []),
    ]).then(([c, s]) => {
      const cmap: Record<number, string> = {}
      for (const x of c.items ?? []) cmap[x.id] = x.name
      setCustomers(cmap)
      const smap: Record<number, string> = {}
      for (const x of Array.isArray(s) ? s : []) smap[x.id] = `${x.code} — ${x.name}`
      setSpecs(smap)
    })
  }, [load])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/spinning/dispatches", {
        method: "POST",
        body: JSON.stringify({
          customer_id: Number(form.customer_id),
          yarn_spec_id: Number(form.yarn_spec_id),
          date: form.date,
          cones_count: parseInt(form.cones_count, 10) || 0,
          net_kg: parseFloat(form.net_kg) || 0,
          rate_per_kg: parseFloat(form.rate_per_kg) || 0,
          notes: form.notes || null,
        }),
      })
      setShowForm(false)
      setForm({ customer_id: "", yarn_spec_id: "", date: today(), cones_count: "", net_kg: "", rate_per_kg: "", notes: "" })
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  async function approve(id: number) {
    try {
      await apiFetch(`/api/spinning/dispatches/${id}/approve`, { method: "PATCH" })
      load()
    } catch { /* ignore */ }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const netKg = parseFloat(form.net_kg) || 0
  const rateKg = parseFloat(form.rate_per_kg) || 0
  const preview = netKg * rateKg

  return (
    <div className="p-4 space-y-4">
      <div className="flex justify-end print:hidden">
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Dispatch
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">YD #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Customer</th>
              <th className="px-3 py-2">Yarn spec</th>
              <th className="px-3 py-2 text-right">Cones</th>
              <th className="px-3 py-2">Net weight</th>
              <th className="px-3 py-2">Rate</th>
              <th className="px-3 py-2 text-right">Value</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 print:hidden"></th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(r => (
              <tr key={r.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap font-medium">{r.number}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="px-3 py-2">{customers[r.customer_id] || `#${r.customer_id}`}</td>
                <td className="px-3 py-2">{specs[r.yarn_spec_id] || `#${r.yarn_spec_id}`}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.cones_count}</td>
                <td className="px-3 py-2"><WeightTripleDisplay kg={r.net_kg} lbs={r.net_lbs} /></td>
                <td className="px-3 py-2"><RateKgLb ratePerKg={r.rate_per_kg} /></td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.dispatch_value)}</td>
                <td className="px-3 py-2 capitalize">{r.status}</td>
                <td className="px-3 py-2 print:hidden">
                  {r.status === "draft" && (
                    <button onClick={() => approve(r.id)} className="text-xs text-[var(--primary)]">Approve</button>
                  )}
                </td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={10} className="px-3 py-8 text-center text-[var(--text-muted)]">No dispatches yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">New Yarn Dispatch</h2>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Customer *</label>
                <select required value={form.customer_id} onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))} className={input}>
                  <option value="">Select…</option>
                  {Object.entries(customers).map(([id, name]) => (
                    <option key={id} value={id}>{name}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Yarn spec *</label>
                <select required value={form.yarn_spec_id} onChange={e => setForm(f => ({ ...f, yarn_spec_id: e.target.value }))} className={input}>
                  <option value="">Select…</option>
                  {Object.entries(specs).map(([id, name]) => (
                    <option key={id} value={id}>{name}</option>
                  ))}
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
                <label className="text-xs text-[var(--text-muted)]">Rate / kg *</label>
                <input type="number" step="any" required value={form.rate_per_kg} onChange={e => setForm(f => ({ ...f, rate_per_kg: e.target.value }))} className={input} />
              </div>
              <div className="col-span-2 text-xs text-[var(--text-muted)] rounded-lg bg-[var(--bg)] p-2">
                Preview value: {preview.toFixed(2)}
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
