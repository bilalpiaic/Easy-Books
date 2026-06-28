'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Plus, Search, Trash2, Download, Printer, Users } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import BulkActionBar from '@/components/BulkActionBar'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'
import CsvImportButton from '@/components/CsvImportButton'
import { usePermission } from "@/context/PermissionContext"
import { NoAccessBanner } from "@/components/NoAccessBanner"
import { useTranslation } from "react-i18next"

interface Customer {
  id: number
  name: string
  email: string | null
  phone: string | null
  address: string | null
  opening_balance: number
  is_active: boolean
}

const PAGE_SIZE = 50

export default function Customers() {
  const { t } = useTranslation()

  const { can } = usePermission()
  if (!can("customers")) return <NoAccessBanner resource="customers" />
  const fmt = useFmt()
  const router = useRouter()
  const [customers, setCustomers] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds)
    if (!window.confirm(`Delete ${ids.length} customer(s)? This cannot be undone.`)) return
    const results = await Promise.allSettled(ids.map(id => apiFetch(`/api/customers/${id}`, { method: 'DELETE' })))
    const failed = results.filter(r => r.status === 'rejected').length
    if (failed > 0) alert(`${failed} deletion(s) failed — they may have linked invoices.`)
    setSelectedIds(new Set())
    load()
  }

  const load = () => {
    setIsLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (search) params.set('search', search)
    apiFetch<{ total: number; items: Customer[] }>(`/api/customers?${params}`)
      .then(d => { setCustomers(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }

  useEffect(() => { setPage(1) }, [search])
  useEffect(load, [page, search])

  const openAdd = () => router.push('/customers/new')

  useEffect(() => {
    const h = () => openAdd()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleDelete = async (c: Customer) => {
    if (!window.confirm(`Delete customer "${c.name}"? This cannot be undone.`)) return
    try {
      await apiFetch(`/api/customers/${c.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const totalOutstanding = customers.reduce((s, c) => s + c.opening_balance, 0)

  return (
    <div className="space-y-6">
      <PrintHeader title="Customers" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">Customers</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Manage customers and track credit accounts</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <CsvImportButton entity="customers" onSuccess={load} />
          <button
            onClick={() => downloadCSV('customers.csv', customers.map(c => ({ Name: c.name, Email: c.email, Phone: c.phone, Address: c.address, Balance: c.opening_balance })))}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
            title="Print"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button onClick={openAdd} className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg hover:bg-[var(--primary-dark)]">
            <Plus className="w-4 h-4" />
            Add Customer
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-[var(--border)] p-6">
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Total Customers</p>
          <p className="text-2xl font-bold text-[var(--primary)] mt-2">{total}</p>
        </div>
        <div className="bg-white rounded-lg border border-[var(--border)] p-6">
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-bold">Opening Balance Total</p>
          <p className="text-2xl font-bold text-[var(--text-primary)] mt-2">{fmt(totalOutstanding)}</p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-[var(--text-muted)]" />
        <input
          type="text"
          placeholder="Search customers..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
        />
      </div>

      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead className="sticky top-0 z-10 bg-[var(--bg-page)] border-b border-[var(--border)]">
            <tr>
              <th className="px-4 py-4 w-10">
                <input type="checkbox"
                  className="rounded border-[var(--border)] accent-[var(--primary)]"
                  checked={customers.length > 0 && customers.every(c => selectedIds.has(c.id))}
                  onChange={e => setSelectedIds(e.target.checked ? new Set(customers.map(c => c.id)) : new Set())}
                />
              </th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Name</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Email</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Phone</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Opening Bal.</th>
              <th className="ui-th text-center text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">{t('col.status', 'Status')}</th>
              <th className="ui-th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {isLoading ? (
              <SkeletonRow cols={7} />
            ) : customers.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-16 text-center">
                  <div className="inline-flex flex-col items-center gap-3">
                    <Users className="w-10 h-10 text-[var(--border)]" />
                    <p className="text-sm text-[var(--text-muted)] font-medium">No customers yet</p>
                    <button onClick={openAdd} className="px-4 py-2 bg-[var(--primary)] text-white text-sm font-medium rounded-lg hover:bg-[var(--primary-dark)] transition-colors">
                      + Add Customer
                    </button>
                  </div>
                </td>
              </tr>
            ) : customers.map(c => (
              <tr key={c.id} className={`hover:bg-[var(--bg-page)]/50 ${selectedIds.has(c.id) ? 'bg-[var(--primary-light)]' : ''}`}>
                <td className="px-4 py-4 w-10">
                  <input type="checkbox"
                    className="rounded border-[var(--border)] accent-[var(--primary)]"
                    checked={selectedIds.has(c.id)}
                    onChange={e => setSelectedIds(prev => {
                      const next = new Set(prev)
                      e.target.checked ? next.add(c.id) : next.delete(c.id)
                      return next
                    })}
                  />
                </td>
                <td className="ui-td font-medium">
                  <DocLink type="customer" id={c.id} label={c.name} className="font-medium" />
                </td>
                <td className="ui-td text-[var(--text-muted)]">{c.email ?? '—'}</td>
                <td className="ui-td text-[var(--text-muted)]">{c.phone ?? '—'}</td>
                <td className="ui-td text-right font-mono">{fmt(c.opening_balance)}</td>
                <td className="ui-td text-center">
                  <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${c.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                    {c.is_active ? 'active' : 'inactive'}
                  </span>
                </td>
                <td className="ui-td flex items-center gap-3">
                  <Link href={`/customers/${c.id}`} className="text-[var(--primary)] text-sm font-bold hover:underline">View</Link>
                  <button onClick={() => router.push(`/customers/${c.id}/edit`)} className="text-[var(--primary)] text-sm font-bold hover:underline">Edit</button>
                  <button onClick={() => handleDelete(c)} className="text-red-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>

        {/* Mobile card list */}
        <div className="md:hidden divide-y divide-[var(--border)]">
          {isLoading ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">Loading…</div>
          ) : customers.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-[var(--text-muted)]">No customers yet</div>
          ) : customers.map(c => (
            <Link
              key={c.id}
              href={`/customers/${c.id}`}
              className="flex items-center justify-between px-4 py-3 hover:bg-[var(--bg-row-hover)] transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{c.name}</p>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">{c.email || c.phone || "—"}</p>
              </div>
              <div className="text-right ml-3 shrink-0">
                <p className="text-sm font-bold font-mono text-[var(--text-primary)]">{fmt(c.opening_balance)}</p>
                <p className="text-xs text-[var(--text-muted)]">balance</p>
              </div>
            </Link>
          ))}
        </div>

        <div className="border-t border-[var(--border)] px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>

      <BulkActionBar
        count={selectedIds.size}
        actions={[{ label: 'Delete Selected', onClick: handleBulkDelete, variant: 'danger' }]}
        onClear={() => setSelectedIds(new Set())}
      />
    </div>
  )
}
