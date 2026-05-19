'use client'

import { useEffect, useState } from 'react'
import { Plus, Search, Trash2, Download } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { fmtPKR, downloadCSV } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'
import CsvImportButton from '@/components/CsvImportButton'

interface Vendor {
  id: number
  name: string
  email: string | null
  phone: string | null
  address: string | null
  opening_balance: number
  is_active: boolean
}

interface FormState {
  name: string
  email: string
  phone: string
  address: string
  opening_balance: string
}

const emptyForm: FormState = { name: '', email: '', phone: '', address: '', opening_balance: '0' }
const PAGE_SIZE = 50

export default function Vendors() {
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editVendor, setEditVendor] = useState<Vendor | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

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

  const openAdd = () => { setEditVendor(null); setForm(emptyForm); setFormError(''); setModalOpen(true) }
  const openEdit = (v: Vendor) => {
    setEditVendor(v)
    setForm({ name: v.name, email: v.email ?? '', phone: v.phone ?? '', address: v.address ?? '', opening_balance: String(v.opening_balance) })
    setFormError('')
    setModalOpen(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) { setFormError('Name is required.'); return }
    setSaving(true); setFormError('')
    try {
      const body = { name: form.name, email: form.email || null, phone: form.phone || null, address: form.address || null, opening_balance: parseFloat(form.opening_balance) || 0 }
      if (editVendor) {
        await apiFetch(`/api/vendors/${editVendor.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      } else {
        await apiFetch('/api/vendors', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      }
      setModalOpen(false); load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

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
    <div className="space-y-6 p-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
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
          <p className="text-2xl font-bold text-[#1a1814] mt-2">{fmtPKR(vendors.reduce((s, v) => s + v.opening_balance, 0))}</p>
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
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Name</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Email</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Phone</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/75">Opening Bal.</th>
              <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-black/75">Status</th>
              <th className="px-6 py-4"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {isLoading ? (
              <SkeletonRow cols={6} />
            ) : vendors.length === 0 ? (
              <tr><td colSpan={6} className="px-6 py-8 text-center text-black/40">No vendors found.</td></tr>
            ) : vendors.map(v => (
              <tr key={v.id} className="hover:bg-[#f6f3ee]/50">
                <td className="px-6 py-4 font-medium">{v.name}</td>
                <td className="px-6 py-4 text-black/70">{v.email ?? '—'}</td>
                <td className="px-6 py-4 text-black/70">{v.phone ?? '—'}</td>
                <td className="px-6 py-4 text-right font-mono">{fmtPKR(v.opening_balance)}</td>
                <td className="px-6 py-4 text-center">
                  <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${v.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                    {v.is_active ? 'active' : 'inactive'}
                  </span>
                </td>
                <td className="px-6 py-4 flex items-center gap-3">
                  <button onClick={() => openEdit(v)} className="text-[#b8943f] text-sm font-bold hover:underline">Edit</button>
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

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-8">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">{editVendor ? 'Edit Vendor' : 'Add Vendor'}</h2>
            <div className="space-y-4">
              {(['name', 'email', 'phone', 'address'] as const).map(field => (
                <div key={field}>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1 capitalize">{field}</label>
                  <input
                    value={form[field]}
                    onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))}
                    className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
                    placeholder={field === 'name' ? 'Vendor name' : ''}
                  />
                </div>
              ))}
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Opening Balance</label>
                <input
                  type="number" step="0.01"
                  value={form.opening_balance}
                  onChange={e => setForm(p => ({ ...p, opening_balance: e.target.value }))}
                  className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
                />
              </div>
              {formError && <p className="text-red-600 text-sm">{formError}</p>}
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setModalOpen(false)} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
                <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
