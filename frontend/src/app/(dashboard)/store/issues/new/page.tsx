"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, PackageMinus, Save, AlertCircle, Plus, Trash2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { todayLocal } from "@/lib/utils"

interface StockLocation { id: number; code: string; name: string }
interface Account { id: number; code: string; name: string; type: string; postable?: boolean }
interface AnalyticAccount { id: number; code: string; name: string }
interface Product { id: number; code?: string; name: string; unit?: string; product_type: string; stock_qty: number }

interface SILineForm {
  product_id: string
  qty: string
}

const emptyLine = (): SILineForm => ({ product_id: "", qty: "1" })

export default function NewStoreIssuePage() {
  const router = useRouter()

  const [locations, setLocations] = useState<StockLocation[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])
  const [products, setProducts] = useState<Product[]>([])

  const [issueDate, setIssueDate] = useState(todayLocal())
  const [locationId, setLocationId] = useState("")
  const [debitAccountId, setDebitAccountId] = useState("")
  const [analyticAccountId, setAnalyticAccountId] = useState("")
  const [notes, setNotes] = useState("")

  const [lines, setLines] = useState<SILineForm[]>([emptyLine()])

  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    apiFetch<{ items: StockLocation[] }>("/api/stock-locations")
      .then(d => setLocations(d.items))
      .catch(() => setLocations([]))
    apiFetch<{ items: Account[] }>("/api/accounts?limit=500")
      .then(d => setAccounts(d.items.filter(a => a.type === "Expense" && a.postable !== false)))
      .catch(() => setAccounts([]))
    apiFetch<{ items: AnalyticAccount[] }>("/api/analytic-accounts?limit=500")
      .then(d => setAnalyticAccounts(d.items))
      .catch(() => setAnalyticAccounts([]))
    apiFetch<{ items: Product[] }>("/api/products?product_type=stock&limit=500")
      .then(d => setProducts(d.items))
      .catch(() => setProducts([]))
  }, [])

  const updateLine = (i: number, field: keyof SILineForm, value: string) => {
    setLines(prev => prev.map((l, idx) => idx !== i ? l : { ...l, [field]: value }))
  }

  const addLine = () => setLines(prev => [...prev, emptyLine()])
  const removeLine = (i: number) => setLines(prev => prev.filter((_, idx) => idx !== i))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (!locationId) { setError("Location is required."); return }
    if (!debitAccountId) { setError("Debit account is required."); return }

    const validLines = lines.filter(l => l.product_id && (parseFloat(l.qty) || 0) > 0)
    if (!validLines.length) { setError("At least one line with a product and quantity is required."); return }

    setSaving(true)
    try {
      const si = await apiFetch<{ id: number }>("/api/store-issues", {
        method: "POST",
        body: JSON.stringify({
          issue_date: issueDate,
          from_location_id: Number(locationId),
          analytic_account_id: analyticAccountId ? Number(analyticAccountId) : null,
          debit_account_id: Number(debitAccountId),
          notes: notes || null,
          lines: validLines.map(l => ({
            product_id: parseInt(l.product_id),
            qty: parseFloat(l.qty),
          })),
        }),
      })
      router.push(`/store/issues/${si.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed")
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <PackageMinus className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">New Store Issue</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Record stock consumed by a department or cost center.</p>
          </div>
        </div>
        <Link href="/store/issues"
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft className="w-4 h-4" /> Back to Store Issues
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
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Issue Details</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Issue Date <span className="text-red-500">*</span></label>
            <input
              type="date"
              required
              value={issueDate}
              onChange={e => setIssueDate(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Location <span className="text-red-500">*</span></label>
            <select
              required
              value={locationId}
              onChange={e => setLocationId(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            >
              <option value="">— Select location —</option>
              {locations.map(l => <option key={l.id} value={l.id}>{l.code} — {l.name}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Debit Account <span className="text-red-500">*</span></label>
            <select
              required
              value={debitAccountId}
              onChange={e => setDebitAccountId(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            >
              <option value="">— Select expense account —</option>
              {accounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Analytic Account</label>
            <select
              value={analyticAccountId}
              onChange={e => setAnalyticAccountId(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            >
              <option value="">None</option>
              {analyticAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
            </select>
          </div>
        </div>
      </section>

      {/* Lines */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Items</h2>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
                <th className="text-left pb-2 pr-2 min-w-[220px]">Product</th>
                <th className="text-right pb-2 pr-2 w-24">Qty</th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {lines.map((line, idx) => {
                const prod = products.find(p => String(p.id) === line.product_id)
                return (
                  <tr key={idx}>
                    <td className="py-1.5 pr-2">
                      <select
                        value={line.product_id}
                        onChange={e => updateLine(idx, "product_id", e.target.value)}
                        className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs focus:ring-2 focus:ring-[var(--primary)] outline-none"
                      >
                        <option value="">— select product —</option>
                        {products.map(p => (
                          <option key={p.id} value={p.id}>
                            {p.code ? `${p.code} — ${p.name}` : p.name} (on hand: {p.stock_qty})
                          </option>
                        ))}
                      </select>
                      {prod && (
                        <p className="mt-1 text-[10px] text-[var(--text-muted)]">On hand: {prod.stock_qty} {prod.unit || ""}</p>
                      )}
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
                    <td className="py-1.5">
                      <button
                        type="button"
                        onClick={() => removeLine(idx)}
                        disabled={lines.length === 1}
                        className="p-1.5 text-red-400 hover:text-red-600 disabled:opacity-30 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                )
              })}
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
          {saving ? "Saving…" : "Save Store Issue"}
        </button>
      </div>
    </form>
  )
}
