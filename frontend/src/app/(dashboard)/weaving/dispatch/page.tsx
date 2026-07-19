"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"

type Contract = {
  id: number
  number: string
  fabric_return_price_per_meter: number
  weaving_rate: number
}
type Row = {
  id: number
  number: string
  contract_id: number
  date: string
  meters: number
  dispatch_value: number
  weaving_charges_billed: number
  net_receivable: number
}

const today = () => new Date().toISOString().slice(0, 10)

export default function DispatchPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    contract_id: "", date: today(), meters: "",
    dispatch_value: "", weaving_charges_billed: "", net_receivable: "",
  })

  const load = useCallback(() => {
    apiFetch<Row[]>("/api/weaving/dispatches").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    apiFetch<Contract[]>("/api/weaving/contracts").then(c => setContracts(Array.isArray(c) ? c : [])).catch(() => setContracts([]))
  }, [load])

  const meters = parseFloat(form.meters) || 0
  const selected = contracts.find(c => String(c.id) === form.contract_id)
  const previewValue = selected ? meters * selected.fabric_return_price_per_meter : 0
  const previewBilled = selected ? meters * selected.weaving_rate : 0
  const previewNet = previewValue - previewBilled

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/weaving/dispatches", {
        method: "POST",
        body: JSON.stringify({
          contract_id: Number(form.contract_id),
          date: form.date,
          meters,
          dispatch_value: form.dispatch_value !== "" ? parseFloat(form.dispatch_value) : null,
          weaving_charges_billed: form.weaving_charges_billed !== "" ? parseFloat(form.weaving_charges_billed) : null,
          net_receivable: form.net_receivable !== "" ? parseFloat(form.net_receivable) : null,
        }),
      })
      setShowForm(false)
      setForm({ contract_id: "", date: today(), meters: "", dispatch_value: "", weaving_charges_billed: "", net_receivable: "" })
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
          <Plus className="w-4 h-4" /> New Dispatch
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">WD #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Contract</th>
              <th className="px-3 py-2 text-right">Meters</th>
              <th className="px-3 py-2 text-right">Dispatch value</th>
              <th className="px-3 py-2 text-right">Weaving billed</th>
              <th className="px-3 py-2 text-right">Net receivable</th>
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
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.meters)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.dispatch_value)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.weaving_charges_billed)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.net_receivable)}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-[var(--text-muted)]">No dispatches yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">New Dispatch</h2>
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
                <label className="text-xs text-[var(--text-muted)]">Meters *</label>
                <input type="number" step="any" required value={form.meters} onChange={e => setForm(f => ({ ...f, meters: e.target.value }))} className={input} />
              </div>
              <div className="col-span-2 text-xs text-[var(--text-muted)] rounded-lg bg-[var(--bg)] p-2">
                Auto preview — value {previewValue.toFixed(2)} · billed {previewBilled.toFixed(2)} · net {previewNet.toFixed(2)}
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Dispatch value (override)</label>
                <input type="number" step="any" value={form.dispatch_value} onChange={e => setForm(f => ({ ...f, dispatch_value: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Weaving charges billed</label>
                <input type="number" step="any" value={form.weaving_charges_billed} onChange={e => setForm(f => ({ ...f, weaving_charges_billed: e.target.value }))} className={input} />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Net receivable</label>
                <input type="number" step="any" value={form.net_receivable} onChange={e => setForm(f => ({ ...f, net_receivable: e.target.value }))} className={input} />
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
