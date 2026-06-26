"use client"
import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { Stethoscope, BedDouble, FlaskConical, Activity, AlertCircle } from "lucide-react"
import { HcCard, StatusBadge } from "@/components/healthcare/primitives"
import Link from "next/link"

type Dashboard = {
  date: string
  tokens_today: number
  visits_today: number
  currently_admitted: number
  total_beds: number
  occupied_beds: number
  bed_occupancy_pct: number
  pending_lab_results: number
}

type PendingLab = {
  id: number
  order_number: string
  order_date: string
  status: string
}

export default function HealthcarePage() {
  const [dash, setDash] = useState<Dashboard | null>(null)
  const [pendingLabs, setPendingLabs] = useState<PendingLab[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const [d, labs] = await Promise.all([
        apiFetch<Dashboard>("/api/healthcare/reports/dashboard").catch(() => null),
        apiFetch<PendingLab[]>("/api/healthcare/lab/orders?status=ordered&limit=10").catch(() => [] as PendingLab[]),
      ])
      if (d) setDash(d)
      setPendingLabs(Array.isArray(labs) ? labs : (labs as { items?: PendingLab[] })?.items ?? [])
      setLoading(false)
    }
    load()
  }, [])

  const kpis = dash ? [
    {
      label: "OPD Tokens Today",
      value: dash.tokens_today,
      sub: `${dash.visits_today} visits`,
      icon: Activity,
      color: "text-blue-500",
    },
    {
      label: "Admitted Patients",
      value: dash.currently_admitted,
      sub: `${dash.occupied_beds}/${dash.total_beds} beds`,
      icon: BedDouble,
      color: "text-rose-500",
    },
    {
      label: "Bed Occupancy",
      value: `${dash.bed_occupancy_pct}%`,
      sub: `${dash.total_beds} total beds`,
      icon: Stethoscope,
      color: "text-amber-500",
    },
    {
      label: "Pending Lab Results",
      value: dash.pending_lab_results,
      sub: "in queue",
      icon: FlaskConical,
      color: "text-purple-500",
    },
  ] : []

  if (loading) {
    return <div className="p-6 text-sm text-neutral-500">Loading healthcare dashboard…</div>
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">Healthcare</h1>
        <p className="text-sm text-neutral-500 mt-0.5">Hospital operations overview</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpis.map(k => {
          const Icon = k.icon
          return (
            <div key={k.label} className="bg-white rounded-xl border border-neutral-200 p-4">
              <div className="flex items-center gap-2 text-neutral-500 text-xs mb-2">
                <Icon className={`w-4 h-4 ${k.color}`} />
                {k.label}
              </div>
              <div className="text-2xl font-bold text-neutral-900">{k.value}</div>
              <div className="text-xs text-neutral-400 mt-0.5">{k.sub}</div>
            </div>
          )
        })}
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { href: "/healthcare/opd", label: "OPD Queue", icon: Activity },
          { href: "/healthcare/ipd", label: "Ward View", icon: BedDouble },
          { href: "/healthcare/lab", label: "Lab Orders", icon: FlaskConical },
          { href: "/healthcare/patients", label: "Patient Registry", icon: Stethoscope },
        ].map(l => {
          const Icon = l.icon
          return (
            <Link
              key={l.href}
              href={l.href}
              className="flex items-center gap-2 bg-white border border-neutral-200 rounded-xl p-4 hover:border-rose-300 hover:bg-rose-50/30 transition-colors text-sm font-medium"
            >
              <Icon className="w-4 h-4 text-rose-400" />
              {l.label}
            </Link>
          )
        })}
      </div>

      {/* Pending lab orders */}
      {pendingLabs.length > 0 && (
        <HcCard title="Pending Lab Results">
          <div className="space-y-2">
            {pendingLabs.map(order => (
              <div key={order.id} className="flex items-center justify-between py-1.5 border-b border-neutral-50 last:border-0">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                  <Link
                    href={`/healthcare/lab?order=${order.id}`}
                    className="text-sm font-medium text-neutral-800 hover:text-rose-600"
                  >
                    {order.order_number}
                  </Link>
                  <span className="text-xs text-neutral-400">{order.order_date}</span>
                </div>
                <StatusBadge status={order.status} />
              </div>
            ))}
          </div>
        </HcCard>
      )}
    </div>
  )
}
