"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { usePRAPortal } from "@/hooks/usePRAPortal"
import { useHomeDashboard } from "@/hooks/useHomeDashboard"
import { Settings2 } from "lucide-react"
import { useTranslation } from "react-i18next"
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Title, Tooltip, Legend, Filler,
  type ChartOptions,
} from "chart.js"
import { useFmt, useFmtCompact, useSettings } from "@/context/SettingsContext"
import { apiFetch } from "@/lib/api"
import DateRangePicker from "@/components/DateRangePicker"
import DashboardGrid from "@/components/dashboard/DashboardGrid"
import { WIDGET_REGISTRY } from "@/lib/dashboardWidgets"
import { useDashboardLayout } from "@/hooks/useDashboardLayout"
import {
  type DashboardData, type ChartData, type WidgetContext, type DashboardChartConfigs,
} from "@/lib/dashboardWidgets"
import type { OperationsSummary } from "@/lib/operationsSummary"

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Title, Tooltip, Legend, Filler
)

const DOUGHNUT_COLORS = [
  "#2CA01C","#2563eb","#dc2626","#7c3aed","#0891b2",
  "#ea580c","#db2777","#65a30d",
]

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

function DashboardInner() {
  const fmt = useFmtCompact()
  const fmtFull = useFmt()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd]     = useState(range.end)
  const [data, setData]   = useState<DashboardData | null>(null)
  const [charts, setCharts] = useState<ChartData | null>(null)
  const [opsSummary, setOpsSummary] = useState<OperationsSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { settings, reload: reloadSettings } = useSettings()
  const { isPortal, settled: praSettled } = usePRAPortal()
  const { view, setView, opsAvailable, settled: homeSettled, subtitle } = useHomeDashboard()
  const router = useRouter()
  const { t } = useTranslation()
  const [checklistDismissed, setChecklistDismissed] = useState(false)

  const layout = useDashboardLayout(view)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    if (praSettled && isPortal) router.replace("/pra-dashboard")
  }, [praSettled, isPortal, router])

  useEffect(() => {
    if (view !== "financial") return
    setData(null)
    apiFetch<DashboardData>(`/api/reports/dashboard?start=${start}&end=${end}`)
      .then(d => { if (!d.summary) throw new Error("Invalid response"); setData(d) })
      .catch(err => setError((err as Error).message))
  }, [start, end, view])

  useEffect(() => {
    if (view !== "financial") return
    apiFetch<ChartData>("/api/reports/dashboard/charts?months=12")
      .then(setCharts)
      .catch(() => {})
  }, [view])

  useEffect(() => {
    if (view !== "operations") return
    setOpsSummary(null)
    apiFetch<OperationsSummary>("/api/dashboard/operations-summary")
      .then(setOpsSummary)
      .catch(err => setError((err as Error).message))
  }, [view])

  // Exit customize mode when switching homes so save state stays per-view
  useEffect(() => {
    setEditing(false)
  }, [view])

  if ((praSettled && isPortal) || !homeSettled) return null

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
    datasets: [{ label: "Net Profit", data: charts?.monthly.map(m => m.profit) ?? [], borderColor: "#2CA01C", backgroundColor: "rgba(44,160,28,0.10)", pointBackgroundColor: "#2CA01C", pointRadius: 4, tension: 0.4, fill: true }],
  }
  const doughnutData = {
    labels: charts?.expense_breakdown.map(e => e.account) ?? [],
    datasets: [{ data: charts?.expense_breakdown.map(e => e.amount) ?? [], backgroundColor: DOUGHNUT_COLORS, borderWidth: 2, borderColor: "#fff" }],
  }
  const customerBarData = {
    labels: charts?.top_customers.map(c => c.name.length > 14 ? c.name.slice(0, 12) + "…" : c.name) ?? [],
    datasets: [{ label: "Invoice Total", data: charts?.top_customers.map(c => c.total) ?? [], backgroundColor: "rgba(44,160,28,0.80)", borderRadius: 4 }],
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
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtFull(ctx.parsed.y as number) } } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmt(v as number) } },
    },
  }
  const lineOpts: ChartOptions<"line"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtFull((ctx.parsed.y ?? 0) as number) } } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmt(v as number) } },
    },
  }
  const doughnutOpts: ChartOptions<"doughnut"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 12, padding: 8 } },
      tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmtFull(ctx.parsed)}` } },
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
    settings, reloadSettings, checklistDismissed, setChecklistDismissed, t,
    quickActions: layout.quickActions,
    updateQuickActions: layout.updateQuickActions,
    view,
    opsSummary,
  }

  const onboardingWidget = WIDGET_REGISTRY.find(w => w.id === "onboarding")
  const alertsWidget = WIDGET_REGISTRY.find(w => w.id === "alerts")

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[var(--text-primary)]">
            {view === "operations"
              ? t('nav.OperationsDashboard', 'Operations Dashboard')
              : t('nav.Dashboard', 'Dashboard')}
          </h1>
          <p className="text-xs text-[var(--text-primary)]/50 mt-0.5 font-medium tracking-wide uppercase">
            {view === "financial" ? t('common.financialOverview', 'Financial Overview') : subtitle}
          </p>
          {opsAvailable && (
            <div className="mt-2 inline-flex rounded-lg border border-[var(--border)] bg-white p-0.5 shadow-sm print:hidden">
              <button
                type="button"
                onClick={() => setView("financial")}
                className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                  view === "financial"
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--text-primary)]/60 hover:text-[var(--text-primary)]"
                }`}
              >
                Financial
              </button>
              <button
                type="button"
                onClick={() => setView("operations")}
                className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                  view === "operations"
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--text-primary)]/60 hover:text-[var(--text-primary)]"
                }`}
              >
                Operations
              </button>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {view === "financial" && (
            <div className="bg-white border border-[var(--border)] rounded-xl px-3 py-2 shadow-sm">
              <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label={t('common.period', 'Period')} />
            </div>
          )}
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--border)] bg-white shadow-sm text-sm font-medium text-[var(--text-primary)]/75 hover:border-[var(--primary)]/40 transition-colors"
            >
              <Settings2 className="w-4 h-4 text-[var(--primary)]" /> {t('common.customize', 'Customize')}
            </button>
          )}
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>}

      {/* Pinned notices — financial home only */}
      {view === "financial" && onboardingWidget?.render(ctx)}
      {view === "financial" && alertsWidget?.render(ctx)}

      <DashboardGrid layout={layout} ctx={ctx} editing={editing} onExitEditing={() => setEditing(false)} />
    </div>
  )
}

export default function Dashboard() {
  return (
    <Suspense fallback={<div className="shimmer h-40 rounded-xl" />}>
      <DashboardInner />
    </Suspense>
  )
}
