"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AlertTriangle, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"

// ── Legacy endpoint (on-hand / reorder / last-movement) ─────────────────────
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

// ── New product-performance endpoint ────────────────────────────────────────
interface ProductPerfItem {
  product_id: number
  name: string
  code: string | null
  opening_qty: number
  opening_value: number
  purchased_qty: number
  sold_qty: number
  closing_qty: number
  closing_value: number
  gp: number
  revenue: number
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
type PerfSortKey = "closing_value" | "opening_qty" | "purchased_qty" | "sold_qty" | "gp" | "name"
type Tab = "stock" | "movement"

export default function InventoryPerformancePage() {
  const fmt = useFmt()

  // Stock view state
  const [data, setData] = useState<InventoryItem[]>([])
  const [isLoadingStock, setIsLoadingStock] = useState(true)

  // Movement/period view state
  const [perfData, setPerfData] = useState<ProductPerfItem[]>([])
  const [isLoadingPerf, setIsLoadingPerf] = useState(true)

  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [tab, setTab] = useState<Tab>("stock")

  // Stock sort
  const [sortKey, setSortKey] = useState<SortKey>("stock_value")
  const [sortAsc, setSortAsc] = useState(false)

  // Movement sort
  const [perfSortKey, setPerfSortKey] = useState<PerfSortKey>("closing_value")
  const [perfSortAsc, setPerfSortAsc] = useState(false)

  // Load stock (legacy) data
  useEffect(() => {
    setIsLoadingStock(true)
    apiFetch<{ items: InventoryItem[] }>(
      `/api/reports/inventory-performance?start=${start}&end=${end}`
    )
      .then(d => { setData(d.items); setIsLoadingStock(false) })
      .catch(() => setIsLoadingStock(false))
  }, [start, end])

  // Load product-performance (movement) data
  useEffect(() => {
    setIsLoadingPerf(true)
    apiFetch<{ items: ProductPerfItem[] }>(
      `/api/reports/product-performance?start=${start}&end=${end}`
    )
      .then(d => { setPerfData(d.items); setIsLoadingPerf(false) })
      .catch(() => setIsLoadingPerf(false))
  }, [start, end])

  // ── Sort helpers ────────────────────────────────────────────────────────────
  const sorted = [...data].sort((a, b) => {
    const av = a[sortKey] ?? ""
    const bv = b[sortKey] ?? ""
    if (av < bv) return sortAsc ? -1 : 1
    if (av > bv) return sortAsc ? 1 : -1
    return 0
  })

  const perfSorted = [...perfData].sort((a, b) => {
    const av = a[perfSortKey] ?? ""
    const bv = b[perfSortKey] ?? ""
    if (av < bv) return perfSortAsc ? -1 : 1
    if (av > bv) return perfSortAsc ? 1 : -1
    return 0
  })

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(p => !p)
    else { setSortKey(key); setSortAsc(false) }
  }

  const togglePerfSort = (key: PerfSortKey) => {
    if (perfSortKey === key) setPerfSortAsc(p => !p)
    else { setPerfSortKey(key); setPerfSortAsc(false) }
  }

  const sortIndicator = (k: SortKey) =>
    sortKey === k ? (sortAsc ? " ▲" : " ▼") : ""

  const perfSortIndicator = (k: PerfSortKey) =>
    perfSortKey === k ? (perfSortAsc ? " ▲" : " ▼") : ""

  // ── Totals ──────────────────────────────────────────────────────────────────
  const totalValue = data.reduce((s, r) => s + r.stock_value, 0)
  const totalCogs  = data.reduce((s, r) => s + r.cogs, 0)
  const lowStockCount = data.filter(r => r.low_stock).length

