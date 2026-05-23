"use client"

import { useEffect, useState } from "react"
import { Wallet, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface TrackerAccount {
  id: number
  operator_name: string
  operator_code: string
  account_reference: string
  deposit_balance: string
  load_balance: string
  gl_deposit_balance: string
  gl_load_balance: string
  is_active: boolean
}

interface Transaction {
  id: number
  txn_date: string
  txn_type: string
  amount: string
  load_disbursed: string
  commission_earned: string
  tracker_reference: string | null
  notes: string | null
}

const TXN_LABELS: Record<string, string> = {
  deposit:          "Deposit",
  load_order:       "Load Order",
  stock_debit:      "Stock Debit",
  commission_credit:"Commission",
  penalty_debit:    "Penalty",
  adjustment:       "Adjustment",
}

const TXN_COLORS: Record<string, string> = {
  deposit:          "text-emerald-700 bg-emerald-50",
  load_order:       "text-blue-700 bg-blue-50",
  stock_debit:      "text-amber-700 bg-amber-50",
  commission_credit:"text-purple-700 bg-purple-50",
  penalty_debit:    "text-red-700 bg-red-50",
  adjustment:       "text-slate-700 bg-slate-50",
}

function fmt(v: string | number | undefined) {
  if (v === undefined || v === null) return "—"
  const n = parseFloat(String(v))
  if (isNaN(n)) return "—"
  return "PKR " + n.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

interface CreateAccountFormProps { onCreated: () => void }
function CreateAccountForm({ onCreated }: CreateAccountFormProps) {
  const [form, setForm] = useState({ operator_name: "", operator_code: "JAZZ", account_reference: "" })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true); setErr(null)
    try {
      await apiFetch("/api/telecom/tracker-accounts", { method: "POST", body: JSON.stringify(form) })
      onCreated()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to create")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="bg-white border border-[#b8943f]/20 rounded-xl p-5 space-y-3">
      <h3 className="font-semibold text-[#1a1814]">Add Tracker Account</h3>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Operator Name</label>
          <input className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
            value={form.operator_name} onChange={e => setForm(f => ({...f, operator_name: e.target.value}))} required />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Operator Code</label>
          <select className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
            value={form.operator_code} onChange={e => setForm(f => ({...f, operator_code: e.target.value}))}>
            {["JAZZ","TELENOR","ZONG","UFONE"].map(c => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div className="col-span-2">
          <label className="text-xs text-[#1a1814]/60 block mb-1">Tracker Account Reference</label>
          <input className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
            placeholder="Your Tracker ID / franchisee code"
            value={form.account_reference} onChange={e => setForm(f => ({...f, account_reference: e.target.value}))} required />
        </div>
      </div>
      <button type="submit" disabled={saving}
        className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium disabled:opacity-50">
        {saving ? "Saving…" : "Create Account"}
      </button>
    </form>
  )
}

export default function TrackerPage() {
  const [accounts, setAccounts] = useState<TrackerAccount[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [detail, setDetail] = useState<{ transactions: Transaction[] } | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    apiFetch<{ items: TrackerAccount[] }>("/api/telecom/tracker-accounts")
      .then(d => { setAccounts(d.items); if (d.items.length > 0 && !selected) setSelected(d.items[0].id) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (!selected) return
    apiFetch<{ transactions: Transaction[] }>(`/api/telecom/tracker-accounts/${selected}`)
      .then(setDetail)
      .catch(() => {})
  }, [selected])

  const selectedAcc = accounts.find(a => a.id === selected)

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wallet className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Tracker & Load</h1>
            <p className="text-sm text-[#1a1814]/60">Operator Tracker wallet and load order history.</p>
          </div>
        </div>
        <button onClick={() => setShowForm(f => !f)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium">
          <Plus className="w-4 h-4" /> Add Account
        </button>
      </header>

      <HelpCallout title="Tracker deposit → Load order cycle" tone="tip">
        <ol className="list-decimal pl-4 space-y-1 text-sm">
          <li>Deposit cash from your bank into Tracker (Dr 1210 / Cr Bank).</li>
          <li>Place a load order — Tracker debits 100%, MSR SIM receives 103% (the 3% uplift posts as commission income).</li>
          <li>Transfer load from MSR SIM to RSO agents via the <b>Load Transfers</b> page.</li>
        </ol>
      </HelpCallout>

      {showForm && <CreateAccountForm onCreated={() => { setShowForm(false); load() }} />}

      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {loading ? (
        <p className="text-sm text-[#1a1814]/50">Loading…</p>
      ) : accounts.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#b8943f]/30 p-10 text-center">
          <Wallet className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="font-medium text-[#1a1814]">No Tracker accounts yet</p>
          <p className="text-sm text-[#1a1814]/50 mt-1">Click "Add Account" to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Account list */}
          <div className="space-y-2">
            {accounts.map(a => (
              <button key={a.id} onClick={() => setSelected(a.id)}
                className={`w-full text-left rounded-xl border p-4 transition-colors
                  ${a.id === selected ? "border-[#b8943f] bg-[#fdf9f0]" : "border-[#b8943f]/20 bg-white hover:bg-[#f6f3ee]"}`}>
                <p className="font-semibold text-sm text-[#1a1814]">{a.operator_name}</p>
                <p className="text-xs text-[#1a1814]/50">{a.operator_code} · {a.account_reference}</p>
                <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
                  <div>
                    <span className="text-[#1a1814]/40">Deposit </span>
                    <span className="font-mono font-semibold">{fmt(a.gl_deposit_balance)}</span>
                  </div>
                  <div>
                    <span className="text-[#1a1814]/40">Load </span>
                    <span className="font-mono font-semibold">{fmt(a.gl_load_balance)}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Transaction history */}
          <div className="md:col-span-2">
            {selectedAcc && (
              <div className="rounded-xl border border-[#b8943f]/20 bg-white overflow-hidden">
                <div className="px-5 py-3 border-b border-[#b8943f]/10 flex items-center justify-between">
                  <h2 className="font-semibold text-[#1a1814]">
                    {selectedAcc.operator_name} — Transactions
                  </h2>
                </div>
                {!detail?.transactions?.length ? (
                  <p className="text-sm text-[#1a1814]/40 p-5">No transactions yet.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-[#1a1814]/40 uppercase tracking-wide border-b border-[#b8943f]/10">
                        <th className="px-4 py-2 text-left">Date</th>
                        <th className="px-4 py-2 text-left">Type</th>
                        <th className="px-4 py-2 text-right">Amount</th>
                        <th className="px-4 py-2 text-right">Load</th>
                        <th className="px-4 py-2 text-right">Commission</th>
                        <th className="px-4 py-2 text-left">Ref</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.transactions.map(t => (
                        <tr key={t.id} className="border-b border-[#b8943f]/5 hover:bg-[#f6f3ee]">
                          <td className="px-4 py-2 font-mono text-xs">{t.txn_date}</td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${TXN_COLORS[t.txn_type] || "text-slate-700 bg-slate-50"}`}>
                              {TXN_LABELS[t.txn_type] || t.txn_type}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-right font-mono">{fmt(t.amount)}</td>
                          <td className="px-4 py-2 text-right font-mono text-blue-700">
                            {parseFloat(t.load_disbursed) > 0 ? fmt(t.load_disbursed) : "—"}
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-emerald-700">
                            {parseFloat(t.commission_earned) > 0 ? fmt(t.commission_earned) : "—"}
                          </td>
                          <td className="px-4 py-2 text-xs text-[#1a1814]/50">{t.tracker_reference || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
