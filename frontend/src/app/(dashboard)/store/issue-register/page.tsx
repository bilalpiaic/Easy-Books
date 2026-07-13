"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ScrollText, Search } from "lucide-react"
import { apiFetch } from "@/lib/api"
import Pagination from "@/components/Pagination"
import DateRangePicker from "@/components/DateRangePicker"
import { useFmt } from "@/context/SettingsContext"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface AnalyticAccount {
  id: number
  code: string
  name: string
}

interface IssueRegisterRow {
  id: number
  number: string
  issue_date: string
  notes: string | null
  location_name: string | null
  debit_account_name: string | null
  analytic_account_name: string | null
  item_count: number
  total_cost: number | string
}

const PAGE_SIZE = 50

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

export default function IssueRegisterPage() {
  const fmt = useFmt()
  const range = defaultRange()

  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [q, setQ] = useState("")
  const [analyticAccountId, setAnalyticAccountId] = useState("")
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])
  const [rows, setRows] = useState<IssueRegisterRow[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    apiFetch<{ items: AnalyticAccount[] }>("/api/analytic-accounts?limit=500")
      .then(d => setAnalyticAccounts(d.items))
      .catch(() => setAnalyticAccounts([]))
  }, [])

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams()
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    if (q) params.set("q", q)
    if (analyticAccountId) params.set("analytic_account_id", analyticAccountId)
    params.set("skip", String((page - 1) * PAGE_SIZE))
    params.set("limit", String(PAGE_SIZE))
    apiFetch<{ total: number; items: IssueRegisterRow[] }>(`/api/store-reports/issue-register?${params.toString()}`)
      .then(d => { setRows(d.items); setTotal(d.total); setIsLoading(false) })
      .catch(() => { setRows([]); setTotal(0); setIsLoading(false) })
  }, [start, end, q, analyticAccountId, page])

  useEffect(() => { setPage(1) }, [start, end, q, analyticAccountId])

  const printSubtitle = `Period: ${start} – ${end}${q ? `  |  Search: ${q}` : ""}`

  return (
    <div className="max-w-6xl mx-auto p-4">
      <PrintHeader title="Issue Register" subtitle={printSubtitle} orientation="landscape" />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Issue Register</h1>
          <p className="text-[var(--text-primary)]/60">Store issues consumed to departments, cost centers and projects</p>
        </div>
        <ScrollText className="w-7 h-7 text-[var(--primary)] hidden md:block" />
      </div>

      {/* Filters */}
      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl grid grid-cols-1 md:grid-cols-4 gap-4 print:hidden">
        <div className="md:col-span-2 flex items-end">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Search Number / Notes</label>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-primary)]/40" />
            <input
              type="text"
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="e.g. SI-2026"
              className="w-full border border-[var(--text-primary)]/10 rounded-lg pl-9 pr-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Analytic Account</label>
          <select
            value={analyticAccountId}
            onChange={e => setAnalyticAccountId(e.target.value)}
            className="w-full border border-[var(--text-primary)]/10 rounded-lg px-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
          >
            <option value="">All Analytic Accounts</option>
            {analyticAccounts.map(aa => (
              <option key={aa.id} value={aa.id}>{aa.code} — {aa.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="table-freeze freeze-col">
          <table className="w-full text-left border-collapse min-w-[1000px]">
            <thead>
              <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">SI #</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Date</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Location</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Debit Account</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Analytic Account</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Items</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-[var(--text-primary)]/75">Loading...</td>
                </tr>
              ) : !rows || rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-[var(--text-primary)]/75">
                    No store issues found for the selected filters.
                  </td>
                </tr>
              ) : (
                rows.map(row => (
                  <tr key={row.id} className="hover:bg-[var(--bg-page)]/30 transition-colors">
                    <td className="ui-td text-sm whitespace-nowrap">
                      <Link href={`/store/issues/${row.id}`} className="text-[var(--primary)] font-semibold">
                        {row.number}
                      </Link>
                    </td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70 whitespace-nowrap">{fmtDate(row.issue_date)}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{row.location_name || "—"}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{row.debit_account_name || "—"}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{row.analytic_account_name || "—"}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{row.item_count}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]">{fmt(Number(row.total_cost))}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
      </div>
    </div>
  )
}
