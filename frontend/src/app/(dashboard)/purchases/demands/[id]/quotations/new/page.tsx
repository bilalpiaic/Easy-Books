"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, FileText, Save, AlertCircle, AlertTriangle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { todayLocal } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"

interface Vendor { id: number; name: string }
interface DemandLine { id: number; product_id?: number; description: string; qty: number; unit?: string }
interface Demand { id: number; number: string; status: string; lines: DemandLine[] }

interface QuoteLineForm {
  demand_line_id: number
  description: string
  demandQty: number
  unit?: string
  rate: string
  qty: string
}

export default function NewQuotationPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const fmt = useFmt()

  const [demand, setDemand] = useState<Demand | null>(null)
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [vendorId, setVendorId] = useState("")
  const [quoteDate, setQuoteDate] = useState(todayLocal())
  const [validUntil, setValidUntil] = useState("")
  const [deliveryTerms, setDeliveryTerms] = useState("")
  const [paymentTerms, setPaymentTerms] = useState("")
  const [notes, setNotes] = useState("")
  const [lines, setLines] = useState<QuoteLineForm[]>([])

  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    Promise.all([
      apiFetch<Demand>(`/api/purchase-demands/${id}`),
      apiFetch<{ items: Vendor[] }>("/api/vendors?limit=500"),
    ])
      .then(([d, v]) => {
        setDemand(d)
        setVendors(v.items)
        setLines(d.lines.map(l => ({
          demand_line_id: l.id,
          description: l.description,
          demandQty: l.qty,
          unit: l.unit,
          rate: "",
          qty: String(l.qty),
        })))
      })
      .catch(e => setLoadError(e instanceof Error ? e.message : "Not found"))
      .finally(() => setLoading(false))
  }, [id])

  const updateLine = (i: number, field: "rate" | "qty", value: string) => {
    setLines(prev => prev.map((l, idx) => idx !== i ? l : { ...l, [field]: value }))
  }

  const pricedLines = lines.filter(l => parseFloat(l.rate) > 0)
  const grandTotal = pricedLines.reduce((sum, l) => sum + (parseFloat(l.rate) || 0) * (parseFloat(l.qty) || 0), 0)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    if (!vendorId) { setError("Vendor is required."); return }
    if (!pricedLines.length) { setError("At least one line must have a rate."); return }

    setSaving(true)
    try {
      await apiFetch("/api/quotations", {
        method: "POST",
        body: JSON.stringify({
          demand_id: Number(id),
          vendor_id: parseInt(vendorId),
          quote_date: quoteDate,
          valid_until: validUntil || null,
          delivery_terms: deliveryTerms || null,
          payment_terms: paymentTerms || null,
          notes: notes || null,
          lines: pricedLines.map(l => ({
            demand_line_id: l.demand_line_id,
            rate: parseFloat(l.rate),
            qty: parseFloat(l.qty) || 1,
          })),
        }),
      })
      router.push(`/purchases/demands/${id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed")
      setSaving(false)
    }
  }

  if (loading) return <p className="p-4 text-sm text-[var(--text-muted)]">Loading…</p>
  if (loadError || !demand) return <p className="p-4 text-sm text-red-600">{loadError ?? "Demand not found"}</p>

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileText className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">New Quotation</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Against demand {demand.number}</p>
          </div>
        </div>
        <Link href={`/purchases/demands/${id}`}
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft className="w-4 h-4" /> Back to Demand
        </Link>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2.5 rounded-lg flex items-start gap-2 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Header fields */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Quotation Details</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Vendor <span className="text-red-500">*</span></label>
            <select
              required
              value={vendorId}
              onChange={e => setVendorId(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            >
              <option value="">— Select vendor —</option>
              {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Quote Date <span className="text-red-500">*</span></label>
            <input
              type="date"
              required
              value={quoteDate}
              onChange={e => setQuoteDate(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Valid Until</label>
            <input
              type="date"
              value={validUntil}
              onChange={e => setValidUntil(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Delivery Terms</label>
            <input
              type="text"
              value={deliveryTerms}
              onChange={e => setDeliveryTerms(e.target.value)}
              placeholder="e.g. 7 days from PO"
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Payment Terms</label>
            <input
              type="text"
              value={paymentTerms}
              onChange={e => setPaymentTerms(e.target.value)}
              placeholder="e.g. Net 30"
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
        </div>
      </section>

      {/* Lines */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Items</h2>
          {lines.length > 0 && (
            <span className={`flex items-center gap-1.5 text-xs font-semibold ${pricedLines.length < lines.length ? "text-amber-600" : "text-[var(--text-muted)]"}`}>
              {pricedLines.length < lines.length && <AlertTriangle className="w-3.5 h-3.5" />}
              {pricedLines.length} of {lines.length} lines priced
            </span>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
                <th className="text-left pb-2 pr-2 min-w-[220px]">Description</th>
                <th className="text-right pb-2 pr-2 w-24">Demand Qty</th>
                <th className="text-right pb-2 pr-2 w-28">Rate</th>
                <th className="text-right pb-2 pr-2 w-24">Qty</th>
                <th className="text-right pb-2 pr-2 w-28">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {lines.map((line, idx) => {
                const amount = (parseFloat(line.rate) || 0) * (parseFloat(line.qty) || 0)
                return (
                  <tr key={line.demand_line_id}>
                    <td className="py-1.5 pr-2 text-[var(--text-primary)]">{line.description}</td>
                    <td className="py-1.5 pr-2 text-right text-[var(--text-muted)]">
                      {line.demandQty}{line.unit ? ` ${line.unit}` : ""}
                    </td>
                    <td className="py-1.5 pr-2">
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={line.rate}
                        onChange={e => updateLine(idx, "rate", e.target.value)}
                        placeholder="0.00"
                        className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs text-right font-mono focus:ring-2 focus:ring-[var(--primary)] outline-none"
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
                    <td className="py-1.5 pr-2 text-right font-mono text-[var(--text-primary)]">{fmt(amount)}</td>
                  </tr>
                )
              })}
              {lines.length === 0 && (
                <tr><td colSpan={5} className="py-8 text-center text-[var(--text-muted)]">No lines on this demand</td></tr>
              )}
            </tbody>
            {lines.length > 0 && (
              <tfoot>
                <tr className="border-t border-[var(--border)] font-bold text-[var(--text-primary)]">
                  <td colSpan={4} className="py-2 pr-2 text-right">Total</td>
                  <td className="py-2 pr-2 text-right font-mono">{fmt(grandTotal)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </section>

      {/* Notes */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5">
        <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Notes</label>
        <textarea
          value={notes}
          onChange={e => setNotes(e.target.value)}
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
          {saving ? "Saving…" : "Save Quotation"}
        </button>
      </div>
    </form>
  )
}
