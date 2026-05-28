'use client'

import { Suspense, use, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Printer } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import PrintHeader from '@/components/PrintHeader'

interface StatementInvoice {
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
  customer: { id: number; name: string; email: string | null; phone: string | null; address: string | null }
  period: { from: string; to: string }
  opening_balance: string
  invoices: StatementInvoice[]
  payments: StatementPayment[]
  closing_balance: string
}

function defaultRange() {
  const fmt = useFmt()
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { from: from.toISOString().split('T')[0], to: to.toISOString().split('T')[0] }
}

function CustomerStatementPageInner({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const searchParams = useSearchParams()
  const r0 = defaultRange()
  const [fromDate, setFromDate] = useState(searchParams.get('from') ?? r0.from)
  const [toDate, setToDate] = useState(searchParams.get('to') ?? r0.to)
  const [data, setData] = useState<Statement | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [generatedDate, setGeneratedDate] = useState('')
  useEffect(() => { setGeneratedDate(new Date().toLocaleDateString()) }, [])

  useEffect(() => {
    setLoading(true)
    apiFetch<Statement>(`/api/customers/${id}/statement?from_date=${fromDate}&to_date=${toDate}`)
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id, fromDate, toDate])

  if (error && !data) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (loading && !data) return <p className="p-4 text-[#1a1814]/60 text-sm">Loading statement…</p>
  if (!data) return null

  const c = data.customer
  const closingNum = Number(data.closing_balance)

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <PrintHeader title={`Statement — ${c.name}`} subtitle={`Period: ${data.period.from} to ${data.period.to}`} />

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-2 print:hidden">
        <Link href={`/customers/${id}/ledger`} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-[#1a1814]/65 hover:text-[#b8943f]">
          <ArrowLeft className="w-4 h-4" /> Back to Ledger
        </Link>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <label className="text-black/50">From</label>
            <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)}
              className="px-2 py-1 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-[#b8943f]" />
            <label className="text-black/50">To</label>
            <input type="date" value={toDate} onChange={e => setToDate(e.target.value)}
              className="px-2 py-1 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-[#b8943f]" />
          </div>
          <button onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee]">
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
      </div>

      {/* Statement document */}
      <div className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden print:border-none print:rounded-none print:shadow-none">
        {/* Customer info header */}
        <div className="p-6 border-b border-[#ede9e2]">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-xl font-serif font-semibold">{c.name}</h2>
              {c.email && <p className="text-sm text-black/60 mt-0.5">{c.email}</p>}
              {c.phone && <p className="text-sm text-black/60">{c.phone}</p>}
              {c.address && <p className="text-sm text-black/60">{c.address}</p>}
            </div>
            <div className="text-right">
              <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Account Statement</p>
              <p className="text-sm text-black/60 mt-1">{data.period.from} — {data.period.to}</p>
            </div>
          </div>
        </div>

        {/* Summary row */}
        <div className="grid grid-cols-3 divide-x divide-[#ede9e2] border-b border-[#ede9e2] bg-[#f6f3ee]">
          <div className="px-6 py-4 text-center">
            <p className="text-xs text-black/50 uppercase tracking-widest font-bold mb-1">Opening Balance</p>
            <p className="text-lg font-bold font-mono">{fmt(Number(data.opening_balance))}</p>
          </div>
          <div className="px-6 py-4 text-center">
            <p className="text-xs text-black/50 uppercase tracking-widest font-bold mb-1">Invoices Issued</p>
            <p className="text-lg font-bold font-mono text-[#b8943f]">
              {fmt(data.invoices.reduce((s, i) => s + Number(i.total), 0))}
            </p>
          </div>
          <div className="px-6 py-4 text-center">
            <p className="text-xs text-black/50 uppercase tracking-widest font-bold mb-1">Closing Balance</p>
            <p className={`text-lg font-bold font-mono ${closingNum > 0 ? 'text-red-600' : 'text-green-600'}`}>
              {fmt(closingNum)}
            </p>
            {closingNum > 0 && <p className="text-[10px] text-red-500 mt-0.5">Amount Owed</p>}
          </div>
        </div>

        {/* Invoices */}
        <div className="p-6">
          <h3 className="text-xs font-bold uppercase tracking-widest text-black/50 mb-3">Invoices</h3>
          {data.invoices.length === 0 ? (
            <p className="text-sm text-black/40 italic">No invoices in this period.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#ede9e2]">
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/50">Invoice #</th>
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/50">Date</th>
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/50">Due</th>
                  <th className="py-2 text-center text-[10px] font-bold uppercase tracking-widest text-black/50">Status</th>
                  <th className="py-2 text-right text-[10px] font-bold uppercase tracking-widest text-black/50">Total</th>
                  <th className="py-2 text-right text-[10px] font-bold uppercase tracking-widest text-black/50">Outstanding</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f6f3ee]">
                {data.invoices.map(inv => (
                  <tr key={inv.id}>
                    <td className="py-2 font-mono text-[#b8943f] text-xs">{inv.number}</td>
                    <td className="py-2 text-black/70">{inv.date}</td>
                    <td className="py-2 text-black/70">{inv.due_date}</td>
                    <td className="py-2 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${inv.status === 'paid' ? 'bg-green-100 text-green-700' : inv.status === 'overdue' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}`}>
                        {inv.status}
                      </span>
                    </td>
                    <td className="py-2 text-right font-mono">{fmt(Number(inv.total))}</td>
                    <td className={`py-2 text-right font-mono font-bold ${Number(inv.outstanding) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {fmt(Number(inv.outstanding))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Payments */}
        <div className="px-6 pb-6">
          <h3 className="text-xs font-bold uppercase tracking-widest text-black/50 mb-3">Payments Received</h3>
          {data.payments.length === 0 ? (
            <p className="text-sm text-black/40 italic">No payments in this period.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#ede9e2]">
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/50">Date</th>
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/50">Method</th>
                  <th className="py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/50">Reference</th>
                  <th className="py-2 text-right text-[10px] font-bold uppercase tracking-widest text-black/50">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f6f3ee]">
                {data.payments.map(p => (
                  <tr key={p.id}>
                    <td className="py-2 text-black/70">{p.date}</td>
                    <td className="py-2 capitalize text-black/70">{p.method}</td>
                    <td className="py-2 text-black/50 text-xs">{p.reference ?? '—'}</td>
                    <td className="py-2 text-right font-mono text-green-600">{fmt(Number(p.amount))}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-[#ede9e2]">
                  <td colSpan={3} className="py-2 text-xs font-bold text-black/50 uppercase tracking-widest">Total Paid</td>
                  <td className="py-2 text-right font-mono font-bold text-green-600">
                    {fmt(data.payments.reduce((s, p) => s + Number(p.amount), 0))}
                  </td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-[#f6f3ee] border-t border-[#ede9e2] flex justify-between items-center">
          <p className="text-xs text-black/50">Statement generated {generatedDate}</p>
          <div className="text-right">
            <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Balance Due</p>
            <p className={`text-xl font-bold font-mono ${closingNum > 0 ? 'text-red-600' : 'text-green-600'}`}>
              {fmt(closingNum)}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function CustomerStatementPage({ params }: { params: Promise<{ id: string }> }) {
  return <Suspense><CustomerStatementPageInner params={params} /></Suspense>
}
