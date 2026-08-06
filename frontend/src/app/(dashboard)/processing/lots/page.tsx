"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Lot = {
  id: number
  number: string
  date: string
  status: string
  received_mtr: number
  ready_mtr: number
  rejection_mtr: number
  sales_order_id: number
  than_count: number
  lot_no?: string | null
  process_name?: string | null
  category?: string | null
}

export default function GreyInwardListPage() {
  const [rows, setRows] = useState<Lot[] | null>(null)

  useEffect(() => {
    apiFetch<Lot[]>("/api/textile-processing/lots")
      .then(d => setRows(Array.isArray(d) ? d : []))
      .catch(() => setRows([]))
  }, [])

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between print:hidden">
        <div>
          <h1 className="text-xl font-semibold">Grey Inward</h1>
          <p className="text-xs text-[var(--text-muted)]">GREY IN — grey fabric receipt &amp; than detail</p>
        </div>
        <Link
          href="/processing/lots/new"
          className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2"
        >
          New Grey Inward
        </Link>
      </div>
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b border-[var(--border)]">
              <th className="p-2">Grey IN#</th>
              <th className="p-2">Lot#</th>
              <th className="p-2">Date</th>
              <th className="p-2">Process</th>
              <th className="p-2 text-right">Received</th>
              <th className="p-2 text-right">Safi / Ready</th>
              <th className="p-2 text-right">Rejection</th>
              <th className="p-2">Thans</th>
              <th className="p-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">
                  <Link href={`/processing/lots/${r.id}`} className="text-[var(--primary)]">
                    {r.number}
                  </Link>
                </td>
                <td className="p-2 whitespace-nowrap">{r.lot_no || "—"}</td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2">{r.process_name || "—"}</td>
                <td className="p-2 text-right tabular-nums">{r.received_mtr}</td>
                <td className="p-2 text-right tabular-nums">{r.ready_mtr}</td>
                <td className="p-2 text-right tabular-nums">{r.rejection_mtr}</td>
                <td className="p-2">{r.than_count}</td>
                <td className="p-2">{r.status}</td>
              </tr>
            ))}
            {rows && rows.length === 0 && (
              <tr>
                <td colSpan={9} className="p-6 text-center text-[var(--text-muted)]">
                  No grey inward lots yet.{" "}
                  <Link href="/processing/lots/new" className="text-[var(--primary)]">
                    Create one
                  </Link>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
