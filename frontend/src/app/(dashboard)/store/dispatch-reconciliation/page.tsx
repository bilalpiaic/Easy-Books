"use client"

import { useEffect, useState } from "react"
import { CheckCheck } from "lucide-react"
import { apiFetch } from "@/lib/api"
import DateRangePicker from "@/components/DateRangePicker"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface DispatchReconciliationRow {
  doc_type: string
  doc_number: string
  party: string | null
  doc_date: string
  has_gate_exit: boolean
  go_number: string | null
}

const TYPE_LABEL: Record<string, string> = {
  invoice: "Invoice",
  debit_note: "Debit Note",
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

export default function DispatchReconciliationPage() {
  const range = defaultRange()

  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [rows, setRows] = useState<DispatchReconciliationRow[] | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams()
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    apiFetch<DispatchReconciliationRow[]>(`/api/store-reports/dispatch-reconciliation?${params.toString()}`)
      .then(d => { setRows(d); setIsLoading(false) })
      .catch(() => { setRows([]); setIsLoading(false) })
  }, [start, end])

  const printSubtitle = `Period: ${start} – ${end}`
  const missingCount = (rows ?? []).filter(r => !r.has_gate_exit).length

  return (
    <div className="max-w-6xl mx-auto p-4">
      <PrintHeader title="Dispatch Reconciliation" subtitle={printSubtitle} orientation="landscape" />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Dispatch Reconciliation</h1>
          <p className="text-[var(--text-primary)]/60">
            Invoices and debit notes matched against recorded gate exits
            {rows ? ` — ${missingCount} without a gate exit` : ""}
          </p>
        </div>
        <CheckCheck className="w-7 h-7 text-[var(--primary)] hidden md:block" />
      </div>

      {/* Filters */}
      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl grid grid-cols-1 md:grid-cols-3 gap-4 print:hidden">
        <div className="md:col-span-2 flex items-end">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="table-freeze freeze-col">
          <table className="w-full text-left border-collapse min-w-[800px]">
            <thead>
              <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Doc Type</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Doc #</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Party</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Date</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Gate Exit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-[var(--text-primary)]/75">Loading...</td>
                </tr>
              ) : !rows || rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-[var(--text-primary)]/75">
                    No dispatch documents found for the selected period.
                  </td>
                </tr>
              ) : (
                rows.map((row, idx) => (
                  <tr
                    key={`${row.doc_type}-${row.doc_number}-${idx}`}
                    className={`hover:bg-[var(--bg-page)]/30 transition-colors ${!row.has_gate_exit ? "bg-amber-50 dark:bg-amber-900/20" : ""}`}
                  >
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{TYPE_LABEL[row.doc_type] || row.doc_type}</td>
                    <td className="ui-td text-sm whitespace-nowrap font-semibold text-[var(--text-primary)]">{row.doc_number}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{row.party || "—"}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70 whitespace-nowrap">{fmtDate(row.doc_date)}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{row.go_number || "— no exit"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
