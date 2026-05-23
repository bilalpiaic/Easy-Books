"use client"

import { useEffect, useState } from "react"
import { ArrowRightLeft, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface LoadTransfer {
  id: number
  transfer_date: string
  from_type: string
  from_ref_id: number | null
  to_type: string
  to_ref_id: number
  amount: string
  is_settled: boolean
}

interface RSOAgent { id: number; name: string }

function fmt(v: string) {
  return "PKR " + parseFloat(v).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

interface AddTransferFormProps { rsos: RSOAgent[]; onCreated: () => void; onCancel: () => void }
function AddTransferForm({ rsos, onCreated, onCancel }: AddTransferFormProps) {
  const [form, setForm] = useState({
    transfer_date: new Date().toISOString().split("T")[0],
    from_type: "msr", from_ref_id: "", to_type: "rso", to_ref_id: "", amount: "",
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setErr(null)
    try {
      const body = {
        transfer_date: form.transfer_date,
        from_type: form.from_type,
        from_ref_id: form.from_ref_id ? parseInt(form.from_ref_id) : null,
        to_type: form.to_type,
        to_ref_id: parseInt(form.to_ref_id),
        amount: parseFloat(form.amount),
      }
      await apiFetch("/api/telecom/load-transfers", { method: "POST", body: JSON.stringify(body) })
      onCreated()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally { setSaving(false) }
  }

  const fromIsRSO = form.from_type === "rso"

  return (
    <form onSubmit={submit} className="bg-white border border-[#b8943f]/20 rounded-xl p-5 space-y-3">
      <h3 className="font-semibold text-[#1a1814]">Record Load Transfer</h3>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Date</label>
          <input type="date" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.transfer_date} onChange={e => setForm(f => ({...f, transfer_date: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">From</label>
          <select className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.from_type} onChange={e => setForm(f => ({...f, from_type: e.target.value}))}>
            <option value="msr">MSR SIM (franchisee)</option>
            <option value="rso">RSO SIM</option>
          </select>
        </div>
        {fromIsRSO && (
          <div>
            <label className="text-xs text-[#1a1814]/60 block mb-1">From RSO</label>
            <select required className="w-full border rounded-lg px-3 py-2 text-sm"
              value={form.from_ref_id} onChange={e => setForm(f => ({...f, from_ref_id: e.target.value}))}>
              <option value="">Select RSO…</option>
              {rsos.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
        )}
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">To</label>
          <select className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.to_type} onChange={e => setForm(f => ({...f, to_type: e.target.value}))}>
            <option value="rso">RSO SIM</option>
            <option value="retail">Retail Outlet</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">To RSO</label>
          <select required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.to_ref_id} onChange={e => setForm(f => ({...f, to_ref_id: e.target.value}))}>
            <option value="">Select RSO…</option>
            {rsos.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </div>
        <div className={fromIsRSO ? "" : "col-span-2"}>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Amount (PKR face value)</label>
          <input type="number" min="0.01" step="0.01" required
            className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.amount} onChange={e => setForm(f => ({...f, amount: e.target.value}))} />
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={saving}
          className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium disabled:opacity-50">
          {saving ? "Posting…" : "Post Transfer"}
        </button>
        <button type="button" onClick={onCancel} className="px-4 py-2 rounded-lg border text-sm">Cancel</button>
      </div>
    </form>
  )
}

export default function LoadTransfersPage() {
  const [transfers, setTransfers] = useState<LoadTransfer[]>([])
  const [rsos, setRsos] = useState<RSOAgent[]>([])
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      apiFetch<{ items: LoadTransfer[] }>("/api/telecom/load-transfers"),
      apiFetch<{ items: RSOAgent[] }>("/api/telecom/rso-agents"),
    ])
      .then(([lt, rso]) => { setTransfers(lt.items); setRsos(rso.items) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const rsoName = (id: number | null) => rsos.find(r => r.id === id)?.name ?? `#${id}`

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ArrowRightLeft className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Load Transfers</h1>
            <p className="text-sm text-[#1a1814]/60">MSR → RSO → Retail load distribution chain.</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium">
          <Plus className="w-4 h-4" /> New Transfer
        </button>
      </header>

      <HelpCallout title="Load transfer chain" tone="tip">
        Load flows in two hops: <b>MSR SIM → RSO SIM</b> (Dr 1212 / Cr 1211), then
        <b> RSO SIM → Retail</b> (Dr 1213 / Cr 1212). Each hop creates a journal entry automatically.
        Transfers are settled when the RSO submits a daily collection.
      </HelpCallout>

      {showForm && <AddTransferForm rsos={rsos} onCreated={() => { setShowForm(false); load() }} onCancel={() => setShowForm(false)} />}
      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {loading ? <p className="text-sm text-[#1a1814]/50">Loading…</p> : (
        <div className="rounded-xl border border-[#b8943f]/20 bg-white overflow-hidden">
          {transfers.length === 0 ? (
            <p className="text-sm text-[#1a1814]/40 p-8 text-center">No load transfers yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[#1a1814]/40 uppercase tracking-wide border-b border-[#b8943f]/10">
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">From</th>
                  <th className="px-4 py-3 text-left">To</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3 text-center">Settled</th>
                </tr>
              </thead>
              <tbody>
                {transfers.map(t => (
                  <tr key={t.id} className="border-b border-[#b8943f]/5 hover:bg-[#f6f3ee]">
                    <td className="px-4 py-2 font-mono text-xs">{t.transfer_date}</td>
                    <td className="px-4 py-2">
                      {t.from_type === "msr" ? "MSR SIM" : rsoName(t.from_ref_id)}
                    </td>
                    <td className="px-4 py-2">
                      {t.to_type === "rso" ? rsoName(t.to_ref_id) : `Retail #${t.to_ref_id}`}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">{fmt(t.amount)}</td>
                    <td className="px-4 py-2 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${t.is_settled ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                        {t.is_settled ? "Settled" : "Pending"}
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
