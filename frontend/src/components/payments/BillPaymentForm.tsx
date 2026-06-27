'use client'

import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt, useDp } from '@/context/SettingsContext'

interface OpenBill {
  id: number
  number: string
  vendor_name: string | null
  bill_date?: string
  due_date: string
  total: number
  balance_due: number
}

interface Account { id: number; code: string; name: string; type: string }

interface AnalyticAccount { id: number; code: string; name: string; type: string }

interface AllocationRow {
  bill_id: number
  checked: boolean
  amount: string
}

interface PayForm {
  vendor_id: string
  payment_date: string
  amount: string
  method: string
  reference: string
  cash_account_id: string
  analytic_account_id: string
}

const emptyForm: PayForm = {
  vendor_id: '', payment_date: new Date().toISOString().split('T')[0],
  amount: '', method: 'bank_transfer', reference: '', cash_account_id: '', analytic_account_id: '',
}

interface Props {
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function BillPaymentForm({ onSaved, onCancel }: Props) {
  const fmt = useFmt()
  const dp = useDp()
  const [form, setForm]             = useState<PayForm>(emptyForm)
  const [saving, setSaving]         = useState(false)
  const [formError, setFormError]   = useState('')
  const [openBills, setOpenBills]   = useState<OpenBill[]>([])
  const [allocations, setAllocations] = useState<AllocationRow[]>([])
  const [accounts, setAccounts]     = useState<Account[]>([])
  const [vendors, setVendors]       = useState<{ id: number; name: string }[]>([])
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])

  // Static data: vendors, accounts, analytic accounts
  useEffect(() => {
    apiFetch<{ items: { id: number; name: string }[] }>('/api/vendors?limit=500')
      .then(d => setVendors(d.items))
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

  // Reload open bills on mount and whenever vendor selection changes.
  // No vendor selected → all open bills; vendor selected → that vendor's only.
  useEffect(() => {
    const url = form.vendor_id
      ? `/api/bills/open-for-allocation?vendor_id=${form.vendor_id}`
      : `/api/bills/open-for-allocation`
    apiFetch<OpenBill[]>(url)
      .then(bills => {
        setOpenBills(bills)
        setAllocations(bills.map(b => ({ bill_id: b.id, checked: false, amount: '' })))
      })
      .catch(() => { setOpenBills([]); setAllocations([]) })
  }, [form.vendor_id])

  const totalApplied   = allocations.filter(a => a.checked && parseFloat(a.amount) > 0).reduce((s, a) => s + parseFloat(a.amount), 0)
  const paymentAmount  = parseFloat(form.amount) || 0
  const diff           = Math.abs(paymentAmount - totalApplied)
  const hasAllocations = allocations.some(a => a.checked)

  const handleSave = async () => {
    if (!form.vendor_id) { setFormError('Vendor is required'); return }
    if (!form.amount || paymentAmount <= 0) { setFormError('Amount must be > 0'); return }
    if (!form.payment_date) { setFormError('Date is required'); return }
    setSaving(true); setFormError('')
    try {
      const body: Record<string, unknown> = {
        vendor_id: form.vendor_id ? Number(form.vendor_id) : null,
        payment_date: form.payment_date,
        amount: paymentAmount,
        method: form.method,
        reference: form.reference || null,
        cash_account_id: form.cash_account_id ? parseInt(form.cash_account_id) : null,
        analytic_account_id: form.analytic_account_id ? parseInt(form.analytic_account_id) : null,
      }
      const allocationLines = allocations
        .filter(a => a.checked && parseFloat(a.amount) > 0)
        .map(a => ({ bill_id: a.bill_id, amount: parseFloat(a.amount) }))
      if (allocationLines.length > 0) {
        body.allocations = allocationLines
      }
      const created = await apiFetch<{ id: number }>('/api/bill-payments', {
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

  const setAlloc = (billId: number, field: 'checked' | 'amount', value: boolean | string) => {
    setAllocations(prev => prev.map(a => a.bill_id === billId ? { ...a, [field]: value } : a))
  }

  const handleCheck = (bill: OpenBill, checked: boolean) => {
    setAlloc(bill.id, 'checked', checked)
    if (checked) {
      const remaining = paymentAmount - totalApplied
      const suggested = Math.min(bill.balance_due, remaining > 0 ? remaining : bill.balance_due)
      setAlloc(bill.id, 'amount', String(suggested.toFixed(dp)))
    } else {
      setAlloc(bill.id, 'amount', '')
    }
  }

  const cashAccounts = accounts.filter(a => a.type === 'Asset')

  return (
    <div className="bg-white rounded-2xl border border-[var(--border)] p-4 sm:p-8 max-w-3xl mx-auto">
      <div className="space-y-4">
        {/* Header fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Vendor *</label>
            <select
              required
              value={form.vendor_id}
              onChange={e => setForm(p => ({ ...p, vendor_id: e.target.value }))}
              className="ui-field w-full bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]"
            >
              <option value="">— Select vendor —</option>
              {vendors.map(v => <option key={v.id} value={String(v.id)}>{v.name}</option>)}
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
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Amount Paid</label>
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

        {/* Bill allocation checklist */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-2">
            Apply to Open Bills <span className="font-normal normal-case">(optional)</span>
            {form.vendor_id && <span className="ml-1 font-normal normal-case text-[var(--primary)]">— filtered by selected vendor</span>}
          </label>
          {openBills.length === 0 ? (
            <p className="text-xs text-[var(--text-muted)] italic py-2">
              {form.vendor_id ? 'No outstanding bills for this vendor.' : 'No outstanding bills.'}
            </p>
          ) : (
            <div className="border border-[var(--border)] rounded-xl overflow-hidden text-sm">
              <table className="w-full">
                <thead className="bg-[var(--bg-page)]">
                  <tr>
                    <th className="w-8 px-3 py-2" />
                    <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Bill</th>
                    <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Vendor</th>
                    <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Balance Due</th>
                    <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Apply</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {openBills.map(bill => {
                    const row = allocations.find(a => a.bill_id === bill.id)
                    if (!row) return null
                    return (
                      <tr key={bill.id} className={row.checked ? 'bg-amber-50/40' : 'hover:bg-[var(--bg-page)]/40'}>
                        <td className="px-3 py-2 text-center">
                          <input
                            type="checkbox"
                            checked={row.checked}
                            onChange={e => handleCheck(bill, e.target.checked)}
                            className="accent-[var(--primary)]"
                          />
                        </td>
                        <td className="px-3 py-2 font-mono text-[var(--primary)] font-bold text-xs">{bill.number}</td>
                        <td className="px-3 py-2 text-[var(--text-muted)] truncate max-w-[120px] text-xs">{bill.vendor_name ?? '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{fmt(bill.balance_due)}</td>
                        <td className="px-3 py-2 text-right">
                          {row.checked ? (
                            <input
                              type="number" step="0.01" min="0.01"
                              value={row.amount}
                              onChange={e => setAlloc(bill.id, 'amount', e.target.value)}
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
        <p className="text-xs text-[var(--text-muted)]">GL posting: Dr Accounts Payable / Cr Cash/Bank</p>
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onCancel} className="px-6 py-3 border border-[var(--text-primary)]/10 rounded-xl font-bold hover:bg-[var(--bg-page)]">Cancel</button>
          <button onClick={handleSave} disabled={!form.vendor_id || saving} className="px-6 py-3 bg-[var(--text-primary)] text-white rounded-xl font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50">
            {saving ? 'Saving...' : 'Record Payment'}
          </button>
        </div>
      </div>
    </div>
  )
}
