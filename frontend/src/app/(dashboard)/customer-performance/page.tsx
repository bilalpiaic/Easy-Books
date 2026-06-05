"use client"

import { useEffect, useState } from "react"
import { Download, Printer } from "lucide-react"
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend,
} from "chart.js"
import { Bar } from "react-chartjs-2"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

interface CustomerRow {
  name: string
  revenue: number
  invoice_count: number
  outstanding: number
  avg_days_to_pay: number | null
}

interface MonthlyEntry {
  month: string
  revenue: number
  units: number
}

interface ProductRow {
  product_id: number
  name: string
  category: string
  qty: number
  revenue: number
  cogs: number
  gp: number
}

interface DetailTotals {
  revenue: number
  cogs: number
  gp: number
  gp_pct: number
}

interface CustomerDetail {
  monthly: MonthlyEntry[]
  products: ProductRow[]
  totals: DetailTotals
}

interface CustomerPerformanceData {
  items: CustomerRow[]
  detail: CustomerDetail | null
}

interface Customer {
  id: number
  name: string
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

export default function CustomerPerformancePage() {
  const fmt = useFmt()
  const [data, setData] = useState<CustomerRow[]>([])
  const [detail, setDetail] = useState<CustomerDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | "">("")

  // Load customer list once
  useEffect(() => {
    apiFetch<{ total: number; items: Customer[] }>("/api/customers?limit=500")
      .then(d => setCustomers(d.items))
      .catch(() => {})
  }, [])

  // Load report whenever filters change
  useEffect(() => {
    setIsLoading(true)
    const qs = new URLSearchParams({ start, end })
    if (selectedCustomerId !== "") qs.set("customer_id", String(selectedCustomerId))
    apiFetch<CustomerPerformanceData>(`/api/reports/customer-performance?${qs}`)
      .then(d => {
        setData(d.items)
        setDetail(d.detail)
        setIsLoading(false)
      })
      .catch(() => setIsLoading(false))
  }, [start, end, selectedCustomerId])

  const totalRevenue     = data.reduce((s, r) => s + r.revenue, 0)
  const totalOutstanding = data.reduce((s, r) => s + r.outstanding, 0)
  const totalInvoices    = data.reduce((s, r) => s + r.invoice_count, 0)

  const sorted = [...data].sort((a, b) => b.revenue - a.revenue)

  const rowHighlight = (idx: number) => {
    if (idx === 0) return "bg-[#b8943f]/10 border-l-4 border-[#b8943f]"
    if (idx === 1) return "bg-[#1a1814]/5 border-l-4 border-[#1a1814]/30"
    if (idx === 2) return "bg-amber-50 border-l-4 border-amber-300"
    return ""
  }

  const barData = detail ? {
    labels: detail.monthly.map(m => m.month),
    datasets: [
      {
        label: "Revenue",
        data: detail.monthly.map(m => m.revenue),
        backgroundColor: "#b8943f",
        borderRadius: 4,
      },
    ],
  } : null

  const barOptions = {
    responsive: true,
    plugins: { legend: { display: false }, tooltip: { mode: "index" as const } },
    scales: { y: { ticks: { callback: (v: number | string) => fmt(Number(v)) } } },
  }

  return (
    <div className="max-w-6xl mx-auto">
      <PrintHeader title="Customer Performance" subtitle={`Period: ${start} — ${end}`} />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Customer Performance</h1>
          <p className="text-[#1a1814]/60">Revenue, invoicing and payment speed ranked by top customers</p>
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
              downloadCSV(`customer-performance-${start}-${end}.csv`,
                sorted.map(r => ({
                  Customer: r.name,
                  Revenue: r.revenue,
                  Invoices: r.invoice_count,
                  Outstanding: r.outstanding,
                  "Avg Days to Pay": r.avg_days_to_pay ?? "",
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

      {/* Filters */}
      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl print:hidden space-y-4">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-[#1a1814]/60 uppercase tracking-widest">
            Customer (optional — drill into a single customer)
          </label>
          <select
            className="ui-field"
            value={selectedCustomerId}
            onChange={e => setSelectedCustomerId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">All customers (ranking view)</option>
            {customers.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* ── DETAIL VIEW (single customer selected) ─────────────────────────── */}
      {selectedCustomerId !== "" && detail && (
        <div className="space-y-6 mb-8">
          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
              <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Revenue</p>
              <p className="text-2xl font-mono font-semibold text-[#1a1814]">{fmt(detail.totals.revenue)}</p>
            </div>
            <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
              <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">COGS</p>
              <p className="text-2xl font-mono font-semibold text-[#1a1814]">{fmt(detail.totals.cogs)}</p>
            </div>
            <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
              <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Gross Profit</p>
              <p className={`text-2xl font-mono font-semibold ${detail.totals.gp >= 0 ? "text-green-700" : "text-red-600"}`}>
                {fmt(detail.totals.gp)}
              </p>
            </div>
            <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
              <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">GP %</p>
              <p className={`text-2xl font-mono font-semibold ${detail.totals.gp_pct >= 0 ? "text-green-700" : "text-red-600"}`}>
                {detail.totals.gp_pct.toFixed(1)}%
              </p>
            </div>
          </div>

          {/* Monthly Sales Volume chart */}
          {barData && detail.monthly.length > 0 && (
            <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
              <h2 className="text-sm font-bold text-[#1a1814]/70 uppercase tracking-widest mb-4">
                Monthly Sales Volume
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse mb-4">
                  <thead>
                    <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
                      <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Month</th>
                      <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Revenue</th>
                      <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Units</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1a1814]/5">
                    {detail.monthly.map(m => (
                      <tr key={m.month} className="hover:bg-[#f6f3ee]/30">
                        <td className="ui-td text-sm text-[#1a1814]">{m.month}</td>
                        <td className="ui-td text-right font-mono text-sm font-semibold text-[#1a1814]">{fmt(m.revenue)}</td>
                        <td className="ui-td text-right text-sm text-[#1a1814]/70">{m.units}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="h-48">
                <Bar data={barData} options={barOptions} />
              </div>
            </div>
          )}

          {/* Product & Category trade */}
          {detail.products.length > 0 && (
            <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
              <div className="px-6 py-4 border-b border-[#1a1814]/5">
                <h2 className="text-sm font-bold text-[#1a1814]/70 uppercase tracking-widest">
                  Product &amp; Category Trade
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse min-w-[700px]">
                  <thead>
                    <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
                      <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Category</th>
                      <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Product</th>
                      <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Qty</th>
                      <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Revenue</th>
                      <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">COGS</th>
                      <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">GP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1a1814]/5">
                    {detail.products.map(r => (
                      <tr key={r.product_id} className="hover:bg-[#f6f3ee]/30 transition-colors">
                        <td className="ui-td text-sm text-[#1a1814]/60">{r.category}</td>
                        <td className="ui-td text-sm font-medium text-[#1a1814]">{r.name}</td>
                        <td className="ui-td text-right text-sm text-[#1a1814]">{r.qty}</td>
                        <td className="ui-td text-right font-mono text-sm font-semibold text-[#1a1814]">{fmt(r.revenue)}</td>
                        <td className="ui-td text-right font-mono text-sm text-[#1a1814]/70">{fmt(r.cogs)}</td>
                        <td className={`ui-td text-right font-mono text-sm font-semibold ${r.gp >= 0 ? "text-green-700" : "text-red-600"}`}>
                          {fmt(r.gp)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── RANKING VIEW (no customer selected) ────────────────────────────── */}
      {selectedCustomerId === "" && (
        <>
          {/* KPI cards */}
          {!isLoading && data.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6 print:hidden">
              <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
                <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Total Revenue</p>
                <p className="text-2xl font-mono font-semibold text-[#1a1814]">{fmt(totalRevenue)}</p>
              </div>
              <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
                <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Outstanding AR</p>
                <p className="text-2xl font-mono font-semibold text-[#1a1814]">{fmt(totalOutstanding)}</p>
              </div>
              <div className="bg-white border border-[#ede9e2] rounded-2xl p-4">
                <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest mb-1">Total Invoices</p>
                <p className="text-2xl font-mono font-semibold text-[#1a1814]">{totalInvoices}</p>
              </div>
            </div>
          )}

          {/* Ranked table */}
          <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[700px]">
                <thead>
                  <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">#</th>
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Customer</th>
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Revenue</th>
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Invoices</th>
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Outstanding</th>
                    <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Avg Days to Pay</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1a1814]/5">
                  {isLoading ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-10 text-center text-[#1a1814]/60">
                        Loading customer data…
                      </td>
                    </tr>
                  ) : sorted.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-10 text-center text-[#1a1814]/60">
                        No invoices found for selected period.
                      </td>
                    </tr>
                  ) : (
                    sorted.map((row, idx) => (
                      <tr
                        key={row.name}
                        className={`hover:bg-[#f6f3ee]/30 transition-colors ${rowHighlight(idx)}`}
                      >
                        <td className="ui-td text-sm font-bold text-[#1a1814]/40">
                          {idx + 1}
                        </td>
                        <td className="ui-td">
                          <span className="font-medium text-[#1a1814]">{row.name}</span>
                          {idx < 3 && (
                            <span className="ml-2 text-[10px] font-bold uppercase tracking-wide text-[#b8943f]">
                              {idx === 0 ? "Top Customer" : idx === 1 ? "2nd" : "3rd"}
                            </span>
                          )}
                        </td>
                        <td className="ui-td text-right font-mono text-sm font-semibold text-[#1a1814]">
                          {fmt(row.revenue)}
                        </td>
                        <td className="ui-td text-right text-sm text-[#1a1814]">
                          {row.invoice_count}
                        </td>
                        <td className="ui-td text-right font-mono text-sm">
                          <span className={row.outstanding > 0 ? "text-red-600 font-semibold" : "text-[#1a1814]/50"}>
                            {row.outstanding > 0 ? fmt(row.outstanding) : "—"}
                          </span>
                        </td>
                        <td className="ui-td text-right text-sm text-[#1a1814]/70">
                          {row.avg_days_to_pay != null ? `${row.avg_days_to_pay} days` : "—"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
                {!isLoading && sorted.length > 0 && (
                  <tfoot>
                    <tr className="bg-[#1a1814] text-white">
                      <td className="ui-td font-bold uppercase tracking-widest text-xs" colSpan={2}>
                        Total
                      </td>
                      <td className="ui-td text-right font-mono font-bold">{fmt(totalRevenue)}</td>
                      <td className="ui-td text-right font-mono font-bold">{totalInvoices}</td>
                      <td className="ui-td text-right font-mono font-bold">{fmt(totalOutstanding)}</td>
                      <td />
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
