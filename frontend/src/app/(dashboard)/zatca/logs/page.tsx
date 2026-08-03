"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useBreadcrumb } from "@/context/BreadcrumbContext"

interface ZatcaLog {
  id: number
  invoice_id: number
  created_at: string
  status: string
  http_status: number | null
  endpoint: string | null
  error_message: string | null
  sandbox: boolean
}

export default function ZatcaLogsPage() {
  useBreadcrumb("ZATCA Submission Logs")
  const [logs, setLogs] = useState<ZatcaLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<ZatcaLog[]>("/api/zatca/logs?limit=100")
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-3xl font-bold">ZATCA Submission Logs</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Audit trail of Fatoora clear/report attempts (sandbox or production)
        </p>
      </div>

      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="overflow-x-auto table-freeze">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] border-b border-[var(--border)]">
              <tr>
                <th className="text-left px-3 py-2 font-semibold">When</th>
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
                  <td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && logs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">
                    No submissions yet. Open an invoice and use &quot;Submit to ZATCA&quot;.
                  </td>
                </tr>
              )}
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-[var(--border-light)]">
                  <td className="px-3 py-2 whitespace-nowrap">{fmtDate(log.created_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <Link
                      href={`/invoices/${log.invoice_id}`}
                      className="text-[var(--text-link)] hover:underline"
                    >
                      #{log.invoice_id}
                    </Link>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{log.status}</td>
                  <td className="px-3 py-2">{log.sandbox ? "Sandbox" : "Production"}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{log.http_status ?? "—"}</td>
                  <td className={`px-3 py-2 ${["cleared", "reported"].includes(log.status) ? "text-green-700" : "text-red-600"}`}>
                    {["cleared", "reported"].includes(log.status) ? "OK" : log.error_message || log.status}
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
