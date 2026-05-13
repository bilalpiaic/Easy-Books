"use client"

import { useEffect, useState } from "react"
import { BookOpen, Search } from "lucide-react"
import { getAuthHeader } from "@/lib/auth"
import { fmtPKR } from "@/lib/utils"

export default function LedgerPage() {
  const [ledgerData, setLedgerData] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Note: Reusing journal report but in a real app, this would be grouped by account
    fetch("http://localhost:8000/api/reports/journal", {
      headers: getAuthHeader()
    })
      .then(res => res.json())
      .then(data => {
        // Simple grouping for prototype
        const grouped = data.reduce((acc: any, entry: any) => {
          if (!acc[entry.account_name]) acc[entry.account_name] = []
          acc[entry.account_name].push(entry)
          return acc
        }, {})
        setLedgerData(Object.entries(grouped))
        setIsLoading(false)
      })
      .catch(err => {
        console.error(err)
        setIsLoading(false)
      })
  }, [])

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">General Ledger</h1>
          <p className="text-[#1a1814]/60">Detailed transaction history grouped by account</p>
        </div>
        <div className="relative">
          <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-[#1a1814]/30" />
          <input 
            type="text" 
            placeholder="Search accounts..." 
            className="pl-12 pr-6 py-3 bg-white border border-[#1a1814]/10 rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] focus:border-transparent"
          />
        </div>
      </div>

      <div className="space-y-8">
        {isLoading ? (
          <div className="text-center py-20 text-[#1a1814]/40">Loading ledger...</div>
        ) : ledgerData.length === 0 ? (
          <div className="text-center py-20 text-[#1a1814]/40">No transactions recorded yet.</div>
        ) : (
          ledgerData.map(([accountName, entries]: [any, any]) => (
            <div key={accountName} className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
              <div className="bg-[#f6f3ee] px-8 py-4 border-b border-[#1a1814]/5 flex justify-between items-center">
                <h3 className="font-serif text-lg text-[#1a1814]">{accountName}</h3>
                <span className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">Account Activity</span>
              </div>
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-[#1a1814]/5">
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">Date</th>
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">Description</th>
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 text-right">Debit</th>
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 text-right">Credit</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1a1814]/5">
                  {entries.map((entry: any, idx: number) => (
                    <tr key={idx} className="hover:bg-[#f6f3ee]/30">
                      <td className="px-8 py-4 text-sm">{entry.date}</td>
                      <td className="px-8 py-4 text-sm text-[#1a1814]/60">{entry.description}</td>
                      <td className="px-8 py-4 text-right font-mono text-sm">{entry.debit > 0 ? fmtPKR(entry.debit) : "-"}</td>
                      <td className="px-8 py-4 text-right font-mono text-sm">{entry.credit > 0 ? fmtPKR(entry.credit) : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
