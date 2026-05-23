"use client"

import { useEffect, useState } from "react"
import { Banknote, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface Collection {
  id: number
  rso_id: number
  collection_date: string
  load_portion: string
  stock_portion: string
  total_deposited: string
  variance: string
  is_reconciled: boolean
  notes: string | null
}

interface RSOAgent { id: number; name: string }

function fmt(v: string) {
  return "PKR " + parseFloat(v).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

interface AddCollectionFormProps { rsos: RSOAgent[]; onCreated: () => void; onCancel: () => void }
function AddCollectionForm({ rsos, onCreated, onCancel }: AddCollectionFormProps) {
  const [form, setForm] = useState({
    rso_id: "", collection_date: new Date().toISOString().split("T")[0],
    load_portion: "", stock_portion: "", total_deposited: "", notes: "",
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const variance = () => {
    const t = parseFloat(form.total_deposited || "0")
    const l = parseFloat(form.load_portion || "0")
    const s = parseFloat(form.stock_portion || "0")
    return (t - l - s).toFixed(4)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setErr(null)
    try {
      const body = {
        rso_id: parseInt(form.rso_id),
        collection_date: form.collection_date,
        load_portion: parseFloat(form.load_portion || "0"),
        stock_portion: parseFloat(form.stock_portion || "0"),
        total_deposited: parseFloat(form.total_deposited),
        notes: form.notes || undefined,
      }
      await apiFetch("/api/telecom/rso-collections", { method: "POST", body: JSON.stringify(body) })
      onCreated()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally { setSaving(false) }
  }

  const varNum = parseFloat(variance())

  return (
    <form onSubmit={submit} className="bg-white border border-[#b8943f]/20 rounded-xl p-5 space-y-3">
      <h3 className="font-semibold text-[#1a1814]">Record RSO Collection</h3>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">RSO Agent</label>
          <select required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.rso_id} onChange={e => setForm(f => ({...f, rso_id: e.target.value}))}>
            <option value="">Select RSO…</option>
            {rsos.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Collection Date</label>
          <input type="date" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.collection_date} onChange={e => setForm(f => ({...f, collection_date: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Load Portion (PKR)</label>
          <input type="number" min="0" step="0.01" className="w-full border rounded-lg px-3 py-2 text-sm"
            placeholder="0.00"
            value={form.load_portion} onChange={e => setForm(f => ({...f, load_portion: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Stock Portion (PKR)</label>
          <input type="number" min="0" step="0.01" className="w-full border rounded-lg px-3 py-2 text-sm"
            placeholder="0.00"
            value={form.stock_portion} onChange={e => setForm(f => ({...f, stock_portion: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Total Deposited (PKR)</label>
          <input type="number" min="0.01" step="0.01" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.total_deposited} onChange={e => setForm(f => ({...f, total_deposited: e.target.value}))} />
        </div>
        <div className="flex items-end">
          {form.total_deposited && (
            <p className={`text-sm ${Math.abs(varNum) < 0.01 ? "text-emerald-700" : "text-amber-700"}`}>
              Variance: <span className="font-mono font-semibold">PKR {varNum.toFixed(2)}</span>
              {Math.abs(varNum) >= 0.01 && " → posts to 5070"}
            </p>
          )}
        </div>
        <div className="col-span-2">
          <label className="text-xs text-[#1a1814]/60 block mb-1">Notes (optional)</label>
          <input className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.notes} onChange={e => setForm(f => ({...f, notes: e.target.value}))} />
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={saving}
          className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium disabled:opacity-50">
          {saving ? "Posting…" : "Post Collection"}
        </button>
        <button type="button" onClick={onCancel} className="px-4 py-2 rounded-lg border text-sm">Cancel</button>
      </div>
    </form>
  )
}

export default function RSOCollectionsPage() {
  const [collections, setCollections] = useState<Collection[]>([])
  const [rsos, setRsos] = useState<RSOAgent[]>([])
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      apiFetch<{ items: Collection[] }>("/api/telecom/rso-collections"),
      apiFetch<{ items: RSOAgent[] }>("/api/telecom/rso-agents"),
    ])
      .then(([c, r]) => { setCollections(c.items); setRsos(r.items) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])
  const rsoName = (id: number) => rsos.find(r => r.id === id)?.name ?? `RSO #${id}`

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Banknote className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Daily Collections</h1>
            <p className="text-sm text-[#1a1814]/60">RSO daily bank deposits settling load and stock.</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium">
          <Plus className="w-4 h-4" /> Record Collection
        </button>
      </header>

      <HelpCallout title="Daily collection" tone="tip">
        RSO deposits a single bank amount covering <b>load consumed</b> and <b>SIM stock sold</b>.
        Any variance posts to account 5070 (Tracker Variance).
        GL: Dr Bank / Cr 1212 (load) / Cr 1120 (stock) ± 5070 (variance).
      </HelpCallout>

      {showForm && <AddCollectionForm rsos={rsos} onCreated={() => { setShowForm(false); load() }} onCancel={() => setShowForm(false)} />}
      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {loading ? <p className="text-sm text-[#1a1814]/50">Loading…</p> : (
        <div className="rounded-xl border border-[#b8943f]/20 bg-white overflow-hidden">
          {collections.length === 0 ? (
            <p className="text-sm text-[#1a1814]/40 p-8 text-center">No collections recorded yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[#1a1814]/40 uppercase tracking-wide border-b border-[#b8943f]/10">
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">RSO</th>
                  <th className="px-4 py-3 text-right">Load</th>
                  <th className="px-4 py-3 text-right">Stock</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3 text-right">Variance</th>
                </tr>
              </thead>
              <tbody>
                {collections.map(c => {
                  const v = parseFloat(c.variance)
                  return (
                    <tr key={c.id} className="border-b border-[#b8943f]/5 hover:bg-[#f6f3ee]">
                      <td className="px-4 py-2 font-mono text-xs">{c.collection_date}</td>
                      <td className="px-4 py-2">{rsoName(c.rso_id)}</td>
                      <td className="px-4 py-2 text-right font-mono">{fmt(c.load_portion)}</td>
                      <td className="px-4 py-2 text-right font-mono">{fmt(c.stock_portion)}</td>
                      <td className="px-4 py-2 text-right font-mono font-semibold">{fmt(c.total_deposited)}</td>
                      <td className={`px-4 py-2 text-right font-mono ${Math.abs(v) >= 0.01 ? "text-amber-700" : "text-[#1a1814]/30"}`}>
                        {Math.abs(v) < 0.01 ? "—" : (v > 0 ? "+" : "") + fmt(c.variance)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
