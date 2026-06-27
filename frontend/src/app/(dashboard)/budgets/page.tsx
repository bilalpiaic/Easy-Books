"use client"

import { useEffect, useRef, useState } from "react"
import { TrendingUp, Plus, Trash2, AlertCircle, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import { EmptyStateGuide } from "@/components/guidance/EmptyStateGuide"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface BudgetRow {
  account_id: number
  account_code: string
  account_name: string
  account_type: string
  month: number
  fiscal_year: number
  budget: number
  actual: number
  variance: number
  variance_pct: number
}

interface Account {
  id: number
  code: string
  name: string
  type: string
  is_group: boolean
  postable: boolean
}

interface BudgetEntry {
  id: number
  account_id: number
  fiscal_year: number
  period_month: number
  amount: string
}

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
const CURRENT_YEAR = new Date().getFullYear()

// Variance positive = under-budget (favourable), negative = over-budget
function varianceTone(v: number, budgeted: number): string {
  if (budgeted === 0) return "text-[var(--text-primary)]/50"
  return v >= 0 ? "text-emerald-700" : "text-red-600"
}

export default function BudgetsPage() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const [year, setYear] = useState(CURRENT_YEAR)
  const [month, setMonth] = useState<number | "">("")
  const [tab, setTab] = useState<"variance" | "set">("variance")

  // Variance tab state
  const [rows, setRows] = useState<BudgetRow[]>([])
  const [loadingV, setLoadingV] = useState(false)
  const [errorV, setErrorV] = useState<string | null>(null)

  // Set-budgets tab state
  const [accounts, setAccounts] = useState<Account[]>([])
  const [entries, setEntries] = useState<BudgetEntry[]>([])
  const [loadingS, setLoadingS] = useState(false)
  const [errorS, setErrorS] = useState<string | null>(null)
  const [addAccId, setAddAccId] = useState("")
  const [saving, setSaving] = useState(false)

  // Fetch variance data whenever year/month changes
  useEffect(() => {
    if (tab !== "variance") return
    setLoadingV(true); setErrorV(null)
    const qs = month !== "" ? `year=${year}&month=${month}` : `year=${year}`
    apiFetch<BudgetRow[]>(`/api/reports/budget-vs-actual?${qs}`)
      .then(setRows)
      .catch(e => setErrorV(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoadingV(false))
  }, [year, month, tab])

  // Fetch accounts + existing budgets for set-budgets tab
  useEffect(() => {
    if (tab !== "set") return
    setLoadingS(true); setErrorS(null)
    Promise.all([
      apiFetch<{ items: Account[] }>("/api/accounts?limit=500"),
      apiFetch<BudgetEntry[]>(`/api/budgets?year=${year}`),
    ])
      .then(([accs, bdgs]) => {
        setAccounts(accs.items.filter(a => a.postable !== false && !a.is_group))
        setEntries(bdgs)
      })
      .catch(e => setErrorS(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoadingS(false))
  }, [year, tab])

  const budgetedAccountIds = [...new Set(entries.map(e => e.account_id))]

  const getEntryAmount = (accountId: number, m: number): string => {
    const e = entries.find(e => e.account_id === accountId && e.period_month === m)
    return e ? e.amount : ""
  }

  const upsertBudget = async (accountId: number, m: number, value: string) => {
    const amount = parseFloat(value)
    if (isNaN(amount) || amount < 0) return
    setSaving(true)
    try {
      await apiFetch("/api/budgets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: accountId, fiscal_year: year, period_month: m, amount }),
      })
      // Refresh entries
      const bdgs = await apiFetch<BudgetEntry[]>(`/api/budgets?year=${year}`)
      setEntries(bdgs)
    } catch (e) {
      setErrorS(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const deleteBudgetsForAccount = async (accountId: number) => {
    const toDelete = entries.filter(e => e.account_id === accountId)
    setSaving(true)
    try {
      await Promise.all(toDelete.map(e => apiFetch(`/api/budgets/${e.id}`, { method: "DELETE" })))
      setEntries(prev => prev.filter(e => e.account_id !== accountId))
    } catch (e) {
      setErrorS(e instanceof Error ? e.message : "Delete failed")
    } finally {
      setSaving(false)
    }
  }

  const addAccount = () => {
    if (!addAccId || budgetedAccountIds.includes(parseInt(addAccId))) return
    setEntries(prev => [...prev, ...MONTHS.map((_, i) => ({
      id: -(Date.now() + i),
      account_id: parseInt(addAccId),
      fiscal_year: year,
      period_month: i + 1,
      amount: "0",
    }))])
    setAddAccId("")
  }

  const YEARS = Array.from({ length: 5 }, (_, i) => CURRENT_YEAR - 2 + i)

  return (
    <div className="space-y-5">
      <PrintHeader title="Budget vs Actual" />
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <TrendingUp className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Budgets</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Set monthly targets and track variance against actual GL activity.</p>
          </div>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          {tab === "variance" && rows.length > 0 && (
            <button
              onClick={() => downloadCSV(`budget-vs-actual.csv`, rows.map(r => ({
                Account: r.account_name, Code: r.account_code, Month: r.month,
                Budget: r.budget, Actual: r.actual, Variance: r.variance, "Variance %": r.variance_pct,
              })))}
              className="p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60"
              title="Export CSV"
            >
              <Download className="w-5 h-5" />
            </button>
          )}
        </div>
      </header>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Tabs */}
        <div className="flex rounded-lg border border-[var(--border)] overflow-hidden text-sm font-semibold">
          {(["variance", "set"] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 capitalize transition-colors ${
                tab === t ? "bg-[var(--text-primary)] text-white" : "bg-white text-[var(--text-primary)]/70 hover:bg-[#faf8f4]"
              }`}
            >
              {t === "variance" ? "Variance Report" : "Set Budgets"}
            </button>
          ))}
        </div>

        {/* Year selector */}
        <select
          value={year}
          onChange={e => setYear(parseInt(e.target.value))}
          className="px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)] bg-white"
        >
          {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
        </select>

        {/* Month selector (variance tab only) */}
        {tab === "variance" && (
          <select
            value={month}
            onChange={e => setMonth(e.target.value === "" ? "" : parseInt(e.target.value))}
            className="px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)] bg-white"
          >
            <option value="">All months (YTD)</option>
            {MONTHS.map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
          </select>
        )}
      </div>

      {/* ── VARIANCE REPORT TAB ─────────────────────────────────────────── */}
      {tab === "variance" && (
        <>
          {errorV && <ErrorBar message={errorV} />}
          {loadingV ? (
            <p className="text-sm text-[var(--text-primary)]/60">Loading…</p>
          ) : rows.length === 0 ? (
            <EmptyStateGuide
              title="No budgets set for this period"
              description="Switch to the 'Set Budgets' tab to add monthly targets per account."
              steps={[
                "Go to Set Budgets → add an account",
                "Enter monthly amounts across the year",
                "Return here to see actual vs. budget variance",
              ]}
            />
          ) : (
            <div className="bg-white border border-[var(--border)] rounded-2xl overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[var(--bg-page)] text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
                  <tr>
                    <th className="text-left px-4 py-2">{t('col.account', 'Account')}</th>
                    <th className="text-left px-4 py-2 w-24">Type</th>
                    {month !== "" && <th className="text-left px-4 py-2 w-16">Month</th>}
                    <th className="text-right px-4 py-2 w-32">Budget</th>
                    <th className="text-right px-4 py-2 w-32">Actual</th>
                    <th className="text-right px-4 py-2 w-32">Variance</th>
                    <th className="text-right px-4 py-2 w-24">Var %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {rows.map((r, i) => (
                    <tr key={i} className="hover:bg-[#faf8f4] transition-colors">
                      <td className="px-4 py-2">
                        <span className="font-mono text-xs text-[var(--primary)] mr-2">{r.account_code}</span>
                        {r.account_name}
                      </td>
                      <td className="px-4 py-2 text-[var(--text-primary)]/60 text-xs">{r.account_type}</td>
                      {month !== "" && <td className="px-4 py-2 text-xs">{MONTHS[r.month - 1]}</td>}
                      <td className="px-4 py-2 text-right font-mono">{fmt(r.budget)}</td>
                      <td className="px-4 py-2 text-right font-mono">{fmt(r.actual)}</td>
                      <td className={`px-4 py-2 text-right font-mono font-semibold ${varianceTone(r.variance, r.budget)}`}>
                        {r.variance >= 0 ? "+" : ""}{fmt(r.variance)}
                      </td>
                      <td className={`px-4 py-2 text-right font-mono text-xs ${varianceTone(r.variance, r.budget)}`}>
                        {r.budget !== 0 ? `${r.variance_pct >= 0 ? "+" : ""}${r.variance_pct.toFixed(1)}%` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="border-t-2 border-[var(--border)] bg-[#faf8f4] text-xs font-bold">
                  <tr>
                    <td colSpan={month !== "" ? 3 : 2} className="px-4 py-2 uppercase tracking-wide text-[var(--text-primary)]/55">{t('col.total', 'Total')}</td>
                    <td className="px-4 py-2 text-right font-mono">{fmt(rows.reduce((s, r) => s + r.budget, 0))}</td>
                    <td className="px-4 py-2 text-right font-mono">{fmt(rows.reduce((s, r) => s + r.actual, 0))}</td>
                    <td className="px-4 py-2 text-right font-mono">
                      {(() => {
                        const v = rows.reduce((s, r) => s + r.variance, 0)
                        return <span className={v >= 0 ? "text-emerald-700" : "text-red-600"}>{v >= 0 ? "+" : ""}{fmt(v)}</span>
                      })()}
                    </td>
                    <td className="px-4 py-2" />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── SET BUDGETS TAB ─────────────────────────────────────────────── */}
      {tab === "set" && (
        <>
          {errorS && <ErrorBar message={errorS} />}

          {/* Add account row */}
          <div className="flex gap-2 items-center">
            <select
              value={addAccId}
              onChange={e => setAddAccId(e.target.value)}
              className="flex-1 px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)] bg-white max-w-sm"
            >
              <option value="">— Add account to budget —</option>
              {accounts
                .filter(a => !budgetedAccountIds.includes(a.id))
                .map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
            </select>
            <button
              onClick={addAccount}
              disabled={!addAccId}
              className="flex items-center gap-1.5 px-3 py-2 bg-[var(--text-primary)] text-white rounded-lg text-sm font-semibold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-40"
            >
              <Plus className="w-4 h-4" />
              Add
            </button>
          </div>

          {loadingS ? (
            <p className="text-sm text-[var(--text-primary)]/60">Loading…</p>
          ) : budgetedAccountIds.length === 0 ? (
            <EmptyStateGuide
              title="No accounts budgeted yet"
              description="Select an account above and click Add to start entering monthly targets."
              steps={[
                "Choose a leaf account (expense or revenue) from the dropdown",
                "Enter monthly amounts — click any cell to edit",
                "Switch to Variance Report to compare against actuals",
              ]}
            />
          ) : (
            <div className="bg-white border border-[var(--border)] rounded-2xl overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-[var(--bg-page)] text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
                  <tr>
                    <th className="text-left px-3 py-2 sticky left-0 bg-[var(--bg-page)] min-w-[180px]">{t('col.account', 'Account')}</th>
                    {MONTHS.map(m => <th key={m} className="text-right px-2 py-2 w-20">{m}</th>)}
                    <th className="text-right px-3 py-2 w-28">Annual Total</th>
                    <th className="w-8 px-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {budgetedAccountIds.map(accId => {
                    const acc = accounts.find(a => a.id === accId)
                    const annual = MONTHS.reduce((s, _, i) => {
                      const v = parseFloat(getEntryAmount(accId, i + 1)) || 0
                      return s + v
                    }, 0)
                    return (
                      <tr key={accId} className="hover:bg-[#faf8f4] transition-colors">
                        <td className="px-3 py-2 sticky left-0 bg-inherit">
                          <div className="font-mono text-[var(--primary)] text-[10px]">{acc?.code ?? `#${accId}`}</div>
                          <div className="text-[var(--text-primary)] leading-tight">{acc?.name ?? "Unknown"}</div>
                        </td>
                        {MONTHS.map((_, mi) => (
                          <td key={mi} className="px-1 py-1">
                            <InlineAmountCell
                              value={getEntryAmount(accId, mi + 1)}
                              onSave={val => upsertBudget(accId, mi + 1, val)}
                              disabled={saving}
                            />
                          </td>
                        ))}
                        <td className="px-3 py-2 text-right font-mono font-semibold text-[var(--text-primary)]">
                          {annual > 0 ? fmt(annual) : <span className="text-[var(--text-primary)]/30">—</span>}
                        </td>
                        <td className="px-2 py-2 text-center">
                          <button
                            onClick={() => deleteBudgetsForAccount(accId)}
                            disabled={saving}
                            title="Remove this account from budget"
                            className="p-1 text-red-400 hover:text-red-600 disabled:opacity-30 transition-colors"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          {saving && <p className="text-xs text-[var(--text-primary)]/50">Saving…</p>}
        </>
      )}
    </div>
  )
}

function ErrorBar({ message }: { message: string }) {
  return (
    <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm flex items-start gap-2">
      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
      {message}
    </div>
  )
}

function InlineAmountCell({
  value,
  onSave,
  disabled,
}: {
  value: string
  onSave: (v: string) => void
  disabled: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setDraft(value) }, [value])
  useEffect(() => { if (editing) inputRef.current?.select() }, [editing])

  const commit = () => {
    setEditing(false)
    const n = parseFloat(draft)
    if (!isNaN(n) && draft !== value) onSave(String(n))
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="number"
        min="0"
        step="any"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => { if (e.key === "Enter") commit(); if (e.key === "Escape") setEditing(false) }}
        disabled={disabled}
        className="w-full px-1.5 py-1 border border-[var(--primary)] rounded text-right font-mono text-xs outline-none bg-[var(--bg-page)]"
      />
    )
  }

  const n = parseFloat(value)
  return (
    <button
      onClick={() => { setDraft(value || "0"); setEditing(true) }}
      className={`w-full text-right px-1.5 py-1 rounded hover:bg-[var(--bg-page)] font-mono text-xs transition-colors ${
        n > 0 ? "text-[var(--text-primary)]" : "text-[var(--text-primary)]/25"
      }`}
    >
      {n > 0 ? n.toLocaleString() : "—"}
    </button>
  )
}
