"use client"

import { useEffect, useState } from "react"
import {
  Chart as ChartJS, BarController, LineController, BarElement, LineElement,
  PointElement, CategoryScale, LinearScale, Legend, Tooltip,
} from "chart.js"
import { Chart } from "react-chartjs-2"
import { TrendingUp, TrendingDown } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmtCompact } from "@/context/SettingsContext"

// Self-registered so the widget doesn't depend on the dashboard page's
// Chart.js registration order (registration is idempotent).
ChartJS.register(
  BarController, LineController, BarElement, LineElement,
  PointElement, CategoryScale, LinearScale, Legend, Tooltip,
)

type RangeKey = "3M" | "6M" | "1Y" | "All"
const RANGES: { key: RangeKey; months: number | null }[] = [
  { key: "3M", months: 3 }, { key: "6M", months: 6 }, { key: "1Y", months: 12 }, { key: "All", months: null },
]

interface NetWorthPoint { month: string; assets: number; liabilities: number; net_worth: number }

export default function NetWorthTrendWidget() {
  const fmt = useFmtCompact()
  const [series, setSeries] = useState<NetWorthPoint[] | null>(null)
  const [error, setError] = useState(false)
  const [range, setRange] = useState<RangeKey>("1Y")

  useEffect(() => {
    apiFetch<{ series: NetWorthPoint[] }>("/api/reports/dashboard/net-worth?months=36")
      .then(r => setSeries(r.series))
      .catch(() => setError(true))
  }, [])

  const months = RANGES.find(r => r.key === range)?.months ?? null
  const visible = series ? (months ? series.slice(-months) : series) : []

  const current = visible.length ? Number(visible[visible.length - 1].net_worth) : 0
  const start = visible.length ? Number(visible[0].net_worth) : 0
  const delta = current - start
  const pct = start !== 0 ? (delta / Math.abs(start)) * 100 : null
  const DeltaIcon = delta < 0 ? TrendingDown : TrendingUp

  const chartData = {
    labels: visible.map(p => p.month),
    datasets: [
      {
        type: "line" as const, label: "Net Worth", order: 0,
        data: visible.map(p => Number(p.net_worth)),
        borderColor: "#b8943f", backgroundColor: "#b8943f",
        pointStyle: "rect" as const, pointRadius: 3, pointHoverRadius: 5,
        borderWidth: 2, tension: 0.3,
      },
      {
        type: "bar" as const, label: "Assets", order: 1,
        data: visible.map(p => Number(p.assets)),
        backgroundColor: "rgba(22, 163, 74, 0.55)", borderRadius: 3,
      },
      {
        // negated so liabilities diverge below the zero axis
        type: "bar" as const, label: "Liabilities", order: 2,
        data: visible.map(p => -Number(p.liabilities)),
        backgroundColor: "rgba(220, 38, 38, 0.5)", borderRadius: 3,
      },
    ],
  }

  const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "bottom" as const,
        labels: { usePointStyle: true, boxWidth: 8, font: { size: 10 } },
      },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
            `${ctx.dataset.label}: ${fmt(Math.abs(ctx.parsed.y ?? 0))}`,
        },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 9 }, maxTicksLimit: 12 } },
      y: {
        grid: { color: "rgba(0, 0, 0, 0.05)" },
        ticks: { font: { size: 9 }, callback: (v: string | number) => fmt(Math.abs(Number(v))) },
      },
    },
  }

  const btnBase = "px-2 py-0.5 rounded-full text-[10px] font-semibold transition-colors"
  const btnActive = "bg-[var(--primary)] text-white"
  const btnInactive = "bg-[var(--bg-page)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"

  return (
    <div className="h-full flex flex-col bg-white border border-[var(--border)] rounded-xl p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/55">Net Worth</p>
          {visible.length > 0 && (
            <div className="flex items-baseline gap-2 mt-0.5">
              <p className="text-base font-bold text-[var(--text-primary)] leading-none">{fmt(current)}</p>
              <span className={`flex items-center gap-0.5 text-[10px] font-semibold ${delta < 0 ? "text-red-600" : "text-green-700"}`}>
                <DeltaIcon className="w-3 h-3" />
                {fmt(Math.abs(delta))}{pct !== null && ` (${Math.abs(pct).toFixed(1)}%)`}
              </span>
            </div>
          )}
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
      ) : !series ? (
        <div className="shimmer flex-1 rounded-lg" />
      ) : series.length === 0 ? (
        <div className="text-sm text-[var(--text-primary)]/40">No transaction history yet.</div>
      ) : (
        <div className="flex-1 min-h-0">
          <Chart type="bar" data={chartData} options={chartOpts} />
        </div>
      )}
    </div>
  )
}
