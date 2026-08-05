"use client"

import React from "react"
import Link from "next/link"
import {
  Activity, AlertTriangle, BedDouble, Factory, FlaskConical, Package,
  Radio, ShoppingCart, Truck, Wallet, Gauge, Layers,
} from "lucide-react"
import KpiCard from "@/components/dashboard/KpiCard"
import type { OperationsSummary } from "@/lib/operationsSummary"
import type { WidgetContext } from "@/lib/dashboardWidgets"

function fmtNum(n: number | string | null | undefined, digits = 0): string {
  if (n == null || n === "") return "—"
  const v = typeof n === "string" ? Number(n) : n
  if (Number.isNaN(v)) return "—"
  return v.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function Panel({
  title, href, hrefLabel, children, empty,
}: {
  title: string
  href: string
  hrefLabel?: string
  children: React.ReactNode
  empty?: boolean
}) {
  if (empty) return null
  return (
    <div className="h-full flex flex-col bg-white border border-[var(--border)] rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/55">{title}</p>
        <Link href={href} className="text-[10px] text-[var(--primary)] hover:underline">{hrefLabel ?? "Open →"}</Link>
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  )
}

function Figure({ label, value, tone }: { label: string; value: string; tone?: "warning" | "danger" }) {
  const color = tone === "danger" ? "text-red-600" : tone === "warning" ? "text-amber-600" : "text-[var(--text-primary)]"
  return (
    <div className="text-center min-w-0">
      <p className={`text-lg font-bold leading-none truncate ${color}`}>{value}</p>
      <p className="text-[10px] text-[var(--text-primary)]/55 mt-1 uppercase tracking-wide leading-tight">{label}</p>
    </div>
  )
}

function Loading() {
  return <div className="shimmer h-16 rounded-lg" />
}

export function OpsPrimaryKpis({ ctx }: { ctx: WidgetContext }) {
  const ops = ctx.opsSummary
  if (!ops) return <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3"><Loading /><Loading /><Loading /></div>

  const cards: React.ReactNode[] = []

  if (ops.spinning) {
    const k = ops.spinning.kpis
    cards.push(
      <KpiCard key="open_lots" title="Open Lots" value={String(k.open_lots)} icon={Layers} tone="amber" href="/spinning/lots" />,
      <KpiCard key="yield" title="Yield %" value={`${fmtNum(k.overall_yield_pct, 1)}%`} icon={Gauge} tone="green" href="/spinning/dashboard" />,
      <KpiCard key="cone" title="Cone Output (kg)" value={fmtNum(k.cone_output?.kg, 1)} icon={Package} tone="blue" href="/spinning/cone-output" />,
      <KpiCard key="disp" title="Dispatched (kg)" value={fmtNum(k.dispatched?.kg, 1)} icon={Truck} tone="emerald" href="/spinning/dispatch" />,
    )
  }
  if (ops.production) {
    const p = ops.production.pipeline
    cards.push(
      <KpiCard key="wip" title="In Production" value={String(p.started ?? 0)} icon={Factory} tone="amber" href="/manufacturing" />,
      <KpiCard key="done" title="Completed" value={String(p.completed ?? 0)} icon={Factory} tone="green" href="/manufacturing/production-orders" />,
      <KpiCard key="wip_cost" title="WIP Cost" value={ctx.fmt(Number(ops.production.totals.wip_cost || 0))} icon={Wallet} tone="blue" href="/manufacturing" />,
    )
  }
  if (ops.weaving) {
    const k = ops.weaving.kpis
    cards.push(
      <KpiCard key="grey" title="Grey Meters" value={fmtNum(k.grey_meters, 0)} icon={Factory} tone="blue" href="/weaving/dashboard" />,
      <KpiCard key="eff" title="Avg Efficiency" value={`${fmtNum(k.avg_efficiency_pct, 1)}%`} icon={Gauge} tone="green" href="/weaving/dashboard" />,
      <KpiCard key="yarn_bal" title="Yarn Balance (kg)" value={fmtNum(k.yarn_balance?.kg, 1)} icon={Package} tone="amber" href="/weaving" />,
    )
  }
  if (ops.textile_processing) {
    const k = ops.textile_processing.kpis
    cards.push(
      <KpiCard key="tp_proc" title="Lots In Process" value={String(k.lots_in_process)} icon={Layers} tone="amber" href="/processing" />,
      <KpiCard key="tp_ready" title="Lots Ready" value={String(k.lots_ready)} icon={Package} tone="green" href="/processing/lots" />,
      <KpiCard key="tp_rej" title="Rejection Pending (m)" value={fmtNum(k.rejection_pending_mtr, 0)} icon={AlertTriangle} tone="red" href="/processing" />,
    )
  }
  if (ops.healthcare) {
    const h = ops.healthcare
    cards.push(
      <KpiCard key="opd" title="OPD Visits Today" value={String(h.visits_today)} icon={Activity} tone="green" href="/healthcare/opd" />,
      <KpiCard key="ipd" title="Admitted" value={String(h.currently_admitted)} icon={BedDouble} tone="blue" href="/healthcare/ipd" />,
      <KpiCard key="beds" title="Bed Occupancy" value={`${fmtNum(h.bed_occupancy_pct, 1)}%`} icon={BedDouble} tone="amber" href="/healthcare" />,
      <KpiCard key="labs" title="Pending Labs" value={String(h.pending_lab_results)} icon={FlaskConical} tone="red" href="/healthcare/lab" />,
    )
  }
  if (ops.telecom) {
    const t = ops.telecom
    cards.push(
      <KpiCard key="float" title="Load Float" value={ctx.fmt(Number(t.tracker.load_float || 0))} icon={Wallet} tone="emerald" href="/telecom/tracker" />,
      <KpiCard key="rso" title="RSO Agents" value={String(t.rso.agent_count)} icon={Radio} tone="blue" href="/telecom/rso" />,
      <KpiCard key="sim" title="SIMs Available" value={String(t.sim.available)} icon={Package} tone="amber" href="/telecom/sim" />,
      <KpiCard key="fca" title="FCA This Month" value={String(t.fca.actual)} icon={Gauge} tone="green" href="/telecom/fca" />,
    )
  }
  if (ops.purchase_store && cards.length < 3) {
    const p = ops.purchase_store
    cards.push(
      <KpiCard key="demands" title="Open Demands" value={String(p.open_demands)} icon={ShoppingCart} tone="amber" href="/purchases/demands" />,
      <KpiCard key="pos" title="Open POs" value={String(p.open_pos)} icon={Truck} tone="blue" href="/purchases" />,
      <KpiCard key="gi" title="Open Gate In" value={String(p.open_gate_inwards)} icon={Package} tone="green" href="/purchases/gate-inward" />,
    )
  }

  if (cards.length === 0) {
    return (
      <div className="bg-white border border-[var(--border)] rounded-xl p-6 text-sm text-[var(--text-primary)]/55">
        No operations modules installed. Install an industry pack from Apps to populate this view.
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {cards.slice(0, 5)}
    </div>
  )
}

export function OpsAlerts({ ctx }: { ctx: WidgetContext }) {
  const ops = ctx.opsSummary
  if (!ops) return null
  const items: { href: string; label: string }[] = []
  if (ops.purchase_store && ops.purchase_store.low_stock_items > 0) {
    items.push({ href: "/products?low_stock=true", label: `${ops.purchase_store.low_stock_items} low-stock product${ops.purchase_store.low_stock_items > 1 ? "s" : ""}` })
  }
  if (ops.healthcare && ops.healthcare.pending_lab_results > 0) {
    items.push({ href: "/healthcare/lab", label: `${ops.healthcare.pending_lab_results} pending lab result${ops.healthcare.pending_lab_results > 1 ? "s" : ""}` })
  }
  if (ops.spinning && ops.spinning.kpis.open_lots > 0) {
    items.push({ href: "/spinning/lots", label: `${ops.spinning.kpis.open_lots} open spin lot${ops.spinning.kpis.open_lots > 1 ? "s" : ""}` })
  }
  if (ops.textile_processing && ops.textile_processing.kpis.rejection_pending_mtr > 0) {
    items.push({ href: "/processing", label: `${fmtNum(ops.textile_processing.kpis.rejection_pending_mtr, 0)} m rejection pending` })
  }
  if (ops.hrm && ops.hrm.pending_runs > 0) {
    items.push({ href: "/payroll", label: `${ops.hrm.pending_runs} pending payroll run${ops.hrm.pending_runs > 1 ? "s" : ""}` })
  }
  if (ops.production && (ops.production.pipeline.started ?? 0) > 0) {
    items.push({ href: "/manufacturing", label: `${ops.production.pipeline.started} production order${ops.production.pipeline.started > 1 ? "s" : ""} in progress` })
  }
  if (items.length === 0) return null
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex flex-wrap gap-3 items-center">
      <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
      <span className="text-sm font-medium text-amber-800">Action required:</span>
      {items.map((it, i) => (
        <span key={it.href} className="inline-flex items-center gap-2">
          {i > 0 && <span className="text-amber-400">·</span>}
          <Link href={it.href} className="text-sm text-amber-700 underline underline-offset-2 hover:text-amber-900">{it.label}</Link>
        </span>
      ))}
    </div>
  )
}

export function SpinningSummaryWidget({ ctx }: { ctx: WidgetContext }) {
  const s = ctx.opsSummary?.spinning
  if (ctx.opsSummary && !s) return null
  return (
    <Panel title="Spinning" href="/spinning/dashboard" empty={!!ctx.opsSummary && !s}>
      {!s ? <Loading /> : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-4 items-center">
          <Figure label="Open Lots" value={String(s.kpis.open_lots)} tone={s.kpis.open_lots > 0 ? "warning" : undefined} />
          <Figure label="Yield %" value={`${fmtNum(s.kpis.overall_yield_pct, 1)}%`} />
          <Figure label="Bale In (kg)" value={fmtNum(s.kpis.bale_received?.kg, 1)} />
          <Figure label="Cone Out (kg)" value={fmtNum(s.kpis.cone_output?.kg, 1)} />
        </div>
      )}
    </Panel>
  )
}

