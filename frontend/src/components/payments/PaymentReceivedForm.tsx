'use client'

import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt, useDp, useSettings } from '@/context/SettingsContext'

interface OpenInvoice {
  id: number
  number: string
  customer_name: string | null
  issue_date?: string
  due_date: string
  total: number
  balance_due: number
  currency?: string
  exchange_rate?: number
  carrying_rate?: number
}

interface Account { id: number; code: string; name: string; type: string }

interface AnalyticAccount { id: number; code: string; name: string; type: string }

interface AllocationRow {
  invoice_id: number
  checked: boolean
  amount: string
}

interface PayForm {
  customer_id: string
  payment_date: string
  amount: string
  method: string
  reference: string
  cash_account_id: string
  analytic_account_id: string
  exchange_rate: string
}

const emptyForm: PayForm = {
  customer_id: '', payment_date: new Date().toISOString().split('T')[0],
  amount: '', method: 'cash', reference: '', cash_account_id: '', analytic_account_id: '',
  exchange_rate: '',
}

interface Props {
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function PaymentReceivedForm({ onSaved, onCancel }: Props) {
  const fmt = useFmt()
  const dp = useDp()
  const { settings } = useSettings()
  const baseCurrency = (settings.currency || 'USD').toUpperCase()
  const [form, setForm] = useState<PayForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [openInvoices, setOpenInvoices] = useState<OpenInvoice[]>([])
  const [allocations, setAllocations] = useState<AllocationRow[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [customers, setCustomers] = useState<{ id: number; name: string }[]>([])
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])

  // Static data: customers, accounts, analytic accounts
  useEffect(() => {
    apiFetch<{ items: { id: number; name: string }[] }>('/api/customers?limit=500')
      .then(d => setCustomers(d.items))
      .catch(() => {})
    apiFetch<AnalyticAccount[] | { items: AnalyticAccount[] }>('/api/analytic-accounts')
      .then(an => {
        const anItems = Array.isArray(an) ? an : ((an as { items: AnalyticAccount[] }).items ?? [])
        setAnalyticAccounts(anItems)
      })
      .catch(() => {})
    apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500')
      .then(d => setAccounts(d.items))
      .catch(() => {})
  }, [])

  // Reload open invoices on mount and whenever customer selection changes.
  // No customer selected → all open invoices; customer selected → that customer's only.
  useEffect(() => {
    const url = form.customer_id
      ? `/api/invoices/open-for-allocation?customer_id=${form.customer_id}`
      : `/api/invoices/open-for-allocation`
    apiFetch<OpenInvoice[]>(url)
      .then(invs => {
        setOpenInvoices(invs)
        setAllocations(invs.map(i => ({ invoice_id: i.id, checked: false, amount: '' })))
      })
      .catch(() => { setOpenInvoices([]); setAllocations([]) })
  }, [form.customer_id])

  const totalApplied = allocations
    .filter(a => a.checked && parseFloat(a.amount) > 0)
    .reduce((s, a) => s + parseFloat(a.amount), 0)

  const paymentAmount = parseFloat(form.amount) || 0
  const diff = Math.abs(paymentAmount - totalApplied)
  const hasAllocations = allocations.some(a => a.checked)

  const checkedInvs = openInvoices.filter(inv =>
    allocations.some(a => a.invoice_id === inv.id && a.checked)
  )
  const fxCurrency = checkedInvs[0]?.currency
  const showFx = checkedInvs.length > 0
    && checkedInvs.every(i => i.currency === checkedInvs[0].currency)
    && Boolean(fxCurrency)
    && fxCurrency.toUpperCase() !== baseCurrency

  // Prefill settlement rate from carrying rate of first checked invoice when FX fields appear
  useEffect(() => {
    if (!showFx || !checkedInvs[0]) return
    const rate = checkedInvs[0].carrying_rate ?? checkedInvs[0].exchange_rate
    if (rate != null) setForm(p => (p.exchange_rate ? p : { ...p, exchange_rate: String(rate) }))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showFx, checkedInvs.map(i => i.id).join(',')])

