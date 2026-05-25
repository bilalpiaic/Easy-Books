"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  TrendingUp, TrendingDown, Hash, Wallet,
  ArrowDownLeft, ArrowUpRight, Clock,
  Package, AlertTriangle, FileSignature,
  Receipt, ChevronRight, Banknote, CalendarClock,
} from "lucide-react"
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Title, Tooltip, Legend, Filler,
  type ChartOptions,
} from "chart.js"
import { Bar, Doughnut, Line } from "react-chartjs-2"
import { fmtPKR } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import DateRangePicker from "@/components/DateRangePicker"

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Title, Tooltip, Legend, Filler
)

interface ArAging {
  current: number
  "1_30": number
  "31_60": number
  "61_90": number
  over_90: number
}

interface DashboardSummary {
  total_revenue: number
  total_expense: number
  transaction_count: number
  ar_outstanding: number
  ap_outstanding: number
  overdue_invoices: number
  unpaid_bills: number
  low_stock_items: number
  cash_balance: number
  ar_aging: ArAging | null
  ap_due_week: number
}

interface RecentTx { id: number; jv_number: string; date: string; description: string }

interface DashboardData {
  summary: DashboardSummary
  recent: RecentTx[]
}

interface ChartData {
  monthly: { month: string; revenue: number; expenses: number; profit: number }[]
  expense_breakdown: { account: string; amount: number }[]
  top_customers: { name: string; total: number }[]
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

const DOUGHNUT_COLORS = [
  "#b8943f","#2563eb","#16a34a","#dc2626","#7c3aed",
  "#0891b2","#ea580c","#db2777","#65a30d",
]

export default function Dashboard() {
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd]     = useState(range.end)
  const [data, setData]   = useState<DashboardData | null>(null)
  const [charts, setCharts] = useState<ChartData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setData(null)
    apiFetch<DashboardData>(`/api/reports/dashboard?start=${start}&end=${end}`)
      .then(d => { if (!d.summary) throw new Error("Invalid response"); setData(d) })
      .catch(err => setError((err as Error).message))
  }, [start, end])

  useEffect(() => {
    apiFetch<ChartData>("/api/reports/dashboard/charts?months=12")
      .then(setCharts)
      .catch(() => {})
  }, [])

  const s = data?.summary
  const netProfit = s ? s.total_revenue - s.total_expense : 0
  const margin = s && s.total_revenue > 0 ? (netProfit / s.total_revenue * 100).toFixed(1) : null

  // ── Chart configs ────────────────────────────────────────────────────────────
  const monthLabels = charts?.monthly.map(m => {
    const [y, mo] = m.month.split("-")
    return new Date(+y, +mo - 1).toLocaleString("default", { month: "short" })
  }) ?? []

  const barData = {
    labels: monthLabels,
    datasets: [
      {
        label: "Revenue",
        data: charts?.monthly.map(m => m.revenue) ?? [],
        backgroundColor: "rgba(22,163,74,0.75)",
        borderRadius: 4,
      },
      {
        label: "Expenses",
        data: charts?.monthly.map(m => m.expenses) ?? [],
        backgroundColor: "rgba(220,38,38,0.70)",
        borderRadius: 4,
      },
    ],
  }

  const lineData = {
    labels: monthLabels,
    datasets: [{
      label: "Net Profit",
      data: charts?.monthly.map(m => m.profit) ?? [],
      borderColor: "#b8943f",
      backgroundColor: "rgba(184,148,63,0.10)",
      pointBackgroundColor: "#b8943f",
      pointRadius: 4,
      tension: 0.4,
      fill: true,
    }],
  }

  const doughnutData = {
    labels: charts?.expense_breakdown.map(e => e.account) ?? [],
    datasets: [{
      data: charts?.expense_breakdown.map(e => e.amount) ?? [],
      backgroundColor: DOUGHNUT_COLORS,
      borderWidth: 2,
      borderColor: "#fff",
    }],
  }

  const customerBarData = {
    labels: charts?.top_customers.map(c => c.name.length > 14 ? c.name.slice(0, 12) + "…" : c.name) ?? [],
    datasets: [{
      label: "Invoice Total",
      data: charts?.top_customers.map(c => c.total) ?? [],
      backgroundColor: "rgba(184,148,63,0.80)",
      borderRadius: 4,
    }],
  }

  const agingLabels = ["Current", "1–30d", "31–60d", "61–90d", "90d+"]
  const agingValues = s?.ar_aging
    ? [s.ar_aging.current, s.ar_aging["1_30"], s.ar_aging["31_60"], s.ar_aging["61_90"], s.ar_aging.over_90]
    : null
  const agingBarData = {
    labels: agingLabels,
    datasets: [{
      data: agingValues ?? [0, 0, 0, 0, 0],
      backgroundColor: [
        "rgba(22,163,74,0.78)",
        "rgba(234,179,8,0.78)",
        "rgba(249,115,22,0.78)",
        "rgba(239,68,68,0.82)",
        "rgba(185,28,28,0.88)",
      ],
      borderRadius: 4,
    }],
  }

  const baseChartOpts: ChartOptions<"bar"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtPKR(ctx.parsed.y as number) } } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmtPKR(v as number) } },
    },
  }

  const lineOpts: ChartOptions<"line"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtPKR((ctx.parsed.y ?? 0) as number) } } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmtPKR(v as number) } },
    },
  }

  const doughnutOpts: ChartOptions<"doughnut"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 12, padding: 8 } },
      tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmtPKR(ctx.parsed)}` } },
    },
    cutout: "62%",
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">Dashboard</h1>
          <p className="text-xs text-[#1a1814]/50 mt-0.5 font-medium tracking-wide uppercase">Financial Overview</p>
        </div>
        <div className="bg-white border border-[#ede9e2] rounded-xl px-3 py-2 shadow-sm">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>}

      {/* Primary KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <PrimaryKpi label="Revenue"    value={s ? fmtPKR(s.total_revenue) : null}           icon={TrendingUp}  bg="bg-green-50"   border="border-green-200"   text="text-green-800"   sub={margin ? `${margin}% margin` : undefined} />
        <PrimaryKpi label="Expenses"   value={s ? fmtPKR(s.total_expense) : null}           icon={TrendingDown} bg="bg-red-50"     border="border-red-200"     text="text-red-800" />
        <PrimaryKpi label="Net Profit" value={s ? fmtPKR(netProfit) : null}                 icon={Wallet}      bg={netProfit < 0 ? "bg-red-50" : "bg-amber-50"} border={netProfit < 0 ? "border-red-200" : "border-amber-200"} text={netProfit < 0 ? "text-red-800" : "text-amber-800"} sub={netProfit < 0 ? "Net loss" : "Net gain"} />
        <PrimaryKpi label="Cash & Bank" value={s ? fmtPKR(s.cash_balance ?? 0) : null}     icon={Banknote}    bg="bg-emerald-50" border="border-emerald-200"   text="text-emerald-800" sub="available balance" />
        <PrimaryKpi label="Vouchers"   value={s ? s.transaction_count.toString() : null}    icon={Hash}        bg="bg-blue-50"    border="border-blue-200"     text="text-blue-800"    sub="posted" compact />
      </div>

      {/* Secondary metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <SecondaryKpi label="AR Outstanding"   value={s ? fmtPKR(s.ar_outstanding) : null}       icon={ArrowDownLeft}  color="text-green-700"  href="/invoices"                badge={s?.overdue_invoices ? { count: s.overdue_invoices, label: "overdue", color: "bg-red-100 text-red-700" } : undefined} />
        <SecondaryKpi label="AP Outstanding"   value={s ? fmtPKR(s.ap_outstanding) : null}       icon={ArrowUpRight}   color="text-orange-700" href="/bills"                   badge={s?.unpaid_bills ? { count: s.unpaid_bills, label: "unpaid", color: "bg-orange-100 text-orange-700" } : undefined} />
        <SecondaryKpi label="Overdue Invoices" value={s ? s.overdue_invoices.toString() : null}   icon={Clock}          color="text-red-600"    href="/invoices"                valueClass={s && s.overdue_invoices > 0 ? "text-red-600 font-bold" : undefined} />
        <SecondaryKpi label="Low Stock Items"  value={s ? s.low_stock_items.toString() : null}    icon={Package}        color="text-purple-600" href="/products?low_stock=true" valueClass={s && s.low_stock_items > 0 ? "text-amber-600 font-bold" : undefined} />
        <SecondaryKpi label="AP Due This Week" value={s ? fmtPKR(s.ap_due_week ?? 0) : null}     icon={CalendarClock}  color="text-rose-600"   href="/bills"                   valueClass={s && (s.ap_due_week ?? 0) > 0 ? "text-rose-600 font-bold" : undefined} />
      </div>

      {/* AR Aging Mini-Chart */}
      {s?.ar_aging && (
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">AR Aging (Receivables)</p>
              <p className="text-[10px] text-[#1a1814]/40 mt-0.5">Outstanding invoice amounts by age bucket</p>
            </div>
            <Link href="/invoices" className="text-[11px] text-[#b8943f] font-semibold hover:text-[#8a6d2e]">View invoices →</Link>
          </div>
          <div className="h-36">
            <Bar data={agingBarData} options={{
              responsive: true, maintainAspectRatio: false,
              plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtPKR(ctx.parsed.y as number) } } },
              scales: {
                x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmtPKR(v as number) } },
              },
            } as ChartOptions<"bar">} />
          </div>
          <div className="flex items-center gap-4 mt-2 flex-wrap">
            {agingLabels.map((label, i) => (
              <span key={label} className="flex items-center gap-1 text-[10px] text-[#1a1814]/55">
                <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ backgroundColor: agingBarData.datasets[0].backgroundColor[i] }} />
                {label}: <span className="font-semibold text-[#1a1814]/75">{fmtPKR(agingValues?.[i] ?? 0)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Alert */}
      {s && (s.overdue_invoices > 0 || s.low_stock_items > 0) && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex flex-wrap gap-3 items-center">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span className="text-sm font-medium text-amber-800">Action required:</span>
          {s.overdue_invoices > 0 && <Link href="/invoices" className="text-sm text-amber-700 underline underline-offset-2 hover:text-amber-900">{s.overdue_invoices} overdue invoice{s.overdue_invoices > 1 ? "s" : ""}</Link>}
          {s.overdue_invoices > 0 && s.low_stock_items > 0 && <span className="text-amber-400">·</span>}
          {s.low_stock_items > 0 && <Link href="/products?low_stock=true" className="text-sm text-amber-700 underline underline-offset-2 hover:text-amber-900">{s.low_stock_items} low-stock product{s.low_stock_items > 1 ? "s" : ""}</Link>}
        </div>
      )}

      {/* ── Charts row 1: Revenue/Expense bar + Net Profit line ──────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">Monthly Revenue vs Expenses</p>
            <div className="flex items-center gap-3 text-[10px] font-medium text-[#1a1814]/50">
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-green-500 inline-block" />Revenue</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-red-500 inline-block" />Expenses</span>
            </div>
          </div>
          <div className="h-48 sm:h-56">
            {charts ? <Bar data={barData} options={baseChartOpts} /> : <ChartSkeleton />}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-3">Net Profit Trend</p>
          <div className="h-48 sm:h-56">
            {charts ? <Line data={lineData} options={lineOpts} /> : <ChartSkeleton />}
          </div>
        </div>
      </div>

      {/* ── Charts row 2: Expense breakdown doughnut + Top customers ─────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-3">Expense Breakdown (YTD)</p>
          <div className="h-52">
            {charts ? (
              charts.expense_breakdown.length > 0
                ? <Doughnut data={doughnutData} options={doughnutOpts} />
                : <div className="h-full flex items-center justify-center text-sm text-[#1a1814]/40">No expense data</div>
            ) : <ChartSkeleton />}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-3">Top Customers by Revenue</p>
          <div className="h-52">
            {charts ? (
              charts.top_customers.length > 0
                ? <Bar data={customerBarData} options={{ ...baseChartOpts, indexAxis: "y" } as ChartOptions<"bar">} />
                : <div className="h-full flex items-center justify-center text-sm text-[#1a1814]/40">No invoice data</div>
            ) : <ChartSkeleton />}
          </div>
        </div>
      </div>

      {/* ── Quick links + Recent transactions ───────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Quick actions */}
        <div className="bg-white rounded-xl border border-[#ede9e2] shadow-sm p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-3">Quick Actions</p>
          <div className="space-y-2">
            {[
              { label: "New Invoice",  href: "/invoices",  icon: FileSignature, color: "text-green-600" },
              { label: "New Bill",     href: "/bills",     icon: Receipt,       color: "text-orange-600" },
              { label: "New Entry",    href: "/entry",     icon: Hash,          color: "text-blue-600" },
              { label: "Products",     href: "/products",  icon: Package,       color: "text-purple-600" },
              { label: "Workflow Guide", href: "/workflow", icon: TrendingUp,   color: "text-[#b8943f]" },
              { label: "User Guide",   href: "/guide",     icon: Wallet,        color: "text-[#1a1814]" },
            ].map(({ label, href, icon: Icon, color }) => (
              <Link key={href} href={href}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg hover:bg-[#faf8f4] hover:border-[#b8943f]/30 border border-transparent transition-all group">
                <Icon className={`w-4 h-4 ${color} flex-shrink-0`} />
                <span className="text-sm font-medium text-[#1a1814]/80 group-hover:text-[#1a1814]">{label}</span>
                <ChevronRight className="w-3.5 h-3.5 text-[#1a1814]/20 ml-auto group-hover:text-[#b8943f]" />
              </Link>
            ))}
          </div>
        </div>

        {/* Recent transactions */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-[#ede9e2] shadow-sm overflow-hidden">
          <div className="px-5 py-3.5 border-b border-[#ede9e2] flex items-center justify-between">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">Recent Transactions</p>
            <Link href="/journal" className="text-[11px] text-[#b8943f] font-semibold hover:text-[#8a6d2e]">View all →</Link>
          </div>
          <div className="overflow-x-auto">
            {!data ? (
              <div className="px-5 py-6 flex flex-col gap-2.5">
                {[...Array(5)].map((_, i) => <div key={i} className="flex gap-3"><div className="shimmer h-4 w-20 rounded" /><div className="shimmer h-4 w-24 rounded" /><div className="shimmer h-4 flex-1 rounded" /></div>)}
              </div>
            ) : data.recent.length === 0 ? (
              <div className="px-5 py-8 text-center text-[#1a1814]/40 text-sm">No transactions for this period.</div>
            ) : (
              <table className="w-full text-left min-w-[420px]">
                <thead>
                  <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">
                    <th className="px-5 py-2.5">JV No.</th>
                    <th className="px-5 py-2.5">Date</th>
                    <th className="px-5 py-2.5">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ede9e2]">
                  {data.recent.map(tx => (
                    <tr key={tx.id} className="hover:bg-[#faf8f4] transition-colors text-sm">
                      <td className="px-5 py-3">
                        <Link href={`/journal?jv=${tx.jv_number}`}
                          className="font-mono text-[11px] text-[#b8943f] font-semibold hover:underline underline-offset-2 whitespace-nowrap">
                          {tx.jv_number}
                        </Link>
                      </td>
                      <td className="px-5 py-3 text-[#1a1814]/55 text-xs whitespace-nowrap">{tx.date}</td>
                      <td className="px-5 py-3 text-[#1a1814]/80 max-w-[200px] truncate">{tx.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function ChartSkeleton() {
  return <div className="h-full w-full shimmer rounded-lg" />
}

interface PrimaryKpiProps {
  label: string; value: string | null; icon: React.ElementType
  bg: string; border: string; text: string; sub?: string; compact?: boolean
}
function PrimaryKpi({ label, value, icon: Icon, bg, border, text, sub, compact }: PrimaryKpiProps) {
  return (
    <div className={`${bg} ${border} border rounded-xl p-3.5 sm:p-4 card-lift`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className={`text-[10px] font-bold uppercase tracking-[0.12em] ${text} opacity-70`}>{label}</p>
          {value === null ? <div className="shimmer h-6 w-24 rounded mt-2" /> : <p className={`${compact ? "text-xl" : "text-lg sm:text-xl"} font-bold ${text} mt-1.5 leading-none truncate`}>{value}</p>}
          {sub && <p className={`text-[10px] ${text} opacity-55 mt-1 font-medium`}>{sub}</p>}
        </div>
        <Icon className={`w-5 h-5 ${text} opacity-25 flex-shrink-0 mt-0.5`} />
      </div>
    </div>
  )
}

interface SecondaryKpiProps {
  label: string; value: string | null; icon: React.ElementType; color: string
  href: string; badge?: { count: number; label: string; color: string }; valueClass?: string
}
function SecondaryKpi({ label, value, icon: Icon, color, href, badge, valueClass }: SecondaryKpiProps) {
  return (
    <Link href={href} className="bg-white border border-[#ede9e2] rounded-xl p-3 flex flex-col gap-1.5 hover:border-[#b8943f]/40 hover:shadow-sm transition-all group">
      <div className="flex items-center gap-1.5">
        <Icon className={`w-3.5 h-3.5 ${color}`} />
        <span className="text-[10px] font-bold uppercase tracking-[0.10em] text-[#1a1814]/50">{label}</span>
      </div>
      {value === null ? <div className="shimmer h-5 w-16 rounded" /> : <p className={`text-base font-bold text-[#1a1814] leading-none ${valueClass ?? ""}`}>{value}</p>}
      {badge && <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full self-start ${badge.color}`}>{badge.count} {badge.label}</span>}
    </Link>
  )
}
