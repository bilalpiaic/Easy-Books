"use client"

import { Chart } from "react-chartjs-2"
import { useFmtCompact } from "@/context/SettingsContext"
import { monthLabel } from "@/lib/dashboardTrends"
import { TrendShell, useTrends } from "./common"

/** Monthly cash in vs out (10xx accounts) with the net movement line. */
export default function CashFlowTrendWidget() {
  const fmt = useFmtCompact()
  const { data, error } = useTrends()

  const hasActivity = !!data && (
    data.cashflow.inflow.some(v => v !== 0) || data.cashflow.outflow.some(v => v !== 0)
  )

  const chartData = {
    labels: data?.months.map(monthLabel) ?? [],
    datasets: [
      {
        type: "line" as const, label: "Net", order: 0,
        data: data?.cashflow.net.map(Number) ?? [],
        borderColor: "#b8943f", backgroundColor: "#b8943f",
        pointStyle: "rect" as const, pointRadius: 3, pointHoverRadius: 5,
        borderWidth: 2, tension: 0.3,
      },
      {
        type: "bar" as const, label: "Cash In", order: 1,
        data: data?.cashflow.inflow.map(Number) ?? [],
        backgroundColor: "rgba(22,163,74,0.55)", borderRadius: 3,
      },
      {
        // negated so outflows diverge below the zero axis
        type: "bar" as const, label: "Cash Out", order: 2,
        data: data?.cashflow.outflow.map(v => -Number(v)) ?? [],
        backgroundColor: "rgba(220,38,38,0.5)", borderRadius: 3,
      },
    ],
  }

  return (
    <TrendShell
      title="Cash Flow" sub="Monthly cash in vs out with net movement"
      href="/banking" linkLabel="Banking"
      loading={!data} error={error} empty={!hasActivity} emptyText="No cash activity yet."
    >
      <Chart type="bar" data={chartData} options={{
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, font: { size: 10 } } },
          tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmt(Math.abs(ctx.parsed.y ?? 0))}` } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 9 }, maxTicksLimit: 12 } },
          y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 9 }, callback: v => fmt(Math.abs(Number(v))) } },
        },
      }} />
    </TrendShell>
  )
}
