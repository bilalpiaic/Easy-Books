"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeftRight, ChevronLeft, ChevronRight, Download } from "lucide-react"
import PrintHeader from "@/components/PrintHeader"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import { useTranslation } from "react-i18next"

interface Movement {
  id: number
  occurred_at: string
  product_id: number
  direction: string
  qty: string
  from_location_id: number | null
  to_location_id: number | null
  lot_no: string | null
  owner_customer_id: number | null
  unit_cost: string
  total_cost: string
  source_doc_type: string | null
  source_doc_id: number | null
  posted_to_gl: boolean
  notes: string | null
}

interface Product      { id: number; code: string; name: string }
interface Location     { id: number; code: string; name: string }
interface Customer     { id: number; name: string }

const PAGE_SIZE = 100

const DIRECTION_TONE: Record<string, string> = {
  RECEIPT:             "bg-emerald-50 text-emerald-800 border-emerald-200",
  CUSTODIAL_RECEIPT:   "bg-sky-50 text-sky-800 border-sky-200",
  ISSUE:               "bg-red-50 text-red-800 border-red-200",
  CUSTODIAL_ISSUE:     "bg-orange-50 text-orange-800 border-orange-200",
  COMPLETION:          "bg-violet-50 text-violet-800 border-violet-200",
  CUSTODIAL_COMPLETION:"bg-purple-50 text-purple-800 border-purple-200",
  DELIVERY:            "bg-teal-50 text-teal-800 border-teal-200",
  SHIPMENT:            "bg-blue-50 text-blue-800 border-blue-200",
  ADJUSTMENT:          "bg-amber-50 text-amber-800 border-amber-200",
}

function sourceLink(docType: string | null, docId: number | null): { href: string; label: string } | null {
  if (!docType || !docId) return null
  switch (docType) {
    case "bill":             return { href: `/bills/${docId}`,                                label: `Bill #${docId}` }
    case "invoice":          return { href: `/invoices/${docId}`,                             label: `Invoice #${docId}` }
    case "grn":              return { href: `/manufacturing/grn/${docId}`,                    label: `GRN #${docId}` }
    case "production_order": return { href: `/manufacturing/production-orders/${docId}`,      label: `PO #${docId}` }
    default:                 return { href: "#",                                              label: `${docType} #${docId}` }
  }
}

