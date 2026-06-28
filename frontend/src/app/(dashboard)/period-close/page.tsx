"use client"

import { useEffect, useState } from "react"
import { CalendarCheck, Plus, Lock, RotateCcw, Eye, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt, useSettings } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface Period {
  id: number
  name: string | null
  period_start: string
  period_end: string
  is_locked: boolean
}

interface PreviewByAccount { code: string; name: string; type: string; amount: string }
interface ClosePreview {
  revenue_total: string
  expense_total: string
  net_income: string
  by_account: PreviewByAccount[]
}

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]

function pad(n: number) { return String(n).padStart(2, "0") }
function lastDay(year: number, month0: number) { return new Date(year, month0 + 1, 0).getDate() }

export default function PeriodClosePage() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const { settings } = useSettings()
  const [periods, setPeriods] = useState<Period[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState<{ period: Period; data: ClosePreview } | null>(null)
  const [err, setErr] = useState("")

  function load() {
    setLoading(true)
    apiFetch<Period[]>("/api/periods").then(d => { setPeriods(d); setLoading(false) }).catch(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const fiscalStartMonth = Math.max(0, MONTHS.indexOf(settings.fiscal_year_start || "January"))

  async function createPreset(kind: "month" | "quarter" | "year") {
    const now = new Date()
    const y = now.getFullYear()
    let name = "", start = "", end = ""
    if (kind === "month") {
      const m = now.getMonth()
      name = `${MONTHS[m]} ${y}`
      start = `${y}-${pad(m + 1)}-01`
      end = `${y}-${pad(m + 1)}-${pad(lastDay(y, m))}`
    } else if (kind === "quarter") {
      const q = Math.floor(now.getMonth() / 3)
      const sm = q * 3, em = sm + 2
      name = `Q${q + 1} ${y}`
      start = `${y}-${pad(sm + 1)}-01`
      end = `${y}-${pad(em + 1)}-${pad(lastDay(y, em))}`
    } else {
      // Fiscal year starting at fiscalStartMonth
      const fyStartYear = now.getMonth() >= fiscalStartMonth ? y : y - 1
      const startD = new Date(fyStartYear, fiscalStartMonth, 1)
      const endD = new Date(fyStartYear + 1, fiscalStartMonth, 0)
      name = `FY ${fyStartYear}${fiscalStartMonth === 0 ? "" : `/${fyStartYear + 1}`}`
      start = `${startD.getFullYear()}-${pad(startD.getMonth() + 1)}-01`
      end = `${endD.getFullYear()}-${pad(endD.getMonth() + 1)}-${pad(endD.getDate())}`
    }
    setBusy(true); setErr("")
    try {
      await apiFetch("/api/periods", { method: "POST", body: JSON.stringify({ name, period_start: start, period_end: end }) })
      load()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  async function showPreview(p: Period) {
    setErr("")
    try {
      const data = await apiFetch<ClosePreview>(`/api/periods/${p.id}/close-preview`)
      setPreview({ period: p, data })
    } catch (e) { setErr((e as Error).message) }
  }

  async function close(p: Period, mode: "soft" | "year_end") {
    if (mode === "year_end" && !window.confirm(
      `Year-end close for "${p.name ?? p.period_start}"?\n\nThis posts the P&L → Retained Earnings closing journal and locks the period. Use only at fiscal year-end.`
    )) return
    setBusy(true); setErr("")
    try {
      await apiFetch(`/api/periods/${p.id}/close?mode=${mode}`, { method: "POST" })
      setPreview(null); load()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  async function reopen(p: Period) {
    if (!window.confirm(`Reopen "${p.name ?? p.period_start}"? This unlocks the period.`)) return
    setBusy(true); setErr("")
    try {
      await apiFetch(`/api/periods/${p.id}/reopen`, { method: "POST" })
      load()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <PrintHeader title="Period Close" />
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--text-primary)] flex items-center justify-center flex-shrink-0">
            <CalendarCheck className="w-5 h-5 text-[#ffd966]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Period Close</h1>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mt-0.5">Soft lock (monthly/quarterly) · Year-end P&L → Retained Earnings</p>
          </div>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button
            onClick={() => downloadCSV('periods.csv', periods.map(p => ({ Name: p.name ?? '', "Period Start": p.period_start, "Period End": p.period_end, Status: p.is_locked ? 'Locked' : 'Open' })))}
            disabled={periods.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
        </div>
      </div>

      <div className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-wrap items-center gap-3">
        <span className="text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/50">New period</span>
        <button onClick={() => createPreset("month")} disabled={busy} className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-page)] rounded-lg text-sm hover:bg-[var(--border)] disabled:opacity-50"><Plus size={14} /> This Month</button>
        <button onClick={() => createPreset("quarter")} disabled={busy} className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-page)] rounded-lg text-sm hover:bg-[var(--border)] disabled:opacity-50"><Plus size={14} /> This Quarter</button>
        <button onClick={() => createPreset("year")} disabled={busy} className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-page)] rounded-lg text-sm hover:bg-[var(--border)] disabled:opacity-50"><Plus size={14} /> This Fiscal Year</button>
      </div>

      {err && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{err}</p>}

      <div className="bg-white rounded-2xl border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[480px]">
          <thead className="bg-[var(--bg-page)]">
            <tr>{["Period", "Range", "Status", "Actions"].map(h => (
              <th key={h} className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/50">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="ui-td py-10 text-center text-[var(--text-primary)]/40 italic">Loading…</td></tr>
            ) : periods.length === 0 ? (
              <tr><td colSpan={4} className="ui-td py-16 text-center">
                <CalendarCheck className="w-8 h-8 mx-auto text-[var(--text-primary)]/20 mb-3" />
                <p className="text-[var(--text-primary)]/50 text-sm">No periods yet — create one with a preset above.</p>
              </td></tr>
            ) : periods.map(p => (
              <tr key={p.id} className="border-t border-[var(--text-primary)]/5 hover:bg-[var(--bg-page)]/40">
                <td className="ui-td font-medium">{p.name ?? "—"}</td>
                <td className="ui-td text-[var(--text-primary)]/60 font-mono text-xs">{p.period_start} → {p.period_end}</td>
                <td className="ui-td">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${p.is_locked ? "bg-gray-200 text-gray-700" : "bg-green-100 text-green-700"}`}>
                    {p.is_locked ? "Locked" : "Open"}
                  </span>
                </td>
                <td className="ui-td">
                  <div className="flex items-center gap-3 text-xs">
                    {!p.is_locked && <>
                      <button onClick={() => showPreview(p)} className="flex items-center gap-1 text-[var(--primary)] hover:underline"><Eye size={12} /> Preview</button>
                      <button onClick={() => close(p, "soft")} className="flex items-center gap-1 text-[var(--text-primary)]/70 hover:text-[var(--primary)]"><Lock size={12} /> Soft Close</button>
                      <button onClick={() => close(p, "year_end")} className="flex items-center gap-1 font-semibold text-[var(--text-primary)] hover:text-[var(--primary)]"><Lock size={12} /> Year-End Close</button>
                    </>}
                    {p.is_locked && <button onClick={() => reopen(p)} className="flex items-center gap-1 text-[var(--text-primary)]/60 hover:text-red-600"><RotateCcw size={12} /> Reopen</button>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {/* Preview modal */}
      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-md max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b border-[var(--border)] flex justify-between items-center">
              <h2 className="text-xl font-bold text-[var(--text-primary)]">Close Preview — {preview.period.name}</h2>
              <button onClick={() => setPreview(null)} className="text-[var(--text-primary)]/40 hover:text-[var(--text-primary)] text-xl">✕</button>
            </div>
            <div className="p-6 space-y-3 text-sm">
              <div className="flex justify-between"><span className="text-[var(--text-primary)]/60">Total Revenue</span><span className="font-mono">{fmt(Number(preview.data.revenue_total))}</span></div>
              <div className="flex justify-between"><span className="text-[var(--text-primary)]/60">Total Expenses</span><span className="font-mono">({fmt(Number(preview.data.expense_total))})</span></div>
              <div className="flex justify-between font-bold border-t border-[var(--border)] pt-2">
                <span>Net Income → Retained Earnings</span>
                <span className={`font-mono ${Number(preview.data.net_income) >= 0 ? "text-green-600" : "text-red-600"}`}>{fmt(Number(preview.data.net_income))}</span>
              </div>
              {preview.data.by_account.length > 0 && (
                <div className="mt-3 pt-3 border-t border-[var(--border)] space-y-1 max-h-48 overflow-y-auto">
                  {preview.data.by_account.map(a => (
                    <div key={a.code} className="flex justify-between text-xs text-[var(--text-primary)]/60">
                      <span>{a.code} {a.name}</span><span className="font-mono">{fmt(Number(a.amount))}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-2 pt-3">
                <button onClick={() => close(preview.period, "soft")} disabled={busy}
                  className="flex-1 py-2.5 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] disabled:opacity-50">Soft Close</button>
                <button onClick={() => close(preview.period, "year_end")} disabled={busy}
                  className="flex-1 py-2.5 bg-[var(--text-primary)] text-white rounded-xl text-sm font-bold hover:bg-[var(--primary)] hover:text-black disabled:opacity-50">Year-End Close</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
