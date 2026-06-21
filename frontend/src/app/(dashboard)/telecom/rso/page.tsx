"use client"

import { useEffect, useState } from "react"
import { Network, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { ActionForm, FieldDef, SelectOption } from "@/components/telecom/ActionForm"
import {
  PageHeader, Section, Tabs, DataTable, Column, ErrorBanner, money, useTelecomList,
} from "@/components/telecom/primitives"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface RsoAgent { id: number; name: string; phone: string | null; territory: string | null }
interface RetailOutlet { id: number; rso_id: number; shop_name: string; owner_name: string | null }
interface TrackerAccount { id: number; account_number: string }
interface SimBatch { id: number; batch_number: string; qty_received: number; qty_activated: number }
interface Collection { id: number; collection_date: string; load_portion: string; stock_portion: string; total_deposited: string; variance: string }
interface LedgerRow {
  rso_id: number; name: string; territory: string | null
  load_in_msr: string; load_out_retail: string
  cash_collected_load: string; cash_collected_stock: string; cash_collected_total: string
  open_load_balance: string
}

export default function RsoPage() {
  const { t } = useTranslation()

  const agents = useTelecomList<RsoAgent>("/api/telecom/rso/agents")
  const outlets = useTelecomList<RetailOutlet>("/api/telecom/rso/retail-outlets")
  const accounts = useTelecomList<TrackerAccount>("/api/telecom/tracker-accounts")
  const batches = useTelecomList<SimBatch>("/api/telecom/sim/batches")
  const collections = useTelecomList<Collection>("/api/telecom/rso/collections")

  const [ledger, setLedger] = useState<LedgerRow[]>([])
  useEffect(() => {
    apiFetch<{ items: LedgerRow[] }>("/api/telecom/reports/rso-ledger")
      .then(d => setLedger(d.items)).catch(() => {})
  }, [agents.items.length, collections.items.length])

  const agentOptions: SelectOption[] = agents.items.map(a => ({ value: String(a.id), label: a.territory ? `${a.name} — ${a.territory}` : a.name }))
  const acctOptions: SelectOption[] = accounts.items.map(a => ({ value: String(a.id), label: a.account_number }))
  const outletOptions: SelectOption[] = outlets.items.map(o => ({ value: String(o.id), label: o.shop_name }))
  const batchOptions: SelectOption[] = batches.items.map(b => ({ value: String(b.id), label: `${b.batch_number} (${b.qty_received - b.qty_activated} left)` }))

  const agentFields: FieldDef[] = [
    { kind: "text", name: "name", label: "Agent name", required: true },
    { kind: "text", name: "phone", label: "Phone" },
    { kind: "text", name: "cnic", label: "CNIC" },
    { kind: "text", name: "territory", label: "Territory" },
  ]
  const outletFields: FieldDef[] = [
    { kind: "select", name: "rso_id", label: "RSO agent", required: true, options: agentOptions },
    { kind: "text", name: "shop_name", label: "Shop name", required: true },
    { kind: "text", name: "owner_name", label: "Owner name" },
    { kind: "text", name: "phone", label: "Phone" },
    { kind: "text", name: "address", label: "Address" },
  ]
  const msrFields: FieldDef[] = [
    { kind: "select", name: "tracker_account_id", label: "From tracker (MSR)", required: true, options: acctOptions },
    { kind: "select", name: "rso_id", label: "To RSO", required: true, options: agentOptions },
    { kind: "number", name: "amount", label: "Load amount", required: true, help: "Dr 1212 RSO Load Receivable / Cr 1211 Load Float" },
    { kind: "date", name: "date", label: "Date" },
  ]
  const retailFields: FieldDef[] = [
    { kind: "select", name: "rso_id", label: "From RSO", required: true, options: agentOptions },
    { kind: "select", name: "retail_outlet_id", label: "To retail outlet", required: true, options: outletOptions },
    { kind: "number", name: "amount", label: "Load amount", required: true, help: "Dr 1213 Retail Load Receivable / Cr 1212 RSO Load Receivable" },
    { kind: "date", name: "date", label: "Date" },
  ]
  const collectionFields: FieldDef[] = [
    { kind: "select", name: "rso_id", label: "RSO agent", required: true, options: agentOptions },
    { kind: "number", name: "load_portion", label: "Load portion", required: true, help: "Settles RSO load receivable (1212)" },
    { kind: "number", name: "stock_portion", label: "Stock portion", required: true, help: "Settles RSO stock receivable (1120)" },
    { kind: "number", name: "total_deposited", label: "Total cash banked", required: true, help: "Variance posts to overage/shortage automatically" },
    { kind: "date", name: "date", label: "Date" },
  ]
  const simIssueFields: FieldDef[] = [
    { kind: "select", name: "rso_id", label: "RSO agent", required: true, options: agentOptions },
    { kind: "select", name: "batch_id", label: "SIM batch", required: true, options: batchOptions },
    { kind: "number", name: "qty", label: "Quantity", required: true, step: "1" },
    { kind: "number", name: "retail_price", label: "Retail price (each)", required: true },
    { kind: "date", name: "date", label: "Date" },
  ]

  const agentCols: Column<RsoAgent>[] = [
    { header: "Name", cell: a => a.name },
    { header: "Phone", cell: a => a.phone ?? "—" },
    { header: "Territory", cell: a => a.territory ?? "—" },
  ]
  const outletCols: Column<RetailOutlet>[] = [
    { header: "Shop", cell: o => o.shop_name },
    { header: "Owner", cell: o => o.owner_name ?? "—" },
  ]
  const collCols: Column<Collection>[] = [
    { header: "Date", cell: c => c.collection_date, mono: true },
    { header: "Load", cell: c => money(c.load_portion) },
    { header: "Stock", cell: c => money(c.stock_portion) },
    { header: "Deposited", cell: c => money(c.total_deposited) },
    { header: "Variance", cell: c => money(c.variance) },
  ]
  const ledgerCols: Column<LedgerRow>[] = [
    { header: "RSO", cell: r => r.name },
    { header: "Territory", cell: r => r.territory ?? "—" },
    { header: "Load in", cell: r => money(r.load_in_msr) },
    { header: "Load out", cell: r => money(r.load_out_retail) },
    { header: "Cash (load)", cell: r => money(r.cash_collected_load) },
    { header: "Open balance", cell: r => money(r.open_load_balance) },
  ]

  return (
    <div className="space-y-6">
      <PrintHeader title="RSO Channel" orientation="landscape" />
      <div className="flex items-center justify-between">
        <PageHeader icon={Network} title="RSO Channel" subtitle="Load distribution down MSR → RSO → Retail, and daily settlement." />
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors print:hidden"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      <HelpCallout title="The distribution chain" tone="tip">
        Load flows from your <b>MSR tracker</b> to <b>RSO agents</b>, then to <b>retail outlets</b>. Each hop
        creates a receivable. RSOs deposit cash daily covering the <i>load</i> and <i>stock</i> they sold;
        any gap posts to an overage/shortage account so balances always reconcile.
      </HelpCallout>

      <ErrorBanner error={agents.error ?? accounts.error} />

      <Tabs tabs={[
        { id: "msr", label: "MSR → RSO", content: (
          <Section title="Transfer load to an RSO">
            <ActionForm endpoint="/api/telecom/load-transfers/msr-to-rso" fields={msrFields} submitLabel="Transfer load" onSuccess={() => { accounts.refetch() }} />
          </Section>
        )},
        { id: "retail", label: "RSO → Retail", content: (
          <Section title="Transfer load to a retail outlet">
            <ActionForm endpoint="/api/telecom/load-transfers/rso-to-retail" fields={retailFields} submitLabel="Transfer load" />
          </Section>
        )},
        { id: "collect", label: "Daily collection", content: (
          <div className="space-y-4">
            <Section title="Record daily RSO collection">
              <ActionForm endpoint="/api/telecom/rso/collections" fields={collectionFields} submitLabel="Post collection" onSuccess={collections.refetch} />
            </Section>
            <Section title="Recent collections" action={<button onClick={() => downloadCSV('rso-collections.csv', collections.items.map(c => ({ Date: c.collection_date, Load: c.load_portion, Stock: c.stock_portion, Deposited: c.total_deposited, Variance: c.variance })))} disabled={collections.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}>
              <DataTable columns={collCols} rows={collections.items} empty="No collections yet." />
            </Section>
          </div>
        )},
        { id: "simissue", label: "SIM issue", content: (
          <Section title="Issue SIMs to an RSO">
            <ActionForm endpoint="/api/telecom/rso/sim-issues" fields={simIssueFields} submitLabel="Issue SIMs" onSuccess={batches.refetch} />
          </Section>
        )},
        { id: "ledger", label: "RSO ledger", content: (
          <Section title="Per-RSO position" action={<button onClick={() => downloadCSV('rso-ledger.csv', ledger.map(r => ({ RSO: r.name, Territory: r.territory ?? '', "Load In": r.load_in_msr, "Load Out": r.load_out_retail, "Cash Collected": r.cash_collected_total, "Open Balance": r.open_load_balance })))} disabled={ledger.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}>
            <DataTable columns={ledgerCols} rows={ledger} empty="No RSO activity yet." />
          </Section>
        )},
        { id: "agents", label: "Agents", content: (
          <div className="space-y-4">
            <Section title="RSO agents"><DataTable columns={agentCols} rows={agents.items} empty="No agents yet." /></Section>
            <Section title="Add an RSO agent">
              <ActionForm endpoint="/api/telecom/rso/agents" fields={agentFields} submitLabel="Add agent" successText={() => "Agent added."} onSuccess={agents.refetch} />
            </Section>
          </div>
        )},
        { id: "outlets", label: "Retail outlets", content: (
          <div className="space-y-4">
            <Section title="Retail outlets"><DataTable columns={outletCols} rows={outlets.items} empty="No outlets yet." /></Section>
            <Section title="Add a retail outlet">
              <ActionForm endpoint="/api/telecom/rso/retail-outlets" fields={outletFields} submitLabel="Add outlet" successText={() => "Outlet added."} onSuccess={outlets.refetch} />
            </Section>
          </div>
        )},
      ]} />
    </div>
  )
}