export default function StockMovementsPage() {
  const { t } = useTranslation()

  const fmt = useFmt()

  const [movements, setMovements] = useState<Movement[]>([])
  const [total, setTotal]         = useState(0)
  const [page, setPage]           = useState(0)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)

  const [productMap, setProductMap]   = useState<Map<number, Product>>(new Map())
  const [locationMap, setLocationMap] = useState<Map<number, Location>>(new Map())
  const [customerMap, setCustomerMap] = useState<Map<number, Customer>>(new Map())

  // Filters
  const [filterProduct,  setFilterProduct]  = useState("")
  const [filterLocation, setFilterLocation] = useState("")
  const [filterDir,      setFilterDir]      = useState("")

  // Populate dropdown options from lookup tables
  const [products,  setProducts]  = useState<Product[]>([])
  const [locations, setLocations] = useState<Location[]>([])

  useEffect(() => {
    Promise.all([
      apiFetch<{ items: Product[] }>("/api/products?limit=500"),
      apiFetch<{ total: number; items: Location[] }>("/api/stock-locations?limit=200"),
      apiFetch<{ items: Customer[] }>("/api/customers?limit=500"),
    ]).then(([p, l, c]) => {
      setProducts(p.items)
      setProductMap(new Map(p.items.map(x => [x.id, x])))
      setLocations(l.items)
      setLocationMap(new Map(l.items.map(x => [x.id, x])))
      setCustomerMap(new Map(c.items.map(x => [x.id, x])))
    }).catch(() => {})
  }, [])

  const load = (pg: number) => {
    setLoading(true)
    const params = new URLSearchParams({ skip: String(pg * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (filterProduct)  params.set("product_id",  filterProduct)
    if (filterLocation) params.set("location_id", filterLocation)
    if (filterDir)      params.set("direction",   filterDir)
    apiFetch<{ total: number; items: Movement[] }>(`/api/stock-locations/movements?${params}`)
      .then(d => { setMovements(d.items); setTotal(d.total) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { setPage(0); load(0) },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filterProduct, filterLocation, filterDir])

  useEffect(() => { load(page) },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [page])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="space-y-5">
      <PrintHeader title="Stock Movements" orientation="landscape" />

      <header className="flex items-start justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <Link href="/manufacturing/stock-locations" className="text-sm text-[var(--primary)] hover:underline">
            ← Stock Locations
          </Link>
        </div>
        <button
          onClick={() => downloadCSV('stock-movements.csv', movements.map(m => ({ Date: m.occurred_at.slice(0, 10), Direction: m.direction, Product: productMap.get(m.product_id)?.name ?? m.product_id, Lot: m.lot_no ?? '', Qty: m.qty, "From": m.from_location_id ? (locationMap.get(m.from_location_id)?.name ?? m.from_location_id) : '', "To": m.to_location_id ? (locationMap.get(m.to_location_id)?.name ?? m.to_location_id) : '', "Unit Cost": m.unit_cost, "Total Cost": m.total_cost, Source: m.source_doc_type ? `${m.source_doc_type} #${m.source_doc_id}` : '' })))}
          disabled={movements.length === 0}
          className="inline-flex items-center gap-2 px-3 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
        >
          <Download className="w-4 h-4" /> CSV
        </button>
      </header>

      <div className="flex items-center gap-3">
        <ArrowLeftRight className="w-7 h-7 text-[var(--primary)]" />
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Stock Movements</h1>
          <p className="text-sm text-[var(--text-primary)]/60">All inventory movement events across all locations.</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 print:hidden">
        <select value={filterProduct} onChange={e => setFilterProduct(e.target.value)}
          className="border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-[var(--primary)]">
          <option value="">All products</option>
          {products.map(p => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}
        </select>
        <select value={filterLocation} onChange={e => setFilterLocation(e.target.value)}
          className="border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-[var(--primary)]">
          <option value="">All locations</option>
          {locations.map(l => <option key={l.id} value={l.id}>{l.code} — {l.name}</option>)}
        </select>
        <select value={filterDir} onChange={e => setFilterDir(e.target.value)}
          className="border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-[var(--primary)]">
          <option value="">All directions</option>
          {Object.keys(DIRECTION_TONE).map(d => <option key={d} value={d}>{d.replace(/_/g, " ")}</option>)}
        </select>
        {(filterProduct || filterLocation || filterDir) && (
          <button onClick={() => { setFilterProduct(""); setFilterLocation(""); setFilterDir("") }}
            className="text-sm text-[var(--text-primary)]/50 hover:text-[var(--text-primary)] underline">
            Clear filters
          </button>
        )}
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)] text-[var(--text-primary)]/70 text-xs uppercase tracking-wide">
            <tr>
              <th className="text-left px-4 py-2">Date</th>
              <th className="text-left px-4 py-2">Direction</th>
              <th className="text-left px-4 py-2">{t('col.product', 'Product')}</th>
              <th className="text-right px-4 py-2">Qty</th>
              <th className="text-left px-4 py-2">From</th>
              <th className="text-left px-4 py-2">To</th>
              <th className="text-right px-4 py-2">Unit cost</th>
              <th className="text-right px-4 py-2">{t('col.total', 'Total')}</th>
              <th className="text-left px-4 py-2">Source</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-[var(--text-primary)]/40 text-sm">Loading…</td></tr>
            ) : movements.length === 0 ? (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-[var(--text-primary)]/40 text-sm">No movements found.</td></tr>
            ) : movements.map(m => {
              const prod  = productMap.get(m.product_id)
              const from  = m.from_location_id ? locationMap.get(m.from_location_id) : null
              const to    = m.to_location_id   ? locationMap.get(m.to_location_id)   : null
              const cust  = m.owner_customer_id ? customerMap.get(m.owner_customer_id) : null
              const src   = sourceLink(m.source_doc_type, m.source_doc_id)
              const tone  = DIRECTION_TONE[m.direction] ?? "bg-slate-50 text-slate-700 border-slate-200"
              return (
                <tr key={m.id} className="border-t border-[var(--border)] hover:bg-[#faf8f4]">
                  <td className="px-4 py-2.5 tabular-nums text-[var(--text-primary)]/70 whitespace-nowrap">
                    {m.occurred_at.slice(0, 10)}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-block border rounded-full px-2 py-0.5 text-[10px] font-semibold ${tone}`}>
                      {m.direction.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    {prod ? (
                      <div>
                        <span className="font-medium text-[var(--text-primary)]">{prod.name}</span>
                        <span className="text-xs text-[var(--text-primary)]/50 ml-1.5 font-mono">{prod.code}</span>
                      </div>
                    ) : <span className="text-[var(--text-primary)]/40">#{m.product_id}</span>}
                    {m.lot_no && <div className="text-xs text-[var(--text-primary)]/50 font-mono">{m.lot_no}</div>}
                    {cust && <div className="text-xs text-sky-700">{cust.name}</div>}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium">{Number(m.qty).toFixed(2)}</td>
                  <td className="px-4 py-2.5 text-xs text-[var(--text-primary)]/70 font-mono">
                    {from ? `${from.code}` : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-[var(--text-primary)]/70 font-mono">
                    {to ? `${to.code}` : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-[var(--text-primary)]/70">
                    {Number(m.unit_cost) > 0 ? fmt(Number(m.unit_cost)) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                    {Number(m.total_cost) > 0 ? fmt(Number(m.total_cost)) : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    {src ? (
                      <Link href={src.href} className="text-[var(--primary)] hover:underline text-xs">{src.label}</Link>
                    ) : m.source_doc_type ? (
                      <span className="text-xs text-[var(--text-primary)]/40">{m.source_doc_type}</span>
                    ) : "—"}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-[var(--text-primary)]/50 print:hidden">
          <span>{total} movements</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => p - 1)} disabled={page === 0}
              className="flex items-center gap-1 px-2 py-1 border border-[var(--border)] rounded disabled:opacity-40 enabled:hover:border-[var(--primary)] enabled:hover:text-[var(--primary)]">
              <ChevronLeft className="w-3.5 h-3.5" /> Prev
            </button>
            <span>Page {page + 1} of {totalPages}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1}
              className="flex items-center gap-1 px-2 py-1 border border-[var(--border)] rounded disabled:opacity-40 enabled:hover:border-[var(--primary)] enabled:hover:text-[var(--primary)]">
              Next <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
