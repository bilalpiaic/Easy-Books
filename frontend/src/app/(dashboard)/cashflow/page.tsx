'use client'

import { useEffect, useState } from 'react'
import { Printer, Download } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { fmtAmount, downloadCSV } from '@/lib/utils'
import { useSettings } from '@/context/SettingsContext'
import DateRangePicker from '@/components/DateRangePicker'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import { useTranslation } from "react-i18next"

interface CashFlowData {
  period: { start: string; end: string }
  net_income: number
  operating_adjustments: { ar_change: number; ap_change: number }
  operating_cash: number
  investing_items: { name: string; amount: number }[]
  investing_cash: number
  financing_items: { name: string; amount: number }[]
  financing_cash: number
  net_cash_change: number
  unclassified: number
  beginning_balance: number
  ending_balance: number
}

interface CashFlowResponse {
  current?: CashFlowData
  comparison?: CashFlowData
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split('T')[0], end: to.toISOString().split('T')[0] }
}

function priorYearRange(start: string, end: string) {
  const priorStart = `${parseInt(start.slice(0, 4)) - 1}${start.slice(4)}`
  const priorEnd   = `${parseInt(end.slice(0, 4)) - 1}${end.slice(4)}`
  return { priorStart, priorEnd }
}

interface RowProps {
  label: string
  current: number
  comparison?: number | null
  showCmp: boolean
  indent?: boolean
  bold?: boolean
  accountName?: string
  fmt: (n: number) => string
}

function Row({ label, current, comparison, showCmp, indent = false, bold = false, accountName, fmt }: RowProps) {
  const curColor = current < 0 ? 'text-red-600' : ''
  const cmpColor = (comparison ?? 0) < 0 ? 'text-red-300' : 'text-[var(--text-primary)]/35'
  return (
    <div className={`flex justify-between py-2 ${bold ? 'border-t border-[var(--border)]' : ''}`}>
      {accountName
        ? <DocLink type="account" id={accountName} label={label} className={`${indent ? 'ml-6 ' : ''}text-sm`} />
        : <span className={`${indent ? 'ml-6 ' : ''}${bold ? 'font-semibold' : 'text-sm text-[var(--text-muted)]'}`}>{label}</span>}
      <div className="flex gap-8">
        <span className={`font-mono text-right w-36 inline-block ${bold ? 'font-semibold' : 'text-sm'} ${curColor}`}>
          {fmt(current)}
        </span>
        {showCmp && (
          <span className={`font-mono text-right w-36 inline-block ${bold ? 'font-semibold' : 'text-sm'} ${cmpColor}`}>
            {fmt(comparison ?? 0)}
          </span>
        )}
      </div>
    </div>
  )
}

