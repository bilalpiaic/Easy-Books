"use client"

import { useEffect, useState } from "react"
import { Users, Plus, UserCheck } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface RSOAgent {
  id: number
  name: string
  phone: string
  cnic: string
  territory: string | null
  load_outstanding: string
  is_active: boolean
}

function fmt(v: string | undefined) {
  if (!v) return "PKR 0"
  const n = parseFloat(v)
  return "PKR " + n.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

interface AddRSOFormProps { onCreated: () => void; onCancel: () => void }
function AddRSOForm({ onCreated, onCancel }: AddRSOFormProps) {
  const [form, setForm] = useState({ name: "", phone: "", cnic: "", territory: "" })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true); setErr(null)
    try {
      await apiFetch("/api/telecom/rso-agents", { method: "POST", body: JSON.stringify(form) })
      onCreated()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to create")
    } finally { setSaving(false) }
  }

  const F = (label: string, key: keyof typeof form, placeholder?: string) => (
    <div>
      <label className="text-xs text-[#1a1814]/60 block mb-1">{label}</label>
      <input required={key !== "territory"}
        className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
        placeholder={placeholder}
        value={form[key]} onChange={e => setForm(f => ({...f, [key]: e.target.value}))} />
    </div>
  )

  return (
    <form onSubmit={submit} className="bg-white border border-[#b8943f]/20 rounded-xl p-5 space-y-3">
      <h3 className="font-semibold text-[#1a1814]">Add RSO Agent</h3>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="grid grid-cols-2 gap-3">
        {F("Full Name", "name")}
        {F("Phone", "phone", "03XX-XXXXXXX")}
        {F("CNIC", "cnic", "XXXXX-XXXXXXX-X")}
        {F("Territory (optional)", "territory", "e.g. North Karachi")}
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={saving}
          className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium disabled:opacity-50">
          {saving ? "Saving…" : "Add RSO"}
        </button>
        <button type="button" onClick={onCancel}
          className="px-4 py-2 rounded-lg border text-sm">Cancel</button>
      </div>
    </form>
  )
}

export default function RSOAgentsPage() {
  const [agents, setAgents] = useState<RSOAgent[]>([])
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    apiFetch<{ items: RSOAgent[] }>("/api/telecom/rso-agents")
      .then(d => setAgents(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">RSO Agents</h1>
            <p className="text-sm text-[#1a1814]/60">Retail Sales Officers who distribute load and SIMs.</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium">
          <Plus className="w-4 h-4" /> Add RSO
        </button>
      </header>

      <HelpCallout title="RSO channel" tone="tip">
        Each RSO receives load from the MSR SIM and SIM card stock. They distribute both to tagged
        retail outlets and deposit cash daily to the franchisee bank account covering both settlements.
      </HelpCallout>

      {showForm && <AddRSOForm onCreated={() => { setShowForm(false); load() }} onCancel={() => setShowForm(false)} />}
      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {loading ? <p className="text-sm text-[#1a1814]/50">Loading…</p> : agents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#b8943f]/30 p-10 text-center">
          <UserCheck className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="font-medium text-[#1a1814]">No RSO agents yet</p>
          <p className="text-sm text-[#1a1814]/50 mt-1">Add your first RSO to start tracking the channel.</p>
        </div>
      ) : (
        <div className="rounded-xl border border-[#b8943f]/20 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#1a1814]/40 uppercase tracking-wide border-b border-[#b8943f]/10">
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Phone</th>
                <th className="px-4 py-3 text-left">Territory</th>
                <th className="px-4 py-3 text-right">Load Outstanding</th>
                <th className="px-4 py-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {agents.map(a => (
                <tr key={a.id} className="border-b border-[#b8943f]/5 hover:bg-[#f6f3ee]">
                  <td className="px-4 py-3 font-medium text-[#1a1814]">{a.name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{a.phone}</td>
                  <td className="px-4 py-3 text-[#1a1814]/60">{a.territory || "—"}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    <span className={parseFloat(a.load_outstanding) > 0 ? "text-amber-700 font-semibold" : ""}>
                      {fmt(a.load_outstanding)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${a.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                      {a.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
