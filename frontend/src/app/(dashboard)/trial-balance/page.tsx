"use client"

import { useEffect, useState } from "react"
import { Scale, Printer, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtPKR, downloadCSV } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"

interface TrialBalanceItem {
  code: string
  name: string
  type: string
  total_debit: number
  total_credit: number
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

export default function TrialBalancePage() {
  const [data, setData] = useState<TrialBalanceItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)

  useEffect(() => {
    setIsLoading(true)
    apiFetch<TrialBalanceItem[]>(`/api/reports/trial-balance?start=${start}&end=${end}`)
      .then(data => { setData(data); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [start, end])

  const grandTotalDebit = data.reduce((sum, item) => sum + item.total_debit, 0)
  const grandTotalCredit = data.reduce((sum, item) => sum + item.total_credit, 0)

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Trial Balance</h1>
          <p className="text-[#1a1814]/60">Debit and credit totals per account</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => window.print()} className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 print:hidden" title="Print">
            <Printer className="w-5 h-5" />
          </button>
          <button
            onClick={() => downloadCSV(`trial-balance-${start}-${end}.csv`, data.map(d => ({ Code: d.code, Name: d.name, Type: d.type, Debit: d.total_debit, Credit: d.total_credit })))}
            className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 print:hidden"
            title="Export CSV"
          >
            <Download className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Account</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Debit</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Credit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1a1814]/5">
            {isLoading ? (
              <tr><td colSpan={3} className="px-8 py-10 text-center text-[#1a1814]/75">Generating report...</td></tr>
            ) : data.length === 0 ? (
              <tr><td colSpan={3} className="px-8 py-10 text-center text-[#1a1814]/75">No balances found for selected period.</td></tr>
            ) : (
              data.map(item => (
                <tr key={item.code} className="hover:bg-[#f6f3ee]/30 transition-colors">
                  <td className="px-8 py-4">
                    <span className="font-mono text-xs text-[#b8943f] mr-3">{item.code}</span>
                    <span className="font-medium text-[#1a1814]">{item.name}</span>
                  </td>
                  <td className="px-8 py-4 text-right font-mono text-sm">
                    {item.total_debit > 0 ? fmtPKR(item.total_debit) : "-"}
                  </td>
                  <td className="px-8 py-4 text-right font-mono text-sm">
                    {item.total_credit > 0 ? fmtPKR(item.total_credit) : "-"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
          {!isLoading && data.length > 0 && (
            <tfoot>
              <tr className="bg-[#1a1814] text-white">
                <td className="px-8 py-5 font-bold uppercase tracking-widest text-xs">Grand Total</td>
                <td className="px-8 py-5 text-right font-mono font-bold">{fmtPKR(grandTotalDebit)}</td>
                <td className="px-8 py-5 text-right font-mono font-bold">{fmtPKR(grandTotalCredit)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {!isLoading && Math.abs(grandTotalDebit - grandTotalCredit) > 0.01 && (
        <div className="mt-6 p-4 bg-red-50 border border-red-100 text-red-700 rounded-xl text-sm flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          Warning: Trial balance is not matching. Difference: {fmtPKR(Math.abs(grandTotalDebit - grandTotalCredit))}
        </div>
      )}
    </div>
  )
}
