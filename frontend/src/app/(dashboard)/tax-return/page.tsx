'use client'

import { useEffect, useState } from 'react'
import { Printer, Download } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV, fmtDate } from '@/lib/utils'
import DateRangePicker from '@/components/DateRangePicker'
import PrintHeader from '@/components/PrintHeader'
import { useTranslation } from 'react-i18next'

interface TaxReturnRow {
  tax_code_id: number
  code: string
  name: string
  type: string
  rate: number
  is_reverse_charge: boolean
  is_exempt: boolean
  is_zero_rated: boolean
  taxable_base: number
  output_tax: number
  input_tax: number
  reverse_charge_tax: number
  net: number
}

interface TaxReturn {
  period: { start: string; end: string }
  rows: TaxReturnRow[]
  totals: {
    taxable_base: number
    output_tax: number
    input_tax: number
    reverse_charge_tax: number
    net: number
  }
}

function defaultRange() {
  const today = new Date()
  const fyStart = today.getMonth() >= 6
    ? new Date(today.getFullYear(), 6, 1)
    : new Date(today.getFullYear() - 1, 6, 1)
  return { start: fyStart.toISOString().split('T')[0], end: today.toISOString().split('T')[0] }
}

export default function TaxReturnPage() {
  const { t } = useTranslation()
  const fmt = useFmt()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<TaxReturn | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    apiFetch<TaxReturn>(`/api/reports/tax-return?start=${start}&end=${end}`)
      .then(setData)
      .catch(err => setError((err as Error).message))
  }, [start, end])

  const exportCsv = () => {
    if (!data) return
    downloadCSV(
      `tax-return-${start}-${end}.csv`,
      data.rows.map(r => ({
        Code: r.code,
        Name: r.name,
        Type: r.type,
        'Rate %': r.rate,
        'Taxable Base': r.taxable_base,
        'Output Tax': r.output_tax,
        'Input Tax': r.input_tax,
        'Reverse Charge': r.reverse_charge_tax,
        Net: r.net,
      })),
    )
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <PrintHeader
        title="Tax Return"
        subtitle={`${fmtDate(start)} — ${fmtDate(end)}`}
        orientation="landscape"
      />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">Tax Return</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Output − input by tax code (line snapshots). Reverse charge is reported but not in net payable.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="p-3 bg-white border border-[var(--border)] rounded-xl">
            <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
          </div>
          <button
            onClick={exportCsv}
            disabled={!data?.rows.length}
            className="p-3 bg-white border border-[var(--border)] rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60 disabled:opacity-40"
            title="Export CSV"
          >
            <Download className="w-5 h-5" />
          </button>
          <button
            onClick={() => window.print()}
            className="p-3 bg-white border border-[var(--border)] rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60"
            title={t('common.print', 'Print')}
          >
            <Printer className="w-5 h-5" />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {!data && !error && (
        <div className="text-sm text-[var(--text-muted)] py-8 text-center">Loading…</div>
      )}

      {data && (
        <div className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
          <div className="table-freeze overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[#faf8f4]">
                  <th className="text-left px-4 py-3 font-semibold">Code</th>
                  <th className="text-left px-4 py-3 font-semibold">Name</th>
                  <th className="text-left px-4 py-3 font-semibold">Type</th>
                  <th className="text-right px-4 py-3 font-semibold">Rate %</th>
                  <th className="text-right px-4 py-3 font-semibold">Taxable Base</th>
                  <th className="text-right px-4 py-3 font-semibold">Output</th>
                  <th className="text-right px-4 py-3 font-semibold">Input</th>
                  <th className="text-right px-4 py-3 font-semibold">RC</th>
                  <th className="text-right px-4 py-3 font-semibold">Net</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-10 text-center text-[var(--text-muted)]">
                      No line-level tax activity in this period. Apply tax codes on invoices/bills to populate this return.
                    </td>
                  </tr>
                ) : (
                  data.rows.map(r => (
                    <tr key={r.tax_code_id} className="border-b border-[var(--border)] last:border-0">
                      <td className="px-4 py-2.5 font-mono text-xs whitespace-nowrap">{r.code}</td>
                      <td className="px-4 py-2.5">
                        {r.name}
                        {(r.is_reverse_charge || r.is_exempt || r.is_zero_rated) && (
                          <span className="ml-2 text-[11px] text-[var(--text-muted)]">
                            {[
                              r.is_zero_rated ? 'Zero' : null,
                              r.is_exempt ? 'Exempt' : null,
                              r.is_reverse_charge ? 'RC' : null,
                            ].filter(Boolean).join(' · ')}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 capitalize whitespace-nowrap">{r.type}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums whitespace-nowrap">{r.rate}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums whitespace-nowrap">{fmt(r.taxable_base)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums whitespace-nowrap">{fmt(r.output_tax)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums whitespace-nowrap">{fmt(r.input_tax)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums whitespace-nowrap">{fmt(r.reverse_charge_tax)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums font-medium whitespace-nowrap">{fmt(r.net)}</td>
                    </tr>
                  ))
                )}
              </tbody>
              {data.rows.length > 0 && (
                <tfoot>
                  <tr className="border-t border-[var(--border)] bg-[#faf8f4] font-semibold">
                    <td className="px-4 py-3" colSpan={4}>Totals</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmt(data.totals.taxable_base)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmt(data.totals.output_tax)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmt(data.totals.input_tax)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmt(data.totals.reverse_charge_tax)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmt(data.totals.net)}</td>
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
