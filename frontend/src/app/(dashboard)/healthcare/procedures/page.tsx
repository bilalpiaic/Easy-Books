"use client"
import { useState, useEffect } from "react"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { StatusBadge } from "@/components/healthcare/primitives"
import { fmtDate } from "@/lib/utils"

type Procedure = { id: number; code: string; name: string; category: string; standard_fee: number; is_active: boolean }
type ProcedureOrder = { id: number; order_date: string; status: string; fee: number; procedure_id: number; patient_id: number }
type Patient = { id: number; mr_number: string; name: string }
type Doctor = { id: number; name: string }

export default function ProceduresPage() {
  const today = new Date().toISOString().split("T")[0]
  const [procs, setProcs] = useState<Procedure[]>([])
  const [orders, setOrders] = useState<ProcedureOrder[]>([])
  const [patients, setPatients] = useState<Patient[]>([])
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [showNewProc, setShowNewProc] = useState(false)
  const [showNewOrder, setShowNewOrder] = useState(false)
  const [procForm, setProcForm] = useState({ code: "", name: "", category: "minor", standard_fee: "" })
  const [orderForm, setOrderForm] = useState({ patient_id: "", doctor_id: "", procedure_id: "", order_date: today })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState("")

  async function load() {
    const [p, o, pts, docs] = await Promise.all([
      apiFetch<Procedure[]>("/api/healthcare/procedures/catalog").catch(() => [] as Procedure[]),
      apiFetch<ProcedureOrder[] | { items: ProcedureOrder[] }>("/api/healthcare/procedure-orders?limit=20").catch(() => [] as ProcedureOrder[]),
      apiFetch<Patient[] | { items: Patient[] }>("/api/healthcare/patients?limit=200").catch(() => [] as Patient[]),
      apiFetch<Doctor[]>("/api/healthcare/doctors").catch(() => [] as Doctor[]),
    ])
    setProcs(p ?? [])
    setOrders(Array.isArray(o) ? o : (o as { items: ProcedureOrder[] }).items ?? [])
    setPatients(Array.isArray(pts) ? pts : (pts as { items: Patient[] }).items ?? [])
    setDoctors(docs ?? [])
  }

  useEffect(() => { load() }, [])

  async function createProc(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await apiFetch("/api/healthcare/procedures/catalog", {
        method: "POST", body: JSON.stringify({ ...procForm, standard_fee: parseFloat(procForm.standard_fee) || 0 })
      })
      setShowNewProc(false)
      setProcForm({ code: "", name: "", category: "minor", standard_fee: "" })
      load()
    } catch {
      // silent
    } finally {
      setSaving(false)
    }
  }

  async function createOrder(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setMsg("")
    try {
      const body = {
        patient_id: Number(orderForm.patient_id),
        procedure_id: Number(orderForm.procedure_id),
        order_date: orderForm.order_date,
        doctor_id: orderForm.doctor_id ? Number(orderForm.doctor_id) : undefined,
      }
      await apiFetch("/api/healthcare/procedure-orders", { method: "POST", body: JSON.stringify(body) })
      setShowNewOrder(false)
      setOrderForm({ patient_id: "", doctor_id: "", procedure_id: "", order_date: today })
      setMsg("Procedure ordered and billed")
      load()
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Failed")
    } finally {
      setSaving(false)
    }
  }

  async function markPerformed(id: number) {
    await apiFetch(`/api/healthcare/procedure-orders/${id}/perform`, { method: "PUT" }).catch(() => null)
    load()
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Procedures</h1>
          <p className="text-sm text-neutral-500">Procedure catalogue & orders</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowNewProc(true)}
            className="px-3 py-2 text-sm border border-neutral-200 rounded-lg hover:bg-neutral-50">
            + Add Procedure
          </button>
          <button onClick={() => setShowNewOrder(true)}
            className="flex items-center gap-1.5 bg-rose-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-rose-600">
            <Plus className="w-4 h-4" /> New Order
          </button>
        </div>
      </div>

      {msg && <div className="text-sm p-3 rounded-lg bg-green-50 text-green-700">{msg}</div>}

      {/* Catalogue */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-100 font-medium text-sm">Procedure Catalogue</div>
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
            <tr>
              <th className="text-left px-4 py-2">Code</th>
              <th className="text-left px-4 py-2">Procedure</th>
              <th className="text-left px-4 py-2">Category</th>
              <th className="text-right px-4 py-2">Fee</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {procs.map(p => (
              <tr key={p.id} className={`hover:bg-neutral-50 ${!p.is_active ? "opacity-50" : ""}`}>
                <td className="px-4 py-2.5 font-mono text-xs text-neutral-500">{p.code}</td>
                <td className="px-4 py-2.5 font-medium">{p.name}</td>
                <td className="px-4 py-2.5 capitalize text-neutral-500">{p.category}</td>
                <td className="px-4 py-2.5 text-right">{parseFloat(String(p.standard_fee)).toLocaleString()}</td>
                <td className="px-4 py-2.5 text-right">
                  <button onClick={() => { setOrderForm(f => ({ ...f, procedure_id: String(p.id) })); setShowNewOrder(true) }}
                    className="text-xs text-rose-600 hover:underline">Order</button>
                </td>
              </tr>
            ))}
            {procs.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-400">No procedures in catalogue</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Recent orders */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-100 font-medium text-sm">Recent Procedure Orders</div>
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
            <tr>
              <th className="text-left px-4 py-2">Date</th>
              <th className="text-right px-4 py-2">Fee</th>
              <th className="text-left px-4 py-2">Status</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {orders.map(o => (
              <tr key={o.id}>
                <td className="px-4 py-2.5 whitespace-nowrap">{fmtDate(o.order_date)}</td>
                <td className="px-4 py-2.5 text-right">{parseFloat(String(o.fee)).toLocaleString()}</td>
                <td className="px-4 py-2.5"><StatusBadge status={o.status} /></td>
                <td className="px-4 py-2.5">
                  {o.status === "ordered" && (
                    <button onClick={() => markPerformed(o.id)}
                      className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded hover:bg-green-100">
                      Mark Performed
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-neutral-400">No recent orders</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showNewProc && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">Add Procedure</h2>
            <form onSubmit={createProc} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Code *</label>
                  <input required value={procForm.code} onChange={e => setProcForm(f => ({ ...f, code: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Category</label>
                  <select value={procForm.category} onChange={e => setProcForm(f => ({ ...f, category: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                    <option value="minor">Minor</option>
                    <option value="surgery">Surgery</option>
                    <option value="diagnostic">Diagnostic</option>
                    <option value="therapy">Therapy</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Name *</label>
                  <input required value={procForm.name} onChange={e => setProcForm(f => ({ ...f, name: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Fee</label>
                  <input type="number" min="0" value={procForm.standard_fee}
                    onChange={e => setProcForm(f => ({ ...f, standard_fee: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowNewProc(false)}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-lg">Cancel</button>
                <button type="submit" disabled={saving}
                  className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg disabled:opacity-50">
                  {saving ? "Saving…" : "Add"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showNewOrder && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">Order Procedure</h2>
            <form onSubmit={createOrder} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">Procedure *</label>
                <select required value={orderForm.procedure_id}
                  onChange={e => setOrderForm(f => ({ ...f, procedure_id: e.target.value }))}
                  className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">Select procedure…</option>
                  {procs.map(p => <option key={p.id} value={p.id}>{p.name} — {parseFloat(String(p.standard_fee)).toLocaleString()}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">Patient *</label>
                <select required value={orderForm.patient_id}
                  onChange={e => setOrderForm(f => ({ ...f, patient_id: e.target.value }))}
                  className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">Select patient…</option>
                  {patients.map(p => <option key={p.id} value={p.id}>{p.name} ({p.mr_number})</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Doctor</label>
                  <select value={orderForm.doctor_id}
                    onChange={e => setOrderForm(f => ({ ...f, doctor_id: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">— Optional —</option>
                    {doctors.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Date</label>
                  <input type="date" value={orderForm.order_date}
                    onChange={e => setOrderForm(f => ({ ...f, order_date: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowNewOrder(false)}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-lg">Cancel</button>
                <button type="submit" disabled={saving}
                  className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg disabled:opacity-50">
                  {saving ? "Ordering…" : "Order & Bill"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
