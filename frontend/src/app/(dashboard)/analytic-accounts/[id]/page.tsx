'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ChevronLeft, TrendingUp, TrendingDown, Minus, Download } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV } from '@/lib/utils'
import { useTranslation } from "react-i18next"

// ── Types ─────────────────────────────────────────────────────────────────────

interface AnalyticAccount {
  id: number
  code: string
  name: string
  type: string
}

interface PlRow {
  name: string
  code: string
  type: 'Revenue' | 'Expense'
  total_debit: number
  total_credit: number
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function thisYear() {
  const y = new Date().getFullYear()
  return { start: `${y}-01-01`, end: `${y}-12-31` }
}

// Revenue net: credits − debits; Expense net: debits − credits
function rowNet(r: PlRow): number {
  return r.type === 'Revenue'
    ? r.total_credit - r.total_debit
    : r.total_debit - r.total_credit
}

const TYPE_LABELS: Record<string, string> = {
  cost_center: 'Cost Center',
  project:     'Project',
  department:  'Department',
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AnalyticPlPage() {
  const { t } = useTranslation()

  const { id } = useParams<{ id: string }>()
  const fmt     = useFmt()
  const { start: defStart, end: defEnd } = thisYear()

  const [account, setAccount]  = useState<AnalyticAccount | null>(null)
  const [rows, setRows]        = useState<PlRow[]>([])
  const [start, setStart]      = useState(defStart)
  const [end, setEnd]          = useState(defEnd)
  const [loading, setLoading]  = useState(true)
  const [error, setError]      = useState<string | null>(null)

  const loadAccount = () =>
    apiFetch<AnalyticAccount>(`/api/analytic-accounts/${id}`)
      .then(setAccount).catch(() => {})

  const loadPl = () => {
    setLoading(true)
    apiFetch<PlRow[]>(
      `/api/reports/analytic-pl?analytic_account_id=${id}&start=${start}&end=${end}`
    )
      .then(setRows)
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadAccount() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { loadPl() }, [id, start, end]) // eslint-disable-line react-hooks/exhaustive-deps

  const revenueRows  = rows.filter(r => r.type === 'Revenue')
  const expenseRows  = rows.filter(r => r.type === 'Expense')
  const totalRevenue = revenueRows.reduce((s, r) => s + rowNet(r), 0)
  const totalExpense = expenseRows.reduce((s, r) => s + rowNet(r), 0)
  const netProfit    = totalRevenue - totalExpense

  const Section = ({
    title,
    sectionRows,
    total,
    positive,
  }: {
    title: string
    sectionRows: PlRow[]
    total: number
    positive: boolean
  }) => (
    <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
      <div className="px-6 py-3 bg-[var(--bg-page)] border-b border-[var(--border)]">
        <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/60">{title}</h2>
      </div>
      {sectionRows.length === 0 ? (
        <p className="px-6 py-4 text-sm text-[var(--text-primary)]/40">No entries in this period.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)]/50">
            <tr>
              <th className="px-6 py-2 text-left text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/50">{t('col.account', 'Account')}</th>
              <th className="px-6 py-2 text-right text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/50">{t('col.amount', 'Amount')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {sectionRows.map(r => (
              <tr key={r.code} className="hover:bg-[var(--bg-page)]/50">
                <td className="px-6 py-2.5">
                  {r.name}
                  {r.code && <span className="ml-1.5 text-xs text-[var(--text-primary)]/40 font-mono">{r.code}</span>}
                </td>
                <td className="px-6 py-2.5 text-right tabular-nums">
                  {fmt(rowNet(r))}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t-2 border-[var(--text-primary)]/10">
            <tr className="bg-[var(--bg-page)]">
              <td className="px-6 py-2.5 text-sm font-bold">Total {title}</td>
              <td className={`px-6 py-2.5 text-right tabular-nums font-bold text-base ${
                positive ? 'text-emerald-700' : 'text-red-700'
              }`}>
                {fmt(total)}
              </td>
            </tr>
          </tfoot>
        </table>
      )}
    </div>
  )

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">

      {/* Back */}
      <Link href="/analytic-accounts" className="flex items-center gap-1 text-sm text-[var(--text-primary)]/60 hover:text-[var(--primary)]">
        <ChevronLeft className="w-4 h-4" /> Analytic Accounts
      </Link>

      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">
          {account ? `${account.code} · ${account.name}` : `Analytic Account #${id}`}
        </h1>
        {account && (
          <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
            {TYPE_LABELS[account.type] ?? account.type} · Profit &amp; Loss
          </p>
        )}
      </div>

      {/* Date range */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">From</label>
          <input
            type="date"
            value={start}
            onChange={e => setStart(e.target.value)}
            className="ui-field bg-[var(--bg-page)] rounded-xl text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">To</label>
          <input
            type="date"
            value={end}
            onChange={e => setEnd(e.target.value)}
            className="ui-field bg-[var(--bg-page)] rounded-xl text-sm"
          />
        </div>
        <button
          onClick={() => downloadCSV(`analytic-pl-${account?.code ?? id}.csv`, rows.map(r => ({ Type: r.type, Account: r.name, Code: r.code, Net: rowNet(r) })))}
          disabled={rows.length === 0}
          className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
        >
          <Download className="w-4 h-4" /> CSV
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-sm text-[var(--text-primary)]/60">Loading…</p>
      ) : (
        <>
          <Section
            title="Revenue"
            sectionRows={revenueRows}
            total={totalRevenue}
            positive={totalRevenue >= 0}
          />
          <Section
            title="Expenses"
            sectionRows={expenseRows}
            total={totalExpense}
            positive={false}
          />

          {/* Net profit summary */}
          <div className={`flex items-center justify-between px-6 py-4 rounded-2xl border-2 font-bold ${
            netProfit >= 0
              ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
              : 'bg-red-50 border-red-300 text-red-800'
          }`}>
            <div className="flex items-center gap-2">
              {netProfit > 0
                ? <TrendingUp className="w-5 h-5" />
                : netProfit < 0
                ? <TrendingDown className="w-5 h-5" />
                : <Minus className="w-5 h-5" />
              }
              <span className="text-base">Net {netProfit >= 0 ? 'Profit' : 'Loss'}</span>
            </div>
            <span className="text-xl tabular-nums">{fmt(Math.abs(netProfit))}</span>
          </div>

          {rows.length === 0 && (
            <div className="text-center py-10 text-[var(--text-primary)]/40 text-sm">
              No journal entries with this analytic tag in the selected period.
            </div>
          )}
        </>
      )}
    </div>
  )
}
