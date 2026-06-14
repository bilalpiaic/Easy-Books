"use client"

import { ReceiptText, Download } from "lucide-react"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { ActionForm, FieldDef, SelectOption } from "@/components/telecom/ActionForm"
import {
  PageHeader, Section, Tabs, DataTable, Column, ErrorBanner, money, useTelecomList,
} from "@/components/telecom/primitives"
import { downloadCSV } from "@/lib/utils"

interface Operator { id: number; name: string; operator_code: string }
interface Connection { id: number; msisdn: string; customer_name: string; plan_name: string; monthly_rental: string; activation_date: string }
interface BillCycle {
  id: number; connection_id: number; billing_month: string; gross_amount: string
  franchise_commission: string; net_remittance: string
  collection_status: string; remittance_status: string
}

export default function PostpaidPage() {
  const operators = useTelecomList<Operator>("/api/telecom/operators")
  const connections = useTelecomList<Connection>("/api/telecom/postpaid/connections")
  const cycles = useTelecomList<BillCycle>("/api/telecom/postpaid/cycles")

  const opOptions: SelectOption[] = operators.items.map(o => ({ value: String(o.id), label: `${o.name} (${o.operator_code})` }))
  const connOptions: SelectOption[] = connections.items.map(c => ({ value: String(c.id), label: `${c.msisdn} — ${c.customer_name}` }))
  const cycleOptions: SelectOption[] = cycles.items.map(c => ({ value: String(c.id), label: `${c.billing_month} — ${money(c.gross_amount)}` }))

  const connFields: FieldDef[] = [
    { kind: "select", name: "operator_id", label: "Operator", required: true, options: opOptions },
    { kind: "text", name: "msisdn", label: "MSISDN", required: true },
    { kind: "text", name: "customer_name", label: "Customer name", required: true },
    { kind: "text", name: "customer_cnic", label: "Customer CNIC" },
    { kind: "text", name: "plan_name", label: "Plan name", required: true, placeholder: "Postpaid Pro" },
    { kind: "number", name: "monthly_rental", label: "Monthly rental", required: true },
    { kind: "number", name: "franchise_commission_rate", label: "Commission %", default: "10" },
    { kind: "date", name: "date", label: "Activation date" },
  ]
  const billFields: FieldDef[] = [
    { kind: "select", name: "connection_id", label: "Connection", required: true, options: connOptions },
    { kind: "text", name: "billing_month", label: "Billing month", required: true, placeholder: "2026-05" },
    { kind: "number", name: "gross_amount", label: "Gross bill amount", required: true, help: "Dr 1130 Customer Receivable / Cr 2110 Collections Payable" },
  ]
  const collectFields: FieldDef[] = [
    { kind: "select", name: "cycle_id", label: "Bill cycle", required: true, options: cycleOptions },
    { kind: "number", name: "amount", label: "Amount collected", required: true, help: "Dr Cash / Cr 1130 Customer Receivable" },
    { kind: "date", name: "date", label: "Date" },
  ]
  const remitFields: FieldDef[] = [
    { kind: "select", name: "cycle_id", label: "Bill cycle", required: true, options: cycleOptions },
    { kind: "date", name: "date", label: "Date" },
  ]

  const connCols: Column<Connection>[] = [
    { header: "MSISDN", cell: c => c.msisdn, mono: true },
    { header: "Customer", cell: c => c.customer_name },
    { header: "Plan", cell: c => c.plan_name },
    { header: "Rental", cell: c => money(c.monthly_rental) },
  ]
  const cycleCols: Column<BillCycle>[] = [
    { header: "Month", cell: c => c.billing_month, mono: true },
    { header: "Gross", cell: c => money(c.gross_amount) },
    { header: "Commission", cell: c => money(c.franchise_commission) },
    { header: "Net remit", cell: c => money(c.net_remittance) },
    { header: "Collection", cell: c => (
      <span className={c.collection_status === "collected" ? "text-emerald-700 font-semibold" : "text-amber-700"}>
        {c.collection_status}
      </span>
    )},
    { header: "Remittance", cell: c => (
      <span className={c.remittance_status === "remitted" ? "text-emerald-700 font-semibold" : "text-[#1a1814]/50"}>
        {c.remittance_status}
      </span>
    )},
  ]

  return (
    <div className="space-y-6">
      <PageHeader icon={ReceiptText} title="Postpaid Billing" subtitle="Bill postpaid customers, collect, then remit net of commission." />

      <HelpCallout title="You collect on the operator's behalf" tone="tip">
        Postpaid revenue belongs to the operator — you bill the customer, collect the cash, then <b>remit</b> it
        keeping your commission. The remittance posts your commission to Acct 4040 and clears the
        collections payable (Acct 2110).
      </HelpCallout>

      <ErrorBanner error={operators.error ?? connections.error ?? cycles.error} />

      <Tabs tabs={[
        { id: "bill", label: "Raise bill", content: (
          <Section title="Raise a postpaid bill">
            <ActionForm endpoint="/api/telecom/postpaid/bills" fields={billFields} submitLabel="Raise bill" onSuccess={cycles.refetch} />
          </Section>
        )},
        { id: "collect", label: "Collect", content: (
          <Section title="Collect a postpaid bill">
            <ActionForm endpoint="/api/telecom/postpaid/collect" fields={collectFields} submitLabel="Post collection" onSuccess={cycles.refetch} />
          </Section>
        )},
        { id: "remit", label: "Remit", content: (
          <Section title="Remit to operator (net of commission)">
            <ActionForm endpoint="/api/telecom/postpaid/remit" fields={remitFields} submitLabel="Post remittance" onSuccess={cycles.refetch} />
          </Section>
        )},
        { id: "cycles", label: "Bill cycles", content: (
          <Section title="Postpaid book" action={<button onClick={() => downloadCSV('postpaid-cycles.csv', cycles.items.map(c => ({ Month: c.billing_month, Gross: c.gross_amount, Commission: c.franchise_commission, "Net Remit": c.net_remittance, Collection: c.collection_status, Remittance: c.remittance_status })))} disabled={cycles.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}><DataTable columns={cycleCols} rows={cycles.items} empty="No bill cycles yet." /></Section>
        )},
        { id: "connections", label: "Connections", content: (
          <div className="space-y-4">
            <Section title="Connections" action={<button onClick={() => downloadCSV('postpaid-connections.csv', connections.items.map(c => ({ MSISDN: c.msisdn, Customer: c.customer_name, Plan: c.plan_name, Rental: c.monthly_rental, Activated: c.activation_date })))} disabled={connections.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}><DataTable columns={connCols} rows={connections.items} empty="No connections yet." /></Section>
            <Section title="Add a postpaid connection">
              <ActionForm endpoint="/api/telecom/postpaid/connections" fields={connFields} submitLabel="Add connection" successText={() => "Connection added."} onSuccess={connections.refetch} />
            </Section>
          </div>
        )},
      ]} />
    </div>
  )
}
