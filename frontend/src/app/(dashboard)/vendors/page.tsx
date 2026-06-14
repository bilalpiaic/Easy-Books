'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Plus, Search, Trash2, Download, Printer, Truck } from 'lucide-react'
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

interface Vendor {
  id: number
  name: string
  email: string | null
  phone: string | null
  address: string | null
  opening_balance: number
  is_active: boolean
}

const PAGE_SIZE = 50

export default function Vendors() {
  const { can } = usePermission()
  if (!can("vendors")) return <NoAccessBanner resource="vendors" />
  const fmt = useFmt()
  const router = useRouter()
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds)
    if (!window.confirm(`Delete ${ids.length} vendor(s)? This cannot be undone.`)) return
    const results = await Promise.allSettled(ids.map(id => apiFetch(`/api/vendors/${id}`, { method: 'DELETE' })))
    const failed = results.filter(r => r.status === 'rejected').length
    if (failed > 0) alert(`${failed} deletion(s) failed — they may have linked bills.`)
    setSelectedIds(new Set())
    load()
  }

  const load = () => {
    setIsLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (search) params.set('search', search)
    apiFetch<{ total: number; items: Vendor[] }>(`/api/vendors?${params}`)
      .then(d => { setVendors(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }

  useEffect(() => { setPage(1) }, [search])
  useEffect(load, [page, search])

  const openAdd = () => router.push('/vendors/new')

  useEffect(() => {
    const h = () => openAdd()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleDelete = async (v: Vendor) => {
    if (!window.confirm(`Delete vendor "${v.name}"? This cannot be undone.`)) return
    try {
      await apiFetch(`/api/vendors/${v.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <PrintHeader title="Vendors" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif font-medium">Vendors</h1>
          <p className="text-sm text-black/75 mt-1">Manage suppliers and track payables</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <CsvImportButton entity="vendors" onSuccess={load} />
          <button
            onClick={() => downloadCSV('vendors.csv', vendors.map(v => ({ Name: v.name, Email: v.email, Phone: v.phone, Address: v.address, Balance: v.opening_balance })))}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
            title="Print"
          >
            <Printer className="w-4 h-4" />
            Print
          </button>
          <button onClick={openAdd} className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" />
            Add Vendor
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Vendors</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-2">{total}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Opening Balance Total</p>
          <p className="text-2xl font-bold text-[#1a1814] mt-2">{fmt(vendors.reduce((s, v) => s + v.opening_balance, 0))}</p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input
          type="text"
          placeholder="Search vendors..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
        />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead className="sticky top-0 z-10 bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-4 py-4 w-10">
                <input type="checkbox"
                  className="rounded border-[#ede9e2] accent-[#b8943f]"
                  checked={vendors.length > 0 && vendors.every(v => selectedIds.has(v.id))}
                  onChange={e => setSelectedIds(e.target.checked ? new Set(vendors.map(v => v.id)) : new Set())}
                />
              </th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">Name</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">Email</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">Phone</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/75">Opening Bal.</th>
              <th className="ui-th text-center text-xs font-bold uppercase tracking-widest text-black/75">Status</th>
              <th className="ui-th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {isLoading ? (
              <SkeletonRow cols={7} />
            ) : vendors.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-16 text-center">
                  <div className="inline-flex flex-col items-center gap-3">
                    <Truck className="w-10 h-10 text-black/20" />
                    <p className="text-sm text-black/40 font-medium">No vendors yet</p>
                    <button onClick={openAdd} className="px-4 py-2 bg-[#b8943f] text-white text-sm font-medium rounded-lg hover:bg-[#a07835] transition-colors">
                      + Add Vendor
                    </button>
                  </div>
                </td>
              </tr>
            ) : vendors.map(v => (
              <tr key={v.id} className={`hover:bg-[#f6f3ee]/50 ${selectedIds.has(v.id) ? 'bg-[#ffd966]/10' : ''}`}>
                <td className="px-4 py-4 w-10">
                  <input type="checkbox"
                    className="rounded border-[#ede9e2] accent-[#b8943f]"
                    checked={selectedIds.has(v.id)}
                    onChange={e => setSelectedIds(prev => {
                      const next = new Set(prev)
                      e.target.checked ? next.add(v.id) : next.delete(v.id)
                      return next
                    })}
                  />
                </td>
                <td className="ui-td font-medium">
                  <DocLink type="vendor" id={v.id} label={v.name} className="font-medium" />
                </td>
                <td className="ui-td text-black/70">{v.email ?? '—'}</td>
                <td className="ui-td text-black/70">{v.phone ?? '—'}</td>
                <td className="ui-td text-right font-mono">{fmt(v.opening_balance)}</td>
                <td className="ui-td text-center">
                  <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${v.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                    {v.is_active ? 'active' : 'inactive'}
                  </span>
                </td>
                <td className="ui-td flex items-center gap-3">
                  <Link href={`/vendors/${v.id}`} className="text-[#b8943f] text-sm font-bold hover:underline">View</Link>
                  <button onClick={() => router.push(`/vendors/${v.id}/edit`)} className="text-[#b8943f] text-sm font-bold hover:underline">Edit</button>
                  <button onClick={() => handleDelete(v)} className="text-red-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
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

      <BulkActionBar
        count={selectedIds.size}
        actions={[{ label: 'Delete Selected', onClick: handleBulkDelete, variant: 'danger' }]}
        onClear={() => setSelectedIds(new Set())}
      />
    </div>
  )
}
