'use client'

import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt, useDp } from '@/context/SettingsContext'

interface OpenInvoice {
  id: number
  number: string
  customer_name: string | null
  due_date: string
  total: number
  outstanding: number  // computed client-side from aging data
}

interface AgingItem {
  id: number; number: string; amount: number; customer_name: string | null; due_date: string
}

interface Account { id: number; code: string; name: string; type: string }

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
}

const emptyForm: PayForm = {
  customer_id: '', payment_date: new Date().toISOString().split('T')[0],
  amount: '', method: 'cash', reference: '', cash_account_id: '',
}

interface Props {
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function PaymentReceivedForm({ onSaved, onCancel }: Props) {
  const fmt = useFmt()
  const dp = useDp()
  const [form, setForm] = useState<PayForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [openInvoices, setOpenInvoices] = useState<OpenInvoice[]>([])
  const [allocations, setAllocations] = useState<AllocationRow[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [customers, setCustomers] = useState<{ id: number; name: string }[]>([])

  useEffect(() => {
    apiFetch<{ items: { id: number; name: string }[] }>('/api/customers?limit=500') // limit=500: covers all parties at current scale; raise if tenants exceed this
      .then(d => setCustomers(d.items))
      .catch(() => {})
    Promise.all([
      apiFetch<{ total: number; items: { id: number; number: string; customer_name: string | null; due_date: string; total: number; status?: string }[] }>(
        '/api/invoices?limit=500&sort_by=due_date&sort_dir=asc'
      ),
      apiFetch<{ items: AgingItem[] }>('/api/invoices/aging'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
    ]).then(([invData, agingData, accData]) => {
      // Build outstanding map from aging items
      const outstandingMap = new Map<number, number>()
      agingData.items.forEach(item => outstandingMap.set(item.id, item.amount))
      // Filter to unpaid/open invoices
      const open = invData.items
        .filter(i => !['paid', 'draft'].includes(i.status ?? ''))
        .map(i => ({
          id: i.id,
          number: i.number,
          customer_name: i.customer_name,
          due_date: i.due_date,
          total: i.total,
          outstanding: outstandingMap.get(i.id) ?? i.total,
        }))
      setOpenInvoices(open)
      setAllocations(open.map(i => ({ invoice_id: i.id, checked: false, amount: '' })))
      setAccounts(accData.items)
    }).catch(() => {
      setOpenInvoices([]); setAllocations([]); setAccounts([])
    })
  }, [])

  const totalApplied = allocations
    .filter(a => a.checked && parseFloat(a.amount) > 0)
    .reduce((s, a) => s + parseFloat(a.amount), 0)

  const paymentAmount = parseFloat(form.amount) || 0
  const diff = Math.abs(paymentAmount - totalApplied)
  const hasAllocations = allocations.some(a => a.checked)

  const handleSave = async () => {
    if (!form.customer_id) { setFormError('Customer is required'); return }
    if (!form.amount || paymentAmount <= 0) { setFormError('Amount must be > 0'); return }
    if (!form.payment_date) { setFormError('Date is required'); return }
    setSaving(true); setFormError('')
    try {
      const body: Record<string, unknown> = {
        customer_id: form.customer_id ? Number(form.customer_id) : null,
        payment_date: form.payment_date,
        amount: paymentAmount,
        method: form.method,
        reference: form.reference || null,
        cash_account_id: form.cash_account_id ? parseInt(form.cash_account_id) : null,
      }
      // Build allocations array from checked rows
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

  // Auto-fill amount when checking a single invoice
  const handleCheck = (inv: OpenInvoice, checked: boolean) => {
    setAlloc(inv.id, 'checked', checked)
    if (checked) {
      const remaining = paymentAmount - totalApplied
      const suggested = Math.min(inv.outstanding, remaining > 0 ? remaining : inv.outstanding)
      setAlloc(inv.id, 'amount', String(suggested.toFixed(dp)))
    } else {
      setAlloc(inv.id, 'amount', '')
    }
  }

  const cashAccounts = accounts.filter(a => a.type === 'Asset')

  return (
    <div className="bg-white rounded-2xl border border-[#ede9e2] p-8 max-w-3xl mx-auto">
      <div className="space-y-4">
        {/* Header fields */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Customer *</label>
            <select
              required
              value={form.customer_id}
              onChange={e => setForm(p => ({ ...p, customer_id: e.target.value }))}
              className="ui-field w-full bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
            >
              <option value="">— Select customer —</option>
              {customers.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Payment Date</label>
            <input type="date" value={form.payment_date} onChange={e => setForm(p => ({ ...p, payment_date: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Amount Received</label>
            <input type="number" step="0.01" value={form.amount}
              onChange={e => setForm(p => ({ ...p, amount: e.target.value }))}
              placeholder="0.00" className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Method</label>
            <select value={form.method} onChange={e => setForm(p => ({ ...p, method: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
              {['cash', 'bank_transfer', 'check', 'credit_card'].map(m => <option key={m} value={m}>{m.replace('_', ' ')}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Reference #</label>
            <input value={form.reference} onChange={e => setForm(p => ({ ...p, reference: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
          </div>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Cash/Bank Account</label>
          <select value={form.cash_account_id} onChange={e => setForm(p => ({ ...p, cash_account_id: e.target.value }))}
            className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
            <option value="">Auto (1000 Cash in Hand)</option>
            {cashAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
          </select>
        </div>

        {/* Invoice allocation checklist */}
        {openInvoices.length > 0 && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-2">
              Apply to Open Invoices (optional)
            </label>
            <div className="border border-[#ede9e2] rounded-xl overflow-hidden text-sm">
              <table className="w-full">
                <thead className="bg-[#f6f3ee]">
                  <tr>
                    <th className="w-8 px-3 py-2" />
                    <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/60">Invoice</th>
                    <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/60">Customer</th>
                    <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-black/60">Outstanding</th>
                    <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-black/60">Apply</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ede9e2]">
                  {openInvoices.map(inv => {
                    const row = allocations.find(a => a.invoice_id === inv.id)
                    if (!row) return null
                    return (
                      <tr key={inv.id} className={row.checked ? 'bg-amber-50/40' : 'hover:bg-[#f6f3ee]/40'}>
                        <td className="px-3 py-2 text-center">
                          <input
                            type="checkbox"
                            checked={row.checked}
                            onChange={e => handleCheck(inv, e.target.checked)}
                            className="accent-[#b8943f]"
                          />
                        </td>
                        <td className="px-3 py-2 font-mono text-[#b8943f] font-bold text-xs">{inv.number}</td>
                        <td className="px-3 py-2 text-black/70 truncate max-w-[120px]">{inv.customer_name ?? '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{fmt(inv.outstanding)}</td>
                        <td className="px-3 py-2 text-right">
                          {row.checked ? (
                            <input
                              type="number" step="0.01" min="0.01"
                              value={row.amount}
                              onChange={e => setAlloc(inv.id, 'amount', e.target.value)}
                              className="w-24 text-right px-2 py-1 border border-[#ede9e2] rounded text-xs outline-none focus:ring-1 focus:ring-[#b8943f]"
                            />
                          ) : (
                            <span className="text-black/25 text-xs">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Allocation summary */}
            {hasAllocations && (
              <div className={`mt-2 flex items-center justify-between text-xs px-3 py-2 rounded-lg ${diff > 0.01 ? 'bg-amber-50 border border-amber-200' : 'bg-green-50 border border-green-200'}`}>
                <span className="text-black/60">
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
        )}

        {formError && <p className="text-red-600 text-sm">{formError}</p>}
        <p className="text-xs text-black/50">GL posting: Dr Cash/Bank / Cr Accounts Receivable</p>
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onCancel} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
          <button onClick={handleSave} disabled={!form.customer_id || saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
            {saving ? 'Saving...' : 'Record Payment'}
          </button>
        </div>
      </div>
    </div>
  )
}
