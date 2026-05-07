"use client"

import { useEffect, useState } from "react"
import { TrendingUp, TrendingDown, ClipboardList, Wallet } from "lucide-react"
import { fmtPKR } from "@/lib/utils"

interface DashboardData {
  summary: {
    total_revenue: number
    total_expense: number
  }
  recent: any[]
import { getAuthHeader } from "@/lib/auth"

interface DashboardData {
...
export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)

  useEffect(() => {
    fetch("http://localhost:8000/api/reports/dashboard", {
      headers: getAuthHeader()
    })
      .then(res => res.json())
      .then(setData)
      .catch(console.error)
  }, [])


  if (!data) return <div>Loading...</div>

  const netProfit = data.summary.total_revenue - data.summary.total_expense

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-serif font-medium">Dashboard</h2>
        <p className="text-sm text-black/50 mt-1">Financial overview · March 2025 – February 2026</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard 
          label="Total Revenue" 
          value={fmtPKR(data.summary.total_revenue)} 
          icon={TrendingUp}
          color="green"
        />
        <KpiCard 
          label="Net Profit" 
          value={fmtPKR(netProfit)} 
          icon={Wallet}
          color="gold"
        />
        <KpiCard 
          label="Total Expenses" 
          value={fmtPKR(data.summary.total_expense)} 
          icon={TrendingDown}
          color="red"
        />
        <KpiCard 
          label="Transactions" 
          value={data.recent.length.toString()} 
          icon={ClipboardList}
          color="blue"
        />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-[#ede9e2]">
          <h3 className="text-xs font-bold uppercase tracking-widest text-black/40">Recent Transactions</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-widest text-black/30">
                <th className="px-6 py-3">JV No.</th>
                <th className="px-6 py-3">Date</th>
                <th className="px-6 py-3">Description</th>
                <th className="px-6 py-3 text-right">Amount (PKR)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {data.recent.map((tx: any) => (
                <tr key={tx.id} className="text-sm hover:bg-[#f6f3ee] transition-colors">
                  <td className="px-6 py-4 font-mono text-xs">{tx.jv_number}</td>
                  <td className="px-6 py-4">{tx.date}</td>
                  <td className="px-6 py-4 max-w-xs truncate">{tx.description}</td>
                  <td className="px-6 py-4 text-right font-medium">{fmtPKR(tx.total_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function KpiCard({ label, value, icon: Icon, color }: any) {
  const colors: any = {
    green: "before:bg-[#2a7d4f]",
    gold: "before:bg-[#b8943f]",
    red: "before:bg-[#c0392b]",
    blue: "before:bg-[#1e5fa8]",
  }

  return (
    <div className={`bg-white p-6 rounded-xl border border-[#ede9e2] shadow-sm relative overflow-hidden before:absolute before:top-0 before:left-0 before:right-0 before:h-0.5 ${colors[color]}`}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[11px] font-medium text-black/50 uppercase tracking-wider">{label}</p>
        <Icon className="w-4 h-4 text-black/20" />
      </div>
      <p className="text-xl font-bold">{value}</p>
    </div>
  )
}
