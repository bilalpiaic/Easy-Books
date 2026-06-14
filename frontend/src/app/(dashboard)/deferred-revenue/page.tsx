"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Calendar, Play, CheckCircle2, Clock, XCircle, TrendingUp, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"

interface DeferredSchedule {
  id: number
  invoice_id: number
  total_amount: number
  recognised_amount: number
  start_date: string
  end_date: string
  frequency: string
  next_recognition_date: string
  status: "active" | "completed" | "cancelled"
  created_at: string
}

interface RecognitionResult {
  recognised_count: number
  details: { schedule_id: number; charge: string; jv: string }[]
}

const STATUS_TONE: Record<string, string> = {
  active:    "bg-emerald-50 text-emerald-800 border-emerald-200",
  completed: "bg-blue-50 text-blue-800 border-blue-200",
  cancelled: "bg-slate-100 text-slate-600 border-slate-200",
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  active:    <Clock className="w-3 h-3" />,
  completed: <CheckCircle2 className="w-3 h-3" />,
  cancelled: <XCircle className="w-3 h-3" />,
}

const today = () => new Date().toISOString().slice(0, 10)

export default function DeferredRevenuePage() {
  const fmt = useFmt()

  const [schedules, setSchedules]   = useState<DeferredSchedule[]>([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>("active")

  const [runDate, setRunDate]       = useState(today)
  const [running, setRunning]       = useState(false)
  const [runResult, setRunResult]   = useState<RecognitionResult | null>(null)
  const [runError, setRunError]     = useState<string | null>(null)

  const load = useCallback((status: string) => {
    setLoading(true)
    const params = new URLSearchParams({ limit: "200" })
    if (status !== "all") params.set("status", status)
    apiFetch<{ total: number; items: DeferredSchedule[] }>(`/api/deferred-revenue?${params}`)
      .then(d => setSchedules(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load(statusFilter) }, [load, statusFilter])

  const runRecognition = async () => {
    if (!runDate) return
    setRunning(true); setRunResult(null); setRunError(null)
    try {
      const res = await apiFetch<RecognitionResult>(
        `/api/deferred-revenue/run-recognition?recognition_date=${runDate}`,
        { method: "POST" }
      )
      setRunResult(res)
      load(statusFilter)
    } catch (e) {
      setRunError(e instanceof Error ? e.message : "Recognition run failed")
    } finally {
      setRunning(false)
    }
  }

  const activeCount    = schedules.filter(s => s.status === "active").length
  const completedCount = schedules.filter(s => s.status === "completed").length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Deferred Revenue</h1>
            <button
              onClick={() => downloadCSV('deferred-revenue.csv', schedules.map(s => ({ "Invoice ID": s.invoice_id, "Total Amount": s.total_amount, "Recognised": s.recognised_amount, "Remaining": s.total_amount - s.recognised_amount, "Start Date": s.start_date, "End Date": s.end_date, Frequency: s.frequency, "Next Recognition": s.next_recognition_date, Status: s.status })))}
              disabled={schedules.length === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
            >
              <Download className="w-3.5 h-3.5" /> CSV
            </button>
          </div>
          <p className="text-sm text-[#1a1814]/60 mt-0.5">
            IFRS 15 recognition schedules. Run monthly to post Dr Deferred Revenue / Cr Revenue.
          </p>
        </div>

        {/* Run Recognition panel */}
        <div className="flex items-center gap-2 bg-white border border-[#ede9e2] rounded-xl px-4 py-3 shrink-0">
          <Calendar className="w-4 h-4 text-[#b8943f] shrink-0" />
          <input
            type="date"
            value={runDate}
            onChange={e => setRunDate(e.target.value)}
            className="border-0 outline-none text-sm text-[#1a1814] bg-transparent w-36"
          />
          <button
            onClick={runRecognition}
            disabled={running || !runDate}
            className="inline-flex items-center gap-1.5 bg-[#b8943f] text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-[#a07c32] disabled:opacity-50 transition-colors"
          >
            <Play className="w-3 h-3" />
            {running ? "Running…" : "Run"}
          </button>
        </div>
      </div>

      {/* Recognition result */}
      {runResult && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl px-4 py-3 text-sm">
          <span className="font-medium">Recognition complete.</span>{" "}
          {runResult.recognised_count === 0
            ? "No schedules were due on or before that date."
            : `${runResult.recognised_count} schedule${runResult.recognised_count !== 1 ? "s" : ""} recognised.`}
          {runResult.details.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-emerald-700">
              {runResult.details.map(d => (
                <li key={d.schedule_id}>
                  Schedule #{d.schedule_id} → {fmt(parseFloat(d.charge))} ({d.jv})
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {runError && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{runError}</div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {/* Summary counts */}
      <div className="grid grid-cols-3 gap-3">
        {(["active", "completed", "all"] as const).map(s => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`rounded-xl border px-4 py-3 text-left transition-colors ${
              statusFilter === s
                ? "border-[#b8943f] bg-[#faf6ec]"
                : "border-[#ede9e2] bg-white hover:border-[#b8943f]/40"
            }`}
          >
            <div className="text-xs font-semibold uppercase tracking-wide text-[#1a1814]/55 capitalize">
              {s === "all" ? "All" : s}
            </div>
            <div className="text-2xl font-serif font-bold text-[#1a1814] mt-0.5">
              {s === "active" ? activeCount : s === "completed" ? completedCount : schedules.length}
            </div>
          </button>
        ))}
      </div>

      {/* Schedules */}
      {loading ? (
        <div className="text-sm text-[#1a1814]/50 py-8 text-center">Loading…</div>
      ) : schedules.length === 0 ? (
        <div className="bg-white border border-[#ede9e2] rounded-xl px-6 py-12 text-center">
          <TrendingUp className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]">
            {statusFilter === "active" ? "No active schedules" : "No schedules found"}
          </p>
          <p className="text-xs text-[#1a1814]/55 mt-1">
            Schedules are created automatically when invoicing products marked as <em>deferred revenue</em>.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {schedules.map(s => {
            const total      = Number(s.total_amount)
            const recognised = Number(s.recognised_amount)
            const remaining  = Math.max(0, total - recognised)
            const pct        = total > 0 ? Math.min(100, Math.round((recognised / total) * 100)) : 0
            return (
              <div key={s.id} className="bg-white border border-[#ede9e2] rounded-xl px-5 py-4 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-[#1a1814]">Schedule #{s.id}</span>
                    <Link
                      href={`/invoices/${s.invoice_id}`}
                      className="text-xs text-[#b8943f] hover:underline"
                    >
                      Invoice #{s.invoice_id} →
                    </Link>
                  </div>
                  <span className={`inline-flex items-center gap-1 border rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_TONE[s.status] ?? "bg-slate-50 text-slate-700 border-slate-200"}`}>
                    {STATUS_ICON[s.status]}
                    {s.status}
                  </span>
                </div>

                {/* Progress bar */}
                <div>
                  <div className="flex justify-between text-xs text-[#1a1814]/60 mb-1">
                    <span>{fmt(recognised)} recognised</span>
                    <span>{pct}% of {fmt(total)}</span>
                  </div>
                  <div className="h-2 bg-[#ede9e2] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${s.status === "completed" ? "bg-blue-500" : "bg-[#b8943f]"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  {remaining > 0 && (
                    <div className="text-xs text-[#1a1814]/50 mt-1">{fmt(remaining)} remaining</div>
                  )}
                </div>

                {/* Metadata row */}
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-[#1a1814]/60">
                  <span><span className="font-medium text-[#1a1814]/80">Period:</span> {s.start_date} → {s.end_date}</span>
                  <span className="capitalize"><span className="font-medium text-[#1a1814]/80">Frequency:</span> {s.frequency}</span>
                  {s.status === "active" && (
                    <span>
                      <span className="font-medium text-[#1a1814]/80">Next recognition:</span>{" "}
                      <span className={s.next_recognition_date <= today() ? "text-amber-600 font-semibold" : ""}>
                        {s.next_recognition_date}
                      </span>
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
