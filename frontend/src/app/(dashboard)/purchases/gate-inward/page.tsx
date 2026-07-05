"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import StatusBadge from "@/components/StatusBadge"

type GateInward = {
  id: number; number: string; po_id: number; gate_date: string
  vehicle_no?: string; challan_no?: string; status: string
  po_number?: string; vendor_name?: string
}

const STATUSES = ["all", "open", "billed", "cancelled"]

export default function GateInwardListPage() {
  const [rows, setRows] = useState<GateInward[] | null>(null)
  const [status, setStatus] = useState("all")

  useEffect(() => {
    const qs = status === "all" ? "" : `?status=${status}`
    apiFetch<GateInward[]>(`/api/gate-inwards${qs}`).then(setRows).catch(() => setRows([]))
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
        <Link href="/purchases/gate-inward/new"
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Gate Inward
        </Link>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">GI #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">PO #</th>
              <th className="px-3 py-2">Vendor</th>
              <th className="px-3 py-2">Vehicle</th>
              <th className="px-3 py-2">Challan</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(gi => (
              <tr key={gi.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/purchases/gate-inward/${gi.id}`} className="text-[var(--primary)]">{gi.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(gi.gate_date)}</td>
                <td className="px-3 py-2 whitespace-nowrap">{gi.po_number || "—"}</td>
                <td className="px-3 py-2">{gi.vendor_name || "—"}</td>
                <td className="px-3 py-2">{gi.vehicle_no || "—"}</td>
                <td className="px-3 py-2">{gi.challan_no || "—"}</td>
                <td className="px-3 py-2"><StatusBadge status={gi.status} /></td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-[var(--text-muted)]">
                No gate entries yet. Record one from an approved purchase order.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
