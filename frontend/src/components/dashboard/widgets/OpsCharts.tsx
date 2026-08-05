"use client"

import React from "react"
import Link from "next/link"
import { Bar, Doughnut, Line } from "react-chartjs-2"
import type { ChartOptions } from "chart.js"
import type { WidgetContext } from "@/lib/dashboardWidgets"

const PALETTE = [
  "rgba(184,148,63,0.85)",
  "rgba(37,99,235,0.80)",
  "rgba(22,163,74,0.80)",
  "rgba(234,179,8,0.80)",
  "rgba(249,115,22,0.80)",
  "rgba(220,38,38,0.80)",
  "rgba(124,58,237,0.80)",
  "rgba(8,145,178,0.80)",
]

function Panel({
  title, href, children,
}: { title: string; href: string; children: React.ReactNode }) {
  return (
    <div className="h-full flex flex-col bg-white border border-[var(--border)] rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/55">{title}</p>
        <Link href={href} className="text-[10px] text-[var(--primary)] hover:underline">Open →</Link>
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  )
}

function Loading() {
  return <div className="shimmer h-full min-h-[120px] rounded-lg" />
}

function Empty({ msg }: { msg: string }) {
  return <div className="h-full flex items-center justify-center text-sm text-[var(--text-primary)]/40">{msg}</div>
}

const barOpts = (fmt?: (n: number) => string): ChartOptions<"bar"> => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: ctx => {
          const v = ctx.parsed.y ?? ctx.parsed.x ?? 0
          return fmt ? ` ${fmt(Number(v))}` : ` ${v}`
        },
      },
    },
  },
  scales: {
    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
    y: {
      grid: { color: "rgba(0,0,0,0.05)" },
      ticks: {
        font: { size: 10 },
        callback: v => (fmt ? fmt(Number(v)) : String(v)),
      },
      beginAtZero: true,
    },
  },
})

const hBarOpts = (fmt?: (n: number) => string): ChartOptions<"bar"> => ({
  ...barOpts(fmt),
  indexAxis: "y",
  scales: {
    x: {
      grid: { color: "rgba(0,0,0,0.05)" },
      ticks: { font: { size: 10 }, callback: v => (fmt ? fmt(Number(v)) : String(v)) },
      beginAtZero: true,
    },
    y: { grid: { display: false }, ticks: { font: { size: 10 } } },
  },
})

const doughnutOpts: ChartOptions<"doughnut"> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 10, padding: 6 } },
  },
  cutout: "58%",
}

const lineOpts: ChartOptions<"line"> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: "bottom", labels: { font: { size: 10 }, boxWidth: 10 } } },
  scales: {
    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
    y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 } }, beginAtZero: true },
  },
}

