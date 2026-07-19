"use client"

import { useEffect, useState, type ReactNode } from "react"
import Link from "next/link"
import {
  Chart as ChartJS, BarController, LineController, DoughnutController,
  BarElement, LineElement, PointElement, ArcElement,
  CategoryScale, LinearScale, Legend, Tooltip, Filler,
} from "chart.js"
import type { ChartOptions } from "chart.js"
import { fetchDashboardTrends, type TrendsData } from "@/lib/dashboardTrends"

// Self-registered so widgets don't depend on the dashboard page's
// Chart.js registration order (registration is idempotent).
ChartJS.register(
  BarController, LineController, DoughnutController,
  BarElement, LineElement, PointElement, ArcElement,
  CategoryScale, LinearScale, Legend, Tooltip, Filler,
)

// Fixed-order categorical palette (validated: lightness band, chroma floor,
// CVD separation, normal-vision floor, contrast — all pass on light surface).
// Same set the dashboard page uses; assign by position, never cycle or re-rank.
export const CATEGORICAL = [
  "#2CA01C", "#2563eb", "#dc2626", "#7c3aed", "#0891b2",
  "#ea580c", "#db2777", "#65a30d",
]

export function useTrends() {
  const [data, setData] = useState<TrendsData | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    let alive = true
    fetchDashboardTrends()
      .then(d => { if (alive) setData(d) })
      .catch(() => { if (alive) setError(true) })
    return () => { alive = false }
  }, [])
  return { data, error }
}

interface ShellProps {
  title: string
  sub?: string
  href?: string
  linkLabel?: string
  loading: boolean
  error: boolean
  empty?: boolean
  emptyText?: string
  footer?: ReactNode
  children: ReactNode
}

/** Standard card chrome for a trend widget: header row + loading/error/empty states. */
export function TrendShell({
  title, sub, href, linkLabel, loading, error, empty, emptyText, footer, children,
}: ShellProps) {
  return (
    <div className="h-full flex flex-col bg-white border border-[var(--border)] rounded-xl p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/55">{title}</p>
          {sub && <p className="text-[10px] text-[var(--text-primary)]/40 mt-0.5">{sub}</p>}
        </div>
        {href && (
          <Link href={href} className="text-[11px] text-[#b8943f] font-semibold hover:text-[#8a6d2e] flex-shrink-0">
            {linkLabel ?? "View"} →
          </Link>
        )}
      </div>
      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : loading ? (
        <div className="shimmer flex-1 rounded-lg" />
      ) : empty ? (
        <div className="flex-1 flex items-center justify-center text-sm text-[var(--text-primary)]/40">
          {emptyText ?? "No data yet."}
        </div>
      ) : (
        <>
          <div className="flex-1 min-h-0">{children}</div>
          {footer}
        </>
      )}
    </div>
  )
}

type FmtFn = (n: number) => string

const legendBottom = {
  position: "bottom" as const,
  labels: { usePointStyle: true, boxWidth: 8, font: { size: 10 } },
}

/** Money y-axis bar options; pass showLegend for ≥2 series. */
export function moneyBarOpts(fmt: FmtFn, showLegend = false): ChartOptions<"bar"> {
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: showLegend ? legendBottom : { display: false },
      tooltip: { callbacks: { label: ctx => `${ctx.dataset.label ?? ""}: ${fmt(Math.abs(ctx.parsed.y ?? 0))}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 9 }, maxTicksLimit: 12 } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 9 }, callback: v => fmt(Math.abs(Number(v))) } },
    },
  }
}

export function moneyLineOpts(fmt: FmtFn, showLegend = false): ChartOptions<"line"> {
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: showLegend ? legendBottom : { display: false },
      tooltip: { mode: "index", intersect: false, callbacks: { label: ctx => `${ctx.dataset.label ?? ""}: ${fmt((ctx.parsed.y ?? 0) as number)}` } },
    },
    interaction: { mode: "index", intersect: false },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 9 }, maxTicksLimit: 12 } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 9 }, callback: v => fmt(Number(v)) } },
    },
  }
}

export function doughnutOpts(fmt: FmtFn): ChartOptions<"doughnut"> {
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 12, padding: 8 } },
      tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.parsed)}` } },
    },
    cutout: "62%",
  }
}
