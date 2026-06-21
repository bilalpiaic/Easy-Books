'use client'

import { useEffect, useState } from 'react'
import { Printer, Download } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV } from '@/lib/utils'
import DateRangePicker from '@/components/DateRangePicker'
import PrintHeader from '@/components/PrintHeader'
import { useTranslation } from "react-i18next"

interface TaxSummary {
  period: { start: string; end: string }
  gst: {
    output_gst: number
    input_gst: number
    net_gst_payable: number
  }
  income_tax: {
    revenue: number
    expenses: number
    taxable_income: number
    estimated_tax: number
    tax_basis: string
  }
}

function defaultRange() {
  const today = new Date()
  const fyStart = today.getMonth() >= 6
    ? new Date(today.getFullYear(), 6, 1)
    : new Date(today.getFullYear() - 1, 6, 1)
  return { start: fyStart.toISOString().split('T')[0], end: today.toISOString().split('T')[0] }
}

export default function TaxReports() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<TaxSummary | null>(null)
  const [error, setError] = useState('')

  const exportCsv = () => {
    if (!data) return
    downloadCSV(`tax-report-${start}-${end}.csv`, [
      { Category: "GST", Item: "Output GST (Sales)", Amount: data.gst.output_gst },
      { Category: "GST", Item: "Input GST (Purchases)", Amount: data.gst.input_gst },
      { Category: "GST", Item: "Net GST Payable", Amount: data.gst.net_gst_payable },
      { Category: "Income Tax", Item: "Total Revenue", Amount: data.income_tax.revenue },
      { Category: "Income Tax", Item: "Business Expenses", Amount: data.income_tax.expenses },
      { Category: "Income Tax", Item: "Taxable Income", Amount: data.income_tax.taxable_income },
      { Category: "Income Tax", Item: "Estimated Tax", Amount: data.income_tax.estimated_tax },
    ])
  }

  useEffect(() => {
    apiFetch<TaxSummary>(`/api/reports/tax-summary?start=${start}&end=${end}`)
      .then(setData)
      .catch(err => setError((err as Error).message))
  }, [start, end])

  return (
    <div className="space-y-6 max-w-5xl">
      <PrintHeader title="Tax Report" subtitle={`Period: ${start} — ${end}`} />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-serif font-medium">Tax Reports</h1>
          <p className="text-sm text-black/75 mt-1">GST returns and income tax estimate — Pakistan ITO 2001</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="p-3 bg-white border border-[#ede9e2] rounded-xl">
            <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Fiscal Period" />
          </div>
          <button onClick={exportCsv} disabled={!data} className="p-3 bg-white border border-[#ede9e2] rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 disabled:opacity-40 print:hidden" title="Export CSV">
            <Download className="w-5 h-5" />
          </button>
          <button onClick={() => window.print()} className="p-3 bg-white border border-[#ede9e2] rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 print:hidden" title="Print">
            <Printer className="w-5 h-5" />
          </button>
        </div>
      </div>

      {error && <div className="text-red-600 font-semibold">{error}</div>}

      {!data ? (
        <div className="text-center py-12 text-black/40">{t('common.loading', 'Loading...')}</div>
      ) : (
        <>
          {/* GST Section */}
          <div className="bg-white rounded-xl border border-[#ede9e2] p-8">
            <h2 className="text-lg font-semibold mb-6 pb-3 border-b border-[#ede9e2]">GST Return Summary</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-[#f6f3ee] rounded-xl p-4 text-center">
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">Output GST (Sales)</p>
                <p className="text-xl font-bold font-mono text-red-600">{fmt(data.gst.output_gst)}</p>
              </div>
              <div className="bg-[#f6f3ee] rounded-xl p-4 text-center">
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">Input GST (Purchases)</p>
                <p className="text-xl font-bold font-mono text-green-600">{fmt(data.gst.input_gst)}</p>
              </div>
              <div className={`rounded-xl p-4 text-center ${data.gst.net_gst_payable > 0 ? 'bg-red-50' : 'bg-green-50'}`}>
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">Net GST Payable</p>
                <p className={`text-xl font-bold font-mono ${data.gst.net_gst_payable > 0 ? 'text-red-700' : 'text-green-700'}`}>
                  {fmt(data.gst.net_gst_payable)}
                </p>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between py-2 border-b border-[#ede9e2]">
                <span>Output GST (account 2200 credits)</span>
                <span className="font-mono">{fmt(data.gst.output_gst)}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-[#ede9e2]">
                <span>Less: Input GST (account 1200 debits)</span>
                <span className="font-mono">({fmt(data.gst.input_gst)})</span>
              </div>
              <div className="flex justify-between py-3 font-semibold text-base">
                <span>Net GST Payable to FBR</span>
                <span className={`font-mono ${data.gst.net_gst_payable > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {fmt(data.gst.net_gst_payable)}
                </span>
              </div>
            </div>
          </div>

          {/* Income Tax Section */}
          <div className="bg-white rounded-xl border border-[#ede9e2] p-8">
            <h2 className="text-lg font-semibold mb-6 pb-3 border-b border-[#ede9e2]">Income Tax Estimate</h2>
            <div className="space-y-3 mb-6">
              <div className="flex justify-between py-2 border-b border-[#ede9e2]">
                <span>Total Revenue</span>
                <span className="font-mono font-bold">{fmt(data.income_tax.revenue)}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-[#ede9e2]">
                <span>Less: Business Expenses</span>
                <span className="font-mono font-bold">({fmt(data.income_tax.expenses)})</span>
              </div>
              <div className="flex justify-between py-3 border-t-2 border-[#1a1814] font-semibold text-lg">
                <span>Taxable Income</span>
                <span className="font-mono text-[#b8943f]">{fmt(data.income_tax.taxable_income)}</span>
              </div>
            </div>

            <div className="bg-[#f6f3ee] rounded-xl p-6 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-black/60">Basis</span>
                <span className="text-black/80">{data.income_tax.tax_basis}</span>
              </div>
              <div className="flex justify-between pt-3 border-t border-[#ede9e2] font-semibold text-lg">
                <span>Estimated Income Tax</span>
                <span className="font-mono text-red-600">{fmt(data.income_tax.estimated_tax)}</span>
              </div>
            </div>

            <div className="mt-6 text-xs text-black/40 bg-amber-50 border border-amber-100 rounded-lg p-3">
              Tax slabs: 0–600K @ 0% | 600K–1.2M @ 5% | 1.2M–2.4M @ 15% | 2.4M–3.6M @ 25% | 3.6M–6M @ 30% | above 6M @ 35%.
              This is an estimate only. Consult a tax advisor for filing.
            </div>
          </div>
        </>
      )}
    </div>
  )
}
