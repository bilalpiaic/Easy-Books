'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Plus, Search, Trash2, Download, Package, Printer, List, FolderTree } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import BulkActionBar from '@/components/BulkActionBar'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV } from '@/lib/utils'
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
  avg_cost: number
  stock_qty: number
  reorder_level: number
  stock_account_id: number | null
  revenue_account_id: number | null
  cogs_account_id: number | null
  category_id: number | null
  is_active: boolean
  is_deferred: boolean
  recognition_months: number
}

interface Cat { id: number; name: string; parent_id: number | null; is_active: boolean; children?: Cat[] }

interface CoaItem { id: number; code: string | null; name: string; qty: number; avg_rate: number; value: number }
interface CoaSub { name: string; qty: number; value: number; items: CoaItem[] }
interface CoaGroup { name: string; qty: number; value: number; subs: CoaSub[] }
interface CoaData { groups: CoaGroup[]; grand: { qty: number; value: number } }

const PAGE_SIZE = 50

function stockBadge(p: Product) {
  if (p.product_type !== 'stock') return null
  if (p.stock_qty <= 0) return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-700">Out of Stock</span>
  if (p.stock_qty <= p.reorder_level) return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700">Low Stock</span>
  return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-green-100 text-green-700">In Stock</span>
}

function ProductsInner() {
  const fmt = useFmt()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [lowStockOnly, setLowStockOnly] = useState(() => searchParams.get('low_stock') === 'true')
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [categories, setCategories] = useState<Cat[]>([])
  const [categoryFilter, setCategoryFilter] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [view, setView] = useState<'list' | 'tree'>('list')
  const [coa, setCoa] = useState<CoaData | null>(null)
  const [coaLoading, setCoaLoading] = useState(false)

  // Fetch the valuation tree the first time the Tree view is opened (and after
  // catalog edits, since stock qty/value may have changed).
  useEffect(() => {
    if (view !== 'tree') return
    setCoaLoading(true)
    apiFetch<CoaData>('/api/reports/product-coa')
      .then(d => setCoa(d))
      .catch(() => {})
      .finally(() => setCoaLoading(false))
  }, [view])

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds)
    if (!window.confirm(`Delete ${ids.length} product(s)? This cannot be undone.`)) return
    const results = await Promise.allSettled(ids.map(id => apiFetch(`/api/products/${id}`, { method: 'DELETE' })))
    const failed = results.filter(r => r.status === 'rejected').length
    if (failed > 0) alert(`${failed} deletion(s) failed — they may be referenced in existing invoices.`)
    setSelectedIds(new Set())
    load()
  }

  const load = () => {
    setIsLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (search) params.set('search', search)
    if (lowStockOnly) params.set('low_stock', 'true')
    if (categoryFilter) params.set('category_id', categoryFilter)
    apiFetch<{ total: number; items: Product[] }>(`/api/products?${params}`)
      .then(d => { setProducts(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }

  useEffect(() => {
    apiFetch<Cat[]>('/api/product-categories')
      .then(setCategories)
      .catch(() => {})
  }, [])

  useEffect(() => { setPage(1) }, [search, lowStockOnly, categoryFilter])
  useEffect(load, [page, search, lowStockOnly, categoryFilter])

  const openAdd = () => router.push('/products/new')

  useEffect(() => {
    const h = () => openAdd()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleDelete = async (p: Product) => {
    if (!window.confirm(`Delete product "${p.name}"? This cannot be undone.`)) return
    try {
      await apiFetch(`/api/products/${p.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  // Flat list of all categories for the list filter
  const allCatsFlat: { id: number; label: string }[] = []
  for (const p of categories) {
    allCatsFlat.push({ id: p.id, label: p.name })
    for (const s of (p.children ?? [])) {
      allCatsFlat.push({ id: s.id, label: `${p.name} › ${s.name}` })
    }
  }
  const catLabel = (id: number | null) =>
    id == null ? '—' : (allCatsFlat.find(c => c.id === id)?.label ?? '—')

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
          <div className="flex rounded-lg border border-[#ede9e2] overflow-hidden">
            <button
              onClick={() => setView('list')}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-bold transition-colors ${view === 'list' ? 'bg-[#1a1814] text-white' : 'bg-white text-black/60 hover:bg-[#f6f3ee]'}`}
              title="List view"
            >
              <List className="w-4 h-4" /> List
            </button>
            <button
              onClick={() => setView('tree')}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-bold transition-colors ${view === 'tree' ? 'bg-[#1a1814] text-white' : 'bg-white text-black/60 hover:bg-[#f6f3ee]'}`}
              title="Category valuation tree"
            >
              <FolderTree className="w-4 h-4" /> Tree
            </button>
          </div>
          <CsvImportButton entity="products" onSuccess={load} />
          <button
            onClick={() => downloadCSV('products.csv', products.map(p => ({
              Code: p.code, Name: p.name, Category: catLabel(p.category_id), Type: p.product_type, Unit: p.unit,
              'Selling Price': p.default_rate, 'Cost Price': p.avg_cost, 'Stock Qty': p.stock_qty, 'Reorder Level': p.reorder_level,
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

      {view === 'list' && (
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
          <input
            type="text" placeholder="Search products..."
            value={search} onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
          />
        </div>
        {allCatsFlat.length > 0 && (
          <select
            value={categoryFilter}
            onChange={e => setCategoryFilter(e.target.value)}
            className="px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f] bg-white"
          >
            <option value="">All Categories</option>
            {allCatsFlat.map(c => <option key={c.id} value={String(c.id)}>{c.label}</option>)}
          </select>
        )}
        <button
          onClick={() => setLowStockOnly(v => !v)}
          className={`px-4 py-2 rounded-lg text-sm font-bold border transition-colors ${lowStockOnly ? 'bg-amber-100 border-amber-300 text-amber-700' : 'border-[#ede9e2] hover:bg-[#f6f3ee] text-black/70'}`}
        >
          {lowStockOnly ? 'Low Stock Only ✓' : 'Low Stock Filter'}
        </button>
      </div>
      )}

      {view === 'tree' && <ProductTree coa={coa} loading={coaLoading} fmt={fmt} />}

      {view === 'list' && (
      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[700px]">
          <thead className="sticky top-0 z-10 bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-4 py-4 w-10">
                <input type="checkbox"
                  className="rounded border-[#ede9e2] accent-[#b8943f]"
                  checked={products.length > 0 && products.every(p => selectedIds.has(p.id))}
                  onChange={e => setSelectedIds(e.target.checked ? new Set(products.map(p => p.id)) : new Set())}
                />
              </th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">Code</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">Name</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">Category</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">Type</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">Unit</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Selling Price</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Cost Price</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Stock Qty</th>
              <th className="ui-th text-center text-xs font-bold uppercase tracking-widest text-black/60">Status</th>
              <th className="ui-th" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {isLoading ? (
              <SkeletonRow cols={11} />
            ) : products.length === 0 ? (
              <tr>
                <td colSpan={11} className="px-6 py-16 text-center">
                  <div className="inline-flex flex-col items-center gap-3">
                    <Package className="w-10 h-10 text-black/20" />
                    <p className="text-sm text-black/40 font-medium">No products yet</p>
                    <button onClick={openAdd} className="px-4 py-2 bg-[#b8943f] text-white text-sm font-medium rounded-lg hover:bg-[#a07835] transition-colors">
                      + Add Product
                    </button>
                  </div>
                </td>
              </tr>
            ) : products.map(p => (
              <tr key={p.id} className={`hover:bg-[#f6f3ee]/50 ${selectedIds.has(p.id) ? 'bg-[#ffd966]/10' : p.product_type === 'stock' && p.stock_qty <= 0 ? 'bg-red-50/30' : p.product_type === 'stock' && p.stock_qty <= p.reorder_level ? 'bg-amber-50/30' : ''}`}>
                <td className="px-4 py-4 w-10">
                  <input type="checkbox"
                    className="rounded border-[#ede9e2] accent-[#b8943f]"
                    checked={selectedIds.has(p.id)}
                    onChange={e => setSelectedIds(prev => {
                      const next = new Set(prev)
                      e.target.checked ? next.add(p.id) : next.delete(p.id)
                      return next
                    })}
                  />
                </td>
                <td className="ui-td font-mono text-xs text-[#b8943f]">
                  {p.code ? <DocLink type="product" id={p.id} label={p.code} className="text-[#b8943f]" /> : '—'}
                </td>
                <td className="ui-td font-medium cursor-pointer" title={p.name}>
                  <DocLink type="product" id={p.id} label={p.name} className="font-medium" />
                </td>
                <td className="ui-td text-black/60 text-xs">{catLabel(p.category_id)}</td>
                <td className="ui-td">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${p.product_type === 'stock' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}>
                    {p.product_type}
                  </span>
                </td>
                <td className="ui-td text-black/60">{p.unit}</td>
                <td className="ui-td text-right font-mono">{fmt(p.default_rate)}</td>
                <td className="ui-td text-right font-mono text-black/70">
                  {p.product_type === 'stock' ? fmt(p.avg_cost) : <span className="text-black/30">—</span>}
                </td>
                <td className="ui-td text-right">
                  {p.product_type === 'stock' ? (
                    <span className="font-mono">{p.stock_qty.toLocaleString()} {p.unit}</span>
                  ) : (
                    <span className="text-black/30">—</span>
                  )}
                </td>
                <td className="ui-td text-center">{stockBadge(p)}</td>
                <td className="ui-td flex items-center gap-3">
                  <button onClick={() => router.push(`/products/${p.id}/edit`)} className="text-[#b8943f] text-sm font-bold hover:underline">Edit</button>
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
      )}

      <BulkActionBar
        count={selectedIds.size}
        actions={[{ label: 'Delete Selected', onClick: handleBulkDelete, variant: 'danger' }]}
        onClear={() => setSelectedIds(new Set())}
      />
    </div>
  )
}

function ProductTree({ coa, loading, fmt }: { coa: CoaData | null; loading: boolean; fmt: (n: number) => string }) {
  return (
    <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">Category / Product</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Qty</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Avg Rate</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {loading ? (
              <tr><td colSpan={4} className="px-6 py-10 text-center text-black/50">Loading valuation…</td></tr>
            ) : !coa || coa.groups.length === 0 ? (
              <tr><td colSpan={4} className="px-6 py-10 text-center text-black/50">No products found.</td></tr>
            ) : (
              coa.groups.map(g => <TreeGroup key={g.name} group={g} fmt={fmt} />)
            )}
          </tbody>
          {!loading && coa && coa.groups.length > 0 && (
            <tfoot>
              <tr className="bg-[#1a1814] text-white">
                <td className="ui-td font-bold uppercase tracking-widest text-xs">Grand Total</td>
                <td className="ui-td text-right font-mono font-bold">{Number(coa.grand.qty).toLocaleString()}</td>
                <td />
                <td className="ui-td text-right font-mono font-bold">{fmt(coa.grand.value)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}

function TreeGroup({ group, fmt }: { group: CoaGroup; fmt: (n: number) => string }) {
  return (
    <>
      <tr className="bg-[#f6f3ee]/60">
        <td className="ui-td font-semibold text-[#1a1814]">{group.name}</td>
        <td className="ui-td text-right font-mono text-sm">{Number(group.qty).toLocaleString()}</td>
        <td />
        <td className="ui-td text-right font-mono text-sm font-semibold">{fmt(group.value)}</td>
      </tr>
      {group.subs.map(sub => (
        <TreeSub key={`${group.name}-${sub.name}`} sub={sub} fmt={fmt} />
      ))}
    </>
  )
}

function TreeSub({ sub, fmt }: { sub: CoaSub; fmt: (n: number) => string }) {
  return (
    <>
      <tr>
        <td className="ui-td pl-10 font-medium text-sm text-[#1a1814]/80">{sub.name}</td>
        <td className="ui-td text-right font-mono text-xs text-[#1a1814]/70">{Number(sub.qty).toLocaleString()}</td>
        <td />
        <td className="ui-td text-right font-mono text-xs text-[#1a1814]/70">{fmt(sub.value)}</td>
      </tr>
      {sub.items.map(it => (
        <tr key={it.id} className="hover:bg-[#f6f3ee]/50">
          <td className="ui-td pl-16 text-sm">
            <Link href={`/products/ledger?product=${it.id}`} className="text-[#1a1814]/90 hover:text-[#b8943f] hover:underline" title="View product ledger">
              {it.name}
            </Link>
            {it.code && <span className="ml-2 font-mono text-xs text-[#b8943f]">{it.code}</span>}
          </td>
          <td className="ui-td text-right font-mono text-sm">{Number(it.qty).toLocaleString()}</td>
          <td className="ui-td text-right font-mono text-sm text-[#1a1814]/70">{fmt(it.avg_rate)}</td>
          <td className="ui-td text-right font-mono text-sm">{fmt(it.value)}</td>
        </tr>
      ))}
    </>
  )
}

export default function Products() {
  return <Suspense><ProductsInner /></Suspense>
}
