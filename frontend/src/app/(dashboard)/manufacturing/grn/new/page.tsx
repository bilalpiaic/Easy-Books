"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Plus, Trash2 } from "lucide-react"
import { apiFetch } from "@/lib/api"

interface Customer { id: number; name: string }
interface Product  { id: number; code: string; name: string }
interface StockLocation { id: number; code: string; name: string; type: string }

interface LineState {
  product_id: string
  qty: string
  lot_no: string
  declared_value: string
  notes: string
}

const emptyLine = (): LineState => ({
  product_id: "", qty: "", lot_no: "", declared_value: "0", notes: "",
})

export default function NewGrnPage() {
  const router = useRouter()

  const [customers, setCustomers]   = useState<Customer[]>([])
  const [products, setProducts]     = useState<Product[]>([])
  const [locations, setLocations]   = useState<StockLocation[]>([])

  const [customerId, setCustomerId]   = useState("")
  const [receivedDate, setReceivedDate] = useState(new Date().toISOString().slice(0, 10))
  const [locationId, setLocationId]   = useState("")
  const [notes, setNotes]             = useState("")
  const [lines, setLines]             = useState<LineState[]>([emptyLine()])

  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [loadErr, setLoadErr] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<{ items: Customer[] }>("/api/customers?limit=500"),
      apiFetch<{ items: Product[] }>("/api/products?limit=500"),
      apiFetch<{ items: StockLocation[] }>("/api/stock-locations?type=customer_custodial"),
    ])
      .then(([c, p, l]) => {
        setCustomers(c.items)
        setProducts(p.items)
        setLocations(l.items)
        if (l.items.length === 1) setLocationId(String(l.items[0].id))
      })
      .catch(() => setLoadErr("Failed to load reference data"))
  }, [])

  const updateLine = (i: number, patch: Partial<LineState>) =>
    setLines(prev => prev.map((l, idx) => idx === i ? { ...l, ...patch } : l))

  const addLine = () => setLines(prev => [...prev, emptyLine()])
  const removeLine = (i: number) => setLines(prev => prev.filter((_, idx) => idx !== i))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!customerId)    { setError("Please select a customer"); return }
    if (!receivedDate)  { setError("Received date is required"); return }
    const validLines = lines.filter(l => l.product_id && parseFloat(l.qty) > 0)
    if (!validLines.length) { setError("At least one line with product and qty is required"); return }

    setSaving(true); setError(null)
    try {
      const body = {
        customer_id:   parseInt(customerId),
        received_date: receivedDate,
        location_id:   locationId ? parseInt(locationId) : undefined,
        notes:         notes || undefined,
        lines: validLines.map(l => ({
          product_id:     parseInt(l.product_id),
          qty:            parseFloat(l.qty),
          lot_no:         l.lot_no || undefined,
          declared_value: parseFloat(l.declared_value) || 0,
          notes:          l.notes || undefined,
        })),
      }
      const res = await apiFetch<{ id: number }>("/api/grn", {
        method: "POST",
        body: JSON.stringify(body),
      })
      router.push(`/manufacturing/grn/${res.id}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save GRN")
    } finally {
      setSaving(false)
    }
  }

  const totalDeclared = lines.reduce((s, l) => s + (parseFloat(l.declared_value) || 0), 0)

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link href="/manufacturing/grn" className="text-sm text-[#b8943f] hover:underline">
          ← Goods Receipt
        </Link>
        <h1 className="text-2xl font-serif font-semibold text-[#1a1814] mt-2">New Goods Receipt Note</h1>
        <p className="text-sm text-[#1a1814]/60 mt-0.5">Record customer-supplied material received into your godown.</p>
      </div>

      {loadErr && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{loadErr}</div>
      )}

      {locations.length === 0 && !loadErr && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 rounded-xl px-4 py-3 text-sm">
          No customer custodial locations found.{" "}
          <Link href="/manufacturing/stock-locations" className="font-medium underline">
            Create a godown first →
          </Link>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Header fields */}
        <div className="bg-white border border-[#ede9e2] rounded-xl p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Customer</label>
              <select
                value={customerId}
                onChange={e => setCustomerId(e.target.value)}
                className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]"
              >
                <option value="">Select customer…</option>
                {customers.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Received Date</label>
              <input
                type="date"
                value={receivedDate}
                onChange={e => setReceivedDate(e.target.value)}
                className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Godown / Location</label>
              <select
                value={locationId}
                onChange={e => setLocationId(e.target.value)}
                className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]"
              >
                <option value="">Auto (first custodial location)</option>
                {locations.map(l => (
                  <option key={l.id} value={l.id}>{l.code} — {l.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Notes</label>
              <input
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Optional"
                className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]"
              />
            </div>
          </div>
        </div>

        {/* Line items */}
        <div className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-[#ede9e2] flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[#1a1814]">Material Lines</h2>
            <button
              type="button"
              onClick={addLine}
              className="inline-flex items-center gap-1.5 text-xs text-[#b8943f] hover:underline"
            >
              <Plus className="w-3.5 h-3.5" /> Add line
            </button>
          </div>

          {/* Desktop table */}
          <div className="overflow-x-auto hidden sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#ede9e2] bg-[#faf8f4]">
                  <th className="text-left px-4 py-2.5 font-semibold text-[#1a1814]/70">Product</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-[#1a1814]/70 w-24">Qty</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-[#1a1814]/70 w-28">Lot No.</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-[#1a1814]/70 w-28">Declared Value</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-[#1a1814]/70">Notes</th>
                  <th className="w-8 px-2" />
                </tr>
              </thead>
              <tbody>
                {lines.map((line, i) => (
                  <tr key={i} className="border-b border-[#ede9e2] last:border-0">
                    <td className="px-4 py-2">
                      <select
                        value={line.product_id}
                        onChange={e => updateLine(i, { product_id: e.target.value })}
                        className="w-full border border-[#d4cfc7] rounded px-2 py-1.5 text-xs focus:outline-none focus:border-[#b8943f]"
                      >
                        <option value="">Select product…</option>
                        {products.map(p => (
                          <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        min="0.001"
                        step="any"
                        value={line.qty}
                        onChange={e => updateLine(i, { qty: e.target.value })}
                        placeholder="0"
                        className="w-full border border-[#d4cfc7] rounded px-2 py-1.5 text-xs text-right tabular-nums focus:outline-none focus:border-[#b8943f]"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        value={line.lot_no}
                        onChange={e => updateLine(i, { lot_no: e.target.value })}
                        placeholder="optional"
                        className="w-full border border-[#d4cfc7] rounded px-2 py-1.5 text-xs font-mono focus:outline-none focus:border-[#b8943f]"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={line.declared_value}
                        onChange={e => updateLine(i, { declared_value: e.target.value })}
                        className="w-full border border-[#d4cfc7] rounded px-2 py-1.5 text-xs text-right tabular-nums focus:outline-none focus:border-[#b8943f]"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        value={line.notes}
                        onChange={e => updateLine(i, { notes: e.target.value })}
                        placeholder="optional"
                        className="w-full border border-[#d4cfc7] rounded px-2 py-1.5 text-xs focus:outline-none focus:border-[#b8943f]"
                      />
                    </td>
                    <td className="px-2 py-2 text-right">
                      {lines.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeLine(i)}
                          className="text-[#1a1814]/30 hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              {totalDeclared > 0 && (
                <tfoot>
                  <tr className="border-t border-[#ede9e2] bg-[#faf8f4]">
                    <td className="px-4 py-2 text-xs text-[#1a1814]/60" colSpan={3}>
                      Total declared value (memo JE will be posted)
                    </td>
                    <td className="px-3 py-2 text-right text-xs font-bold tabular-nums text-[#1a1814]">
                      {totalDeclared.toFixed(2)}
                    </td>
                    <td colSpan={2} />
                  </tr>
                </tfoot>
              )}
            </table>
          </div>

          {/* Mobile stacked */}
          <div className="sm:hidden divide-y divide-[#ede9e2]">
            {lines.map((line, i) => (
              <div key={i} className="p-4 space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-[#1a1814]/60">Line {i + 1}</span>
                  {lines.length > 1 && (
                    <button type="button" onClick={() => removeLine(i)} className="text-red-400">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                <select
                  value={line.product_id}
                  onChange={e => updateLine(i, { product_id: e.target.value })}
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]"
                >
                  <option value="">Select product…</option>
                  {products.map(p => (
                    <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
                  ))}
                </select>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-[#1a1814]/60 mb-1 block">Qty</label>
                    <input
                      type="number" min="0.001" step="any" value={line.qty}
                      onChange={e => updateLine(i, { qty: e.target.value })}
                      placeholder="0"
                      className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right focus:outline-none focus:border-[#b8943f]"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-[#1a1814]/60 mb-1 block">Declared Value</label>
                    <input
                      type="number" min="0" step="any" value={line.declared_value}
                      onChange={e => updateLine(i, { declared_value: e.target.value })}
                      className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right focus:outline-none focus:border-[#b8943f]"
                    />
                  </div>
                </div>
                <input
                  value={line.lot_no}
                  onChange={e => updateLine(i, { lot_no: e.target.value })}
                  placeholder="Lot No. (optional)"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#b8943f]"
                />
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
        )}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="flex-1 sm:flex-none bg-[#b8943f] text-white px-8 py-2.5 rounded-lg text-sm font-medium hover:bg-[#a07c32] disabled:opacity-50 transition-colors"
          >
            {saving ? "Saving…" : "Create GRN"}
          </button>
          <Link
            href="/manufacturing/grn"
            className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
