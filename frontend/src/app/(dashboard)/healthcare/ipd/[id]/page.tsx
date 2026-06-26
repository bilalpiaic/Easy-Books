"use client"
import { useState, useEffect } from "react"
import { use } from "react"
import { ArrowLeft, Plus, LogOut } from "lucide-react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { StatusBadge } from "@/components/healthcare/primitives"
import { fmtDate } from "@/lib/utils"

type Admission = {
  id: number; admission_number: string; patient_id: number; ward_id: number; bed_id: number
  admission_date: string; discharge_date?: string; diagnosis?: string; admission_type: string
  status: string; deposit_amount: number
}
type Charge = { id: number; charge_date: string; charge_type: string; description: string; amount: number }
type LabOrder = { id: number; order_number: string; order_date: string; status: string }
type ProcedureOrder = { id: number; order_date: string; status: string; fee: number }

type Tab = "charges" | "lab" | "procedures"

export default function AdmissionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const today = new Date().toISOString().split("T")[0]
  const [admission, setAdmission] = useState<Admission | null>(null)
  const [charges, setCharges] = useState<Charge[]>([])
  const [labOrders, setLabOrders] = useState<LabOrder[]>([])
  const [procOrders, setProcOrders] = useState<ProcedureOrder[]>([])
  const [tab, setTab] = useState<Tab>("charges")
  const [loading, setLoading] = useState(true)
  const [showDischarge, setShowDischarge] = useState(false)
  const [showCharge, setShowCharge] = useState(false)
  const [chargeForm, setChargeForm] = useState({ charge_date: today, charge_type: "nursing", description: "", amount: "" })
  const [discharging, setDischarging] = useState(false)
  const [addingCharge, setAddingCharge] = useState(false)
  const [msg, setMsg] = useState("")

  async function load() {
    setLoading(true)
    const [adm, ch, lab, proc] = await Promise.all([
      apiFetch<Admission>(`/api/healthcare/admissions/${id}`).catch(() => null),
      apiFetch<Charge[] | { items: Charge[] }>(`/api/healthcare/admissions/${id}/charges`).catch(() => [] as Charge[]),
      apiFetch<LabOrder[] | { items: LabOrder[] }>(`/api/healthcare/lab/orders?admission_id=${id}`).catch(() => [] as LabOrder[]),
      apiFetch<ProcedureOrder[] | { items: ProcedureOrder[] }>(`/api/healthcare/procedure-orders?admission_id=${id}`).catch(() => [] as ProcedureOrder[]),
    ])
    setAdmission(adm)
    setCharges(Array.isArray(ch) ? ch : (ch as { items: Charge[] }).items ?? [])
    setLabOrders(Array.isArray(lab) ? lab : (lab as { items: LabOrder[] }).items ?? [])
    setProcOrders(Array.isArray(proc) ? proc : (proc as { items: ProcedureOrder[] }).items ?? [])
    setLoading(false)
  }

  useEffect(() => { load() }, [id])

  const chargeTotal = charges.reduce((sum, c) => sum + parseFloat(String(c.amount)), 0)

  async function addCharge(e: React.FormEvent) {
    e.preventDefault()
    setAddingCharge(true)
    try {
      await apiFetch(`/api/healthcare/admissions/${id}/charges`, {
        method: "POST",
        body: JSON.stringify({ ...chargeForm, amount: parseFloat(chargeForm.amount) || 0 }),
      })
      setShowCharge(false)
      setChargeForm({ charge_date: today, charge_type: "nursing", description: "", amount: "" })
      load()
    } catch {
      // silent
    } finally {
      setAddingCharge(false)
    }
  }

  async function discharge() {
    setDischarging(true)
    setMsg("")
    try {
      const result = await apiFetch<{ invoice_id: number; net_amount: number }>(`/api/healthcare/admissions/${id}/discharge`, { method: "POST" })
      setMsg(`Discharged. Invoice #${result.invoice_id}, net amount: ${result.net_amount.toLocaleString()}`)
      setShowDischarge(false)
      load()
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Discharge failed")
    } finally {
      setDischarging(false)
    }
  }

  if (loading) return <div className="p-6 text-neutral-400">Loading…</div>
  if (!admission) return <div className="p-6 text-neutral-400">Admission not found.</div>

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/healthcare/ipd" className="text-neutral-400 hover:text-neutral-700">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">{admission.admission_number}</h1>
          <p className="text-sm text-neutral-500 capitalize">{admission.admission_type} · {fmtDate(admission.admission_date)}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <StatusBadge status={admission.status} />
          {admission.status === "admitted" && (
            <button onClick={() => setShowDischarge(true)}
              className="flex items-center gap-1.5 bg-rose-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-rose-600">
              <LogOut className="w-4 h-4" /> Discharge
            </button>
          )}
        </div>
      </div>

      {msg && (
        <div className={`text-sm p-3 rounded-lg ${msg.includes("fail") || msg.includes("Failed") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {msg}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Total Charges", value: chargeTotal.toLocaleString() },
          { label: "Deposit Paid", value: parseFloat(String(admission.deposit_amount)).toLocaleString() },
          { label: "Net Payable", value: Math.max(0, chargeTotal - parseFloat(String(admission.deposit_amount))).toLocaleString() },
        ].map(card => (
          <div key={card.label} className="bg-white rounded-xl border border-neutral-200 p-4 text-center">
            <div className="text-xs text-neutral-500 mb-1">{card.label}</div>
            <div className="text-xl font-semibold text-neutral-800">{card.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-neutral-200 items-center justify-between">
        <div className="flex">
          {([
            ["charges", `Daily Charges (${charges.length})`],
            ["lab", `Lab Orders (${labOrders.length})`],
            ["procedures", `Procedures (${procOrders.length})`],
          ] as [Tab, string][]).map(([t, label]) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium ${tab === t ? "border-b-2 border-rose-500 text-rose-600" : "text-neutral-600 hover:text-neutral-800"}`}>
              {label}
            </button>
          ))}
        </div>
        {tab === "charges" && admission.status === "admitted" && (
          <button onClick={() => setShowCharge(true)}
            className="flex items-center gap-1 text-xs bg-white border border-neutral-200 text-neutral-700 px-2 py-1.5 rounded-lg hover:bg-neutral-50">
            <Plus className="w-3.5 h-3.5" /> Add Charge
          </button>
        )}
      </div>

      {tab === "charges" && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Type</th>
                <th className="text-left px-4 py-3">Description</th>
                <th className="text-right px-4 py-3">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {charges.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-6 text-center text-neutral-400">No charges yet</td></tr>
              ) : charges.map(c => (
                <tr key={c.id}>
                  <td className="px-4 py-3 whitespace-nowrap">{fmtDate(c.charge_date)}</td>
                  <td className="px-4 py-3 capitalize text-neutral-600">{c.charge_type}</td>
                  <td className="px-4 py-3 text-neutral-600">{c.description}</td>
                  <td className="px-4 py-3 text-right font-medium">{parseFloat(String(c.amount)).toLocaleString()}</td>
                </tr>
              ))}
              {charges.length > 0 && (
                <tr className="bg-neutral-50 font-medium">
                  <td colSpan={3} className="px-4 py-3 text-right text-neutral-700">Total</td>
                  <td className="px-4 py-3 text-right">{chargeTotal.toLocaleString()}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "lab" && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Order No.</th>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {labOrders.length === 0 ? (
                <tr><td colSpan={3} className="px-4 py-6 text-center text-neutral-400">No lab orders</td></tr>
              ) : labOrders.map(o => (
                <tr key={o.id}>
                  <td className="px-4 py-3 font-medium">{o.order_number}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{fmtDate(o.order_date)}</td>
                  <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "procedures" && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-right px-4 py-3">Fee</th>
                <th className="text-left px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {procOrders.length === 0 ? (
                <tr><td colSpan={3} className="px-4 py-6 text-center text-neutral-400">No procedures</td></tr>
              ) : procOrders.map(p => (
                <tr key={p.id}>
                  <td className="px-4 py-3 whitespace-nowrap">{fmtDate(p.order_date)}</td>
                  <td className="px-4 py-3 text-right">{parseFloat(String(p.fee)).toLocaleString()}</td>
                  <td className="px-4 py-3"><StatusBadge status={p.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Charge modal */}
      {showCharge && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">Add Charge</h2>
            <form onSubmit={addCharge} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Date</label>
                  <input type="date" value={chargeForm.charge_date}
                    onChange={e => setChargeForm(f => ({ ...f, charge_date: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Type</label>
                  <select value={chargeForm.charge_type}
                    onChange={e => setChargeForm(f => ({ ...f, charge_type: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                    <option value="bed">Bed/Ward</option>
                    <option value="nursing">Nursing</option>
                    <option value="procedure">Procedure</option>
                    <option value="lab">Lab</option>
                    <option value="pharmacy">Pharmacy</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Description</label>
                  <input value={chargeForm.description}
                    onChange={e => setChargeForm(f => ({ ...f, description: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Amount *</label>
                  <input required type="number" min="0" step="0.01" value={chargeForm.amount}
                    onChange={e => setChargeForm(f => ({ ...f, amount: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowCharge(false)}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-lg">Cancel</button>
                <button type="submit" disabled={addingCharge}
                  className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg disabled:opacity-50">
                  {addingCharge ? "Adding…" : "Add Charge"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Discharge confirm modal */}
      {showDischarge && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-2">Confirm Discharge</h2>
            <p className="text-sm text-neutral-600 mb-4">
              This will consolidate all {charges.length} charges (total: <strong>{chargeTotal.toLocaleString()}</strong>) into a single invoice, settle the deposit of <strong>{parseFloat(String(admission.deposit_amount)).toLocaleString()}</strong>, and free the bed.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowDischarge(false)}
                className="px-4 py-2 text-sm border border-neutral-200 rounded-lg">Cancel</button>
              <button onClick={discharge} disabled={discharging}
                className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg disabled:opacity-50">
                {discharging ? "Processing…" : "Confirm Discharge"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
