"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import StatusBadge from "@/components/StatusBadge"

type CS = {
  id: number
  number: string
  cs_date: string
  demand_id: number
  status: string
  demand: { id: number; number: string }
}

const STATUSES = ["all", "draft", "approved", "converted", "cancelled"]

export default function ComparativesPage() {
  const [rows, setRows] = useState<CS[] | null>(null)
  const [status, setStatus] = useState("all")

  useEffect(() => {
    const qs = status === "all" ? "" : `?status=${status}`
    apiFetch<CS[]>(`/api/comparatives${qs}`).then(setRows).catch(() => setRows([]))
  }, [status])

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between print:hidden">
        <div className="flex gap-1">
          {STATUSES.map(s => (
            <button key={s} onClick={() => setStatus(s)}
              className={`px-3 py-1 rounded-full text-xs border ${status === s
                ? "bg-[var(--primary)] text-white border-transparent"
                : "border-[var(--border)] text-[var(--text-secondary)]"}`}>
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">CS #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Demand #</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(cs => (
              <tr key={cs.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/purchases/comparatives/${cs.id}`} className="text-[var(--primary)]">{cs.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(cs.cs_date)}</td>
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/purchases/demands/${cs.demand_id}`} className="text-[var(--primary)]">{cs.demand?.number}</Link>
                </td>
                <td className="px-3 py-2"><StatusBadge status={cs.status} /></td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={4} className="px-3 py-8 text-center text-[var(--text-muted)]">No comparatives yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
