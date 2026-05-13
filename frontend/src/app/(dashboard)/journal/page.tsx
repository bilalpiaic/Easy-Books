"use client"

import { useEffect, useState } from "react"
import { ClipboardList, Filter } from "lucide-react"
import { getAuthHeader } from "@/lib/auth"
import { fmtPKR } from "@/lib/utils"

interface JournalEntry {
  id: number
  jv_number: string
  date: string
  description: string
  account_name: string
  debit: number
  credit: number
}

export default function JournalPage() {
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetch("http://localhost:8000/api/reports/journal", {
      headers: getAuthHeader()
    })
      .then(res => res.json())
      .then(data => {
        setEntries(data)
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
          <h1 className="text-3xl font-serif text-[#1a1814]">General Journal</h1>
          <p className="text-[#1a1814]/60">Chronological record of all financial transactions</p>
        </div>
        <button className="bg-white border border-[#1a1814]/10 text-[#1a1814] font-bold px-6 py-3 rounded-xl flex items-center gap-2 hover:bg-[#f6f3ee] transition-colors">
          <Filter className="w-5 h-5" />
          Filter
        </button>
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/40">Date</th>
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/40">JV #</th>
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/40">Account & Description</th>
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 text-right">Debit</th>
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 text-right">Credit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1a1814]/5">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center text-[#1a1814]/40">Loading journal entries...</td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center text-[#1a1814]/40">No entries found.</td>
              </tr>
            ) : (
              entries.map((entry, idx) => (
                <tr key={idx} className="hover:bg-[#f6f3ee]/50 transition-colors">
                  <td className="px-6 py-5 text-sm">{entry.date}</td>
                  <td className="px-6 py-5 font-mono text-xs font-bold text-[#b8943f]">{entry.jv_number}</td>
                  <td className="px-6 py-5">
                    <div className="font-medium text-[#1a1814]">{entry.account_name}</div>
                    <div className="text-xs text-[#1a1814]/40">{entry.description}</div>
                  </td>
                  <td className="px-6 py-5 text-right font-mono text-sm">
                    {entry.debit > 0 ? fmtPKR(entry.debit) : "-"}
                  </td>
                  <td className="px-6 py-5 text-right font-mono text-sm">
                    {entry.credit > 0 ? fmtPKR(entry.credit) : "-"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
