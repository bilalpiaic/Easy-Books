"use client"
import { useState, useEffect } from "react"
import { FlaskConical, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { StatusBadge } from "@/components/healthcare/primitives"
import { fmtDate } from "@/lib/utils"

type LabOrder = { id: number; order_number: string; order_date: string; source: string; status: string; patient_id: number }
type LabTest = { id: number; code: string; name: string; standard_fee: number; category: string }
type Patient = { id: number; mr_number: string; name: string }

export default function LabPage() {
  const today = new Date().toISOString().split("T")[0]
  const [orders, setOrders] = useState<LabOrder[]>([])
  const [tests, setTests] = useState<LabTest[]>([])
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ status: "" })
  const [showNew, setShowNew] = useState(false)
  const [form, setForm] = useState({ patient_id: "", order_date: today, source: "walkin", test_ids: [] as number[] })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState("")

  async function loadOrders() {
    setLoading(true)
    try {
      const qs = new URLSearchParams(filter.status ? { status: filter.status } : {})
      const json = await apiFetch<LabOrder[] | { items: LabOrder[] }>(`/api/healthcare/lab/orders?${qs}&limit=50`)
      setOrders(Array.isArray(json) ? json : json.items ?? [])
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOrders()
    apiFetch<LabTest[]>("/api/healthcare/lab/tests").then(d => setTests(d ?? [])).catch(() => setTests([]))
    apiFetch<Patient[] | { items: Patient[] }>("/api/healthcare/patients?limit=200")
      .then(d => setPatients(Array.isArray(d) ? d : d.items ?? []))
      .catch(() => setPatients([]))
  }, [])

  function toggleTest(id: number) {
    setForm(f => ({
      ...f,
      test_ids: f.test_ids.includes(id) ? f.test_ids.filter(t => t !== id) : [...f.test_ids, id],
    }))
  }

  async function createOrder(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setMsg("")
    try {
      const body = { patient_id: Number(form.patient_id), order_date: form.order_date, source: form.source, test_ids: form.test_ids }
      const order = await apiFetch<{ id: number }>("/api/healthcare/lab/orders", { method: "POST", body: JSON.stringify(body) })
      if (form.source === "walkin") {
        await apiFetch(`/api/healthcare/lab/orders/${order.id}/bill`, { method: "POST" }).catch(() => null)
      }
      setShowNew(false)
      setForm({ patient_id: "", order_date: today, source: "walkin", test_ids: [] })
      setMsg("Lab order created")
      loadOrders()
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Failed to create order")
    } finally {
      setSaving(false)
    }
  }

  async function updateStatus(orderId: number, action: "collect" | "deliver") {
    if (action === "collect") {
      await apiFetch(`/api/healthcare/lab/orders/${orderId}/collect`, {
        method: "POST", body: JSON.stringify({ collection_point: "lab", specimen_type: "blood" }),
      }).catch(() => null)
    } else {
      await apiFetch(`/api/healthcare/lab/orders/${orderId}/deliver`, { method: "PUT" }).catch(() => null)
    }
    loadOrders()
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Laboratory</h1>
          <p className="text-sm text-neutral-500">Lab orders, sample collection & results</p>
        </div>
        <div className="flex gap-2">
          <a href="/healthcare/lab/tests"
            className="px-3 py-2 text-sm border border-neutral-200 rounded-lg hover:bg-neutral-50">
            Test Catalogue
          </a>
          <button onClick={() => setShowNew(true)}
            className="flex items-center gap-1.5 bg-rose-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-rose-600">
            <Plus className="w-4 h-4" /> New Order
          </button>
        </div>
      </div>

      {msg && <div className="text-sm p-3 rounded-lg bg-green-50 text-green-700">{msg}</div>}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {["", "ordered", "sample_collected", "processing", "resulted", "delivered"].map(s => (
          <button key={s} onClick={() => { setFilter(f => ({ ...f, status: s })); loadOrders() }}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium border ${
              filter.status === s ? "bg-rose-500 text-white border-rose-500" : "bg-white border-neutral-200 text-neutral-600 hover:border-rose-300"
            }`}>
            {s || "All"}
          </button>
        ))}
      </div>

      {/* Orders table */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
            <tr>
              <th className="text-left px-4 py-3">Order No.</th>
              <th className="text-left px-4 py-3">Date</th>
              <th className="text-left px-4 py-3">Source</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-400">Loading…</td></tr>
            ) : orders.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-neutral-400">
                <FlaskConical className="w-8 h-8 mx-auto mb-2 opacity-30" />
                No lab orders
              </td></tr>
            ) : orders.map(o => (
              <tr key={o.id} className="hover:bg-neutral-50">
                <td className="px-4 py-3 font-medium">{o.order_number}</td>
                <td className="px-4 py-3 whitespace-nowrap">{fmtDate(o.order_date)}</td>
                <td className="px-4 py-3 capitalize text-neutral-600">{o.source.replace("_", " ")}</td>
                <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5">
                    {o.status === "ordered" && (
                      <button onClick={() => updateStatus(o.id, "collect")}
                        className="text-xs bg-orange-50 text-orange-700 px-2 py-0.5 rounded hover:bg-orange-100">
                        Collect
                      </button>
                    )}
                    {o.status === "resulted" && (
                      <button onClick={() => updateStatus(o.id, "deliver")}
                        className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded hover:bg-green-100">
                        Deliver
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* New order modal */}
      {showNew && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-4">New Lab Order</h2>
            <form onSubmit={createOrder} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">Patient *</label>
                <select required value={form.patient_id}
                  onChange={e => setForm(f => ({ ...f, patient_id: e.target.value }))}
                  className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">Select patient…</option>
                  {patients.map(p => <option key={p.id} value={p.id}>{p.name} ({p.mr_number})</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Order Date</label>
                  <input type="date" value={form.order_date}
                    onChange={e => setForm(f => ({ ...f, order_date: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Source</label>
                  <select value={form.source} onChange={e => setForm(f => ({ ...f, source: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                    <option value="walkin">Walk-in</option>
                    <option value="opd">OPD Referral</option>
                    <option value="ipd">IPD</option>
                    <option value="collection_centre">Collection Centre</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-2">Tests</label>
                <div className="grid grid-cols-2 gap-2 max-h-52 overflow-y-auto">
                  {tests.map(t => (
                    <label key={t.id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-neutral-50 p-1.5 rounded">
                      <input type="checkbox" checked={form.test_ids.includes(t.id)} onChange={() => toggleTest(t.id)} />
                      <span className="flex-1">{t.name}</span>
                      <span className="text-xs text-neutral-400">{parseFloat(String(t.standard_fee)).toLocaleString()}</span>
                    </label>
                  ))}
                </div>
                {form.test_ids.length > 0 && (
                  <p className="text-xs text-neutral-500 mt-1">{form.test_ids.length} test(s) selected</p>
                )}
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowNew(false)}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-lg">Cancel</button>
                <button type="submit" disabled={saving || form.test_ids.length === 0}
                  className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg disabled:opacity-50">
                  {saving ? "Creating…" : "Create Order"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
