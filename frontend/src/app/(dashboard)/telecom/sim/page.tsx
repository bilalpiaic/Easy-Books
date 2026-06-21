"use client"

import { useEffect, useState } from "react"
import { Smartphone, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { ActionForm, FieldDef, SelectOption } from "@/components/telecom/ActionForm"
import {
  PageHeader, Section, Tabs, DataTable, Column, ErrorBanner, money, useTelecomList,
} from "@/components/telecom/primitives"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface Operator { id: number; name: string; operator_code: string }
interface SimBatch { id: number; batch_number: string; qty_received: number; qty_activated: number; unit_cost: string; received_date: string }
interface SimActivation {
  id: number; sim_number: string; activation_date: string; activation_type: string
  status: string; commission_rate: string; commission_status: string; customer_name: string | null
}
interface UtilRow { id: number; batch_number: string; qty_received: number; qty_activated: number; qty_available: number; unit_cost: string }

export default function SimPage() {
  const operators = useTelecomList<Operator>("/api/telecom/operators")
  const batches = useTelecomList<SimBatch>("/api/telecom/sim/batches")
  const activations = useTelecomList<SimActivation>("/api/telecom/sim/activations")

  const [util, setUtil] = useState<UtilRow[]>([])
  useEffect(() => {
    apiFetch<{ items: UtilRow[] }>("/api/telecom/reports/sim-utilisation")
      .then(d => setUtil(d.items)).catch(() => {})
  }, [batches.items.length])

  const opOptions: SelectOption[] = operators.items.map(o => ({ value: String(o.id), label: `${o.name} (${o.operator_code})` }))
  const actOptions: SelectOption[] = activations.items
    .filter(a => a.commission_status !== "accrued" && a.commission_status !== "settled")
    .map(a => ({ value: String(a.id), label: `${a.sim_number} — ${a.customer_name ?? "walk-in"}` }))

  const activationFields: FieldDef[] = [
    { kind: "select", name: "operator_id", label: "Operator", required: true, options: opOptions },
    { kind: "text", name: "sim_number", label: "SIM / MSISDN", required: true },
    { kind: "select", name: "activation_type", label: "Type", default: "prepaid",
      options: [{ value: "prepaid", label: "Prepaid" }, { value: "postpaid", label: "Postpaid" }] },
    { kind: "text", name: "customer_name", label: "Customer name" },
    { kind: "text", name: "customer_cnic", label: "Customer CNIC" },
    { kind: "number", name: "commission_rate", label: "Commission (each)", default: "0" },
    { kind: "date", name: "date", label: "Activation date" },
  ]
  const accrueFields: FieldDef[] = [
    { kind: "select", name: "activation_id", label: "Activation", required: true, options: actOptions },
    { kind: "number", name: "amount", label: "Commission amount", required: true, help: "Dr 1110 Commission Receivable / Cr revenue" },
    { kind: "select", name: "revenue_account_code", label: "Revenue stream", default: "4020",
      options: [
        { value: "4020", label: "Load uplift (4020)" },
        { value: "4010", label: "SIM activation (4010)" },
        { value: "4021", label: "Recharge commission (4021)" },
      ] },
    { kind: "date", name: "date", label: "Date" },
  ]
  const counterFields: FieldDef[] = [
    { kind: "number", name: "qty", label: "Quantity", required: true, step: "1" },
    { kind: "number", name: "sale_price", label: "Sale price (each)", required: true },
    { kind: "number", name: "unit_cost", label: "Unit cost (each)", required: true },
    { kind: "date", name: "date", label: "Date" },
  ]

  const batchCols: Column<UtilRow>[] = [
    { header: "Batch", cell: b => b.batch_number, mono: true },
    { header: "Received", cell: b => String(b.qty_received) },
    { header: "Activated", cell: b => String(b.qty_activated) },
    { header: "Available", cell: b => String(b.qty_available) },
    { header: "Unit cost", cell: b => money(b.unit_cost) },
  ]
  const actCols: Column<SimActivation>[] = [
    { header: "SIM / MSISDN", cell: a => a.sim_number, mono: true },
    { header: "Date", cell: a => a.activation_date, mono: true },
    { header: "Type", cell: a => a.activation_type },
    { header: "Customer", cell: a => a.customer_name ?? "—" },
    { header: "Commission", cell: a => money(a.commission_rate) },
    { header: "Status", cell: a => (
      <span className={a.commission_status === "settled" ? "text-emerald-700" : a.commission_status === "accrued" ? "text-amber-700" : "text-[#1a1814]/50"}>
        {a.commission_status}
      </span>
    )},
  ]

  return (
    <div className="space-y-6">
      <PrintHeader title="SIM & Activations" orientation="landscape" />
      <div className="flex items-center justify-between">
        <PageHeader icon={Smartphone} title="SIM & Activations" subtitle="SIM batches, customer activations, counter sales and commission accrual." />
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors print:hidden"
        >
          <Printer className="w-4 h-4" /> Print
        </button>
      </div>

      <HelpCallout title="SIM stock vs commission" tone="tip">
        SIM <b>inventory</b> arrives via a tracker stock-debit and lives at cost (Acct 1200). When you
        <b> activate</b> a SIM you log the activation and later <b>accrue</b> the operator commission as a
        receivable (Acct 1110), cleared when the commission statement settles.
      </HelpCallout>

      <ErrorBanner error={operators.error ?? batches.error ?? activations.error} />

      <Tabs tabs={[
        { id: "activate", label: "Activate SIM", content: (
          <div className="space-y-4">
            <Section title="Record a SIM activation">
              <ActionForm endpoint="/api/telecom/sim/activations" fields={activationFields} submitLabel="Activate" successText={() => "Activation recorded."} onSuccess={activations.refetch} />
            </Section>
            <Section title="Recent activations" action={
              <button onClick={() => downloadCSV('sim-activations.csv', activations.items.map(a => ({ "SIM/MSISDN": a.sim_number, Date: a.activation_date, Type: a.activation_type, Customer: a.customer_name ?? '', Commission: a.commission_rate, "Commission Status": a.commission_status, Status: a.status })))} disabled={activations.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>
            }>
              <DataTable columns={actCols} rows={activations.items} empty="No activations yet." />
            </Section>
          </div>
        )},
        { id: "accrue", label: "Accrue commission", content: (
          <Section title="Accrue activation commission">
            <ActionForm endpoint="/api/telecom/sim/activations/accrue-commission" fields={accrueFields} submitLabel="Accrue commission" onSuccess={activations.refetch} />
          </Section>
        )},
        { id: "counter", label: "Counter sale", content: (
          <Section title="Walk-in SIM counter sale">
            <ActionForm endpoint="/api/telecom/sim/counter-sales" fields={counterFields} submitLabel="Post sale" successText={r => {
              const x = r as { sale_transaction?: { jv_number?: string } }
              return x?.sale_transaction?.jv_number ? `Posted — JV ${x.sale_transaction.jv_number}` : "Sale posted."
            }} />
          </Section>
        )},
        { id: "batches", label: "Batches", content: (
          <Section title="SIM batch utilisation" action={
            <button onClick={() => downloadCSV('sim-batches.csv', util.map(b => ({ Batch: b.batch_number, Received: b.qty_received, Activated: b.qty_activated, Available: b.qty_available, "Unit Cost": b.unit_cost })))} disabled={util.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>
          }>
            <DataTable columns={batchCols} rows={util} empty="No SIM batches yet — procure stock via Tracker → Stock debit." />
          </Section>
        )},
      ]} />
    </div>
  )
}
