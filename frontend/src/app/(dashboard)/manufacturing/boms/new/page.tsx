"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Plus, Trash2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

interface Product { id: number; code: string; name: string }
interface StockLocation { id: number; code: string; name: string; type: string }

interface LineState {
  component_product_id: string
  qty_per_output: string
  source: string
  default_location_id: string
  is_optional: boolean
  notes: string
}

const emptyLine = (): LineState => ({
  component_product_id: "", qty_per_output: "", source: "own_stock",
  default_location_id: "", is_optional: false, notes: "",
})

export default function NewBomPage() {
  const { t } = useTranslation()

  const router = useRouter()

  const [products, setProducts]     = useState<Product[]>([])
  const [locations, setLocations]   = useState<StockLocation[]>([])
  const [loadErr, setLoadErr]       = useState<string | null>(null)

  const [outputProductId, setOutputProductId]       = useState("")
  const [outputQty, setOutputQty]                   = useState("1")
  const [description, setDescription]               = useState("")
  const [explodeOnInvoice, setExplodeOnInvoice]     = useState(false)
  const [lines, setLines]                           = useState<LineState[]>([emptyLine()])

  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<{ items: Product[] }>("/api/products?limit=500"),
      apiFetch<{ items: StockLocation[] }>("/api/stock-locations"),
    ])
      .then(([p, l]) => { setProducts(p.items); setLocations(l.items) })
      .catch(() => setLoadErr("Failed to load products / locations"))
  }, [])

  const updateLine = (i: number, patch: Partial<LineState>) =>
    setLines(prev => prev.map((l, idx) => idx === i ? { ...l, ...patch } : l))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!outputProductId)      { setError("Output product is required"); return }
    const oQty = parseFloat(outputQty)
    if (isNaN(oQty) || oQty <= 0) { setError("Output qty must be > 0"); return }
    const validLines = lines.filter(l => l.component_product_id && parseFloat(l.qty_per_output) > 0)
    if (!validLines.length)    { setError("At least one component line is required"); return }

    setSaving(true); setError(null)
    try {
      const res = await apiFetch<{ id: number }>("/api/bom", {
        method: "POST",
        body: JSON.stringify({
          output_product_id: parseInt(outputProductId),
          output_qty:        oQty,
          explode_on_invoice: explodeOnInvoice,
          description:       description.trim() || undefined,
          lines: validLines.map(l => ({
            component_product_id: parseInt(l.component_product_id),
            qty_per_output:       parseFloat(l.qty_per_output),
            source:               l.source,
            default_location_id:  l.default_location_id ? parseInt(l.default_location_id) : undefined,
            is_optional:          l.is_optional,
            notes:                l.notes.trim() || undefined,
          })),
        }),
      })
      router.push("/manufacturing/boms")
      void res
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save BOM")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <Link href="/manufacturing/boms" className="text-sm text-[#b8943f] hover:underline">
          ← Bills of Material
        </Link>
        <h1 className="text-2xl font-serif font-semibold text-[#1a1814] mt-2">New Bill of Material</h1>
        <p className="text-sm text-[#1a1814]/60 mt-0.5">Define which components produce one batch of output.</p>
      </div>

      {loadErr && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 rounded-xl px-4 py-3 text-sm">{loadErr}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Output product */}
        <div className="bg-white border border-[#ede9e2] rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-[#1a1814]">Output (Finished Good)</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">{t('col.product', 'Product')}</label>
              <select value={outputProductId} onChange={e => setOutputProductId(e.target.value)}
                className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]">
                <option value="">Select output product…</option>
                {products.map(p => (
                  <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Output Qty per batch</label>
              <input type="number" min="0.001" step="any" value={outputQty}
                onChange={e => setOutputQty(e.target.value)}
                className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right tabular-nums focus:outline-none focus:border-[#b8943f]" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">{t('col.description', 'Description')}</label>
            <input value={description} onChange={e => setDescription(e.target.value)}
              placeholder="Optional description / version note"
              className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]" />
          </div>
          <label className="flex items-start gap-3 cursor-pointer p-3 bg-amber-50 border border-amber-100 rounded-lg">
            <input type="checkbox" checked={explodeOnInvoice} onChange={e => setExplodeOnInvoice(e.target.checked)}
              className="mt-0.5 w-4 h-4 accent-[#b8943f]" />
            <span className="text-sm text-[#1a1814]">
              <span className="font-semibold">Auto-consume components on sale invoice</span>
              <span className="block text-xs text-[#1a1814]/60 mt-0.5">When enabled, posting an invoice for this product automatically consumes its BOM components from stock instead of the finished product itself. Use for kit / assembly-to-order products.</span>
            </span>
          </label>
        </div>

        {/* Component lines */}
        <div className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-[#ede9e2] flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[#1a1814]">Component Lines</h2>
            <button type="button" onClick={() => setLines(prev => [...prev, emptyLine()])}
              className="inline-flex items-center gap-1.5 text-xs text-[#b8943f] hover:underline">
              <Plus className="w-3.5 h-3.5" /> Add component
            </button>
          </div>
          <div className="overflow-x-auto hidden sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#ede9e2] bg-[#faf8f4]">
                  <th className="text-left px-4 py-2.5 font-semibold text-[#1a1814]/70">Component Product</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-[#1a1814]/70 w-24">Qty / batch</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-[#1a1814]/70 w-36">Source</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-[#1a1814]/70 w-36">Default Location</th>
                  <th className="text-center px-3 py-2.5 font-semibold text-[#1a1814]/70 w-20">Optional?</th>
                  <th className="w-8 px-2" />
                </tr>
              </thead>
              <tbody>
                {lines.map((line, i) => (
                  <tr key={i} className="border-b border-[#ede9e2] last:border-0">
                    <td className="px-4 py-2">
                      <select value={line.component_product_id}
                        onChange={e => updateLine(i, { component_product_id: e.target.value })}
                        className="w-full border border-[#d4cfc7] rounded px-2 py-1.5 text-xs focus:outline-none focus:border-[#b8943f]">
                        <option value="">Select…</option>
                        {products.map(p => (
                          <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <input type="number" min="0.001" step="any" value={line.qty_per_output}
                        onChange={e => updateLine(i, { qty_per_output: e.target.value })}
                        placeholder="1"
                        className="w-full border border-[#d4cfc7] rounded px-2 py-1.5 text-xs text-right tabular-nums focus:outline-none focus:border-[#b8943f]" />
                    </td>
                    <td className="px-3 py-2">
                      <select value={line.source} onChange={e => updateLine(i, { source: e.target.value })}
                        className="w-full border border-[#d4cfc7] rounded px-2 py-1.5 text-xs focus:outline-none focus:border-[#b8943f]">
                        <option value="own_stock">Own stock</option>
                        <option value="customer_supplied">Customer supplied</option>
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <select value={line.default_location_id}
                        onChange={e => updateLine(i, { default_location_id: e.target.value })}
                        className="w-full border border-[#d4cfc7] rounded px-2 py-1.5 text-xs focus:outline-none focus:border-[#b8943f]">
                        <option value="">Auto</option>
                        {locations.map(l => (
                          <option key={l.id} value={l.id}>{l.code}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <input type="checkbox" checked={line.is_optional}
                        onChange={e => updateLine(i, { is_optional: e.target.checked })}
                        className="w-4 h-4 accent-[#b8943f]" />
                    </td>
                    <td className="px-2 py-2 text-right">
                      {lines.length > 1 && (
                        <button type="button" onClick={() => setLines(prev => prev.filter((_, idx) => idx !== i))}
                          className="text-[#1a1814]/30 hover:text-red-500 transition-colors">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile stacked */}
          <div className="sm:hidden divide-y divide-[#ede9e2]">
            {lines.map((line, i) => (
              <div key={i} className="p-4 space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-[#1a1814]/60">Component {i + 1}</span>
                  {lines.length > 1 && (
                    <button type="button" onClick={() => setLines(prev => prev.filter((_, idx) => idx !== i))}
                      className="text-red-400"><Trash2 className="w-3.5 h-3.5" /></button>
                  )}
                </div>
                <select value={line.component_product_id}
                  onChange={e => updateLine(i, { component_product_id: e.target.value })}
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]">
                  <option value="">Select product…</option>
                  {products.map(p => (
                    <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
                  ))}
                </select>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-[#1a1814]/60 mb-1 block">Qty / batch</label>
                    <input type="number" min="0.001" step="any" value={line.qty_per_output}
                      onChange={e => updateLine(i, { qty_per_output: e.target.value })}
                      className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm text-right focus:outline-none focus:border-[#b8943f]" />
                  </div>
                  <div>
                    <label className="text-xs text-[#1a1814]/60 mb-1 block">Source</label>
                    <select value={line.source} onChange={e => updateLine(i, { source: e.target.value })}
                      className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]">
                      <option value="own_stock">Own stock</option>
                      <option value="customer_supplied">Customer supplied</option>
                    </select>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
        )}

        <div className="flex gap-3">
          <button type="submit" disabled={saving}
            className="flex-1 sm:flex-none bg-[#b8943f] text-white px-8 py-2.5 rounded-lg text-sm font-medium hover:bg-[#a07c32] disabled:opacity-50 transition-colors">
            {saving ? "Saving…" : "Create BOM"}
          </button>
          <Link href="/manufacturing/boms"
            className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors">{t('common.cancel', 'Cancel')}</Link>
        </div>
      </form>
    </div>
  )
}
