"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { RotateCcw, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import { VOUCHER_TYPES, voucherTypeBadgeClass } from "@/lib/voucherTypes"
import DateRangePicker from "@/components/DateRangePicker"
import Pagination from "@/components/Pagination"
import SkeletonRow from "@/components/SkeletonRow"
import PrintHeader from "@/components/PrintHeader"
import CsvImportButton from "@/components/CsvImportButton"

interface JournalEntry {
  id: number
  transaction_id: number
  jv_number: string
  voucher_type: string
  legacy_jv_number: string | null
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
  const fmt = useFmt()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [voucherTypeFilter, setVoucherTypeFilter] = useState("")
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [reversing, setReversing] = useState<number | null>(null)

  useEffect(() => {
    setPage(1)
  }, [start, end, voucherTypeFilter])

  const loadEntries = () => {
    setIsLoading(true)
    const skip = (page - 1) * PAGE_SIZE
    const params = new URLSearchParams({ start, end, skip: String(skip), limit: String(PAGE_SIZE) })
    if (voucherTypeFilter) params.set("voucher_type", voucherTypeFilter)
    apiFetch<JournalResponse>(`/api/reports/journal?${params}`)
      .then(data => { setEntries(data.items); setTotal(data.total); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }

  useEffect(loadEntries, [start, end, voucherTypeFilter, page])

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
    <div>
      <PrintHeader title="General Journal" subtitle={`Period: ${start} — ${end}`} orientation="landscape" />
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">General Journal</h1>
          <p className="text-[#1a1814]/60">Chronological record of all financial transactions</p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <CsvImportButton entity="transactions" onSuccess={loadEntries} />
          <button
            onClick={() => downloadCSV(`journal-${start}-${end}.csv`, entries.map(e => ({ Date: e.date, JV: e.jv_number, Account: e.account_name, Description: e.description, Debit: e.debit, Credit: e.credit })))}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>

      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl space-y-3">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        <div className="flex items-center gap-2">
          <label className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 shrink-0">
            Voucher Type
          </label>
          <select
            value={voucherTypeFilter}
            onChange={e => setVoucherTypeFilter(e.target.value)}
            className="ui-field text-sm border border-[#ede9e2] rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-[#b8943f]"
          >
            <option value="">All Types</option>
            {Object.entries(VOUCHER_TYPES).map(([code, label]) => (
              <option key={code} value={code}>{code} — {label}</option>
            ))}
          </select>
          {voucherTypeFilter && (
            <button
              onClick={() => setVoucherTypeFilter("")}
              className="text-xs text-[#1a1814]/50 hover:text-[#b8943f] transition-colors"
              title="Clear filter"
            >
              ✕ Clear
            </button>
          )}
        </div>
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-left min-w-[640px]">
          <thead>
            <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Date</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">JV #</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Account &amp; Description</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Debit</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Credit</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 print:hidden"></th>
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
                      <td className="ui-td text-sm">{entry.date}</td>
                      <td className="ui-td">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Link href={`/journal/${entry.transaction_id}`} className="font-mono text-xs font-bold text-[#b8943f] hover:underline">
                            {entry.jv_number}
                          </Link>
                          {isFirstLine && (
                            <span
                              className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${voucherTypeBadgeClass(entry.voucher_type)}`}
                              title={VOUCHER_TYPES[entry.voucher_type] ?? entry.voucher_type}
                            >
                              {entry.voucher_type}
                            </span>
                          )}
                          {entry.is_reversed && isFirstLine && (
                            <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-[10px] font-bold uppercase rounded-full">Reversed</span>
                          )}
                        </div>
                        {isFirstLine && entry.legacy_jv_number && (
                          <div className="mt-0.5 text-[9px] text-[#1a1814]/40 font-mono" title="Original voucher number before renumbering">
                            was {entry.legacy_jv_number}
                          </div>
                        )}
                      </td>
                      <td className="ui-td">
                        <Link href={`/ledger?account=${encodeURIComponent(entry.account_name)}`}
                          className="font-medium text-[#1a1814] hover:text-[#b8943f] hover:underline underline-offset-2 transition-colors">
                          {entry.account_name}
                        </Link>
                        <div className="text-xs text-[#1a1814]/75">{entry.description}</div>
                      </td>
                      <td className="ui-td text-right font-mono text-sm">{entry.debit > 0 ? fmt(entry.debit) : "-"}</td>
                      <td className="ui-td text-right font-mono text-sm">{entry.credit > 0 ? fmt(entry.credit) : "-"}</td>
                      <td className="ui-td print:hidden">
                        {isFirstLine && (
                          <div className="flex items-center gap-1.5">
                            <Link
                              href={`/journal/${entry.transaction_id}/print`}
                              title="Print this JV"
                              className="inline-flex p-1.5 rounded border border-[#ede9e2] hover:bg-[#faf6ec] text-[#1a1814]/55 hover:text-[#b8943f]"
                            >
                              <Printer className="w-3 h-3" />
                            </Link>
                            {!entry.is_reversed && (
                              <button
                                onClick={() => handleReverse(entry)}
                                disabled={reversing === entry.transaction_id}
                                className="flex items-center gap-1 px-2 py-1 text-xs font-bold text-[#1a1814]/60 hover:text-[#b8943f] hover:bg-[#f6f3ee] rounded transition-colors disabled:opacity-50"
                                title="Reverse this entry"
                              >
                                <RotateCcw className="w-3 h-3" />
                                Reverse
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })
              })()
            }
          </tbody>
        </table>
        </div>
        <div className="border-t border-[#1a1814]/5 px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>
    </div>
  )
}