  const handleSave = async () => {
    if (!form.customer_id) { setFormError('Customer is required'); return }
    if (!form.amount || paymentAmount <= 0) { setFormError('Amount must be > 0'); return }
    if (!form.payment_date) { setFormError('Date is required'); return }
    if (showFx && checkedInvs.some(i => i.currency !== checkedInvs[0].currency)) {
      setFormError('Cannot allocate across mixed document currencies'); return
    }
    setSaving(true); setFormError('')
    try {
      const body: Record<string, unknown> = {
        customer_id: form.customer_id ? Number(form.customer_id) : null,
        payment_date: form.payment_date,
        amount: paymentAmount,
        method: form.method,
        reference: form.reference || null,
        cash_account_id: form.cash_account_id ? parseInt(form.cash_account_id) : null,
        analytic_account_id: form.analytic_account_id ? parseInt(form.analytic_account_id) : null,
      }
      if (showFx && fxCurrency) {
        body.currency = fxCurrency
        if (form.exchange_rate) body.exchange_rate = parseFloat(form.exchange_rate)
      }
      const allocationLines = allocations
        .filter(a => a.checked && parseFloat(a.amount) > 0)
        .map(a => ({ invoice_id: a.invoice_id, amount: parseFloat(a.amount) }))
      if (allocationLines.length > 0) {
        body.allocations = allocationLines
      }
      const created = await apiFetch<{ id: number }>('/api/payments-received', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      onSaved(created.id)
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const setAlloc = (invoiceId: number, field: 'checked' | 'amount', value: boolean | string) => {
    setAllocations(prev => prev.map(a =>
      a.invoice_id === invoiceId ? { ...a, [field]: value } : a
    ))
  }

  const handleCheck = (inv: OpenInvoice, checked: boolean) => {
    setAlloc(inv.id, 'checked', checked)
    if (checked) {
      const remaining = paymentAmount - totalApplied
      const suggested = Math.min(inv.balance_due, remaining > 0 ? remaining : inv.balance_due)
      setAlloc(inv.id, 'amount', String(suggested.toFixed(dp)))
    } else {
      setAlloc(inv.id, 'amount', '')
    }
  }

  const cashAccounts = accounts.filter(a => a.type === 'Asset')

  return (
    <div className="bg-white rounded-2xl border border-[var(--border)] p-4 sm:p-8 max-w-3xl mx-auto">
      <div className="space-y-4">
        {/* Header fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Customer *</label>
            <select
              required
              value={form.customer_id}
              onChange={e => setForm(p => ({ ...p, customer_id: e.target.value }))}
              className="ui-field w-full bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]"
            >
              <option value="">— Select customer —</option>
              {customers.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Payment Date</label>
            <input type="date" value={form.payment_date} onChange={e => setForm(p => ({ ...p, payment_date: e.target.value }))}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
              Amount Received{showFx && fxCurrency ? ` (${fxCurrency})` : ''}
            </label>
            <input type="number" step="0.01" value={form.amount}
              onChange={e => setForm(p => ({ ...p, amount: e.target.value }))}
              placeholder="0.00" className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Method</label>
            <select value={form.method} onChange={e => setForm(p => ({ ...p, method: e.target.value }))}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
              {['cash', 'bank_transfer', 'check', 'credit_card'].map(m => <option key={m} value={m}>{m.replace('_', ' ')}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Reference #</label>
            <input value={form.reference} onChange={e => setForm(p => ({ ...p, reference: e.target.value }))}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
          </div>
        </div>
        {showFx && (
          <div className="grid grid-cols-2 gap-4 p-3 rounded-xl bg-amber-50/60 border border-amber-200">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Currency</label>
              <div className="px-3 py-2 text-sm font-mono font-bold">{fxCurrency}</div>
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
                Settlement rate → {baseCurrency}
              </label>
              <input type="number" step="0.0001" value={form.exchange_rate}
                onChange={e => setForm(p => ({ ...p, exchange_rate: e.target.value }))}
                className="w-full px-3 py-2 bg-white rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
            </div>
            <p className="col-span-2 text-xs text-amber-800">
              Amount and allocations are in {fxCurrency}. GL posts cash at settlement rate and clears AR at each invoice&apos;s carrying rate; difference → Realised FX (4903).
            </p>
          </div>
        )}
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Cash/Bank Account</label>
          <select value={form.cash_account_id} onChange={e => setForm(p => ({ ...p, cash_account_id: e.target.value }))}
            className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
            <option value="">Auto (1000 Cash in Hand)</option>
            {cashAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
          </select>
        </div>
        {analyticAccounts.length > 0 && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
              Analytic Account <span className="font-normal normal-case">(optional)</span>
            </label>
            <select
              value={form.analytic_account_id}
              onChange={e => setForm(p => ({ ...p, analytic_account_id: e.target.value }))}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            >
              <option value="">— none —</option>
              {analyticAccounts.map(a => (
                <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Invoice allocation checklist */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-2">
            Apply to Open Invoices <span className="font-normal normal-case">(optional)</span>
            {form.customer_id && <span className="ml-1 font-normal normal-case text-[var(--primary)]">— filtered by selected customer</span>}
          </label>
          {openInvoices.length === 0 ? (
            <p className="text-xs text-[var(--text-muted)] italic py-2">
              {form.customer_id ? 'No outstanding invoices for this customer.' : 'No outstanding invoices.'}
            </p>
          ) : (
            <div className="border border-[var(--border)] rounded-xl overflow-hidden text-sm">
              <table className="w-full">
                <thead className="bg-[var(--bg-page)]">
                  <tr>
                    <th className="w-8 px-3 py-2" />
                    <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Invoice</th>
                    <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">CCY</th>
                    <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Customer</th>
                    <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Balance Due</th>
                    <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Apply</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {openInvoices.map(inv => {
                    const row = allocations.find(a => a.invoice_id === inv.id)
                    if (!row) return null
                    return (
                      <tr key={inv.id} className={row.checked ? 'bg-amber-50/40' : 'hover:bg-[var(--bg-page)]/40'}>
                        <td className="px-3 py-2 text-center">
                          <input
                            type="checkbox"
                            checked={row.checked}
                            onChange={e => handleCheck(inv, e.target.checked)}
                            className="accent-[var(--primary)]"
                          />
                        </td>
                        <td className="px-3 py-2 font-mono text-[var(--primary)] font-bold text-xs">{inv.number}</td>
                        <td className="px-3 py-2 font-mono text-xs">{inv.currency ?? '—'}</td>
                        <td className="px-3 py-2 text-[var(--text-muted)] truncate max-w-[120px] text-xs">{inv.customer_name ?? '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{fmt(inv.balance_due)}</td>
                        <td className="px-3 py-2 text-right">
                          {row.checked ? (
                            <input
                              type="number" step="0.01" min="0.01"
                              value={row.amount}
                              onChange={e => setAlloc(inv.id, 'amount', e.target.value)}
                              className="w-24 text-right px-2 py-1 border border-[var(--border)] rounded text-xs outline-none focus:ring-1 focus:ring-[var(--primary)]"
                            />
                          ) : (
                            <span className="text-[var(--border)] text-xs">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Allocation summary */}
          {hasAllocations && (
            <div className={`mt-2 flex items-center justify-between text-xs px-3 py-2 rounded-lg ${diff > 0.01 ? 'bg-amber-50 border border-amber-200' : 'bg-green-50 border border-green-200'}`}>
              <span className="text-[var(--text-muted)]">
                Payment: <strong>{fmt(paymentAmount)}</strong> · Applied: <strong>{fmt(totalApplied)}</strong>
              </span>
              {diff > 0.01 ? (
                <span className="flex items-center gap-1 text-amber-700 font-medium">
                  <AlertCircle className="w-3 h-3" /> Unallocated: {fmt(diff)}
                </span>
              ) : (
                <span className="text-green-700 font-medium">Fully applied ✓</span>
              )}
            </div>
          )}
        </div>

        {formError && <p className="text-red-600 text-sm">{formError}</p>}
        <p className="text-xs text-[var(--text-muted)]">
          {showFx
            ? `GL posting: Dr Cash (settle rate) / Cr AR (carrying rate) / Realised FX 4903`
            : `GL posting: Dr Cash/Bank / Cr Accounts Receivable`}
        </p>
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onCancel} className="px-6 py-3 border border-[var(--text-primary)]/10 rounded-xl font-bold hover:bg-[var(--bg-page)]">Cancel</button>
          <button onClick={handleSave} disabled={!form.customer_id || saving} className="px-6 py-3 bg-[var(--text-primary)] text-white rounded-xl font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50">
            {saving ? 'Saving...' : 'Record Payment'}
          </button>
        </div>
      </div>
    </div>
  )
}
