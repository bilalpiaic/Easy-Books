"use client"

import { Bar } from "react-chartjs-2"
import type { ChartOptions } from "chart.js"
import { useFmtCompact } from "@/context/SettingsContext"
import { TrendShell, moneyBarOpts, useTrends } from "./common"

/** Top vendors by billed spend — the AP mirror of Top Customers. */
export default function TopVendorsWidget() {
  const fmt = useFmtCompact()
  const { data, error } = useTrends()

  const rows = data?.top_vendors ?? []
  const chartData = {
    labels: rows.map(v => v.name.length > 14 ? v.name.slice(0, 12) + "…" : v.name),
    datasets: [{
      label: "Billed Total",
      data: rows.map(v => Number(v.total)),
      backgroundColor: "rgba(234,88,12,0.75)", borderRadius: 4,
    }],
  }

  const opts = { ...moneyBarOpts(fmt), indexAxis: "y" } as ChartOptions<"bar">
  if (opts.scales?.x) opts.scales.x = { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 9 }, callback: v => fmt(Number(v)) } }
  if (opts.scales?.y) opts.scales.y = { grid: { display: false }, ticks: { font: { size: 10 } } }

  return (
    <TrendShell
      title="Top Vendors by Spend" sub="Billed totals, all time"
      href="/vendors" linkLabel="Vendors"
      loading={!data} error={error} empty={rows.length === 0} emptyText="No bill data."
    >
      <Bar data={chartData} options={opts} />
    </TrendShell>
  )
}
