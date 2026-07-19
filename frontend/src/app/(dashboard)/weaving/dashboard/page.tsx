"use client"

import { useEffect, useState } from "react"
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend, Filler,
} from "chart.js"
import { Line } from "react-chartjs-2"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import KpiCard from "@/components/dashboard/KpiCard"
import { formatWeightTriple, type WeightTriple } from "@/lib/weavingUnits"

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend, Filler)

type Dash = {
  kpis: {
    yarn_received: WeightTriple
    yarn_used: WeightTriple
    yarn_balance: WeightTriple
    sizing_output: WeightTriple
    grey_meters: number
    dispatch_meters: number
    weaving_revenue: number
    avg_efficiency_pct: number
    contract_count: number
    status_summary: Record<string, number>
  }
  monthly_trend: {
    month: string
    yarn_received: WeightTriple
    yarn_used: WeightTriple
    grey_meters: number
    dispatch_meters: number
    weaving_revenue: number
  }[]
}

export default function WeavingDashboardPage() {
  const fmt = useFmt()
  const [dash, setDash] = useState<Dash | null>(null)

  useEffect(() => {
    apiFetch<Dash>("/api/weaving/reports/dashboard").then(setDash).catch(() => setDash(null))
  }, [])

  const k = dash?.kpis
  const trend = dash?.monthly_trend ?? []

  const chartData = {
    labels: trend.map(t => t.month),
    datasets: [
      {
        label: "Yarn received (kg)",
        data: trend.map(t => t.yarn_received.kg),
        borderColor: "#2563eb",
        backgroundColor: "rgba(37,99,235,0.15)",
        tension: 0.3,
        fill: true,
      },
      {
        label: "Yarn used (kg)",
        data: trend.map(t => t.yarn_used.kg),
        borderColor: "#d97706",
        backgroundColor: "rgba(217,119,6,0.1)",
        tension: 0.3,
        fill: true,
      },
      {
        label: "Dispatch m",
        data: trend.map(t => t.dispatch_meters),
        borderColor: "#059669",
        tension: 0.3,
        yAxisID: "y1",
      },
    ],
  }

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title="Weaving Dashboard" orientation="landscape" />
      <div className="print:hidden">
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Weaving Dashboard</h1>
        <p className="text-sm text-[var(--text-muted)]">Kg · Lbs · Bags on yarn KPIs · monthly trend</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard title="Yarn received" value={k ? formatWeightTriple(k.yarn_received) : null} tone="blue"
          sub={k ? `${k.yarn_received.lbs.toFixed(1)} lb · ${k.yarn_received.bags.toFixed(2)} bags` : undefined} />
        <KpiCard title="Yarn used" value={k ? formatWeightTriple(k.yarn_used) : null} tone="amber"
          sub={k ? `${k.yarn_used.lbs.toFixed(1)} lb · ${k.yarn_used.bags.toFixed(2)} bags` : undefined} />
        <KpiCard title="Yarn balance" value={k ? formatWeightTriple(k.yarn_balance) : null} tone="green"
          sub={k ? `${k.yarn_balance.lbs.toFixed(1)} lb · ${k.yarn_balance.bags.toFixed(2)} bags` : undefined} />
        <KpiCard title="Sizing output" value={k ? formatWeightTriple(k.sizing_output) : null} />
        <KpiCard title="Grey meters" value={k ? fmt(k.grey_meters) : null} />
        <KpiCard title="Dispatch meters" value={k ? fmt(k.dispatch_meters) : null} />
        <KpiCard title="Weaving revenue" value={k ? fmt(k.weaving_revenue) : null} tone="emerald" />
        <KpiCard title="Avg efficiency" value={k ? `${fmt(k.avg_efficiency_pct)}%` : null} />
      </div>

      {k && Object.keys(k.status_summary).length > 0 && (
        <div className="flex flex-wrap gap-2 text-sm">
          {Object.entries(k.status_summary).map(([s, n]) => (
            <span key={s} className="px-2 py-1 rounded-lg border border-[var(--border)] capitalize">
              {s.replace("_", " ")}: {n}
            </span>
          ))}
        </div>
      )}

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
        <h2 className="text-sm font-semibold mb-3">Monthly trend</h2>
        {trend.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">No activity yet</p>
        ) : (
          <div className="h-72">
            <Line
              data={chartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                scales: {
                  y: { beginAtZero: true, title: { display: true, text: "Kg" } },
                  y1: {
                    beginAtZero: true,
                    position: "right",
                    grid: { drawOnChartArea: false },
                    title: { display: true, text: "Meters" },
                  },
                },
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
