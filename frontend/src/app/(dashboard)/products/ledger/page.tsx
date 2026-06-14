"use client"

import { Suspense, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import { BookOpen, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"

interface Product {
  id: number
  name: string
  code: string | null
  product_type: string
}

interface StockLocation {
  id: number
  name: string
  code: string
}

interface LedgerItem {
  date: string
  direction: string
  qty_in: number
  qty_out: number
  running_qty: number
  unit_cost: number
  source: string
  location: string
}

interface LedgerData {
  product_id: number
  location_id: number | null
  items: LedgerItem[]
}

interface ProductsResponse {
  items: Product[]
}

interface LocationsResponse {
  items: StockLocation[]
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

function ProductLedgerInner() {
  const fmt = useFmt()
  const range = defaultRange()
  const searchParams = useSearchParams()

  const [products, setProducts] = useState<Product[]>([])
  const [locations, setLocations] = useState<StockLocation[]>([])
  const [productId, setProductId] = useState<string>(searchParams.get("product") ?? "")
  const [locationId, setLocationId] = useState<string>("")
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<LedgerData | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  // Load product and location lists on mount
  useEffect(() => {
    apiFetch<ProductsResponse>("/api/products?limit=500")
      .then(r => setProducts(r.items))
      .catch(() => {})
    apiFetch<LocationsResponse>("/api/stock-locations")
      .then(r => setLocations(r.items))
      .catch(() => {})
  }, [])

  // Fetch ledger when product changes
  useEffect(() => {
    if (!productId) {
      setData(null)
      return
    }
    setIsLoading(true)
    const params = new URLSearchParams({ product_id: productId })
    if (locationId) params.set("location_id", locationId)
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    apiFetch<LedgerData>(`/api/reports/product-ledger?${params.toString()}`)
      .then(d => { setData(d); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [productId, locationId, start, end])

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Product Ledger</h1>
          <p className="text-[#1a1814]/60">Stock movement history by product and store</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (!data?.items.length) return
              downloadCSV("product-ledger.csv", data.items.map(m => ({
                Date: m.date, Direction: m.direction, "Qty In": m.qty_in, "Qty Out": m.qty_out,
                "Running Qty": m.running_qty, "Unit Cost": m.unit_cost, Location: m.location, Source: m.source,
              })))
            }}
            disabled={!data?.items.length}
            className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 disabled:opacity-40"
            title="Export CSV"
          >
            <Download className="w-5 h-5" />
          </button>
          <BookOpen className="w-7 h-7 text-[#b8943f] hidden md:block" />
        </div>
      </div>

      {/* Filters */}
      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Product</label>
          <select
            value={productId}
            onChange={e => setProductId(e.target.value)}
            className="w-full border border-[#1a1814]/10 rounded-lg px-3 py-2 text-sm bg-[#f6f3ee] text-[#1a1814] focus:outline-none focus:border-[#b8943f]"
          >
            <option value="">— Select product —</option>
            {products.map(p => (
              <option key={p.id} value={String(p.id)}>
                {p.code ? `${p.code} · ` : ""}{p.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Store / Location</label>
          <select
            value={locationId}
            onChange={e => setLocationId(e.target.value)}
            className="w-full border border-[#1a1814]/10 rounded-lg px-3 py-2 text-sm bg-[#f6f3ee] text-[#1a1814] focus:outline-none focus:border-[#b8943f]"
          >
            <option value="">Consolidated (all stores)</option>
            {locations.map(l => (
              <option key={l.id} value={String(l.id)}>
                {l.code} · {l.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">From</label>
          <input
            type="date"
            value={start}
            onChange={e => setStart(e.target.value)}
            className="w-full border border-[#1a1814]/10 rounded-lg px-3 py-2 text-sm bg-[#f6f3ee] text-[#1a1814] focus:outline-none focus:border-[#b8943f]"
          />
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">To</label>
          <input
            type="date"
            value={end}
            onChange={e => setEnd(e.target.value)}
            className="w-full border border-[#1a1814]/10 rounded-lg px-3 py-2 text-sm bg-[#f6f3ee] text-[#1a1814] focus:outline-none focus:border-[#b8943f]"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[700px]">
            <thead>
              <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Date</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Direction</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Qty In</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Qty Out</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Running Qty</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Unit Cost</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Location</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1a1814]/5">
              {!productId ? (
                <tr>
                  <td colSpan={8} className="px-6 py-10 text-center text-[#1a1814]/50">
                    Select a product to view its movement ledger.
                  </td>
                </tr>
              ) : isLoading ? (
                <tr>
                  <td colSpan={8} className="px-6 py-10 text-center text-[#1a1814]/75">Loading...</td>
                </tr>
              ) : !data || data.items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-10 text-center text-[#1a1814]/75">
                    No movements found for the selected filters.
                  </td>
                </tr>
              ) : (
                data.items.map((item, idx) => (
                  <tr key={idx} className="hover:bg-[#f6f3ee]/30 transition-colors">
                    <td className="ui-td text-sm text-[#1a1814]/70">{item.date}</td>
                    <td className="ui-td">
                      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-[#b8943f]/10 text-[#b8943f]">
                        {item.direction}
                      </span>
                    </td>
                    <td className="ui-td text-right font-mono text-sm text-green-700">
                      {Number(item.qty_in) > 0 ? item.qty_in : "—"}
                    </td>
                    <td className="ui-td text-right font-mono text-sm text-red-600">
                      {Number(item.qty_out) > 0 ? item.qty_out : "—"}
                    </td>
                    <td className="ui-td text-right font-mono text-sm font-semibold text-[#1a1814]">
                      {item.running_qty}
                    </td>
                    <td className="ui-td text-right font-mono text-sm text-[#1a1814]/70">
                      {Number(item.unit_cost) > 0 ? fmt(item.unit_cost) : "—"}
                    </td>
                    <td className="ui-td text-sm text-[#1a1814]/70">{item.location || "—"}</td>
                    <td className="ui-td text-sm text-[#1a1814]/60">{item.source || "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default function ProductLedgerPage() {
  return (
    <Suspense fallback={null}>
      <ProductLedgerInner />
    </Suspense>
  )
}
