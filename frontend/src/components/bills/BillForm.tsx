'use client'

import { useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { DimensionPickers, slotsToPayload, type AnalyticSlots } from '@/components/DimensionPickers'
import CurrencyRatePicker from '@/components/fx/CurrencyRatePicker'
import { useFmt, useSettings } from '@/context/SettingsContext'
import LineItemsTable, { LineItem, TaxCodeOption } from '@/components/LineItemsTable'
import { CustomFieldsInputs, type CustomFieldValues } from '@/components/studio/CustomFieldsInputs'
import { useFormSchema } from '@/components/studio/formSchema'

export interface BillFull {
  id: number
  number: string
  status: string
  vendor_id: number | null
  vendor_name: string | null
  bill_date: string
  due_date: string
  payment_term_id: number | null
  description: string | null
  notes: string | null
  internal_memo: string | null
  gst_rate: number
  ap_account_id: number | null
  expense_account_id: number | null
  analytic_account_id: number | null
  currency: string
  exchange_rate: number
  is_intercompany?: boolean
  ic_counterparty_tenant_id?: number | null
  custom_fields?: CustomFieldValues
  lines: (LineItem & { tax_code_id?: number | null })[]
}

interface Vendor { id: number; name: string }
interface Account { id: number; code: string; name: string; type: string }
interface AnalyticAccount { id: number; code: string; name: string; type: string }
interface Product { id: number; name: string; code: string | null; unit: string; default_rate: number; product_type: string; stock_qty?: number }
interface PaymentTerm { id: number; code: string; name: string; days: number }
interface IcCounterparty { tenant_id: number; name: string; relationship: string }

interface FormState {
  vendor_id: string
  vendor_name: string
  bill_date: string
  due_date: string
  payment_term_id: string
  description: string
  notes: string
  internal_memo: string
  gst_rate: string
  ap_account_id: string
  expense_account_id: string
  analytic_account_id: string
  currency: string
  exchange_rate: string
  is_intercompany: boolean
  ic_counterparty_tenant_id: string
}

const emptyForm: FormState = {
  vendor_id: '', vendor_name: '', bill_date: new Date().toISOString().split('T')[0],
  due_date: '', payment_term_id: '', description: '', notes: '', internal_memo: '', gst_rate: '17',
  ap_account_id: '', expense_account_id: '', analytic_account_id: '',
  currency: 'PKR', exchange_rate: '1',
  is_intercompany: false, ic_counterparty_tenant_id: '',
}

interface Props {
  mode: 'create' | 'edit'
  bill?: BillFull
  initialVendorId?: number
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function BillForm({ mode, bill, initialVendorId, onSaved, onCancel }: Props) {
  const fmt = useFmt()
  const { settings } = useSettings()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [lines, setLines] = useState<LineItem[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [paymentTerms, setPaymentTerms] = useState<PaymentTerm[]>([])
  const [taxCodes, setTaxCodes] = useState<TaxCodeOption[]>([])
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])
  const [analyticSlots, setAnalyticSlots] = useState<AnalyticSlots>({})
  const [confirmPostedEdit, setConfirmPostedEdit] = useState(false)
  const [icCounterparties, setIcCounterparties] = useState<IcCounterparty[]>([])
  const [customFields, setCustomFields] = useState<CustomFieldValues>({})
  const { fields: schemaFields, fieldAccess, visible: vis, required: req } = useFormSchema('bill')
  const currencyTouched = useRef(false)

  // Sync default currency to tenant base once settings load (create mode only)
  useEffect(() => {
    if (mode === 'create' && !currencyTouched.current) {
      setForm(f => ({ ...f, currency: settings.currency }))
    }
  }, [settings.currency]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    Promise.all([
      apiFetch<{ total: number; items: Vendor[] }>('/api/vendors?limit=200'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
      apiFetch<{ total: number; items: Product[] }>('/api/products?limit=500'),
      apiFetch<PaymentTerm[]>('/api/payment-terms'),
      apiFetch<{ total: number; items: TaxCodeOption[] }>('/api/tax-codes?limit=100'),
      apiFetch<AnalyticAccount[] | { items: AnalyticAccount[] }>('/api/analytic-accounts'),
      apiFetch<IcCounterparty[]>('/api/intercompany/counterparties').catch(() => [] as IcCounterparty[]),
    ]).then(([v, a, p, terms, tc, an, cps]) => {
      setVendors(v.items); setAccounts(a.items); setProducts(p.items)
      setPaymentTerms(terms); setTaxCodes(tc.items)
      const anItems = Array.isArray(an) ? an : ((an as { items: AnalyticAccount[] }).items ?? [])
      setAnalyticAccounts(anItems)
      setIcCounterparties(Array.isArray(cps) ? cps : [])
      if (mode === 'create' && initialVendorId) {
        const vend = v.items.find((x: Vendor) => x.id === initialVendorId)
        if (vend) setForm(f => ({ ...f, vendor_id: String(vend.id), vendor_name: vend.name }))
      }
    }).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mode === 'edit' && bill) {
      setForm({
        vendor_id: String(bill.vendor_id ?? ''),
        vendor_name: bill.vendor_name ?? '',
        bill_date: bill.bill_date,
        due_date: bill.due_date,
        payment_term_id: bill.payment_term_id ? String(bill.payment_term_id) : '',
        description: bill.description ?? '',
        notes: bill.notes ?? '',
        internal_memo: bill.internal_memo ?? '',
        gst_rate: String(bill.gst_rate ?? 17),
        ap_account_id: bill.ap_account_id ? String(bill.ap_account_id) : '',
        expense_account_id: bill.expense_account_id ? String(bill.expense_account_id) : '',
        analytic_account_id: bill.analytic_account_id ? String(bill.analytic_account_id) : '',
        currency: bill.currency ?? 'PKR',
        exchange_rate: String(bill.exchange_rate ?? 1),
        is_intercompany: Boolean(bill.is_intercompany),
        ic_counterparty_tenant_id: bill.ic_counterparty_tenant_id
          ? String(bill.ic_counterparty_tenant_id) : '',
      })
      setCustomFields(bill.custom_fields ?? {})
      setAnalyticSlots({
        0: bill.analytic_account_id ? String(bill.analytic_account_id) : "",
        1: (bill as { analytic_2_id?: number | null }).analytic_2_id
          ? String((bill as { analytic_2_id?: number | null }).analytic_2_id)
          : "",
        2: (bill as { analytic_3_id?: number | null }).analytic_3_id
          ? String((bill as { analytic_3_id?: number | null }).analytic_3_id)
          : "",
      })
      setLines((bill.lines ?? []).map(l => ({
        product_id: l.product_id ?? undefined,
        description: l.description,
        qty: Number(l.qty),
        unit: l.unit ?? 'pcs',
        rate: Number(l.rate),
        amount: Number(l.amount),
        tax_code_id: l.tax_code_id ?? null,
      })))
    }
  }, [mode, bill])

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

  const apAccounts = accounts.filter(a => a.type === 'Liability')
  const expenseAccounts = accounts.filter(a => a.type === 'Expense')

  const handleSave = async () => {
    if (lines.length === 0) { setFormError('Add at least one line item'); return }
    if (lines.some(l => !l.description.trim())) { setFormError('All lines must have a description'); return }
    if (!form.bill_date || (!form.due_date && !form.payment_term_id)) {
      setFormError('Bill date required; provide either a due date or a payment term'); return
    }
    if (mode === 'edit' && bill && bill.status !== 'draft') {
      if (!confirmPostedEdit) { setConfirmPostedEdit(true); return }
      setConfirmPostedEdit(false)
    }
    setSaving(true); setFormError('')
    const body = {
      vendor_id: form.vendor_id ? parseInt(form.vendor_id) : null,
      vendor_name: form.vendor_name || null,
      bill_date: form.bill_date,
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
      ap_account_id: form.ap_account_id ? parseInt(form.ap_account_id) : null,
      expense_account_id: form.expense_account_id ? parseInt(form.expense_account_id) : null,
      ...slotsToPayload(analyticSlots),
      currency: form.currency || settings.currency,
      exchange_rate: parseFloat(form.exchange_rate) || 1,
      is_intercompany: form.is_intercompany,
      ic_counterparty_tenant_id: form.is_intercompany && form.ic_counterparty_tenant_id
        ? parseInt(form.ic_counterparty_tenant_id) : null,
      custom_fields: customFields,
    }
    try {
      if (mode === 'edit' && bill) {
        await apiFetch(`/api/bills/${bill.id}`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        })
        onSaved(bill.id)
      } else {
        const created = await apiFetch<BillFull>('/api/bills', {
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
    <div className="bg-white rounded-2xl border border-[var(--border)] p-4 sm:p-6 max-w-6xl mx-auto">
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Vendor</label>
            <select value={form.vendor_id}
              onChange={e => { const v = vendors.find(v => v.id === parseInt(e.target.value)); setForm(p => ({ ...p, vendor_id: e.target.value, vendor_name: v?.name ?? '' })) }}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
              <option value="">— Select or type name —</option>
              {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>
          {vis('vendor_name') && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
              Vendor Name
              {req('vendor_name') ? <span className="text-red-600"> *</span> : null}
            </label>
            <input value={form.vendor_name} onChange={e => setForm(p => ({ ...p, vendor_name: e.target.value }))}
              placeholder="or type manually"
              required={req('vendor_name')}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
          </div>
          )}
        </div>
        {vis('is_intercompany') && icCounterparties.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-3 rounded-xl bg-[var(--bg-page)] border border-[var(--border)]">
            <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
              <input
                type="checkbox"
                checked={form.is_intercompany}
                onChange={e => setForm(p => ({
                  ...p,
                  is_intercompany: e.target.checked,
                  ic_counterparty_tenant_id: e.target.checked ? p.ic_counterparty_tenant_id : '',
                }))}
                className="rounded border-[var(--border)]"
              />
              Intercompany bill
            </label>
            {form.is_intercompany && (
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
                  IC Counterparty
                </label>
                <select
                  value={form.ic_counterparty_tenant_id}
                  onChange={e => setForm(p => ({ ...p, ic_counterparty_tenant_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-white rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
                >
                  <option value="">— Select entity —</option>
                  {icCounterparties.map(c => (
                    <option key={c.tenant_id} value={c.tenant_id}>{c.name}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Bill Date</label>
            <input type="date" value={form.bill_date} onChange={e => setForm(p => ({ ...p, bill_date: e.target.value }))}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
          </div>
          {vis('payment_term_id') && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Payment Term</label>
            <select
              value={form.payment_term_id}
              onChange={e => {
                const termId = e.target.value
                setForm(p => {
                  const term = paymentTerms.find(t => String(t.id) === termId)
                  const due = term && p.bill_date
                    ? new Date(new Date(p.bill_date).getTime() + term.days * 86400000).toISOString().split('T')[0]
                    : p.due_date
                  return { ...p, payment_term_id: termId, due_date: due }
                })
              }}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            >
              <option value="">— select —</option>
              {paymentTerms.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          )}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Due Date</label>
            <input type="date" value={form.due_date} onChange={e => setForm(p => ({ ...p, due_date: e.target.value }))}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
          </div>
        </div>
        {vis('description') && (
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
            Description
            {req('description') ? <span className="text-red-600"> *</span> : null}
          </label>
          <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
            placeholder="e.g. Office supplies — May 2026"
            required={req('description')}
            className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
        </div>
        )}

        {vis('currency') && (
        <CurrencyRatePicker
          currency={form.currency}
          exchangeRate={form.exchange_rate}
          baseCurrency={settings.currency}
          onDate={form.bill_date}
          onCurrencyChange={cur => {
            currencyTouched.current = true
            setForm(p => ({ ...p, currency: cur, exchange_rate: cur === settings.currency ? '1' : p.exchange_rate }))
          }}
          onRateChange={rate => setForm(p => ({ ...p, exchange_rate: rate }))}
        />
        )}

        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-2">Line Items</label>
          <LineItemsTable lines={lines} onChange={setLines} products={products} taxCodes={taxCodes.filter(t => t.type === 'input')} showTax showStockHint customerId={form.vendor_id ? Number(form.vendor_id) : null} priceKind="purchase" hideDiscount={!vis('discount_pct')} />
        </div>

        <div className="bg-[var(--bg-page)] rounded-xl p-4 space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-[var(--text-muted)]">Subtotal</span>
            <span className="font-mono">{fmt(subtotal)}</span>
          </div>
          <div className="flex justify-between items-center gap-2">
            <span className="text-[var(--text-muted)]">Tax</span>
            {usePerLineTax ? (
              <span className="font-mono text-xs text-[var(--text-muted)]">(per-line) {fmt(gstAmount)}</span>
            ) : vis('gst_rate') ? (
              <div className="flex items-center gap-2">
                <input type="number" min="0" max="100" step="0.5"
                  value={form.gst_rate}
                  onChange={e => setForm(p => ({ ...p, gst_rate: e.target.value }))}
                  className="w-16 text-right bg-white border border-[var(--border)] rounded px-2 py-0.5 text-xs outline-none focus:ring-1 focus:ring-[var(--primary)]"
                />
                <span className="text-[var(--text-muted)] text-xs">%</span>
                <span className="font-mono">{fmt(gstAmount)}</span>
              </div>
            ) : (
              <span className="font-mono">{fmt(gstAmount)}</span>
            )}
          </div>
          <div className="flex justify-between border-t border-[var(--border)] pt-2 font-bold">
            <span>Total ({form.currency})</span>
            <span className="font-mono text-[var(--text-primary)]">{fmt(totalAmount)}</span>
          </div>
          {form.currency !== settings.currency && parseFloat(form.exchange_rate) > 0 && (
            <div className="flex justify-between text-xs text-[var(--text-muted)]">
              <span>≈ {settings.currency} equivalent</span>
              <span className="font-mono">{fmt(Math.round(totalAmount * parseFloat(form.exchange_rate) * 100) / 100)}</span>
            </div>
          )}
        </div>

        {(vis('notes') || vis('internal_memo')) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {vis('notes') && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
              Notes (printed)
              {req('notes') ? <span className="text-red-600"> *</span> : null}
            </label>
            <textarea rows={2} value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))}
              placeholder="Printed on the bill for the vendor"
              required={req('notes')}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm resize-none" />
          </div>
          )}
          {vis('internal_memo') && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-amber-700/70 mb-1">Internal Memo</label>
            <textarea rows={2} value={form.internal_memo} onChange={e => setForm(p => ({ ...p, internal_memo: e.target.value }))}
              placeholder="Staff-only note, not printed"
              className="w-full px-3 py-2 bg-amber-50 border border-amber-200 rounded-xl outline-none focus:ring-2 focus:ring-amber-400 text-sm resize-none" />
          </div>
          )}
        </div>
        )}

        <CustomFieldsInputs entity="bill" values={customFields} onChange={setCustomFields} schemaFields={schemaFields} fieldAccess={fieldAccess} />

        {(vis('analytic_account_id') || vis('analytic_2_id') || vis('analytic_3_id')) && (
          <DimensionPickers slots={analyticSlots} onChange={setAnalyticSlots} />
        )}

        {formError && <p className="text-red-600 text-sm">{formError}</p>}
        {confirmPostedEdit && (
          <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 text-sm text-amber-900">
            <p className="font-semibold mb-1">Confirm posted-bill edit</p>
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
        <p className="text-xs text-[var(--text-muted)]">GL posting: Dr Expense / Dr GST Receivable / Cr Accounts Payable</p>
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={() => { setConfirmPostedEdit(false); onCancel() }} className="px-6 py-3 border border-[var(--text-primary)]/10 rounded-xl font-bold hover:bg-[var(--bg-page)]">Cancel</button>
          {!confirmPostedEdit && (
            <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[var(--text-primary)] text-white rounded-xl font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50">
              {saving ? 'Posting...' : mode === 'edit' ? 'Save Changes' : 'Post Bill'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
