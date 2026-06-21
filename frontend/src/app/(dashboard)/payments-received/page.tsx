'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Plus, Search, Printer, Download } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV, fmtDate } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import { useTranslation } from "react-i18next"

interface Payment {
  id: number
  invoice_id: number | null
  customer_name: string | null
  payment_date: string
  amount: number
  method: string
  reference: string | null
}

const PAGE_SIZE = 50

export default function PaymentsReceived() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const router = useRouter()
  const [payments, setPayments] = useState<Payment[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    apiFetch<{ total: number; items: Payment[] }>(`/api/payments-received?${params}`)
      .then(d => { setPayments(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(load, [page])

  const openCreate = () => router.push('/payments-received/new')

  const filtered = payments.filter(p =>
    !search ||
    (p.customer_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
    (p.reference ?? '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <PrintHeader title="Payments Received" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-serif font-medium">Payments Received</h1>
          <p className="text-sm text-black/75 mt-1">Record customer payments and track cash receipts</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => downloadCSV('payments-received.csv', filtered.map(p => ({ Date: p.payment_date, Customer: p.customer_name ?? '', Method: p.method, Reference: p.reference ?? '', Amount: p.amount })))}
            disabled={filtered.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors print:hidden"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" /> Record Payment
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
        <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Received (this page)</p>
        <p className="text-xl sm:text-3xl font-bold text-green-600 mt-2">{fmt(filtered.reduce((s, p) => s + p.amount, 0))}</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input type="text" placeholder="Search by customer or reference..." value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]" />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[520px]">
            <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
              <tr>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">Date</th>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">{t('col.customer', 'Customer')}</th>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">{t('col.reference', 'Ref #')}</th>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">Method</th>
                <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/75">{t('col.amount', 'Amount')}</th>
                <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/75 w-16 print:hidden">{t('common.print', 'Print')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {loading ? (
                <tr><td colSpan={6} className="px-6 py-8 text-center text-black/40">{t('common.loading', 'Loading...')}</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={6} className="px-6 py-8 text-center text-black/40">No payments recorded.</td></tr>
              ) : filtered.map(p => (
                <tr key={p.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="ui-td text-black/70">{fmtDate(p.payment_date)}</td>
                  <td className="ui-td font-medium">
                    {p.invoice_id && p.customer_name
                      ? <DocLink type="invoice" id={p.invoice_id} label={p.customer_name} />
                      : (p.customer_name ?? '—')}
                  </td>
                  <td className="ui-td font-mono text-sm text-black/60">
                    {p.invoice_id
                      ? <DocLink type="invoice" id={p.invoice_id} label={p.reference ?? `INV #${p.invoice_id}`} className="text-black/60" />
                      : (p.reference ?? '—')}
                  </td>
                  <td className="ui-td capitalize text-black/70">{p.method.replace('_', ' ')}</td>
                  <td className="ui-td text-right font-mono font-bold text-green-700">{fmt(p.amount)}</td>
                  <td className="ui-td text-right print:hidden">
                    <Link
                      href={`/payments-received/${p.id}/print`}
                      title="Print receipt"
                      className="inline-flex p-1.5 rounded border border-[#ede9e2] hover:bg-[#faf6ec] text-[#1a1814]/55 hover:text-[#b8943f]"
                    >
                      <Printer className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="border-t border-[#ede9e2] px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>
    </div>
  )
}
