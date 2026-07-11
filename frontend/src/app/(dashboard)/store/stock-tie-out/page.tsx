"use client"

import { useEffect, useState } from "react"
import { CheckCheck } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"

interface Product {
  id: number
  code?: string
  name: string
}

interface StockTieOutRow {
  product_id: number
  product_name: string
  opening_qty: number | string
  received_qty: number | string
  issued_qty: number | string
  expected_closing: number | string | null
  actual_closing: number | string | null
  variance: number | string | null
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

export default function StockTieOutPage() {
  const fmt = useFmt()
  const range = defaultRange()

  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [productId, setProductId] = useState("")
  const [products, setProducts] = useState<Product[]>([])
  const [rows, setRows] = useState<StockTieOutRow[] | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    apiFetch<{ items: Product[] }>("/api/products?product_type=stock&limit=500")
      .then(d => setProducts(d.items))
      .catch(() => setProducts([]))
  }, [])

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams()
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    if (productId) params.set("product_id", productId)
    apiFetch<StockTieOutRow[]>(`/api/store-reports/stock-tie-out?${params.toString()}`)
      .then(d => { setRows(d); setIsLoading(false) })
      .catch(() => { setRows([]); setIsLoading(false) })
  }, [start, end, productId])

  const printSubtitle = `Period: ${start} – ${end}`

  return (
    <div className="max-w-6xl mx-auto p-4">
      <PrintHeader title="Stock Tie-Out" subtitle={printSubtitle} orientation="landscape" />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Stock Tie-Out</h1>
          <p className="text-[var(--text-primary)]/60">
            Opening + received − issued reconciled against live stock. Reconciliation columns are only available
            when no end date is set (a truncated window cannot be compared against live stock).
          </p>
        </div>
        <CheckCheck className="w-7 h-7 text-[var(--primary)] hidden md:block" />
      </div>

      {/* Filters */}
      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl grid grid-cols-1 md:grid-cols-3 gap-4 print:hidden">
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">From</label>
          <input
            type="date"
            value={start}
            onChange={e => setStart(e.target.value)}
            className="w-full border border-[var(--text-primary)]/10 rounded-lg px-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">To</label>
          <input
            type="date"
            value={end}
            onChange={e => setEnd(e.target.value)}
            className="w-full border border-[var(--text-primary)]/10 rounded-lg px-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Product</label>
          <select
            value={productId}
            onChange={e => setProductId(e.target.value)}
            className="w-full border border-[var(--text-primary)]/10 rounded-lg px-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
          >
            <option value="">All Products</option>
            {products.map(p => (
              <option key={p.id} value={p.id}>{p.code ? `${p.code} — ${p.name}` : p.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="table-freeze freeze-col">
          <table className="w-full text-left border-collapse min-w-[1000px]">
            <thead>
              <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Product</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Opening</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Received</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Issued</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Expected Closing</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Actual Closing</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Variance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-[var(--text-primary)]/75">Loading...</td>
                </tr>
              ) : !rows || rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-[var(--text-primary)]/75">
                    No stock-tracked products found for the selected filters.
                  </td>
                </tr>
              ) : (
                rows.map(row => {
                  const variance = row.variance === null || row.variance === undefined ? null : Number(row.variance)
                  const hasVariance = variance !== null && variance !== 0
                  return (
                    <tr key={row.product_id} className="hover:bg-[var(--bg-page)]/30 transition-colors">
                      <td className="ui-td text-sm text-[var(--text-primary)]">{row.product_name}</td>
                      <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(Number(row.opening_qty))}</td>
                      <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(Number(row.received_qty))}</td>
                      <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(Number(row.issued_qty))}</td>
                      <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">
                        {row.expected_closing === null || row.expected_closing === undefined ? "—" : fmt(Number(row.expected_closing))}
                      </td>
                      <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">
                        {row.actual_closing === null || row.actual_closing === undefined ? "—" : fmt(Number(row.actual_closing))}
                      </td>
                      <td className={`ui-td text-right font-mono text-sm whitespace-nowrap font-semibold ${hasVariance ? "text-red-600" : "text-[var(--text-primary)]/70"}`}>
                        {variance === null ? "—" : `${variance > 0 ? "+" : ""}${fmt(variance)}`}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
