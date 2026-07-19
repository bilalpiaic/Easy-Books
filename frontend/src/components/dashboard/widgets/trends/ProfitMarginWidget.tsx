"use client"

import { Line } from "react-chartjs-2"
import type { ChartData } from "@/lib/dashboardWidgets"
import { TrendShell } from "./common"

/** Monthly net profit margin % — derived from the page's monthly rev/exp series. */
export default function ProfitMarginWidget({ charts }: { charts: ChartData | null }) {
  const monthly = charts?.monthly ?? []
  const raw = monthly.map(m =>
    Number(m.revenue) > 0 ? (Number(m.profit) / Number(m.revenue)) * 100 : null
  )
  // Winsorize for display: a near-zero-revenue month can produce a ±100,000%
  // outlier that flattens every other point. Tooltip keeps the true value.
  const CAP = 150
  const points = raw.map(p => p === null ? null : Math.max(-CAP, Math.min(CAP, p)))
  const hasActivity = points.some(p => p !== null)

  const labels = monthly.map(m => {
    const [y, mo] = m.month.split("-")
    return new Date(+y, +mo - 1).toLocaleString("default", { month: "short" })
  })

  const chartData = {
    labels,
    datasets: [{
      label: "Margin %",
      data: points,
      borderColor: "#7c3aed", backgroundColor: "rgba(124,58,237,0.10)",
      pointBackgroundColor: "#7c3aed", pointRadius: 3, pointHoverRadius: 5,
      borderWidth: 2, tension: 0.3, fill: true, spanGaps: true,
    }],
  }

  return (
    <TrendShell
      title="Profit Margin" sub="Net profit as % of revenue, monthly"
      href="/pl" linkLabel="P&L"
      loading={!charts} error={false} empty={!hasActivity} emptyText="No revenue recorded yet."
    >
      <Line data={chartData} options={{
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => {
            const real = raw[ctx.dataIndex]
            return ` ${(real ?? 0).toFixed(1)}%${real !== null && Math.abs(real) > CAP ? " (clipped)" : ""}`
          } } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 9 }, maxTicksLimit: 12 } },
          y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 9 }, callback: v => `${Number(v).toFixed(0)}%` } },
        },
      }} />
    </TrendShell>
  )
}
