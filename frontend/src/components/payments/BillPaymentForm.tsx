'use client'

import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'

interface OpenBill {
  id: number
  number: string
  vendor_name: string | null
  due_date: string
  total: number
  outstanding: number
}

interface AgingItem {
  id: number; number: string; amount: number; name: string | null; due_date: string
}

interface Account { id: number; code: string; name: string; type: string }

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
}

const emptyForm: PayForm = {
  vendor_id: '', payment_date: new Date().toISOString().split('T')[0],
  amount: '', method: 'bank_transfer', reference: '', cash_account_id: '',
}

interface Props {
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function BillPaymentForm({ onSaved, onCancel }: Props) {
  const fmt = useFmt()
  const [form, setForm]             = useState<PayForm>(emptyForm)
  const [saving, setSaving]         = useState(false)
  const [formError, setFormError]   = useState('')
  const [openBills, setOpenBills]   = useState<OpenBill[]>([])
  const [allocations, setAllocations] = useState<AllocationRow[]>([])
  const [accounts, setAccounts]     = useState<Account[]>([])
  const [vendors, setVendors]       = useState<{ id: number; name: string }[]>([])

  useEffect(() => {
    apiFetch<{ items: { id: number; name: string }[] }>('/api/vendors?limit=500') // limit=500: covers all parties at current scale; raise if tenants exceed this
      .then(d => setVendors(d.items))
      .catch(() => {})
    Promise.all([
      apiFetch<{ total: number; items: { id: number; number: string; vendor_name: string | null; due_date: string; total: number; status?: string }[] }>(
        '/api/bills?limit=500&sort_by=due_date&sort_dir=asc'
      ),
      apiFetch<{ items: AgingItem[] }>('/api/bills/aging'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
    ]).then(([billData, agingData, accData]) => {
      // Build outstanding map from aging items (accounts for partial payments)
      const outstandingMap = new Map<number, number>()
      agingData.items.forEach(item => outstandingMap.set(item.id, item.amount))
      // Filter to unpaid/open bills
      const open = billData.items
        .filter(b => !['paid', 'draft'].includes(b.status ?? ''))
        .map(b => ({
          id: b.id,
          number: b.number,
          vendor_name: b.vendor_name,
          due_date: b.due_date,
          total: b.total,
          outstanding: outstandingMap.get(b.id) ?? b.total,
        }))
      setOpenBills(open)
      setAllocations(open.map(b => ({ bill_id: b.id, checked: false, amount: '' })))
      setAccounts(accData.items)
    }).catch(() => {
      setOpenBills([]); setAllocations([]); setAccounts([])
    })
  }, [])

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
      const suggested = Math.min(bill.outstanding, remaining > 0 ? remaining : bill.outstanding)
      setAlloc(bill.id, 'amount', String(suggested.toFixed(2)))
    } else {
      setAlloc(bill.id, 'amount', '')
    }
  }

  const cashAccounts = accounts.filter(a => a.type === 'Asset')

  return (
    <div className="bg-white rounded-2xl border border-[#ede9e2] p-8 max-w-3xl mx-auto">
      <div className="space-y-4">
        {/* Header fields */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Vendor *</label>
            <select
              required
              value={form.vendor_id}
              onChange={e => setForm(p => ({ ...p, vendor_id: e.target.value }))}
              className="ui-field w-full bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
            >
              <option value="">— Select vendor —</option>
              {vendors.map(v => <option key={v.id} value={String(v.id)}>{v.name}</option>)}
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
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Amount Paid</label>
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

        {/* Bill allocation checklist */}
        {openBills.length > 0 && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-2">
              Apply to Open Bills (optional)
            </label>
            <div className="border border-[#ede9e2] rounded-xl overflow-hidden text-sm">
              <table className="w-full">
                <thead className="bg-[#f6f3ee]">
                  <tr>
                    <th className="w-8 px-3 py-2" />
                    <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/60">Bill</th>
                    <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/60">Vendor</th>
                    <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-black/60">Outstanding</th>
                    <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-black/60">Apply</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ede9e2]">
                  {openBills.map(bill => {
                    const row = allocations.find(a => a.bill_id === bill.id)
                    if (!row) return null
                    return (
                      <tr key={bill.id} className={row.checked ? 'bg-amber-50/40' : 'hover:bg-[#f6f3ee]/40'}>
                        <td className="px-3 py-2 text-center">
                          <input
                            type="checkbox"
                            checked={row.checked}
                            onChange={e => handleCheck(bill, e.target.checked)}
                            className="accent-[#b8943f]"
                          />
                        </td>
                        <td className="px-3 py-2 font-mono text-[#b8943f] font-bold text-xs">{bill.number}</td>
                        <td className="px-3 py-2 text-black/70 truncate max-w-[120px]">{bill.vendor_name ?? '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">{fmt(bill.outstanding)}</td>
                        <td className="px-3 py-2 text-right">
                          {row.checked ? (
                            <input
                              type="number" step="0.01" min="0.01"
                              value={row.amount}
                              onChange={e => setAlloc(bill.id, 'amount', e.target.value)}
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
        <p className="text-xs text-black/50">GL posting: Dr Accounts Payable / Cr Cash/Bank</p>
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onCancel} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
          <button onClick={handleSave} disabled={!form.vendor_id || saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
            {saving ? 'Saving...' : 'Record Payment'}
          </button>
        </div>
      </div>
    </div>
  )
}
