"use client"

import { useEffect, useState } from "react"
import { Plus, Trash2, Pencil, Tags, Check, X, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface PromoRule {
  id: number
  name: string
  description: string | null
  is_active: boolean
  start_date: string | null
  end_date: string | null
  product_id: number | null
  category_id: number | null
  min_qty: number | null
  min_invoice_value: number | null
  discount_type: string
  discount_value: number | null
  giveaway_product_id: number | null
  giveaway_qty: number | null
}

interface Product { id: number; name: string; code?: string }
interface Category { id: number; name: string; parent_id: number | null }

const EMPTY: Omit<PromoRule, "id"> = {
  name: "",
  description: null,
  is_active: true,
  start_date: null,
  end_date: null,
  product_id: null,
  category_id: null,
  min_qty: null,
  min_invoice_value: null,
  discount_type: "percent",
  discount_value: null,
  giveaway_product_id: null,
  giveaway_qty: null,
}

export default function PromoDiscountsPage() {
  const [rules, setRules] = useState<PromoRule[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<PromoRule | null>(null)
  const [form, setForm] = useState<Omit<PromoRule, "id">>(EMPTY)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  async function load() {
    const [r, p, c] = await Promise.all([
      apiFetch<PromoRule[]>("/api/promo-rules"),
      apiFetch<{ items: Product[] }>("/api/products?limit=500"),
      apiFetch<Category[]>("/api/product-categories"),
    ])
    setRules(r)
    setProducts(p.items)
    setCategories(c)
  }

  useEffect(() => { load().catch(console.error) }, [])

  function openNew() {
    setEditing(null)
    setForm(EMPTY)
    setShowForm(true)
    setError("")
  }

  function openEdit(rule: PromoRule) {
    setEditing(rule)
    const { id, ...rest } = rule
    setForm(rest)
    setShowForm(true)
    setError("")
  }

  function set<K extends keyof Omit<PromoRule, "id">>(k: K, v: Omit<PromoRule, "id">[K]) {
    setForm(f => ({ ...f, [k]: v }))
  }

  async function handleSave() {
    if (!form.name.trim()) { setError("Name is required"); return }
    setSaving(true); setError("")
    try {
      if (editing) {
        await apiFetch(`/api/promo-rules/${editing.id}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        })
      } else {
        await apiFetch("/api/promo-rules", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        })
      }
      setShowForm(false)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  async function handleDeactivate(id: number) {
    if (!confirm("Deactivate this promo rule?")) return
    await apiFetch(`/api/promo-rules/${id}`, { method: "DELETE" })
    await load()
  }

  function discountLabel(r: PromoRule) {
    if (r.discount_type === "percent") return `${r.discount_value ?? 0}% off`
    if (r.discount_type === "fixed") return `${r.discount_value ?? 0} off`
    const gp = products.find(p => p.id === r.giveaway_product_id)
    return `Giveaway: ${r.giveaway_qty ?? 1}× ${gp?.name ?? "product"}`
  }

  function scopeLabel(r: PromoRule) {
    if (r.product_id) return products.find(p => p.id === r.product_id)?.name ?? `Product #${r.product_id}`
    if (r.category_id) return categories.find(c => c.id === r.category_id)?.name ?? `Category #${r.category_id}`
    return "All products"
  }

  return (
    <div className="max-w-5xl mx-auto">
      <PrintHeader title="Promotional Discounts" />
      <header className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <Tags className="w-6 h-6 text-[#b8943f] shrink-0" />
          <div>
            <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">Promotional Discounts</h1>
            <p className="text-xs sm:text-sm text-[#1a1814]/60">Time-limited price rules for products and categories</p>
          </div>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
          <button
            onClick={() => downloadCSV('promo-discounts.csv', rules.map(r => ({ Rule: r.name, Product: r.product_id ? products.find(p => p.id === r.product_id)?.name ?? '' : 'All', "Min Qty": r.min_qty ?? '', Discount: discountLabel(r), Active: r.is_active ? 'Yes' : 'No' })))}
            disabled={rules.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={openNew}
            className="flex items-center gap-2 px-4 py-2 bg-[#1a1814] text-white rounded-lg text-sm font-semibold hover:bg-[#b8943f] hover:text-black transition-all"
          >
            <Plus className="w-4 h-4" /> New Rule
          </button>
        </div>
      </header>

      {/* ── Rule form modal ─────────────────────────────────────────────── */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-serif font-semibold">{editing ? "Edit Rule" : "New Promo Rule"}</h2>
              <button onClick={() => setShowForm(false)}><X className="w-5 h-5 text-[#1a1814]/50" /></button>
            </div>

            {error && <p className="text-red-600 text-xs">{error}</p>}

            <div className="space-y-3">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Rule Name *</label>
                <input value={form.name} onChange={e => set("name", e.target.value)}
                  className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm" placeholder="e.g. Summer Sale 20%" />
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Description</label>
                <input value={form.description ?? ""} onChange={e => set("description", e.target.value || null)}
                  className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm" placeholder="Optional note" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Start Date</label>
                  <input type="date" value={form.start_date ?? ""} onChange={e => set("start_date", e.target.value || null)}
                    className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm" />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">End Date</label>
                  <input type="date" value={form.end_date ?? ""} onChange={e => set("end_date", e.target.value || null)}
                    className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Product (optional)</label>
                  <select value={form.product_id ?? ""} onChange={e => set("product_id", e.target.value ? parseInt(e.target.value) : null)}
                    className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm">
                    <option value="">— Any —</option>
                    {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Category (optional)</label>
                  <select value={form.category_id ?? ""} onChange={e => set("category_id", e.target.value ? parseInt(e.target.value) : null)}
                    className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm">
                    <option value="">— Any —</option>
                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Min Qty Trigger</label>
                  <input type="number" step="0.01" value={form.min_qty ?? ""} onChange={e => set("min_qty", e.target.value ? parseFloat(e.target.value) : null)}
                    className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm" placeholder="e.g. 10" />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Min Invoice Value</label>
                  <input type="number" step="0.01" value={form.min_invoice_value ?? ""} onChange={e => set("min_invoice_value", e.target.value ? parseFloat(e.target.value) : null)}
                    className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm" placeholder="e.g. 5000" />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Discount Type</label>
                <select value={form.discount_type} onChange={e => set("discount_type", e.target.value)}
                  className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm">
                  <option value="percent">Percentage (% off)</option>
                  <option value="fixed">Fixed Amount off</option>
                  <option value="giveaway">Giveaway (free product)</option>
                </select>
              </div>

              {(form.discount_type === "percent" || form.discount_type === "fixed") && (
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">{form.discount_type === "percent" ? "Discount %" : "Discount Amount"}</label>
                  <input type="number" step="0.01" value={form.discount_value ?? ""} onChange={e => set("discount_value", e.target.value ? parseFloat(e.target.value) : null)}
                    className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm" placeholder={form.discount_type === "percent" ? "e.g. 15" : "e.g. 500"} />
                </div>
              )}

              {form.discount_type === "giveaway" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Giveaway Product</label>
                    <select value={form.giveaway_product_id ?? ""} onChange={e => set("giveaway_product_id", e.target.value ? parseInt(e.target.value) : null)}
                      className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm">
                      <option value="">Select product</option>
                      {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Giveaway Qty</label>
                    <input type="number" step="0.01" value={form.giveaway_qty ?? ""} onChange={e => set("giveaway_qty", e.target.value ? parseFloat(e.target.value) : null)}
                      className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm" placeholder="e.g. 1" />
                  </div>
                </div>
              )}

              {editing && (
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.is_active} onChange={e => set("is_active", e.target.checked)} className="accent-[#b8943f]" />
                  Active
                </label>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button onClick={() => setShowForm(false)}
                className="px-4 py-2 bg-[#f6f3ee] border border-[#ede9e2] rounded-lg text-sm font-semibold hover:bg-[#ede9e2]">
                Cancel
              </button>
              <button onClick={handleSave} disabled={saving}
                className="px-4 py-2 bg-[#1a1814] text-white rounded-lg text-sm font-semibold hover:bg-[#b8943f] hover:text-black disabled:opacity-50">
                {saving ? "Saving…" : editing ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Rules table ──────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl shadow-sm border border-[#ede9e2] overflow-hidden">
        {rules.length === 0 ? (
          <div className="p-10 text-center text-[#1a1814]/40 text-sm">
            No promo rules yet. Create one to apply automatic discounts on invoices.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-[#faf6ec]">
              <tr>
                <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Rule</th>
                <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 hidden md:table-cell">Scope</th>
                <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 hidden sm:table-cell">Dates</th>
                <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Discount</th>
                <th className="px-4 py-3 text-center text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Active</th>
                <th className="w-20"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {rules.map(r => (
                <tr key={r.id} className={r.is_active ? "" : "opacity-50"}>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-[#1a1814]">{r.name}</div>
                    {r.description && <div className="text-xs text-[#1a1814]/50">{r.description}</div>}
                    {(r.min_qty || r.min_invoice_value) && (
                      <div className="text-xs text-[#b8943f] mt-0.5">
                        {r.min_qty ? `min qty ${r.min_qty}` : ""}
                        {r.min_qty && r.min_invoice_value ? " · " : ""}
                        {r.min_invoice_value ? `min value ${r.min_invoice_value}` : ""}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[#1a1814]/70 hidden md:table-cell">{scopeLabel(r)}</td>
                  <td className="px-4 py-3 text-xs text-[#1a1814]/60 hidden sm:table-cell">
                    {r.start_date ?? "∞"} → {r.end_date ?? "∞"}
                  </td>
                  <td className="px-4 py-3 font-semibold text-[#1a1814]">{discountLabel(r)}</td>
                  <td className="px-4 py-3 text-center">
                    {r.is_active
                      ? <Check className="w-4 h-4 text-emerald-500 mx-auto" />
                      : <X className="w-4 h-4 text-red-400 mx-auto" />}
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2 justify-end">
                      <button onClick={() => openEdit(r)} className="p-1.5 text-[#b8943f] hover:text-[#1a1814]">
                        <Pencil className="w-4 h-4" />
                      </button>
                      {r.is_active && (
                        <button onClick={() => handleDeactivate(r.id)} className="p-1.5 text-red-400 hover:text-red-600">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
