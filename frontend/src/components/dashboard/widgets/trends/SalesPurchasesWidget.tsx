"use client"

import { Bar } from "react-chartjs-2"
import { useFmtCompact } from "@/context/SettingsContext"
import { monthLabel } from "@/lib/dashboardTrends"
import { TrendShell, moneyBarOpts, useTrends } from "./common"

/** Monthly invoiced sales vs billed purchases (document totals, void excluded). */
export default function SalesPurchasesWidget() {
  const fmt = useFmtCompact()
  const { data, error } = useTrends()

  const hasActivity = !!data && (
    data.sales_purchases.sales.some(v => v !== 0) || data.sales_purchases.purchases.some(v => v !== 0)
  )

  const chartData = {
    labels: data?.months.map(monthLabel) ?? [],
    datasets: [
      { label: "Sales", data: data?.sales_purchases.sales.map(Number) ?? [], backgroundColor: "rgba(22,163,74,0.75)", borderRadius: 4 },
      { label: "Purchases", data: data?.sales_purchases.purchases.map(Number) ?? [], backgroundColor: "rgba(37,99,235,0.65)", borderRadius: 4 },
    ],
  }

  return (
    <TrendShell
      title="Sales vs Purchases" sub="Invoiced vs billed per month"
      href="/invoices" linkLabel="Invoices"
      loading={!data} error={error} empty={!hasActivity} emptyText="No invoices or bills yet."
    >
      <Bar data={chartData} options={moneyBarOpts(fmt, true)} />
    </TrendShell>
  )
}
