"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Users, Package, MapPin, ChevronDown, ChevronRight } from "lucide-react"
import { apiFetch } from "@/lib/api"

interface CustodyRow {
  customer_id: number
  product_id: number
  product_code: string
  product_name: string
  lot_no: string | null
  location_id: number
  qty_on_hand: number
}

interface StockLocation {
  id: number
  code: string
  name: string
}

interface Customer {
  id: number
  name: string
}

interface CustomerGroup {
  customer_id: number
  customer_name: string
  rows: CustodyRow[]
  total_qty: number
}

export default function CustodyPage() {
  const [rows, setRows]         = useState<CustodyRow[]>([])
  const [locations, setLocations] = useState<Map<number, StockLocation>>(new Map())
  const [customers, setCustomers] = useState<Map<number, string>>(new Map())
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  useEffect(() => {
    Promise.all([
      apiFetch<CustodyRow[]>("/api/stock-locations/custody"),
      apiFetch<{ total: number; items: StockLocation[] }>("/api/stock-locations?limit=200"),
      apiFetch<{ total: number; items: Customer[] }>("/api/customers?limit=500"),
    ])
      .then(([custody, locs, custs]) => {
        setRows(custody)
        setLocations(new Map(locs.items.map(l => [l.id, l])))
        setCustomers(new Map(custs.items.map(c => [c.id, c.name])))
        // expand all by default when there is data
        if (custody.length > 0) {
          const ids = new Set(custody.map(r => r.customer_id))
          setExpanded(ids)
        }
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])

  const toggleCustomer = (customerId: number) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(customerId) ? next.delete(customerId) : next.add(customerId)
      return next
    })
  }

  // Group rows by customer
  const groups: CustomerGroup[] = []
  const seen = new Map<number, CustomerGroup>()
  for (const row of rows) {
    if (!seen.has(row.customer_id)) {
      const group: CustomerGroup = {
        customer_id: row.customer_id,
        customer_name: customers.get(row.customer_id) ?? `Customer #${row.customer_id}`,
        rows: [],
        total_qty: 0,
      }
      seen.set(row.customer_id, group)
      groups.push(group)
    }
    const group = seen.get(row.customer_id)!
    group.rows.push(row)
    group.total_qty += Number(row.qty_on_hand)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Customer Goods in Custody</h1>
          <p className="text-sm text-[#1a1814]/60 mt-0.5">
            Inventory belonging to customers currently held at your locations.
          </p>
        </div>
        <Link
          href="/manufacturing/stock-locations"
          className="inline-flex items-center gap-2 border border-[#ede9e2] px-3 py-2 rounded-lg text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors"
        >
          <MapPin className="w-4 h-4" /> All Locations
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {loading ? (
        <div className="text-sm text-[#1a1814]/50 py-8 text-center">Loading…</div>
      ) : groups.length === 0 ? (
        <div className="bg-white border border-[#ede9e2] rounded-xl px-6 py-12 text-center">
          <Users className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]">No customer goods in custody</p>
          <p className="text-xs text-[#1a1814]/55 mt-1">
            When inventory layers with a customer owner are created, they appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map(group => {
            const isOpen = expanded.has(group.customer_id)
            return (
              <div key={group.customer_id} className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
                {/* Customer header row */}
                <button
                  onClick={() => toggleCustomer(group.customer_id)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#faf8f4] transition-colors text-left"
                >
                  <span className="text-[#1a1814]/30">
                    {isOpen
                      ? <ChevronDown className="w-4 h-4" />
                      : <ChevronRight className="w-4 h-4" />
                    }
                  </span>
                  <Users className="w-4 h-4 text-[#b8943f]/70 shrink-0" />
                  <span className="flex-1 text-sm font-medium text-[#1a1814]">{group.customer_name}</span>
                  <span className="text-xs text-[#1a1814]/50 tabular-nums">
                    {group.rows.length} SKU{group.rows.length !== 1 ? "s" : ""}
                  </span>
                  <span className="ml-4 text-xs font-semibold text-[#1a1814] tabular-nums">
                    {Number(group.total_qty).toFixed(2)} total
                  </span>
                </button>

                {/* Product rows */}
                {isOpen && (
                  <div className="border-t border-[#ede9e2]">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-[#ede9e2] bg-[#faf8f4]">
                          <th className="text-left px-6 py-2 font-semibold text-[#1a1814]/60">Product</th>
                          <th className="text-left px-4 py-2 font-semibold text-[#1a1814]/60">Lot / Batch</th>
                          <th className="text-left px-4 py-2 font-semibold text-[#1a1814]/60">Location</th>
                          <th className="text-right px-4 py-2 font-semibold text-[#1a1814]/60">Qty on Hand</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.rows.map((row, i) => {
                          const loc = locations.get(row.location_id)
                          return (
                            <tr key={i} className="border-b border-[#ede9e2] last:border-0 hover:bg-[#faf8f4]">
                              <td className="px-6 py-2 text-[#1a1814]/80">
                                <Link
                                  href={`/products/ledger?product=${row.product_id}`}
                                  className="text-[#b8943f] hover:underline font-mono mr-1.5"
                                >
                                  {row.product_code}
                                </Link>
                                {row.product_name}
                              </td>
                              <td className="px-4 py-2 text-[#1a1814]/55 font-mono">
                                {row.lot_no || <span className="text-[#1a1814]/30">—</span>}
                              </td>
                              <td className="px-4 py-2 text-[#1a1814]/70">
                                {loc ? (
                                  <span className="inline-flex items-center gap-1">
                                    <MapPin className="w-3 h-3 text-[#1a1814]/30" />
                                    <span className="font-mono text-[#1a1814]/60 mr-1">{loc.code}</span>
                                    {loc.name}
                                  </span>
                                ) : (
                                  <span className="text-[#1a1814]/30">Loc #{row.location_id}</span>
                                )}
                              </td>
                              <td className="px-4 py-2 text-right tabular-nums font-medium text-[#1a1814]">
                                {Number(row.qty_on_hand).toFixed(2)}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                      <tfoot>
                        <tr className="border-t border-[#ede9e2] bg-[#f5f2ed]">
                          <td className="px-6 py-2 text-xs font-semibold text-[#1a1814]/60" colSpan={3}>
                            {group.rows.length} item{group.rows.length !== 1 ? "s" : ""} in custody
                          </td>
                          <td className="px-4 py-2 text-right text-xs font-bold text-[#1a1814] tabular-nums">
                            {Number(group.total_qty).toFixed(2)}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <div className="bg-violet-50 border border-violet-200 rounded-xl px-4 py-3 text-xs text-violet-800">
        <Package className="w-4 h-4 inline mr-1.5 -mt-0.5" />
        <strong>Custody inventory</strong> belongs to customers but is physically at your location — it does not count
        toward your own stock value. These items appear as a liability until returned or invoiced.
      </div>
    </div>
  )
}
