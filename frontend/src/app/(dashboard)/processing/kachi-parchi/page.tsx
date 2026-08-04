"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Row = { id: number; number: string; date: string; lot_id: number; meters: number; than_count: number }

export default function Page() {
  const [rows, setRows] = useState<Row[] | null>(null)
  useEffect(() => {
    apiFetch<Row[]>("/api/textile-processing/kachi-parchis").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])
  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Kachi Parchi</h1>
        <Link href="/processing" className="text-sm text-[var(--primary)] print:hidden">Hub</Link>
      </div>
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Number</th><th className="p-2">Date</th><th className="p-2">Lot</th>
            <th className="p-2 text-right">Meters</th><th className="p-2">Thans</th>
            <th className="p-2 print:hidden">Print</th>
          </tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">
                  <Link href={`/processing/kachi-parchi/${r.id}`} className="text-[var(--primary)]">{r.number}</Link>
                </td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2 whitespace-nowrap">{r.lot_id}</td>
                <td className="p-2 text-right tabular-nums">{r.meters}</td>
                <td className="p-2">{r.than_count}</td>
                <td className="p-2 print:hidden">
                  <Link href={`/processing/kachi-parchi/${r.id}`} className="text-xs text-[var(--primary)]">Open / Print</Link>
                </td>
              </tr>
            ))}
            {rows && rows.length === 0 && (
              <tr><td className="p-4 text-[var(--text-muted)]" colSpan={6}>No records</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
