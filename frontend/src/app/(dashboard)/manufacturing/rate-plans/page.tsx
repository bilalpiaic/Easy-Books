"use client"

import { useEffect, useState } from "react"
import { Tags, Printer, Plus, Pencil, UserPlus, Download } from "lucide-react"
import PrintHeader from "@/components/PrintHeader"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { downloadCSV } from "@/lib/utils"
import { useTranslation } from "react-i18next"

interface RatePlan {
  id: number; code: string; name: string; version: number; is_active: boolean
  per_unit_rate: number; includes_materials_at_cost: boolean
  overhead_pct: number; margin_pct: number
  valid_from: string | null; valid_to: string | null; notes: string | null
}
interface Customer { id: number; name: string }

interface PlanForm {
  code: string; name: string; per_unit_rate: string
  includes_materials_at_cost: boolean
  overhead_pct: string; margin_pct: string
  valid_from: string; valid_to: string; notes: string
}

const emptyPlanForm = (): PlanForm => ({
  code: "", name: "", per_unit_rate: "",
  includes_materials_at_cost: true,
  overhead_pct: "0", margin_pct: "0",
  valid_from: "", valid_to: "", notes: "",
})

export default function RatePlansPage() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const [plans, setPlans]           = useState<RatePlan[]>([])
  const [customers, setCustomers]   = useState<Customer[]>([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)

  // Plan create/edit modal
  const [planModal, setPlanModal]   = useState(false)
  const [editingPlan, setEditingPlan] = useState<RatePlan | null>(null)
  const [planForm, setPlanForm]     = useState<PlanForm>(emptyPlanForm)
  const [planSaving, setPlanSaving] = useState(false)
  const [planErr, setPlanErr]       = useState<string | null>(null)

  // Assign modal
  const [assignModal, setAssignModal] = useState(false)
  const [assignPlan, setAssignPlan]   = useState<RatePlan | null>(null)
  const [assignCustomer, setAssignCustomer] = useState("")
  const [assignSaving, setAssignSaving]     = useState(false)
  const [assignErr, setAssignErr]           = useState<string | null>(null)
  const [assignOk, setAssignOk]             = useState<string | null>(null)

  const load = () =>
    Promise.all([
      apiFetch<{ items: RatePlan[] }>("/api/rate-plans"),
      apiFetch<{ items: Customer[] }>("/api/customers?limit=500"),
    ])
      .then(([p, c]) => { setPlans(p.items); setCustomers(c.items) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))

  useEffect(() => {
    load()
    const h = () => openCreate()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Plan modal helpers ───────────────────────────────────────────────────────

  const openCreate = () => {
    setEditingPlan(null)
    setPlanForm(emptyPlanForm())
    setPlanErr(null)
    setPlanModal(true)
  }

  const openEdit = (p: RatePlan) => {
    setEditingPlan(p)
    setPlanForm({
      code: p.code, name: p.name,
      per_unit_rate: String(p.per_unit_rate),
      includes_materials_at_cost: p.includes_materials_at_cost,
      overhead_pct: String(p.overhead_pct),
      margin_pct: String(p.margin_pct),
      valid_from: p.valid_from ?? "",
      valid_to: p.valid_to ?? "",
      notes: p.notes ?? "",
    })
    setPlanErr(null)
    setPlanModal(true)
  }

  const handlePlanSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!planForm.code.trim())       { setPlanErr("Code is required"); return }
    if (!planForm.name.trim())       { setPlanErr("Name is required"); return }
    const rate = parseFloat(planForm.per_unit_rate)
    if (isNaN(rate) || rate < 0)    { setPlanErr("Per-unit rate must be a non-negative number"); return }
    setPlanSaving(true); setPlanErr(null)
    try {
      const body = {
        name: planForm.name.trim(),
        per_unit_rate: rate,
        includes_materials_at_cost: planForm.includes_materials_at_cost,
        overhead_pct: parseFloat(planForm.overhead_pct) || 0,
        margin_pct:   parseFloat(planForm.margin_pct)   || 0,
        valid_from:   planForm.valid_from  || undefined,
        valid_to:     planForm.valid_to    || undefined,
        notes:        planForm.notes.trim() || undefined,
      }
      if (editingPlan) {
        await apiFetch(`/api/rate-plans/${editingPlan.id}`, { method: "PUT", body: JSON.stringify(body) })
      } else {
        await apiFetch("/api/rate-plans", {
          method: "POST",
          body: JSON.stringify({ code: planForm.code.trim().toUpperCase(), ...body }),
        })
      }
      setPlanModal(false)
      load()
    } catch (e: unknown) {
      setPlanErr(e instanceof Error ? e.message : "Save failed")
    } finally {
      setPlanSaving(false)
    }
  }

  // ── Assign modal helpers ─────────────────────────────────────────────────────

  const openAssign = (p: RatePlan) => {
    setAssignPlan(p)
    setAssignCustomer("")
    setAssignErr(null)
    setAssignOk(null)
    setAssignModal(true)
  }

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!assignCustomer) { setAssignErr("Select a customer"); return }
    if (!assignPlan) return
    setAssignSaving(true); setAssignErr(null); setAssignOk(null)
    try {
      await apiFetch("/api/rate-plans/assign", {
        method: "POST",
        body: JSON.stringify({ customer_id: parseInt(assignCustomer), rate_plan_id: assignPlan.id }),
      })
      const cust = customers.find(c => c.id === parseInt(assignCustomer))
      setAssignOk(`Assigned to ${cust?.name ?? "customer"}.`)
      setAssignCustomer("")
    } catch (e: unknown) {
      setAssignErr(e instanceof Error ? e.message : "Assignment failed")
    } finally {
      setAssignSaving(false)
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
            onClick={() => downloadCSV('rate-plans.csv', plans.map(p => ({ Code: p.code, Name: p.name, Version: p.version, Active: p.is_active ? 'Yes' : 'No', "Unit Rate": p.per_unit_rate, "Overhead %": p.overhead_pct, "Margin %": p.margin_pct, "Valid From": p.valid_from ?? '', "Valid To": p.valid_to ?? '' })))}
            disabled={plans.length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button onClick={openCreate}
            className="inline-flex items-center gap-2 bg-[#b8943f] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#a07c32] transition-colors">
            <Plus className="w-4 h-4" /> New Plan
          </button>
          <button onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm hover:bg-[#f6f3ee] transition-colors">
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
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
        <p className="mt-2 opacity-80 text-xs">
          Assign a plan to a customer so production orders auto-select it. Use the <UserPlus className="inline w-3 h-3" /> button.
        </p>
      </HelpCallout>

      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {loading ? (
        <p className="text-sm text-[#1a1814]/60">Loading…</p>
      ) : plans.length === 0 ? (
        <div className="bg-white border border-[#ede9e2] rounded-xl px-6 py-12 text-center">
          <Tags className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]">No rate plans yet</p>
          <p className="text-xs text-[#1a1814]/55 mt-1 mb-4">Create a plan to price your value-addition work.</p>
          <button onClick={openCreate}
            className="inline-flex items-center gap-2 bg-[#b8943f] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#a07c32] transition-colors">
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
                <th className="text-center px-4 py-2">{t('col.status', 'Status')}</th>
                <th className="px-4 py-2 print:hidden" />
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
                      ? <span className="text-emerald-700 text-xs font-semibold">{t('status.active', 'Active')}</span>
                      : <span className="text-[#1a1814]/40 text-xs">Archived</span>}
                  </td>
                  <td className="px-4 py-2.5 print:hidden">
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => openEdit(p)} title="Edit plan"
                        className="p-1.5 rounded border border-[#ede9e2] hover:bg-[#faf6ec] text-[#1a1814]/40 hover:text-[#b8943f] transition-colors">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      {p.is_active && (
                        <button onClick={() => openAssign(p)} title="Assign to customer"
                          className="p-1.5 rounded border border-[#ede9e2] hover:bg-[#faf6ec] text-[#1a1814]/40 hover:text-[#b8943f] transition-colors">
                          <UserPlus className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit Plan Modal */}
      {planModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
            <div className="px-6 py-4 border-b border-[#ede9e2]">
              <h2 className="text-lg font-serif font-semibold text-[#1a1814]">
                {editingPlan ? `Edit ${editingPlan.code}` : "New Rate Plan"}
              </h2>
            </div>
            <form onSubmit={handlePlanSave} className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Code</label>
                  <input value={planForm.code}
                    onChange={e => setPlanForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                    disabled={!!editingPlan}
                    placeholder="STITCH-STD"
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f] font-mono disabled:bg-[#f5f2ed]" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Per-unit Rate</label>
                  <input type="number" min="0" step="any" value={planForm.per_unit_rate}
                    onChange={e => setPlanForm(f => ({ ...f, per_unit_rate: e.target.value }))}
                    placeholder="0.00"
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right tabular-nums focus:outline-none focus:border-[#b8943f]" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Name</label>
                <input value={planForm.name} onChange={e => setPlanForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Standard Stitching Rate"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Overhead %</label>
                  <input type="number" min="0" max="100" step="any" value={planForm.overhead_pct}
                    onChange={e => setPlanForm(f => ({ ...f, overhead_pct: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right focus:outline-none focus:border-[#b8943f]" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Margin %</label>
                  <input type="number" min="0" max="100" step="any" value={planForm.margin_pct}
                    onChange={e => setPlanForm(f => ({ ...f, margin_pct: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right focus:outline-none focus:border-[#b8943f]" />
                </div>
              </div>
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input type="checkbox" checked={planForm.includes_materials_at_cost}
                  onChange={e => setPlanForm(f => ({ ...f, includes_materials_at_cost: e.target.checked }))}
                  className="w-4 h-4 accent-[#b8943f]" />
                <span className="text-sm text-[#1a1814]">Include own-stock material cost at WAvg in total</span>
              </label>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Valid From</label>
                  <input type="date" value={planForm.valid_from}
                    onChange={e => setPlanForm(f => ({ ...f, valid_from: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Valid To</label>
                  <input type="date" value={planForm.valid_to}
                    onChange={e => setPlanForm(f => ({ ...f, valid_to: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]" />
                </div>
              </div>
              {planErr && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{planErr}</p>}
              <div className="flex gap-3 pt-1">
                <button type="submit" disabled={planSaving}
                  className="flex-1 bg-[#b8943f] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[#a07c32] disabled:opacity-50 transition-colors">
                  {planSaving ? "Saving…" : editingPlan ? "Save Changes" : "Create Rate Plan"}
                </button>
                <button type="button" onClick={() => setPlanModal(false)}
                  className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors">{t('common.cancel', 'Cancel')}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assign to Customer Modal */}
      {assignModal && assignPlan && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
            <div className="px-6 py-4 border-b border-[#ede9e2]">
              <h2 className="text-lg font-serif font-semibold text-[#1a1814]">Assign {assignPlan.code}</h2>
              <p className="text-xs text-[#1a1814]/60 mt-0.5">
                Link this plan to a customer so production orders auto-select it.
                Any prior active assignment for the customer will be replaced.
              </p>
            </div>
            <form onSubmit={handleAssign} className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">{t('col.customer', 'Customer')}</label>
                <select value={assignCustomer} onChange={e => setAssignCustomer(e.target.value)}
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]">
                  <option value="">— Select customer —</option>
                  {customers.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              {assignErr && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{assignErr}</p>}
              {assignOk  && <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">{assignOk}</p>}
              <div className="flex gap-3 pt-1">
                <button type="submit" disabled={assignSaving}
                  className="flex-1 bg-[#1a1814] text-white py-2.5 rounded-lg text-sm font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                  {assignSaving ? "Assigning…" : "Assign"}
                </button>
                <button type="button" onClick={() => setAssignModal(false)}
                  className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors">
                  Close
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
