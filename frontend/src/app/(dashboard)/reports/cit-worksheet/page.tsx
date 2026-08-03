'use client'

import { useCallback, useEffect, useState } from 'react'
import { Plus, Printer, Trash2 } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import DateRangePicker from '@/components/DateRangePicker'
import PrintHeader from '@/components/PrintHeader'
import { fmtDate } from '@/lib/utils'

interface CitAdj {
  id: number
  fiscal_year: string
  kind: 'addback' | 'deduction'
  description: string
  amount: number
}

interface CitWorksheet {
  period: { start: string; end: string }
  fiscal_year: string
  tax_rate: number
  accounting_profit: number
  revenue: number
  expenses: number
  addbacks: CitAdj[]
  deductions: CitAdj[]
  total_addbacks: number
  total_deductions: number
  taxable_income: number
  estimated_tax: number
  note: string
}

function defaultRange() {
  const today = new Date()
  const start = new Date(today.getFullYear(), 0, 1)
  return {
    start: start.toISOString().split('T')[0],
    end: today.toISOString().split('T')[0],
    fy: String(today.getFullYear()),
  }
}

export default function CitWorksheetPage() {
  const fmt = useFmt()
  const defaults = defaultRange()
  const [start, setStart] = useState(defaults.start)
  const [end, setEnd] = useState(defaults.end)
  const [fiscalYear, setFiscalYear] = useState(defaults.fy)
  const [taxRate, setTaxRate] = useState('29')
  const [data, setData] = useState<CitWorksheet | null>(null)
  const [error, setError] = useState('')
  const [kind, setKind] = useState<'addback' | 'deduction'>('addback')
  const [desc, setDesc] = useState('')
  const [amount, setAmount] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    const rate = parseFloat(taxRate) || 29
    apiFetch<CitWorksheet>(
      `/api/reports/cit-worksheet?start=${start}&end=${end}&fiscal_year=${encodeURIComponent(fiscalYear)}&tax_rate=${rate}`,
    )
      .then(setData)
      .catch(err => setError((err as Error).message))
  }, [start, end, fiscalYear, taxRate])

  useEffect(() => { load() }, [load])

  const addAdj = async () => {
    if (!desc.trim() || !amount) return
    setSaving(true)
    try {
      await apiFetch('/api/reports/cit-adjustments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fiscal_year: fiscalYear,
          kind,
          description: desc.trim(),
          amount: parseFloat(amount),
        }),
      })
      setDesc('')
      setAmount('')
      load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const removeAdj = async (id: number) => {
    try {
      await apiFetch(`/api/reports/cit-adjustments/${id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <PrintHeader
        title="Corporate Tax Worksheet"
        subtitle={`FY ${fiscalYear} · ${fmtDate(start)} — ${fmtDate(end)}`}
      />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">Corporate Tax Worksheet</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Accounting profit → addbacks / deductions → estimated tax
          </p>
        </div>
        <button
          onClick={() => window.print()}
          className="p-3 bg-white border border-[var(--border)] rounded-xl hover:bg-[var(--bg-page)] self-start"
          title="Print"
        >
          <Printer className="w-5 h-5" />
        </button>
      </div>

      <div className="flex flex-wrap gap-3 print:hidden p-4 bg-white border border-[var(--border)] rounded-xl">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="P&amp;L period" />
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] mb-1">Fiscal year</label>
          <input
            value={fiscalYear}
            onChange={e => setFiscalYear(e.target.value)}
            className="ui-field w-28 bg-[var(--bg-page)] rounded-xl"
            placeholder="2026"
          />
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] mb-1">Tax rate %</label>
          <input
            type="number" step="0.01"
            value={taxRate}
            onChange={e => setTaxRate(e.target.value)}
            className="ui-field w-24 bg-[var(--bg-page)] rounded-xl"
          />
        </div>
      </div>

      {error && <div className="text-red-600 font-semibold print:hidden">{error}</div>}

      {!data ? (
        <div className="text-center py-12 text-[var(--text-muted)]">Loading…</div>
      ) : (
        <div className="bg-white rounded-xl border border-[var(--border)] p-6 space-y-4">
          <p className="text-xs text-[var(--text-muted)] italic">{data.note}</p>

          <div className="grid grid-cols-2 gap-y-2 text-sm max-w-lg">
            <span className="text-[var(--text-muted)]">Revenue</span>
            <span className="text-right font-mono">{fmt(data.revenue)}</span>
            <span className="text-[var(--text-muted)]">Expenses</span>
            <span className="text-right font-mono">{fmt(data.expenses)}</span>
            <span className="font-semibold border-t border-[var(--border)] pt-2">Accounting profit</span>
            <span className="text-right font-mono font-semibold border-t border-[var(--border)] pt-2">{fmt(data.accounting_profit)}</span>
          </div>

          <div>
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-muted)] mb-2">Addbacks</h2>
            {data.addbacks.length === 0 ? (
              <p className="text-xs text-[var(--text-muted)] italic mb-2">None</p>
            ) : (
              <ul className="space-y-1 mb-2">
                {data.addbacks.map(a => (
                  <li key={a.id} className="flex items-center justify-between text-sm gap-2">
                    <span>{a.description}</span>
                    <span className="flex items-center gap-2 font-mono">
                      {fmt(a.amount)}
                      <button type="button" onClick={() => removeAdj(a.id)} className="print:hidden text-red-500" title="Remove">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-right font-mono text-[var(--text-muted)]">+ {fmt(data.total_addbacks)}</p>
          </div>

          <div>
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-muted)] mb-2">Deductions</h2>
            {data.deductions.length === 0 ? (
              <p className="text-xs text-[var(--text-muted)] italic mb-2">None</p>
            ) : (
              <ul className="space-y-1 mb-2">
                {data.deductions.map(a => (
                  <li key={a.id} className="flex items-center justify-between text-sm gap-2">
                    <span>{a.description}</span>
                    <span className="flex items-center gap-2 font-mono">
                      ({fmt(a.amount)})
                      <button type="button" onClick={() => removeAdj(a.id)} className="print:hidden text-red-500" title="Remove">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-right font-mono text-[var(--text-muted)]">− {fmt(data.total_deductions)}</p>
          </div>

          <div className="grid grid-cols-2 gap-y-2 text-sm max-w-lg border-t border-[var(--border)] pt-4">
            <span className="font-semibold">Taxable income</span>
            <span className="text-right font-mono font-semibold">{fmt(data.taxable_income)}</span>
            <span className="text-[var(--text-muted)]">Estimated tax @ {data.tax_rate}%</span>
            <span className="text-right font-mono font-bold text-lg">{fmt(data.estimated_tax)}</span>
          </div>

          <div className="print:hidden border-t border-[var(--border)] pt-4 space-y-2">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Add adjustment</p>
            <div className="flex flex-wrap gap-2 items-end">
              <select
                value={kind}
                onChange={e => setKind(e.target.value as 'addback' | 'deduction')}
                className="ui-field bg-[var(--bg-page)] rounded-xl"
              >
                <option value="addback">Addback</option>
                <option value="deduction">Deduction</option>
              </select>
              <input
                value={desc}
                onChange={e => setDesc(e.target.value)}
                placeholder="Description"
                className="ui-field flex-1 min-w-[160px] bg-[var(--bg-page)] rounded-xl"
              />
              <input
                type="number" step="0.01"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                placeholder="Amount"
                className="ui-field w-28 bg-[var(--bg-page)] rounded-xl"
              />
              <button
                type="button"
                onClick={addAdj}
                disabled={saving || !desc.trim() || !amount}
                className="inline-flex items-center gap-1 px-4 py-2 bg-[var(--text-primary)] text-white rounded-xl font-bold text-sm disabled:opacity-50"
              >
                <Plus className="w-4 h-4" /> Add
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
