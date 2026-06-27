"use client"

import { useCallback, useEffect, useState } from "react"
import { Percent, Plus, Trash2, RefreshCw, CheckCircle, BookOpen, ChevronDown, ChevronRight, AlertCircle, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useDp } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

// ── Types ──────────────────────────────────────────────────────────────────

interface StaffUser {
  id: number
  name: string
  email: string
}

interface Plan {
  id: number
  user_id: number
  user_name: string
  rate: number
  sales_target: number | null
  recovery_target: number | null
  target_bonus: number | null
  effective_from: string
  effective_to: string | null
  active: boolean
}

interface LedgerEntry {
  id: number
  user_id: number
  user_name: string
  period: string
  total_invoiced: number
  total_recovered: number
  rate: number
  commission_amount: number
  bonus_amount: number
  total_payable: number
  status: "draft" | "approved" | "posted"
  transaction_id: number | null
}

interface Account {
  id: number
  code: string
  name: string
  type?: string
}

// ── Helpers ────────────────────────────────────────────────────────────────

const STATUS_BADGE: Record<string, string> = {
  draft:    "bg-gray-100 text-gray-700",
  approved: "bg-blue-100 text-blue-700",
  posted:   "bg-emerald-100 text-emerald-700",
}

function thisMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function CommissionsPage() {
  const { t } = useTranslation()

  const dp = useDp()
  const [tab, setTab] = useState<"plans" | "ledger">("ledger")
  const [plans, setPlans] = useState<Plan[]>([])
  const [ledger, setLedger] = useState<LedgerEntry[]>([])
  const [staff, setStaff] = useState<StaffUser[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [period, setPeriod] = useState(thisMonth())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [info, setInfo] = useState("")

  // Plan form state
  const [showPlanForm, setShowPlanForm] = useState(false)
  const [planForm, setPlanForm] = useState({
    user_id: "", rate: "", sales_target: "", recovery_target: "",
    target_bonus: "", effective_from: new Date().toISOString().split("T")[0], effective_to: "",
  })

  // Post form state (per entry)
  const [postingId, setPostingId] = useState<number | null>(null)
  const [postForm, setPostForm] = useState({ expense_account_id: "", payable_account_id: "", date: new Date().toISOString().split("T")[0] })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [p, s, a, l] = await Promise.all([
        apiFetch<Plan[]>("/api/commissions/plans"),
        apiFetch<StaffUser[]>("/api/commissions/staff"),
        apiFetch<{ items: Account[] }>("/api/accounts?limit=500"),
        apiFetch<LedgerEntry[]>(`/api/commissions/ledger?period=${period}`),
      ])
      setPlans(p)
      setStaff(s)
      setAccounts(a.items.filter(ac => ac.type === "Expense" || ac.type === "Liability"))
      setLedger(l)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed")
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => { load() }, [load])

  // ── Plan actions ─────────────────────────────────────────────────────────

  const createPlan = async () => {
    if (!planForm.user_id || !planForm.rate || !planForm.effective_from) {
      setError("User, rate, and effective from are required"); return
    }
    setError("")
    try {
      await apiFetch("/api/commissions/plans", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: parseInt(planForm.user_id),
          rate: parseFloat(planForm.rate),
          sales_target: planForm.sales_target ? parseFloat(planForm.sales_target) : null,
          recovery_target: planForm.recovery_target ? parseFloat(planForm.recovery_target) : null,
          target_bonus: planForm.target_bonus ? parseFloat(planForm.target_bonus) : null,
          effective_from: planForm.effective_from,
          effective_to: planForm.effective_to || null,
        }),
      })
      setShowPlanForm(false)
      setPlanForm({ user_id: "", rate: "", sales_target: "", recovery_target: "", target_bonus: "", effective_from: new Date().toISOString().split("T")[0], effective_to: "" })
      load()
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to create plan") }
  }

  const deactivatePlan = async (id: number) => {
    if (!confirm("Deactivate this commission plan?")) return
    try {
      await apiFetch(`/api/commissions/plans/${id}`, { method: "DELETE" })
      load()
    } catch (e) { setError(e instanceof Error ? e.message : "Failed") }
  }

  // ── Ledger actions ───────────────────────────────────────────────────────

  const compute = async () => {
    setError(""); setInfo("")
    try {
      const r = await apiFetch<{ created: number; updated: number; period: string }>("/api/commissions/compute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period }),
      })
      setInfo(`Computed ${period}: ${r.created} new, ${r.updated} updated`)
      load()
    } catch (e) { setError(e instanceof Error ? e.message : "Compute failed") }
  }

  const approve = async (id: number) => {
    try {
      await apiFetch(`/api/commissions/ledger/${id}/approve`, { method: "POST" })
      load()
    } catch (e) { setError(e instanceof Error ? e.message : "Approve failed") }
  }

  const postToGL = async (id: number) => {
    if (!postForm.expense_account_id || !postForm.payable_account_id) {
      setError("Select both accounts to post"); return
    }
    setError("")
    try {
      const r = await apiFetch<{ jv_number: string }>(`/api/commissions/ledger/${id}/post`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expense_account_id: parseInt(postForm.expense_account_id),
          payable_account_id: parseInt(postForm.payable_account_id),
          date: postForm.date,
        }),
      })
      setInfo(`Posted — JV ${r.jv_number}`)
      setPostingId(null)
      load()
    } catch (e) { setError(e instanceof Error ? e.message : "Post failed") }
  }

  // ── Render ───────────────────────────────────────────────────────────────

  const expenseAccounts = accounts.filter(a => a.type === "Expense")
  const liabilityAccounts = accounts.filter(a => a.type === "Liability")

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <PrintHeader title="Sales Commissions" />
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Percent className="w-6 h-6 text-[var(--primary)]" />
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">Sales Commissions</h1>
            <p className="text-xs text-[var(--text-primary)]/60">Track commission plans and monthly payables</p>
          </div>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button
            onClick={() => downloadCSV('commissions.csv', ledger.map(r => ({ Staff: r.user_name, Period: r.period, Amount: r.total_payable, Status: r.status })))}
            disabled={ledger.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[var(--border)] rounded-xl p-1 w-fit">
        {(["ledger", "plans"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-all capitalize ${tab === t ? "bg-white text-[var(--text-primary)] shadow-sm" : "text-[var(--text-primary)]/60 hover:text-[var(--text-primary)]"}`}
          >
            {t === "ledger" ? "Ledger" : "Plans"}
          </button>
        ))}
      </div>

      {/* Alerts */}
      {error && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 rounded-xl px-3 py-2.5 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
      {info && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-xl px-3 py-2.5 text-sm">
          {info}
        </div>
      )}

      {/* ── LEDGER TAB ─────────────────────────────────────────────────────── */}
      {tab === "ledger" && (
        <div className="space-y-4">
          {/* Period selector + Compute */}
          <div className="bg-white rounded-2xl border border-[var(--border)] shadow-sm p-4 flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Period</label>
              <input
                type="month"
                value={period}
                onChange={e => setPeriod(e.target.value)}
                className="px-3 py-2 bg-[var(--bg-page)] border border-transparent rounded-lg text-sm focus:ring-2 focus:ring-[var(--primary)] outline-none"
              />
            </div>
            <button
              onClick={compute}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-semibold hover:bg-[var(--primary-dark)] disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Compute
            </button>
          </div>

          {/* Ledger table */}
          <div className="bg-white rounded-2xl border border-[var(--border)] shadow-sm overflow-hidden">
            {ledger.length === 0 ? (
              <div className="py-16 text-center text-[var(--text-primary)]/40 text-sm">
                No commission entries for {period}. Click <strong>Compute</strong> to generate.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[var(--bg-page)]">
                    <tr>
                      {["Sales Person","Invoiced","Recovered","Rate","Commission","Bonus","Total Payable","Status",""].map(h => (
                        <th key={h} className="px-3 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {ledger.map(row => (
                      <>
                        <tr key={row.id} className="hover:bg-[#faf8f4]">
                          <td className="px-3 py-2.5 font-medium">{row.user_name}</td>
                          <td className="px-3 py-2.5 font-mono text-right">{row.total_invoiced.toFixed(dp)}</td>
                          <td className="px-3 py-2.5 font-mono text-right">{row.total_recovered.toFixed(dp)}</td>
                          <td className="px-3 py-2.5 text-right">{row.rate}%</td>
                          <td className="px-3 py-2.5 font-mono text-right">{row.commission_amount.toFixed(dp)}</td>
                          <td className="px-3 py-2.5 font-mono text-right">{row.bonus_amount > 0 ? row.bonus_amount.toFixed(dp) : "—"}</td>
                          <td className="px-3 py-2.5 font-mono text-right font-bold">{row.total_payable.toFixed(dp)}</td>
                          <td className="px-3 py-2.5">
                            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${STATUS_BADGE[row.status]}`}>
                              {row.status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-1">
                              {row.status === "draft" && (
                                <button
                                  onClick={() => approve(row.id)}
                                  className="p-1 text-blue-500 hover:text-blue-700 transition-colors"
                                  title="Approve"
                                >
                                  <CheckCircle className="w-4 h-4" />
                                </button>
                              )}
                              {row.status === "approved" && (
                                <button
                                  onClick={() => setPostingId(postingId === row.id ? null : row.id)}
                                  className="p-1 text-emerald-600 hover:text-emerald-800 transition-colors"
                                  title="Post to GL"
                                >
                                  <BookOpen className="w-4 h-4" />
                                </button>
                              )}
                              {row.status === "posted" && row.transaction_id && (
                                <a
                                  href={`/journal/${row.transaction_id}/print`}
                                  target="_blank"
                                  className="p-1 text-[var(--text-primary)]/40 hover:text-[var(--text-primary)]"
                                  title="View JV"
                                >
                                  <BookOpen className="w-4 h-4" />
                                </a>
                              )}
                            </div>
                          </td>
                        </tr>
                        {/* Post-to-GL inline form */}
                        {postingId === row.id && (
                          <tr key={`post-${row.id}`} className="bg-[var(--bg-page)]">
                            <td colSpan={9} className="px-4 py-3">
                              <div className="flex flex-wrap items-end gap-3">
                                <div>
                                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Commission Expense Account</label>
                                  <select
                                    value={postForm.expense_account_id}
                                    onChange={e => setPostForm(f => ({...f, expense_account_id: e.target.value}))}
                                    className="px-2 py-2 border border-[var(--border)] rounded-lg text-sm bg-white focus:ring-2 focus:ring-[var(--primary)] outline-none min-w-[200px]"
                                  >
                                    <option value="">Select expense account</option>
                                    {expenseAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                                  </select>
                                </div>
                                <div>
                                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Commissions Payable Account</label>
                                  <select
                                    value={postForm.payable_account_id}
                                    onChange={e => setPostForm(f => ({...f, payable_account_id: e.target.value}))}
                                    className="px-2 py-2 border border-[var(--border)] rounded-lg text-sm bg-white focus:ring-2 focus:ring-[var(--primary)] outline-none min-w-[200px]"
                                  >
                                    <option value="">Select payable account</option>
                                    {liabilityAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                                  </select>
                                </div>
                                <div>
                                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Posting Date</label>
                                  <input
                                    type="date"
                                    value={postForm.date}
                                    onChange={e => setPostForm(f => ({...f, date: e.target.value}))}
                                    className="px-2 py-2 border border-[var(--border)] rounded-lg text-sm bg-white focus:ring-2 focus:ring-[var(--primary)] outline-none"
                                  />
                                </div>
                                <button
                                  onClick={() => postToGL(row.id)}
                                  className="px-4 py-2 bg-[var(--text-primary)] text-white rounded-lg text-sm font-semibold hover:bg-[var(--primary)] transition-colors"
                                >
                                  Post to GL
                                </button>
                                <button
                                  onClick={() => setPostingId(null)}
                                  className="px-3 py-2 text-sm text-[var(--text-primary)]/60 hover:text-[var(--text-primary)]"
                                >{t('common.cancel', 'Cancel')}</button>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── PLANS TAB ──────────────────────────────────────────────────────── */}
      {tab === "plans" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setShowPlanForm(v => !v)}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--text-primary)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--primary)] transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Plan
            </button>
          </div>

          {/* New plan form */}
          {showPlanForm && (
            <div className="bg-white rounded-2xl border border-[var(--border)] shadow-sm p-5 space-y-4">
              <h3 className="font-semibold text-[var(--text-primary)]">New Commission Plan</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Sales Person *</label>
                  <select
                    value={planForm.user_id}
                    onChange={e => setPlanForm(f => ({...f, user_id: e.target.value}))}
                    className="w-full px-3 py-2 bg-[var(--bg-page)] border border-transparent rounded-lg text-sm focus:ring-2 focus:ring-[var(--primary)] outline-none"
                  >
                    <option value="">Select person</option>
                    {staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Commission Rate (%) *</label>
                  <input type="number" step="0.01" value={planForm.rate} onChange={e => setPlanForm(f => ({...f, rate: e.target.value}))} placeholder="e.g. 2.5" className="w-full px-3 py-2 bg-[var(--bg-page)] border border-transparent rounded-lg text-sm focus:ring-2 focus:ring-[var(--primary)] outline-none" />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Effective From *</label>
                  <input type="date" value={planForm.effective_from} onChange={e => setPlanForm(f => ({...f, effective_from: e.target.value}))} className="w-full px-3 py-2 bg-[var(--bg-page)] border border-transparent rounded-lg text-sm focus:ring-2 focus:ring-[var(--primary)] outline-none" />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Sales Target (optional)</label>
                  <input type="number" step="0.01" value={planForm.sales_target} onChange={e => setPlanForm(f => ({...f, sales_target: e.target.value}))} placeholder="Monthly target" className="w-full px-3 py-2 bg-[var(--bg-page)] border border-transparent rounded-lg text-sm focus:ring-2 focus:ring-[var(--primary)] outline-none" />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Recovery Target (optional)</label>
                  <input type="number" step="0.01" value={planForm.recovery_target} onChange={e => setPlanForm(f => ({...f, recovery_target: e.target.value}))} placeholder="Monthly recovery target" className="w-full px-3 py-2 bg-[var(--bg-page)] border border-transparent rounded-lg text-sm focus:ring-2 focus:ring-[var(--primary)] outline-none" />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Target Bonus (optional)</label>
                  <input type="number" step="0.01" value={planForm.target_bonus} onChange={e => setPlanForm(f => ({...f, target_bonus: e.target.value}))} placeholder="Bonus if targets met" className="w-full px-3 py-2 bg-[var(--bg-page)] border border-transparent rounded-lg text-sm focus:ring-2 focus:ring-[var(--primary)] outline-none" />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Effective To (leave blank = ongoing)</label>
                  <input type="date" value={planForm.effective_to} onChange={e => setPlanForm(f => ({...f, effective_to: e.target.value}))} className="w-full px-3 py-2 bg-[var(--bg-page)] border border-transparent rounded-lg text-sm focus:ring-2 focus:ring-[var(--primary)] outline-none" />
                </div>
              </div>
              <div className="flex gap-2 justify-end pt-2">
                <button onClick={() => setShowPlanForm(false)} className="px-4 py-2 bg-white border border-[var(--border)] rounded-lg text-sm font-semibold hover:bg-[var(--bg-page)]">{t('common.cancel', 'Cancel')}</button>
                <button onClick={createPlan} className="px-4 py-2 bg-[var(--text-primary)] text-white rounded-lg text-sm font-semibold hover:bg-[var(--primary)]">Save Plan</button>
              </div>
            </div>
          )}

          {/* Plans table */}
          <div className="bg-white rounded-2xl border border-[var(--border)] shadow-sm overflow-hidden">
            {plans.length === 0 ? (
              <div className="py-16 text-center text-[var(--text-primary)]/40 text-sm">
                No commission plans yet. Click <strong>New Plan</strong> to add one.
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-[var(--bg-page)]">
                  <tr>
                    {["Sales Person","Rate","Sales Target","Recovery Target","Bonus","Effective From","To","Status",""].map(h => (
                      <th key={h} className="px-3 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {plans.map(p => (
                    <tr key={p.id} className={`hover:bg-[#faf8f4] ${!p.active ? "opacity-50" : ""}`}>
                      <td className="px-3 py-2.5 font-medium">{p.user_name}</td>
                      <td className="px-3 py-2.5 text-right font-mono">{p.rate}%</td>
                      <td className="px-3 py-2.5 text-right font-mono">{p.sales_target?.toFixed(dp) ?? "—"}</td>
                      <td className="px-3 py-2.5 text-right font-mono">{p.recovery_target?.toFixed(dp) ?? "—"}</td>
                      <td className="px-3 py-2.5 text-right font-mono">{p.target_bonus?.toFixed(dp) ?? "—"}</td>
                      <td className="px-3 py-2.5">{p.effective_from}</td>
                      <td className="px-3 py-2.5">{p.effective_to ?? "Open"}</td>
                      <td className="px-3 py-2.5">
                        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${p.active ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
                          {p.active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        {p.active && (
                          <button onClick={() => deactivatePlan(p.id)} className="p-1 text-red-400 hover:text-red-600" title="Deactivate">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