export function WeavingSummaryWidget({ ctx }: { ctx: WidgetContext }) {
  const s = ctx.opsSummary?.weaving
  if (ctx.opsSummary && !s) return null
  return (
    <Panel title="Weaving" href="/weaving/dashboard" empty={!!ctx.opsSummary && !s}>
      {!s ? <Loading /> : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-4 items-center">
          <Figure label="Grey Meters" value={fmtNum(s.kpis.grey_meters, 0)} />
          <Figure label="Efficiency" value={`${fmtNum(s.kpis.avg_efficiency_pct, 1)}%`} />
          <Figure label="Yarn Bal (kg)" value={fmtNum(s.kpis.yarn_balance?.kg, 1)} />
          <Figure label="Dispatch (m)" value={fmtNum(s.kpis.dispatch_meters, 0)} />
        </div>
      )}
    </Panel>
  )
}

export function ProductionWipWidget({ ctx }: { ctx: WidgetContext }) {
  const s = ctx.opsSummary?.production
  if (ctx.opsSummary && !s) return null
  return (
    <Panel title="Production WIP" href="/manufacturing" empty={!!ctx.opsSummary && !s}>
      {!s ? <Loading /> : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-4 items-center">
          <Figure label="Started" value={String(s.pipeline.started ?? 0)} tone={(s.pipeline.started ?? 0) > 0 ? "warning" : undefined} />
          <Figure label="Completed" value={String(s.pipeline.completed ?? 0)} />
          <Figure label="WIP Cost" value={ctx.fmt(Number(s.totals.wip_cost || 0))} />
          <Figure label="FG Cost" value={ctx.fmt(Number(s.totals.finished_goods_cost || 0))} />
        </div>
      )}
    </Panel>
  )
}

