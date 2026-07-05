"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, DoorOpen, Save, AlertCircle, Plus, Trash2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { todayLocal } from "@/lib/utils"

type SourceType = "invoice" | "debit_note" | "scrap"

interface Invoice { id: number; number: string; customer_name: string | null; status: string }
interface DebitNote { id: number; number: string; vendor_name: string | null; status: string }

interface SourceLine { product_id?: number; description: string; qty: number }
interface SourceDoc { id: number; number: string; lines: SourceLine[] }

interface Product { id: number; code?: string; name: string; unit?: string; avg_cost?: number }

interface ScrapLineForm {
  product_id: string
  qty: string
  unit_cost: string
  unit_value: string
}

const emptyScrapLine = (): ScrapLineForm => ({ product_id: "", qty: "1", unit_cost: "0", unit_value: "0" })

export default function NewGateOutwardPage() {
  const router = useRouter()

  const [sourceType, setSourceType] = useState<SourceType>("invoice")

  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [debitNotes, setDebitNotes] = useState<DebitNote[]>([])
  const [products, setProducts] = useState<Product[]>([])

  const [sourceDocId, setSourceDocId] = useState("")
  const [sourceLines, setSourceLines] = useState<SourceLine[]>([])
  const [loadingDoc, setLoadingDoc] = useState(false)

  const [scrapLines, setScrapLines] = useState<ScrapLineForm[]>([emptyScrapLine()])

  const [gateDate, setGateDate] = useState(todayLocal())
  const [timeOut, setTimeOut] = useState("")
  const [vehicleNo, setVehicleNo] = useState("")
  const [challanNo, setChallanNo] = useState("")
  const [remarks, setRemarks] = useState("")

  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    apiFetch<{ items: Invoice[] }>("/api/invoices?limit=500")
      .then(d => setInvoices(d.items.filter(i => i.status !== "void")))
      .catch(() => setInvoices([]))
    apiFetch<{ items: DebitNote[] }>("/api/debit-notes?limit=500")
      .then(d => setDebitNotes(d.items.filter(dn => dn.status !== "draft")))
      .catch(() => setDebitNotes([]))
    apiFetch<{ items: Product[] }>("/api/products?limit=500")
      .then(d => setProducts(d.items))
      .catch(() => setProducts([]))
  }, [])

  // Reset the source-doc selection whenever the source type changes.
  useEffect(() => {
    setSourceDocId("")
    setSourceLines([])
    setError("")
  }, [sourceType])

  useEffect(() => {
    if (sourceType === "scrap" || !sourceDocId) { setSourceLines([]); return }
    setLoadingDoc(true)
    const path = sourceType === "invoice" ? `/api/invoices/${sourceDocId}` : `/api/debit-notes/${sourceDocId}`
    apiFetch<SourceDoc>(path)
      .then(d => setSourceLines(d.lines))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load document"))
      .finally(() => setLoadingDoc(false))
  }, [sourceType, sourceDocId])

  const updateScrapLine = (i: number, field: keyof ScrapLineForm, value: string) => {
    setScrapLines(prev => prev.map((l, idx) => {
      if (idx !== i) return l
      const next = { ...l, [field]: value }
      if (field === "product_id" && value) {
        const prod = products.find(p => String(p.id) === value)
        if (prod && prod.avg_cost != null) next.unit_cost = String(prod.avg_cost)
      }
      return next
    }))
  }

  const addScrapLine = () => setScrapLines(prev => [...prev, emptyScrapLine()])
  const removeScrapLine = (i: number) => setScrapLines(prev => prev.filter((_, idx) => idx !== i))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    let lines: { product_id: number; qty: number; unit_cost?: number; unit_value?: number }[]
    if (sourceType === "scrap") {
      const validLines = scrapLines.filter(l => l.product_id && (parseFloat(l.qty) || 0) > 0)
      if (!validLines.length) { setError("At least one line with a product and quantity is required."); return }
      lines = validLines.map(l => ({
        product_id: parseInt(l.product_id),
        qty: parseFloat(l.qty),
        unit_cost: parseFloat(l.unit_cost) || 0,
        unit_value: parseFloat(l.unit_value) || 0,
      }))
    } else {
      if (!sourceDocId) { setError(`${sourceType === "invoice" ? "Invoice" : "Debit note"} is required.`); return }
      if (!sourceLines.length) { setError("The selected document has no lines to record."); return }
      lines = sourceLines
        .filter(l => l.product_id)
        .map(l => ({ product_id: l.product_id as number, qty: l.qty }))
      if (!lines.length) { setError("The selected document has no product lines to record."); return }
    }

    setSaving(true)
    try {
      const go = await apiFetch<{ id: number }>("/api/gate-outwards", {
        method: "POST",
        body: JSON.stringify({
          source_doc_type: sourceType,
          source_doc_id: sourceType === "scrap" ? null : Number(sourceDocId),
          gate_date: gateDate,
          time_out: timeOut || null,
          vehicle_no: vehicleNo || null,
          challan_no: challanNo || null,
          remarks: remarks || null,
          lines,
        }),
      })
      router.push(`/store/gate-outward/${go.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed")
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <DoorOpen className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">New Gate Outward</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Record goods leaving at the gate.</p>
          </div>
        </div>
        <Link href="/store/gate-outward"
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft className="w-4 h-4" /> Back to Gate Outward
        </Link>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2.5 rounded-lg flex items-start gap-2 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Source type */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Exit Source</h2>
        <div className="flex gap-2">
          {(["invoice", "debit_note", "scrap"] as SourceType[]).map(t => (
            <button
              key={t}
              type="button"
              onClick={() => setSourceType(t)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${sourceType === t
                ? "bg-[var(--primary)] text-white border-transparent"
                : "border-[var(--border)] text-[var(--text-secondary)]"}`}
            >
              {t === "invoice" ? "Invoice" : t === "debit_note" ? "Debit Note" : "Scrap"}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {sourceType !== "scrap" && (
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">
                {sourceType === "invoice" ? "Invoice" : "Debit Note"} <span className="text-red-500">*</span>
              </label>
              <select
                required
                value={sourceDocId}
                onChange={e => setSourceDocId(e.target.value)}
                className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
              >
                <option value="">— Select {sourceType === "invoice" ? "invoice" : "debit note"} —</option>
                {sourceType === "invoice"
                  ? invoices.map(i => <option key={i.id} value={i.id}>{i.number} — {i.customer_name || "—"}</option>)
                  : debitNotes.map(dn => <option key={dn.id} value={dn.id}>{dn.number} — {dn.vendor_name || "—"}</option>)}
              </select>
            </div>
          )}
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Gate Date <span className="text-red-500">*</span></label>
            <input
              type="date"
              required
              value={gateDate}
              onChange={e => setGateDate(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Time Out</label>
            <input
              type="time"
              value={timeOut}
              onChange={e => setTimeOut(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Vehicle No.</label>
            <input
              type="text"
              value={vehicleNo}
              onChange={e => setVehicleNo(e.target.value)}
              placeholder="e.g. LEA-1234"
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Challan No.</label>
            <input
              type="text"
              value={challanNo}
              onChange={e => setChallanNo(e.target.value)}
              placeholder="Delivery challan / bilty #"
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
        </div>
      </section>

      {/* Lines */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Items</h2>

        {sourceType !== "scrap" ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
                  <th className="text-left pb-2 pr-2 min-w-[220px]">Description</th>
                  <th className="text-right pb-2 pr-2 w-24">Qty</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {sourceLines.map((line, idx) => (
                  <tr key={idx}>
                    <td className="py-1.5 pr-2 text-[var(--text-primary)]">{line.description}</td>
                    <td className="py-1.5 pr-2 text-right text-[var(--text-muted)]">{line.qty}</td>
                  </tr>
                ))}
                {sourceLines.length === 0 && (
                  <tr>
                    <td colSpan={2} className="py-8 text-center text-[var(--text-muted)]">
                      {loadingDoc ? "Loading…" : `Select ${sourceType === "invoice" ? "an invoice" : "a debit note"} to load its lines`}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
                    <th className="text-left pb-2 pr-2 min-w-[180px]">Product</th>
                    <th className="text-right pb-2 pr-2 w-24">Qty</th>
                    <th className="text-right pb-2 pr-2 w-28">Unit Cost</th>
                    <th className="text-right pb-2 pr-2 w-28">Unit Value</th>
                    <th className="w-10"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {scrapLines.map((line, idx) => (
                    <tr key={idx}>
                      <td className="py-1.5 pr-2">
                        <select
                          value={line.product_id}
                          onChange={e => updateScrapLine(idx, "product_id", e.target.value)}
                          className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs focus:ring-2 focus:ring-[var(--primary)] outline-none"
                        >
                          <option value="">— select product —</option>
                          {products.map(p => <option key={p.id} value={p.id}>{p.code ? `${p.code} — ${p.name}` : p.name}</option>)}
                        </select>
                      </td>
                      <td className="py-1.5 pr-2">
                        <input
                          type="number"
                          min="0"
                          step="any"
                          value={line.qty}
                          onChange={e => updateScrapLine(idx, "qty", e.target.value)}
                          className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs text-right font-mono focus:ring-2 focus:ring-[var(--primary)] outline-none"
                        />
                      </td>
                      <td className="py-1.5 pr-2">
                        <input
                          type="number"
                          min="0"
                          step="any"
                          value={line.unit_cost}
                          onChange={e => updateScrapLine(idx, "unit_cost", e.target.value)}
                          className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs text-right font-mono focus:ring-2 focus:ring-[var(--primary)] outline-none"
                        />
                      </td>
                      <td className="py-1.5 pr-2">
                        <input
                          type="number"
                          min="0"
                          step="any"
                          value={line.unit_value}
                          onChange={e => updateScrapLine(idx, "unit_value", e.target.value)}
                          className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs text-right font-mono focus:ring-2 focus:ring-[var(--primary)] outline-none"
                        />
                      </td>
                      <td className="py-1.5">
                        <button
                          type="button"
                          onClick={() => removeScrapLine(idx)}
                          disabled={scrapLines.length === 1}
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
              onClick={addScrapLine}
              className="flex items-center gap-1.5 text-sm font-semibold text-[var(--primary)] hover:text-[var(--text-primary)] transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add line
            </button>
          </>
        )}
      </section>

      {/* Remarks */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5">
        <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Remarks</label>
        <textarea
          value={remarks}
          onChange={e => setRemarks(e.target.value)}
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
          {saving ? "Saving…" : "Save Gate Outward"}
        </button>
      </div>
    </form>
  )
}
