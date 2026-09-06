"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import KpiCard from "@/components/dashboard/KpiCard"
import StatusBadge from "@/components/StatusBadge"
import { formatWeightTriple, type WeightTriple } from "@/lib/weavingUnits"
import { fmtDate } from "@/lib/utils"
import { ClipboardList, PlusCircle, Scale, Truck } from "lucide-react"

type Ticket = {
  id: number
  number: string
  ticket_date: string
  vehicle_no: string
  party_name?: string | null
  status: string
  net?: WeightTriple
}

type Hub = {
  today_count: number
  on_site: number
  net_kg_today: number
  net_today: WeightTriple
  recent: Ticket[]
}

const LINKS = [
  { href: "/weighbridge/tickets/new", label: "New ticket", icon: PlusCircle },
  { href: "/weighbridge/tickets", label: "Tickets", icon: ClipboardList },
  { href: "/weighbridge/reports/register", label: "Register", icon: Truck },
]

export default function WeighbridgeHubPage() {
  const [hub, setHub] = useState<Hub | null>(null)

  useEffect(() => {
    apiFetch<Hub>("/api/weighbridge/summary").then(setHub).catch(() => setHub(null))
  }, [])

  return (
    <div className="p-4 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Weighbridge</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Vehicle tickets — first and second weigh, net Kg / Lbs / Bags. Memo/ops, no GL in v1.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <KpiCard title="Tickets today" value={hub ? String(hub.today_count) : null} tone="blue" href="/weighbridge/tickets" />
        <KpiCard title="Vehicles on site" value={hub ? String(hub.on_site) : null} tone="amber" />
        <KpiCard title="Net kg today" value={hub ? formatWeightTriple(hub.net_today) : null} tone="green" />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
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

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] overflow-hidden">
        <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Recent tickets</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Ticket</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Vehicle</th>
              <th className="px-3 py-2">Party</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(hub?.recent ?? []).map(t => (
              <tr key={t.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/weighbridge/tickets/${t.id}`} className="text-[var(--primary)]">{t.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(t.ticket_date)}</td>
                <td className="px-3 py-2">{t.vehicle_no}</td>
                <td className="px-3 py-2">{t.party_name || "—"}</td>
                <td className="px-3 py-2"><StatusBadge status={t.status} /></td>
              </tr>
            ))}
            {hub && hub.recent.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--text-muted)]">
                No tickets yet. <Link href="/weighbridge/tickets/new" className="text-[var(--primary)]">Create one</Link>.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-[var(--text-muted)] flex items-center gap-1">
        <Scale className="w-3.5 h-3.5" /> Invoice Gate pass overlay still lives on Add-ons → Marketplace.
      </p>
    </div>
  )
}
