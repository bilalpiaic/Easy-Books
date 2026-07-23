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

interface BillPaymentRecord {
  id: number
  bill_id: number | null
  vendor_name: string | null
  payment_date: string
  amount: number
  method: string
  reference: string | null
}

const PAGE_SIZE = 50

export default function BillPayments() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const router = useRouter()
  const [payments, setPayments]     = useState<BillPaymentRecord[]>([])
  const [total, setTotal]           = useState(0)
  const [page, setPage]             = useState(1)
  const [search, setSearch]         = useState('')
  const [loading, setLoading]       = useState(true)

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    apiFetch<{ total: number; items: BillPaymentRecord[] }>(`/api/bill-payments?${params}`)
      .then(d => { setPayments(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(load, [page])

  const openCreate = () => router.push('/bill-payments/new')

  const filtered = payments.filter(p =>
    !search ||
    (p.vendor_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
    (p.reference ?? '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <PrintHeader title="Bill Payments" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">Bill Payments</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Record vendor payments and track cash outflows</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => downloadCSV('bill-payments.csv', filtered.map(p => ({ Date: p.payment_date, Vendor: p.vendor_name ?? '', Method: p.method, Reference: p.reference ?? '', Amount: p.amount })))}
            disabled={filtered.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors print:hidden"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg hover:bg-[var(--primary-dark)]">
            <Plus className="w-4 h-4" /> Pay Bill
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[var(--border)] p-6">
        <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Total Paid (this page)</p>
        <p className="text-xl sm:text-3xl font-bold text-red-600 mt-2">{fmt(filtered.reduce((s, p) => s + p.amount, 0))}</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-[var(--text-muted)]" />
        <input type="text" placeholder="Search by vendor or reference..." value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)]" />
      </div>

      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="hidden md:block overflow-x-auto print:block">
          <table className="w-full text-sm min-w-[520px]">
            <thead className="bg-[var(--bg-page)] border-b border-[var(--border)]">
              <tr>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Date</th>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.vendor', 'Vendor')}</th>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.reference', 'Ref #')}</th>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Method</th>
                <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.amount', 'Amount')}</th>
                <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)] w-16 print:hidden">{t('common.print', 'Print')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {loading ? (
                <tr><td colSpan={6} className="px-6 py-8 text-center text-[var(--text-muted)]">{t('common.loading', 'Loading...')}</td></tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center">
                    <p className="text-[var(--text-muted)] mb-3">No payments recorded.</p>
                    <button onClick={openCreate} className="text-sm text-[var(--primary)] hover:underline font-medium">
                      + Record your first payment
                    </button>
                  </td>
                </tr>
              ) : filtered.map(p => (
                <tr key={p.id} className="hover:bg-[var(--bg-page)]/50">
                  <td className="ui-td text-[var(--text-muted)] whitespace-nowrap">{fmtDate(p.payment_date)}</td>
                  <td className="ui-td font-medium">
                    {p.bill_id && p.vendor_name
                      ? <DocLink type="bill" id={p.bill_id} label={p.vendor_name} />
                      : (p.vendor_name ?? '—')}
                  </td>
                  <td className="ui-td font-mono text-sm text-[var(--text-muted)]">
                    {p.bill_id
                      ? <DocLink type="bill" id={p.bill_id} label={p.reference ?? `BILL #${p.bill_id}`} className="text-[var(--text-muted)]" />
                      : (p.reference ?? '—')}
                  </td>
                  <td className="ui-td capitalize text-[var(--text-muted)]">{p.method.replace('_', ' ')}</td>
                  <td className="ui-td text-right font-mono font-bold text-red-700">{fmt(p.amount)}</td>
                  <td className="ui-td text-right print:hidden">
                    <Link
                      href={`/bill-payments/${p.id}/print`}
                      title="Print voucher"
                      className="inline-flex p-1.5 rounded border border-[var(--border)] hover:bg-[var(--bg-page)] text-[var(--text-primary)]/55 hover:text-[var(--primary)]"
                    >
                      <Printer className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="md:hidden print:hidden divide-y divide-[var(--border)]">
          {loading ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">{t('common.loading', 'Loading...')}</div>
          ) : filtered.length === 0 ? (
            <div className="px-4 py-10 text-center">
              <p className="text-[var(--text-muted)] mb-3 text-sm">No payments recorded.</p>
              <button type="button" onClick={openCreate} className="text-sm text-[var(--primary)] hover:underline font-medium">
                + Record your first payment
              </button>
            </div>
          ) : filtered.map(p => (
            <div key={p.id} className="px-4 py-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[var(--text-primary)] truncate">
                  {p.vendor_name ?? "—"}
                </p>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  {fmtDate(p.payment_date)} · {p.method.replace("_", " ")}
                  {p.reference ? ` · ${p.reference}` : ""}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1.5 shrink-0">
                <span className="text-sm font-mono font-bold text-red-700">{fmt(p.amount)}</span>
                <Link
                  href={`/bill-payments/${p.id}/print`}
                  className="text-xs text-[var(--primary)] underline"
                >
                  Print
                </Link>
              </div>
            </div>
          ))}
        </div>
        <div className="border-t border-[var(--border)] px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>
    </div>
  )
}
