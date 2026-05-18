"use client"

import { useEffect, useState } from "react"
import { TrendingUp, Printer, Download, Calendar } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtPKR } from "@/lib/utils"

interface PnLItem {
  name: string
  type: string
  total_debit: number
  total_credit: number
}

export default function PnLPage() {
  const [data, setData] = useState<PnLItem[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    apiFetch<PnLItem[]>("/api/reports/income-statement")
      .then(data => { setData(data); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [])

  const revenueItems = data.filter(i => i.type === 'Revenue')
  const expenseItems = data.filter(i => i.type === 'Expense')

  const totalRevenue = revenueItems.reduce((sum, i) => sum + (i.total_credit - i.total_debit), 0)
  const totalExpense = expenseItems.reduce((sum, i) => sum + (i.total_debit - i.total_credit), 0)
  const netIncome = totalRevenue - totalExpense

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Income Statement</h1>
          <p className="text-[#1a1814]/60">For the period ending {new Date().toLocaleDateString()}</p>
        </div>
        <div className="flex gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-white border border-[#1a1814]/10 rounded-xl text-xs font-bold text-[#1a1814]/60 hover:bg-[#f6f3ee] transition-colors">
            <Calendar className="w-4 h-4" />
            Last 30 Days
          </button>
          <button className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60">
            <Printer className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 p-10 space-y-12">
        {/* Revenue Section */}
        <section className="space-y-4">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 border-b border-[#1a1814]/5 pb-2">Revenue</h3>
          {isLoading ? (
            <div className="text-sm text-[#1a1814]/75 italic">Loading...</div>
          ) : revenueItems.length === 0 ? (
            <div className="text-sm text-[#1a1814]/75 italic">No revenue recorded.</div>
          ) : (
            revenueItems.map(item => (
              <div key={item.name} className="flex justify-between text-sm">
                <span className="text-[#1a1814]/60">{item.name}</span>
                <span className="font-mono">{fmtPKR(item.total_credit - item.total_debit)}</span>
              </div>
            ))
          )}
          <div className="flex justify-between pt-4 border-t border-[#1a1814]/5 font-bold">
            <span className="text-[#1a1814]">Total Revenue</span>
            <span className="font-mono underline decoration-double underline-offset-4">{fmtPKR(totalRevenue)}</span>
          </div>
        </section>

        {/* Expense Section */}
        <section className="space-y-4">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 border-b border-[#1a1814]/5 pb-2">Expenses</h3>
          {isLoading ? (
            <div className="text-sm text-[#1a1814]/75 italic">Loading...</div>
          ) : expenseItems.length === 0 ? (
            <div className="text-sm text-[#1a1814]/75 italic">No expenses recorded.</div>
          ) : (
            expenseItems.map(item => (
              <div key={item.name} className="flex justify-between text-sm">
                <span className="text-[#1a1814]/60">{item.name}</span>
                <span className="font-mono">({fmtPKR(item.total_debit - item.total_credit)})</span>
              </div>
            ))
          )}
          <div className="flex justify-between pt-4 border-t border-[#1a1814]/5 font-bold text-red-600">
            <span>Total Operating Expenses</span>
            <span className="font-mono">({fmtPKR(totalExpense)})</span>
          </div>
        </section>

        {/* Net Income */}
        <section className="pt-8 border-t-2 border-[#1a1814] flex justify-between items-end">
          <div>
            <h2 className="text-2xl font-serif text-[#1a1814]">Net Income</h2>
            <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75">Bottom Line Performance</p>
          </div>
          <div className={`text-3xl font-serif ${netIncome >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {netIncome < 0 && "("}{fmtPKR(Math.abs(netIncome))}{netIncome < 0 && ")"}
          </div>
        </section>
      </div>
    </div>
  )
}
