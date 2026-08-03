'use client'

import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'
import { useModules } from '@/context/ModuleContext'

export interface ProductFull {
  id: number
  code: string | null
  name: string
  unit: string
  product_type: string
  default_rate: number
  reorder_level: number
  stock_account_id: number | null
  revenue_account_id: number | null
  cogs_account_id: number | null
  category_id: number | null
  is_active: boolean
  is_deferred: boolean
  recognition_months: number
  hs_code: string | null
  pct_code: string | null
  hsn_sac: string | null
  cost_method: string | null
  standalone_selling_price: number | null
}

interface Cat { id: number; name: string; parent_id: number | null; is_active: boolean; children?: Cat[] }
interface Account { id: number; code: string; name: string; type: string }

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
  category_id: string
  is_deferred: boolean
  recognition_months: string
  opening_qty: string
  opening_cost: string
  hs_code: string
  pct_code: string    // PRA 8-digit product classification
  hsn_sac: string
  cost_method: string  // '' = inherit from tenant, 'wavg', 'fifo'
  standalone_selling_price: string
}

const UNITS = ['pcs', 'kg', 'mtr', 'hrs', 'ltr', 'box', 'doz']

const emptyForm: FormState = {
  code: '', name: '', unit: 'pcs', product_type: 'service',
  default_rate: '0', reorder_level: '0',
  stock_account_id: '', revenue_account_id: '', cogs_account_id: '',
  category_id: '',
  is_deferred: false, recognition_months: '12',
  opening_qty: '0', opening_cost: '0',
  hs_code: '', pct_code: '', hsn_sac: '',
  cost_method: '',
  standalone_selling_price: '',
}

