"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import Pagination from "@/components/Pagination"
import StatusBadge from "@/components/StatusBadge"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
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

export default function WeighbridgeRegisterPage() {
  const [rows, setRows] = useState<Ticket[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState("")
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")

  useEffect(() => { setPage(1) }, [q, start, end])

  useEffect(() => {
    const params = new URLSearchParams({
      skip: String((page - 1) * PAGE_SIZE),
      limit: String(PAGE_SIZE),
    })
    if (q.trim()) params.set("q", q.trim())
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    apiFetch<{ total: number; items: Ticket[] }>(`/api/weighbridge/reports/register?${params}`)
      .then(d => { setRows(d.items); setTotal(d.total) })
      .catch(() => { setRows([]); setTotal(0) })
  }, [page, q, start, end])

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title="Weighbridge Register" orientation="landscape" />
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Weighbridge Register</h1>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search…"
            className="px-2.5 py-1.5 text-sm border border-[var(--border)] rounded-lg"
          />
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        </div>
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
              <tr><td colSpan={8} className="px-3 py-8 text-center text-[var(--text-muted)]">No tickets in this period.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
    </div>
  )
}
