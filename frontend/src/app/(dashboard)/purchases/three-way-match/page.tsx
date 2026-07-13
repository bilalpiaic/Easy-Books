"use client"

import { useEffect, useState } from "react"
import { CheckCheck, Search } from "lucide-react"
import { apiFetch } from "@/lib/api"
import Pagination from "@/components/Pagination"
import DateRangePicker from "@/components/DateRangePicker"
import { useFmt, useCurrency } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"

interface ThreeWayMatchRow {
  po_number: string
  vendor_name: string | null
  line_description: string
  po_qty: number | string
  po_rate: number | string
  po_amount: number | string
  gi_qty: number | string
  bill_qty: number | string
  bill_amount: number | string
  qty_variance: number | string
  amount_variance: number | string
  flag: boolean
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

export default function ThreeWayMatchPage() {
  const fmt = useFmt()
  const currency = useCurrency()
  const range = defaultRange()

  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [q, setQ] = useState("")
  const [rows, setRows] = useState<ThreeWayMatchRow[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams()
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    if (q) params.set("q", q)
    params.set("skip", String((page - 1) * PAGE_SIZE))
    params.set("limit", String(PAGE_SIZE))
    apiFetch<{ total: number; items: ThreeWayMatchRow[] }>(`/api/purchase-reports/three-way-match?${params.toString()}`)
      .then(d => { setRows(d.items); setTotal(d.total); setIsLoading(false) })
      .catch(() => { setRows([]); setTotal(0); setIsLoading(false) })
  }, [start, end, q, page])

  useEffect(() => { setPage(1) }, [start, end, q])

  const printSubtitle = `Period: ${start} – ${end}`

  return (
    <div className="max-w-6xl mx-auto p-4">
      <PrintHeader title="3-Way Match — PO vs Gate vs Bill" subtitle={printSubtitle} orientation="landscape" />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">3-Way Match</h1>
          <p className="text-[var(--text-primary)]/60">Purchase order vs gate-received quantity vs billed quantity/amount</p>
        </div>
        <CheckCheck className="w-7 h-7 text-[var(--primary)] hidden md:block" />
      </div>

      {/* Filters */}
      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl grid grid-cols-1 md:grid-cols-3 gap-4 print:hidden">
        <div className="md:col-span-2 flex items-end">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Search PO # / Vendor</label>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-primary)]/40" />
            <input
              type="text"
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="e.g. PO-2026 or Steel"
              className="w-full border border-[var(--text-primary)]/10 rounded-lg pl-9 pr-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="table-freeze freeze-col">
          <table className="w-full text-left border-collapse min-w-[1200px]">
            <thead>
              <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">PO #</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Vendor</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Line</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">PO Qty</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">PO Rate ({currency})</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">PO Amount ({currency})</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">GI Qty</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Bill Qty</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Bill Amount ({currency})</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Qty Var</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Amt Var ({currency})</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={11} className="px-6 py-10 text-center text-[var(--text-primary)]/75">Loading...</td>
                </tr>
              ) : !rows || rows.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-6 py-10 text-center text-[var(--text-primary)]/75">
                    No purchase orders with gate receipts or bills found for the selected period.
                  </td>
                </tr>
              ) : (
                rows.map((row, idx) => (
                  <tr
                    key={idx}
                    className={`hover:bg-[var(--bg-page)]/30 transition-colors ${row.flag ? "bg-amber-50 dark:bg-amber-900/20" : ""}`}
                  >
                    <td className="ui-td text-sm whitespace-nowrap text-[var(--text-primary)]/70">{row.po_number}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{row.vendor_name || "—"}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]">{row.line_description}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(Number(row.po_qty))}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(Number(row.po_rate))}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(Number(row.po_amount))}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(Number(row.gi_qty))}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(Number(row.bill_qty))}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(Number(row.bill_amount))}</td>
                    <td className={`ui-td text-right font-mono text-sm font-semibold ${Number(row.qty_variance) !== 0 ? "text-amber-700" : "text-[var(--text-primary)]/70"}`}>
                      {Number(row.qty_variance) > 0 ? "+" : ""}{fmt(Number(row.qty_variance))}
                    </td>
                    <td className={`ui-td text-right font-mono text-sm font-semibold ${Number(row.amount_variance) !== 0 ? "text-amber-700" : "text-[var(--text-primary)]/70"}`}>
                      {Number(row.amount_variance) > 0 ? "+" : ""}{fmt(Number(row.amount_variance))}
                    </td>
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
