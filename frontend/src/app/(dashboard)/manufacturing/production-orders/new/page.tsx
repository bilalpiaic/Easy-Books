"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

interface BomOption {
  id: number
  output_product_id: number
  version: number
  description: string | null
  is_active: boolean
  output_qty: string
}

interface Customer { id: number; name: string }
interface RatePlan { id: number; code: string; name: string; is_active: boolean }

export default function NewProductionOrderPage() {
  const { t } = useTranslation()

  const router = useRouter()

  const [boms, setBoms]           = useState<BomOption[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [ratePlans, setRatePlans] = useState<RatePlan[]>([])
  const [loadErr, setLoadErr]     = useState<string | null>(null)

  const [bomId, setBomId]           = useState("")
  const [customerId, setCustomerId] = useState("")
  const [outputQty, setOutputQty]   = useState("")
  const [ratePlanId, setRatePlanId] = useState("")
  const [notes, setNotes]           = useState("")

  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<{ items: BomOption[] }>("/api/bom"),
      apiFetch<{ items: Customer[] }>("/api/customers"),
      apiFetch<{ items: RatePlan[] }>("/api/rate-plans"),
    ])
      .then(([b, c, r]) => {
        setBoms(b.items.filter(x => x.is_active))
        setCustomers(c.items)
        setRatePlans(r.items.filter(x => x.is_active))
      })
      .catch(() => setLoadErr("Failed to load options"))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!bomId)      { setError("Bill of Material is required"); return }
    if (!customerId) { setError("Customer is required"); return }
    const qty = parseFloat(outputQty)
    if (isNaN(qty) || qty <= 0) { setError("Output qty must be > 0"); return }

    setSaving(true); setError(null)
    try {
      const res = await apiFetch<{ id: number; number: string }>("/api/production-orders", {
        method: "POST",
        body: JSON.stringify({
          bom_id:       parseInt(bomId),
          customer_id:  parseInt(customerId),
          output_qty:   qty,
          rate_plan_id: ratePlanId ? parseInt(ratePlanId) : undefined,
          notes:        notes.trim() || undefined,
        }),
      })
      router.push(`/manufacturing/production-orders`)
      void res
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create PO")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <div>
        <Link href="/manufacturing/production-orders" className="text-sm text-[var(--primary)] hover:underline">
          ← Production Orders
        </Link>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] mt-2">New Production Order</h1>
        <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">Start a batch from a Bill of Material.</p>
      </div>

      {loadErr && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 rounded-xl px-4 py-3 text-sm">{loadErr}</div>
      )}

      <form onSubmit={handleSubmit} className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
        <div>
          <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">
            Bill of Material
          </label>
          <select value={bomId} onChange={e => setBomId(e.target.value)}
            className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]">
            <option value="">Select BOM…</option>
            {boms.map(b => (
              <option key={b.id} value={b.id}>
                #{b.id} — product #{b.output_product_id} v{b.version}
                {b.description ? ` (${b.description})` : ""}
              </option>
            ))}
          </select>
          {boms.length === 0 && !loadErr && (
            <p className="text-xs text-amber-700 mt-1">
              No active BOMs found.{" "}
              <Link href="/manufacturing/boms/new" className="underline">Create one first.</Link>
            </p>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">{t('col.customer', 'Customer')}</label>
          <select value={customerId} onChange={e => setCustomerId(e.target.value)}
            className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]">
            <option value="">Select customer…</option>
            {customers.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">
            Output Qty
          </label>
          <input type="number" min="0.001" step="any" value={outputQty}
            onChange={e => setOutputQty(e.target.value)}
            placeholder="e.g. 100"
            className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right tabular-nums focus:outline-none focus:border-[var(--primary)]" />
        </div>

        <div>
          <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">
            Rate Plan <span className="font-normal normal-case text-[var(--text-primary)]/50">(optional — auto-picks customer&apos;s active plan)</span>
          </label>
          <select value={ratePlanId} onChange={e => setRatePlanId(e.target.value)}
            className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]">
            <option value="">Auto-select</option>
            {ratePlans.map(r => (
              <option key={r.id} value={r.id}>{r.code} — {r.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">{t('col.notes', 'Notes')}</label>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
            placeholder="Optional internal notes"
            className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:border-[var(--primary)]" />
        </div>

        <div className="bg-[#faf8f4] border border-[var(--border)] rounded-lg px-4 py-3 text-xs text-[var(--text-primary)]/70 space-y-1">
          <p className="font-semibold text-[var(--text-primary)]/90">After creation</p>
          <p>The PO starts in <b>{t('status.draft', 'Draft')}</b> state. Walk it through: <b>Start → Complete → Deliver → Bill</b> using the action buttons on the list page.</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg px-4 py-3 text-sm">{error}</div>
        )}

        <div className="flex gap-3 pt-1">
          <button type="submit" disabled={saving}
            className="flex-1 bg-[var(--primary)] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50 transition-colors">
            {saving ? "Creating…" : "Create Production Order"}
          </button>
          <Link href="/manufacturing/production-orders"
            className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors">{t('common.cancel', 'Cancel')}</Link>
        </div>
      </form>
    </div>
  )
}
