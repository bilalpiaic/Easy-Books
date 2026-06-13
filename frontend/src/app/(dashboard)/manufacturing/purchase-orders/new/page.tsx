"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ShoppingCart, Plus, Trash2, Save, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"

interface Vendor { id: number; name: string }
interface Product { id: number; name: string; code: string; default_rate: string }

interface POLine {
  product_id: string
  description: string
  qty: string
  unit: string
  rate: string
}

const emptyLine = (): POLine => ({ product_id: "", description: "", qty: "1", unit: "", rate: "" })

export default function NewPurchaseOrderPage() {
  const router = useRouter()
  const fmt = useFmt()

  const [vendors, setVendors] = useState<Vendor[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [vendorId, setVendorId] = useState("")
  const [vendorName, setVendorName] = useState("")
  const [orderDate, setOrderDate] = useState(new Date().toISOString().split("T")[0])
  const [expectedDate, setExpectedDate] = useState("")
  const [description, setDescription] = useState("")
  const [notes, setNotes] = useState("")
  const [lines, setLines] = useState<POLine[]>([emptyLine()])
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    apiFetch<{ items: Vendor[] }>("/api/vendors?limit=500").then(d => setVendors(d.items)).catch(() => {})
    apiFetch<{ items: Product[] }>("/api/products?limit=500").then(d => setProducts(d.items)).catch(() => {})
  }, [])

  const updateLine = (i: number, field: keyof POLine, value: string) => {
    setLines(prev => {
      const next = prev.map((l, idx) => idx !== i ? l : { ...l, [field]: value })
      // auto-fill rate when a product is selected
      if (field === "product_id" && value) {
        const prod = products.find(p => String(p.id) === value)
        if (prod) {
          next[i].description = prod.name
          next[i].rate = prod.default_rate
        }
      }
      return next
    })
  }

  const total = lines.reduce((s, l) => s + (parseFloat(l.qty) || 0) * (parseFloat(l.rate) || 0), 0)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const validLines = lines.filter(l => l.description.trim() && parseFloat(l.qty) > 0)
    if (!validLines.length) { setError("At least one line with a description and quantity is required."); return }

    setSaving(true); setError("")
    try {
      const po = await apiFetch<{ id: number }>("/api/purchase-orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vendor_id: vendorId ? parseInt(vendorId) : null,
          vendor_name: vendorId ? null : (vendorName || null),
          order_date: orderDate,
          expected_date: expectedDate || null,
          description: description || null,
          notes: notes || null,
          lines: validLines.map(l => ({
            product_id: l.product_id ? parseInt(l.product_id) : null,
            description: l.description,
            qty: parseFloat(l.qty),
            unit: l.unit || null,
            rate: parseFloat(l.rate) || 0,
          })),
        }),
      })
      router.push(`/manufacturing/purchase-orders/${po.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed")
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl">
      <header className="flex items-center gap-3">
        <ShoppingCart className="w-7 h-7 text-[#b8943f]" />
        <div>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">New Purchase Order</h1>
          <p className="text-sm text-[#1a1814]/60">Order goods from a vendor before they arrive.</p>
        </div>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2.5 rounded-lg flex items-start gap-2 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Header fields */}
      <section className="bg-white border border-[#ede9e2] rounded-2xl p-5 space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[#1a1814]/50">Order Details</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-black/85 mb-1.5">Vendor</label>
            <select
              value={vendorId}
              onChange={e => { setVendorId(e.target.value); setVendorName("") }}
              className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
            >
              <option value="">— Select vendor or enter name below —</option>
              {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
            {!vendorId && (
              <input
                type="text"
                placeholder="Or type vendor name"
                value={vendorName}
                onChange={e => setVendorName(e.target.value)}
                className="mt-2 w-full px-3 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
              />
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-1.5">Order Date <span className="text-red-500">*</span></label>
              <input
                type="date"
                required
                value={orderDate}
                onChange={e => setOrderDate(e.target.value)}
                className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-1.5">Expected Delivery</label>
              <input
                type="date"
                value={expectedDate}
                onChange={e => setExpectedDate(e.target.value)}
                className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
              />
            </div>
          </div>
        </div>

        <div>
          <label className="block text-sm font-semibold text-black/85 mb-1.5">Description</label>
          <input
            type="text"
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="What is this order for?"
            className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
          />
        </div>
      </section>

      {/* Line items */}
      <section className="bg-white border border-[#ede9e2] rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[#1a1814]/50">Items</h2>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">
                <th className="text-left pb-2 pr-2 min-w-[160px]">Product</th>
                <th className="text-left pb-2 pr-2 min-w-[200px]">Description <span className="text-red-500">*</span></th>
                <th className="text-right pb-2 pr-2 w-20">Qty</th>
                <th className="text-left pb-2 pr-2 w-20">Unit</th>
                <th className="text-right pb-2 pr-2 w-28">Rate</th>
                <th className="text-right pb-2 w-28">Amount</th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {lines.map((line, idx) => (
                <tr key={idx}>
                  <td className="py-1.5 pr-2">
                    <select
                      value={line.product_id}
                      onChange={e => updateLine(idx, "product_id", e.target.value)}
                      className="w-full px-2 py-1.5 border border-[#ede9e2] rounded-md text-xs focus:ring-2 focus:ring-[#b8943f] outline-none"
                    >
                      <option value="">— optional —</option>
                      {products.map(p => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}
                    </select>
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      required
                      type="text"
                      value={line.description}
                      onChange={e => updateLine(idx, "description", e.target.value)}
                      className="w-full px-2 py-1.5 border border-[#ede9e2] rounded-md text-xs focus:ring-2 focus:ring-[#b8943f] outline-none"
                    />
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={line.qty}
                      onChange={e => updateLine(idx, "qty", e.target.value)}
                      className="w-full px-2 py-1.5 border border-[#ede9e2] rounded-md text-xs text-right font-mono focus:ring-2 focus:ring-[#b8943f] outline-none"
                    />
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      type="text"
                      value={line.unit}
                      onChange={e => updateLine(idx, "unit", e.target.value)}
                      placeholder="pcs"
                      className="w-full px-2 py-1.5 border border-[#ede9e2] rounded-md text-xs focus:ring-2 focus:ring-[#b8943f] outline-none"
                    />
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={line.rate}
                      onChange={e => updateLine(idx, "rate", e.target.value)}
                      className="w-full px-2 py-1.5 border border-[#ede9e2] rounded-md text-xs text-right font-mono focus:ring-2 focus:ring-[#b8943f] outline-none"
                    />
                  </td>
                  <td className="py-1.5 pr-2 text-right font-mono text-xs text-[#1a1814]/70">
                    {fmt((parseFloat(line.qty) || 0) * (parseFloat(line.rate) || 0))}
                  </td>
                  <td className="py-1.5">
                    <button
                      type="button"
                      onClick={() => setLines(l => l.filter((_, i) => i !== idx))}
                      disabled={lines.length === 1}
                      className="p-1.5 text-red-400 hover:text-red-600 disabled:opacity-30 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-[#ede9e2]">
          <button
            type="button"
            onClick={() => setLines(l => [...l, emptyLine()])}
            className="flex items-center gap-1.5 text-sm font-semibold text-[#b8943f] hover:text-[#1a1814] transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add line
          </button>
          <div className="text-sm font-bold text-[#1a1814] font-mono">
            Total: {fmt(total)}
          </div>
        </div>
      </section>

      {/* Notes */}
      <section className="bg-white border border-[#ede9e2] rounded-2xl p-5">
        <label className="block text-sm font-semibold text-black/85 mb-1.5">Notes (internal)</label>
        <textarea
          value={notes}
          onChange={e => setNotes(e.target.value)}
          rows={2}
          placeholder="Payment terms, delivery instructions…"
          className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-sm resize-none"
        />
      </section>

      {/* Actions */}
      <div className="flex gap-3 justify-end">
        <button
          type="button"
          onClick={() => router.back()}
          className="px-5 py-2.5 bg-white border border-[#ede9e2] rounded-lg font-semibold hover:bg-[#f6f3ee] transition-colors text-sm"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving}
          className="px-5 py-2.5 bg-[#1a1814] text-white rounded-lg font-semibold flex items-center gap-2 hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50 text-sm"
        >
          <Save className="w-4 h-4" />
          {saving ? "Saving…" : "Save PO"}
        </button>
      </div>
    </form>
  )
}