export function HealthcareCensusWidget({ ctx }: { ctx: WidgetContext }) {
  const s = ctx.opsSummary?.healthcare
  if (ctx.opsSummary && !s) return null
  return (
    <Panel title="Healthcare Census" href="/healthcare" empty={!!ctx.opsSummary && !s}>
      {!s ? <Loading /> : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-4 items-center">
          <Figure label="Visits Today" value={String(s.visits_today)} />
          <Figure label="Admitted" value={String(s.currently_admitted)} />
          <Figure label="Bed Occ." value={`${fmtNum(s.bed_occupancy_pct, 1)}%`} tone={s.bed_occupancy_pct > 90 ? "danger" : undefined} />
          <Figure label="Pending Labs" value={String(s.pending_lab_results)} tone={s.pending_lab_results > 0 ? "warning" : undefined} />
        </div>
      )}
    </Panel>
  )
}

export function TelecomTrackerWidget({ ctx }: { ctx: WidgetContext }) {
  const s = ctx.opsSummary?.telecom
  if (ctx.opsSummary && !s) return null
  return (
    <Panel title="Telecom Tracker" href="/telecom" empty={!!ctx.opsSummary && !s}>
      {!s ? <Loading /> : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-4 items-center">
          <Figure label="Load Float" value={ctx.fmt(Number(s.tracker.load_float || 0))} />
          <Figure label="Deposit" value={ctx.fmt(Number(s.tracker.deposit_balance || 0))} />
          <Figure label="RSO Agents" value={String(s.rso.agent_count)} />
          <Figure label="FCA MTD" value={String(s.fca.actual)} />
        </div>
      )}
    </Panel>
  )
}

