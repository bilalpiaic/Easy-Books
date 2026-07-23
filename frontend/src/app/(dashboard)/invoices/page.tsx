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
import { useTranslation } from "react-i18next"
import { usePRAPortal } from "@/hooks/usePRAPortal"
import StatusBadge from "@/components/StatusBadge"
import { useMessages } from "@/context/MessageContext"

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
  pra_status: string | null
  pra_fiscal_number: string | null
}

interface AgingBuckets {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
  items: { id: number; name: string; number: string; due_date: string; amount: number; days_past: number; bucket: string }[]
}

const PAGE_SIZE = 50
const INVOICE_STATUSES = ['draft', 'sent', 'partial', 'paid', 'overdue']

function InvoicesContent() {
  const { confirm, toast } = useMessages()
  const { t } = useTranslation()
  const { can } = usePermission()
  const fmt = useFmt()
  const { isPortal } = usePRAPortal()
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

  const openCreate = () => router.push('/invoices/new')

  useEffect(() => {
    const customerId = searchParams.get('customer_id')
    if (customerId) {
      apiFetch<{ id: number; name: string }>(`/api/customers/${customerId}`)
        .then(c => setCustomerFilter({ id: c.id, name: c.name }))
        .catch(() => {})
    }
    const from = searchParams.get('date_from')
    const to = searchParams.get('date_to')
    if (from) setDateFrom(from)
    if (to) setDateTo(to)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => { setPage(1) }, [search, status, dateFrom, dateTo, customerFilter])
  useEffect(load, [page, search, status, dateFrom, dateTo, sortBy, sortDir, customerFilter])
  useEffect(() => {
    apiFetch<AgingBuckets>('/api/invoices/aging').then(setAging).catch(() => {})
  }, [])
  useEffect(() => {
    const h = () => openCreate()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!can("invoices")) return <NoAccessBanner resource="invoices" />

  const handleBulkAction = async (action: string) => {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    if (action === 'delete') {
      const ok = await confirm({
        title: `Delete ${ids.length} draft invoice(s)?`,
        confirmLabel: "Delete",
        danger: true,
      })
      if (!ok) return
    }
    if (action === 'void') {
      const ok = await confirm({
        title: `Void ${ids.length} invoice(s)?`,
        confirmLabel: "Void",
        danger: true,
      })
      if (!ok) return
    }
    try {
      const res = await apiFetch<{ affected: number; errors: string[] }>('/api/invoices/bulk', {
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

  const outstanding = invoices.filter(i => i.status !== 'paid').reduce((s, i) => s + i.total, 0)
  const paid = invoices.filter(i => i.status === 'paid').reduce((s, i) => s + i.total, 0)

  return (
    <div className="space-y-6">
      <PrintHeader title="Invoices" orientation="landscape" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">Invoices</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Sales invoices to customers</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => downloadCSV('invoices.csv', invoices.map(i => ({ Number: i.number, Customer: i.customer_name, Date: i.issue_date, Due: i.due_date, Subtotal: i.subtotal, GST: i.gst_amount, Total: i.total, Status: i.status })))}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors print:hidden"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button onClick={openCreate} disabled={!can("invoices", "edit")} className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg hover:bg-[var(--primary-dark)] disabled:opacity-40 disabled:cursor-not-allowed">
            <Plus className="w-4 h-4" />
            New Invoice
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 print:grid-cols-3 gap-3 sm:gap-4">
        <div className="bg-white rounded-lg border border-[var(--border)] p-6">
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Outstanding</p>
          <p className="text-2xl font-bold text-[var(--primary)] mt-2">{fmt(outstanding)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[var(--border)] p-6">
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Collected</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmt(paid)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[var(--border)] p-6">
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Total Invoices</p>
          <p className="text-2xl font-bold text-[var(--text-primary)] mt-2">{total}</p>
        </div>
      </div>

      {isPortal && (() => {
        const today = new Date().toISOString().split("T")[0]
        const todayInvoices = invoices.filter(i => i.issue_date === today)
        const todaySales = todayInvoices.reduce((s, i) => s + i.total, 0)
        const submitted = invoices.filter(i => i.pra_status === "submitted").length
        const failed    = invoices.filter(i => i.pra_status === "failed")
        const pending   = invoices.filter(i => i.pra_status === "pending").length
        return (
          <div className="bg-[#1a1814] text-white rounded-xl px-6 py-4 flex flex-wrap items-center gap-6 print:hidden">
            <div>
              <p className="text-xs text-white/50 uppercase tracking-widest font-bold">Today&apos;s Sales</p>
              <p className="text-xl font-bold font-mono mt-0.5">{fmt(todaySales)}</p>
              <p className="text-[10px] text-white/40 mt-0.5">{todayInvoices.length} invoice{todayInvoices.length !== 1 ? "s" : ""}</p>
            </div>
            <div>
              <p className="text-xs text-white/50 uppercase tracking-widest font-bold">PRA Submitted</p>
              <p className="text-xl font-bold text-emerald-400 mt-0.5">{submitted} ✓</p>
            </div>
            <div>
              <p className="text-xs text-white/50 uppercase tracking-widest font-bold">Failed</p>
              <p className="text-xl font-bold text-red-400 mt-0.5">{failed.length} ✗</p>
            </div>
            <div>
              <p className="text-xs text-white/50 uppercase tracking-widest font-bold">Pending</p>
              <p className="text-xl font-bold text-amber-400 mt-0.5">{pending} ⏳</p>
            </div>
            {failed.length > 0 && (
              <Link
                href={`/invoices/${failed[0].id}`}
                className="ml-auto text-xs text-red-300 border border-red-400/40 rounded-lg px-3 py-1.5 hover:bg-red-900/30 transition-colors"
              >
                Fix Failed →
              </Link>
            )}
          </div>
        )
      })()}

      {customerFilter && (
        <div className="flex items-center gap-2 text-sm">
          <span className="bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20 rounded-full px-3 py-1 font-medium">
            Customer: {customerFilter.name}
          </span>
          <button
            onClick={() => setCustomerFilter(null)}
            className="text-[var(--text-primary)]/40 hover:text-red-500 text-xs transition-colors"
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

      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="hidden md:block print:block overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="sticky top-0 z-10 bg-[var(--bg-page)] border-b border-[var(--border)]">
              <tr>
                <th className="px-4 py-4 w-10 print:hidden">
                  <input type="checkbox"
                    className="rounded border-[var(--border)] accent-[var(--primary)]"
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
                {isPortal && (
                  <th className="px-4 py-4 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">PRA</th>
                )}
                <th className="ui-th print:hidden" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {loading ? (
                <SkeletonRow cols={isPortal ? 9 : 8} />
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={isPortal ? 9 : 8} className="px-6 py-16 text-center">
                    <div className="inline-flex flex-col items-center gap-3">
                      <FileSignature className="w-10 h-10 text-[var(--border)]" />
                      <p className="text-sm text-[var(--text-muted)] font-medium">No invoices yet</p>
                      <button onClick={openCreate} className="px-4 py-2 bg-[var(--primary)] text-white text-sm font-medium rounded-lg hover:bg-[var(--primary-dark)] transition-colors">
                        + Create Invoice
                      </button>
                    </div>
                  </td>
                </tr>
              ) : invoices.map(inv => (
                <tr key={inv.id} className={`hover:bg-[var(--bg-page)]/50 ${inv.status === 'overdue' ? 'bg-red-50/30' : ''} ${selectedIds.has(inv.id) ? 'bg-[var(--primary-light)]' : ''}`}>
                  <td className="px-4 py-4 w-10 print:hidden">
                    <input type="checkbox"
                      className="rounded border-[var(--border)] accent-[var(--primary)]"
                      checked={selectedIds.has(inv.id)}
                      onChange={e => setSelectedIds(prev => {
                        const next = new Set(prev)
                        if (e.target.checked) { next.add(inv.id) } else { next.delete(inv.id) }
                        return next
                      })}
                    />
                  </td>
                  <td className="ui-td font-mono font-bold text-[var(--primary)]">
                    <DocLink type="invoice" id={inv.id} label={inv.number} className="text-[var(--primary)] font-bold" />
                  </td>
                  <td className="ui-td">
                    {inv.customer_id && inv.customer_name
                      ? <DocLink type="customer" id={inv.customer_id} label={inv.customer_name} />
                      : (inv.customer_name ?? '—')}
                  </td>
                  <td className="ui-td text-[var(--text-muted)]">{fmtDate(inv.issue_date)}</td>
                  <td className={`ui-td ${inv.status === 'overdue' ? 'text-red-600 font-medium' : 'text-[var(--text-muted)]'}`}>{fmtDate(inv.due_date)}</td>
                  <td className="ui-td text-right font-mono">{fmt(inv.total)}</td>
                  <td className="ui-td text-center">
                    <StatusBadge status={inv.status} />
                  </td>
                  {isPortal && (
                    <td className="ui-td text-xs">
                      {inv.pra_status === "submitted" && (
                        <span className="text-emerald-700 font-mono">✓ {inv.pra_fiscal_number ?? "FIN"}</span>
                      )}
                      {inv.pra_status === "pending" && (
                        <span className="text-amber-600">⏳ Pending</span>
                      )}
                      {inv.pra_status === "failed" && (
                        <span className="text-red-600 font-medium">✗ Failed</span>
                      )}
                    </td>
                  )}
                  <td className="ui-td print:hidden">
                    <div className="flex items-center justify-end gap-2">
                      {(inv.status === 'draft' || inv.status === 'sent' || inv.status === 'posted' || inv.status === 'overdue') && (
                        <button
                          onClick={() => router.push(`/invoices/${inv.id}/edit`)}
                          className="text-xs px-2 py-1 border border-[var(--primary)]/40 text-[var(--primary)] rounded hover:bg-[var(--bg-page)]"
                        >
                          Edit
                        </button>
                      )}
                      <Link
                        href={`/invoices/${inv.id}/print`}
                        title="Print this invoice"
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
        <div className="md:hidden print:hidden divide-y divide-[var(--border)]">
          {loading ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">Loading…</div>
          ) : invoices.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-[var(--text-muted)]">No invoices yet</div>
          ) : invoices.map(inv => (
            <Link
              key={inv.id}
              href={`/invoices/${inv.id}`}
              className="flex items-start justify-between px-4 py-3 hover:bg-[var(--bg-row-hover)] transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{inv.customer_name ?? "—"}</p>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">{inv.number} · {fmtDate(inv.issue_date)}</p>
              </div>
              <div className="flex flex-col items-end gap-1 ml-3 shrink-0">
                <span className="text-sm font-bold font-mono text-[var(--text-primary)]">{fmt(inv.total)}</span>
                <StatusBadge status={inv.status} />
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
            <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">AR Aging Analysis</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-[var(--border)]">
            {([['Current', aging.current], ['1–30 days', aging['1_30']], ['31–60 days', aging['31_60']], ['61–90 days', aging['61_90']], ['90+ days', aging.over_90]] as [string, number][]).map(([label, val]) => (
              <div key={label} className="p-4 text-center">
                <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest mb-1">{label}</p>
                <p className={`text-lg font-bold font-mono ${Number(val) > 0 ? 'text-red-600' : 'text-[var(--text-muted)]'}`}>{fmt(Number(val))}</p>
              </div>
            ))}
          </div>
          {aging.items && aging.items.filter(i => i.days_past > 0).length > 0 && (
            <div className="border-t border-[var(--border)] overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-[var(--bg-page)]">
                  <tr>
                    <th className="px-4 py-2 text-left font-bold uppercase tracking-widest text-[var(--text-muted)]">Invoice</th>
                    <th className="px-4 py-2 text-left font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.customer', 'Customer')}</th>
                    <th className="px-4 py-2 text-left font-bold uppercase tracking-widest text-[var(--text-muted)]">Due</th>
                    <th className="px-4 py-2 text-right font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.amount', 'Amount')}</th>
                    <th className="px-4 py-2 text-right font-bold uppercase tracking-widest text-red-600">Days Overdue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {aging.items.filter(i => i.days_past > 0).sort((a, b) => b.days_past - a.days_past).slice(0, 10).map(item => (
                    <tr key={item.id} className="hover:bg-red-50/30">
                      <td className="px-4 py-2 font-mono font-bold text-[var(--primary)]">{item.number}</td>
                      <td className="px-4 py-2 text-[var(--text-muted)]">{item.name}</td>
                      <td className="px-4 py-2 text-[var(--text-muted)]">{item.due_date}</td>
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
