"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import Pagination from "@/components/Pagination"
import PrintHeader from "@/components/PrintHeader"
import DateRangePicker from "@/components/DateRangePicker"

interface Transfer {
  id: number
  number: string
  transfer_date: string
  status: string
  from_location_name?: string
  to_location_name?: string
}

export default function TransferRegisterPage() {
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")
  const [items, setItems] = useState<Transfer[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const limit = 50

  const load = useCallback(() => {
    const params = new URLSearchParams({
      skip: String((page - 1) * limit),
      limit: String(limit),
    })
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    apiFetch<{ total: number; items: Transfer[] }>(`/api/stock-transfers/register?${params}`)
      .then((r) => { setItems(r.items); setTotal(r.total) })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [page, start, end])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-4 max-w-5xl">
      <PrintHeader title="Transfer Register" orientation="landscape" />
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-2xl font-bold">Transfer Register</h1>
          <p className="text-sm text-[var(--text-primary)]/55">All warehouse transfers.</p>
        </div>
        <Link href="/inventory/transfers" className="text-sm text-[var(--primary)] hover:underline">Transfers →</Link>
      </div>

      <div className="print:hidden">
        <DateRangePicker
          start={start}
          end={end}
          onStartChange={(s) => { setStart(s); setPage(1) }}
          onEndChange={(e) => { setEnd(e); setPage(1) }}
        />
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-3 py-2 text-sm">{error}</div>}

      <div className="table-freeze overflow-x-auto bg-white border border-[var(--text-primary)]/10 rounded-xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-[var(--text-primary)]/60">
              <th className="px-3 py-2">Number</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">From</th>
              <th className="px-3 py-2">To</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id} className="border-b border-[var(--text-primary)]/5">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/inventory/transfers/${t.id}`} className="text-[var(--primary)] hover:underline">{t.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(t.transfer_date)}</td>
                <td className="px-3 py-2">{t.from_location_name}</td>
                <td className="px-3 py-2">{t.to_location_name}</td>
                <td className="px-3 py-2 capitalize">{t.status.replace("_", " ")}</td>
              </tr>
            ))}
            {!items.length && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--text-primary)]/45">No transfers in range.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={limit} total={total} onPage={setPage} />
    </div>
  )
}
