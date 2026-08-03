'use client'

import { useEffect, useState } from 'react'
import { Printer } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import DateRangePicker from '@/components/DateRangePicker'
import PrintHeader from '@/components/PrintHeader'
import { fmtDate } from '@/lib/utils'

interface WhtRow {
  vendor_id: number | null
  vendor: string
  base: number
  wht: number
  payments: number
}

interface WhtReport {
  period: { start: string; end: string }
  items: WhtRow[]
  totals: { base: number; wht: number; payments: number }
}

function defaultRange() {
  const today = new Date()
  const start = new Date(today.getFullYear(), 0, 1)
  return {
    start: start.toISOString().split('T')[0],
    end: today.toISOString().split('T')[0],
  }
}

export default function WhtReportPage() {
  const fmt = useFmt()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<WhtReport | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch<WhtReport>(`/api/reports/wht?start=${start}&end=${end}`)
      .then(setData)
      .catch(err => setError((err as Error).message))
  }, [start, end])

  return (
    <div className="space-y-6 max-w-5xl">
      <PrintHeader
        title="Withholding Tax Report"
        subtitle={`${fmtDate(start)} — ${fmtDate(end)}`}
        orientation="landscape"
      />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">Withholding Tax</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            WHT deducted on vendor bill payments by period
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="p-3 bg-white border border-[var(--border)] rounded-xl">
            <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
          </div>
          <button
            onClick={() => window.print()}
            className="p-3 bg-white border border-[var(--border)] rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60"
            title="Print"
          >
            <Printer className="w-5 h-5" />
          </button>
        </div>
      </div>

      {error && <div className="text-red-600 font-semibold">{error}</div>}

      {!data ? (
        <div className="text-center py-12 text-[var(--text-muted)]">Loading…</div>
      ) : (
        <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
          <div className="table-freeze">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--bg-page)]">
                  <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Vendor</th>
                  <th className="px-4 py-3 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Payments</th>
                  <th className="px-4 py-3 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Base</th>
                  <th className="px-4 py-3 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">WHT</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-[var(--text-muted)] italic">
                      No withholding tax in this period.
                    </td>
                  </tr>
                ) : (
                  data.items.map((row, i) => (
                    <tr key={`${row.vendor_id ?? 'x'}-${i}`} className="hover:bg-[var(--bg-page)]/40">
                      <td className="px-4 py-2.5">{row.vendor}</td>
                      <td className="px-4 py-2.5 text-right font-mono whitespace-nowrap">{row.payments}</td>
                      <td className="px-4 py-2.5 text-right font-mono whitespace-nowrap">{fmt(row.base)}</td>
                      <td className="px-4 py-2.5 text-right font-mono whitespace-nowrap font-semibold">{fmt(row.wht)}</td>
                    </tr>
                  ))
                )}
              </tbody>
              {data.items.length > 0 && (
                <tfoot>
                  <tr className="border-t-2 border-[var(--border)] font-bold bg-[var(--bg-page)]">
                    <td className="px-4 py-3">Totals</td>
                    <td className="px-4 py-3 text-right font-mono">{data.totals.payments}</td>
                    <td className="px-4 py-3 text-right font-mono">{fmt(data.totals.base)}</td>
                    <td className="px-4 py-3 text-right font-mono">{fmt(data.totals.wht)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
