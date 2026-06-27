"use client"

import { useEffect, useState } from "react"
import { Wallet, Download, Printer } from "lucide-react"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { ActionForm, FieldDef, SelectOption } from "@/components/telecom/ActionForm"
import {
  PageHeader, Section, Tabs, DataTable, Column, ErrorBanner, money, useTelecomList,
} from "@/components/telecom/primitives"
import { apiFetch } from "@/lib/api"
import PrintHeader from "@/components/PrintHeader"
import { downloadCSV } from "@/lib/utils"
import { useTranslation } from "react-i18next"

interface Operator { id: number; name: string; operator_code: string; commission_settlement_cycle: string }
interface TrackerAccount { id: number; operator_id: number; account_number: string; deposit_balance: string; load_balance: string }
interface TrackerTxn {
  id: number; txn_date: string; txn_type: string; amount: string
  load_disbursed: string; commission_earned: string; tracker_reference: string | null
}

interface TrackerStatement {
  tracker_accounts: { id: number; account_number: string; deposit_balance: string; load_balance: string }[]
  transactions: TrackerTxn[]
  gl_deposit_balance: string
  gl_load_balance: string
}

export default function TrackerPage() {
  const { t } = useTranslation()

  const operators = useTelecomList<Operator>("/api/telecom/operators")
  const accounts = useTelecomList<TrackerAccount>("/api/telecom/tracker-accounts")
  const txns = useTelecomList<TrackerTxn>("/api/telecom/tracker/transactions")
  const [stmt, setStmt] = useState<TrackerStatement | null>(null)
  const [stmtErr, setStmtErr] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<TrackerStatement>("/api/telecom/reports/tracker-statement")
      .then(setStmt)
      .catch(e => setStmtErr(e instanceof Error ? e.message : "Failed to load"))
  }, [])

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
      <PrintHeader title="Tracker & Load" orientation="landscape" />
      <div className="flex items-center justify-between">
        <PageHeader icon={Wallet} title="Tracker & Load" subtitle="Operator deposit wallet, load orders, and stock procurement." />
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors print:hidden"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

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
            <Section title="Tracker accounts" action={<button onClick={() => downloadCSV('tracker-accounts.csv', accounts.items.map(a => ({ "Account #": a.account_number, "Deposit Balance": a.deposit_balance, "Load Balance": a.load_balance })))} disabled={accounts.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] rounded-lg text-xs font-bold hover:bg-[var(--bg-page)] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}>
              <DataTable columns={acctCols} rows={accounts.items} empty="No tracker accounts yet." />
            </Section>
            <Section title="Register a tracker account">
              <ActionForm endpoint="/api/telecom/tracker-accounts" fields={acctFields} submitLabel="Add tracker account" successText={() => "Tracker account added."} onSuccess={accounts.refetch} />
            </Section>
          </div>
        )},
        { id: "operators", label: "Operators", content: (
          <div className="space-y-4">
            <Section title="Operators" action={<button onClick={() => downloadCSV('tracker-operators.csv', operators.items.map(o => ({ Name: o.name, Code: o.operator_code, "Settlement Cycle": o.commission_settlement_cycle })))} disabled={operators.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] rounded-lg text-xs font-bold hover:bg-[var(--bg-page)] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}>
              <DataTable columns={opCols} rows={operators.items} empty="No operators yet." />
            </Section>
            <Section title="Add an operator">
              <ActionForm endpoint="/api/telecom/operators" fields={operatorFields} submitLabel="Add operator" successText={() => "Operator added."} onSuccess={operators.refetch} />
            </Section>
          </div>
        )},
        { id: "txns", label: "Transactions", content: (
          <Section title="Tracker transaction ledger" action={<button onClick={() => downloadCSV('tracker-transactions.csv', txns.items.map(t => ({ Date: t.txn_date, Type: t.txn_type, Amount: t.amount, "Load Disbursed": t.load_disbursed, Commission: t.commission_earned, Reference: t.tracker_reference ?? '' })))} disabled={txns.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] rounded-lg text-xs font-bold hover:bg-[var(--bg-page)] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>}>
            <DataTable columns={txnCols} rows={txns.items} empty="No tracker transactions yet." />
          </Section>
        )},
        { id: "statement", label: "Reconciliation", content: (
          <div className="space-y-4">
            {stmtErr && <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{stmtErr}</div>}
            {stmt && (
              <>
                <Section title="GL control totals">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)]">
                        <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60">{t('col.account', 'Account')}</th>
                        <th className="text-right px-4 py-2 font-semibold text-[var(--text-primary)]/60">Sub-ledger sum</th>
                        <th className="text-right px-4 py-2 font-semibold text-[var(--text-primary)]/60">GL balance</th>
                        <th className="text-right px-4 py-2 font-semibold text-[var(--text-primary)]/60">Difference</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        const depositSum = stmt.tracker_accounts.reduce((s, a) => s + parseFloat(a.deposit_balance), 0)
                        const loadSum    = stmt.tracker_accounts.reduce((s, a) => s + parseFloat(a.load_balance), 0)
                        const glDep = parseFloat(stmt.gl_deposit_balance)
                        const glLoad = parseFloat(stmt.gl_load_balance)
                        const depDiff  = depositSum - glDep
                        const loadDiff = loadSum - glLoad
                        return (
                          <>
                            <tr className="border-b border-[var(--border)]">
                              <td className="px-4 py-2 text-[var(--text-primary)]">1210 — Tracker Deposit</td>
                              <td className="px-4 py-2 text-right tabular-nums">{money(depositSum.toFixed(2))}</td>
                              <td className="px-4 py-2 text-right tabular-nums">{money(stmt.gl_deposit_balance)}</td>
                              <td className={`px-4 py-2 text-right tabular-nums font-semibold ${Math.abs(depDiff) > 0.01 ? "text-red-600" : "text-emerald-600"}`}>
                                {Math.abs(depDiff) < 0.01 ? "✓ Balanced" : money(depDiff.toFixed(2))}
                              </td>
                            </tr>
                            <tr>
                              <td className="px-4 py-2 text-[var(--text-primary)]">1211 — Load Float</td>
                              <td className="px-4 py-2 text-right tabular-nums">{money(loadSum.toFixed(2))}</td>
                              <td className="px-4 py-2 text-right tabular-nums">{money(stmt.gl_load_balance)}</td>
                              <td className={`px-4 py-2 text-right tabular-nums font-semibold ${Math.abs(loadDiff) > 0.01 ? "text-red-600" : "text-emerald-600"}`}>
                                {Math.abs(loadDiff) < 0.01 ? "✓ Balanced" : money(loadDiff.toFixed(2))}
                              </td>
                            </tr>
                          </>
                        )
                      })()}
                    </tbody>
                  </table>
                </Section>
                <Section title="Per-account balances">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)]">
                        <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60">Tracker account</th>
                        <th className="text-right px-4 py-2 font-semibold text-[var(--text-primary)]/60">Deposit balance</th>
                        <th className="text-right px-4 py-2 font-semibold text-[var(--text-primary)]/60">Load balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stmt.tracker_accounts.map(a => (
                        <tr key={a.id} className="border-b border-[var(--border)] last:border-0">
                          <td className="px-4 py-2 font-mono text-[var(--text-primary)]/80">{a.account_number}</td>
                          <td className="px-4 py-2 text-right tabular-nums">{money(a.deposit_balance)}</td>
                          <td className="px-4 py-2 text-right tabular-nums">{money(a.load_balance)}</td>
                        </tr>
                      ))}
                      {stmt.tracker_accounts.length === 0 && (
                        <tr><td colSpan={3} className="px-4 py-4 text-center text-[var(--text-primary)]/40 text-sm">No tracker accounts yet.</td></tr>
                      )}
                    </tbody>
                  </table>
                </Section>
              </>
            )}
          </div>
        )},
      ]} />
    </div>
  )
}