export function PurchasesPipelineWidget({ ctx }: { ctx: WidgetContext }) {
  const s = ctx.opsSummary?.purchase_store
  if (ctx.opsSummary && !s) return null
  return (
    <Panel title="Purchases Pipeline" href="/purchases" empty={!!ctx.opsSummary && !s}>
      {!s ? <Loading /> : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-4 items-center">
          <Figure label="Open Demands" value={String(s.open_demands)} tone={s.open_demands > 0 ? "warning" : undefined} />
          <Figure label="Open POs" value={String(s.open_pos)} />
          <Figure label="Gate Inward" value={String(s.open_gate_inwards)} />
          <Figure label="Low Stock" value={String(s.low_stock_items)} tone={s.low_stock_items > 0 ? "danger" : undefined} />
        </div>
      )}
    </Panel>
  )
}

export function TextileProcessingWidget({ ctx }: { ctx: WidgetContext }) {
  const s = ctx.opsSummary?.textile_processing
  if (ctx.opsSummary && !s) return null
  return (
    <Panel title="Textile Processing" href="/processing" empty={!!ctx.opsSummary && !s}>
      {!s ? <Loading /> : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-4 items-center">
          <Figure label="In Process" value={String(s.kpis.lots_in_process)} tone={s.kpis.lots_in_process > 0 ? "warning" : undefined} />
          <Figure label="Ready" value={String(s.kpis.lots_ready)} />
          <Figure label="Ready (m)" value={fmtNum(s.kpis.ready_mtr, 0)} />
          <Figure label="Rejection (m)" value={fmtNum(s.kpis.rejection_pending_mtr, 0)} tone={s.kpis.rejection_pending_mtr > 0 ? "danger" : undefined} />
        </div>
      )}
    </Panel>
  )
}

export function OpsPipelineWidget({ ctx }: { ctx: WidgetContext }) {
  const ops = ctx.opsSummary
  if (!ops) return <Panel title="Pipeline" href="/dashboard"><Loading /></Panel>

  if (ops.spinning) {
    const stages = Object.entries(ops.spinning.wip_by_stage || {})
    return (
      <Panel title="Spinning WIP by Stage" href="/spinning/dashboard">
        {stages.length === 0 ? (
          <p className="text-sm text-[var(--text-primary)]/45">No stage WIP</p>
        ) : (
          <div className="space-y-2">
            {stages.map(([stage, kg]) => (
              <div key={stage} className="flex items-center justify-between text-sm">
                <span className="capitalize text-[var(--text-primary)]/70">{stage.replace(/_/g, " ")}</span>
                <span className="font-semibold tabular-nums">{fmtNum(kg, 1)} kg</span>
              </div>
            ))}
          </div>
        )}
      </Panel>
    )
  }

  if (ops.production) {
    const p = ops.production.pipeline
    const rows = [
      ["Draft", p.draft], ["Started", p.started], ["Completed", p.completed],
      ["Delivered", p.delivered], ["Billed", p.billed],
    ] as const
    return (
      <Panel title="Production Pipeline" href="/manufacturing">
        <div className="space-y-2">
          {rows.map(([label, n]) => (
            <div key={label} className="flex items-center justify-between text-sm">
              <span className="text-[var(--text-primary)]/70">{label}</span>
              <span className="font-semibold tabular-nums">{n ?? 0}</span>
            </div>
          ))}
        </div>
      </Panel>
    )
  }

  if (ops.healthcare) {
    return (
      <Panel title="Today's Activity" href="/healthcare">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-[var(--text-primary)]/70">Tokens</span><span className="font-semibold">{ops.healthcare.tokens_today}</span></div>
          <div className="flex justify-between"><span className="text-[var(--text-primary)]/70">Visits</span><span className="font-semibold">{ops.healthcare.visits_today}</span></div>
          <div className="flex justify-between"><span className="text-[var(--text-primary)]/70">Beds occupied</span><span className="font-semibold">{ops.healthcare.occupied_beds}/{ops.healthcare.total_beds}</span></div>
        </div>
      </Panel>
    )
  }

  if (ops.purchase_store) {
    return (
      <Panel title="Purchase Flow" href="/purchases">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-[var(--text-primary)]/70">Demands</span><span className="font-semibold">{ops.purchase_store.open_demands}</span></div>
          <div className="flex justify-between"><span className="text-[var(--text-primary)]/70">Purchase Orders</span><span className="font-semibold">{ops.purchase_store.open_pos}</span></div>
          <div className="flex justify-between"><span className="text-[var(--text-primary)]/70">Gate Inwards</span><span className="font-semibold">{ops.purchase_store.open_gate_inwards}</span></div>
        </div>
      </Panel>
    )
  }

  return (
    <Panel title="Pipeline" href="/apps">
      <p className="text-sm text-[var(--text-primary)]/45">Install a production or industry module to see the pipeline.</p>
    </Panel>
  )
}

// Keep type import used for consumers
export type { OperationsSummary }
