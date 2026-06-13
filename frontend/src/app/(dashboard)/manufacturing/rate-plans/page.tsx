"use client"

import { useEffect, useState } from "react"
import { Tags, Printer, Plus } from "lucide-react"
import PrintHeader from "@/components/PrintHeader"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface RatePlan {
  id: number; code: string; name: string; version: number; is_active: boolean
  per_unit_rate: number; includes_materials_at_cost: boolean
  overhead_pct: number; margin_pct: number
}

interface FormState {
  code: string; name: string; per_unit_rate: string
  includes_materials_at_cost: boolean
  overhead_pct: string; margin_pct: string
  valid_from: string; valid_to: string; notes: string
}

const emptyForm = (): FormState => ({
  code: "", name: "", per_unit_rate: "",
  includes_materials_at_cost: true,
  overhead_pct: "0", margin_pct: "0",
  valid_from: "", valid_to: "", notes: "",
})

export default function RatePlansPage() {
  const fmt = useFmt()
  const [plans, setPlans]         = useState<RatePlan[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm]           = useState<FormState>(emptyForm)
  const [saving, setSaving]       = useState(false)
  const [formErr, setFormErr]     = useState<string | null>(null)

  const load = () => {
    apiFetch<{ items: RatePlan[] }>("/api/rate-plans")
      .then(d => setPlans(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const h = () => { setForm(emptyForm()); setFormErr(null); setModalOpen(true) }
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  }, [])

  const openAdd = () => { setForm(emptyForm()); setFormErr(null); setModalOpen(true) }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.code.trim())       { setFormErr("Code is required"); return }
    if (!form.name.trim())       { setFormErr("Name is required"); return }
    const rate = parseFloat(form.per_unit_rate)
    if (isNaN(rate) || rate < 0) { setFormErr("Per-unit rate must be a non-negative number"); return }
    setSaving(true); setFormErr(null)
    try {
      await apiFetch("/api/rate-plans", {
        method: "POST",
        body: JSON.stringify({
          code:                       form.code.trim().toUpperCase(),
          name:                       form.name.trim(),
          per_unit_rate:              rate,
          includes_materials_at_cost: form.includes_materials_at_cost,
          overhead_pct:               parseFloat(form.overhead_pct) || 0,
          margin_pct:                 parseFloat(form.margin_pct)   || 0,
          valid_from:                 form.valid_from  || undefined,
          valid_to:                   form.valid_to    || undefined,
          notes:                      form.notes.trim() || undefined,
        }),
      })
      setModalOpen(false)
      load()
    } catch (e: unknown) {
      setFormErr(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      <PrintHeader title="Rate Plans" orientation="landscape" />
      <header className="flex items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <Tags className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Rate Plans</h1>
            <p className="text-sm text-[#1a1814]/60">How you charge customers for your value-addition work.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-2 bg-[#b8943f] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#a07c32] transition-colors"
          >
            <Plus className="w-4 h-4" /> New Plan
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm hover:bg-[#f6f3ee] transition-colors"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
      </header>

      <HelpCallout title="Billing formula" tone="tip">
        <pre className="bg-white/50 rounded px-2 py-1 text-[11px] leading-relaxed">
{`base     = per_unit_rate × output_qty
           [+ own-stock material cost at WAvg if includes_materials_at_cost]
overhead = base × overhead_pct%
margin   = (base + overhead) × margin_pct%
total    = base + overhead + margin`}
        </pre>
      </HelpCallout>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-[#1a1814]/60">Loading…</p>
      ) : plans.length === 0 ? (
        <div className="bg-white border border-[#ede9e2] rounded-xl px-6 py-12 text-center">
          <Tags className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]">No rate plans yet</p>
          <p className="text-xs text-[#1a1814]/55 mt-1 mb-4">Create a plan to price your value-addition work.</p>
          <button onClick={openAdd} className="inline-flex items-center gap-2 bg-[#b8943f] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#a07c32] transition-colors">
            <Plus className="w-4 h-4" /> Create first plan
          </button>
        </div>
      ) : (
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#faf6ec] text-[#1a1814]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">Code</th>
                <th className="text-left px-4 py-2">Name</th>
                <th className="text-right px-4 py-2">Per unit</th>
                <th className="text-center px-4 py-2">Mat&apos;l</th>
                <th className="text-right px-4 py-2">Ovh %</th>
                <th className="text-right px-4 py-2">Margin %</th>
                <th className="text-center px-4 py-2">Ver.</th>
                <th className="text-center px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {plans.map(p => (
                <tr key={p.id} className="border-t border-[#ede9e2] hover:bg-[#faf8f4]">
                  <td className="px-4 py-2.5 font-mono text-xs">{p.code}</td>
                  <td className="px-4 py-2.5">{p.name}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmt(Number(p.per_unit_rate))}</td>
                  <td className="px-4 py-2.5 text-center text-xs">{p.includes_materials_at_cost ? "✓" : "—"}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{Number(p.overhead_pct).toFixed(1)}%</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{Number(p.margin_pct).toFixed(1)}%</td>
                  <td className="px-4 py-2.5 text-center text-xs text-[#1a1814]/60">v{p.version}</td>
                  <td className="px-4 py-2.5 text-center">
                    {p.is_active
                      ? <span className="text-emerald-700 text-xs font-semibold">Active</span>
                      : <span className="text-[#1a1814]/40 text-xs">Archived</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* New Rate Plan Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
            <div className="px-6 py-4 border-b border-[#ede9e2]">
              <h2 className="text-lg font-serif font-semibold text-[#1a1814]">New Rate Plan</h2>
            </div>
            <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Code</label>
                  <input value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                    placeholder="STITCH-STD" className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f] font-mono" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Per-unit Rate</label>
                  <input type="number" min="0" step="any" value={form.per_unit_rate}
                    onChange={e => setForm(f => ({ ...f, per_unit_rate: e.target.value }))}
                    placeholder="0.00" className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right tabular-nums focus:outline-none focus:border-[#b8943f]" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Name</label>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Standard Stitching Rate" className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Overhead %</label>
                  <input type="number" min="0" max="100" step="any" value={form.overhead_pct}
                    onChange={e => setForm(f => ({ ...f, overhead_pct: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right focus:outline-none focus:border-[#b8943f]" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Margin %</label>
                  <input type="number" min="0" max="100" step="any" value={form.margin_pct}
                    onChange={e => setForm(f => ({ ...f, margin_pct: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right focus:outline-none focus:border-[#b8943f]" />
                </div>
              </div>
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input type="checkbox" checked={form.includes_materials_at_cost}
                  onChange={e => setForm(f => ({ ...f, includes_materials_at_cost: e.target.checked }))}
                  className="w-4 h-4 accent-[#b8943f]" />
                <span className="text-sm text-[#1a1814]">Include own-stock material cost at WAvg in total</span>
              </label>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Valid From</label>
                  <input type="date" value={form.valid_from} onChange={e => setForm(f => ({ ...f, valid_from: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Valid To</label>
                  <input type="date" value={form.valid_to} onChange={e => setForm(f => ({ ...f, valid_to: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]" />
                </div>
              </div>
              {formErr && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{formErr}</p>}
              <div className="flex gap-3 pt-1">
                <button type="submit" disabled={saving}
                  className="flex-1 bg-[#b8943f] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[#a07c32] disabled:opacity-50 transition-colors">
                  {saving ? "Saving…" : "Create Rate Plan"}
                </button>
                <button type="button" onClick={() => setModalOpen(false)}
                  className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