interface Props {
  mode: 'create' | 'edit'
  product?: ProductFull
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function ProductForm({ mode, product, onSaved, onCancel }: Props) {
  const { installedModules } = useModules()
  const showGst = installedModules.has('in_gst')
  const [form, setForm] = useState<FormState>(emptyForm)
  const [formParentCat, setFormParentCat] = useState('')
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [accounts, setAccounts] = useState<Account[]>([])
  const [categories, setCategories] = useState<Cat[]>([])

  useEffect(() => {
    apiFetch<{ items: Account[] }>('/api/accounts?limit=500')
      .then(d => setAccounts(d.items))
      .catch(() => {})
    apiFetch<Cat[]>('/api/product-categories')
      .then(setCategories)
      .catch(() => {})
  }, [])

  // Populate the form in edit mode. Resolving the category's parent/sub split
  // needs the categories list, so this runs once both are available.
  useEffect(() => {
    if (mode !== 'edit' || !product) return
    let initParentCat = ''
    let initCategoryId = ''
    if (product.category_id != null) {
      const asParent = categories.find(c => c.id === product.category_id)
      if (asParent) {
        initParentCat = String(asParent.id)
        initCategoryId = String(product.category_id)
      } else {
        for (const parent of categories) {
          const sub = (parent.children ?? []).find(s => s.id === product.category_id)
          if (sub) {
            initParentCat = String(parent.id)
            initCategoryId = String(product.category_id)
            break
          }
        }
      }
    }
    setFormParentCat(initParentCat)
    setForm({
      code: product.code ?? '',
      name: product.name,
      unit: product.unit,
      product_type: product.product_type,
      default_rate: String(product.default_rate),
      reorder_level: String(product.reorder_level),
      stock_account_id: product.stock_account_id ? String(product.stock_account_id) : '',
      revenue_account_id: product.revenue_account_id ? String(product.revenue_account_id) : '',
      cogs_account_id: product.cogs_account_id ? String(product.cogs_account_id) : '',
      category_id: initCategoryId,
      is_deferred: product.is_deferred ?? false,
      recognition_months: String(product.recognition_months ?? 12),
      opening_qty: '0',
      opening_cost: '0',
      hs_code: product.hs_code ?? '',
      pct_code: product.pct_code ?? '',
      hsn_sac: product.hsn_sac ?? '',
      cost_method: product.cost_method ?? '',
      standalone_selling_price: product.standalone_selling_price != null
        ? String(product.standalone_selling_price) : '',
    })
  }, [mode, product, categories])

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
        category_id: form.category_id ? Number(form.category_id) : null,
        is_deferred: form.is_deferred,
        recognition_months: parseInt(form.recognition_months) || 12,
        hs_code: form.hs_code.trim() || null,
        pct_code: form.pct_code.trim() || null,
        hsn_sac: form.hsn_sac.trim() || null,
        cost_method: form.cost_method || null,
        standalone_selling_price: form.standalone_selling_price.trim()
          ? parseFloat(form.standalone_selling_price) : null,
      }
      if (mode === 'edit' && product) {
        await apiFetch(`/api/products/${product.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
        onSaved(product.id)
      } else {
        const createBody = form.product_type === 'stock'
          ? { ...body, opening_qty: parseFloat(form.opening_qty) || 0, opening_cost: parseFloat(form.opening_cost) || 0 }
          : body
        const created = await apiFetch<ProductFull>('/api/products', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(createBody) })
        onSaved(created.id)
      }
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const isStock = form.product_type === 'stock'
  const assetAccounts = accounts.filter(a => a.type === 'Asset')
  const revenueAccounts = accounts.filter(a => a.type === 'Revenue')
  const expenseAccounts = accounts.filter(a => a.type === 'Expense')

  const selectedParentCat = categories.find(c => String(c.id) === formParentCat)
  const subCategories = selectedParentCat?.children ?? []

  return (
    <div className="bg-white rounded-2xl border border-[var(--border)] p-8 max-w-2xl mx-auto">
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Code</label>
            <input value={form.code} onChange={e => setForm(p => ({ ...p, code: e.target.value }))}
              placeholder="e.g. SKU-001"
              className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]" />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">HS Code <span className="normal-case font-normal">(FBR)</span></label>
            <input value={form.hs_code} onChange={e => setForm(p => ({ ...p, hs_code: e.target.value }))}
              placeholder="e.g. 8471.30"
              className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]" />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">PCT Code <span className="normal-case font-normal">(PRA)</span></label>
            <input value={form.pct_code} onChange={e => setForm(p => ({ ...p, pct_code: e.target.value }))}
              placeholder="8-digit PRA code"
              className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]" />
          </div>
          {showGst && (
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">HSN / SAC <span className="normal-case font-normal">(India GST)</span></label>
              <input value={form.hsn_sac} onChange={e => setForm(p => ({ ...p, hsn_sac: e.target.value }))}
                placeholder="e.g. 998314"
                className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] font-mono" />
            </div>
          )}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Unit</label>
            <select value={form.unit} onChange={e => setForm(p => ({ ...p, unit: e.target.value }))}
              className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]">
              {UNITS.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Name *</label>
          <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
            placeholder="Product name"
            className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]" />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-2">Type</label>
          <div className="flex gap-3">
            {['service', 'stock'].map(t => (
              <button key={t} type="button"
                onClick={() => setForm(p => ({ ...p, product_type: t }))}
                className={`px-4 py-2 rounded-lg text-sm font-bold capitalize transition-all ${form.product_type === t ? 'bg-[var(--text-primary)] text-white' : 'bg-[var(--bg-page)] text-[var(--text-muted)] hover:bg-[var(--border)]'}`}>
                {t}
              </button>
            ))}
          </div>
        </div>
        {categories.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Category</label>
              <select
                value={formParentCat}
                onChange={e => {
                  setFormParentCat(e.target.value)
                  // When parent changes, default category_id to the parent itself (or clear)
                  setForm(p => ({ ...p, category_id: e.target.value }))
                }}
                className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
              >
                <option value="">— None —</option>
                {categories.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
              </select>
            </div>
            {subCategories.length > 0 && (
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Sub-category</label>
                <select
                  value={form.category_id}
                  onChange={e => setForm(p => ({ ...p, category_id: e.target.value }))}
                  className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
                >
                  <option value={formParentCat}>— (parent only) —</option>
                  {subCategories.map(s => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
                </select>
              </div>
            )}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Selling Price</label>
            <input type="number" min="0" step="0.01" value={form.default_rate}
              onChange={e => setForm(p => ({ ...p, default_rate: e.target.value }))}
              className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]" />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">
              Standalone Selling Price <span className="normal-case font-normal">(IFRS 15 SSP)</span>
            </label>
            <input type="number" min="0" step="0.01" value={form.standalone_selling_price}
              onChange={e => setForm(p => ({ ...p, standalone_selling_price: e.target.value }))}
              placeholder="Optional — for multi-element allocation"
              className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]" />
          </div>
          {isStock && (
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Reorder Level</label>
              <input type="number" min="0" step="0.001" value={form.reorder_level}
                onChange={e => setForm(p => ({ ...p, reorder_level: e.target.value }))}
                className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]" />
            </div>
          )}
        </div>
        {isStock && mode === 'create' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border border-amber-100 bg-amber-50/60 rounded-xl p-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Opening Qty</label>
              <input type="number" min="0" step="0.001" value={form.opening_qty}
                onChange={e => setForm(p => ({ ...p, opening_qty: e.target.value }))}
                className="w-full ui-field bg-white rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]" />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Unit Cost (opening)</label>
              <input type="number" min="0" step="0.0001" value={form.opening_cost}
                onChange={e => setForm(p => ({ ...p, opening_cost: e.target.value }))}
                className="w-full ui-field bg-white rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]" />
            </div>
            <p className="col-span-2 text-xs text-amber-700/80">Sets the initial stock balance. Leave at 0 if stock will come in via bills or GRN.</p>
          </div>
        )}
        <div className="border-t border-[var(--border)] pt-4 space-y-3">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Deferred Revenue</p>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_deferred}
              onChange={e => setForm(p => ({ ...p, is_deferred: e.target.checked }))}
              className="rounded border-[var(--border)] accent-[var(--primary)] w-4 h-4"
            />
            <span className="text-sm text-[var(--text-primary)]/80">Recognize revenue over time (deferred)</span>
          </label>
          {form.is_deferred && (
            <div className="w-full sm:w-1/2 max-w-xs">
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Recognition Months</label>
              <input
                type="number" min="1" step="1"
                value={form.recognition_months}
                onChange={e => setForm(p => ({ ...p, recognition_months: e.target.value }))}
                className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]"
              />
            </div>
          )}
        </div>
        {isStock && (
          <div className="border-t border-[var(--border)] pt-4 space-y-2">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Cost Flow Method (IAS 2.25)</p>
            <select
              value={form.cost_method}
              onChange={e => setForm(p => ({ ...p, cost_method: e.target.value }))}
              className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            >
              <option value="">— Inherit from company settings —</option>
              <option value="wavg">Weighted Average (WAvg)</option>
              <option value="fifo">FIFO — First In, First Out</option>
            </select>
            <p className="text-xs text-[var(--text-muted)]">Override the company-wide cost method for this product only.</p>
          </div>
        )}
        {isStock && (
          <div className="space-y-3 border-t border-[var(--border)] pt-4">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">GL Accounts (optional)</p>
            {[
              { label: 'Stock / Inventory Account', key: 'stock_account_id', opts: assetAccounts },
              { label: 'Revenue Account', key: 'revenue_account_id', opts: revenueAccounts },
              { label: 'COGS Account', key: 'cogs_account_id', opts: expenseAccounts },
            ].map(({ label, key, opts }) => (
              <div key={key}>
                <label className="block text-xs text-[var(--text-primary)]/60 mb-1">{label}</label>
                <select
                  value={(form as unknown as Record<string, string>)[key]}
                  onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
                  className="w-full px-4 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
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
          <button onClick={onCancel} className="px-6 py-3 border border-[var(--text-primary)]/10 rounded-xl font-bold hover:bg-[var(--bg-page)]">Cancel</button>
          <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[var(--text-primary)] text-white rounded-xl font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50">
            {saving ? 'Saving...' : mode === 'edit' ? 'Save Changes' : 'Add Product'}
          </button>
        </div>
      </div>
    </div>
  )
}
