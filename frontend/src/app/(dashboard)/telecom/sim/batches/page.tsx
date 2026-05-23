"use client"

import { useEffect, useState } from "react"
import { Smartphone, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface SimBatch {
  id: number
  operator_name: string
  batch_reference: string
  qty_received: number
  qty_activated: number
  qty_issued_rso: number
  qty_available: number
  unit_cost: string
  received_date: string
}

function fmt(v: string | number) {
  return "PKR " + parseFloat(String(v)).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

interface AddBatchFormProps { onCreated: () => void; onCancel: () => void }
function AddBatchForm({ onCreated, onCancel }: AddBatchFormProps) {
  const [form, setForm] = useState({
    operator_name: "", batch_reference: "", series_from: "", series_to: "",
    qty_received: "", unit_cost: "", received_date: new Date().toISOString().split("T")[0], notes: "",
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setErr(null)
    try {
      const body = {
        operator_name: form.operator_name, batch_reference: form.batch_reference,
        series_from: form.series_from || undefined, series_to: form.series_to || undefined,
        qty_received: parseInt(form.qty_received), unit_cost: parseFloat(form.unit_cost),
        received_date: form.received_date, notes: form.notes || undefined,
      }
      await apiFetch("/api/telecom/sim-batches", { method: "POST", body: JSON.stringify(body) })
      onCreated()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally { setSaving(false) }
  }

  return (
    <form onSubmit={submit} className="bg-white border border-[#b8943f]/20 rounded-xl p-5 space-y-3">
      <h3 className="font-semibold text-[#1a1814]">Receive SIM Batch</h3>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Operator</label>
          <select className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.operator_name} onChange={e => setForm(f => ({...f, operator_name: e.target.value}))}>
            <option value="">Select…</option>
            {["Jazz (PMCL)","Telenor Pakistan","Zong (CMPak)","Ufone"].map(o => <option key={o}>{o}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Batch Reference</label>
          <input required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.batch_reference} onChange={e => setForm(f => ({...f, batch_reference: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Series From</label>
          <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Optional"
            value={form.series_from} onChange={e => setForm(f => ({...f, series_from: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Series To</label>
          <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Optional"
            value={form.series_to} onChange={e => setForm(f => ({...f, series_to: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Qty Received</label>
          <input type="number" min="1" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.qty_received} onChange={e => setForm(f => ({...f, qty_received: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Unit Cost (PKR / SIM)</label>
          <input type="number" min="0" step="0.01" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.unit_cost} onChange={e => setForm(f => ({...f, unit_cost: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Received Date</label>
          <input type="date" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.received_date} onChange={e => setForm(f => ({...f, received_date: e.target.value}))} />
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={saving}
          className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium disabled:opacity-50">
          {saving ? "Saving…" : "Record Batch"}
        </button>
        <button type="button" onClick={onCancel} className="px-4 py-2 rounded-lg border text-sm">Cancel</button>
      </div>
    </form>
  )
}

export default function SimBatchesPage() {
  const [batches, setBatches] = useState<SimBatch[]>([])
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    apiFetch<{ items: SimBatch[] }>("/api/telecom/sim-batches")
      .then(d => setBatches(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Smartphone className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">SIM Batches</h1>
            <p className="text-sm text-[#1a1814]/60">SIM card batches received from the telecom company.</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium">
          <Plus className="w-4 h-4" /> Receive Batch
        </button>
      </header>

      <HelpCallout title="SIM inventory" tone="tip">
        SIMs received are recorded here. The cost is typically a Tracker stock debit — link to the
        Tracker transaction for reconciliation. SIMs sold at the counter go to <b>SIM Sales</b>;
        SIMs issued to RSOs go to <b>SIM Issues</b> (also in SIM Sales page).
      </HelpCallout>

      {showForm && <AddBatchForm onCreated={() => { setShowForm(false); load() }} onCancel={() => setShowForm(false)} />}
      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {loading ? <p className="text-sm text-[#1a1814]/50">Loading…</p> : (
        <div className="rounded-xl border border-[#b8943f]/20 bg-white overflow-hidden">
          {batches.length === 0 ? (
            <p className="text-sm text-[#1a1814]/40 p-8 text-center">No SIM batches yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[#1a1814]/40 uppercase tracking-wide border-b border-[#b8943f]/10">
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">Operator</th>
                  <th className="px-4 py-3 text-left">Batch Ref</th>
                  <th className="px-4 py-3 text-right">Received</th>
                  <th className="px-4 py-3 text-right">Sold</th>
                  <th className="px-4 py-3 text-right">RSO</th>
                  <th className="px-4 py-3 text-right">Available</th>
                  <th className="px-4 py-3 text-right">Unit Cost</th>
                </tr>
              </thead>
              <tbody>
                {batches.map(b => (
                  <tr key={b.id} className="border-b border-[#b8943f]/5 hover:bg-[#f6f3ee]">
                    <td className="px-4 py-2 font-mono text-xs">{b.received_date}</td>
                    <td className="px-4 py-2">{b.operator_name}</td>
                    <td className="px-4 py-2 font-mono text-xs">{b.batch_reference}</td>
                    <td className="px-4 py-2 text-right">{b.qty_received}</td>
                    <td className="px-4 py-2 text-right">{b.qty_activated}</td>
                    <td className="px-4 py-2 text-right">{b.qty_issued_rso}</td>
                    <td className={`px-4 py-2 text-right font-semibold ${b.qty_available === 0 ? "text-[#1a1814]/30" : "text-emerald-700"}`}>
                      {b.qty_available}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">{fmt(b.unit_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
