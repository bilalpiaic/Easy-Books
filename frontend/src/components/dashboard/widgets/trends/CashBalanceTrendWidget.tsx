"use client"

import { Line } from "react-chartjs-2"
import { TrendingUp, TrendingDown } from "lucide-react"
import { useFmtCompact } from "@/context/SettingsContext"
import { monthLabel } from "@/lib/dashboardTrends"
import { TrendShell, moneyLineOpts, useTrends } from "./common"

/** Month-end Cash & Bank balance (cumulative over all history). */
export default function CashBalanceTrendWidget() {
  const fmt = useFmtCompact()
  const { data, error } = useTrends()

  const balances = data?.cash_balance.map(Number) ?? []
  const current = balances.length ? balances[balances.length - 1] : 0
  const start = balances.length ? balances[0] : 0
  const delta = current - start
  const DeltaIcon = delta < 0 ? TrendingDown : TrendingUp
  const hasActivity = balances.some(v => v !== 0)

  const chartData = {
    labels: data?.months.map(monthLabel) ?? [],
    datasets: [{
      label: "Cash & Bank",
      data: balances,
      borderColor: "#b8943f", backgroundColor: "rgba(184,148,63,0.12)",
      pointBackgroundColor: "#b8943f", pointRadius: 3, pointHoverRadius: 5,
      borderWidth: 2, tension: 0.3, fill: true,
    }],
  }

  return (
    <TrendShell
      title="Cash Balance Trend"
      sub="Month-end Cash & Bank position"
      href="/banking" linkLabel="Banking"
      loading={!data} error={error} empty={!hasActivity} emptyText="No cash activity yet."
      footer={
        <div className="flex items-baseline gap-2 mt-2">
          <span className="text-sm font-bold text-[var(--text-primary)]">{fmt(current)}</span>
          <span className={`flex items-center gap-0.5 text-[10px] font-semibold ${delta < 0 ? "text-red-600" : "text-green-700"}`}>
            <DeltaIcon className="w-3 h-3" />
            {fmt(Math.abs(delta))} over 12 mo
          </span>
        </div>
      }
    >
      <Line data={chartData} options={moneyLineOpts(fmt)} />
    </TrendShell>
  )
}
