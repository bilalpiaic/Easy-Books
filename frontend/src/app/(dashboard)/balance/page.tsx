"use client"

import { useEffect, useState } from "react"
import { Printer, HelpCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtPKR } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"

interface BalanceItem {
  code: string
  name: string
  type: string
  balance: number
}

function today() { return new Date().toISOString().split("T")[0] }

export default function BalanceSheetPage() {
  const [data, setData] = useState<BalanceItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [asOf, setAsOf] = useState(today())

  useEffect(() => {
    setIsLoading(true)
    apiFetch<BalanceItem[]>(`/api/reports/balance-sheet?end=${asOf}`)
      .then(data => { setData(data); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [asOf])

  const assets = data.filter(i => i.type === "Asset")
  const liabilities = data.filter(i => i.type === "Liability")
  const equity = data.filter(i => i.type === "Equity")

  const totalAssets = assets.reduce((sum, i) => sum + i.balance, 0)
  const totalLiabilities = liabilities.reduce((sum, i) => sum + i.balance, 0)
  const totalEquity = equity.reduce((sum, i) => sum + i.balance, 0)
  const totalLE = totalLiabilities + totalEquity
  const isBalanced = Math.abs(totalAssets - totalLE) <= 0.01

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Balance Sheet</h1>
          <p className="text-[#1a1814]/60">Financial position as of {new Date(asOf).toLocaleDateString()}</p>
        </div>
        <button onClick={() => window.print()} className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 print:hidden" title="Print">
          <Printer className="w-5 h-5" />
        </button>
      </div>

      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl flex items-center gap-3 flex-wrap">
        <span className="text-xs font-bold uppercase tracking-widest text-black/50">As of</span>
        <input
          type="date"
          value={asOf}
          onChange={(e) => setAsOf(e.target.value)}
          className="px-3 py-1.5 text-sm border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
        />
      </div>

      {isLoading ? (
        <div className="text-center py-20 text-[#1a1814]/75">Generating report...</div>
      ) : (
        <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 p-10 space-y-12">
          {/* Assets */}
          <section className="space-y-4">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 border-b border-[#1a1814]/5 pb-2">Assets</h3>
            {assets.map(item => (
              <div key={item.code} className="flex justify-between text-sm">
                <span className="text-[#1a1814]/60">{item.name}</span>
                <span className="font-mono">{fmtPKR(item.balance)}</span>
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
              <div key={item.code} className="flex justify-between text-sm">
                <span className="text-[#1a1814]/60">{item.name}</span>
                <span className="font-mono">{fmtPKR(item.balance)}</span>
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
              <div key={item.code} className="flex justify-between text-sm">
                <span className={`${item.code === "RE-CUR" ? "text-[#1a1814] font-medium italic" : "text-[#1a1814]/60"}`}>
                  {item.name}
                </span>
                <span className="font-mono">{fmtPKR(item.balance)}</span>
              </div>
            ))}
            <div className="flex justify-between pt-4 border-t border-[#1a1814]/5 font-bold">
              <span className="text-[#1a1814]">Total Equity</span>
              <span className="font-mono underline underline-offset-4">{fmtPKR(totalEquity)}</span>
            </div>
          </section>

          {/* Summary */}
          <section className="pt-8 border-t-2 border-[#1a1814] flex justify-between items-center bg-[#f6f3ee]/30 -mx-10 px-10 py-6">
            <h2 className="text-xl font-serif text-[#1a1814]">Total Liabilities &amp; Equity</h2>
            <div className="text-2xl font-serif text-[#1a1814]">{fmtPKR(totalLE)}</div>
          </section>

          {!isBalanced && (
            <div className="p-4 bg-orange-50 border border-orange-100 text-orange-700 rounded-xl text-xs flex items-center gap-3 italic">
              <HelpCircle className="w-4 h-4" />
              Balance sheet is out by {fmtPKR(Math.abs(totalAssets - totalLE))}. Check for missing entries or run year-end closing.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
