"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import KpiCard from "@/components/dashboard/KpiCard"
import { formatWeightTriple, type WeightTriple } from "@/lib/spinningUnits"

type Dash = {
  kpis: {
    open_lots: number
    bale_received: WeightTriple
    cone_output: WeightTriple
    dispatched: WeightTriple
    dispatch_value: number
    overall_yield_pct: number
    lot_count: number
    status_summary: Record<string, number>
  }
  wip_by_stage: Record<string, number>
}

export default function SpinningDashboardPage() {
  const fmt = useFmt()
  const [dash, setDash] = useState<Dash | null>(null)

  useEffect(() => {
    apiFetch<Dash>("/api/spinning/reports/dashboard").then(setDash).catch(() => setDash(null))
  }, [])

  const k = dash?.kpis

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title="Spinning Dashboard" orientation="landscape" />
      <div className="print:hidden">
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Spinning Dashboard</h1>
        <p className="text-sm text-[var(--text-muted)]">Kg · Lbs · Bags on weight KPIs · WIP by stage</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard title="Open lots" value={k ? String(k.open_lots) : null} tone="blue" href="/spinning/lots" />
        <KpiCard title="Bale received" value={k ? formatWeightTriple(k.bale_received) : null} tone="amber"
          sub={k ? `${k.bale_received.lbs.toFixed(1)} lb · ${k.bale_received.bags.toFixed(2)} bags` : undefined} />
        <KpiCard title="Cone output" value={k ? formatWeightTriple(k.cone_output) : null} tone="green"
          sub={k ? `${k.cone_output.lbs.toFixed(1)} lb · ${k.cone_output.bags.toFixed(2)} bags` : undefined} />
        <KpiCard title="Dispatched" value={k ? formatWeightTriple(k.dispatched) : null}
          sub={k ? `${k.dispatched.lbs.toFixed(1)} lb` : undefined} />
        <KpiCard title="Dispatch value" value={k ? fmt(k.dispatch_value) : null} tone="emerald" />
        <KpiCard title="Overall yield" value={k ? `${fmt(k.overall_yield_pct)}%` : null} />
        <KpiCard title="Total lots" value={k ? String(k.lot_count) : null} href="/spinning/lots" />
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

      {dash?.wip_by_stage && Object.keys(dash.wip_by_stage).length > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
          <h2 className="text-sm font-semibold mb-3">WIP by stage (kg)</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
            {Object.entries(dash.wip_by_stage).map(([stage, kg]) => (
              <div key={stage} className="rounded-lg border border-[var(--border)] p-2 text-center text-sm">
                <div className="capitalize font-medium">{stage}</div>
                <div className="tabular-nums text-[var(--text-muted)]">{fmt(kg)} kg</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
