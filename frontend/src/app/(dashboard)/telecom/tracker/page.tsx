"use client"

import { Wallet } from "lucide-react"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { ActionForm, FieldDef, SelectOption } from "@/components/telecom/ActionForm"
import {
  PageHeader, Section, Tabs, DataTable, Column, ErrorBanner, money, useTelecomList,
} from "@/components/telecom/primitives"

interface Operator { id: number; name: string; operator_code: string; commission_settlement_cycle: string }
interface TrackerAccount { id: number; operator_id: number; account_number: string; deposit_balance: string; load_balance: string }
interface TrackerTxn {
  id: number; txn_date: string; txn_type: string; amount: string
  load_disbursed: string; commission_earned: string; tracker_reference: string | null
}

export default function TrackerPage() {
  const operators = useTelecomList<Operator>("/api/telecom/operators")
  const accounts = useTelecomList<TrackerAccount>("/api/telecom/tracker-accounts")
  const txns = useTelecomList<TrackerTxn>("/api/telecom/tracker/transactions")

  const opOptions: SelectOption[] = operators.items.map(o => ({ value: String(o.id), label: `${o.name} (${o.operator_code})` }))
  const acctOptions: SelectOption[] = accounts.items.map(a => ({ value: String(a.id), label: a.account_number }))

  const refreshAccounts = () => { accounts.refetch(); txns.refetch() }

  const operatorFields: FieldDef[] = [
    { kind: "text", name: "name", label: "Operator name", required: true, placeholder: "Jazz" },
    { kind: "text", name: "operator_code", label: "Operator code", required: true, placeholder: "JAZZ" },
    { kind: "text", name: "contact_person", label: "Contact person" },
    { kind: "text", name: "contact_phone", label: "Contact phone" },
    { kind: "select", name: "commission_settlement_cycle", label: "Settlement cycle", default: "monthly",
      options: [{ value: "monthly", label: "Monthly" }, { value: "weekly", label: "Weekly" }, { value: "fortnightly", label: "Fortnightly" }] },
  ]

  const acctFields: FieldDef[] = [
    { kind: "select", name: "operator_id", label: "Operator", required: true, options: opOptions },
    { kind: "text", name: "account_number", label: "Tracker / MSR number", required: true, placeholder: "3001234567" },
  ]

  const depositFields: FieldDef[] = [
    { kind: "select", name: "tracker_account_id", label: "Tracker account", required: true, options: acctOptions },
    { kind: "number", name: "amount", label: "Amount deposited", required: true, help: "Dr 1210 Tracker Deposit / Cr Bank" },
    { kind: "date", name: "date", label: "Date" },
    { kind: "text", name: "reference", label: "Reference / slip #" },
  ]

  const loadFields: FieldDef[] = [
    { kind: "select", name: "tracker_account_id", label: "Tracker account", required: true, options: acctOptions },
    { kind: "number", name: "cash_debit", label: "Cash from deposit", required: true, help: "Deduction from Tracker Deposit balance" },
    { kind: "number", name: "uplift_pct", label: "Uplift %", default: "3.00", help: "Commission uplift earned at disbursement" },
    { kind: "date", name: "date", label: "Date" },
    { kind: "text", name: "reference", label: "Reference" },
  ]

  const stockFields: FieldDef[] = [
    { kind: "select", name: "tracker_account_id", label: "Tracker account", required: true, options: acctOptions },
    { kind: "select", name: "inventory_account_code", label: "Inventory type", default: "1200",
      options: [{ value: "1200", label: "SIM cards (1200)" }, { value: "1204", label: "IMSI (1204)" }, { value: "1201", label: "Scratch / PIN (1201)" }] },
    { kind: "number", name: "qty", label: "Quantity", required: true, step: "1" },
    { kind: "number", name: "unit_cost", label: "Unit cost", required: true },
    { kind: "text", name: "batch_number", label: "Batch number" },
    { kind: "date", name: "date", label: "Date" },
  ]

  const acctCols: Column<TrackerAccount>[] = [
    { header: "Account #", cell: a => a.account_number, mono: true },
    { header: "Deposit balance", cell: a => money(a.deposit_balance) },
    { header: "Load balance", cell: a => money(a.load_balance) },
  ]

  const opCols: Column<Operator>[] = [
    { header: "Code", cell: o => o.operator_code, mono: true },
    { header: "Name", cell: o => o.name },
    { header: "Cycle", cell: o => o.commission_settlement_cycle },
  ]

  const txnCols: Column<TrackerTxn>[] = [
    { header: "Date", cell: t => t.txn_date, mono: true },
    { header: "Type", cell: t => t.txn_type },
    { header: "Amount", cell: t => money(t.amount) },
    { header: "Load disbursed", cell: t => money(t.load_disbursed) },
    { header: "Commission", cell: t => money(t.commission_earned) },
    { header: "Reference", cell: t => t.tracker_reference ?? "—" },
  ]

  return (
    <div className="space-y-6">
      <PageHeader icon={Wallet} title="Tracker & Load" subtitle="Operator deposit wallet, load orders, and stock procurement." />

      <HelpCallout title="The 3% load uplift, explained" tone="tip">
        A load order converts your Tracker deposit into spendable load float. The operator credits you
        <b> 3% more face value</b> than the cash you spend, booked as commission revenue right away:
        <pre className="mt-2 bg-white/50 rounded px-2 py-1 text-[11px] leading-relaxed">
{`Dr 1211 Load Float Asset     cash × 1.03
   Cr 1210 Tracker Deposit       cash
   Cr 4020 Load Uplift Commission cash × 0.03`}
        </pre>
      </HelpCallout>

      <ErrorBanner error={operators.error ?? accounts.error ?? txns.error} />

      <Tabs tabs={[
        { id: "deposit", label: "Deposit", content: (
          <Section title="Top up tracker deposit">
            <ActionForm endpoint="/api/telecom/tracker/deposits" fields={depositFields} submitLabel="Post deposit" onSuccess={refreshAccounts} />
          </Section>
        )},
        { id: "load", label: "Load order", content: (
          <Section title="Place load order (3% uplift)">
            <ActionForm endpoint="/api/telecom/tracker/load-orders" fields={loadFields} submitLabel="Post load order" onSuccess={refreshAccounts} />
          </Section>
        )},
        { id: "stock", label: "Stock debit", content: (
          <Section title="Procure stock via tracker">
            <ActionForm endpoint="/api/telecom/tracker/stock-debits" fields={stockFields} submitLabel="Post stock debit" onSuccess={refreshAccounts} />
          </Section>
        )},
        { id: "accounts", label: "Accounts", content: (
          <div className="space-y-4">
            <Section title="Tracker accounts">
              <DataTable columns={acctCols} rows={accounts.items} empty="No tracker accounts yet." />
            </Section>
            <Section title="Register a tracker account">
              <ActionForm endpoint="/api/telecom/tracker-accounts" fields={acctFields} submitLabel="Add tracker account" successText={() => "Tracker account added."} onSuccess={accounts.refetch} />
            </Section>
          </div>
        )},
        { id: "operators", label: "Operators", content: (
          <div className="space-y-4">
            <Section title="Operators">
              <DataTable columns={opCols} rows={operators.items} empty="No operators yet." />
            </Section>
            <Section title="Add an operator">
              <ActionForm endpoint="/api/telecom/operators" fields={operatorFields} submitLabel="Add operator" successText={() => "Operator added."} onSuccess={operators.refetch} />
            </Section>
          </div>
        )},
        { id: "txns", label: "Transactions", content: (
          <Section title="Tracker transaction ledger">
            <DataTable columns={txnCols} rows={txns.items} empty="No tracker transactions yet." />
          </Section>
        )},
      ]} />
    </div>
  )
}
