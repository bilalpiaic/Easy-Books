"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Demand = {
  id: number; number: string; demand_date: string; required_by?: string
  purpose?: string; status: string
  lines: { id: number; description: string; qty: number; unit?: string }[]
}

const STATUSES = ["all", "draft", "approved", "converted", "closed", "cancelled"]

export default function DemandsPage() {
  const [rows, setRows] = useState<Demand[] | null>(null)
  const [status, setStatus] = useState("all")

  useEffect(() => {
    const qs = status === "all" ? "" : `?status=${status}`
    apiFetch<Demand[]>(`/api/purchase-demands${qs}`).then(setRows).catch(() => setRows([]))
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
        <Link href="/purchases/demands/new"
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Demand
        </Link>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">PD #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Purpose</th>
              <th className="px-3 py-2">Items</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(d => (
              <tr key={d.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/purchases/demands/${d.id}`} className="text-[var(--primary)]">{d.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(d.demand_date)}</td>
                <td className="px-3 py-2">{d.purpose || "—"}</td>
                <td className="px-3 py-2">{d.lines.length}</td>
                <td className="px-3 py-2">{d.status}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--text-muted)]">No demands yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
