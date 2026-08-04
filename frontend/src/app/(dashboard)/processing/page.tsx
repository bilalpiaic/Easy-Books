"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import KpiCard from "@/components/dashboard/KpiCard"
import {
  Activity, ClipboardCheck, DoorOpen, Factory, FileCheck, FileSignature,
  Layers, Package, Receipt, Scale, Scissors, Settings2, Truck, AlertTriangle,
  BookOpen, PieChart, ScrollText,
} from "lucide-react"

type Dash = {
  kpis: {
    lots_total: number
    lots_in_process: number
    lots_ready: number
    received_mtr: number
    ready_mtr: number
    rejection_pending_mtr: number
    visible_wastage_mtr: number
    invisible_wastage_mtr: number
  }
}

const LINKS = [
  { href: "/processing/setup", label: "Setup", icon: Settings2 },
  { href: "/processing/sales-orders", label: "Sales Orders", icon: FileSignature },
  { href: "/processing/lots", label: "Grey Lots", icon: Package },
  { href: "/processing/mending", label: "Mending", icon: Scissors },
  { href: "/processing/kachi-parchi", label: "Kachi Parchi", icon: ScrollText },
  { href: "/processing/pakki-parchi", label: "Pakki Parchi", icon: FileCheck },
  { href: "/processing/rejection", label: "Rejection / OGP", icon: DoorOpen },
  { href: "/processing/production-orders", label: "Production Orders", icon: Factory },
  { href: "/processing/stages", label: "PPC Stages", icon: Activity },
  { href: "/processing/dispatch", label: "Fresh Dispatch", icon: Truck },
  { href: "/processing/labor-bills", label: "Labor Bills", icon: Receipt },
  { href: "/processing/settlements", label: "Grey Settlement", icon: Scale },
  { href: "/processing/inspections", label: "Inspections", icon: ClipboardCheck },
  { href: "/processing/reports/rejection", label: "Rejection Register", icon: AlertTriangle },
  { href: "/processing/reports/stock-ledger", label: "Customer Stock", icon: BookOpen },
  { href: "/processing/reports/ppc", label: "PPC Reports", icon: PieChart },
]

export default function ProcessingHubPage() {
  const [dash, setDash] = useState<Dash | null>(null)

  useEffect(() => {
    apiFetch<Dash>("/api/textile-processing/dashboard").then(setDash).catch(() => setDash(null))
  }, [])

  const k = dash?.kpis
  const n = (v: number | undefined) => (v == null ? null : String(v))

  return (
    <div className="p-4 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-xl font-semibold text-[var(--text-primary)] flex items-center gap-2">
          <Layers className="w-5 h-5 text-[var(--primary)]" /> Textile Processing
        </h1>
        <p className="text-sm text-[var(--text-muted)]">
          Customer-owned grey lots through mending, PPC, fresh dispatch, and grey settlement
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard title="Lots" value={n(k?.lots_total)} tone="blue" href="/processing/lots" />
        <KpiCard title="In process" value={n(k?.lots_in_process)} tone="amber" />
        <KpiCard title="Ready (Safi)" value={k ? `${k.ready_mtr.toFixed(1)} MTR` : null} tone="green" />
        <KpiCard title="Received" value={k ? `${k.received_mtr.toFixed(1)} MTR` : null} />
        <KpiCard title="Rejection pending" value={k ? `${k.rejection_pending_mtr.toFixed(1)} MTR` : null} tone="red" href="/processing/rejection" />
        <KpiCard title="Visible wastage" value={k ? `${k.visible_wastage_mtr.toFixed(1)} MTR` : null} />
        <KpiCard title="Invisible wastage" value={k ? `${k.invisible_wastage_mtr.toFixed(1)} MTR` : null} />
        <KpiCard title="Lots ready" value={n(k?.lots_ready)} href="/processing/lots" />
      </div>

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
