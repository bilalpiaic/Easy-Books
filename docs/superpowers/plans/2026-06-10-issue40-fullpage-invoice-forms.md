# Full-page Invoice Forms (#40 Pilot) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the invoice create/edit experience from a modal embedded in the list page to dedicated full-page routes (`/invoices/new`, `/invoices/[id]/edit`), backed by one extracted `InvoiceForm` component.

**Architecture:** Lift the modal body + all its form logic into `components/invoices/InvoiceForm.tsx` (4-prop interface, routing-agnostic). Two thin page shells render it. The list page becomes a pure list; the detail page's existing Edit link is retargeted from the `?edit=` modal trigger to the new edit route.

**Tech Stack:** Next.js 16 App Router (async `params` via `use()`), React 19, TypeScript, Tailwind v4. No backend/API change. Verification = `npm run build` + `npm run lint` + manual smoke (the frontend has no unit-test runner; the spec sets build/lint/manual as the gate).

**Working directory for all commands:** `frontend/`

---

### Task 1: Extract `InvoiceForm` component

**Files:**
- Create: `frontend/src/components/invoices/InvoiceForm.tsx`

The component owns everything the modal owned (form state, dropdown loading, totals, posted-edit guard, submit) but knows nothing about routing or the list. Create mode starts blank; edit mode seeds from the `invoice` prop.

- [ ] **Step 1: Create the component file**

Create `frontend/src/components/invoices/InvoiceForm.tsx` with exactly this content:

