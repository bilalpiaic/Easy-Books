"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { RotateCcw, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV, fmtDate } from "@/lib/utils"
import { VOUCHER_TYPES } from "@/lib/voucherTypes"
import DateRangePicker from "@/components/DateRangePicker"
import Pagination from "@/components/Pagination"
import SkeletonRow from "@/components/SkeletonRow"
import PrintHeader from "@/components/PrintHeader"
import CsvImportButton from "@/components/CsvImportButton"
import { useTranslation } from "react-i18next"

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
  const { t } = useTranslation()

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
      <PrintHeader title="General Journal" subtitle={`Period: ${fmtDate(start)} — ${fmtDate(end)}`} orientation="landscape" />
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">General Journal</h1>
          <p className="text-[var(--text-primary)]/60">Chronological record of all financial transactions</p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <CsvImportButton entity="transactions" onSuccess={loadEntries} />
          <button
            onClick={() => downloadCSV(`journal-${start}-${end}.csv`, entries.map(e => ({ Date: e.date, JV: e.jv_number, Account: e.account_name, Description: e.description, Debit: e.debit, Credit: e.credit })))}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Download className="w-4 h-4" />{t('common.exportCsv', 'Export CSV')}</button>
        </div>
      </div>

      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl space-y-3 print:hidden">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        <div className="flex items-center gap-2">
          <label className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 shrink-0">
            Voucher Type
          </label>
          <select
            value={voucherTypeFilter}
            onChange={e => setVoucherTypeFilter(e.target.value)}
            className="ui-field text-sm border border-[var(--border)] rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          >
            <option value="">All Types</option>
            {Object.entries(VOUCHER_TYPES).map(([code, label]) => (
              <option key={code} value={code}>{code} — {label}</option>
            ))}
          </select>
          {voucherTypeFilter && (
            <button
              onClick={() => setVoucherTypeFilter("")}
              className="text-xs text-[var(--text-primary)]/50 hover:text-[var(--primary)] transition-colors"
              title="Clear filter"
            >
              ✕ Clear
            </button>
          )}
        </div>
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-left min-w-[640px]">
          <thead>
            <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 w-24">Date</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 w-28">JV #</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Account &amp; Description</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right w-24">{t('col.debit', 'Debit')}</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right w-24">{t('col.credit', 'Credit')}</th>
              <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 print:hidden"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--text-primary)]/5">
            {isLoading ? (
              <SkeletonRow cols={6} />
            ) : entries.length === 0 ? (
              <tr><td colSpan={6} className="px-6 py-10 text-center text-[var(--text-primary)]/75">No entries found for selected period.</td></tr>
            ) : (() => {
                const seenTxns = new Set<number>()
                return entries.map((entry, idx) => {
                  const isFirstLine = !seenTxns.has(entry.transaction_id)
                  if (isFirstLine) seenTxns.add(entry.transaction_id)
                  return (
                    <tr key={idx} className={`hover:bg-[var(--bg-page)]/50 transition-colors ${entry.is_reversed ? 'opacity-60' : ''}`}>
                      <td className="ui-td text-sm whitespace-nowrap">{fmtDate(entry.date)}</td>
                      <td className="ui-td whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <Link href={`/journal/${entry.transaction_id}`} className="font-mono text-xs font-bold text-[var(--primary)] hover:underline">
                            {entry.jv_number}
                          </Link>
                          {entry.is_reversed && isFirstLine && (
                            <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-[10px] font-bold uppercase rounded-full print:hidden">Reversed</span>
                          )}
                        </div>
                        {isFirstLine && entry.legacy_jv_number && (
                          <div className="mt-0.5 text-[9px] text-[var(--text-primary)]/40 font-mono print:hidden">
                            was {entry.legacy_jv_number}
                          </div>
                        )}
                      </td>
                      <td className="ui-td">
                        <Link href={`/ledger?account=${encodeURIComponent(entry.account_name)}`}
                          className="font-medium text-[var(--text-primary)] hover:text-[var(--primary)] hover:underline underline-offset-2 transition-colors">
                          {entry.account_name}
                        </Link>
                        <div className="text-xs text-[var(--text-primary)]/75">{entry.description}</div>
                      </td>
                      <td className="ui-td text-right font-mono text-sm">{entry.debit > 0 ? fmt(entry.debit) : "-"}</td>
                      <td className="ui-td text-right font-mono text-sm">{entry.credit > 0 ? fmt(entry.credit) : "-"}</td>
                      <td className="ui-td print:hidden">
                        {isFirstLine && (
                          <div className="flex items-center gap-1.5">
                            <Link
                              href={`/journal/${entry.transaction_id}/print`}
                              title="Print this JV"
                              className="inline-flex p-1.5 rounded border border-[var(--border)] hover:bg-[var(--bg-page)] text-[var(--text-primary)]/55 hover:text-[var(--primary)]"
                            >
                              <Printer className="w-3 h-3" />
                            </Link>
                            {!entry.is_reversed && (
                              <button
                                onClick={() => handleReverse(entry)}
                                disabled={reversing === entry.transaction_id}
                                className="flex items-center gap-1 px-2 py-1 text-xs font-bold text-[var(--text-primary)]/60 hover:text-[var(--primary)] hover:bg-[var(--bg-page)] rounded transition-colors disabled:opacity-50"
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

        {/* Mobile card list */}
        <div className="md:hidden divide-y divide-[var(--border)]">
          {isLoading ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">Loading…</div>
          ) : entries.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-[var(--text-muted)]">No entries found</div>
          ) : entries.map((e, idx) => (
            <Link
              key={idx}
              href={`/journal/${e.transaction_id}`}
              className="flex items-start justify-between px-4 py-3 hover:bg-[var(--bg-row-hover)] transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{e.account_name}</p>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">{e.jv_number} · {fmtDate(e.date)}</p>
                {e.description && <p className="text-xs text-[var(--text-muted)] truncate">{e.description}</p>}
              </div>
              <div className="text-right ml-3 shrink-0">
                {e.debit > 0 && <p className="text-sm font-bold font-mono text-[var(--text-primary)]">{fmt(e.debit)}</p>}
                {e.credit > 0 && <p className="text-sm font-bold font-mono text-[var(--text-muted)]">{fmt(e.credit)}</p>}
              </div>
            </Link>
          ))}
        </div>

        <div className="border-t border-[var(--text-primary)]/5 px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>
    </div>
  )
}
