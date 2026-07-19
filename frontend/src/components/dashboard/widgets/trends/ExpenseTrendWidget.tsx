"use client"

import { Line } from "react-chartjs-2"
import { useFmtCompact } from "@/context/SettingsContext"
import { monthLabel } from "@/lib/dashboardTrends"
import { CATEGORICAL, TrendShell, moneyLineOpts, useTrends } from "./common"

/** Monthly trend of the top-5 expense accounts (fixed-order categorical hues). */
export default function ExpenseTrendWidget() {
  const fmt = useFmtCompact()
  const { data, error } = useTrends()

  const accounts = data?.expense_trend.accounts ?? []

  const chartData = {
    labels: data?.months.map(monthLabel) ?? [],
    datasets: accounts.map((name, i) => ({
      label: name.length > 18 ? name.slice(0, 16) + "…" : name,
      data: data?.expense_trend.series[i]?.map(Number) ?? [],
      borderColor: CATEGORICAL[i], backgroundColor: CATEGORICAL[i],
      pointRadius: 2, pointHoverRadius: 5, borderWidth: 2, tension: 0.3,
    })),
  }

  return (
    <TrendShell
      title="Expense Trend" sub="Top 5 expense accounts, monthly"
      href="/pl" linkLabel="P&L"
      loading={!data} error={error} empty={accounts.length === 0} emptyText="No expense data."
    >
      <Line data={chartData} options={moneyLineOpts(fmt, true)} />
    </TrendShell>
  )
}
