"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  TrendingUp, TrendingDown, Hash, Wallet,
  ArrowDownLeft, ArrowUpRight, AlertTriangle,
  Package, Clock, Receipt, FileSignature,
  ChevronRight,
} from "lucide-react"
import { fmtPKR } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import DateRangePicker from "@/components/DateRangePicker"

interface DashboardSummary {
  total_revenue: number
  total_expense: number
  transaction_count: number
  ar_outstanding: number
  ap_outstanding: number
  overdue_invoices: number
  unpaid_bills: number
  low_stock_items: number
}

interface RecentTx {
  id: number
  jv_number: string
  date: string
  description: string
}

interface DashboardData {
  summary: DashboardSummary
  recent: RecentTx[]
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

export default function Dashboard() {
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setData(null)
    apiFetch<DashboardData>(`/api/reports/dashboard?start=${start}&end=${end}`)
      .then(d => { if (!d.summary) throw new Error("Invalid response"); setData(d) })
      .catch(err => setError((err as Error).message))
  }, [start, end])

  const s = data?.summary
  const netProfit = s ? s.total_revenue - s.total_expense : 0
  const margin = s && s.total_revenue > 0 ? (netProfit / s.total_revenue * 100).toFixed(1) : null

  return (
    <div className="space-y-5">
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

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 font-medium">
          {error}
        </div>
      )}

      {/* Primary KPIs — 2×2 on mobile, 4 across on md+ */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <PrimaryKpi
          label="Revenue"
          value={s ? fmtPKR(s.total_revenue) : null}
          icon={TrendingUp}
          accent="#16a34a"
          bg="bg-green-50"
          border="border-green-200"
          text="text-green-800"
          sub={margin ? `${margin}% margin` : undefined}
        />
        <PrimaryKpi
          label="Expenses"
          value={s ? fmtPKR(s.total_expense) : null}
          icon={TrendingDown}
          accent="#dc2626"
          bg="bg-red-50"
          border="border-red-200"
          text="text-red-800"
        />
        <PrimaryKpi
          label="Net Profit"
          value={s ? fmtPKR(netProfit) : null}
          icon={Wallet}
          accent={netProfit < 0 ? "#dc2626" : "#b8943f"}
          bg={netProfit < 0 ? "bg-red-50" : "bg-amber-50"}
          border={netProfit < 0 ? "border-red-200" : "border-amber-200"}
          text={netProfit < 0 ? "text-red-800" : "text-amber-800"}
          sub={netProfit < 0 ? "Net loss" : "Net gain"}
        />
        <PrimaryKpi
          label="Vouchers"
          value={s ? s.transaction_count.toString() : null}
          icon={Hash}
          accent="#2563eb"
          bg="bg-blue-50"
          border="border-blue-200"
          text="text-blue-800"
          sub="journal entries"
          compact
        />
      </div>

      {/* Secondary metrics row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SecondaryKpi
          label="AR Outstanding"
          value={s ? fmtPKR(s.ar_outstanding) : null}
          icon={ArrowDownLeft}
          color="text-green-700"
          href="/invoices"
          badge={s?.overdue_invoices ? { count: s.overdue_invoices, label: "overdue", color: "bg-red-100 text-red-700" } : undefined}
        />
        <SecondaryKpi
          label="AP Outstanding"
          value={s ? fmtPKR(s.ap_outstanding) : null}
          icon={ArrowUpRight}
          color="text-orange-700"
          href="/bills"
          badge={s?.unpaid_bills ? { count: s.unpaid_bills, label: "unpaid", color: "bg-orange-100 text-orange-700" } : undefined}
        />
        <SecondaryKpi
          label="Overdue Invoices"
          value={s ? s.overdue_invoices.toString() : null}
          icon={Clock}
          color="text-red-600"
          href="/invoices"
          valueClass={s && s.overdue_invoices > 0 ? "text-red-600 font-bold" : undefined}
        />
        <SecondaryKpi
          label="Low Stock Items"
          value={s ? s.low_stock_items.toString() : null}
          icon={Package}
          color="text-purple-600"
          href="/products"
          valueClass={s && s.low_stock_items > 0 ? "text-amber-600 font-bold" : undefined}
        />
      </div>

      {/* Alert banner — only shown when there are actionable items */}
      {s && (s.overdue_invoices > 0 || s.low_stock_items > 0) && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex flex-wrap gap-3 items-center">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span className="text-sm font-medium text-amber-800">Action required:</span>
          {s.overdue_invoices > 0 && (
            <Link href="/invoices" className="text-sm text-amber-700 underline underline-offset-2 hover:text-amber-900">
              {s.overdue_invoices} overdue invoice{s.overdue_invoices > 1 ? "s" : ""}
            </Link>
          )}
          {s.overdue_invoices > 0 && s.low_stock_items > 0 && <span className="text-amber-400">·</span>}
          {s.low_stock_items > 0 && (
            <Link href="/products" className="text-sm text-amber-700 underline underline-offset-2 hover:text-amber-900">
              {s.low_stock_items} low-stock product{s.low_stock_items > 1 ? "s" : ""}
            </Link>
          )}
        </div>
      )}

      {/* Quick links */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "New Invoice",  href: "/invoices",          icon: FileSignature, color: "text-green-600" },
          { label: "New Bill",     href: "/bills",             icon: Receipt,       color: "text-orange-600" },
          { label: "New Entry",    href: "/entry",             icon: Hash,          color: "text-blue-600" },
          { label: "Products",     href: "/products",          icon: Package,       color: "text-purple-600" },
        ].map(({ label, href, icon: Icon, color }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-2.5 bg-white border border-[#ede9e2] rounded-xl px-4 py-3 hover:border-[#b8943f]/40 hover:bg-[#faf8f4] transition-all group shadow-sm"
          >
            <Icon className={`w-4 h-4 ${color} flex-shrink-0`} />
            <span className="text-sm font-medium text-[#1a1814]/80 group-hover:text-[#1a1814] truncate">{label}</span>
            <ChevronRight className="w-3.5 h-3.5 text-[#1a1814]/30 ml-auto group-hover:text-[#b8943f] transition-colors" />
          </Link>
        ))}
      </div>

      {/* Recent transactions */}
      <div className="bg-white rounded-xl border border-[#ede9e2] shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b border-[#ede9e2] flex items-center justify-between">
          <h3 className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/60">Recent Transactions</h3>
          <Link href="/journal" className="text-[11px] text-[#b8943f] font-semibold hover:text-[#8a6d2e] transition-colors">
            View all →
          </Link>
        </div>
        <div className="table-scroll">
          {!data ? (
            <div className="px-5 py-10 flex flex-col gap-2.5">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex gap-3">
                  <div className="shimmer h-4 w-20 rounded" />
                  <div className="shimmer h-4 w-24 rounded" />
                  <div className="shimmer h-4 flex-1 rounded" />
                </div>
              ))}
            </div>
          ) : data.recent.length === 0 ? (
            <div className="px-5 py-10 text-center text-[#1a1814]/40 text-sm">
              No transactions for this period.
            </div>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">
                  <th className="px-5 py-2.5 whitespace-nowrap">JV No.</th>
                  <th className="px-5 py-2.5 whitespace-nowrap">Date</th>
                  <th className="px-5 py-2.5">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ede9e2]">
                {data.recent.map(tx => (
                  <tr key={tx.id} className="text-sm hover:bg-[#faf8f4] transition-colors">
                    <td className="px-5 py-3 font-mono text-[11px] text-[#b8943f] font-semibold whitespace-nowrap">{tx.jv_number}</td>
                    <td className="px-5 py-3 text-[#1a1814]/60 text-xs whitespace-nowrap">{tx.date}</td>
                    <td className="px-5 py-3 text-[#1a1814]/80 max-w-[240px] truncate">{tx.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

interface PrimaryKpiProps {
  label: string
  value: string | null
  icon: React.ElementType
  accent: string
  bg: string
  border: string
  text: string
  sub?: string
  compact?: boolean
}

function PrimaryKpi({ label, value, icon: Icon, bg, border, text, sub, compact }: PrimaryKpiProps) {
  return (
    <div className={`${bg} ${border} border rounded-xl p-4 card-lift`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className={`text-[10px] font-bold uppercase tracking-[0.12em] ${text} opacity-70`}>{label}</p>
          {value === null ? (
            <div className="shimmer h-6 w-24 rounded mt-2" />
          ) : (
            <p className={`${compact ? "text-xl" : "text-lg sm:text-xl"} font-bold ${text} mt-1.5 leading-none truncate`}>{value}</p>
          )}
          {sub && <p className={`text-[10px] ${text} opacity-55 mt-1.5 font-medium`}>{sub}</p>}
        </div>
        <Icon className={`w-5 h-5 ${text} opacity-30 flex-shrink-0 mt-0.5`} />
      </div>
    </div>
  )
}

interface Badge { count: number; label: string; color: string }

interface SecondaryKpiProps {
  label: string
  value: string | null
  icon: React.ElementType
  color: string
  href: string
  badge?: Badge
  valueClass?: string
}

function SecondaryKpi({ label, value, icon: Icon, color, href, badge, valueClass }: SecondaryKpiProps) {
  return (
    <Link
      href={href}
      className="bg-white border border-[#ede9e2] rounded-xl p-3.5 flex flex-col gap-2 hover:border-[#b8943f]/40 hover:shadow-sm transition-all group"
    >
      <div className="flex items-center gap-1.5">
        <Icon className={`w-3.5 h-3.5 ${color}`} />
        <span className="text-[10px] font-bold uppercase tracking-[0.10em] text-[#1a1814]/50">{label}</span>
      </div>
      {value === null ? (
        <div className="shimmer h-5 w-16 rounded" />
      ) : (
        <p className={`text-base font-bold text-[#1a1814] leading-none ${valueClass ?? ""}`}>{value}</p>
      )}
      {badge && (
        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full self-start ${badge.color}`}>
          {badge.count} {badge.label}
        </span>
      )}
    </Link>
  )
}
