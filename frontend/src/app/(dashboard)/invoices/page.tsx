'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Plus, Download, Printer, FileSignature } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import FilterBar from '@/components/FilterBar'
import SortableHeader from '@/components/SortableHeader'
import BulkActionBar from '@/components/BulkActionBar'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV, fmtDate } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'
import { usePermission } from "@/context/PermissionContext"
import { NoAccessBanner } from "@/components/NoAccessBanner"

interface Invoice {
  id: number
  number: string
  customer_id: number | null
  customer_name: string | null
  issue_date: string
  due_date: string
  subtotal: number
  gst_amount: number
  total: number
  status: string
  description: string | null
  notes: string | null
  internal_memo: string | null
}

interface AgingBuckets {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
  items: { id: number; name: string; number: string; due_date: string; amount: number; days_past: number; bucket: string }[]
}

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  sent: 'bg-blue-100 text-blue-700',
  paid: 'bg-green-100 text-green-700',
  overdue: 'bg-red-100 text-red-700',
  partial: 'bg-amber-100 text-amber-700',
}

const PAGE_SIZE = 50
const INVOICE_STATUSES = ['draft', 'sent', 'partial', 'paid', 'overdue']

function InvoicesContent() {
  const { can } = usePermission()
  if (!can("invoices")) return <NoAccessBanner resource="invoices" />
  const fmt = useFmt()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [customerFilter, setCustomerFilter] = useState<{ id: number; name: string } | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sortBy, setSortBy] = useState('issue_date')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [loading, setLoading] = useState(true)
  const [aging, setAging] = useState<AgingBuckets | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    const customerId = searchParams.get('customer_id')
    if (customerId) {
      apiFetch<{ id: number; name: string }>(`/api/customers/${customerId}`)
        .then(c => setCustomerFilter({ id: c.id, name: c.name }))
        .catch(() => {})
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({
      skip: String((page - 1) * PAGE_SIZE),
      limit: String(PAGE_SIZE),
      sort_by: sortBy,
      sort_dir: sortDir,
    })
    if (search)         params.set('search', search)
    if (status)         params.set('status', status)
    if (dateFrom)       params.set('date_from', dateFrom)
    if (dateTo)         params.set('date_to', dateTo)
    if (customerFilter) params.set('customer_id', String(customerFilter.id))
    apiFetch<{ total: number; items: Invoice[] }>(`/api/invoices?${params}`)
      .then(d => { setInvoices(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  const handleSort = (field: string, dir: 'asc' | 'desc') => {
    setSortBy(field); setSortDir(dir); setPage(1)
  }

  useEffect(() => { setPage(1) }, [search, status, dateFrom, dateTo, customerFilter])
  useEffect(load, [page, search, status, dateFrom, dateTo, sortBy, sortDir, customerFilter])
  useEffect(() => {
    apiFetch<AgingBuckets>('/api/invoices/aging').then(setAging).catch(() => {})
  }, [])

  const openCreate = () => router.push('/invoices/new')

  useEffect(() => {
    const h = () => openCreate()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleBulkAction = async (action: string) => {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    if (action === 'delete' && !window.confirm(`Delete ${ids.length} draft invoice(s)?`)) return
    if (action === 'void' && !window.confirm(`Void ${ids.length} invoice(s)?`)) return
    try {
      const res = await apiFetch<{ affected: number; errors: string[] }>('/api/invoices/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids, action }),
      })
      if (res.errors.length > 0) alert(res.errors.join('\n'))
      setSelectedIds(new Set())
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const handleStatusChange = async (inv: Invoice, newStatus: string) => {
    try {
      await apiFetch(`/api/invoices/${inv.id}/status?status=${newStatus}`, { method: 'PATCH' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const outstanding = invoices.filter(i => i.status !== 'paid').reduce((s, i) => s + i.total, 0)
  const paid = invoices.filter(i => i.status === 'paid').reduce((s, i) => s + i.total, 0)

  return (
    <div className="space-y-6">
      <PrintHeader title="Invoices" orientation="landscape" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif font-medium">Invoices</h1>
          <p className="text-sm text-black/75 mt-1">Sales invoices to customers</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => downloadCSV('invoices.csv', invoices.map(i => ({ Number: i.number, Customer: i.customer_name, Date: i.issue_date, Due: i.due_date, Subtotal: i.subtotal, GST: i.gst_amount, Total: i.total, Status: i.status })))}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors print:hidden"
          >
            <Printer className="w-4 h-4" />
            Print
          </button>
          <button onClick={openCreate} disabled={!can("invoices", "edit")} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35] disabled:opacity-40 disabled:cursor-not-allowed">
            <Plus className="w-4 h-4" />
            New Invoice
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Outstanding</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-2">{fmt(outstanding)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Collected</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmt(paid)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Invoices</p>
          <p className="text-2xl font-bold text-[#1a1814] mt-2">{total}</p>
        </div>
      </div>

      {customerFilter && (
        <div className="flex items-center gap-2 text-sm">
          <span className="bg-[#b8943f]/10 text-[#b8943f] border border-[#b8943f]/20 rounded-full px-3 py-1 font-medium">
            Customer: {customerFilter.name}
          </span>
          <button
            onClick={() => setCustomerFilter(null)}
            className="text-[#1a1814]/40 hover:text-red-500 text-xs transition-colors"
          >
            Clear filter
          </button>
        </div>
      )}

      <FilterBar
        search={search} onSearch={setSearch}
        statuses={INVOICE_STATUSES} status={status} onStatus={setStatus}
        dateFrom={dateFrom} dateTo={dateTo}
        onDateFrom={setDateFrom} onDateTo={setDateTo}
        placeholder="Search by invoice # or customer…"
      />

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="sticky top-0 z-10 bg-[#f6f3ee] border-b border-[#ede9e2]">
              <tr>
                <th className="px-4 py-4 w-10 print:hidden">
                  <input type="checkbox"
                    className="rounded border-[#ede9e2] accent-[#b8943f]"
                    checked={invoices.length > 0 && invoices.every(i => selectedIds.has(i.id))}
                    onChange={e => setSelectedIds(e.target.checked ? new Set(invoices.map(i => i.id)) : new Set())}
                  />
                </th>
                <SortableHeader label="Invoice #"  field="number"        sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Customer"   field="customer_name" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Issue Date" field="issue_date"    sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Due Date"   field="due_date"      sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Total"      field="total"         sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-right" />
                <SortableHeader label="Status"     field="status"        sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-center" />
                <th className="ui-th print:hidden" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {loading ? (
                <SkeletonRow cols={8} />
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-16 text-center">
                    <div className="inline-flex flex-col items-center gap-3">
                      <FileSignature className="w-10 h-10 text-black/20" />
                      <p className="text-sm text-black/40 font-medium">No invoices yet</p>
                      <button onClick={openCreate} className="px-4 py-2 bg-[#b8943f] text-white text-sm font-medium rounded-lg hover:bg-[#a07835] transition-colors">
                        + Create Invoice
                      </button>
                    </div>
                  </td>
                </tr>
              ) : invoices.map(inv => (
                <tr key={inv.id} className={`hover:bg-[#f6f3ee]/50 ${inv.status === 'overdue' ? 'bg-red-50/30' : ''} ${selectedIds.has(inv.id) ? 'bg-[#ffd966]/10' : ''}`}>
                  <td className="px-4 py-4 w-10 print:hidden">
                    <input type="checkbox"
                      className="rounded border-[#ede9e2] accent-[#b8943f]"
                      checked={selectedIds.has(inv.id)}
                      onChange={e => setSelectedIds(prev => {
                        const next = new Set(prev)
                        e.target.checked ? next.add(inv.id) : next.delete(inv.id)
                        return next
                      })}
                    />
                  </td>
                  <td className="ui-td font-mono font-bold text-[#b8943f]">
                    <DocLink type="invoice" id={inv.id} label={inv.number} className="text-[#b8943f] font-bold" />
                  </td>
                  <td className="ui-td">
                    {inv.customer_id && inv.customer_name
                      ? <DocLink type="customer" id={inv.customer_id} label={inv.customer_name} />
                      : (inv.customer_name ?? '—')}
                  </td>
                  <td className="ui-td text-black/70">{fmtDate(inv.issue_date)}</td>
                  <td className={`ui-td ${inv.status === 'overdue' ? 'text-red-600 font-medium' : 'text-black/70'}`}>{fmtDate(inv.due_date)}</td>
                  <td className="ui-td text-right font-mono">{fmt(inv.total)}</td>
                  <td className="ui-td text-center">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${statusColors[inv.status] ?? 'bg-gray-100 text-gray-700'}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td className="ui-td print:hidden">
                    <div className="flex items-center justify-end gap-2">
                      {(inv.status === 'draft' || inv.status === 'sent' || inv.status === 'posted' || inv.status === 'overdue') && (
                        <button
                          onClick={() => router.push(`/invoices/${inv.id}/edit`)}
                          className="text-xs px-2 py-1 border border-[#b8943f]/40 text-[#b8943f] rounded hover:bg-[#faf6ec]"
                        >
                          Edit
                        </button>
                      )}
                      <Link
                        href={`/invoices/${inv.id}/print`}
                        title="Print this invoice"
                        className="p-1.5 rounded border border-[#ede9e2] hover:bg-[#faf6ec] text-[#1a1814]/55 hover:text-[#b8943f]"
                      >
                        <Printer className="w-3.5 h-3.5" />
                      </Link>
                      <select
                        value={inv.status}
                        onChange={e => handleStatusChange(inv, e.target.value)}
                        className="text-xs border border-[#ede9e2] rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#b8943f]"
                      >
                        {INVOICE_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
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

      {aging && (
        <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
          <div className="px-6 py-4 border-b border-[#ede9e2]">
            <h3 className="text-xs font-bold uppercase tracking-widest text-black/75">AR Aging Analysis</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-[#ede9e2]">
            {([['Current', aging.current], ['1–30 days', aging['1_30']], ['31–60 days', aging['31_60']], ['61–90 days', aging['61_90']], ['90+ days', aging.over_90]] as [string, number][]).map(([label, val]) => (
              <div key={label} className="p-4 text-center">
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">{label}</p>
                <p className={`text-lg font-bold font-mono ${Number(val) > 0 ? 'text-red-600' : 'text-black/40'}`}>{fmt(Number(val))}</p>
              </div>
            ))}
          </div>
          {aging.items && aging.items.filter(i => i.days_past > 0).length > 0 && (
            <div className="border-t border-[#ede9e2] overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-[#f6f3ee]">
                  <tr>
                    <th className="px-4 py-2 text-left font-bold uppercase tracking-widest text-black/50">Invoice</th>
                    <th className="px-4 py-2 text-left font-bold uppercase tracking-widest text-black/50">Customer</th>
                    <th className="px-4 py-2 text-left font-bold uppercase tracking-widest text-black/50">Due</th>
                    <th className="px-4 py-2 text-right font-bold uppercase tracking-widest text-black/50">Amount</th>
                    <th className="px-4 py-2 text-right font-bold uppercase tracking-widest text-red-600">Days Overdue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ede9e2]">
                  {aging.items.filter(i => i.days_past > 0).sort((a, b) => b.days_past - a.days_past).slice(0, 10).map(item => (
                    <tr key={item.id} className="hover:bg-red-50/30">
                      <td className="px-4 py-2 font-mono font-bold text-[#b8943f]">{item.number}</td>
                      <td className="px-4 py-2 text-black/70">{item.name}</td>
                      <td className="px-4 py-2 text-black/60">{item.due_date}</td>
                      <td className="px-4 py-2 text-right font-mono">{fmt(item.amount)}</td>
                      <td className="px-4 py-2 text-right font-bold text-red-600">{item.days_past}d</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <BulkActionBar
        count={selectedIds.size}
        actions={[
          { label: 'Mark Sent', onClick: () => handleBulkAction('mark_sent') },
          { label: 'Void', onClick: () => handleBulkAction('void'), variant: 'danger' },
          { label: 'Delete', onClick: () => handleBulkAction('delete'), variant: 'danger' },
        ]}
        onClear={() => setSelectedIds(new Set())}
      />
    </div>
  )
}

export default function Invoices() {
  return (
    <Suspense>
      <InvoicesContent />
    </Suspense>
  )
}
