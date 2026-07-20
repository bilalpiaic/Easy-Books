"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import KpiCard from "@/components/dashboard/KpiCard"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { formatWeightTriple, type WeightTriple } from "@/lib/weavingUnits"
import { Activity, Factory, PackagePlus, Truck, Scissors, Layers, Calculator } from "lucide-react"

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
}

const LINKS = [
  { href: "/weaving/setup", label: "Setup", icon: Scissors },
  { href: "/weaving/contracts", label: "Contracts", icon: Factory },
  { href: "/weaving/yarn-inward", label: "Yarn Inward", icon: PackagePlus },
  { href: "/weaving/sizing", label: "Sizing", icon: Layers },
  { href: "/weaving/production", label: "Production", icon: Activity },
  { href: "/weaving/dispatch", label: "Dispatch", icon: Truck },
  { href: "/weaving/calculators/weaving", label: "Weaving Calc", icon: Calculator },
  { href: "/weaving/calculators/sizing", label: "Sizing Calc", icon: Calculator },
  { href: "/weaving/dashboard", label: "Full Dashboard", icon: Factory },
]

export default function WeavingHubPage() {
  const fmt = useFmt()
  const [dash, setDash] = useState<Dash | null>(null)

  useEffect(() => {
    apiFetch<Dash>("/api/weaving/reports/dashboard").then(setDash).catch(() => setDash(null))
  }, [])

  const k = dash?.kpis

  return (
    <div className="p-4 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Weaving</h1>
        <p className="text-sm text-[var(--text-muted)]">Unit control — contracts through dispatch (memo/ops, no GL in v1)</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard title="Yarn received" value={k ? formatWeightTriple(k.yarn_received) : null} tone="blue" />
        <KpiCard title="Yarn used" value={k ? formatWeightTriple(k.yarn_used) : null} tone="amber" />
        <KpiCard title="Yarn balance" value={k ? formatWeightTriple(k.yarn_balance) : null} tone="green" />
        <KpiCard title="Weaving revenue" value={k ? fmt(k.weaving_revenue) : null} tone="emerald" />
        <KpiCard title="Grey meters" value={k ? fmt(k.grey_meters) : null} />
        <KpiCard title="Dispatched m" value={k ? fmt(k.dispatch_meters) : null} />
        <KpiCard title="Avg efficiency" value={k ? `${fmt(k.avg_efficiency_pct)}%` : null} />
        <KpiCard title="Contracts" value={k ? String(k.contract_count) : null} href="/weaving/contracts" />
      </div>

      {k && (
        <div className="text-sm text-[var(--text-muted)] flex flex-wrap gap-3">
          <span>Sizing out: <WeightTripleDisplay triple={k.sizing_output} /></span>
          {Object.entries(k.status_summary).map(([s, n]) => (
            <span key={s} className="capitalize">{s.replace("_", " ")}: {n}</span>
          ))}
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
