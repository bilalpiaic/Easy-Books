'use client'

import { useEffect, useState } from 'react'
import { Plus, Search, Trash2, Download, Package, Printer } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import { apiFetch } from '@/lib/api'
import { fmtPKR, downloadCSV } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'
import CsvImportButton from '@/components/CsvImportButton'

interface Product {
  id: number
  code: string | null
  name: string
  unit: string
  product_type: string
  default_rate: number
  stock_qty: number
  reorder_level: number
  stock_account_id: number | null
  revenue_account_id: number | null
  cogs_account_id: number | null
  is_active: boolean
}

interface Account {
  id: number
  code: string
  name: string
  type: string
}

interface FormState {
  code: string
  name: string
  unit: string
  product_type: string
  default_rate: string
  reorder_level: string
  stock_account_id: string
  revenue_account_id: string
  cogs_account_id: string
}

const UNITS = ['pcs', 'kg', 'mtr', 'hrs', 'ltr', 'box', 'doz']
const PAGE_SIZE = 50

const emptyForm: FormState = {
  code: '', name: '', unit: 'pcs', product_type: 'service',
  default_rate: '0', reorder_level: '0',
  stock_account_id: '', revenue_account_id: '', cogs_account_id: '',
}

function stockBadge(p: Product) {
  if (p.product_type !== 'stock') return null
  if (p.stock_qty <= 0) return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-700">Out of Stock</span>
  if (p.stock_qty <= p.reorder_level) return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700">Low Stock</span>
  return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-green-100 text-green-700">In Stock</span>
}

