"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useBreadcrumb } from "@/context/BreadcrumbContext"

interface PRALog {
  id: number
  invoice_id: number
  attempt_at: string
  endpoint: string
  http_status: number | null
  response_code: string | null
  success: boolean
  error_message: string | null
}

export default function PRALogsPage() {
  useBreadcrumb("PRA Submission Logs")
  const [logs, setLogs] = useState<PRALog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<PRALog[]>("/api/pra/logs?limit=100")
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-3xl font-bold">PRA Submission Logs</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">Audit trail of every PRA e-IMS API call</p>
      </div>

      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="overflow-x-auto table-freeze">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="bg-[var(--bg-page)] border-b border-[var(--border)]">
              <tr>
                <th className="ui-th text-left">Date / Time</th>
                <th className="ui-th text-left">Invoice</th>
                <th className="ui-th text-center">HTTP</th>
                <th className="ui-th text-center">PRA Code</th>
                <th className="ui-th text-center">Status</th>
                <th className="ui-th text-left">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {loading ? (
                <tr><td colSpan={6} className="px-6 py-10 text-center text-sm text-[var(--text-muted)]">Loading…</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={6} className="px-6 py-10 text-center text-sm text-[var(--text-muted)]">No PRA submissions yet.</td></tr>
              ) : logs.map(log => (
                <tr key={log.id} className={log.success ? "" : "bg-red-50/30"}>
                  <td className="ui-td whitespace-nowrap text-[var(--text-muted)]">{fmtDate(log.attempt_at)}</td>
                  <td className="ui-td">
                    <Link href={`/invoices/${log.invoice_id}`} className="text-[var(--primary)] font-mono font-bold hover:underline">
                      #{log.invoice_id}
                    </Link>
                  </td>
                  <td className="ui-td text-center font-mono">{log.http_status ?? "—"}</td>
                  <td className="ui-td text-center font-mono">{log.response_code ?? "—"}</td>
                  <td className="ui-td text-center">
                    {log.success
                      ? <span className="text-emerald-700 font-bold">✓ OK</span>
                      : <span className="text-red-600 font-bold">✗ Failed</span>}
                  </td>
                  <td className="ui-td text-xs text-red-600 max-w-xs truncate">{log.error_message ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