  const perfTotalClosingValue = perfData.reduce((s, r) => s + r.closing_value, 0)
  const perfTotalGP = perfData.reduce((s, r) => s + r.gp, 0)

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
            onClick={() => {
              if (tab === "stock") {
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
              } else {
                downloadCSV(`product-movement-${start}-${end}.csv`,
                  perfSorted.map(r => ({
                    Name: r.name, Code: r.code ?? "",
                    "Opening Qty": r.opening_qty, "Opening Value": r.opening_value,
                    "Purchased Qty": r.purchased_qty, "Sold Qty (Net)": r.sold_qty,
                    "Closing Qty": r.closing_qty, "Closing Value": r.closing_value,
                    "Revenue": r.revenue, "GP": r.gp,
                  }))
                )
              }
            }}
            className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60"
            title="Export CSV"
          >
            <Download className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Period picker + tab toggle */}
      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl print:hidden space-y-4">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
        <div className="flex gap-2">
          <button
            onClick={() => setTab("stock")}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${tab === "stock" ? "bg-[#1a1814] text-white" : "bg-[#f6f3ee] text-[#1a1814]/70 hover:bg-[#ede9e2]"}`}
          >
            Stock View
          </button>
          <button
            onClick={() => setTab("movement")}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${tab === "movement" ? "bg-[#1a1814] text-white" : "bg-[#f6f3ee] text-[#1a1814]/70 hover:bg-[#ede9e2]"}`}
          >
            Period Movement
          </button>
        </div>
      </div>

      {/* ── STOCK VIEW ──────────────────────────────────────────────────────── */}
      {tab === "stock" && (
        <>
          {/* KPI summary */}
          {!isLoadingStock && data.length > 0 && (
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

          <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[800px]">
                <thead>
                  <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 cursor-pointer select-none"
                      onClick={() => toggleSort("name")}
                    >
                      Product{sortIndicator("name")}
                    </th>
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                      onClick={() => toggleSort("on_hand")}
                    >
                      On Hand{sortIndicator("on_hand")}
                    </th>
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">
                      Avg Cost
                    </th>
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                      onClick={() => toggleSort("stock_value")}
                    >
                      Stock Value{sortIndicator("stock_value")}
                    </th>
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-center">
                      Status
                    </th>
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">
                      Last Movement
                    </th>
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                      onClick={() => toggleSort("units_sold")}
                    >
                      Units Sold{sortIndicator("units_sold")}
                    </th>
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                      onClick={() => toggleSort("cogs")}
                    >
                      COGS{sortIndicator("cogs")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1a1814]/5">
                  {isLoadingStock ? (
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
                        <td className="ui-td">
                          <Link
                            href={`/products/ledger?product=${item.id}`}
                            className="font-medium text-[#1a1814] hover:text-[#b8943f] hover:underline"
                            title="View product ledger"
                          >
                            {item.name}
                          </Link>
                          {item.code && (
                            <span className="ml-2 font-mono text-xs text-[#b8943f]">{item.code}</span>
                          )}
                        </td>
                        <td className="ui-td text-right font-mono text-sm text-[#1a1814]">
                          {Number(item.on_hand).toLocaleString()}
                        </td>
                        <td className="ui-td text-right font-mono text-sm text-[#1a1814]/70">
                          {fmt(item.avg_cost)}
                        </td>
                        <td className="ui-td text-right font-mono text-sm font-semibold text-[#1a1814]">
                          {fmt(item.stock_value)}
                        </td>
                        <td className="ui-td text-center">
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
                        <td className="ui-td text-right text-sm text-[#1a1814]/60">
                          {item.last_movement ?? "—"}
                        </td>
                        <td className="ui-td text-right font-mono text-sm text-[#1a1814]">
                          {Number(item.units_sold).toLocaleString()}
                        </td>
                        <td className="ui-td text-right font-mono text-sm text-[#1a1814]">
                          {fmt(item.cogs)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
                {!isLoadingStock && sorted.length > 0 && (
                  <tfoot>
                    <tr className="bg-[#1a1814] text-white">
                      <td className="ui-td font-bold uppercase tracking-widest text-xs" colSpan={3}>
                        Total
                      </td>
                      <td className="ui-td text-right font-mono font-bold">{fmt(totalValue)}</td>
                      <td colSpan={3} />
                      <td className="ui-td text-right font-mono font-bold">{fmt(totalCogs)}</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
        </>
      )}

      {/* ── PERIOD MOVEMENT VIEW ─────────────────────────────────────────────── */}
      {tab === "movement" && (
        <>
          {!isLoadingPerf && perfData.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6 print:hidden">
              <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
                <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Closing Stock Value</p>
                <p className="text-2xl font-mono font-semibold text-[#1a1814]">{fmt(perfTotalClosingValue)}</p>
              </div>
              <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
                <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Gross Profit (Period)</p>
                <p className={`text-2xl font-mono font-semibold ${perfTotalGP >= 0 ? "text-green-700" : "text-red-600"}`}>
                  {fmt(perfTotalGP)}
                </p>
              </div>
              <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
                <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Products</p>
                <p className="text-2xl font-mono font-semibold text-[#1a1814]">{perfData.length}</p>
              </div>
            </div>
          )}

          <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[900px]">
                <thead>
                  <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 cursor-pointer select-none"
                      onClick={() => togglePerfSort("name")}
                    >
                      Product{perfSortIndicator("name")}
                    </th>
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                      onClick={() => togglePerfSort("opening_qty")}
                    >
                      Opening Qty{perfSortIndicator("opening_qty")}
                    </th>
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">
                      Opening Value
                    </th>
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                      onClick={() => togglePerfSort("purchased_qty")}
                    >
                      Purchased{perfSortIndicator("purchased_qty")}
                    </th>
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                      onClick={() => togglePerfSort("sold_qty")}
                    >
                      Sold (Net){perfSortIndicator("sold_qty")}
                    </th>
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                      onClick={() => togglePerfSort("gp")}
                    >
                      GP{perfSortIndicator("gp")}
                    </th>
                    <th
                      className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right cursor-pointer select-none"
                      onClick={() => togglePerfSort("closing_value")}
                    >
                      Closing Qty / Value{perfSortIndicator("closing_value")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1a1814]/5">
                  {isLoadingPerf ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-10 text-center text-[#1a1814]/60">
                        Loading movement data…
                      </td>
                    </tr>
                  ) : perfSorted.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-10 text-center text-[#1a1814]/60">
                        No stock products found.
                      </td>
                    </tr>
                  ) : (
                    perfSorted.map(item => (
                      <tr key={item.product_id} className="hover:bg-[#f6f3ee]/30 transition-colors">
                        <td className="ui-td">
                          <Link
                            href={`/products/ledger?product=${item.product_id}`}
                            className="font-medium text-[#1a1814] hover:text-[#b8943f] hover:underline"
                            title="View product ledger"
                          >
                            {item.name}
                          </Link>
                          {item.code && (
                            <span className="ml-2 font-mono text-xs text-[#b8943f]">{item.code}</span>
                          )}
                        </td>
                        <td className="ui-td text-right font-mono text-sm text-[#1a1814]">
                          {Number(item.opening_qty).toLocaleString()}
                        </td>
                        <td className="ui-td text-right font-mono text-sm text-[#1a1814]/70">
                          {fmt(item.opening_value)}
                        </td>
                        <td className="ui-td text-right font-mono text-sm text-green-700">
                          +{Number(item.purchased_qty).toLocaleString()}
                        </td>
                        <td className="ui-td text-right font-mono text-sm text-red-600">
                          {item.sold_qty > 0 ? `-${Number(item.sold_qty).toLocaleString()}` : "—"}
                        </td>
                        <td className={`ui-td text-right font-mono text-sm font-semibold ${item.gp >= 0 ? "text-green-700" : "text-red-600"}`}>
                          {fmt(item.gp)}
                        </td>
                        <td className="ui-td text-right font-mono text-sm font-semibold text-[#1a1814]">
                          {Number(item.closing_qty).toLocaleString()}
                          <span className="ml-1 text-[#1a1814]/50 font-normal">({fmt(item.closing_value)})</span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
                {!isLoadingPerf && perfSorted.length > 0 && (
                  <tfoot>
                    <tr className="bg-[#1a1814] text-white">
                      <td className="ui-td font-bold uppercase tracking-widest text-xs" colSpan={5}>
                        Total
                      </td>
                      <td className="ui-td text-right font-mono font-bold">{fmt(perfTotalGP)}</td>
                      <td className="ui-td text-right font-mono font-bold">{fmt(perfTotalClosingValue)}</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
