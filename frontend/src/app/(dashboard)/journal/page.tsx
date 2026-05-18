"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtPKR } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"

interface JournalEntry {
  id: number
  jv_number: string
  date: string
  description: string
  account_name: string
  debit: number
  credit: number
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

export default function JournalPage() {
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setIsLoading(true)
    apiFetch<JournalEntry[]>(`/api/reports/journal?start=${start}&end=${end}`)
      .then(data => { setEntries(data); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [start, end])

  return (
    <div className="p-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">General Journal</h1>
          <p className="text-[#1a1814]/60">Chronological record of all financial transactions</p>
        </div>
      </div>

      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Date</th>
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">JV #</th>
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Account &amp; Description</th>
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Debit</th>
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Credit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1a1814]/5">
            {isLoading ? (
              <tr><td colSpan={5} className="px-6 py-10 text-center text-[#1a1814]/75">Loading journal entries...</td></tr>
            ) : entries.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-10 text-center text-[#1a1814]/75">No entries found for selected period.</td></tr>
            ) : (
              entries.map((entry, idx) => (
                <tr key={idx} className="hover:bg-[#f6f3ee]/50 transition-colors">
                  <td className="px-6 py-5 text-sm">{entry.date}</td>
                  <td className="px-6 py-5 font-mono text-xs font-bold text-[#b8943f]">{entry.jv_number}</td>
                  <td className="px-6 py-5">
                    <div className="font-medium text-[#1a1814]">{entry.account_name}</div>
                    <div className="text-xs text-[#1a1814]/75">{entry.description}</div>
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
