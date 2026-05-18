"use client"

import { useEffect, useState } from "react"
import { TrendingUp, TrendingDown, Hash, Wallet } from "lucide-react"
import { fmtPKR } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import DateRangePicker from "@/components/DateRangePicker"

interface DashboardData {
  summary: {
    total_revenue: number
    total_expense: number
    transaction_count: number
  }
  recent: { id: number; jv_number: string; date: string; description: string }[]
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
    apiFetch<DashboardData>(`/api/reports/dashboard?start=${start}&end=${end}`)
      .then(data => {
        if (!data.summary) throw new Error("Invalid response: missing summary")
        setData(data)
      })
      .catch(err => setError((err as Error).message))
  }, [start, end])

  if (error) return <div className="text-red-600 font-semibold p-8">Error: {error}</div>

  const netProfit = data ? data.summary.total_revenue - data.summary.total_expense : 0

  return (
    <div className="space-y-6 p-2">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-serif font-medium text-black">Dashboard</h2>
          <p className="text-sm text-black/70 mt-1">Financial overview</p>
        </div>
        <div className="p-3 bg-white border border-[#ede9e2] rounded-xl">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Total Revenue"
          value={data ? fmtPKR(data.summary.total_revenue) : "—"}
          icon={TrendingUp}
          color="green"
        />
        <KpiCard
          label="Net Profit"
          value={data ? fmtPKR(netProfit) : "—"}
          icon={Wallet}
          color={data && netProfit < 0 ? "red" : "gold"}
        />
        <KpiCard
          label="Total Expenses"
          value={data ? fmtPKR(data.summary.total_expense) : "—"}
          icon={TrendingDown}
          color="red"
        />
        <KpiCard
          label="Journal Vouchers"
          value={data ? data.summary.transaction_count.toString() : "—"}
          icon={Hash}
          color="blue"
        />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-[#ede9e2]">
          <h3 className="text-xs font-bold uppercase tracking-widest text-black/75">Recent Transactions</h3>
        </div>
        <div className="overflow-x-auto">
          {!data ? (
            <div className="px-6 py-8 text-center text-black/50">Loading...</div>
          ) : data.recent.length === 0 ? (
            <div className="px-6 py-8 text-center text-black/50">No transactions for selected period.</div>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-widest text-black/65">
                  <th className="px-6 py-3">JV No.</th>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ede9e2]">
                {data.recent.map(tx => (
                  <tr key={tx.id} className="text-sm text-black/80 hover:bg-[#f6f3ee] transition-colors">
                    <td className="px-6 py-4 font-mono text-xs text-black/70">{tx.jv_number}</td>
                    <td className="px-6 py-4 text-black/75">{tx.date}</td>
                    <td className="px-6 py-4 max-w-xs truncate text-black/75">{tx.description}</td>
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

function KpiCard({ label, value, icon: Icon, color }: { label: string; value: string; icon: any; color: string }) {
  const colorMap: Record<string, string> = {
    green: "bg-green-50 border-green-200 text-green-700",
    gold: "bg-amber-50 border-amber-200 text-amber-700",
    red: "bg-red-50 border-red-200 text-red-700",
    blue: "bg-blue-50 border-blue-200 text-blue-700",
  }
  return (
    <div className={`${colorMap[color]} border rounded-xl p-6`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold opacity-80">{label}</p>
          <p className="text-2xl font-bold mt-2">{value}</p>
        </div>
        <Icon className="w-8 h-8 opacity-40" />
      </div>
    </div>
  )
}
