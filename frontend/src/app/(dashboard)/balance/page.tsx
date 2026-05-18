"use client"

import { useEffect, useState } from "react"
import { PieChart, Printer, Download, HelpCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtPKR } from "@/lib/utils"

interface BalanceItem {
  name: string
  type: string
  total_debit: number
  total_credit: number
}

export default function BalanceSheetPage() {
  const [data, setData] = useState<BalanceItem[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    apiFetch<BalanceItem[]>("/api/reports/trial-balance")
      .then(data => { setData(data); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [])

  const assets = data.filter(i => i.type === 'Asset')
  const liabilities = data.filter(i => i.type === 'Liability')
  const equity = data.filter(i => i.type === 'Equity')

  const totalAssets = assets.reduce((sum, i) => sum + (i.total_debit - i.total_credit), 0)
  const totalLiabilities = liabilities.reduce((sum, i) => sum + (i.total_credit - i.total_debit), 0)
  const totalEquity = equity.reduce((sum, i) => sum + (i.total_credit - i.total_debit), 0)

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Balance Sheet</h1>
          <p className="text-[#1a1814]/60">Financial position as of {new Date().toLocaleDateString()}</p>
        </div>
        <div className="flex gap-3">
          <button className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60">
            <Printer className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 p-10 space-y-12">
        {/* Assets */}
        <section className="space-y-4">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 border-b border-[#1a1814]/5 pb-2">Assets</h3>
          {assets.map(item => (
            <div key={item.name} className="flex justify-between text-sm">
              <span className="text-[#1a1814]/60">{item.name}</span>
              <span className="font-mono">{fmtPKR(item.total_debit - item.total_credit)}</span>
            </div>
          ))}
          <div className="flex justify-between pt-4 border-t border-[#1a1814]/5 font-bold">
            <span className="text-[#1a1814]">Total Assets</span>
            <span className="font-mono underline decoration-double underline-offset-4">{fmtPKR(totalAssets)}</span>
          </div>
        </section>

        {/* Liabilities */}
        <section className="space-y-4">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 border-b border-[#1a1814]/5 pb-2">Liabilities</h3>
          {liabilities.map(item => (
            <div key={item.name} className="flex justify-between text-sm">
              <span className="text-[#1a1814]/60">{item.name}</span>
              <span className="font-mono">{fmtPKR(item.total_credit - item.total_debit)}</span>
            </div>
          ))}
          <div className="flex justify-between pt-4 border-t border-[#1a1814]/5 font-bold">
            <span className="text-[#1a1814]">Total Liabilities</span>
            <span className="font-mono underline underline-offset-4">{fmtPKR(totalLiabilities)}</span>
          </div>
        </section>

        {/* Equity */}
        <section className="space-y-4">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 border-b border-[#1a1814]/5 pb-2">Equity</h3>
          {equity.map(item => (
            <div key={item.name} className="flex justify-between text-sm">
              <span className="text-[#1a1814]/60">{item.name}</span>
              <span className="font-mono">{fmtPKR(item.total_credit - item.total_debit)}</span>
            </div>
          ))}
          <div className="flex justify-between pt-4 border-t border-[#1a1814]/5 font-bold">
            <span className="text-[#1a1814]">Total Equity</span>
            <span className="font-mono underline underline-offset-4">{fmtPKR(totalEquity)}</span>
          </div>
        </section>

        {/* Summary check */}
        <section className="pt-8 border-t-2 border-[#1a1814] flex justify-between items-center bg-[#f6f3ee]/30 -mx-10 px-10 py-6">
          <div>
            <h2 className="text-xl font-serif text-[#1a1814]">Total Liabilities & Equity</h2>
          </div>
          <div className="text-2xl font-serif text-[#1a1814]">
            {fmtPKR(totalLiabilities + totalEquity)}
          </div>
        </section>

        {Math.abs(totalAssets - (totalLiabilities + totalEquity)) > 0.01 && (
          <div className="p-4 bg-orange-50 border border-orange-100 text-orange-700 rounded-xl text-xs flex items-center gap-3 italic">
            <HelpCircle className="w-4 h-4" />
            Note: Current balance sheet excludes current period retained earnings. Run year-end closing for full alignment.
          </div>
        )}
      </div>
    </div>
  )
}
