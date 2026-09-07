"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useBreadcrumb } from "@/context/BreadcrumbContext"

interface UkMtdLog {
  id: number
  invoice_id: number
  created_at: string
  status: string
  http_status: number | null
  endpoint: string | null
  error_message: string | null
  sandbox: boolean
  period_key: string | null
}

export default function UkMtdLogsPage() {
  useBreadcrumb("UK MTD Submission Logs")
  const [logs, setLogs] = useState<UkMtdLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<UkMtdLog[]>("/api/uk-mtd/logs?limit=100")
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">UK MTD Submission Logs</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Audit trail of HMRC VAT return and invoice sandbox submits
          </p>
        </div>
        <Link href="/uk-mtd" className="text-sm font-semibold text-[var(--primary)] hover:underline">
          ← Dashboard
        </Link>
      </div>

      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="overflow-x-auto table-freeze">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] border-b border-[var(--border)]">
              <tr>
                <th className="text-left px-3 py-2 font-semibold">When</th>
                <th className="text-left px-3 py-2 font-semibold">Period</th>
                <th className="text-left px-3 py-2 font-semibold">Invoice</th>
                <th className="text-left px-3 py-2 font-semibold">Status</th>
                <th className="text-left px-3 py-2 font-semibold">Mode</th>
                <th className="text-left px-3 py-2 font-semibold">HTTP</th>
                <th className="text-left px-3 py-2 font-semibold">Result</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-[var(--text-muted)]">
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && logs.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-[var(--text-muted)]">
                    No submissions yet. Open the dashboard and submit a sandbox VAT return.
                  </td>
                </tr>
              )}
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-[var(--border-light)]">
                  <td className="px-3 py-2 whitespace-nowrap">{fmtDate(log.created_at)}</td>
                  <td className="px-3 py-2 font-mono text-xs">{log.period_key || "—"}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {log.invoice_id ? (
                      <Link
                        href={`/invoices/${log.invoice_id}`}
                        className="text-[var(--text-link)] hover:underline"
                      >
                        #{log.invoice_id}
                      </Link>
                    ) : (
                      "Return"
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{log.status}</td>
                  <td className="px-3 py-2">{log.sandbox ? "Sandbox" : "Production"}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{log.http_status ?? "—"}</td>
                  <td className={`px-3 py-2 ${log.status === "accepted" ? "text-green-700" : "text-red-600"}`}>
                    {log.status === "accepted" ? "OK" : log.error_message || log.status}
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
