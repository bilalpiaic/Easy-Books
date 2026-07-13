"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ScrollText, Search } from "lucide-react"
import { apiFetch } from "@/lib/api"
import DateRangePicker from "@/components/DateRangePicker"
import { useFmt } from "@/context/SettingsContext"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import StatusBadge from "@/components/StatusBadge"

interface GateOutwardRegisterRow {
  id: number
  number: string
  gate_date: string
  time_out: string | null
  vehicle_no: string | null
  challan_no: string | null
  remarks: string | null
  status: string
  source_doc_type: string
  reference: string | null
  item_count: number
  total_qty: number | string
}

const TYPE_LABEL: Record<string, string> = {
  invoice: "Invoice",
  debit_note: "Debit Note",
  scrap: "Scrap",
}

const TYPE_OPTIONS = [
  { value: "", label: "All Types" },
  { value: "invoice", label: "Invoice" },
  { value: "debit_note", label: "Debit Note" },
  { value: "scrap", label: "Scrap" },
]

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

export default function GateOutwardRegisterPage() {
  const fmt = useFmt()
  const range = defaultRange()

  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [q, setQ] = useState("")
  const [sourceDocType, setSourceDocType] = useState("")
  const [rows, setRows] = useState<GateOutwardRegisterRow[] | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams()
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    if (q) params.set("q", q)
    if (sourceDocType) params.set("source_doc_type", sourceDocType)
    apiFetch<GateOutwardRegisterRow[]>(`/api/store-reports/gate-outward-register?${params.toString()}`)
      .then(d => { setRows(d); setIsLoading(false) })
      .catch(() => { setRows([]); setIsLoading(false) })
  }, [start, end, q, sourceDocType])

  const printSubtitle = `Period: ${start} – ${end}${q ? `  |  Search: ${q}` : ""}`

  return (
    <div className="max-w-6xl mx-auto p-4">
      <PrintHeader title="Gate Outward Register" subtitle={printSubtitle} orientation="landscape" />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Gate Outward Register</h1>
          <p className="text-[var(--text-primary)]/60">Goods leaving the gate against invoices, debit notes and scrap</p>
        </div>
        <ScrollText className="w-7 h-7 text-[var(--primary)] hidden md:block" />
      </div>

      {/* Filters */}
      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl grid grid-cols-1 md:grid-cols-4 gap-4 print:hidden">
        <div className="md:col-span-2 flex items-end">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Search Vehicle / Challan</label>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-primary)]/40" />
            <input
              type="text"
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="e.g. LEA-1234"
              className="w-full border border-[var(--text-primary)]/10 rounded-lg pl-9 pr-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Type</label>
          <select
            value={sourceDocType}
            onChange={e => setSourceDocType(e.target.value)}
            className="w-full border border-[var(--text-primary)]/10 rounded-lg px-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
          >
            {TYPE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
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
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">GO #</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Date</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Type</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Reference</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Vehicle</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Challan</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Items</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Qty</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={9} className="px-6 py-10 text-center text-[var(--text-primary)]/75">Loading...</td>
                </tr>
              ) : !rows || rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-6 py-10 text-center text-[var(--text-primary)]/75">
                    No gate outward entries found for the selected filters.
                  </td>
                </tr>
              ) : (
                rows.map(row => (
                  <tr key={row.id} className="hover:bg-[var(--bg-page)]/30 transition-colors">
                    <td className="ui-td text-sm whitespace-nowrap">
                      <Link href={`/store/gate-outward/${row.id}`} className="text-[var(--primary)] font-semibold">
                        {row.number}
                      </Link>
                    </td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70 whitespace-nowrap">{fmtDate(row.gate_date)}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{TYPE_LABEL[row.source_doc_type] || row.source_doc_type}</td>
                    <td className="ui-td text-sm whitespace-nowrap text-[var(--text-primary)]/70">{row.reference || "—"}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{row.vehicle_no || "—"}</td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{row.challan_no || "—"}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{row.item_count}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]">{fmt(Number(row.total_qty))}</td>
                    <td className="ui-td"><StatusBadge status={row.status} /></td>
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
