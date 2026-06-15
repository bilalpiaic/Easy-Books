"use client"

import { useEffect, useMemo, useState } from "react"
import { Plus, Trash2, Save, AlertCircle, ScrollText, Info } from "lucide-react"
import { apiFetch } from "@/lib/api"
import {
  VOUCHER_SIDE_FILTERS,
  filterAccountsForSide,
} from "@/lib/voucherTypes"
import { useDp } from "@/context/SettingsContext"
import { useRouter } from "next/navigation"

interface Account {
  id: number
  code: string
  name: string
  type?: string
  postable?: boolean
}

interface AnalyticAccount { id: number; code: string; name: string; type: string }

interface EntryRow {
  account_id: string
  debit: string
  credit: string
}


export default function NewEntryPage() {
  const router = useRouter()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])
  const [analyticAccountId, setAnalyticAccountId] = useState<string>("")
  const [date, setDate] = useState(new Date().toISOString().split("T")[0])
  const [voucherType, setVoucherType] = useState("JV")
  const [description, setDescription] = useState("")
  const [rows, setRows] = useState<EntryRow[]>([
    { account_id: "", debit: "", credit: "" },
    { account_id: "", debit: "", credit: "" },
  ])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    Promise.all([
      apiFetch<{ total: number; items: Account[] }>("/api/accounts?limit=500"),
      apiFetch<AnalyticAccount[] | { items: AnalyticAccount[] }>("/api/analytic-accounts"),
    ])
      .then(([d, an]) => {
        setAccounts(d.items.filter(a => a.postable !== false))
        const items = Array.isArray(an) ? an : ((an as { items: AnalyticAccount[] }).items ?? [])
        setAnalyticAccounts(items)
      })
      .catch(console.error)
  }, [])

  const addRow = () =>
    setRows(r => [...r, { account_id: "", debit: "", credit: "" }])

  const removeRow = (i: number) => {
    if (rows.length <= 2) return
    setRows(r => r.filter((_, idx) => idx !== i))
  }

  const updateRow = (i: number, field: keyof EntryRow, value: string) => {
    setRows(prev => {
      const next = prev.map((r, idx) => {
        if (idx !== i) return r
        const copy: EntryRow = { ...r, [field]: value }
        if (field === "debit"  && value !== "") copy.credit = ""
        if (field === "credit" && value !== "") copy.debit  = ""
        return copy
      })
      return next
    })
  }

  const totalDebit  = rows.reduce((s, r) => s + (parseFloat(r.debit)  || 0), 0)
  const totalCredit = rows.reduce((s, r) => s + (parseFloat(r.credit) || 0), 0)
  const difference  = Math.abs(totalDebit - totalCredit)
  const balanced    = difference < 0.005

  const dp = useDp()

  // ── Per-side account filter helpers (Issue #77 Part 1) ───────────────────
  const hasFilter = !!VOUCHER_SIDE_FILTERS[voucherType]

  // IDs in use on each side (for CV exclusion: can't debit & credit same account)
  const debitAccountIds = useMemo(
    () => new Set(rows.filter(r => parseFloat(r.debit) > 0 && r.account_id).map(r => parseInt(r.account_id))),
    [rows],
  )
  const creditAccountIds = useMemo(
    () => new Set(rows.filter(r => parseFloat(r.credit) > 0 && r.account_id).map(r => parseInt(r.account_id))),
    [rows],
  )

  function rowSide(row: EntryRow): "debit" | "credit" | "none" {
    if (parseFloat(row.debit)  > 0) return "debit"
    if (parseFloat(row.credit) > 0) return "credit"
    return "none"
  }

  /** Filtered accounts + optional empty-state reason for a single row. */
  function accountsForRow(row: EntryRow): {
    debitAccounts: Account[]
    creditAccounts: Account[]
    side: "debit" | "credit" | "none"
    emptyReason?: string
  } {
    if (!hasFilter) {
      return { debitAccounts: accounts, creditAccounts: accounts, side: "none" }
    }
    const side = rowSide(row)
    const isCV = voucherType === "CV"
    if (side === "debit") {
      const exclude = isCV ? creditAccountIds : undefined
      const { accounts: filtered, emptyReason } = filterAccountsForSide(accounts, voucherType, "debit", exclude)
      return { debitAccounts: filtered, creditAccounts: [], side: "debit", emptyReason }
    }
    if (side === "credit") {
      const exclude = isCV ? debitAccountIds : undefined
      const { accounts: filtered, emptyReason } = filterAccountsForSide(accounts, voucherType, "credit", exclude)
      return { debitAccounts: [], creditAccounts: filtered, side: "credit", emptyReason }
    }
    // "none" — row has no amount yet: show both sides as labelled optgroups
    const { accounts: debitFiltered }  = filterAccountsForSide(accounts, voucherType, "debit")
    const { accounts: creditFiltered } = filterAccountsForSide(accounts, voucherType, "credit")
    return { debitAccounts: debitFiltered, creditAccounts: creditFiltered, side: "none" }
  }

  // Collect any empty-reason messages to surface above the form
  const sideWarnings = useMemo(() => {
    if (!hasFilter) return []
    const msgs = new Set<string>()
    for (const row of rows) {
      const { emptyReason } = accountsForRow(row)
      if (emptyReason) msgs.add(emptyReason)
    }
    return [...msgs]
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, accounts, voucherType])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!balanced) {
      setError("Journal entry is not balanced. Debits must equal Credits.")
      return
    }
    setIsSubmitting(true)
    setError("")
    const payload: Record<string, unknown> = {
      date,
      description,
      voucher_type: voucherType,
      analytic_account_id: analyticAccountId ? parseInt(analyticAccountId) : null,
      entries: rows
        .filter(r => r.account_id && (parseFloat(r.debit) > 0 || parseFloat(r.credit) > 0))
        .map(r => ({
          account_id: parseInt(r.account_id),
          debit: parseFloat(r.debit)  || 0,
          credit: parseFloat(r.credit) || 0,
        })),
    }
    try {
      const created = await apiFetch<{ id: number }>("/api/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      router.push(`/journal/${created.id}/print`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <header className="flex items-center gap-3 mb-5">
        <ScrollText className="w-6 h-6 text-[#b8943f] shrink-0" />
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">New Journal Entry</h1>
          <p className="text-xs sm:text-sm text-[#1a1814]/60">Record a manual double-entry transaction</p>
        </div>
      </header>

      <form onSubmit={handleSubmit} className="space-y-4">
        <section className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-[#ede9e2] space-y-4">
          {/* ── Header fields ───────────────────────────────────── */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
                Voucher Type
              </label>
              <select
                value={voucherType}
                onChange={e => setVoucherType(e.target.value)}
                className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm"
              >
                <option value="JV">Journal Voucher</option>
                <option value="CO">Contra</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
                Transaction Date
              </label>
              <input
                type="date"
                value={date}
                onChange={e => setDate(e.target.value)}
                className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
                Description / Memo
              </label>
              <input
                type="text"
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="e.g. Monthly Rent Payment"
                className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm"
                required
              />
            </div>
          </div>

          {/* ── Analytic Account ────────────────────────────────── */}
          {analyticAccounts.length > 0 && (
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
                Analytic Account <span className="font-normal normal-case">(optional)</span>
              </label>
              <select
                value={analyticAccountId}
                onChange={e => setAnalyticAccountId(e.target.value)}
                className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
              >
                <option value="">— none —</option>
                {analyticAccounts.map(a => (
                  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* ── Line items ─────────────────────────────────────── */}
          <div className="mt-2">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">
                Line items
              </span>
              <div className="flex items-center gap-3">
                {hasFilter && (
                  <span className="text-[10px] text-[#b8943f] font-semibold">
                    Account heads filtered for {voucherType}
                  </span>
                )}
                <span className="text-[10px] text-[#1a1814]/40">
                  {rows.length} {rows.length === 1 ? "line" : "lines"}
                </span>
              </div>
            </div>

            {/* ── COA gap warnings ─────────────────────────────── */}
            {sideWarnings.map(msg => (
              <div key={msg} className="flex items-start gap-2 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2 mb-3 text-xs">
                <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                <span>{msg}</span>
              </div>
            ))}

            {/* ── Desktop / wide table (md+) ───────────────────── */}
            <div className="hidden md:block">
              <div className="overflow-x-auto rounded-lg border border-[#ede9e2]">
                <table className="w-full text-sm">
                  <thead className="bg-[#faf6ec]">
                    <tr>
                      <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Account</th>
                      <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-36">Debit</th>
                      <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-36">Credit</th>
                      <th className="w-10"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#ede9e2]">
                    {rows.map((row, idx) => {
                      const { debitAccounts, creditAccounts, side, emptyReason } = accountsForRow(row)
                      // For a determined side, show only that side's accounts
                      // For undetermined rows, show debit + credit in separate optgroups
                      const noAccounts = emptyReason && (debitAccounts.length + creditAccounts.length === 0)
                      return (
                      <tr key={idx}>
                        <td className="px-3 py-2">
                          <select
                            value={row.account_id}
                            onChange={e => updateRow(idx, "account_id", e.target.value)}
                            className={`w-full px-2 py-2 bg-white border rounded-md focus:ring-2 focus:ring-[#b8943f] outline-none text-sm ${noAccounts ? "border-amber-300" : "border-[#ede9e2]"}`}
                            required
                          >
                            <option value="">{noAccounts ? "⚠ No accounts available" : "Select Account"}</option>
                            {side === "none" && hasFilter ? (
                              <>
                                {debitAccounts.length > 0 && (
                                  <optgroup label="── Debit side ──">
                                    {debitAccounts.map(a => (
                                      <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                                    ))}
                                  </optgroup>
                                )}
                                {creditAccounts.length > 0 && (
                                  <optgroup label="── Credit side ──">
                                    {creditAccounts.map(a => (
                                      <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                                    ))}
                                  </optgroup>
                                )}
                              </>
                            ) : (
                              (side === "debit" ? debitAccounts : side === "credit" ? creditAccounts : accounts).map(a => (
                                <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                              ))
                            )}
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            step="0.01"
                            value={row.debit}
                            onChange={e => updateRow(idx, "debit", e.target.value)}
                            placeholder="0.00"
                            className="w-full px-2 py-2 bg-white border border-[#ede9e2] rounded-md focus:ring-2 focus:ring-[#b8943f] outline-none text-right font-mono text-sm"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            step="0.01"
                            value={row.credit}
                            onChange={e => updateRow(idx, "credit", e.target.value)}
                            placeholder="0.00"
                            className="w-full px-2 py-2 bg-white border border-[#ede9e2] rounded-md focus:ring-2 focus:ring-[#b8943f] outline-none text-right font-mono text-sm"
                          />
                        </td>
                        <td className="px-2 py-2 text-center">
                          <button
                            type="button"
                            onClick={() => removeRow(idx)}
                            disabled={rows.length <= 2}
                            className="p-1.5 text-red-400 hover:text-red-600 disabled:opacity-30 disabled:hover:text-red-400 transition-colors"
                            title="Remove line"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    )})}
                  </tbody>
                </table>
              </div>
            </div>

            {/* ── Mobile cards (< md) ──────────────────────────── */}
            <div className="md:hidden space-y-2">
              {rows.map((row, idx) => {
                const { debitAccounts, creditAccounts, side, emptyReason } = accountsForRow(row)
                const noAccounts = emptyReason && (debitAccounts.length + creditAccounts.length === 0)
                return (
                <div
                  key={idx}
                  className="border border-[#ede9e2] rounded-lg p-3 bg-[#faf8f4]"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/55">
                      Line {idx + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeRow(idx)}
                      disabled={rows.length <= 2}
                      className="p-1 text-red-400 hover:text-red-600 disabled:opacity-30 transition-colors"
                      aria-label="Remove line"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <select
                    value={row.account_id}
                    onChange={e => updateRow(idx, "account_id", e.target.value)}
                    className={`w-full px-3 py-2 bg-white border rounded-md focus:ring-2 focus:ring-[#b8943f] outline-none text-sm mb-2 ${noAccounts ? "border-amber-300" : "border-[#ede9e2]"}`}
                    required
                  >
                    <option value="">{noAccounts ? "⚠ No accounts available" : "Select Account"}</option>
                    {side === "none" && hasFilter ? (
                      <>
                        {debitAccounts.length > 0 && (
                          <optgroup label="── Debit side ──">
                            {debitAccounts.map(a => (
                              <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                            ))}
                          </optgroup>
                        )}
                        {creditAccounts.length > 0 && (
                          <optgroup label="── Credit side ──">
                            {creditAccounts.map(a => (
                              <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                            ))}
                          </optgroup>
                        )}
                      </>
                    ) : (
                      (side === "debit" ? debitAccounts : side === "credit" ? creditAccounts : accounts).map(a => (
                        <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                      ))
                    )}
                  </select>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
                        Debit
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        inputMode="decimal"
                        value={row.debit}
                        onChange={e => updateRow(idx, "debit", e.target.value)}
                        placeholder="0.00"
                        className="w-full px-2 py-2 bg-white border border-[#ede9e2] rounded-md focus:ring-2 focus:ring-[#b8943f] outline-none text-right font-mono text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
                        Credit
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        inputMode="decimal"
                        value={row.credit}
                        onChange={e => updateRow(idx, "credit", e.target.value)}
                        placeholder="0.00"
                        className="w-full px-2 py-2 bg-white border border-[#ede9e2] rounded-md focus:ring-2 focus:ring-[#b8943f] outline-none text-right font-mono text-sm"
                      />
                    </div>
                  </div>
                </div>
              )})}
            </div>

            <button
              type="button"
              onClick={addRow}
              className="mt-3 inline-flex items-center gap-1.5 text-[#b8943f] text-sm font-bold hover:underline"
            >
              <Plus className="w-4 h-4" /> Add Line
            </button>
          </div>

          {/* ── Totals bar ──────────────────────────────────────── */}
          <div className="pt-3 border-t border-[#ede9e2]">
            <div className="grid grid-cols-3 gap-2 sm:gap-4 text-right font-mono">
              <div>
                <div className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-0.5">Debit</div>
                <div className="text-sm sm:text-base font-bold text-[#1a1814]">{totalDebit.toFixed(dp)}</div>
              </div>
              <div>
                <div className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-0.5">Credit</div>
                <div className="text-sm sm:text-base font-bold text-[#1a1814]">{totalCredit.toFixed(dp)}</div>
              </div>
              <div className="border-l border-[#ede9e2] pl-2 sm:pl-4">
                <div className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-0.5">Diff</div>
                <div className={`text-sm sm:text-base font-bold ${balanced ? "text-emerald-600" : "text-red-600"}`}>
                  {difference.toFixed(dp)}
                </div>
              </div>
            </div>
          </div>
        </section>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2.5 rounded-lg flex items-start gap-2 text-xs sm:text-sm">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* ── Actions ─────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:justify-end gap-2 sm:gap-3 sticky bottom-0 sm:static bg-[#f6f3ee] sm:bg-transparent py-2 sm:py-0 -mx-3 sm:mx-0 px-3 sm:px-0 border-t sm:border-t-0 border-[#ede9e2]">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-5 py-2.5 bg-white border border-[#ede9e2] rounded-lg font-semibold hover:bg-[#f6f3ee] transition-colors text-sm"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting || !balanced}
            className="px-5 py-2.5 bg-[#1a1814] text-white rounded-lg font-semibold flex items-center justify-center gap-2 hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50 text-sm"
          >
            <Save className="w-4 h-4" />
            {isSubmitting ? "Saving…" : "Post Transaction"}
          </button>
        </div>
      </form>
    </div>
  )
}
