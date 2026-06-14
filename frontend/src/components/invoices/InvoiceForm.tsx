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
  assigned_to_id: number | null
  lines: (LineItem & { tax_code_id?: number | null })[]
}

interface Customer { id: number; name: string }
interface StaffUser { id: number; name: string; email: string }
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
  assigned_to_id: string
}

const emptyForm: FormState = {
  customer_id: '', customer_name: '', issue_date: new Date().toISOString().split('T')[0],
  due_date: '', payment_term_id: '', description: '', notes: '', internal_memo: '', gst_rate: '17',
  ar_account_id: '', revenue_account_id: '',
  currency: 'PKR', exchange_rate: '1',
  assigned_to_id: '',
}

interface Props {
  mode: 'create' | 'edit'
  invoice?: InvoiceFull
  initialCustomerId?: number
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function InvoiceForm({ mode, invoice, initialCustomerId, onSaved, onCancel }: Props) {
  const fmt = useFmt()
  const { settings } = useSettings()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [lines, setLines] = useState<LineItem[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [customers, setCustomers] = useState<Customer[]>([])
  const [staff, setStaff] = useState<StaffUser[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [paymentTerms, setPaymentTerms] = useState<PaymentTerm[]>([])
  const [taxCodes, setTaxCodes] = useState<TaxCodeOption[]>([])
  const [customerBalance, setCustomerBalance] = useState<number | null>(null)
  const [confirmPostedEdit, setConfirmPostedEdit] = useState(false)
  const [applyingPromos, setApplyingPromos] = useState(false)
  const [promoMsg, setPromoMsg] = useState("")

  useEffect(() => {
    Promise.all([
      apiFetch<{ total: number; items: Customer[] }>('/api/customers?limit=200'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
      apiFetch<{ total: number; items: Product[] }>('/api/products?limit=500'),
      apiFetch<PaymentTerm[]>('/api/payment-terms'),
      apiFetch<{ total: number; items: TaxCodeOption[] }>('/api/tax-codes?limit=100'),
      apiFetch<StaffUser[]>('/api/commissions/staff'),
    ]).then(([c, a, p, terms, tc, s]) => {
      setCustomers(c.items); setAccounts(a.items); setProducts(p.items)
      setPaymentTerms(terms); setTaxCodes(tc.items); setStaff(s)
      if (mode === 'create' && initialCustomerId) {
        const cust = c.items.find((x: Customer) => x.id === initialCustomerId)
        if (cust) setForm(f => ({ ...f, customer_id: String(cust.id), customer_name: cust.name }))
      }
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
        assigned_to_id: invoice.assigned_to_id ? String(invoice.assigned_to_id) : '',
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

  const handleApplyPromos = async () => {
    if (lines.length === 0) return
    setApplyingPromos(true); setPromoMsg("")
    try {
      const subtotal = lines.reduce((s, l) => s + l.amount, 0)
      const suggestions = await apiFetch<Array<{
        rule_id: number; rule_name: string; line_idx: number | null
        discount_type: string; discount_value: number | null
        giveaway_product_id: number | null; giveaway_qty: number | null
      }>>("/api/promo-rules/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date: form.issue_date || new Date().toISOString().split("T")[0],
          lines: lines.map(l => ({ product_id: l.product_id ?? 0, qty: l.qty, rate: l.rate })),
          invoice_total: subtotal,
        }),
      })
      if (suggestions.length === 0) { setPromoMsg("No matching promos found."); return }
      let applied = 0
      const newLines = [...lines]
      for (const s of suggestions) {
        if (s.discount_type === "giveaway") {
          const gp = products.find(p => p.id === s.giveaway_product_id)
          if (gp) {
            newLines.push({
              product_id: gp.id,
              description: `Giveaway: ${gp.name}`,
              qty: s.giveaway_qty ?? 1,
              unit: gp.unit,
              rate: 0,
              discount_pct: 0,
              promo_rule_id: s.rule_id,
              amount: 0,
              tax_code_id: null,
            })
            applied++
          }
        } else if (s.line_idx !== null && s.line_idx < newLines.length) {
          const l = newLines[s.line_idx]
          const disc = s.discount_type === "percent"
            ? (s.discount_value ?? 0)
            : (s.discount_value ? Math.min(s.discount_value / l.rate * 100, 100) : 0)
          newLines[s.line_idx] = {
            ...l,
            discount_pct: parseFloat(disc.toFixed(2)),
            promo_rule_id: s.rule_id,
            amount: Math.round(l.qty * l.rate * (1 - disc / 100) * 100) / 100,
          }
          applied++
        }
      }
      setLines(newLines)
      setPromoMsg(`${applied} promo${applied !== 1 ? "s" : ""} applied.`)
    } catch (e) {
      setPromoMsg(e instanceof Error ? e.message : "Failed to check promos")
    } finally {
      setApplyingPromos(false)
    }
  }

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
        discount_pct: l.discount_pct ?? 0,
        promo_rule_id: l.promo_rule_id ?? null,
        tax_code_id: l.tax_code_id ?? null,
      })),
      gst_rate: parseFloat(form.gst_rate) || 0,
      ar_account_id: form.ar_account_id ? parseInt(form.ar_account_id) : null,
      revenue_account_id: form.revenue_account_id ? parseInt(form.revenue_account_id) : null,
      currency: form.currency || settings.currency,
      exchange_rate: parseFloat(form.exchange_rate) || 1,
      assigned_to_id: form.assigned_to_id ? parseInt(form.assigned_to_id) : null,
    }
    try {
      if (mode === 'edit' && invoice) {
        await apiFetch(`/api/invoices/${invoice.id}`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        })
        onSaved(invoice.id)
      } else {
        const created = await apiFetch<InvoiceFull>('/api/invoices', {
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
    <div className="bg-white rounded-2xl border border-[#ede9e2] p-8 max-w-3xl mx-auto">
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
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Description</label>
            <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
              placeholder="e.g. Consulting services — May 2026"
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Sales Person <span className="font-normal normal-case text-[#1a1814]/40">(optional)</span></label>
            <select value={form.assigned_to_id} onChange={e => setForm(p => ({ ...p, assigned_to_id: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
              <option value="">None</option>
              {staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
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
          <div className="flex items-center justify-between mb-2">
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Line Items</label>
            <div className="flex items-center gap-2">
              {promoMsg && <span className="text-xs text-[#b8943f]">{promoMsg}</span>}
              <button type="button" onClick={handleApplyPromos} disabled={applyingPromos || lines.length === 0}
                className="px-3 py-1.5 text-xs font-semibold bg-[#faf6ec] border border-[#b8943f]/40 text-[#b8943f] rounded-lg hover:bg-[#b8943f]/10 disabled:opacity-40 transition-colors">
                {applyingPromos ? "Checking…" : "Apply Promos"}
              </button>
            </div>
          </div>
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
          <button onClick={() => { setConfirmPostedEdit(false); onCancel() }} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
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
