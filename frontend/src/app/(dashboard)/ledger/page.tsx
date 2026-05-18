"use client"

import { useEffect, useState } from "react"
import { Search } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtPKR } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import Pagination from "@/components/Pagination"

interface LedgerEntry {
  date: string
  jv_number: string
  description: string
  debit: number
  credit: number
  balance: number
}

interface LedgerAccount {
  code: string
  name: string
  type: string
  entries: LedgerEntry[]
  running_balance: number
}

interface LedgerResponse {
  total: number
  items: LedgerAccount[]
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

const PAGE_SIZE = 20

export default function LedgerPage() {
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [search, setSearch] = useState("")
  const [ledgerData, setLedgerData] = useState<LedgerAccount[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => { setPage(1) }, [start, end, search])

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams({ start, end, skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (search) params.set("search", search)
    apiFetch<LedgerResponse>(`/api/reports/ledger?${params}`)
      .then(data => { setLedgerData(data.items); setTotal(data.total); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [start, end, search, page])

  return (
    <div className="p-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">General Ledger</h1>
          <p className="text-[#1a1814]/60">Transaction history with running balance per account</p>
        </div>
        <div className="relative">
          <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-[#1a1814]/75" />
          <input
            type="text"
            placeholder="Search accounts..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-12 pr-6 py-3 bg-white border border-[#1a1814]/10 rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] focus:border-transparent"
          />
        </div>
      </div>

      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
      </div>

      <div className="space-y-8">
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="bg-white rounded-3xl border border-[#1a1814]/5 overflow-hidden animate-pulse">
                <div className="bg-[#f6f3ee] px-8 py-4 h-14" />
                <div className="p-6 space-y-3">
                  {[1,2,3].map(j => <div key={j} className="h-4 bg-[#f0ece4] rounded" />)}
                </div>
              </div>
            ))}
          </div>
        ) : ledgerData.length === 0 ? (
          <div className="text-center py-20 text-[#1a1814]/75">No transactions for selected period.</div>
        ) : (
          ledgerData.map(account => (
            <div key={account.code} className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
              <div className="bg-[#f6f3ee] px-8 py-4 border-b border-[#1a1814]/5 flex justify-between items-center">
                <div>
                  <span className="font-mono text-xs text-[#b8943f] mr-3">{account.code}</span>
                  <span className="font-serif text-lg text-[#1a1814]">{account.name}</span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 block">Closing Balance</span>
                  <span className={`font-mono font-bold text-sm ${account.running_balance >= 0 ? "text-[#1a1814]" : "text-red-600"}`}>
                    {fmtPKR(account.running_balance)}
                  </span>
                </div>
              </div>
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-[#1a1814]/5">
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75">Date</th>
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75">JV #</th>
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75">Description</th>
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Debit</th>
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Credit</th>
                    <th className="px-8 py-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Balance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1a1814]/5">
                  {account.entries.map((entry, idx) => (
                    <tr key={idx} className="hover:bg-[#f6f3ee]/30">
                      <td className="px-8 py-4 text-sm">{entry.date}</td>
                      <td className="px-8 py-4 font-mono text-xs text-[#b8943f]">{entry.jv_number}</td>
                      <td className="px-8 py-4 text-sm text-[#1a1814]/60">{entry.description}</td>
                      <td className="px-8 py-4 text-right font-mono text-sm">{entry.debit > 0 ? fmtPKR(entry.debit) : "-"}</td>
                      <td className="px-8 py-4 text-right font-mono text-sm">{entry.credit > 0 ? fmtPKR(entry.credit) : "-"}</td>
                      <td className={`px-8 py-4 text-right font-mono text-sm font-semibold ${entry.balance < 0 ? "text-red-600" : ""}`}>
                        {fmtPKR(entry.balance)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))
        )}
      </div>

      <div className="mt-4">
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
      </div>
    </div>
  )
}
