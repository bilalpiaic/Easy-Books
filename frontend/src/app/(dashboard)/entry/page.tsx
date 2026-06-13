"use client"

import { useEffect, useState } from "react"
import { Plus, Trash2, Save, AlertCircle, ScrollText } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { VOUCHER_TYPES, VOUCHER_ACCOUNT_HINTS, AccountType } from "@/lib/voucherTypes"
import { useDp } from "@/context/SettingsContext"
import { useRouter } from "next/navigation"

interface Account {
  id: number
  code: string
  name: string
  type?: string
  postable?: boolean
}

interface EntryRow {
  account_id: string
  debit: string
  credit: string
}

export default function NewEntryPage() {
  const router = useRouter()
  const [accounts, setAccounts] = useState<Account[]>([])
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
    apiFetch<{ total: number; items: Account[] }>("/api/accounts?limit=500")
      .then(d => setAccounts(d.items.filter(a => a.postable !== false)))
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
  const hintTypes = VOUCHER_ACCOUNT_HINTS[voucherType] ?? []
  const hintedAccounts = hintTypes.length > 0
    ? accounts.filter(a => hintTypes.includes(a.type as AccountType))
    : []
  const otherAccounts = hintTypes.length > 0
    ? accounts.filter(a => !hintTypes.includes(a.type as AccountType))
    : accounts

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!balanced) {
      setError("Journal entry is not balanced. Debits must equal Credits.")
      return
    }
    setIsSubmitting(true)
    setError("")
    const payload = {
      date,
      description,
      voucher_type: voucherType,
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
                {Object.entries(VOUCHER_TYPES).map(([code, label]) => (
                  <option key={code} value={code}>{code} — {label}</option>
                ))}
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

          {/* ── Line items ─────────────────────────────────────── */}
          <div className="mt-2">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">
                Line items
              </span>
              <span className="text-[10px] text-[#1a1814]/40">
                {rows.length} {rows.length === 1 ? "line" : "lines"}
              </span>
            </div>

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
                    {rows.map((row, idx) => (
                      <tr key={idx}>
                        <td className="px-3 py-2">
                          <select
                            value={row.account_id}
                            onChange={e => updateRow(idx, "account_id", e.target.value)}
                            className="w-full px-2 py-2 bg-white border border-[#ede9e2] rounded-md focus:ring-2 focus:ring-[#b8943f] outline-none text-sm"
                            required
                          >
                            <option value="">Select Account</option>
                            {hintedAccounts.map(a => (
                              <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                            ))}
                            {hintedAccounts.length > 0 && otherAccounts.length > 0 && (
                              <option disabled>── All accounts ──</option>
                            )}
                            {otherAccounts.map(a => (
                              <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                            ))}
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
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* ── Mobile cards (< md) ──────────────────────────── */}
            <div className="md:hidden space-y-2">
              {rows.map((row, idx) => (
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
                    className="w-full px-3 py-2 bg-white border border-[#ede9e2] rounded-md focus:ring-2 focus:ring-[#b8943f] outline-none text-sm mb-2"
                    required
                  >
                    <option value="">Select Account</option>
                    {hintedAccounts.map(a => (
                      <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                    ))}
                    {hintedAccounts.length > 0 && otherAccounts.length > 0 && (
                      <option disabled>── All accounts ──</option>
                    )}
                    {otherAccounts.map(a => (
                      <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                    ))}
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
              ))}
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