function prettyStatus(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

/** Process funnel / WIP stage bar — primary process-visibility chart. */
export function OpsProcessChart({ ctx }: { ctx: WidgetContext }) {
  const ops = ctx.opsSummary
  if (!ops) return <Panel title="Process Visibility" href="/dashboard"><Loading /></Panel>

  // Spinning WIP by stage
  if (ops.spinning?.wip_by_stage && Object.keys(ops.spinning.wip_by_stage).length > 0) {
    const entries = Object.entries(ops.spinning.wip_by_stage)
    return (
      <Panel title="Spinning WIP by Stage (kg)" href="/spinning/dashboard">
        <Bar
          data={{
            labels: entries.map(([s]) => prettyStatus(s)),
            datasets: [{
              data: entries.map(([, v]) => v),
              backgroundColor: PALETTE,
              borderRadius: 4,
            }],
          }}
          options={hBarOpts(n => n.toLocaleString(undefined, { maximumFractionDigits: 1 }))}
        />
      </Panel>
    )
  }

  // Production pipeline funnel
  if (ops.production?.pipeline) {
    const order = ["draft", "started", "completed", "delivered", "billed"] as const
    const labels = ["Draft", "Started", "Completed", "Delivered", "Billed"]
    const data = order.map(k => ops.production!.pipeline[k] ?? 0)
    return (
      <Panel title="Production Pipeline" href="/manufacturing">
        <Bar
          data={{
            labels,
            datasets: [{ data, backgroundColor: PALETTE.slice(0, 5), borderRadius: 4 }],
          }}
          options={barOpts()}
        />
      </Panel>
    )
  }

  // Purchase funnel
  if (ops.purchase_store?.funnel) {
    const f = ops.purchase_store.funnel
    return (
      <Panel title="Purchase Process Funnel" href="/purchases">
        <Bar
          data={{
            labels: ["Demands", "Open Demands", "POs", "Open POs", "Gate In", "Billed POs"],
            datasets: [{
              data: [f.demands, f.demands_open, f.pos, f.pos_open, f.gate_inwards, f.pos_billed],
              backgroundColor: PALETTE.slice(0, 6),
              borderRadius: 4,
            }],
          }}
          options={barOpts()}
        />
      </Panel>
    )
  }

  // Healthcare bed occupancy doughnut
  if (ops.healthcare) {
    const h = ops.healthcare
    const free = Math.max((h.total_beds || 0) - (h.occupied_beds || 0), 0)
    return (
      <Panel title="Bed Occupancy" href="/healthcare/ipd">
        {h.total_beds > 0 ? (
          <Doughnut
            data={{
              labels: ["Occupied", "Available"],
              datasets: [{
                data: [h.occupied_beds, free],
                backgroundColor: ["rgba(249,115,22,0.85)", "rgba(22,163,74,0.75)"],
                borderWidth: 2,
                borderColor: "#fff",
              }],
            }}
            options={doughnutOpts}
          />
        ) : <Empty msg="No beds configured" />}
      </Panel>
    )
  }

  // Telecom SIM utilisation
  if (ops.telecom) {
    const s = ops.telecom.sim
    return (
      <Panel title="SIM Utilisation" href="/telecom/sim">
        <Doughnut
          data={{
            labels: ["Activated", "Available"],
            datasets: [{
              data: [s.total_activated, s.available],
              backgroundColor: ["rgba(37,99,235,0.85)", "rgba(184,148,63,0.80)"],
              borderWidth: 2,
              borderColor: "#fff",
            }],
          }}
          options={doughnutOpts}
        />
      </Panel>
    )
  }

  // Textile processing mix
  if (ops.textile_processing) {
    const k = ops.textile_processing.kpis
    const other = Math.max(k.lots_total - k.lots_in_process - k.lots_ready, 0)
    return (
      <Panel title="Lot Status Mix" href="/processing">
        <Doughnut
          data={{
            labels: ["In Process", "Ready", "Other"],
            datasets: [{
              data: [k.lots_in_process, k.lots_ready, other],
              backgroundColor: PALETTE.slice(0, 3),
              borderWidth: 2,
              borderColor: "#fff",
            }],
          }}
          options={doughnutOpts}
        />
      </Panel>
    )
  }

  // Weaving yarn balance doughnut
  if (ops.weaving) {
    const k = ops.weaving.kpis
    return (
      <Panel title="Yarn Mass Balance (kg)" href="/weaving/dashboard">
        <Doughnut
          data={{
            labels: ["Received", "Used", "Balance"],
            datasets: [{
              data: [k.yarn_received?.kg ?? 0, k.yarn_used?.kg ?? 0, k.yarn_balance?.kg ?? 0],
              backgroundColor: PALETTE.slice(0, 3),
              borderWidth: 2,
              borderColor: "#fff",
            }],
          }}
          options={doughnutOpts}
        />
      </Panel>
    )
  }

  return (
    <Panel title="Process Visibility" href="/apps">
      <Empty msg="Install an industry pack to see process charts" />
    </Panel>
  )
}

/** Trend / time-series chart for ops throughput. */
export function OpsTrendChart({ ctx }: { ctx: WidgetContext }) {
  const ops = ctx.opsSummary
  if (!ops) return <Panel title="Operations Trend" href="/dashboard"><Loading /></Panel>

  // Weaving monthly trend
  const trend = ops.weaving?.monthly_trend
  if (trend && trend.length > 0) {
    const recent = trend.slice(-12)
    const labels = recent.map(m => {
      const [y, mo] = m.month.split("-")
      return new Date(+y, +mo - 1).toLocaleString("default", { month: "short" })
    })
    return (
      <Panel title="Weaving Monthly Trend" href="/weaving/dashboard">
        <Line
          data={{
            labels,
            datasets: [
              {
                label: "Grey (m)",
                data: recent.map(m => m.grey_meters),
                borderColor: "#2563eb",
                backgroundColor: "rgba(37,99,235,0.12)",
                tension: 0.35,
                fill: true,
                pointRadius: 3,
              },
              {
                label: "Dispatch (m)",
                data: recent.map(m => m.dispatch_meters),
                borderColor: "#16a34a",
                backgroundColor: "rgba(22,163,74,0.10)",
                tension: 0.35,
                fill: true,
                pointRadius: 3,
              },
            ],
          }}
          options={lineOpts}
        />
      </Panel>
    )
  }

  // Spinning mass flow bars
  if (ops.spinning) {
    const k = ops.spinning.kpis
    return (
      <Panel title="Spinning Mass Flow (kg)" href="/spinning/dashboard">
        <Bar
          data={{
            labels: ["Bale In", "Cone Out", "Dispatched"],
            datasets: [{
              data: [k.bale_received?.kg ?? 0, k.cone_output?.kg ?? 0, k.dispatched?.kg ?? 0],
              backgroundColor: ["rgba(184,148,63,0.85)", "rgba(37,99,235,0.80)", "rgba(22,163,74,0.80)"],
              borderRadius: 4,
            }],
          }}
          options={barOpts(n => n.toLocaleString(undefined, { maximumFractionDigits: 1 }))}
        />
      </Panel>
    )
  }

  // Telecom FCA vs target
  if (ops.telecom) {
    const f = ops.telecom.fca
    const target = f.target != null ? Number(f.target) : 0
    return (
      <Panel title={`FCA Progress (${f.month})`} href="/telecom/fca">
        <Bar
          data={{
            labels: ["Actual", "Target"],
            datasets: [{
              data: [f.actual, target],
              backgroundColor: ["rgba(37,99,235,0.85)", "rgba(184,148,63,0.75)"],
              borderRadius: 4,
            }],
          }}
          options={barOpts()}
        />
        {f.achievement_pct != null && (
          <p className="text-[10px] text-[var(--text-primary)]/50 mt-1 text-center">
            Achievement {Number(f.achievement_pct).toFixed(1)}%
          </p>
        )}
      </Panel>
    )
  }

  // Healthcare today activity bars
  if (ops.healthcare) {
    const h = ops.healthcare
    return (
      <Panel title="Today's Throughput" href="/healthcare">
        <Bar
          data={{
            labels: ["Tokens", "Visits", "Admitted", "Pending Labs", "Dialysis"],
            datasets: [{
              data: [
                h.tokens_today,
                h.visits_today,
                h.currently_admitted,
                h.pending_lab_results,
                h.dialysis_sessions_today ?? 0,
              ],
              backgroundColor: PALETTE.slice(0, 5),
              borderRadius: 4,
            }],
          }}
          options={barOpts()}
        />
      </Panel>
    )
  }

  // Textile meters mix
  if (ops.textile_processing) {
    const k = ops.textile_processing.kpis
    return (
      <Panel title="Meters Overview" href="/processing">
        <Bar
          data={{
            labels: ["Received", "Ready", "Rejection", "Vis. Waste", "Invis. Waste"],
            datasets: [{
              data: [
                k.received_mtr, k.ready_mtr, k.rejection_pending_mtr,
                k.visible_wastage_mtr, k.invisible_wastage_mtr,
              ],
              backgroundColor: PALETTE.slice(0, 5),
              borderRadius: 4,
            }],
          }}
          options={barOpts(n => n.toLocaleString(undefined, { maximumFractionDigits: 0 }))}
        />
      </Panel>
    )
  }

  // Production cost bars
  if (ops.production) {
    const t = ops.production.totals
    return (
      <Panel title="WIP vs Finished Goods Cost" href="/manufacturing">
        <Bar
          data={{
            labels: ["WIP Cost", "FG Cost"],
            datasets: [{
              data: [Number(t.wip_cost || 0), Number(t.finished_goods_cost || 0)],
              backgroundColor: ["rgba(249,115,22,0.85)", "rgba(22,163,74,0.80)"],
              borderRadius: 4,
            }],
          }}
          options={barOpts(ctx.fmt)}
        />
      </Panel>
    )
  }

  // Purchase status bars
  if (ops.purchase_store?.po_by_status) {
    const entries = Object.entries(ops.purchase_store.po_by_status)
    return (
      <Panel title="PO Status Distribution" href="/purchases">
        <Bar
          data={{
            labels: entries.map(([s]) => prettyStatus(s)),
            datasets: [{
              data: entries.map(([, n]) => n),
              backgroundColor: PALETTE,
              borderRadius: 4,
            }],
          }}
          options={barOpts()}
        />
      </Panel>
    )
  }

  return (
    <Panel title="Operations Trend" href="/apps">
      <Empty msg="No trend series for installed modules yet" />
    </Panel>
  )
}

/** Status / process table for operational control. */
export function OpsStatusTable({ ctx }: { ctx: WidgetContext }) {
  const ops = ctx.opsSummary
  if (!ops) return <Panel title="Status Board" href="/dashboard"><Loading /></Panel>

  type Row = { label: string; value: string | number; tone?: "warn" | "danger" | "ok" }
  let title = "Status Board"
  let href = "/dashboard"
  let rows: Row[] = []

  if (ops.spinning) {
    title = "Spin Lot Status"
    href = "/spinning/lots"
    const s = ops.spinning.kpis.status_summary || {}
    rows = Object.entries(s).map(([k, v]) => ({
      label: prettyStatus(k),
      value: v,
      tone: k === "in_process" || k === "draft" ? "warn" : k === "cancelled" ? "danger" : "ok",
    }))
    rows.unshift(
      { label: "Open Lots", value: ops.spinning.kpis.open_lots, tone: "warn" },
      { label: "Yield %", value: `${ops.spinning.kpis.overall_yield_pct.toFixed(1)}%`, tone: "ok" },
    )
  } else if (ops.production) {
    title = "Production Orders"
    href = "/manufacturing/production-orders"
    const p = ops.production.pipeline
    rows = (["draft", "started", "completed", "delivered", "billed", "cancelled"] as const).map(k => ({
      label: prettyStatus(k),
      value: p[k] ?? 0,
      tone: k === "started" ? "warn" : k === "cancelled" ? "danger" : "ok",
    }))
  } else if (ops.weaving) {
    title = "Contract Status"
    href = "/weaving"
    const s = ops.weaving.kpis.status_summary || {}
    rows = Object.entries(s).map(([k, v]) => ({
      label: prettyStatus(k),
      value: v,
      tone: k === "active" || k === "in_process" ? "warn" : "ok",
    }))
    rows.push(
      { label: "Grey Meters", value: Math.round(ops.weaving.kpis.grey_meters).toLocaleString() },
      { label: "Avg Efficiency", value: `${ops.weaving.kpis.avg_efficiency_pct.toFixed(1)}%`, tone: "ok" },
    )
  } else if (ops.purchase_store) {
    title = "Purchase Status Board"
    href = "/purchases"
    const d = ops.purchase_store.demand_by_status || {}
    const p = ops.purchase_store.po_by_status || {}
    rows = [
      ...Object.entries(d).map(([k, v]) => ({ label: `Demand · ${prettyStatus(k)}`, value: v, tone: (k === "draft" || k === "approved" ? "warn" : "ok") as Row["tone"] })),
      ...Object.entries(p).map(([k, v]) => ({ label: `PO · ${prettyStatus(k)}`, value: v, tone: (k === "approved" || k === "received" ? "warn" : k === "cancelled" ? "danger" : "ok") as Row["tone"] })),
      { label: "Low Stock Items", value: ops.purchase_store.low_stock_items, tone: ops.purchase_store.low_stock_items > 0 ? "danger" : "ok" },
    ]
  } else if (ops.healthcare) {
    title = "Census Board"
    href = "/healthcare"
    const h = ops.healthcare
    rows = [
      { label: "Tokens Today", value: h.tokens_today },
      { label: "Visits Today", value: h.visits_today, tone: "ok" },
      { label: "Currently Admitted", value: h.currently_admitted, tone: "warn" },
      { label: "Bed Occupancy", value: `${h.bed_occupancy_pct}%`, tone: h.bed_occupancy_pct > 90 ? "danger" : "ok" },
      { label: "Pending Labs", value: h.pending_lab_results, tone: h.pending_lab_results > 0 ? "warn" : "ok" },
      { label: "Dialysis Today", value: h.dialysis_sessions_today ?? 0 },
    ]
  } else if (ops.telecom) {
    title = "Tracker Board"
    href = "/telecom"
    const t = ops.telecom
    rows = [
      { label: "Load Float", value: ctx.fmt(Number(t.tracker.load_float || 0)) },
      { label: "Deposit Balance", value: ctx.fmt(Number(t.tracker.deposit_balance || 0)) },
      { label: "RSO Agents", value: t.rso.agent_count },
      { label: "SIMs Available", value: t.sim.available, tone: t.sim.available < 10 ? "warn" : "ok" },
      { label: "FCA Actual", value: t.fca.actual },
      { label: "FCA Achievement", value: t.fca.achievement_pct != null ? `${Number(t.fca.achievement_pct).toFixed(1)}%` : "—", tone: "ok" },
    ]
  } else if (ops.textile_processing) {
    title = "Processing Board"
    href = "/processing"
    const k = ops.textile_processing.kpis
    rows = [
      { label: "Lots Total", value: k.lots_total },
      { label: "In Process", value: k.lots_in_process, tone: "warn" },
      { label: "Ready", value: k.lots_ready, tone: "ok" },
      { label: "Rejection Pending (m)", value: Math.round(k.rejection_pending_mtr).toLocaleString(), tone: k.rejection_pending_mtr > 0 ? "danger" : "ok" },
      { label: "Visible Wastage (m)", value: Math.round(k.visible_wastage_mtr).toLocaleString() },
    ]
  } else if (ops.hrm) {
    title = "Workforce Board"
    href = "/hrm"
    const h = ops.hrm
    rows = [
      { label: "Active Employees", value: h.active_employees },
      { label: "Pending Payroll Runs", value: h.pending_runs, tone: h.pending_runs > 0 ? "warn" : "ok" },
      { label: "Attendance MTD", value: `${h.avg_attendance_pct}%`, tone: h.avg_attendance_pct < 70 ? "danger" : "ok" },
      { label: "Last Payroll Net", value: ctx.fmt(h.last_payroll_net) },
    ]
  }

  if (rows.length === 0) {
    return (
      <Panel title="Status Board" href="/apps">
        <Empty msg="No operational status rows yet" />
      </Panel>
    )
  }

  return (
    <Panel title={title} href={href}>
      <div className="overflow-auto h-full">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-[var(--text-primary)]/45 border-b border-[var(--border)]">
              <th className="text-left py-1.5 font-bold">Metric / Status</th>
              <th className="text-right py-1.5 font-bold">Value</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.label} className="border-b border-[var(--border)]/60 last:border-0">
                <td className="py-1.5 text-[var(--text-primary)]/75">{r.label}</td>
                <td className={`py-1.5 text-right font-semibold tabular-nums ${
                  r.tone === "danger" ? "text-red-600"
                    : r.tone === "warn" ? "text-amber-600"
                      : "text-[var(--text-primary)]"
                }`}>{r.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

/** Mixed secondary doughnut — mass/attention mix when primary chart is already used. */
export function OpsMixChart({ ctx }: { ctx: WidgetContext }) {
  const ops = ctx.opsSummary
  if (!ops) return <Panel title="Mix View" href="/dashboard"><Loading /></Panel>

  if (ops.spinning) {
    const s = ops.spinning.kpis.status_summary || {}
    const entries = Object.entries(s)
    if (entries.length === 0) return <Panel title="Lot Mix" href="/spinning/lots"><Empty msg="No lots yet" /></Panel>
    return (
      <Panel title="Lot Status Mix" href="/spinning/lots">
        <Doughnut
          data={{
            labels: entries.map(([k]) => prettyStatus(k)),
            datasets: [{
              data: entries.map(([, v]) => v),
              backgroundColor: PALETTE,
              borderWidth: 2,
              borderColor: "#fff",
            }],
          }}
          options={doughnutOpts}
        />
      </Panel>
    )
  }

  if (ops.telecom) {
    const t = ops.telecom.tracker
    return (
      <Panel title="Tracker Floats" href="/telecom/tracker">
        <Bar
          data={{
            labels: ["Deposit", "Load Float", "RSO Load Rec.", "Retail Load Rec."],
            datasets: [{
              data: [
                Number(t.deposit_balance || 0),
                Number(t.load_float || 0),
                Number(t.rso_load_receivable || 0),
                Number(t.retail_load_receivable || 0),
              ],
              backgroundColor: PALETTE.slice(0, 4),
              borderRadius: 4,
            }],
          }}
          options={hBarOpts(ctx.fmt)}
        />
      </Panel>
    )
  }

  if (ops.healthcare) {
    const h = ops.healthcare
    return (
      <Panel title="Care Activity Mix" href="/healthcare">
        <Doughnut
          data={{
            labels: ["Tokens", "Visits", "Admitted", "Pending Labs"],
            datasets: [{
              data: [h.tokens_today, h.visits_today, h.currently_admitted, h.pending_lab_results],
              backgroundColor: PALETTE.slice(0, 4),
              borderWidth: 2,
              borderColor: "#fff",
            }],
          }}
          options={doughnutOpts}
        />
      </Panel>
    )
  }

  if (ops.weaving) {
    const k = ops.weaving.kpis
    return (
      <Panel title="Grey vs Dispatch (m)" href="/weaving/dashboard">
        <Bar
          data={{
            labels: ["Grey Produced", "Dispatched"],
            datasets: [{
              data: [k.grey_meters, k.dispatch_meters],
              backgroundColor: ["rgba(37,99,235,0.80)", "rgba(22,163,74,0.80)"],
              borderRadius: 4,
            }],
          }}
          options={barOpts(n => Math.round(n).toLocaleString())}
        />
      </Panel>
    )
  }

  if (ops.purchase_store?.demand_by_status) {
    const entries = Object.entries(ops.purchase_store.demand_by_status)
    return (
      <Panel title="Demand Status Mix" href="/purchases/demands">
        <Doughnut
          data={{
            labels: entries.map(([k]) => prettyStatus(k)),
            datasets: [{
              data: entries.map(([, v]) => v),
              backgroundColor: PALETTE,
              borderWidth: 2,
              borderColor: "#fff",
            }],
          }}
          options={doughnutOpts}
        />
      </Panel>
    )
  }

  if (ops.textile_processing) {
    const k = ops.textile_processing.kpis
    return (
      <Panel title="Meters Mix" href="/processing">
        <Doughnut
          data={{
            labels: ["Ready", "Rejection", "Vis. Waste", "Invis. Waste"],
            datasets: [{
              data: [
                k.ready_mtr,
                k.rejection_pending_mtr,
                k.visible_wastage_mtr,
                k.invisible_wastage_mtr,
              ],
              backgroundColor: PALETTE.slice(0, 4),
              borderWidth: 2,
              borderColor: "#fff",
            }],
          }}
          options={doughnutOpts}
        />
      </Panel>
    )
  }

  if (ops.production) {
    const p = ops.production.pipeline
    return (
      <Panel title="Order State Mix" href="/manufacturing">
        <Doughnut
          data={{
            labels: ["Draft", "Started", "Completed", "Delivered", "Billed"],
            datasets: [{
              data: [p.draft ?? 0, p.started ?? 0, p.completed ?? 0, p.delivered ?? 0, p.billed ?? 0],
              backgroundColor: PALETTE.slice(0, 5),
              borderWidth: 2,
              borderColor: "#fff",
            }],
          }}
          options={doughnutOpts}
        />
      </Panel>
    )
  }

  return (
    <Panel title="Mix View" href="/apps">
      <Empty msg="No mix chart for current modules" />
    </Panel>
  )
}
