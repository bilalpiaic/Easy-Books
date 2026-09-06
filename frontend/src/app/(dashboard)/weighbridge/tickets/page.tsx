"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import Pagination from "@/components/Pagination"
import StatusBadge from "@/components/StatusBadge"
import DateRangePicker from "@/components/DateRangePicker"
import { formatWeightTriple, type WeightTriple } from "@/lib/weavingUnits"

type Ticket = {
  id: number
  number: string
  ticket_date: string
  direction: string
  vehicle_no: string
  party_name?: string | null
  commodity?: string | null
  status: string
  net?: WeightTriple
}

const PAGE_SIZE = 50
const STATUSES = ["all", "draft", "weighed_in", "completed", "cancelled"]

export default function WeighbridgeTicketListPage() {
  const [rows, setRows] = useState<Ticket[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState("")
  const [status, setStatus] = useState("all")
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")

  useEffect(() => { setPage(1) }, [q, status, start, end])

  useEffect(() => {
    const params = new URLSearchParams({
      skip: String((page - 1) * PAGE_SIZE),
      limit: String(PAGE_SIZE),
    })
    if (q.trim()) params.set("q", q.trim())
    if (status !== "all") params.set("status", status)
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    apiFetch<{ total: number; items: Ticket[] }>(`/api/weighbridge/tickets?${params}`)
      .then(d => { setRows(d.items); setTotal(d.total) })
      .catch(() => { setRows([]); setTotal(0) })
  }, [page, q, status, start, end])

  return (
    <div className="p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search vehicle, ticket, party…"
            className="px-2.5 py-1.5 text-sm border border-[var(--border)] rounded-lg min-w-[12rem]"
          />
          <div className="flex gap-1">
            {STATUSES.map(s => (
              <button key={s} onClick={() => setStatus(s)}
                className={`px-3 py-1 rounded-full text-xs border ${status === s
                  ? "bg-[var(--primary)] text-white border-transparent"
                  : "border-[var(--border)] text-[var(--text-secondary)]"}`}>
                {s.replace("_", " ")}
              </button>
            ))}
          </div>
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        </div>
        <Link href="/weighbridge/tickets/new"
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New ticket
        </Link>
      </div>

      <div className="table-freeze freeze-col rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">WB #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Dir</th>
              <th className="px-3 py-2">Vehicle</th>
              <th className="px-3 py-2">Party</th>
              <th className="px-3 py-2">Commodity</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right">Net</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(t => (
              <tr key={t.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/weighbridge/tickets/${t.id}`} className="text-[var(--primary)]">{t.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(t.ticket_date)}</td>
                <td className="px-3 py-2 capitalize">{t.direction}</td>
                <td className="px-3 py-2">{t.vehicle_no}</td>
                <td className="px-3 py-2">{t.party_name || "—"}</td>
                <td className="px-3 py-2">{t.commodity || "—"}</td>
                <td className="px-3 py-2"><StatusBadge status={t.status} /></td>
                <td className="px-3 py-2 text-right whitespace-nowrap">{t.status === "completed" ? formatWeightTriple(t.net) : "—"}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-[var(--text-muted)]">
                No tickets in this filter.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
    </div>
  )
}
