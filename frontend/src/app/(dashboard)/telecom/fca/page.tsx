"use client"

import { useEffect, useState } from "react"
import { Target, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { ActionForm, FieldDef, SelectOption } from "@/components/telecom/ActionForm"
import {
  PageHeader, Section, Tabs, DataTable, Column, ErrorBanner, money, useTelecomList,
} from "@/components/telecom/primitives"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface Operator { id: number; name: string; operator_code: string }
interface TrackerAccount { id: number; account_number: string }
interface FcaEvent { id: number; msisdn: string; event_date: string; source_channel: string }
interface KpiTarget { id: number; target_month: string; metric: string; target_value: string }
interface FcaProgress { month: string; target: string; actual: number; achievement_pct: string | null; delta: string }

export default function FcaPage() {
  const operators = useTelecomList<Operator>("/api/telecom/operators")
  const accounts = useTelecomList<TrackerAccount>("/api/telecom/tracker-accounts")
  const events = useTelecomList<FcaEvent>("/api/telecom/fca/events")
  const targets = useTelecomList<KpiTarget>("/api/telecom/kpi/targets")

  const [progress, setProgress] = useState<FcaProgress | null>(null)
  useEffect(() => {
    apiFetch<FcaProgress>("/api/telecom/reports/fca-target")
      .then(setProgress).catch(() => {})
  }, [events.items.length, targets.items.length])

  const opOptions: SelectOption[] = operators.items.map(o => ({ value: String(o.id), label: `${o.name} (${o.operator_code})` }))
  const acctOptions: SelectOption[] = accounts.items.map(a => ({ value: String(a.id), label: a.account_number }))

  const eventFields: FieldDef[] = [
    { kind: "text", name: "msisdn", label: "MSISDN", required: true, placeholder: "03001234567" },
    { kind: "select", name: "source_channel", label: "Source channel", default: "rso_retail",
      options: [
        { value: "rso_retail", label: "RSO / Retail" },
        { value: "counter", label: "Counter" },
        { value: "online", label: "Online" },
      ] },
    { kind: "date", name: "date", label: "Event date" },
  ]
  const targetFields: FieldDef[] = [
    { kind: "select", name: "operator_id", label: "Operator", required: true, options: opOptions },
    { kind: "text", name: "target_month", label: "Target month", required: true, placeholder: "2026-05" },
    { kind: "select", name: "metric", label: "Metric", default: "fca",
      options: [
        { value: "fca", label: "FCA (first-call activations)" },
        { value: "recharge", label: "Recharge volume" },
        { value: "sim_sales", label: "SIM sales" },
      ] },
    { kind: "number", name: "target_value", label: "Target value", required: true, step: "1" },
  ]
  const commissionFields: FieldDef[] = [
    { kind: "select", name: "credit_to", label: "Credit to", default: "tracker",
      options: [{ value: "tracker", label: "Tracker deposit" }, { value: "bank", label: "Bank" }] },
    { kind: "select", name: "tracker_account_id", label: "Tracker account", options: acctOptions, help: "Required when crediting tracker" },
    { kind: "number", name: "amount", label: "Commission amount", required: true, help: "Cr 4060 FCA Target Commission" },
    { kind: "date", name: "date", label: "Date" },
  ]
  const penaltyFields: FieldDef[] = [
    { kind: "select", name: "tracker_account_id", label: "Tracker account", required: true, options: acctOptions },
    { kind: "number", name: "amount", label: "Penalty amount", required: true, help: "Dr 5090 Target Shortfall Penalty / Cr Tracker" },
    { kind: "date", name: "date", label: "Date" },
  ]

  const eventCols: Column<FcaEvent>[] = [
    { header: "MSISDN", cell: e => e.msisdn, mono: true },
    { header: "Date", cell: e => e.event_date, mono: true },
    { header: "Channel", cell: e => e.source_channel },
  ]
  const targetCols: Column<KpiTarget>[] = [
    { header: "Month", cell: t => t.target_month, mono: true },
    { header: "Metric", cell: t => t.metric },
    { header: "Target", cell: t => money(t.target_value) },
  ]

  const pct = progress?.achievement_pct ? Number(progress.achievement_pct) : null

  return (
    <div className="space-y-6">
      <PrintHeader title="FCA & Targets" />
      <div className="flex items-center justify-between">
        <PageHeader icon={Target} title="FCA & Targets" subtitle="First-call activations counted toward monthly operator targets." />
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors print:hidden"
        >
          <Printer className="w-4 h-4" /> Print
        </button>
      </div>

      <HelpCallout title="FCA is counted, not booked per event" tone="tip">
        Each first-call activation is a <b>counter</b>, not a journal entry. Hitting the monthly target unlocks a
        <b> target commission</b> (Acct 4060); missing it can trigger a <b>shortfall penalty</b> (Acct 5090). Only
        those settlement events post to the GL.
      </HelpCallout>

      <ErrorBanner error={events.error ?? targets.error} />

      {progress && (
        <Section title={`Progress — ${progress.month}`}>
          <div className="bg-white border border-[#ede9e2] rounded-2xl px-4 py-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#1a1814]/60">Activations this month</span>
              <span className="font-serif font-bold">{progress.actual} / {money(progress.target)}</span>
            </div>
            <div className="mt-2 h-2.5 rounded-full bg-[#f0ece4] overflow-hidden">
              <div className="h-full bg-[#b8943f]" style={{ width: pct !== null ? `${Math.min(pct, 100)}%` : "0%" }} />
            </div>
            <div className="mt-1.5 text-xs text-[#1a1814]/55">
              {pct !== null ? `${pct}% — delta ${progress.delta}` : "No target set for this month."}
            </div>
          </div>
        </Section>
      )}

      <Tabs tabs={[
        { id: "event", label: "Log FCA", content: (
          <div className="space-y-4">
            <Section title="Log a first-call activation">
              <ActionForm endpoint="/api/telecom/fca/events" fields={eventFields} submitLabel="Log event" successText={() => "FCA event logged."} onSuccess={events.refetch} />
            </Section>
            <Section title="Recent events" action={<button onClick={() => downloadCSV('fca-events.csv', events.items.map(e => ({ MSISDN: e.msisdn, Date: e.event_date, Channel: e.source_channel })))} disabled={events.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}><DataTable columns={eventCols} rows={events.items} empty="No FCA events yet." /></Section>
          </div>
        )},
        { id: "target", label: "Targets", content: (
          <div className="space-y-4">
            <Section title="Set a monthly target">
              <ActionForm endpoint="/api/telecom/kpi/targets" fields={targetFields} submitLabel="Save target" successText={() => "Target saved."} onSuccess={targets.refetch} />
            </Section>
            <Section title="Targets" action={<button onClick={() => downloadCSV('fca-targets.csv', targets.items.map(t => ({ Month: t.target_month, Metric: t.metric, Target: t.target_value })))} disabled={targets.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}><DataTable columns={targetCols} rows={targets.items} empty="No targets set yet." /></Section>
          </div>
        )},
        { id: "commission", label: "Target commission", content: (
          <Section title="Post target commission earned">
            <ActionForm endpoint="/api/telecom/fca/target-commission" fields={commissionFields} submitLabel="Post commission" onSuccess={accounts.refetch} />
          </Section>
        )},
        { id: "penalty", label: "Shortfall penalty", content: (
          <Section title="Post target shortfall penalty">
            <ActionForm endpoint="/api/telecom/fca/target-penalty" fields={penaltyFields} submitLabel="Post penalty" onSuccess={accounts.refetch} />
          </Section>
        )},
      ]} />
    </div>
  )
}
