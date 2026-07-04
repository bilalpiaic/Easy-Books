"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ClipboardList, Plus, Trash2, Save, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { todayLocal } from "@/lib/utils"

interface AnalyticAccount { id: number; code: string; name: string }
interface Product { id: number; code?: string; name: string; unit: string }

export interface DemandLineForm {
  product_id: string
  description: string
  qty: string
  unit: string
}

export interface DemandFormValues {
  demand_date: string
  required_by: string
  analytic_account_id: string
  purpose: string
  notes: string
  lines: DemandLineForm[]
}

export const emptyDemandLine = (): DemandLineForm => ({ product_id: "", description: "", qty: "1", unit: "" })

export const emptyDemandForm = (): DemandFormValues => ({
  demand_date: todayLocal(),
  required_by: "",
  analytic_account_id: "",
  purpose: "",
  notes: "",
  lines: [emptyDemandLine()],
})

export function DemandForm({
  title,
  subtitle,
  initial,
  onSubmit,
  submitLabel = "Save Demand",
}: {
  title: string
  subtitle?: string
  initial: DemandFormValues
  onSubmit: (payload: Record<string, unknown>) => Promise<void>
  submitLabel?: string
}) {
  const router = useRouter()
  const [accounts, setAccounts] = useState<AnalyticAccount[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [form, setForm] = useState<DemandFormValues>(initial)
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    apiFetch<{ items: AnalyticAccount[] }>("/api/analytic-accounts?limit=500").then(d => setAccounts(d.items)).catch(() => {})
    apiFetch<{ items: Product[] }>("/api/products?limit=500").then(d => setProducts(d.items)).catch(() => {})
  }, [])

  const updateLine = (i: number, field: keyof DemandLineForm, value: string) => {
    setForm(prev => {
      const next = prev.lines.map((l, idx) => idx !== i ? l : { ...l, [field]: value })
      // auto-fill description + unit when a product is selected (still editable after)
      if (field === "product_id" && value) {
        const prod = products.find(p => String(p.id) === value)
        if (prod) {
          next[i] = { ...next[i], description: prod.name, unit: prod.unit }
        }
      }
      return { ...prev, lines: next }
    })
  }

  const addLine = () => setForm(f => ({ ...f, lines: [...f.lines, emptyDemandLine()] }))
  const removeLine = (i: number) => setForm(f => ({ ...f, lines: f.lines.filter((_, idx) => idx !== i) }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const validLines = form.lines.filter(l => l.description.trim() && parseFloat(l.qty) > 0)
    if (!validLines.length) { setError("At least one line with a description and quantity is required."); return }

    setSaving(true); setError("")
    try {
      await onSubmit({
        demand_date: form.demand_date,
        required_by: form.required_by || null,
        analytic_account_id: form.analytic_account_id ? parseInt(form.analytic_account_id) : null,
        purpose: form.purpose || null,
        notes: form.notes || null,
        lines: validLines.map(l => ({
          product_id: l.product_id ? parseInt(l.product_id) : null,
          description: l.description,
          qty: parseFloat(l.qty),
          unit: l.unit || null,
        })),
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed")
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl p-4">
      <header className="flex items-center gap-3">
        <ClipboardList className="w-7 h-7 text-[var(--primary)]" />
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{title}</h1>
          {subtitle && <p className="text-sm text-[var(--text-primary)]/60">{subtitle}</p>}
        </div>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2.5 rounded-lg flex items-start gap-2 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Header fields */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Demand Details</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Demand Date <span className="text-red-500">*</span></label>
            <input
              type="date"
              required
              value={form.demand_date}
              onChange={e => setForm(f => ({ ...f, demand_date: e.target.value }))}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Required By</label>
            <input
              type="date"
              value={form.required_by}
              onChange={e => setForm(f => ({ ...f, required_by: e.target.value }))}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Department / Cost Center</label>
            <select
              value={form.analytic_account_id}
              onChange={e => setForm(f => ({ ...f, analytic_account_id: e.target.value }))}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            >
              <option value="">— None —</option>
              {accounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Purpose</label>
            <input
              type="text"
              value={form.purpose}
              onChange={e => setForm(f => ({ ...f, purpose: e.target.value }))}
              placeholder="What is this requisition for?"
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
        </div>
      </section>

      {/* Line items — quantity only, no rate/amount column by design */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Items</h2>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
                <th className="text-left pb-2 pr-2 min-w-[160px]">Product</th>
                <th className="text-left pb-2 pr-2 min-w-[220px]">Description<span className="text-red-500">*</span></th>
                <th className="text-right pb-2 pr-2 w-24">Qty</th>
                <th className="text-left pb-2 pr-2 w-24">Unit</th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {form.lines.map((line, idx) => (
                <tr key={idx}>
                  <td className="py-1.5 pr-2">
                    <select
                      value={line.product_id}
                      onChange={e => updateLine(idx, "product_id", e.target.value)}
                      className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs focus:ring-2 focus:ring-[var(--primary)] outline-none"
                    >
                      <option value="">— optional —</option>
                      {products.map(p => <option key={p.id} value={p.id}>{p.code ? `${p.code} — ${p.name}` : p.name}</option>)}
                    </select>
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      required
                      type="text"
                      value={line.description}
                      onChange={e => updateLine(idx, "description", e.target.value)}
                      className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs focus:ring-2 focus:ring-[var(--primary)] outline-none"
                    />
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={line.qty}
                      onChange={e => updateLine(idx, "qty", e.target.value)}
                      className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs text-right font-mono focus:ring-2 focus:ring-[var(--primary)] outline-none"
                    />
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      type="text"
                      value={line.unit}
                      onChange={e => updateLine(idx, "unit", e.target.value)}
                      placeholder="pcs"
                      className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs focus:ring-2 focus:ring-[var(--primary)] outline-none"
                    />
                  </td>
                  <td className="py-1.5">
                    <button
                      type="button"
                      onClick={() => removeLine(idx)}
                      disabled={form.lines.length === 1}
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

        <button
          type="button"
          onClick={addLine}
          className="flex items-center gap-1.5 text-sm font-semibold text-[var(--primary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add line
        </button>
      </section>

      {/* Notes */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5">
        <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Notes (internal)</label>
        <textarea
          value={form.notes}
          onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
          rows={2}
          placeholder="Additional context…"
          className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm resize-none"
        />
      </section>

      {/* Actions */}
      <div className="flex gap-3 justify-end">
        <button
          type="button"
          onClick={() => router.back()}
          className="px-5 py-2.5 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg font-semibold hover:bg-[var(--bg-page)] transition-colors text-sm"
        >Cancel</button>
        <button
          type="submit"
          disabled={saving}
          className="px-5 py-2.5 bg-[var(--text-primary)] text-white rounded-lg font-semibold flex items-center gap-2 hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50 text-sm"
        >
          <Save className="w-4 h-4" />
          {saving ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  )
}

export default function NewDemandPage() {
  const router = useRouter()

  return (
    <DemandForm
      title="New Purchase Demand"
      subtitle="Request goods or services — quantities only, no pricing."
      initial={emptyDemandForm()}
      onSubmit={async payload => {
        const d = await apiFetch<{ id: number }>("/api/purchase-demands", {
          method: "POST",
          body: JSON.stringify(payload),
        })
        router.push(`/purchases/demands/${d.id}`)
      }}
    />
  )
}
