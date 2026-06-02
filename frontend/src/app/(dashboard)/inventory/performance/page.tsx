"use client"

import { useEffect, useState } from "react"
import { AlertTriangle, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"

interface InventoryItem {
  id: number
  name: string
  code: string | null
  on_hand: number
  avg_cost: number
  stock_value: number
  reorder_level: number
  low_stock: boolean
  last_movement: string | null
  units_sold: number
  cogs: number
}

interface InventoryPerformanceData {
  items: InventoryItem[]
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

type SortKey = "stock_value" | "on_hand" | "units_sold" | "cogs" | "name"

export default function InventoryPerformancePage() {
  const fmt = useFmt()
  const [data, setData] = useState<InventoryItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [sortKey, setSortKey] = useState<SortKey>("stock_value")
  const [sortAsc, setSortAsc] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    apiFetch<InventoryPerformanceData>(
      `/api/reports/inventory-performance?start=${start}&end=${end}`
    )
      .then(d => { setData(d.items); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [start, end])

  const sorted = [...data].sort((a, b) => {
    const av = a[sortKey] ?? ""
    const bv = b[sortKey] ?? ""
    if (av < bv) return sortAsc ? -1 : 1
    if (av > bv) return sortAsc ? 1 : -1
    return 0
  })

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(p => !p)
    else { setSortKey(key); setSortAsc(false) }
  }

  const SortIndicator = ({ k }: { k: SortKey }) =>
    sortKey === k ? (sortAsc ? " ▲" : " ▼") : ""

  const totalValue = data.reduce((s, r) => s + r.stock_value, 0)
  const totalCogs  = data.reduce((s, r) => s + r.cogs, 0)
  const lowStockCount = data.filter(r => r.low_stock).length

  return (
    <div className="max-w-7xl mx-auto">
      <PrintHeader title="Inventory Performance" subtitle={`Period: ${start} — ${end}`} />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Inventory Performance</h1>
          <p className="text-[#1a1814]/60">Stock valuation, movement analysis and low-stock alerts</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => window.print()}
            className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60"
            title="Print"
          >
            <Printer className="w-5 h-5" />
          </button>
          <button
            onClick={() =>
              downloadCSV(`inventory-performance-${start}-${end}.csv`,
                sorted.map(r => ({
                  Name: r.name, Code: r.code ?? "",
                  "On Hand": r.on_hand, "Avg Cost": r.avg_cost,
                  "Stock Value": r.stock_value, "Reorder Level": r.reorder_level,
                  "Low Stock": r.low_stock ? "Yes" : "No",
                  "Last Movement": r.last_movement ?? "",
                  "Units Sold": r.units_sold, "COGS": r.cogs,
                }))
              )
            }
            className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60"
            title="Export CSV"
          >
            <Download className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Period picker */}
      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl print:hidden">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
      </div>

      {/* KPI summary */}
      {!isLoading && data.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 print:hidden">
          <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Total Stock Value</p>
            <p className="text-2xl font-mono font-semibold text-[#1a1814]">{fmt(totalValue)}</p>
          </div>
          <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">COGS (Period)</p>
            <p className="text-2xl font-mono font-semibold text-[#1a1814]">{fmt(totalCogs)}</p>
          </div>
          <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Products</p>
            <p className="text-2xl font-mono font-semibold text-[#1a1814]">{data.length}</p>
          </div>
          <div className={`rounded-2xl p-4 border ${lowStockCount > 0 ? "bg-red-50 border-red-200" : "bg-white border-[#ede9e2]"}`}>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Low Stock</p>
            <p className={`text-2xl font-mono font-semibold ${lowStockCount > 0 ? "text-red-600" : "text-[#1a1814]"}`}>
              {lowStockCount}
            </p>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[800px]">
            <thead>
              <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
                <th
                  className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 cursor-pointer select-none"
                  onClick={() => toggleSort("name")}
                >
                  Product<SortIndicator k="name" />
                </th>
                <th
                  className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                  onClick={() => toggleSort("on_hand")}
                >
                  On Hand<SortIndicator k="on_hand" />
                </th>
                <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">
                  Avg Cost
                </th>
                <th
                  className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                  onClick={() => toggleSort("stock_value")}
                >
                  Stock Value<SortIndicator k="stock_value" />
                </th>
                <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-center">
                  Status
                </th>
                <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">
                  Last Movement
                </th>
                <th
                  className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                  onClick={() => toggleSort("units_sold")}
                >
                  Units Sold<SortIndicator k="units_sold" />
                </th>
                <th
                  className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                  onClick={() => toggleSort("cogs")}
                >
                  COGS<SortIndicator k="cogs" />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1a1814]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="px-6 py-10 text-center text-[#1a1814]/60">
                    Loading inventory data…
                  </td>
                </tr>
              ) : sorted.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-10 text-center text-[#1a1814]/60">
                    No stock products found.
                  </td>
                </tr>
              ) : (
                sorted.map(item => (
                  <tr key={item.id} className={`hover:bg-[#f6f3ee]/30 transition-colors ${item.low_stock ? "bg-red-50/40" : ""}`}>
                    <td className="px-6 py-4">
                      <span className="font-medium text-[#1a1814]">{item.name}</span>
                      {item.code && (
                        <span className="ml-2 font-mono text-xs text-[#b8943f]">{item.code}</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-sm text-[#1a1814]">
                      {Number(item.on_hand).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-sm text-[#1a1814]/70">
                      {fmt(item.avg_cost)}
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-sm font-semibold text-[#1a1814]">
                      {fmt(item.stock_value)}
                    </td>
                    <td className="px-6 py-4 text-center">
                      {item.low_stock ? (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-100 px-2 py-0.5 rounded-full">
                          <AlertTriangle className="w-3 h-3" />
                          Low Stock
                        </span>
                      ) : (
                        <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                          OK
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right text-sm text-[#1a1814]/60">
                      {item.last_movement ?? "—"}
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-sm text-[#1a1814]">
                      {Number(item.units_sold).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-sm text-[#1a1814]">
                      {fmt(item.cogs)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
            {!isLoading && sorted.length > 0 && (
              <tfoot>
                <tr className="bg-[#1a1814] text-white">
                  <td className="px-6 py-5 font-bold uppercase tracking-widest text-xs" colSpan={3}>
                    Total
                  </td>
                  <td className="px-6 py-5 text-right font-mono font-bold">{fmt(totalValue)}</td>
                  <td colSpan={3} />
                  <td className="px-6 py-5 text-right font-mono font-bold">{fmt(totalCogs)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </div>
  )
}
