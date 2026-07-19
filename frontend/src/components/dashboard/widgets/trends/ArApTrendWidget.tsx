"use client"

import { useState } from "react"
import { Line } from "react-chartjs-2"
import { useFmtCompact } from "@/context/SettingsContext"
import { monthLabel } from "@/lib/dashboardTrends"
import { moneyLineOpts, useTrends } from "./common"

type RangeKey = "3M" | "6M" | "1Y" | "All"
const RANGES: { key: RangeKey; months: number | null }[] = [
  { key: "3M", months: 3 }, { key: "6M", months: 6 }, { key: "1Y", months: 12 }, { key: "All", months: null },
]

/** Month-end AR total vs AP total balances with a timeline selector. */
export default function ArApTrendWidget() {
  const fmt = useFmtCompact()
  const { data, error } = useTrends()
  const [range, setRange] = useState<RangeKey>("1Y")

  const trend = data?.ar_ap_trend
  const n = RANGES.find(r => r.key === range)?.months ?? null
  const slice = <T,>(arr: T[]) => (n ? arr.slice(-n) : arr)

  const months = slice(trend?.months ?? [])
  const ar = slice(trend?.ar ?? []).map(Number)
  const ap = slice(trend?.ap ?? []).map(Number)
  const hasActivity = !!trend && (trend.ar.some(v => Number(v) !== 0) || trend.ap.some(v => Number(v) !== 0))

  const chartData = {
    labels: months.map(monthLabel),
    datasets: [
      {
        label: "Receivables (AR)", data: ar,
        borderColor: "#16a34a", backgroundColor: "rgba(22,163,74,0.10)",
        pointRadius: 2, pointHoverRadius: 5, borderWidth: 2, tension: 0.3, fill: true,
      },
      {
        label: "Payables (AP)", data: ap,
        borderColor: "#ea580c", backgroundColor: "#ea580c",
        pointRadius: 2, pointHoverRadius: 5, borderWidth: 2, tension: 0.3,
      },
    ],
  }

  const btnBase = "px-2 py-0.5 rounded-full text-[10px] font-semibold transition-colors"
  const btnActive = "bg-[var(--primary)] text-white"
  const btnInactive = "bg-[var(--bg-page)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"

  return (
    <div className="h-full flex flex-col bg-white border border-[var(--border)] rounded-xl p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/55">AR vs AP Trend</p>
          <p className="text-[10px] text-[var(--text-primary)]/40 mt-0.5">Month-end receivable vs payable balances</p>
        </div>
        <div className="flex gap-1 flex-shrink-0">
          {RANGES.map(r => (
            <button key={r.key} onClick={() => setRange(r.key)} className={`${btnBase} ${range === r.key ? btnActive : btnInactive}`}>
              {r.key}
            </button>
          ))}
        </div>
      </div>
      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !data ? (
        <div className="shimmer flex-1 rounded-lg" />
      ) : !hasActivity ? (
        <div className="flex-1 flex items-center justify-center text-sm text-[var(--text-primary)]/40">No AR/AP activity yet.</div>
      ) : (
        <div className="flex-1 min-h-0">
          <Line data={chartData} options={moneyLineOpts(fmt, true)} />
        </div>
      )}
    </div>
  )
}
