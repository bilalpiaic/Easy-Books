"use client"

import { useEffect, useState } from "react"
import { Package, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface SimBatch { id: number; operator_name: string; batch_reference: string; qty_available: number; unit_cost: string }
interface RSOAgent { id: number; name: string }
interface Activation {
  id: number; sim_batch_id: number; activation_date: string
  activation_type: string; customer_name: string | null
  sale_price: string; status: string; rso_id: number | null
}

function fmt(v: string) {
  return "PKR " + parseFloat(v).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

interface SaleFormProps { batches: SimBatch[]; rsos: RSOAgent[]; onCreated: () => void; onCancel: () => void }
function SaleForm({ batches, rsos, onCreated, onCancel }: SaleFormProps) {
  const [mode, setMode] = useState<"counter" | "rso">("counter")
  const [form, setForm] = useState({
    sim_batch_id: "", activation_date: new Date().toISOString().split("T")[0],
    sim_number: "", customer_name: "", customer_cnic: "", sale_price: "",
    rso_id: "", qty: "1", face_price_per_sim: "",
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setErr(null)
    try {
      if (mode === "counter") {
        await apiFetch("/api/telecom/sim-sales", { method: "POST", body: JSON.stringify({
          sim_batch_id: parseInt(form.sim_batch_id),
          activation_date: form.activation_date,
          sim_number: form.sim_number || undefined,
          customer_name: form.customer_name || undefined,
          customer_cnic: form.customer_cnic || undefined,
          sale_price: parseFloat(form.sale_price),
        })})
      } else {
        await apiFetch("/api/telecom/sim-issues", { method: "POST", body: JSON.stringify({
          sim_batch_id: parseInt(form.sim_batch_id),
          rso_id: parseInt(form.rso_id),
          issue_date: form.activation_date,
          qty: parseInt(form.qty),
          face_price_per_sim: parseFloat(form.face_price_per_sim),
        })})
      }
      onCreated()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally { setSaving(false) }
  }

  return (
    <form onSubmit={submit} className="bg-white border border-[#b8943f]/20 rounded-xl p-5 space-y-3">
      <div className="flex gap-2 mb-2">
        {(["counter","rso"] as const).map(m => (
          <button key={m} type="button" onClick={() => setMode(m)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors
              ${mode === m ? "bg-[#b8943f] text-white border-[#b8943f]" : "border-[#b8943f]/30 text-[#1a1814]"}`}>
            {m === "counter" ? "Counter Sale" : "RSO Issue"}
          </button>
        ))}
      </div>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">SIM Batch</label>
          <select required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.sim_batch_id} onChange={e => setForm(f => ({...f, sim_batch_id: e.target.value}))}>
            <option value="">Select batch…</option>
            {batches.filter(b => b.qty_available > 0).map(b => (
              <option key={b.id} value={b.id}>{b.operator_name} · {b.batch_reference} ({b.qty_available} avail)</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Date</label>
          <input type="date" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.activation_date} onChange={e => setForm(f => ({...f, activation_date: e.target.value}))} />
        </div>
        {mode === "counter" ? (
          <>
            <div>
              <label className="text-xs text-[#1a1814]/60 block mb-1">SIM Number (optional)</label>
              <input className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.sim_number} onChange={e => setForm(f => ({...f, sim_number: e.target.value}))} />
            </div>
            <div>
              <label className="text-xs text-[#1a1814]/60 block mb-1">Sale Price (PKR)</label>
              <input type="number" min="0" step="0.01" required className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.sale_price} onChange={e => setForm(f => ({...f, sale_price: e.target.value}))} />
            </div>
            <div>
              <label className="text-xs text-[#1a1814]/60 block mb-1">Customer Name</label>
              <input className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.customer_name} onChange={e => setForm(f => ({...f, customer_name: e.target.value}))} />
            </div>
            <div>
              <label className="text-xs text-[#1a1814]/60 block mb-1">Customer CNIC</label>
              <input className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.customer_cnic} onChange={e => setForm(f => ({...f, customer_cnic: e.target.value}))} />
            </div>
          </>
        ) : (
          <>
            <div>
              <label className="text-xs text-[#1a1814]/60 block mb-1">RSO Agent</label>
              <select required className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.rso_id} onChange={e => setForm(f => ({...f, rso_id: e.target.value}))}>
                <option value="">Select RSO…</option>
                {rsos.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-[#1a1814]/60 block mb-1">Qty</label>
              <input type="number" min="1" required className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.qty} onChange={e => setForm(f => ({...f, qty: e.target.value}))} />
            </div>
            <div>
              <label className="text-xs text-[#1a1814]/60 block mb-1">Face Price per SIM (PKR)</label>
              <input type="number" min="0" step="0.01" required className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.face_price_per_sim} onChange={e => setForm(f => ({...f, face_price_per_sim: e.target.value}))} />
            </div>
          </>
        )}
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={saving}
          className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium disabled:opacity-50">
          {saving ? "Posting…" : mode === "counter" ? "Post Sale" : "Issue to RSO"}
        </button>
        <button type="button" onClick={onCancel} className="px-4 py-2 rounded-lg border text-sm">Cancel</button>
      </div>
    </form>
  )
}

export default function SimSalesPage() {
  const [activations, setActivations] = useState<Activation[]>([])
  const [batches, setBatches] = useState<SimBatch[]>([])
  const [rsos, setRsos] = useState<RSOAgent[]>([])
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      apiFetch<{ items: SimBatch[] }>("/api/telecom/sim-batches"),
      apiFetch<{ items: RSOAgent[] }>("/api/telecom/rso-agents"),
    ])
      .then(([b, r]) => { setBatches(b.items); setRsos(r.items) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false))

    // Collect activations across all batches
    apiFetch<{ items: SimBatch[] }>("/api/telecom/sim-batches")
      .then(d => Promise.all(d.items.map(b =>
        apiFetch<{ activations: Activation[] }>(`/api/telecom/sim-batches/${b.id}`)
          .then(r => r.activations)
      )))
      .then(all => setActivations(all.flat().sort((a, b) => b.activation_date.localeCompare(a.activation_date))))
      .catch(() => {})
  }

  useEffect(() => { load() }, [])

  const batchName = (id: number) => {
    const b = batches.find(b => b.id === id)
    return b ? `${b.operator_name} · ${b.batch_reference}` : `Batch #${id}`
  }
  const rsoName = (id: number | null) => id ? (rsos.find(r => r.id === id)?.name ?? `RSO #${id}`) : "—"

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Package className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">SIM Sales & Issues</h1>
            <p className="text-sm text-[#1a1814]/60">Counter sales and RSO channel SIM issues.</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium">
          <Plus className="w-4 h-4" /> New
        </button>
      </header>

      <HelpCallout title="Counter sale vs RSO issue" tone="tip">
        <b>Counter sale</b>: customer buys at service counter (Dr Cash / Cr 4030 + COGS entry).
        <b> RSO issue</b>: SIMs given to RSO channel (Dr 1120 RSO Receivables / Cr 1200 + margin to 4050).
      </HelpCallout>

      {showForm && <SaleForm batches={batches} rsos={rsos} onCreated={() => { setShowForm(false); load() }} onCancel={() => setShowForm(false)} />}
      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {loading ? <p className="text-sm text-[#1a1814]/50">Loading…</p> : (
        <div className="rounded-xl border border-[#b8943f]/20 bg-white overflow-hidden">
          {activations.length === 0 ? (
            <p className="text-sm text-[#1a1814]/40 p-8 text-center">No SIM sales or issues yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[#1a1814]/40 uppercase tracking-wide border-b border-[#b8943f]/10">
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">Batch</th>
                  <th className="px-4 py-3 text-left">Type</th>
                  <th className="px-4 py-3 text-left">Customer / RSO</th>
                  <th className="px-4 py-3 text-right">Price</th>
                  <th className="px-4 py-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {activations.map(a => (
                  <tr key={a.id} className="border-b border-[#b8943f]/5 hover:bg-[#f6f3ee]">
                    <td className="px-4 py-2 font-mono text-xs">{a.activation_date}</td>
                    <td className="px-4 py-2 text-xs">{batchName(a.sim_batch_id)}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${a.activation_type === "counter_sale" ? "bg-blue-50 text-blue-700" : "bg-amber-50 text-amber-700"}`}>
                        {a.activation_type === "counter_sale" ? "Counter" : "RSO Issue"}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-[#1a1814]/70">
                      {a.activation_type === "counter_sale" ? (a.customer_name || "—") : rsoName(a.rso_id)}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">{fmt(a.sale_price)}</td>
                    <td className="px-4 py-2 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs
                        ${a.status === "active" ? "bg-emerald-50 text-emerald-700"
                         : a.status === "rejected" ? "bg-red-50 text-red-700"
                         : "bg-slate-50 text-slate-700"}`}>
                        {a.status}
                      </span>
                    </td>
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
