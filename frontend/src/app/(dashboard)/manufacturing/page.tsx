"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Factory, Package, Warehouse, Layers, Wrench, ShoppingCart, BarChart2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface Dashboard {
  pipeline: {
    draft: number; started: number; completed: number;
    delivered: number; billed: number; cancelled: number
  }
  totals: { wip_cost: string; finished_goods_cost: string; custodial_qty: string }
}

const STAGES: { key: keyof Dashboard["pipeline"]; label: string; tone: string }[] = [
  { key: "draft",     label: "Draft",     tone: "bg-slate-100 text-slate-800 border-slate-200"  },
  { key: "started",   label: "In WIP",    tone: "bg-amber-50 text-amber-900 border-amber-200"   },
  { key: "completed", label: "Completed", tone: "bg-blue-50 text-blue-900 border-blue-200"      },
  { key: "delivered", label: "Delivered", tone: "bg-emerald-50 text-emerald-900 border-emerald-200" },
  { key: "billed",    label: "Billed",    tone: "bg-violet-50 text-violet-900 border-violet-200" },
]

export default function ManufacturingDashboardPage() {
  const [data, setData]   = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Dashboard>("/api/manufacturing/dashboard")
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [])

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <Factory className="w-7 h-7 text-[#b8943f]" />
        <div>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Production Floor</h1>
          <p className="text-sm text-[#1a1814]/60">Live view of your manufacturing operations.</p>
        </div>
      </header>

      <HelpCallout title="How a production order flows" tone="tip">
        <ol className="list-decimal pl-4 space-y-1">
          <li><b>Receive customer goods</b> (Goods Receipt) — record fabric/material a customer brings in.</li>
          <li><b>Define a recipe</b> (Bill of Material) — what raw materials produce each unit of output.</li>
          <li><b>Assign a Rate Plan</b> — your per-unit value-addition charge for that customer.</li>
          <li><b>Create a Production Order</b> — then walk it through <i>start → complete → deliver → bill</i>.</li>
        </ol>
        <p className="mt-2 text-[11px] opacity-80">
          Each transition posts the right journal entries automatically. Customer-supplied
          material stays off your balance sheet (memo accounts only).
        </p>
      </HelpCallout>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Pipeline counts */}
      <section>
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50 mb-2">Pipeline</h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {STAGES.map(s => (
            <div key={s.key} className={`${s.tone} border rounded-xl px-3 py-3`}>
              <div className="text-xs font-semibold opacity-70">{s.label}</div>
              <div className="text-2xl font-serif font-bold mt-0.5">
                {data?.pipeline[s.key] ?? "—"}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Totals */}
      <section>
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50 mb-2">Inventory at a glance</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Tile icon={Wrench} label="WIP cost" value={fmt(data?.totals.wip_cost)} />
          <Tile icon={Layers} label="Finished goods cost" value={fmt(data?.totals.finished_goods_cost)} />
          <Tile icon={Warehouse} label="Customer goods on hand (qty)" value={data?.totals.custodial_qty ?? "—"} />
        </div>
      </section>

      {/* Quick links */}
      <section>
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50 mb-2">Jump to</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <QuickLink href="/manufacturing/purchase-orders"    icon={ShoppingCart} title="Purchase Orders"  subtitle="Order goods from vendors" />
          <QuickLink href="/manufacturing/grn"               icon={Package}    title="Goods Receipt"     subtitle="Record what a customer brings in" />
          <QuickLink href="/manufacturing/boms"              icon={Layers}     title="Bills of Material" subtitle="Define recipes for outputs" />
          <QuickLink href="/manufacturing/rate-plans"        icon={Wrench}     title="Rate Plans"        subtitle="Set your value-add pricing" />
          <QuickLink href="/manufacturing/production-orders" icon={Warehouse}  title="Production Orders" subtitle="Run the floor" />
          <QuickLink href="/manufacturing/reports"          icon={BarChart2}  title="Mfg Reports"       subtitle="WIP aging, summary, custody" />
        </div>
      </section>
    </div>
  )
}

function fmt(v?: string): string {
  if (!v) return "—"
  const n = Number(v)
  if (Number.isNaN(n)) return v
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function Tile({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="bg-white border border-[#ede9e2] rounded-xl px-4 py-3 flex items-center gap-3">
      <div className="w-10 h-10 rounded-lg bg-[#faf6ec] border border-[#b8943f]/30 flex items-center justify-center">
        <Icon className="w-5 h-5 text-[#b8943f]" />
      </div>
      <div className="min-w-0">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-[#1a1814]/55">{label}</div>
        <div className="text-lg font-serif font-bold text-[#1a1814] truncate">{value}</div>
      </div>
    </div>
  )
}

function QuickLink({
  href, icon: Icon, title, subtitle,
}: { href: string; icon: React.ElementType; title: string; subtitle: string }) {
  return (
    <Link
      href={href}
      className="bg-white border border-[#ede9e2] rounded-xl px-4 py-3 hover:border-[#b8943f]/60 transition-colors block"
    >
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-[#b8943f]" />
        <div className="text-sm font-semibold text-[#1a1814]">{title}</div>
      </div>
      <p className="text-xs text-[#1a1814]/60 mt-1.5">{subtitle}</p>
    </Link>
  )
}
