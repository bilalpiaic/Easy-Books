"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

export default function Page() {
  const [rows, setRows] = useState<any[] | null>(null)
  const [err, setErr] = useState("")
  function load() {
    apiFetch<any[]>("/api/textile-processing/pakki-parchis").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }
  useEffect(() => { load() }, [])
  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Pakki Parchi</h1>
        <Link href="/processing" className="text-sm text-[var(--primary)] print:hidden">Hub</Link>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]"><th className="p-2">Number</th><th className="p-2">Date</th><th className="p-2">Lot</th><th className="p-2">Safi MTR</th><th className="p-2">Thans</th></tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{String((r as any)["number"] ?? "—")}</td><td className="p-2 whitespace-nowrap">{String((r as any)["date"] ?? "—")}</td><td className="p-2 whitespace-nowrap">{String((r as any)["lot_id"] ?? "—")}</td><td className="p-2 whitespace-nowrap">{String((r as any)["meters"] ?? "—")}</td><td className="p-2 whitespace-nowrap">{String((r as any)["than_count"] ?? "—")}</td>
              </tr>
            ))}
            {rows && rows.length === 0 && (
              <tr><td className="p-4 text-[var(--text-muted)]" colSpan={20}>No records</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