```tsx
'use client'

import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'
import { useFmt, useSettings } from '@/context/SettingsContext'
import LineItemsTable, { LineItem, TaxCodeOption } from '@/components/LineItemsTable'

export interface InvoiceFull {
  id: number
  number: string
  status: string
  customer_id: number | null
  customer_name: string | null
  issue_date: string
  due_date: string
  payment_term_id: number | null
  description: string | null
  notes: string | null
  internal_memo: string | null
  gst_rate: number
  ar_account_id: number | null
  revenue_account_id: number | null
  currency: string
  exchange_rate: number
  lines: (LineItem & { tax_code_id?: number | null })[]
}

interface Customer { id: number; name: string }
interface Account { id: number; code: string; name: string; type: string }
interface Product { id: number; name: string; code: string | null; unit: string; default_rate: number; product_type: string; stock_qty?: number }
interface PaymentTerm { id: number; code: string; name: string; days: number }

interface FormState {
  customer_id: string
  customer_name: string
  issue_date: string
  due_date: string
  payment_term_id: string
  description: string
  notes: string
  internal_memo: string
  gst_rate: string
  ar_account_id: string
  revenue_account_id: string
  currency: string
  exchange_rate: string
}

const emptyForm: FormState = {
  customer_id: '', customer_name: '', issue_date: new Date().toISOString().split('T')[0],
  due_date: '', payment_term_id: '', description: '', notes: '', internal_memo: '', gst_rate: '17',
  ar_account_id: '', revenue_account_id: '',
  currency: 'PKR', exchange_rate: '1',
}

interface Props {
  mode: 'create' | 'edit'
  invoice?: InvoiceFull
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function InvoiceForm({ mode, invoice, onSaved, onCancel }: Props) {
  const fmt = useFmt()
  const { settings } = useSettings()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [lines, setLines] = useState<LineItem[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [customers, setCustomers] = useState<Customer[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [paymentTerms, setPaymentTerms] = useState<PaymentTerm[]>([])
  const [taxCodes, setTaxCodes] = useState<TaxCodeOption[]>([])
  const [customerBalance, setCustomerBalance] = useState<number | null>(null)
  const [confirmPostedEdit, setConfirmPostedEdit] = useState(false)

  useEffect(() => {
    Promise.all([
      apiFetch<{ total: number; items: Customer[] }>('/api/customers?limit=200'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
      apiFetch<{ total: number; items: Product[] }>('/api/products?limit=500'),
      apiFetch<PaymentTerm[]>('/api/payment-terms'),
      apiFetch<{ total: number; items: TaxCodeOption[] }>('/api/tax-codes?limit=100'),
    ]).then(([c, a, p, terms, tc]) => {
      setCustomers(c.items); setAccounts(a.items); setProducts(p.items)
      setPaymentTerms(terms); setTaxCodes(tc.items)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (mode === 'edit' && invoice) {
      setForm({
        customer_id: String(invoice.customer_id ?? ''),
        customer_name: invoice.customer_name ?? '',
        issue_date: invoice.issue_date,
        due_date: invoice.due_date,
        payment_term_id: invoice.payment_term_id ? String(invoice.payment_term_id) : '',
        description: invoice.description ?? '',
        notes: invoice.notes ?? '',
        internal_memo: invoice.internal_memo ?? '',
        gst_rate: String(invoice.gst_rate ?? 17),
        ar_account_id: invoice.ar_account_id ? String(invoice.ar_account_id) : '',
        revenue_account_id: invoice.revenue_account_id ? String(invoice.revenue_account_id) : '',
        currency: invoice.currency ?? 'PKR',
        exchange_rate: String(invoice.exchange_rate ?? 1),
      })
      setLines((invoice.lines ?? []).map(l => ({
        product_id: l.product_id ?? undefined,
        description: l.description,
        qty: Number(l.qty),
        unit: l.unit ?? 'pcs',
        rate: Number(l.rate),
        amount: Number(l.amount),
        tax_code_id: l.tax_code_id ?? null,
      })))
    }
  }, [mode, invoice])

  const subtotal = lines.reduce((s, l) => s + l.amount, 0)
  const usePerLineTax = lines.some(l => l.tax_code_id)
  const perLineTaxTotal = usePerLineTax
    ? lines.reduce((s, l) => {
        if (!l.tax_code_id) return s
        const tc = taxCodes.find(t => t.id === l.tax_code_id)
        return s + (tc ? Math.round(l.amount * tc.rate / 100 * 100) / 100 : 0)
      }, 0)
    : 0
  const gstAmount = usePerLineTax
    ? perLineTaxTotal
    : Math.round(subtotal * (parseFloat(form.gst_rate) || 0) / 100 * 100) / 100
  const totalAmount = Math.round((subtotal + gstAmount) * 100) / 100

  const arAccounts = accounts.filter(a => a.type === 'Asset')
  const revenueAccounts = accounts.filter(a => a.type === 'Revenue')

  const handleSave = async () => {
    if (lines.length === 0) { setFormError('Add at least one line item'); return }
    if (lines.some(l => !l.description.trim())) { setFormError('All lines must have a description'); return }
    if (!form.issue_date || (!form.due_date && !form.payment_term_id)) {
      setFormError('Issue date required; provide either a due date or a payment term'); return
    }
    if (mode === 'edit' && invoice && invoice.status !== 'draft') {
      if (!confirmPostedEdit) { setConfirmPostedEdit(true); return }
      setConfirmPostedEdit(false)
    }
    setSaving(true); setFormError('')
    const body = {
      customer_id: form.customer_id ? parseInt(form.customer_id) : null,
      customer_name: form.customer_name || null,
      issue_date: form.issue_date,
      due_date: form.due_date,
      payment_term_id: form.payment_term_id ? parseInt(form.payment_term_id) : null,
      description: form.description || null,
      notes: form.notes || null,
      internal_memo: form.internal_memo || null,
      lines: lines.map(l => ({
        product_id: l.product_id ?? null,
        description: l.description,
        qty: l.qty,
        unit: l.unit ?? null,
        rate: l.rate,
        tax_code_id: l.tax_code_id ?? null,
      })),
      gst_rate: parseFloat(form.gst_rate) || 0,
      ar_account_id: form.ar_account_id ? parseInt(form.ar_account_id) : null,
      revenue_account_id: form.revenue_account_id ? parseInt(form.revenue_account_id) : null,
      currency: form.currency || settings.currency,
      exchange_rate: parseFloat(form.exchange_rate) || 1,
    }
    try {
      if (mode === 'edit' && invoice) {
        await apiFetch(`/api/invoices/${invoice.id}`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        })
        onSaved(invoice.id)
      } else {
        const created = await apiFetch<{ id: number }>('/api/invoices', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        })
        onSaved(created.id)
      }
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-[#ede9e2] p-8 max-w-3xl">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Customer</label>
            <select value={form.customer_id}
              onChange={e => {
                const c = customers.find(c => c.id === parseInt(e.target.value))
                setForm(p => ({ ...p, customer_id: e.target.value, customer_name: c?.name ?? '' }))
                setCustomerBalance(null)
                if (e.target.value) {
                  apiFetch<{ closing_balance?: number; balance?: number }>(`/api/customers/${e.target.value}/ledger`)
                    .then(d => setCustomerBalance(d.closing_balance ?? d.balance ?? null))
                    .catch(() => {})
                }
              }}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
              <option value="">— Select or type name —</option>
              {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            {customerBalance !== null && customerBalance > 0 && (
              <p className="text-xs text-amber-700 mt-1 font-medium">Outstanding balance: {fmt(customerBalance)}</p>
            )}
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Customer Name</label>
            <input value={form.customer_name} onChange={e => setForm(p => ({ ...p, customer_name: e.target.value }))}
              placeholder="or type manually"
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Issue Date</label>
            <input type="date" value={form.issue_date} onChange={e => setForm(p => ({ ...p, issue_date: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Payment Term</label>
            <select
              value={form.payment_term_id}
              onChange={e => {
                const termId = e.target.value
                setForm(p => {
                  const term = paymentTerms.find(t => String(t.id) === termId)
                  const due = term && p.issue_date
                    ? new Date(new Date(p.issue_date).getTime() + term.days * 86400000).toISOString().split('T')[0]
                    : p.due_date
                  return { ...p, payment_term_id: termId, due_date: due }
                })
              }}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
            >
              <option value="">— select —</option>
              {paymentTerms.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Due Date</label>
            <input type="date" value={form.due_date} onChange={e => setForm(p => ({ ...p, due_date: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
          </div>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Description</label>
          <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
            placeholder="e.g. Consulting services — May 2026"
            className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Currency</label>
            <select value={form.currency} onChange={e => setForm(p => ({ ...p, currency: e.target.value, exchange_rate: e.target.value === settings.currency ? '1' : p.exchange_rate }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
              {['PKR','USD','EUR','GBP','AED','SAR','CNY'].map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
              Exchange Rate (1 {form.currency} = ? {settings.currency})
            </label>
            <input type="number" step="0.0001" min="0" value={form.exchange_rate}
              onChange={e => setForm(p => ({ ...p, exchange_rate: e.target.value }))}
              disabled={form.currency === settings.currency}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm disabled:opacity-50" />
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-2">Line Items</label>
          <LineItemsTable lines={lines} onChange={setLines} products={products} taxCodes={taxCodes} showTax showStockHint warnOversell customerId={form.customer_id ? Number(form.customer_id) : null} priceKind="sale" />
        </div>

        <div className="bg-[#f6f3ee] rounded-xl p-4 space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-black/60">Subtotal</span>
            <span className="font-mono">{fmt(subtotal)}</span>
          </div>
          <div className="flex justify-between items-center gap-2">
            <span className="text-black/60">Tax</span>
            {usePerLineTax ? (
              <span className="font-mono text-xs text-black/60">(per-line) {fmt(gstAmount)}</span>
            ) : (
              <div className="flex items-center gap-2">
                <input type="number" min="0" max="100" step="0.5"
                  value={form.gst_rate}
                  onChange={e => setForm(p => ({ ...p, gst_rate: e.target.value }))}
                  className="w-16 text-right bg-white border border-[#ede9e2] rounded px-2 py-0.5 text-xs outline-none focus:ring-1 focus:ring-[#b8943f]"
                />
                <span className="text-black/60 text-xs">%</span>
                <span className="font-mono">{fmt(gstAmount)}</span>
              </div>
            )}
          </div>
          <div className="flex justify-between border-t border-[#ede9e2] pt-2 font-bold">
            <span>Total</span>
            <span className="font-mono text-[#1a1814]">{fmt(totalAmount)}</span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Notes (printed)</label>
            <textarea rows={2} value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))}
              placeholder="Printed on the invoice for the customer"
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm resize-none" />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-amber-700/70 mb-1">Internal Memo</label>
            <textarea rows={2} value={form.internal_memo} onChange={e => setForm(p => ({ ...p, internal_memo: e.target.value }))}
              placeholder="Staff-only note, not printed"
              className="w-full px-3 py-2 bg-amber-50 border border-amber-200 rounded-xl outline-none focus:ring-2 focus:ring-amber-400 text-sm resize-none" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">AR Account</label>
            <select value={form.ar_account_id} onChange={e => setForm(p => ({ ...p, ar_account_id: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
              <option value="">Auto (1100)</option>
              {arAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Revenue Account</label>
            <select value={form.revenue_account_id} onChange={e => setForm(p => ({ ...p, revenue_account_id: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
              <option value="">Auto (4000)</option>
              {revenueAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
            </select>
          </div>
        </div>

        {formError && <p className="text-red-600 text-sm">{formError}</p>}
        {confirmPostedEdit && (
          <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 text-sm text-amber-900">
            <p className="font-semibold mb-1">Confirm posted-invoice edit</p>
            <p className="mb-3">This will reverse the original ledger entry and post a correction, keeping the same document number. Continue?</p>
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 bg-amber-700 text-white rounded-lg font-bold hover:bg-amber-800 disabled:opacity-50 text-xs"
              >
                {saving ? 'Saving…' : 'Yes, post correction'}
              </button>
              <button
                onClick={() => setConfirmPostedEdit(false)}
                className="px-4 py-2 border border-amber-400 text-amber-800 rounded-lg font-bold hover:bg-amber-100 text-xs"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
        <p className="text-xs text-black/50">GL posting: Dr Accounts Receivable / Cr Revenue / Cr GST Payable</p>
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onCancel} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
          {!confirmPostedEdit && (
            <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
              {saving ? 'Saving…' : mode === 'edit' ? 'Save Changes' : 'Post Invoice'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Type-check via build**

Run: `npm run build`
Expected: build SUCCEEDS (the new component compiles; it's not yet imported anywhere). If TypeScript errors appear, fix them before continuing.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/invoices/InvoiceForm.tsx
git commit -m "feat(invoices): extract InvoiceForm component (#40)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Create the `/invoices/new` route

**Files:**
- Create: `frontend/src/app/(dashboard)/invoices/new/page.tsx`

- [ ] **Step 1: Create the route file**

Create `frontend/src/app/(dashboard)/invoices/new/page.tsx` with exactly this content:

```tsx
'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import InvoiceForm from '@/components/invoices/InvoiceForm'

