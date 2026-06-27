"use client"

import { useEffect, useState } from "react"
import { Percent, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { ActionForm, FieldDef, SelectOption } from "@/components/telecom/ActionForm"
import {
  PageHeader, Section, Tabs, DataTable, Column, ErrorBanner, Tile, money, useTelecomList,
} from "@/components/telecom/primitives"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface Operator { id: number; name: string; operator_code: string }
interface Statement {
  id: number; operator_id: number; statement_date: string; period_from: string; period_to: string
  statement_reference: string | null; total_commission: string; status: string
}
interface Aging { current: string; "1_30": string; "31_60": string; "61_90": string; "90_plus": string }

export default function CommissionsPage() {
  const { t } = useTranslation()

  const operators = useTelecomList<Operator>("/api/telecom/operators")
  const statements = useTelecomList<Statement>("/api/telecom/commissions/statements")

  const [aging, setAging] = useState<Aging | null>(null)
  useEffect(() => {
    apiFetch<Aging>("/api/telecom/reports/commission-aging").then(setAging).catch(() => {})
  }, [statements.items.length])

  const opOptions: SelectOption[] = operators.items.map(o => ({ value: String(o.id), label: `${o.name} (${o.operator_code})` }))
  const stmtOptions: SelectOption[] = statements.items
    .filter(s => s.status !== "settled")
    .map(s => ({ value: String(s.id), label: `${s.statement_date} — ${money(s.total_commission)}` }))

  const stmtFields: FieldDef[] = [
    { kind: "select", name: "operator_id", label: "Operator", required: true, options: opOptions },
    { kind: "date", name: "statement_date", label: "Statement date", required: true },
    { kind: "date", name: "period_from", label: "Period from", required: true },
    { kind: "date", name: "period_to", label: "Period to", required: true },
    { kind: "text", name: "statement_reference", label: "Reference" },
    { kind: "number", name: "total_commission", label: "Total commission", required: true },
  ]
  const settleFields: FieldDef[] = [
    { kind: "select", name: "statement_id", label: "Statement", required: true, options: stmtOptions },
    { kind: "number", name: "settlement_amount", label: "Settlement amount", required: true, help: "Clears 1110 receivable; variance to incentive/adjustment" },
    { kind: "select", name: "credit_via", label: "Settled via", default: "bank",
      options: [{ value: "bank", label: "Bank" }, { value: "tracker", label: "Tracker deposit" }] },
    { kind: "date", name: "date", label: "Date" },
  ]

  const stmtCols: Column<Statement>[] = [
    { header: "Date", cell: s => s.statement_date, mono: true },
    { header: "Period", cell: s => `${s.period_from} → ${s.period_to}` },
    { header: "Reference", cell: s => s.statement_reference ?? "—" },
    { header: "Total", cell: s => money(s.total_commission) },
    { header: "Status", cell: s => (
      <span className={s.status === "settled" ? "text-emerald-700 font-semibold" : "text-amber-700"}>{s.status}</span>
    )},
  ]

  return (
    <div className="space-y-6">
      <PrintHeader title="Telecom Commissions" />
      <div className="flex items-center justify-between">
        <PageHeader icon={Percent} title="Commissions" subtitle="Operator commission statements, settlement and receivable aging." />
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors print:hidden"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      <HelpCallout title="Accrue, then reconcile" tone="tip">
        Commission you've earned sits as a <b>receivable</b> (Acct 1110). When the operator issues a
        <b> commission statement</b> and pays, you <b>settle</b> it — any difference between what you accrued and
        what they paid posts to a franchise incentive (gain) or adjustment (shortfall).
      </HelpCallout>

      <ErrorBanner error={operators.error ?? statements.error} />

      {aging && (
        <Section title="Receivable aging">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <Tile icon={Percent} label="Current" value={money(aging.current)} />
            <Tile icon={Percent} label="1–30 days" value={money(aging["1_30"])} />
            <Tile icon={Percent} label="31–60 days" value={money(aging["31_60"])} />
            <Tile icon={Percent} label="61–90 days" value={money(aging["61_90"])} />
            <Tile icon={Percent} label="90+ days" value={money(aging["90_plus"])} />
          </div>
        </Section>
      )}

      <Tabs tabs={[
        { id: "settle", label: "Settle", content: (
          <Section title="Settle a commission statement">
            <ActionForm endpoint="/api/telecom/commissions/settle" fields={settleFields} submitLabel="Settle statement" onSuccess={statements.refetch} />
          </Section>
        )},
        { id: "statements", label: "Statements", content: (
          <div className="space-y-4">
            <Section title="Commission statements" action={
              <button onClick={() => downloadCSV('commissions.csv', statements.items.map(s => ({ Date: s.statement_date, "Period From": s.period_from, "Period To": s.period_to, Reference: s.statement_reference ?? '', Total: s.total_commission, Status: s.status })))} disabled={statements.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] rounded-lg text-xs font-bold hover:bg-[var(--bg-page)] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>
            }><DataTable columns={stmtCols} rows={statements.items} empty="No statements yet." /></Section>
            <Section title="Record a commission statement">
              <ActionForm endpoint="/api/telecom/commissions/statements" fields={stmtFields} submitLabel="Record statement" successText={() => "Statement recorded."} onSuccess={statements.refetch} />
            </Section>
          </div>
        )},
      ]} />
    </div>
  )
}
