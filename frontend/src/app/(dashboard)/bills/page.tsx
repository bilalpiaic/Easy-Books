'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Plus, Download, Printer, Receipt } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import FilterBar from '@/components/FilterBar'
import SortableHeader from '@/components/SortableHeader'
import BulkActionBar from '@/components/BulkActionBar'
import { apiFetch } from '@/lib/api'
import { downloadCSV, fmtDate } from '@/lib/utils'
import { useFmt } from '@/context/SettingsContext'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'
import { usePermission } from "@/context/PermissionContext"
import { NoAccessBanner } from "@/components/NoAccessBanner"
import { useTranslation } from "react-i18next"
import StatusBadge from "@/components/StatusBadge"
import { useMessages } from "@/context/MessageContext"

interface Bill {
  id: number
  number: string
  vendor_id: number | null
  vendor_name: string | null
  bill_date: string
  due_date: string
  subtotal: number
  gst_amount: number
  total: number
  status: string
}

interface AgingBuckets {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
  items: { id: number; name: string; number: string; due_date: string; amount: number; days_past: number; bucket: string }[]
}


const PAGE_SIZE = 50
const BILL_STATUSES = ['draft', 'received', 'partial', 'paid', 'overdue']

function BillsContent() {
  const { confirm, toast } = useMessages()
  const { t } = useTranslation()
  const { can } = usePermission()
  if (!can("bills")) return <NoAccessBanner resource="bills" />
  const fmt = useFmt()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [vendorFilter, setVendorFilter] = useState<{ id: number; name: string } | null>(null)
  const [bills, setBills]       = useState<Bill[]>([])
  const [total, setTotal]       = useState(0)
  const [page, setPage]         = useState(1)
  const [search, setSearch]     = useState('')
  const [status, setStatus]     = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo]     = useState('')
  const [sortBy, setSortBy]     = useState('bill_date')
  const [sortDir, setSortDir]   = useState<'asc' | 'desc'>('desc')
  const [loading, setLoading]   = useState(true)
  const [aging, setAging]       = useState<AgingBuckets | null>(null)
  const [selectedIds, setSelectedIds]   = useState<Set<number>>(new Set())

  useEffect(() => {
    const vendorId = searchParams.get('vendor_id')
    if (vendorId) {
      apiFetch<{ id: number; name: string }>(`/api/vendors/${vendorId}`)
        .then(v => setVendorFilter({ id: v.id, name: v.name }))
        .catch(() => {})
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleBulkAction = async (action: string) => {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    if (action === 'delete') {
      const ok = await confirm({
        title: `Delete ${ids.length} draft bill(s)?`,
        confirmLabel: "Delete",
        danger: true,
      })
      if (!ok) return
    }
    if (action === 'void') {
      const ok = await confirm({
        title: `Void ${ids.length} bill(s)?`,
        confirmLabel: "Void",
        danger: true,
      })
      if (!ok) return
    }
    try {
      const res = await apiFetch<{ affected: number; errors: string[] }>('/api/bills/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids, action }),
      })
      if (res.errors.length > 0) toast(res.errors.join("\n"), "error")
      setSelectedIds(new Set())
      load()
    } catch (err) {
      toast((err as Error).message, "error")
    }
  }

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({
      skip: String((page - 1) * PAGE_SIZE),
      limit: String(PAGE_SIZE),
      sort_by: sortBy,
      sort_dir: sortDir,
    })
    if (search)          params.set('search',    search)
    if (status)          params.set('status',    status)
    if (dateFrom)        params.set('date_from', dateFrom)
    if (dateTo)          params.set('date_to',   dateTo)
    if (vendorFilter)    params.set('vendor_id', String(vendorFilter.id))
    apiFetch<{ total: number; items: Bill[] }>(`/api/bills?${params}`)
      .then(d => { setBills(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  const handleSort = (field: string, dir: 'asc' | 'desc') => {
    setSortBy(field); setSortDir(dir); setPage(1)
  }

  useEffect(() => { setPage(1) }, [search, status, dateFrom, dateTo, vendorFilter])
  useEffect(load, [page, search, status, dateFrom, dateTo, sortBy, sortDir, vendorFilter])
  useEffect(() => {
    apiFetch<AgingBuckets>('/api/bills/aging').then(setAging).catch(() => {})
  }, [])

  const openCreate = () => router.push('/bills/new')

  useEffect(() => {
    const h = () => openCreate()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const payable = bills.filter(b => b.status !== 'paid').reduce((s, b) => s + b.total, 0)
  const paid    = bills.filter(b => b.status === 'paid').reduce((s, b) => s + b.total, 0)

  return (
    <div className="space-y-6">
      <PrintHeader title="Bills" orientation="landscape" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">Bills</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Vendor bills and purchase liabilities</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => downloadCSV('bills.csv', bills.map(b => ({ Number: b.number, Vendor: b.vendor_name, Date: b.bill_date, Due: b.due_date, Subtotal: b.subtotal, GST: b.gst_amount, Total: b.total, Status: b.status })))}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Download className="w-4 h-4" /> Export
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors print:hidden"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg hover:bg-[var(--primary-dark)]">
            <Plus className="w-4 h-4" /> New Bill
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
        <div className="bg-white rounded-lg border border-[var(--border)] p-6">
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Total Payable</p>
          <p className="text-2xl font-bold text-orange-600 mt-2">{fmt(payable)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[var(--border)] p-6">
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Total Paid</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmt(paid)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[var(--border)] p-6">
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Total Bills</p>
          <p className="text-2xl font-bold text-[var(--text-primary)] mt-2">{total}</p>
        </div>
      </div>

      {vendorFilter && (
        <div className="flex items-center gap-2 text-sm">
          <span className="bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20 rounded-full px-3 py-1 font-medium">
            Vendor: {vendorFilter.name}
          </span>
          <button
            onClick={() => setVendorFilter(null)}
            className="text-[var(--text-primary)]/40 hover:text-red-500 text-xs transition-colors"
          >
            Clear filter
          </button>
        </div>
      )}

      <FilterBar
        search={search} onSearch={setSearch}
        statuses={BILL_STATUSES} status={status} onStatus={setStatus}
        dateFrom={dateFrom} dateTo={dateTo}
        onDateFrom={setDateFrom} onDateTo={setDateTo}
        placeholder="Search by bill # or vendor…"
      />

      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="sticky top-0 z-10 bg-[var(--bg-page)] border-b border-[var(--border)]">
              <tr>
                <th className="px-4 py-4 w-10 print:hidden">
                  <input type="checkbox"
                    className="rounded border-[var(--border)] accent-[var(--primary)]"
                    checked={bills.length > 0 && bills.every(b => selectedIds.has(b.id))}
                    onChange={e => setSelectedIds(e.target.checked ? new Set(bills.map(b => b.id)) : new Set())}
                  />
                </th>
                <SortableHeader label="Bill #"     field="number"      sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Vendor"     field="vendor_name" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Bill Date"  field="bill_date"   sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Due Date"   field="due_date"    sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Total"      field="total"       sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-right" />
                <SortableHeader label="Status"     field="status"      sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-center" />
                <th className="ui-th print:hidden" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {loading ? (
                <SkeletonRow cols={8} />
              ) : bills.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-16 text-center">
                    <div className="inline-flex flex-col items-center gap-3">
                      <Receipt className="w-10 h-10 text-[var(--border)]" />
                      <p className="text-sm text-[var(--text-muted)] font-medium">No bills yet</p>
                      <button onClick={openCreate} className="px-4 py-2 bg-[var(--primary)] text-white text-sm font-medium rounded-lg hover:bg-[var(--primary-dark)] transition-colors">
                        + Record Bill
                      </button>
                    </div>
                  </td>
                </tr>
              ) : bills.map(b => (
                <tr key={b.id} className={`hover:bg-[var(--bg-page)]/50 ${b.status === 'overdue' ? 'bg-red-50/30' : ''} ${selectedIds.has(b.id) ? 'bg-[var(--primary-light)]' : ''}`}>
                  <td className="px-4 py-4 w-10 print:hidden">
                    <input type="checkbox"
                      className="rounded border-[var(--border)] accent-[var(--primary)]"
                      checked={selectedIds.has(b.id)}
                      onChange={e => setSelectedIds(prev => {
                        const next = new Set(prev)
                        e.target.checked ? next.add(b.id) : next.delete(b.id)
                        return next
                      })}
                    />
                  </td>
                  <td className="ui-td font-mono font-bold text-[var(--primary)]">
                    <DocLink type="bill" id={b.id} label={b.number} className="text-[var(--primary)] font-bold" />
                  </td>
                  <td className="ui-td">
                    {b.vendor_id && b.vendor_name
                      ? <DocLink type="vendor" id={b.vendor_id} label={b.vendor_name} />
                      : (b.vendor_name ?? '—')}
                  </td>
                  <td className="ui-td text-[var(--text-muted)]">{fmtDate(b.bill_date)}</td>
                  <td className={`ui-td ${b.status === 'overdue' ? 'text-red-600 font-medium' : 'text-[var(--text-muted)]'}`}>{fmtDate(b.due_date)}</td>
                  <td className="ui-td text-right font-mono">{fmt(b.total)}</td>
                  <td className="ui-td text-center">
                    <StatusBadge status={b.status} />
                  </td>
                  <td className="ui-td print:hidden">
                    <div className="flex items-center justify-end gap-2">
                      {(b.status === 'draft' || b.status === 'received' || b.status === 'overdue') && (
                        <button
                          onClick={() => router.push(`/bills/${b.id}/edit`)}
                          className="text-xs px-2 py-1 border border-[var(--primary)]/40 text-[var(--primary)] rounded hover:bg-[var(--bg-page)]"
                        >
                          Edit
                        </button>
                      )}
                      <Link
                        href={`/bills/${b.id}/print`}
                        title="Print this bill"
                        className="p-1.5 rounded border border-[var(--border)] hover:bg-[var(--bg-page)] text-[var(--text-primary)]/55 hover:text-[var(--primary)]"
                      >
                        <Printer className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile card list */}
        <div className="md:hidden divide-y divide-[var(--border)]">
          {loading ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">Loading…</div>
          ) : bills.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-[var(--text-muted)]">No bills yet</div>
          ) : bills.map(b => (
            <Link
              key={b.id}
              href={`/bills/${b.id}`}
              className="flex items-start justify-between px-4 py-3 hover:bg-[var(--bg-row-hover)] transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{b.vendor_name ?? "—"}</p>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">{b.number} · {fmtDate(b.bill_date)}</p>
              </div>
              <div className="flex flex-col items-end gap-1 ml-3 shrink-0">
                <span className="text-sm font-bold font-mono text-[var(--text-primary)]">{fmt(b.total)}</span>
                <StatusBadge status={b.status} />
              </div>
            </Link>
          ))}
        </div>

        <div className="border-t border-[var(--border)] px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>

      {aging && (
        <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
          <div className="px-6 py-4 border-b border-[var(--border)]">
            <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">AP Aging Analysis</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-[var(--border)]">
            {([['Current', aging.current], ['1–30 days', aging['1_30']], ['31–60 days', aging['31_60']], ['61–90 days', aging['61_90']], ['90+ days', aging.over_90]] as [string, number][]).map(([label, val]) => (
              <div key={label} className="p-4 text-center">
                <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest mb-1">{label}</p>
                <p className={`text-lg font-bold font-mono ${Number(val) > 0 ? 'text-orange-600' : 'text-[var(--text-muted)]'}`}>{fmt(Number(val))}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <BulkActionBar
        count={selectedIds.size}
        actions={[
          { label: 'Mark Received', onClick: () => handleBulkAction('mark_received') },
          { label: 'Void', onClick: () => handleBulkAction('void'), variant: 'danger' },
          { label: 'Delete', onClick: () => handleBulkAction('delete'), variant: 'danger' },
        ]}
        onClear={() => setSelectedIds(new Set())}
      />
    </div>
  )
}

export default function Bills() {
  return (
    <Suspense>
      <BillsContent />
    </Suspense>
  )
}
