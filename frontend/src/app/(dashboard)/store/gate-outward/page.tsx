"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import StatusBadge from "@/components/StatusBadge"

type GateOutward = {
  id: number; number: string; source_doc_type: string; gate_date: string
  reference?: string; status: string
}

const STATUSES = ["all", "draft", "approved", "cancelled"]

const TYPE_LABEL: Record<string, string> = {
  invoice: "Invoice",
  debit_note: "Debit Note",
  scrap: "Scrap",
}

export default function GateOutwardListPage() {
  const [rows, setRows] = useState<GateOutward[] | null>(null)
  const [status, setStatus] = useState("all")

  useEffect(() => {
    const qs = status === "all" ? "" : `?status=${status}`
    apiFetch<GateOutward[]>(`/api/gate-outwards${qs}`).then(setRows).catch(() => setRows([]))
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
        <Link href="/store/gate-outward/new"
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Gate Outward
        </Link>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">GO #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Reference</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(go => (
              <tr key={go.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/store/gate-outward/${go.id}`} className="text-[var(--primary)]">{go.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(go.gate_date)}</td>
                <td className="px-3 py-2">{TYPE_LABEL[go.source_doc_type] || go.source_doc_type}</td>
                <td className="px-3 py-2">{go.reference || "—"}</td>
                <td className="px-3 py-2"><StatusBadge status={go.status} /></td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--text-muted)]">
                No gate exits recorded yet.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
