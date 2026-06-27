"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft, Pencil, Package, BarChart2, BookOpen,
  FileText, TrendingDown, TrendingUp, AlertTriangle, ClipboardCheck,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { useTranslation } from "react-i18next"

interface Product {
  id: number
  code: string | null
  name: string
  unit: string
  product_type: string
  default_rate: number
  stock_qty: number
  avg_cost: number
  reorder_level: number
  is_active: boolean
  is_deferred: boolean
  recognition_months: number
  hs_code: string | null
  category_id: number | null
  cost_method: string | null
}

interface CostLayer {
  id: number
  qty_received: string
  qty_remaining: string
  unit_cost: string
  lot_no: string | null
  source_doc: string | null
  created_at: string | null
}

interface Bom {
  id: number
  version: number
  is_active: boolean
  explode_on_invoice: boolean
  output_qty: string
  description: string | null
  lines: { id: number }[]
}

export default function ProductHubPage() {
  const { t } = useTranslation()

  const params = useParams()
  const id = params.id as string
  const fmt = useFmt()

  const [product, setProduct] = useState<Product | null>(null)
  const [boms, setBoms]       = useState<Bom[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  // Cost layers
  const [layers, setLayers]           = useState<CostLayer[] | null>(null)
  const [layersOpen, setLayersOpen]   = useState(false)
  const [layersLoading, setLayersLoading] = useState(false)

  const loadLayers = () => {
    if (layers !== null) { setLayersOpen(true); return }
    setLayersLoading(true)
    apiFetch<CostLayer[]>(`/api/products/${id}/layers`)
      .then(d => { setLayers(d); setLayersOpen(true) })
      .catch(() => {})
      .finally(() => setLayersLoading(false))
  }

  // Stock adjustment modal
  const [adjOpen, setAdjOpen]     = useState(false)
  const [adjQty, setAdjQty]       = useState("")
  const [adjDate, setAdjDate]     = useState(() => new Date().toISOString().slice(0, 10))
  const [adjNotes, setAdjNotes]   = useState("")
  const [adjBusy, setAdjBusy]     = useState(false)
  const [adjResult, setAdjResult] = useState<{ jv_number: string; message: string } | null>(null)
  const [adjErr, setAdjErr]       = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<Product>(`/api/products/${id}`),
      apiFetch<{ total: number; items: Bom[] }>(`/api/bom?output_product_id=${id}&limit=10`),
    ])
      .then(([p, b]) => { setProduct(p); setBoms(b.items) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [id])

  const submitAdjustment = async () => {
    if (!adjQty || isNaN(Number(adjQty))) { setAdjErr("Enter a valid counted quantity"); return }
    setAdjBusy(true); setAdjErr(null); setAdjResult(null)
    try {
      const res = await apiFetch<{ jv_number: string; message: string }>(
        `/api/products/${id}/adjust-stock`,
        { method: "POST", body: JSON.stringify({ counted_qty: Number(adjQty), date: adjDate, notes: adjNotes || null }) }
      )
      setAdjResult(res)
      // Refresh product data to show updated stock qty
      const updated = await apiFetch<Product>(`/api/products/${id}`)
      setProduct(updated)
    } catch (e) {
      setAdjErr(e instanceof Error ? e.message : "Adjustment failed")
    } finally { setAdjBusy(false) }
  }

  if (loading) return <div className="p-8 text-sm text-[var(--text-primary)]/50 text-center">Loading…</div>
  if (error)   return <div className="p-8 text-sm text-red-600">{error}</div>
  if (!product) return null

  const isStock    = product.product_type === "stock"
  const stockValue = product.stock_qty * product.avg_cost
  const lowStock   = isStock && product.stock_qty <= product.reorder_level && product.stock_qty > 0
  const outOfStock = isStock && product.stock_qty <= 0
  const activeBom  = boms.find(b => b.is_active)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Link href="/products" className="text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">{product.name}</h1>
            <p className="text-sm text-[var(--text-primary)]/55 mt-0.5 flex items-center gap-2">
              <span className="capitalize">{product.product_type}</span>
              {product.code && <span className="font-mono text-xs bg-[#f0ede6] px-1.5 py-0.5 rounded">{product.code}</span>}
              {product.hs_code && <span className="text-xs text-[var(--text-primary)]/40">HS: {product.hs_code}</span>}
            </p>
          </div>
          {!product.is_active && (
            <span className="inline-block bg-slate-100 text-slate-500 text-xs font-medium px-2.5 py-0.5 rounded-full border border-slate-200">{t('status.inactive', 'Inactive')}</span>
          )}
        </div>
        <Link
          href={`/products/${id}/edit`}
          className="inline-flex items-center gap-2 border border-[var(--border)] px-3 py-2 rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors"
        >
          <Pencil className="w-4 h-4" /> Edit
        </Link>
      </div>

      {/* Stock status cards (stock products only) */}
      {isStock && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className={`bg-white border rounded-xl p-4 text-center ${outOfStock ? "border-red-200 bg-red-50/30" : lowStock ? "border-amber-200 bg-amber-50/30" : "border-[var(--border)]"}`}>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">On Hand</p>
            <p className={`text-xl font-bold tabular-nums ${outOfStock ? "text-red-600" : lowStock ? "text-amber-700" : "text-[var(--text-primary)]"}`}>
              {Number(product.stock_qty).toFixed(3)} {product.unit}
            </p>
            {outOfStock && <p className="text-xs text-red-500 mt-0.5">Out of stock</p>}
            {lowStock   && <p className="text-xs text-amber-600 mt-0.5">Below reorder level</p>}
          </div>
          <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">Avg Cost</p>
            <p className="text-xl font-bold tabular-nums text-[var(--text-primary)]">{fmt(product.avg_cost)}</p>
          </div>
          <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">Stock Value</p>
            <p className="text-xl font-bold tabular-nums text-[var(--text-primary)]">{fmt(stockValue)}</p>
          </div>
          <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">Sale Price</p>
            <p className="text-xl font-bold tabular-nums text-[var(--text-primary)]">{fmt(product.default_rate)}</p>
          </div>
        </div>
      )}

      {/* Service product summary */}
      {!isStock && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">Default Rate</p>
            <p className="text-xl font-bold tabular-nums text-[var(--text-primary)]">{fmt(product.default_rate)}</p>
          </div>
          {product.is_deferred && (
            <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
              <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">Recognition</p>
              <p className="text-xl font-bold text-[var(--text-primary)]">{product.recognition_months} months</p>
            </div>
          )}
        </div>
      )}

      {/* Low-stock alert */}
      {outOfStock && (
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          Stock is at zero. Create a Bill or GRN to restock.
        </div>
      )}
      {lowStock && (
        <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          Stock is below the reorder level of {Number(product.reorder_level).toFixed(3)} {product.unit}.
        </div>
      )}

      {/* Active BOM banner */}
      {activeBom && (
        <div className="flex items-center gap-3 bg-violet-50 border border-violet-200 rounded-xl px-4 py-3 text-sm text-violet-800">
          <Package className="w-4 h-4 shrink-0" />
          <span>
            Active BOM v{activeBom.version} · {activeBom.lines.length} component{activeBom.lines.length !== 1 ? "s" : ""}
            {activeBom.explode_on_invoice && <span className="ml-2 bg-amber-100 text-amber-800 text-xs font-medium px-1.5 py-0.5 rounded">Kit — auto-consumes on invoice</span>}
          </span>
          <Link href="/manufacturing/boms" className="ml-auto text-xs text-violet-600 hover:underline">View BOMs</Link>
        </div>
      )}

      {/* Quick links */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {isStock && (
          <Link
            href={`/products/${id}/stock-card`}
            className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
          >
            <BarChart2 className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
            <span className="text-sm font-medium text-[var(--text-primary)]">Stock Card</span>
          </Link>
        )}
        <Link
          href={`/products/ledger?product=${id}`}
          className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
        >
          <BookOpen className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">Ledger</span>
        </Link>
        <Link
          href={`/invoices/new`}
          className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
        >
          <TrendingUp className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">New Invoice</span>
        </Link>
        {isStock && (
          <Link
            href={`/bills/new`}
            className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
          >
            <TrendingDown className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
            <span className="text-sm font-medium text-[var(--text-primary)]">New Bill</span>
          </Link>
        )}
        {boms.length > 0 && (
          <Link
            href="/manufacturing/boms"
            className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
          >
            <FileText className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
            <span className="text-sm font-medium text-[var(--text-primary)]">BOMs ({boms.length})</span>
          </Link>
        )}
        {isStock && (
          <button
            onClick={() => { setAdjOpen(true); setAdjResult(null); setAdjErr(null); setAdjQty(String(product.stock_qty)) }}
            className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
          >
            <ClipboardCheck className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
            <span className="text-sm font-medium text-[var(--text-primary)]">Adjust Stock</span>
          </button>
        )}
      </div>

      {/* Stock adjustment modal */}
      {adjOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={e => { if (e.target === e.currentTarget) setAdjOpen(false) }}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h2 className="text-xl font-bold text-[var(--text-primary)]">Physical Count — Adjust Stock</h2>
            <p className="text-sm text-[var(--text-primary)]/60">
              Enter the physically counted quantity. If it differs from the system ({Number(product.stock_qty).toFixed(3)} {product.unit}), a variance journal entry will be posted automatically.
            </p>

            {adjResult ? (
              <div className="space-y-3">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-xl px-4 py-3 text-sm">
                  <p className="font-semibold">{adjResult.message}</p>
                  <p className="text-xs mt-0.5 text-emerald-700">JV: {adjResult.jv_number}</p>
                </div>
                <button onClick={() => setAdjOpen(false)} className="w-full bg-[var(--primary)] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[var(--primary-dark)]">
                  Done
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/65 uppercase tracking-wide mb-1">Counted Quantity ({product.unit})</label>
                  <input
                    type="number"
                    step="0.001"
                    value={adjQty}
                    onChange={e => setAdjQty(e.target.value)}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                    placeholder="0.000"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/65 uppercase tracking-wide mb-1">Count Date</label>
                  <input
                    type="date"
                    value={adjDate}
                    onChange={e => setAdjDate(e.target.value)}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/65 uppercase tracking-wide mb-1">Notes (optional)</label>
                  <input
                    type="text"
                    value={adjNotes}
                    onChange={e => setAdjNotes(e.target.value)}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                    placeholder="Reason for adjustment…"
                  />
                </div>
                {adjErr && <p className="text-xs text-red-600">{adjErr}</p>}
                <div className="flex gap-2 pt-1">
                  <button onClick={() => setAdjOpen(false)} className="flex-1 border border-[var(--border)] py-2.5 rounded-lg text-sm text-[var(--text-primary)]/60 hover:bg-[var(--bg-page)]">{t('common.cancel', 'Cancel')}</button>
                  <button onClick={submitAdjustment} disabled={adjBusy} className="flex-1 bg-[var(--primary)] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[var(--primary-dark)] disabled:opacity-50">
                    {adjBusy ? "Posting…" : "Post Adjustment"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Product details card */}
      <div className="bg-white border border-[var(--border)] rounded-xl p-5 grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-4 text-sm">
        <div>
          <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">Type</p>
          <p className="capitalize font-medium text-[var(--text-primary)]">{product.product_type}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">{t('col.unit', 'Unit')}</p>
          <p className="font-medium text-[var(--text-primary)]">{product.unit}</p>
        </div>
        {product.code && (
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">SKU / Code</p>
            <p className="font-mono text-[var(--text-primary)]">{product.code}</p>
          </div>
        )}
        {product.hs_code && (
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">HS Code (FBR)</p>
            <p className="font-mono text-[var(--text-primary)]">{product.hs_code}</p>
          </div>
        )}
        {isStock && (
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">Reorder Level</p>
            <p className="tabular-nums text-[var(--text-primary)]">{Number(product.reorder_level).toFixed(3)} {product.unit}</p>
          </div>
        )}
        {product.is_deferred && (
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">Revenue Recognition</p>
            <p className="text-[var(--text-primary)]">Deferred · {product.recognition_months} months</p>
          </div>
        )}
        {isStock && (
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">Cost Method</p>
            <p className="font-medium text-[var(--text-primary)]">
              {product.cost_method === 'fifo' ? 'FIFO (per-product)' : product.cost_method === 'wavg' ? 'WAvg (per-product)' : 'Inherit from company'}
            </p>
          </div>
        )}
      </div>

      {/* FIFO cost layers — available for all stock products */}
      {isStock && (
        <div className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
          <button
            onClick={() => layersOpen ? setLayersOpen(false) : loadLayers()}
            className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-page)] transition-colors"
          >
            <span>Cost Layers (FIFO view)</span>
            <span className="text-xs text-[var(--text-primary)]/40">{layersOpen ? '▲ Hide' : '▼ Show open layers'}</span>
          </button>
          {layersOpen && (
            <div className="border-t border-[var(--border)]">
              {layersLoading ? (
                <p className="px-5 py-4 text-sm text-[var(--text-primary)]/40">Loading…</p>
              ) : !layers || layers.length === 0 ? (
                <p className="px-5 py-4 text-sm text-[var(--text-primary)]/40">No open cost layers. Receive stock via a Bill or GRN first.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-[var(--bg-page)]">
                    <tr>
                      <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Received</th>
                      <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Source</th>
                      <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Lot</th>
                      <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Qty Received</th>
                      <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Qty Remaining</th>
                      <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Unit Cost</th>
                      <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Layer Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {layers.map(l => {
                      const remaining = parseFloat(l.qty_remaining)
                      const cost = parseFloat(l.unit_cost)
                      return (
                        <tr key={l.id} className="hover:bg-[var(--bg-page)]/50">
                          <td className="ui-td whitespace-nowrap text-[var(--text-muted)]">{l.created_at ? l.created_at.split('T')[0] : '—'}</td>
                          <td className="ui-td font-mono text-xs text-[var(--primary)]">{l.source_doc ?? '—'}</td>
                          <td className="ui-td text-[var(--text-muted)]">{l.lot_no ?? '—'}</td>
                          <td className="ui-td text-right font-mono">{parseFloat(l.qty_received).toFixed(3)}</td>
                          <td className="ui-td text-right font-mono font-semibold">{remaining.toFixed(3)}</td>
                          <td className="ui-td text-right font-mono">{fmt(cost)}</td>
                          <td className="ui-td text-right font-mono">{fmt(remaining * cost)}</td>
                        </tr>
                      )
                    })}
                    <tr className="bg-[var(--bg-page)] font-semibold">
                      <td colSpan={4} className="ui-td text-right text-xs uppercase tracking-widest text-[var(--text-muted)]">{t('col.total', 'Total')}</td>
                      <td className="ui-td text-right font-mono">
                        {layers.reduce((s, l) => s + parseFloat(l.qty_remaining), 0).toFixed(3)}
                      </td>
                      <td className="ui-td" />
                      <td className="ui-td text-right font-mono">
                        {fmt(layers.reduce((s, l) => s + parseFloat(l.qty_remaining) * parseFloat(l.unit_cost), 0))}
                      </td>
                    </tr>
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
