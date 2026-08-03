"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useBreadcrumb } from "@/context/BreadcrumbContext"

interface UaeLog {
  id: number
  invoice_id: number
  attempt_at: string
  status?: string
  http_status: number | null
  endpoint: string
  error_message: string | null
  sandbox: boolean
  success: boolean
  response_uuid: string | null
}

export default function UaeLogsPage() {
  useBreadcrumb("UAE e-Invoice Logs")
  const [logs, setLogs] = useState<UaeLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<UaeLog[]>("/api/uae/logs?limit=100")
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">UAE e-Invoice Logs</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Audit trail of FTA sandbox / adapter submissions
          </p>
        </div>
        <Link href="/uae" className="text-sm font-semibold text-[var(--primary)] hover:underline">
          ← Dashboard
        </Link>
      </div>

      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="overflow-x-auto table-freeze">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] border-b border-[var(--border)]">
              <tr>
                <th className="text-left px-3 py-2 font-semibold">When</th>
                <th className="text-left px-3 py-2 font-semibold">Invoice</th>
                <th className="text-left px-3 py-2 font-semibold">Result</th>
                <th className="text-left px-3 py-2 font-semibold">Mode</th>
                <th className="text-left px-3 py-2 font-semibold">HTTP</th>
                <th className="text-left px-3 py-2 font-semibold">UUID / Error</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">Loading…</td>
                </tr>
              )}
              {!loading && logs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">
                    No submissions yet. Open an invoice and use &quot;Submit to UAE&quot;.
                  </td>
                </tr>
              )}
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-[var(--border-light)]">
                  <td className="px-3 py-2 whitespace-nowrap">{fmtDate(log.attempt_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <Link href={`/invoices/${log.invoice_id}`} className="text-[var(--text-link)] hover:underline">
                      #{log.invoice_id}
                    </Link>
                  </td>
                  <td className={`px-3 py-2 font-mono text-xs ${log.success ? "text-green-700" : "text-red-600"}`}>
                    {log.success ? "OK" : "failed"}
                  </td>
                  <td className="px-3 py-2">{log.sandbox ? "Sandbox" : "Production"}</td>
                  <td className="px-3 py-2">{log.http_status ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {log.success ? (log.response_uuid || "—") : (log.error_message || "—")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