export default function Products() {
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [editProduct, setEditProduct] = useState<Product | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const load = () => {
    setIsLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (search) params.set('search', search)
    apiFetch<{ total: number; items: Product[] }>(`/api/products?${params}`)
      .then(d => { setProducts(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }

  useEffect(() => {
    apiFetch<{ items: Account[] }>('/api/accounts?limit=500')
      .then(d => setAccounts(d.items))
      .catch(() => {})
  }, [])

  useEffect(() => { setPage(1) }, [search])
  useEffect(load, [page, search])

  const openAdd = () => { setEditProduct(null); setForm(emptyForm); setFormError(''); setModalOpen(true) }
  const openEdit = (p: Product) => {
    setEditProduct(p)
    setForm({
      code: p.code ?? '',
      name: p.name,
      unit: p.unit,
      product_type: p.product_type,
      default_rate: String(p.default_rate),
      reorder_level: String(p.reorder_level),
      stock_account_id: p.stock_account_id ? String(p.stock_account_id) : '',
      revenue_account_id: p.revenue_account_id ? String(p.revenue_account_id) : '',
      cogs_account_id: p.cogs_account_id ? String(p.cogs_account_id) : '',
    })
    setFormError('')
    setModalOpen(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) { setFormError('Name is required.'); return }
    setSaving(true); setFormError('')
    try {
      const body = {
        code: form.code || null,
        name: form.name,
        unit: form.unit,
        product_type: form.product_type,
        default_rate: parseFloat(form.default_rate) || 0,
        reorder_level: parseFloat(form.reorder_level) || 0,
        stock_account_id: form.stock_account_id ? parseInt(form.stock_account_id) : null,
        revenue_account_id: form.revenue_account_id ? parseInt(form.revenue_account_id) : null,
        cogs_account_id: form.cogs_account_id ? parseInt(form.cogs_account_id) : null,
      }
      if (editProduct) {
        await apiFetch(`/api/products/${editProduct.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      } else {
        await apiFetch('/api/products', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      }
      setModalOpen(false); load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (p: Product) => {
    if (!window.confirm(`Delete product "${p.name}"? This cannot be undone.`)) return
    try {
      await apiFetch(`/api/products/${p.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const isStock = form.product_type === 'stock'
  const assetAccounts = accounts.filter(a => a.type === 'Asset')
  const revenueAccounts = accounts.filter(a => a.type === 'Revenue')
  const expenseAccounts = accounts.filter(a => a.type === 'Expense')

  return (
    <div className="space-y-6">
      <PrintHeader title="Products" orientation="landscape" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif font-medium flex items-center gap-2">
            <Package className="w-7 h-7 text-[#b8943f]" /> Products
          </h1>
          <p className="text-sm text-black/75 mt-1">Manage product catalog and track inventory</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <CsvImportButton entity="products" onSuccess={load} />
          <button
            onClick={() => downloadCSV('products.csv', products.map(p => ({
              Code: p.code, Name: p.name, Type: p.product_type, Unit: p.unit,
              Rate: p.default_rate, 'Stock Qty': p.stock_qty, 'Reorder Level': p.reorder_level,
            })))}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Download className="w-4 h-4" /> Export
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
            title="Print"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
          <button onClick={openAdd} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" /> Add Product
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-4">
          <p className="text-xs text-black/60 uppercase tracking-widest font-bold">Total Products</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-1">{total}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-4">
          <p className="text-xs text-black/60 uppercase tracking-widest font-bold">Stock Items</p>
          <p className="text-2xl font-bold text-[#1a1814] mt-1">{products.filter(p => p.product_type === 'stock').length}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-4">
          <p className="text-xs text-black/60 uppercase tracking-widest font-bold">Low Stock</p>
          <p className="text-2xl font-bold text-amber-600 mt-1">{products.filter(p => p.product_type === 'stock' && p.stock_qty > 0 && p.stock_qty <= p.reorder_level).length}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-4">
          <p className="text-xs text-black/60 uppercase tracking-widest font-bold">Out of Stock</p>
          <p className="text-2xl font-bold text-red-600 mt-1">{products.filter(p => p.product_type === 'stock' && p.stock_qty <= 0).length}</p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input
          type="text" placeholder="Search products..."
          value={search} onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
        />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[700px]">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Code</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Name</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Type</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Unit</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/60">Default Rate</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/60">Stock Qty</th>
              <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-black/60">Status</th>
              <th className="px-6 py-4" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {isLoading ? (
              <SkeletonRow cols={8} />
            ) : products.length === 0 ? (
              <tr><td colSpan={8} className="px-6 py-8 text-center text-black/40">No products found.</td></tr>
            ) : products.map(p => (
              <tr key={p.id} className={`hover:bg-[#f6f3ee]/50 ${p.product_type === 'stock' && p.stock_qty <= 0 ? 'bg-red-50/30' : p.product_type === 'stock' && p.stock_qty <= p.reorder_level ? 'bg-amber-50/30' : ''}`}>
                <td className="px-6 py-4 font-mono text-xs text-[#b8943f]">
                  {p.code ? <DocLink type="product" id={p.id} label={p.code} className="text-[#b8943f]" /> : '—'}
                </td>
                <td className="px-6 py-4 font-medium">
                  <DocLink type="product" id={p.id} label={p.name} className="font-medium" />
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${p.product_type === 'stock' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}>
                    {p.product_type}
                  </span>
                </td>
                <td className="px-6 py-4 text-black/60">{p.unit}</td>
                <td className="px-6 py-4 text-right font-mono">{fmtPKR(p.default_rate)}</td>
                <td className="px-6 py-4 text-right">
                  {p.product_type === 'stock' ? (
                    <span className="font-mono">{p.stock_qty.toLocaleString()} {p.unit}</span>
                  ) : (
                    <span className="text-black/30">—</span>
                  )}
                </td>
                <td className="px-6 py-4 text-center">{stockBadge(p)}</td>
                <td className="px-6 py-4 flex items-center gap-3">
                  <button onClick={() => openEdit(p)} className="text-[#b8943f] text-sm font-bold hover:underline">Edit</button>
                  <button onClick={() => handleDelete(p)} className="text-red-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
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
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-8 max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">{editProduct ? 'Edit Product' : 'Add Product'}</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Code</label>
                  <input value={form.code} onChange={e => setForm(p => ({ ...p, code: e.target.value }))}
                    placeholder="e.g. SKU-001"
                    className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Unit</label>
                  <select value={form.unit} onChange={e => setForm(p => ({ ...p, unit: e.target.value }))}
                    className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]">
                    {UNITS.map(u => <option key={u} value={u}>{u}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Name *</label>
                <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="Product name"
                  className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-2">Type</label>
                <div className="flex gap-3">
                  {['service', 'stock'].map(t => (
                    <button key={t} type="button"
                      onClick={() => setForm(p => ({ ...p, product_type: t }))}
                      className={`px-4 py-2 rounded-lg text-sm font-bold capitalize transition-all ${form.product_type === t ? 'bg-[#1a1814] text-white' : 'bg-[#f6f3ee] text-black/60 hover:bg-[#ede9e2]'}`}>
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Default Rate</label>
                  <input type="number" min="0" step="0.01" value={form.default_rate}
                    onChange={e => setForm(p => ({ ...p, default_rate: e.target.value }))}
                    className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
                </div>
                {isStock && (
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Reorder Level</label>
                    <input type="number" min="0" step="0.001" value={form.reorder_level}
                      onChange={e => setForm(p => ({ ...p, reorder_level: e.target.value }))}
                      className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
                  </div>
                )}
              </div>
              {isStock && (
                <div className="space-y-3 border-t border-[#ede9e2] pt-4">
                  <p className="text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">GL Accounts (optional)</p>
                  {[
                    { label: 'Stock / Inventory Account', key: 'stock_account_id', opts: assetAccounts },
                    { label: 'Revenue Account', key: 'revenue_account_id', opts: revenueAccounts },
                    { label: 'COGS Account', key: 'cogs_account_id', opts: expenseAccounts },
                  ].map(({ label, key, opts }) => (
                    <div key={key}>
                      <label className="block text-xs text-[#1a1814]/60 mb-1">{label}</label>
                      <select
                        value={(form as unknown as Record<string, string>)[key]}
                        onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
                        className="w-full px-4 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
                      >
                        <option value="">— use default —</option>
                        {opts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                      </select>
                    </div>
                  ))}
                </div>
              )}
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
