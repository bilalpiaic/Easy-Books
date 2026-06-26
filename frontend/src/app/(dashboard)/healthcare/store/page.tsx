"use client"
import { useState, useEffect } from "react"
import { Warehouse, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HcCard } from "@/components/healthcare/primitives"
import { fmtDate } from "@/lib/utils"

type StoreIssue = { id: number; issue_number: string; issue_date: string; purpose: string; from_location_id: number }
type Product = { id: number; name: string }
type Location = { id: number; name: string }
type PendingRx = { id: number; medicine_name: string; qty: number; dispensed_qty?: number }

type Tab = "issues" | "pending"

export default function HcStorePage() {
  const today = new Date().toISOString().split("T")[0]
  const [tab, setTab] = useState<Tab>("issues")
  const [issues, setIssues] = useState<StoreIssue[]>([])
  const [pending, setPending] = useState<PendingRx[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)
  const [form, setForm] = useState({
    issue_date: today, from_location_id: "", to_location_id: "", purpose: "ward",
    items: [] as Array<{ product_id: string; qty: string; charge_to_patient: boolean; charge_amount: string }>,
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const [iss, pend, locs, prods] = await Promise.all([
        apiFetch<StoreIssue[] | { items: StoreIssue[] }>("/api/healthcare/store/issues?limit=50").catch(() => [] as StoreIssue[]),
        apiFetch<PendingRx[]>("/api/healthcare/store/pharmacy/pending").catch(() => [] as PendingRx[]),
        apiFetch<Location[] | { items: Location[] }>("/api/stock-locations").catch(() => [] as Location[]),
        apiFetch<Product[] | { items: Product[] }>("/api/products?limit=200").catch(() => [] as Product[]),
      ])
      setIssues(Array.isArray(iss) ? iss : (iss as { items: StoreIssue[] }).items ?? [])
      setPending(Array.isArray(pend) ? pend : [])
      setLocations(Array.isArray(locs) ? locs : (locs as { items: Location[] }).items ?? [])
      setProducts(Array.isArray(prods) ? prods : (prods as { items: Product[] }).items ?? [])
      setLoading(false)
    }
    load()
  }, [])

  function addItem() {
    setForm(f => ({ ...f, items: [...f.items, { product_id: "", qty: "1", charge_to_patient: false, charge_amount: "0" }] }))
  }

  function removeItem(i: number) {
    setForm(f => ({ ...f, items: f.items.filter((_, idx) => idx !== i) }))
  }

  async function dispense(itemId: number, qty: number) {
    await apiFetch(`/api/healthcare/store/pharmacy/dispense?item_id=${itemId}&dispensed_qty=${qty}`, { method: "POST" }).catch(() => null)
    const pend = await apiFetch<PendingRx[]>("/api/healthcare/store/pharmacy/pending").catch(() => [] as PendingRx[])
    setPending(Array.isArray(pend) ? pend : [])
  }

  async function createIssue(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const body = {
        issue_date: form.issue_date,
        from_location_id: Number(form.from_location_id),
        to_location_id: form.to_location_id ? Number(form.to_location_id) : undefined,
        purpose: form.purpose,
        items: form.items.map(i => ({
          product_id: Number(i.product_id),
          qty: parseFloat(i.qty) || 1,
          charge_to_patient: i.charge_to_patient,
          charge_amount: parseFloat(i.charge_amount) || 0,
        })),
      }
      await apiFetch("/api/healthcare/store/issues", { method: "POST", body: JSON.stringify(body) })
      setShowNew(false)
      setForm({ issue_date: today, from_location_id: "", to_location_id: "", purpose: "ward", items: [] })
      const iss = await apiFetch<StoreIssue[] | { items: StoreIssue[] }>("/api/healthcare/store/issues?limit=50").catch(() => [] as StoreIssue[])
      setIssues(Array.isArray(iss) ? iss : (iss as { items: StoreIssue[] }).items ?? [])
    } catch {
      // silent
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Hospital Store</h1>
          <p className="text-sm text-neutral-500">Stock issues, pharmacy dispensing & transfers</p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="flex items-center gap-1.5 bg-rose-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-rose-600">
          <Plus className="w-4 h-4" /> Issue Stock
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-neutral-200">
        {(["issues", "pending"] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium ${tab === t ? "border-b-2 border-rose-500 text-rose-600" : "text-neutral-600 hover:text-neutral-800"}`}>
            {t === "pending" ? (
              <>Pending Dispense{pending.length > 0 && <span className="ml-1.5 bg-rose-500 text-white text-xs px-1.5 py-0.5 rounded-full">{pending.length}</span>}</>
            ) : "Stock Issues"}
          </button>
        ))}
      </div>

      {tab === "issues" && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Issue No.</th>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Purpose</th>
                <th className="text-left px-4 py-3">From Location</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {loading ? (
                <tr><td colSpan={4} className="px-4 py-6 text-center text-neutral-400">Loading…</td></tr>
              ) : issues.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-neutral-400">
                  <Warehouse className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  No stock issues recorded
                </td></tr>
              ) : issues.map(i => (
                <tr key={i.id} className="hover:bg-neutral-50">
                  <td className="px-4 py-3 font-medium">{i.issue_number}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{fmtDate(i.issue_date)}</td>
                  <td className="px-4 py-3 capitalize text-neutral-600">{i.purpose}</td>
                  <td className="px-4 py-3 text-neutral-600">
                    {locations.find(l => l.id === i.from_location_id)?.name ?? `#${i.from_location_id}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "pending" && (
        <HcCard title="Pending Prescription Dispenses">
          {pending.length === 0 ? (
            <p className="text-sm text-neutral-400 text-center py-4">No pending items to dispense</p>
          ) : (
            <div className="space-y-2">
              {pending.map(item => (
                <div key={item.id} className="flex items-center justify-between p-3 bg-neutral-50 rounded-lg">
                  <div>
                    <div className="text-sm font-medium">{item.medicine_name}</div>
                    <div className="text-xs text-neutral-500">Prescribed: {item.qty}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    {item.dispensed_qty != null ? (
                      <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded">Dispensed: {item.dispensed_qty}</span>
                    ) : (
                      <button onClick={() => dispense(item.id, item.qty)}
                        className="text-xs bg-rose-500 text-white px-3 py-1.5 rounded-lg hover:bg-rose-600">
                        Dispense {item.qty}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </HcCard>
      )}

      {/* Issue stock modal */}
      {showNew && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-4">Issue Stock</h2>
            <form onSubmit={createIssue} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Date</label>
                  <input type="date" value={form.issue_date} onChange={e => setForm(f => ({ ...f, issue_date: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Purpose</label>
                  <select value={form.purpose} onChange={e => setForm(f => ({ ...f, purpose: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                    <option value="ward">Ward</option>
                    <option value="pharmacy">Pharmacy</option>
                    <option value="lab">Lab</option>
                    <option value="procedure">Procedure</option>
                    <option value="transfer">Transfer</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">From *</label>
                  <select required value={form.from_location_id} onChange={e => setForm(f => ({ ...f, from_location_id: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">Select…</option>
                    {locations.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">To</label>
                  <select value={form.to_location_id} onChange={e => setForm(f => ({ ...f, to_location_id: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">Patient / Dept</option>
                    {locations.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                  </select>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-neutral-600">Items</label>
                  <button type="button" onClick={addItem} className="text-xs text-rose-600 hover:underline">+ Add Item</button>
                </div>
                {form.items.map((item, i) => (
                  <div key={i} className="grid grid-cols-12 gap-2 mb-2 items-center">
                    <div className="col-span-5">
                      <select value={item.product_id}
                        onChange={e => setForm(f => ({ ...f, items: f.items.map((it, idx) => idx === i ? { ...it, product_id: e.target.value } : it) }))}
                        className="w-full border border-neutral-200 rounded-lg px-2 py-1.5 text-xs">
                        <option value="">Product…</option>
                        {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </div>
                    <div className="col-span-2">
                      <input type="number" min="0.01" step="0.01" placeholder="Qty" value={item.qty}
                        onChange={e => setForm(f => ({ ...f, items: f.items.map((it, idx) => idx === i ? { ...it, qty: e.target.value } : it) }))}
                        className="w-full border border-neutral-200 rounded-lg px-2 py-1.5 text-xs" />
                    </div>
                    <div className="col-span-3">
                      <input type="number" min="0" step="0.01" placeholder="Charge" value={item.charge_amount}
                        onChange={e => setForm(f => ({ ...f, items: f.items.map((it, idx) => idx === i ? { ...it, charge_amount: e.target.value } : it) }))}
                        className="w-full border border-neutral-200 rounded-lg px-2 py-1.5 text-xs" />
                    </div>
                    <div className="col-span-1 text-center">
                      <input type="checkbox" title="Charge to patient" checked={item.charge_to_patient}
                        onChange={e => setForm(f => ({ ...f, items: f.items.map((it, idx) => idx === i ? { ...it, charge_to_patient: e.target.checked } : it) }))} />
                    </div>
                    <div className="col-span-1 text-center">
                      <button type="button" onClick={() => removeItem(i)} className="text-neutral-400 hover:text-red-500 text-lg leading-none">×</button>
                    </div>
                  </div>
                ))}
                {form.items.length === 0 && <p className="text-xs text-neutral-400">No items. Click + Add Item.</p>}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowNew(false)}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-lg">Cancel</button>
                <button type="submit" disabled={saving || form.items.length === 0}
                  className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg disabled:opacity-50">
                  {saving ? "Issuing…" : "Issue Stock"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
