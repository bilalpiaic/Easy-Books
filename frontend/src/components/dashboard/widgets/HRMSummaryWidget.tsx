"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useFmt } from "@/context/SettingsContext"
import { apiFetch } from "@/lib/api"

interface HRMSummary {
  active_employees: number
  last_payroll_net: number
  pending_runs: number
  avg_attendance_pct: number
}

function Figure({ label, value, tone }: { label: string; value: string; tone?: "warning" | "danger" }) {
  const color = tone === "danger" ? "text-red-600" : tone === "warning" ? "text-amber-600" : "text-[var(--text-primary)]"
  return (
    <div className="text-center min-w-0">
      <p className={`text-lg font-bold leading-none truncate ${color}`}>{value}</p>
      <p className="text-[10px] text-[var(--text-primary)]/55 mt-1 uppercase tracking-wide leading-tight">{label}</p>
    </div>
  )
}

export default function HRMSummaryWidget() {
  const fmt = useFmt()
  const [data, setData] = useState<HRMSummary | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiFetch<HRMSummary>("/api/payroll/summary")
      .then(setData)
      .catch(() => setError(true))
  }, [])

  return (
    <div className="h-full flex flex-col bg-white border border-[var(--border)] rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/55">HRM & Payroll</p>
        <Link href="/hrm" className="text-[10px] text-[var(--primary)] hover:underline">Overview →</Link>
      </div>
      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !data ? (
        <div className="shimmer h-16 rounded-lg" />
      ) : (
        <div className="flex-1 grid grid-cols-2 gap-x-3 gap-y-4 items-center">
          <Figure label="Active Employees" value={String(data.active_employees)} />
          <Figure label="Last Payroll Net" value={fmt(data.last_payroll_net)} />
          <Figure
            label="Pending Runs"
            value={String(data.pending_runs)}
            tone={data.pending_runs > 0 ? "warning" : undefined}
          />
          <Figure
            label="Attendance MTD"
            value={`${data.avg_attendance_pct}%`}
            tone={data.avg_attendance_pct < 70 ? "danger" : data.avg_attendance_pct < 85 ? "warning" : undefined}
          />
        </div>
      )}
    </div>
  )
}
