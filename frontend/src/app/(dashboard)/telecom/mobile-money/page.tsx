"use client"

import { useEffect, useState } from "react"
import { Banknote, Download, Printer } from "lucide-react"
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
interface MmAccount { id: number; account_number: string; account_type: string; current_float_balance: string }
interface MmTxn { id: number; txn_date: string; txn_type: string; amount: string; customer_reference: string | null }
interface FloatStatement {
  gl_balance_1214: string; system_balance_total: string
  items: { id: number; account_number: string; account_type: string; system_balance: string }[]
}

export default function MobileMoneyPage() {
  const { t } = useTranslation()

  const operators = useTelecomList<Operator>("/api/telecom/operators")
  const mmAccounts = useTelecomList<MmAccount>("/api/telecom/mm/accounts")
  const txns = useTelecomList<MmTxn>("/api/telecom/mm/transactions")

  const [stmt, setStmt] = useState<FloatStatement | null>(null)
  const loadStmt = () => apiFetch<FloatStatement>("/api/telecom/reports/float-statement").then(setStmt).catch(() => {})
  useEffect(() => { loadStmt() }, [mmAccounts.items.length, txns.items.length])

  const opOptions: SelectOption[] = operators.items.map(o => ({ value: String(o.id), label: `${o.name} (${o.operator_code})` }))
  const mmOptions: SelectOption[] = mmAccounts.items.map(a => ({ value: String(a.id), label: `${a.account_number} (${a.account_type})` }))

  const accountFields: FieldDef[] = [
    { kind: "select", name: "operator_id", label: "Operator", required: true, options: opOptions },
    { kind: "text", name: "account_number", label: "Account number", required: true },
    { kind: "select", name: "account_type", label: "Wallet type", default: "jazzcash",
      options: [
        { value: "jazzcash", label: "JazzCash" },
        { value: "easypaisa", label: "Easypaisa" },
        { value: "other", label: "Other" },
      ] },
  ]
  const txnFields = (extra: FieldDef[] = []): FieldDef[] => [
    { kind: "select", name: "mm_account_id", label: "MM account", required: true, options: mmOptions },
    { kind: "number", name: "amount", label: "Amount", required: true },
    { kind: "text", name: "customer_reference", label: "Customer reference" },
    { kind: "date", name: "date", label: "Date" },
    ...extra,
  ]
  const topUpFields: FieldDef[] = [
    { kind: "select", name: "mm_account_id", label: "MM account", required: true, options: mmOptions },
    { kind: "number", name: "amount", label: "Float top-up amount", required: true, help: "Dr 1214 MM Float Asset / Cr Cash" },
    { kind: "date", name: "date", label: "Date" },
  ]
  const commissionFields: FieldDef[] = [
    { kind: "select", name: "mm_account_id", label: "MM account", required: true, options: mmOptions },
    { kind: "number", name: "amount", label: "Commission amount", required: true, help: "Cr 4022 Mobile Money Commission" },
    { kind: "select", name: "credit_to", label: "Credit to", default: "float",
      options: [{ value: "float", label: "MM float asset" }, { value: "bank", label: "Bank" }] },
    { kind: "date", name: "date", label: "Date" },
  ]
  const reconcileFields: FieldDef[] = [
    { kind: "select", name: "mm_account_id", label: "MM account", required: true, options: mmOptions },
    { kind: "number", name: "statement_balance", label: "Wallet statement balance", required: true, help: "Difference posts to overage/shortage" },
    { kind: "date", name: "date", label: "Date" },
  ]

  const txnCols: Column<MmTxn>[] = [
    { header: "Date", cell: t => t.txn_date, mono: true },
    { header: "Type", cell: t => t.txn_type },
    { header: "Amount", cell: t => money(t.amount) },
    { header: "Reference", cell: t => t.customer_reference ?? "—" },
  ]

  return (
    <div className="space-y-6">
      <PrintHeader title="Mobile Money" orientation="landscape" />
      <div className="flex items-center justify-between">
        <PageHeader icon={Banknote} title="Mobile Money" subtitle="Agency float for JazzCash / Easypaisa deposits, withdrawals and commission." />
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors print:hidden"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      <HelpCallout title="Float moves opposite to cash" tone="tip">
        Your <b>float</b> (Acct 1214) is e-money held with the operator. A <b>customer deposit</b> hands you cash and
        <i> reduces</i> float (you send e-money out); a <b>withdrawal</b> pays out cash and <i>increases</i> float.
        Reconcile the wallet statement regularly so GL float matches the app balance.
      </HelpCallout>

      <ErrorBanner error={operators.error ?? mmAccounts.error} />

      {stmt && (
        <Section title="Float reconciliation" action={
          <button onClick={loadStmt} className="text-xs text-[#b8943f] hover:underline">Refresh</button>
        }>
          <div className="grid grid-cols-2 gap-3">
            <Tile icon={Banknote} label="GL float (1214)" value={money(stmt.gl_balance_1214)} />
            <Tile icon={Banknote} label="System float total" value={money(stmt.system_balance_total)} />
          </div>
        </Section>
      )}

      <Tabs tabs={[
        { id: "deposit", label: "Deposit", content: (
          <Section title="Customer deposit (cash in)">
            <ActionForm endpoint="/api/telecom/mm/deposit" fields={txnFields()} submitLabel="Post deposit" onSuccess={() => { txns.refetch(); mmAccounts.refetch() }} />
          </Section>
        )},
        { id: "withdrawal", label: "Withdrawal", content: (
          <Section title="Customer withdrawal (cash out)">
            <ActionForm endpoint="/api/telecom/mm/withdrawal" fields={txnFields()} submitLabel="Post withdrawal" onSuccess={() => { txns.refetch(); mmAccounts.refetch() }} />
          </Section>
        )},
        { id: "topup", label: "Float top-up", content: (
          <Section title="Top up agency float">
            <ActionForm endpoint="/api/telecom/mm/top-up" fields={topUpFields} submitLabel="Top up float" onSuccess={() => { txns.refetch(); mmAccounts.refetch() }} />
          </Section>
        )},
        { id: "commission", label: "Commission", content: (
          <Section title="Record mobile-money commission">
            <ActionForm endpoint="/api/telecom/mm/commission" fields={commissionFields} submitLabel="Post commission" onSuccess={() => { txns.refetch(); mmAccounts.refetch() }} />
          </Section>
        )},
        { id: "reconcile", label: "Reconcile", content: (
          <Section title="Reconcile wallet statement">
            <ActionForm endpoint="/api/telecom/mm/reconcile" fields={reconcileFields} submitLabel="Reconcile" successText={r => {
              const x = r as { transaction?: { jv_number?: string } | null }
              return x?.transaction?.jv_number ? `Adjusted — JV ${x.transaction.jv_number}` : "Already balanced — no entry needed."
            }} onSuccess={loadStmt} />
          </Section>
        )},
        { id: "accounts", label: "Accounts", content: (
          <div className="space-y-4">
            <Section title="Mobile money accounts">
              <DataTable
                columns={[
                  { header: "Account", cell: (a: MmAccount) => a.account_number, mono: true },
                  { header: "Type", cell: (a: MmAccount) => a.account_type },
                  { header: "System float", cell: (a: MmAccount) => money(a.current_float_balance) },
                ]}
                rows={mmAccounts.items}
                empty="No mobile money accounts yet."
              />
            </Section>
            <Section title="Add an MM account">
              <ActionForm endpoint="/api/telecom/mm/accounts" fields={accountFields} submitLabel="Add account" successText={() => "Account added."} onSuccess={mmAccounts.refetch} />
            </Section>
          </div>
        )},
        { id: "txns", label: "Transactions", content: (
          <Section title="Mobile money transactions" action={<button onClick={() => downloadCSV('mm-transactions.csv', txns.items.map(t => ({ Date: t.txn_date, Type: t.txn_type, Amount: t.amount, Reference: t.customer_reference ?? '' })))} disabled={txns.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}>
            <DataTable columns={txnCols} rows={txns.items} empty="No transactions yet." />
          </Section>
        )},
      ]} />
    </div>
  )
}
