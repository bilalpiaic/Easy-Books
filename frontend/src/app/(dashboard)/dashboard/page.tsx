"use client"

import { useEffect, useState } from "react"
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Title, Tooltip, Legend, Filler,
  type ChartOptions,
} from "chart.js"
import { useFmt, useSettings } from "@/context/SettingsContext"
import { apiFetch } from "@/lib/api"
import DateRangePicker from "@/components/DateRangePicker"
import DashboardGrid from "@/components/dashboard/DashboardGrid"
import { WIDGET_REGISTRY } from "@/lib/dashboardWidgets"
import { useDashboardLayout } from "@/hooks/useDashboardLayout"
import {
  type DashboardData, type ChartData, type WidgetContext, type DashboardChartConfigs,
} from "@/lib/dashboardWidgets"

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Title, Tooltip, Legend, Filler
)

const DOUGHNUT_COLORS = [
  "#b8943f","#2563eb","#16a34a","#dc2626","#7c3aed",
  "#0891b2","#ea580c","#db2777","#65a30d",
]

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

export default function Dashboard() {
  const fmt = useFmt()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd]     = useState(range.end)
  const [data, setData]   = useState<DashboardData | null>(null)
  const [charts, setCharts] = useState<ChartData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { settings, reload: reloadSettings } = useSettings()
  const [checklistDismissed, setChecklistDismissed] = useState(false)

  const layout = useDashboardLayout()

  useEffect(() => {
    setData(null)
    apiFetch<DashboardData>(`/api/reports/dashboard?start=${start}&end=${end}`)
      .then(d => { if (!d.summary) throw new Error("Invalid response"); setData(d) })
      .catch(err => setError((err as Error).message))
  }, [start, end])

  useEffect(() => {
    apiFetch<ChartData>("/api/reports/dashboard/charts?months=12")
      .then(setCharts)
      .catch(() => {})
  }, [])

  const s = data?.summary
  const netProfit = s ? s.total_revenue - s.total_expense : 0
  const margin = s && s.total_revenue > 0 ? (netProfit / s.total_revenue * 100).toFixed(1) : null

  const monthLabels = charts?.monthly.map(m => {
    const [y, mo] = m.month.split("-")
    return new Date(+y, +mo - 1).toLocaleString("default", { month: "short" })
  }) ?? []

  const barData = {
    labels: monthLabels,
    datasets: [
      { label: "Revenue",  data: charts?.monthly.map(m => m.revenue) ?? [],  backgroundColor: "rgba(22,163,74,0.75)",  borderRadius: 4 },
      { label: "Expenses", data: charts?.monthly.map(m => m.expenses) ?? [], backgroundColor: "rgba(220,38,38,0.70)", borderRadius: 4 },
    ],
  }
  const lineData = {
    labels: monthLabels,
    datasets: [{ label: "Net Profit", data: charts?.monthly.map(m => m.profit) ?? [], borderColor: "#b8943f", backgroundColor: "rgba(184,148,63,0.10)", pointBackgroundColor: "#b8943f", pointRadius: 4, tension: 0.4, fill: true }],
  }
  const doughnutData = {
    labels: charts?.expense_breakdown.map(e => e.account) ?? [],
    datasets: [{ data: charts?.expense_breakdown.map(e => e.amount) ?? [], backgroundColor: DOUGHNUT_COLORS, borderWidth: 2, borderColor: "#fff" }],
  }
  const customerBarData = {
    labels: charts?.top_customers.map(c => c.name.length > 14 ? c.name.slice(0, 12) + "…" : c.name) ?? [],
    datasets: [{ label: "Invoice Total", data: charts?.top_customers.map(c => c.total) ?? [], backgroundColor: "rgba(184,148,63,0.80)", borderRadius: 4 }],
  }

  const agingLabels = ["Current", "1–30d", "31–60d", "61–90d", "90d+"]
  const agingValues = s?.ar_aging
    ? [s.ar_aging.current, s.ar_aging["1_30"], s.ar_aging["31_60"], s.ar_aging["61_90"], s.ar_aging.over_90]
    : null
  const agingBarData = {
    labels: agingLabels,
    datasets: [{
      data: agingValues ?? [0, 0, 0, 0, 0],
      backgroundColor: [
        "rgba(22,163,74,0.78)", "rgba(234,179,8,0.78)", "rgba(249,115,22,0.78)",
        "rgba(239,68,68,0.82)", "rgba(185,28,28,0.88)",
      ],
      borderRadius: 4,
    }],
  }

  const baseChartOpts: ChartOptions<"bar"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmt(ctx.parsed.y as number) } } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmt(v as number) } },
    },
  }
  const lineOpts: ChartOptions<"line"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmt((ctx.parsed.y ?? 0) as number) } } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmt(v as number) } },
    },
  }
  const doughnutOpts: ChartOptions<"doughnut"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 12, padding: 8 } },
      tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.parsed)}` } },
    },
    cutout: "62%",
  }

  const chartConfigs: DashboardChartConfigs = {
    barData, lineData, doughnutData, customerBarData, agingBarData,
    baseChartOpts, lineOpts, doughnutOpts,
  }

  const ctx: WidgetContext = {
    data, charts, s, netProfit, margin, fmt,
    agingLabels, agingValues, chartConfigs,
    settings, reloadSettings, checklistDismissed, setChecklistDismissed,
  }

  const onboardingWidget = WIDGET_REGISTRY.find(w => w.id === "onboarding")
  const alertsWidget = WIDGET_REGISTRY.find(w => w.id === "alerts")

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">Dashboard</h1>
          <p className="text-xs text-[#1a1814]/50 mt-0.5 font-medium tracking-wide uppercase">Financial Overview</p>
        </div>
        <div className="bg-white border border-[#ede9e2] rounded-xl px-3 py-2 shadow-sm">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>}

      {/* Pinned notices (not part of the customizable grid) */}
      {onboardingWidget?.render(ctx)}
      {alertsWidget?.render(ctx)}

      <DashboardGrid layout={layout} ctx={ctx} editing={false} />
    </div>
  )
}
