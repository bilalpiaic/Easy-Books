"use client"

import { useEffect, useState } from "react"
import { RotateCcw, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtPKR, downloadCSV } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import Pagination from "@/components/Pagination"
import SkeletonRow from "@/components/SkeletonRow"

interface JournalEntry {
  id: number
  transaction_id: number
  jv_number: string
  date: string
  description: string
  account_name: string
  debit: number
  credit: number
  is_reversed: boolean
}

interface JournalResponse {
  total: number
  items: JournalEntry[]
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

const PAGE_SIZE = 50

export default function JournalPage() {
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [reversing, setReversing] = useState<number | null>(null)

  useEffect(() => {
    setPage(1)
  }, [start, end])

  const loadEntries = () => {
    setIsLoading(true)
    const skip = (page - 1) * PAGE_SIZE
    apiFetch<JournalResponse>(`/api/reports/journal?start=${start}&end=${end}&skip=${skip}&limit=${PAGE_SIZE}`)
      .then(data => { setEntries(data.items); setTotal(data.total); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }

  useEffect(loadEntries, [start, end, page])

  const handleReverse = async (entry: JournalEntry) => {
    if (!window.confirm(`Reverse ${entry.jv_number}? A new equal-and-opposite JV will be posted today.`)) return
    setReversing(entry.transaction_id)
    try {
      const result = await apiFetch<{ reversal_jv_number: string }>(`/api/transactions/${entry.transaction_id}/reverse`, { method: "POST" })
      alert(`Reversal posted as ${result.reversal_jv_number}`)
      loadEntries()
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setReversing(null)
    }
  }

  return (
    <div className="p-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">General Journal</h1>
          <p className="text-[#1a1814]/60">Chronological record of all financial transactions</p>
        </div>
        <button
          onClick={() => downloadCSV(`journal-${start}-${end}.csv`, entries.map(e => ({ Date: e.date, JV: e.jv_number, Account: e.account_name, Description: e.description, Debit: e.debit, Credit: e.credit })))}
          className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold hover:bg-[#f6f3ee] transition-colors print:hidden"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </button>
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
              <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1a1814]/5">
            {isLoading ? (
              <SkeletonRow cols={6} />
            ) : entries.length === 0 ? (
              <tr><td colSpan={6} className="px-6 py-10 text-center text-[#1a1814]/75">No entries found for selected period.</td></tr>
            ) : (() => {
                const seenTxns = new Set<number>()
                return entries.map((entry, idx) => {
                  const isFirstLine = !seenTxns.has(entry.transaction_id)
                  if (isFirstLine) seenTxns.add(entry.transaction_id)
                  return (
                    <tr key={idx} className={`hover:bg-[#f6f3ee]/50 transition-colors ${entry.is_reversed ? 'opacity-60' : ''}`}>
                      <td className="px-6 py-5 text-sm">{entry.date}</td>
                      <td className="px-6 py-5">
                        <span className="font-mono text-xs font-bold text-[#b8943f]">{entry.jv_number}</span>
                        {entry.is_reversed && isFirstLine && (
                          <span className="ml-2 px-2 py-0.5 bg-gray-100 text-gray-500 text-[10px] font-bold uppercase rounded-full">Reversed</span>
                        )}
                      </td>
                      <td className="px-6 py-5">
                        <div className="font-medium text-[#1a1814]">{entry.account_name}</div>
                        <div className="text-xs text-[#1a1814]/75">{entry.description}</div>
                      </td>
                      <td className="px-6 py-5 text-right font-mono text-sm">{entry.debit > 0 ? fmtPKR(entry.debit) : "-"}</td>
                      <td className="px-6 py-5 text-right font-mono text-sm">{entry.credit > 0 ? fmtPKR(entry.credit) : "-"}</td>
                      <td className="px-6 py-5">
                        {isFirstLine && !entry.is_reversed && (
                          <button
                            onClick={() => handleReverse(entry)}
                            disabled={reversing === entry.transaction_id}
                            className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-[#1a1814]/60 hover:text-[#b8943f] hover:bg-[#f6f3ee] rounded-lg transition-colors disabled:opacity-50"
                            title="Reverse this entry"
                          >
                            <RotateCcw className="w-3 h-3" />
                            Reverse
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })
              })()
            }
          </tbody>
        </table>
        <div className="border-t border-[#1a1814]/5 px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>
    </div>
  )
}