export default function NewInvoicePage() {
  const router = useRouter()
  return (
    <div className="space-y-6">
      <div>
        <Link href="/invoices" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Invoices
        </Link>
        <h1 className="text-3xl font-serif font-medium">New Invoice</h1>
        <p className="text-sm text-black/75 mt-1">Create a sales invoice to a customer</p>
      </div>
      <InvoiceForm
        mode="create"
        onSaved={(id) => router.push(`/invoices/${id}`)}
        onCancel={() => router.push('/invoices')}
      />
    </div>
  )
}
```

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: build SUCCEEDS; route `/invoices/new` appears in the route list.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(dashboard\)/invoices/new/page.tsx
git commit -m "feat(invoices): full-page /invoices/new route (#40)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Create the `/invoices/[id]/edit` route

**Files:**
- Create: `frontend/src/app/(dashboard)/invoices/[id]/edit/page.tsx`

Fetches the full invoice (the same `GET /api/invoices/{id}` the old `openEdit` used), shows a loading state, redirects to the list on failure, then renders `InvoiceForm` in edit mode.

- [ ] **Step 1: Create the route file**

Create `frontend/src/app/(dashboard)/invoices/[id]/edit/page.tsx` with exactly this content:

```tsx
'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import InvoiceForm, { InvoiceFull } from '@/components/invoices/InvoiceForm'
import { apiFetch } from '@/lib/api'