export default function CashFlow() {
  const { t } = useTranslation()

  const { settings } = useSettings()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<CashFlowData | null>(null)
  const [comparison, setComparison] = useState<CashFlowData | null>(null)
  const [compareMode, setCompareMode] = useState(false)
  const { priorStart, priorEnd } = priorYearRange(start, end)
  const [cmpStart, setCmpStart] = useState(priorStart)
  const [cmpEnd, setCmpEnd] = useState(priorEnd)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(true)

  const fmt = (n: number) => fmtAmount(n, settings.currency)

  const exportCsv = () => {
    if (!data) return
    const rows: Record<string, string | number>[] = [
      { Section: "Operating", Item: "Net Income", Amount: data.net_income },
      { Section: "Operating", Item: "AR Change", Amount: data.operating_adjustments.ar_change },
      { Section: "Operating", Item: "AP Change", Amount: data.operating_adjustments.ap_change },
      { Section: "Operating", Item: "Net Operating Cash", Amount: data.operating_cash },
      ...data.investing_items.map(i => ({ Section: "Investing", Item: i.name, Amount: i.amount })),
      { Section: "Investing", Item: "Net Investing Cash", Amount: data.investing_cash },
      ...data.financing_items.map(i => ({ Section: "Financing", Item: i.name, Amount: i.amount })),
      { Section: "Financing", Item: "Net Financing Cash", Amount: data.financing_cash },
      { Section: "Summary", Item: "Net Cash Change", Amount: data.net_cash_change },
      { Section: "Summary", Item: "Beginning Balance", Amount: data.beginning_balance },
      { Section: "Summary", Item: "Ending Balance", Amount: data.ending_balance },
    ]
    downloadCSV(`cash-flow-${start}-${end}.csv`, rows)
  }

  useEffect(() => {
    setIsLoading(true)
    setError('')
    const params = new URLSearchParams({ start, end })
    if (compareMode) {
      params.set('compare_start', cmpStart)
      params.set('compare_end', cmpEnd)
    }
    apiFetch<CashFlowData | CashFlowResponse>(`/api/reports/cash-flow?${params}`)
      .then(res => {
        if (compareMode && res && typeof res === 'object' && 'current' in res) {
          setData((res as CashFlowResponse).current ?? null)
          setComparison((res as CashFlowResponse).comparison ?? null)
        } else {
          setData(res as CashFlowData)
          setComparison(null)
        }
        setIsLoading(false)
      })
      .catch(err => {
        setError((err as Error).message)
        setIsLoading(false)
      })
  }, [start, end, compareMode, cmpStart, cmpEnd])

  const showCmp = !!comparison

  return (
    <div className="space-y-6 max-w-5xl">
      <PrintHeader title="Cash Flow Statement" subtitle={`Period: ${start} — ${end}`} />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">Cash Flow Statement</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Sources and uses of cash — Indirect Method</p>
        </div>
        <div className="flex items-center gap-2">
          {!compareMode && (
            <button onClick={exportCsv} disabled={isLoading || !data} className="p-3 bg-white border border-[var(--border)] rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60 disabled:opacity-40" title="Export CSV">
              <Download className="w-5 h-5" />
            </button>
          )}
          <button onClick={() => window.print()} className="p-3 bg-white border border-[var(--border)] rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60" title="Print">
            <Printer className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="mb-4 p-4 bg-white border border-[var(--border)] rounded-xl space-y-3 print:hidden">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]/70 cursor-pointer">
          <input
            type="checkbox"
            checked={compareMode}
            onChange={e => setCompareMode(e.target.checked)}
            className="rounded"
          />
          Compare with prior period
        </label>
        {compareMode && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-[var(--text-primary)]/50">Prior period:</span>
            <input type="date" value={cmpStart} onChange={e => setCmpStart(e.target.value)}
                   className="border border-[var(--border)] rounded px-2 py-1 text-sm" />
            <span className="text-[var(--text-primary)]/50">to</span>
            <input type="date" value={cmpEnd} onChange={e => setCmpEnd(e.target.value)}
                   className="border border-[var(--border)] rounded px-2 py-1 text-sm" />
          </div>
        )}
      </div>

      {error && <div className="text-red-600 font-semibold">{error}</div>}

      {isLoading ? (
        <div className="text-center py-12 text-[var(--text-muted)]">{t('common.loading', 'Loading...')}</div>
      ) : !data ? (
        <div className="text-center py-12 text-[var(--text-muted)]">No data available.</div>
      ) : (
        <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 p-10 space-y-8">
          <div className="text-center pb-6 border-b border-[var(--border)]">
            <h2 className="text-xl font-bold mb-1">Statement of Cash Flows</h2>
            <p className="text-xs text-[var(--text-muted)] mt-1">{data.period.start} — {data.period.end}</p>
          </div>

          {/* Column headers */}
          {showCmp && (
            <div className="flex justify-end gap-8 text-xs font-bold text-[var(--text-primary)]/50 uppercase tracking-widest">
              <span className="w-36 text-right">Current Period</span>
              <span className="w-36 text-right text-[var(--text-primary)]/30">Comparative Period</span>
            </div>
          )}

          {/* Operating */}
          <div>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2 mb-3">Operating Activities</h3>
            <Row label="Net Income" current={data.net_income} comparison={comparison?.net_income} showCmp={showCmp} fmt={fmt} />
            <Row label="Decrease (Increase) in Accounts Receivable" current={-data.operating_adjustments.ar_change} comparison={comparison ? -comparison.operating_adjustments.ar_change : null} showCmp={showCmp} indent fmt={fmt} />
            <Row label="Increase (Decrease) in Accounts Payable" current={data.operating_adjustments.ap_change} comparison={comparison?.operating_adjustments.ap_change} showCmp={showCmp} indent fmt={fmt} />
            <Row label="Net Cash from Operations" current={data.operating_cash} comparison={comparison?.operating_cash} showCmp={showCmp} bold fmt={fmt} />
          </div>

          {/* Investing */}
          <div>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2 mb-3">Investing Activities</h3>
            {data.investing_items.length === 0 && !showCmp ? (
              <p className="text-sm text-[var(--text-muted)] mb-3">No fixed asset movements</p>
            ) : data.investing_items.map((item, i) => (
              <Row key={i} label={item.name} current={item.amount}
                comparison={comparison?.investing_items.find(ci => ci.name === item.name)?.amount ?? null}
                showCmp={showCmp} indent accountName={item.name} fmt={fmt} />
            ))}
            {showCmp && comparison && comparison.investing_items.filter(ci => !data.investing_items.find(di => di.name === ci.name)).map((item, i) => (
              <Row key={`cmp-only-inv-${i}`} label={item.name} current={0} comparison={item.amount}
                showCmp={showCmp} indent accountName={item.name} fmt={fmt} />
            ))}
            <Row label="Net Cash from Investing" current={data.investing_cash} comparison={comparison?.investing_cash} showCmp={showCmp} bold fmt={fmt} />
          </div>

          {/* Financing */}
          <div>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2 mb-3">Financing Activities</h3>
            {data.financing_items.length === 0 && !showCmp ? (
              <p className="text-sm text-[var(--text-muted)] mb-3">No financing movements</p>
            ) : data.financing_items.map((item, i) => (
              <Row key={i} label={item.name} current={item.amount}
                comparison={comparison?.financing_items.find(ci => ci.name === item.name)?.amount ?? null}
                showCmp={showCmp} indent accountName={item.name} fmt={fmt} />
            ))}
            {showCmp && comparison && comparison.financing_items.filter(ci => !data.financing_items.find(di => di.name === ci.name)).map((item, i) => (
              <Row key={`cmp-only-fin-${i}`} label={item.name} current={0} comparison={item.amount}
                showCmp={showCmp} indent accountName={item.name} fmt={fmt} />
            ))}
            <Row label="Net Cash from Financing" current={data.financing_cash} comparison={comparison?.financing_cash} showCmp={showCmp} bold fmt={fmt} />
          </div>

          {/* Reconciling difference (only when classification didn't fully tie out) */}
          {(Math.abs(data.unclassified) >= 0.005 || (!!comparison && Math.abs(comparison.unclassified) >= 0.005)) && (
            <div>
              <Row label="Unclassified / reconciling" current={data.unclassified}
                comparison={comparison?.unclassified ?? null} showCmp={showCmp} indent fmt={fmt} />
            </div>
          )}

          {/* Summary */}
          <div className="bg-[var(--bg-page)] p-6 rounded-xl space-y-3">
            <div className="flex justify-between pb-3 border-b border-[var(--border)]">
              <span className="font-semibold flex items-center gap-2">
                Net Change in Cash
                {Math.abs(data.unclassified) < 0.005 ? (
                  <span className="text-[10px] text-green-600 font-bold uppercase tracking-wide">✓ Reconciled</span>
                ) : (
                  <span className="text-[10px] text-amber-600 font-bold">incl. unclassified</span>
                )}
              </span>
              <div className="flex gap-8">
                <span className={`font-mono text-right w-36 inline-block font-bold text-lg ${(data.net_cash_change + data.unclassified) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {(data.net_cash_change + data.unclassified) >= 0 ? '+' : ''}{fmt(data.net_cash_change + data.unclassified)}
                </span>
                {showCmp && comparison && (
                  <span className={`font-mono text-right w-36 inline-block font-bold text-lg ${(comparison.net_cash_change + comparison.unclassified) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                    {(comparison.net_cash_change + comparison.unclassified) >= 0 ? '+' : ''}{fmt(comparison.net_cash_change + comparison.unclassified)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex justify-between text-sm">
              <span>Beginning Cash Balance</span>
              <div className="flex gap-8">
                <span className="font-mono text-right w-36 inline-block">{fmt(data.beginning_balance)}</span>
                {showCmp && comparison && (
                  <span className="font-mono text-right w-36 inline-block text-[var(--text-primary)]/35">{fmt(comparison.beginning_balance)}</span>
                )}
              </div>
            </div>
            <div className="flex justify-between text-lg font-bold border-t border-[var(--border)] pt-3">
              <span>Ending Cash Balance</span>
              <div className="flex gap-8">
                <span className="font-mono text-right w-36 inline-block text-[var(--primary)]">{fmt(data.ending_balance)}</span>
                {showCmp && comparison && (
                  <span className="font-mono text-right w-36 inline-block text-[var(--primary)]/40">{fmt(comparison.ending_balance)}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
