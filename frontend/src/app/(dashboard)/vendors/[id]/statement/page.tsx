'use client'

import { Suspense, use, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Printer, Download } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV, fmtDate, fmtDateJs } from '@/lib/utils'
import PrintHeader from '@/components/PrintHeader'
import DateRangePicker from '@/components/DateRangePicker'
import { useTranslation } from "react-i18next"

interface StatementBill {
  id: number
  number: string
  date: string
  due_date: string
  status: string
  total: string
  outstanding: string
  currency: string
}

interface StatementPayment {
  id: number
  date: string
  method: string
  reference: string | null
  amount: string
}

interface Statement {
  vendor: { id: number; name: string; email: string | null; phone: string | null; address: string | null }
  period: { from: string; to: string }
  opening_balance: string
  bills: StatementBill[]
  payments: StatementPayment[]
  closing_balance: string
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { from: from.toISOString().split('T')[0], to: to.toISOString().split('T')[0] }
}

function VendorStatementPageInner({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()
  const fmt = useFmt()
  const { id } = use(params)
  const searchParams = useSearchParams()
  const r0 = defaultRange()
  const [fromDate, setFromDate] = useState(searchParams.get('from') ?? r0.from)
  const [toDate, setToDate] = useState(searchParams.get('to') ?? r0.to)
  const [data, setData] = useState<Statement | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [generatedDate, setGeneratedDate] = useState('')
  useEffect(() => { setGeneratedDate(fmtDateJs(new Date())) }, [])

  useEffect(() => {
    setLoading(true)
    apiFetch<Statement>(`/api/vendors/${id}/statement?from_date=${fromDate}&to_date=${toDate}`)
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id, fromDate, toDate])

  if (error && !data) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (loading && !data) return <p className="p-4 text-[var(--text-primary)]/60 text-sm">Loading statement…</p>
  if (!data) return null

  const v = data.vendor
  const closingNum = Number(data.closing_balance)

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <PrintHeader title={`Statement — ${v.name}`} subtitle={`Period: ${fmtDate(data.period.from)} to ${fmtDate(data.period.to)}`} />

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-2 print:hidden">
        <Link href={`/vendors/${id}/ledger`} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-[var(--text-primary)]/65 hover:text-[var(--primary)]">
          <ArrowLeft className="w-4 h-4" /> Back to Ledger
        </Link>
        <div className="flex items-center gap-3">
          <DateRangePicker start={fromDate} end={toDate} onStartChange={setFromDate} onEndChange={setToDate} hideAll />
          <button
            onClick={() => downloadCSV(`statement-${v.name}-${fromDate}-${toDate}.csv`, [
              ...data.bills.map(b => ({ Date: b.date, Type: "Bill", Reference: b.number, Debit: Number(b.total), Credit: 0, Outstanding: Number(b.outstanding) })),
              ...data.payments.map(p => ({ Date: p.date, Type: "Payment", Reference: p.reference ?? "", Debit: 0, Credit: Number(p.amount), Outstanding: 0 })),
            ])}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)]">
            <Download className="w-4 h-4" /> CSV
          </button>
          <button onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] print:hidden">
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
        </div>
      </div>

      {/* Statement document */}
      <div className="bg-white border border-[var(--border)] rounded-xl overflow-hidden print:border-none print:rounded-none">
        {/* Vendor info header */}
        <div className="p-6 border-b border-[var(--border)]">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-xl font-bold">{v.name}</h2>
              {v.email && <p className="text-sm text-[var(--text-muted)] mt-0.5">{v.email}</p>}
              {v.phone && <p className="text-sm text-[var(--text-muted)]">{v.phone}</p>}
              {v.address && <p className="text-sm text-[var(--text-muted)]">{v.address}</p>}
            </div>
            <div className="text-right">
              <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Vendor Statement</p>
              <p className="text-sm text-[var(--text-muted)] mt-1">{data.period.from} — {data.period.to}</p>
            </div>
          </div>
        </div>

        {/* Summary row */}
        <div className="grid grid-cols-3 divide-x divide-[var(--border)] border-b border-[var(--border)] bg-[var(--bg-page)]">
          <div className="px-6 py-4 text-center">
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold mb-1">Opening Balance</p>
            <p className="text-lg font-bold font-mono">{fmt(Number(data.opening_balance))}</p>
          </div>
          <div className="px-6 py-4 text-center">
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold mb-1">Bills Received</p>
            <p className="text-lg font-bold font-mono text-orange-600">
              {fmt(data.bills.reduce((s, b) => s + Number(b.total), 0))}
            </p>
          </div>
          <div className="px-6 py-4 text-center">
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold mb-1">Closing Balance</p>
            <p className={`text-lg font-bold font-mono ${closingNum > 0 ? 'text-red-600' : 'text-green-600'}`}>
              {fmt(closingNum)}
            </p>
            {closingNum > 0 && <p className="text-[10px] text-red-500 mt-0.5">Amount Owed to Vendor</p>}
          </div>
        </div>

        {/* Bills */}
        <div className="p-6">
          <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)] mb-3">Bills</h3>
          {data.bills.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)] italic">No bills in this period.</p>
          ) : (
            <div className="table-freeze">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Bill #</th>
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Date</th>
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Due</th>
                  <th className="py-2 text-center text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.status', 'Status')}</th>
                  <th className="py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.total', 'Total')}</th>
                  <th className="py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Outstanding</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {data.bills.map(b => (
                  <tr key={b.id}>
                    <td className="py-2 font-mono text-[var(--primary)] text-xs">{b.number}</td>
                    <td className="py-2 text-[var(--text-muted)]">{fmtDate(b.date)}</td>
                    <td className="py-2 text-[var(--text-muted)]">{b.due_date}</td>
                    <td className="py-2 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${b.status === 'paid' ? 'bg-green-100 text-green-700' : b.status === 'overdue' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="py-2 text-right font-mono">{fmt(Number(b.total))}</td>
                    <td className={`py-2 text-right font-mono font-bold ${Number(b.outstanding) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {fmt(Number(b.outstanding))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>

        {/* Payments */}
        <div className="px-6 pb-6">
          <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)] mb-3">Payments Made</h3>
          {data.payments.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)] italic">No payments in this period.</p>
          ) : (
            <div className="table-freeze">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Date</th>
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Method</th>
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.reference', 'Ref #')}</th>
                  <th className="py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.amount', 'Amount')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {data.payments.map(p => (
                  <tr key={p.id}>
                    <td className="py-2 text-[var(--text-muted)]">{fmtDate(p.date)}</td>
                    <td className="py-2 capitalize text-[var(--text-muted)]">{p.method}</td>
                    <td className="py-2 text-[var(--text-muted)] text-xs">{p.reference ?? '—'}</td>
                    <td className="py-2 text-right font-mono text-green-600">{fmt(Number(p.amount))}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-[var(--border)]">
                  <td colSpan={3} className="py-2 text-xs font-bold text-[var(--text-muted)] uppercase tracking-widest">Total Paid</td>
                  <td className="py-2 text-right font-mono font-bold text-green-600">
                    {fmt(data.payments.reduce((s, p) => s + Number(p.amount), 0))}
                  </td>
                </tr>
              </tfoot>
            </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-[var(--bg-page)] border-t border-[var(--border)] flex justify-between items-center">
          <p className="text-xs text-[var(--text-muted)]">Statement generated {generatedDate}</p>
          <div className="text-right">
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Balance Owed</p>
            <p className={`text-xl font-bold font-mono ${closingNum > 0 ? 'text-red-600' : 'text-green-600'}`}>
              {fmt(closingNum)}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function VendorStatementPage({ params }: { params: Promise<{ id: string }> }) {
  return <Suspense><VendorStatementPageInner params={params} /></Suspense>
}
