"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import KpiCard from "@/components/dashboard/KpiCard"
import { formatWeightTriple, type WeightTriple } from "@/lib/spinningUnits"
import {
  Activity, Factory, PackagePlus, Truck, CircleDot, Settings2,
  ClipboardList, Package, AlertTriangle, Calculator, LayoutDashboard,
} from "lucide-react"

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

const LINKS = [
  { href: "/spinning/setup", label: "Setup", icon: Settings2 },
  { href: "/spinning/plans", label: "Production Plans", icon: ClipboardList },
  { href: "/spinning/lots", label: "Spin Lots", icon: Factory },
  { href: "/spinning/bale-receipts", label: "Bale Receipts", icon: PackagePlus },
  { href: "/spinning/stages", label: "Stage Entries", icon: Activity },
  { href: "/spinning/cone-output", label: "Cone Output", icon: Package },
  { href: "/spinning/waste", label: "Waste Logs", icon: AlertTriangle },
  { href: "/spinning/dispatch", label: "Yarn Dispatch", icon: Truck },
  { href: "/spinning/calculators/yield", label: "Yield Calc", icon: Calculator },
  { href: "/spinning/dashboard", label: "Full Dashboard", icon: LayoutDashboard },
]

export default function SpinningHubPage() {
  const fmt = useFmt()
  const [dash, setDash] = useState<Dash | null>(null)

  useEffect(() => {
    apiFetch<Dash>("/api/spinning/reports/dashboard").then(setDash).catch(() => setDash(null))
  }, [])

  const k = dash?.kpis

  return (
    <div className="p-4 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Yarn Spinning</h1>
        <p className="text-sm text-[var(--text-muted)]">Bale receipt through cone output — multi-stage lot tracking with GL costing</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard title="Open lots" value={k ? String(k.open_lots) : null} tone="blue" href="/spinning/lots" />
        <KpiCard title="Bale received" value={k ? formatWeightTriple(k.bale_received) : null} tone="amber" />
        <KpiCard title="Cone output" value={k ? formatWeightTriple(k.cone_output) : null} tone="green" />
        <KpiCard title="Dispatched" value={k ? formatWeightTriple(k.dispatched) : null} />
        <KpiCard title="Dispatch value" value={k ? fmt(k.dispatch_value) : null} tone="emerald" />
        <KpiCard title="Overall yield" value={k ? `${fmt(k.overall_yield_pct)}%` : null} />
        <KpiCard title="Total lots" value={k ? String(k.lot_count) : null} href="/spinning/lots" />
      </div>

      {k && (
        <div className="text-sm text-[var(--text-muted)] flex flex-wrap gap-3">
          {Object.entries(k.status_summary).map(([s, n]) => (
            <span key={s} className="capitalize">{s.replace("_", " ")}: {n}</span>
          ))}
        </div>
      )}

      {dash?.wip_by_stage && Object.keys(dash.wip_by_stage).length > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
          <h2 className="text-sm font-semibold mb-2">WIP by stage (kg)</h2>
          <div className="flex flex-wrap gap-3 text-sm">
            {Object.entries(dash.wip_by_stage).map(([stage, kg]) => (
              <span key={stage} className="capitalize px-2 py-1 rounded-lg border border-[var(--border)]">
                {stage}: {fmt(kg)} kg
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {LINKS.map(l => {
          const Icon = l.icon
          return (
            <Link key={l.href} href={l.href}
              className="flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-3 text-sm hover:border-[var(--primary)]/40">
              <Icon className="w-4 h-4 text-[var(--primary)]" />
              {l.label}
            </Link>
          )
        })}
      </div>
    </div>
  )
}