export default function EditInvoicePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [invoice, setInvoice] = useState<InvoiceFull | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    apiFetch<InvoiceFull>(`/api/invoices/${id}`)
      .then(setInvoice)
      .catch(() => setFailed(true))
  }, [id])

  useEffect(() => {
    if (failed) router.replace('/invoices')
  }, [failed, router])

  if (failed) return null
  if (!invoice) return <div className="p-8 text-sm text-black/50">Loading invoice…</div>

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/invoices/${invoice.id}`} className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Invoice {invoice.number}
        </Link>
        <h1 className="text-3xl font-serif font-medium">Edit Invoice {invoice.number}</h1>
      </div>
      <InvoiceForm
        mode="edit"
        invoice={invoice}
        onSaved={(savedId) => router.push(`/invoices/${savedId}`)}
        onCancel={() => router.push('/invoices')}
      />
    </div>
  )
}
```

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: build SUCCEEDS; route `/invoices/[id]/edit` appears in the route list.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(dashboard\)/invoices/\[id\]/edit/page.tsx
git commit -m "feat(invoices): full-page /invoices/[id]/edit route (#40)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Slim the invoices list page (remove the modal)

**Files:**
- Modify (full replace): `frontend/src/app/(dashboard)/invoices/page.tsx`

Replace the entire file. All modal/form state, `loadModalData`, `openEdit`, `handleSave`, the totals block, the `?edit=` auto-open effect, the AR/revenue derivations, and the modal JSX are removed. The "New Invoice" buttons and the row Edit button become `router.push` navigations. `useSearchParams`/`Suspense`/`useSettings`/`LineItemsTable` imports drop out.

- [ ] **Step 1: Replace the file**

Overwrite `frontend/src/app/(dashboard)/invoices/page.tsx` with exactly this content:

```tsx
'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Plus, Download, Printer, FileSignature } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import FilterBar from '@/components/FilterBar'
import SortableHeader from '@/components/SortableHeader'
import BulkActionBar from '@/components/BulkActionBar'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'

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

export default function Invoices() {
  const fmt = useFmt()
  const router = useRouter()
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
    if (search) params.set('search', search)
    if (status) params.set('status', status)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    apiFetch<{ total: number; items: Invoice[] }>(`/api/invoices?${params}`)
      .then(d => { setInvoices(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  const handleSort = (field: string, dir: 'asc' | 'desc') => {
    setSortBy(field); setSortDir(dir); setPage(1)
  }

  useEffect(() => { setPage(1) }, [search, status, dateFrom, dateTo])
  useEffect(load, [page, search, status, dateFrom, dateTo, sortBy, sortDir])
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
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Printer className="w-4 h-4" />
            Print
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
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
                <th className="px-4 py-4 w-10">
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
                <th className="ui-th" />
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
                  <td className="px-4 py-4 w-10">
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
                  <td className="ui-td text-black/70">{inv.issue_date}</td>
                  <td className={`ui-td ${inv.status === 'overdue' ? 'text-red-600 font-medium' : 'text-black/70'}`}>{inv.due_date}</td>
                  <td className="ui-td text-right font-mono">{fmt(inv.total)}</td>
                  <td className="ui-td text-center">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${statusColors[inv.status] ?? 'bg-gray-100 text-gray-700'}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td className="ui-td">
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
```

- [ ] **Step 2: Build & lint**

Run: `npm run build && npm run lint`
Expected: both SUCCEED. (No remaining references to removed symbols like `LineItemsTable`, `useSettings`, `modalOpen`, `useSearchParams`.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(dashboard\)/invoices/page.tsx
git commit -m "refactor(invoices): list page routes to full-page forms, modal removed (#40)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Retarget the detail-page Edit link

**Files:**
- Modify: `frontend/src/app/(dashboard)/invoices/[id]/page.tsx:121`

The detail page's enabled Edit link currently points at `/invoices?edit=${inv.id}` (the old modal trigger). Point it at the new edit route. The disabled Edit affordance for paid/partial invoices (no `href`) is left unchanged.

- [ ] **Step 1: Edit the link**

In `frontend/src/app/(dashboard)/invoices/[id]/page.tsx`, change:

```tsx
              href={`/invoices?edit=${inv.id}`}
```

to:

```tsx
              href={`/invoices/${inv.id}/edit`}
```

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: build SUCCEEDS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(dashboard\)/invoices/\[id\]/page.tsx
git commit -m "refactor(invoices): detail Edit link targets full-page edit route (#40)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Verification & manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Clean build + lint**

Run: `npm run build && npm run lint`
Expected: both SUCCEED with no errors.

- [ ] **Step 2: Manual smoke (dev server)**

Start the stack (`./dev.sh` from repo root, or `npm run dev` in `frontend/` against a running backend), log in, then verify:

1. **Create** — Invoices list → "New Invoice" → lands on `/invoices/new` (full page, no modal). Pick a customer, add a line, Post Invoice → redirects to `/invoices/{id}` detail page showing the saved invoice.
2. **Edit draft** — From the list, click "Edit" on a draft → lands on `/invoices/{id}/edit` with fields + lines pre-filled. Change a line → Save Changes → redirects to detail, change reflected.
3. **Edit from detail** — Open a draft's detail page → "Edit" button → lands on the edit route (not the list).
4. **Posted-edit guard** — Edit a `sent`/`posted`/`overdue` invoice → Save → the amber "Confirm posted-invoice edit" panel appears; confirming saves, cancelling dismisses.
5. **Cancel** — Cancel on both `/invoices/new` and the edit route → returns to `/invoices`.
6. **Keyboard** — Press the "new" shortcut on the list (fires `kbd:new`) → navigates to `/invoices/new`.

- [ ] **Step 3: Final confirmation**

No commit needed (Tasks 1–5 already committed). Report the build/lint result and the smoke-test outcome.

---

## Notes for the implementer

- **Next.js 16:** dynamic route params are async — always `params: Promise<{ id: string }>` then `const { id } = use(params)` (see `journal/[id]/page.tsx` for the established pattern). Read `node_modules/next/dist/docs/` before improvising any App Router API.
- **No API changes.** `POST /api/invoices` returns the created invoice (used for `created.id`); `GET /api/invoices/{id}` returns the full invoice incl. `lines`, `gst_rate`, `ar_account_id`, `revenue_account_id`, `payment_term_id`, `currency`, `exchange_rate` (the old `openEdit` relied on exactly these).
- **Out of scope:** the other six named forms (bills, payments-received, bill-payments, products, customers, vendors) replicate this same five-unit shape in later batches — do not touch them here.
