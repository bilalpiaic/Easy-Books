'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Plus, Search, Printer, AlertCircle } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import Pagination from '@/components/Pagination'

interface Payment {
  id: number
  invoice_id: number | null
  customer_name: string | null
  payment_date: string
  amount: number
  method: string
  reference: string | null
}

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
  customer_name: string
  payment_date: string
  amount: string
  method: string
  reference: string
  cash_account_id: string
}

const emptyForm: PayForm = {
  customer_name: '', payment_date: new Date().toISOString().split('T')[0],
  amount: '', method: 'cash', reference: '', cash_account_id: '',
}

const PAGE_SIZE = 50

export default function PaymentsReceived() {
  const fmt = useFmt()
  const [payments, setPayments] = useState<Payment[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<PayForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [openInvoices, setOpenInvoices] = useState<OpenInvoice[]>([])
  const [allocations, setAllocations] = useState<AllocationRow[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    apiFetch<{ total: number; items: Payment[] }>(`/api/payments-received?${params}`)
      .then(d => { setPayments(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(load, [page])

  const openModal = async () => {
    try {
      const [invData, agingData, accData] = await Promise.all([
        apiFetch<{ total: number; items: { id: number; number: string; customer_name: string | null; due_date: string; total: number }[] }>(
          '/api/invoices?limit=500&sort_by=due_date&sort_dir=asc'
        ),
        apiFetch<{ items: AgingItem[] }>('/api/invoices/aging'),
        apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
      ])
      // Build outstanding map from aging items
      const outstandingMap = new Map<number, number>()
      agingData.items.forEach(item => outstandingMap.set(item.id, item.amount))

      // Filter to unpaid/open invoices
      const open = invData.items
        .filter(i => !['paid', 'draft'].includes((i as any).status ?? ''))
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
    } catch {
      setOpenInvoices([])
      setAllocations([])
      setAccounts([])
    }
    setForm(emptyForm)
    setFormError('')
    setModalOpen(true)
  }

  const totalApplied = allocations
    .filter(a => a.checked && parseFloat(a.amount) > 0)
    .reduce((s, a) => s + parseFloat(a.amount), 0)

  const paymentAmount = parseFloat(form.amount) || 0
  const diff = Math.abs(paymentAmount - totalApplied)
  const hasAllocations = allocations.some(a => a.checked)

  const handleSave = async () => {
    if (!form.amount || paymentAmount <= 0) { setFormError('Amount must be > 0'); return }
    if (!form.payment_date) { setFormError('Date is required'); return }
    setSaving(true); setFormError('')
    try {
      const body: Record<string, unknown> = {
        customer_name: form.customer_name || null,
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
      await apiFetch('/api/payments-received', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      setModalOpen(false); load()
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
      setAlloc(inv.id, 'amount', String(suggested.toFixed(2)))
    } else {
      setAlloc(inv.id, 'amount', '')
    }
  }

  const filtered = payments.filter(p =>
    !search ||
    (p.customer_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
    (p.reference ?? '').toLowerCase().includes(search.toLowerCase())
  )

  const cashAccounts = accounts.filter(a => a.type === 'Asset')

  return (
    <div className="space-y-6">
      <PrintHeader title="Payments Received" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif font-medium">Payments Received</h1>
          <p className="text-sm text-black/75 mt-1">Record customer payments and track cash receipts</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
          <button onClick={openModal} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" /> Record Payment
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
        <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Received (this page)</p>
        <p className="text-3xl font-bold text-green-600 mt-2">{fmt(filtered.reduce((s, p) => s + p.amount, 0))}</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input type="text" placeholder="Search by customer or reference..." value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]" />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[520px]">
            <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
              <tr>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">Date</th>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">Customer</th>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">Reference</th>
                <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/75">Method</th>
                <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/75">Amount</th>
                <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/75 w-16">Print</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {loading ? (
                <tr><td colSpan={6} className="px-6 py-8 text-center text-black/40">Loading...</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={6} className="px-6 py-8 text-center text-black/40">No payments recorded.</td></tr>
              ) : filtered.map(p => (
                <tr key={p.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="ui-td text-black/70">{p.payment_date}</td>
                  <td className="ui-td font-medium">
                    {p.invoice_id && p.customer_name
                      ? <DocLink type="invoice" id={p.invoice_id} label={p.customer_name} />
                      : (p.customer_name ?? '—')}
                  </td>
                  <td className="ui-td font-mono text-sm text-black/60">
                    {p.invoice_id
                      ? <DocLink type="invoice" id={p.invoice_id} label={p.reference ?? `INV #${p.invoice_id}`} className="text-black/60" />
                      : (p.reference ?? '—')}
                  </td>
                  <td className="ui-td capitalize text-black/70">{p.method.replace('_', ' ')}</td>
                  <td className="ui-td text-right font-mono font-bold text-green-700">{fmt(p.amount)}</td>
                  <td className="ui-td text-right">
                    <Link
                      href={`/payments-received/${p.id}/print`}
                      title="Print receipt"
                      className="inline-flex p-1.5 rounded border border-[#ede9e2] hover:bg-[#faf6ec] text-[#1a1814]/55 hover:text-[#b8943f]"
                    >
                      <Printer className="w-3.5 h-3.5" />
                    </Link>
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

      {/* Record Payment Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 p-8 overflow-y-auto max-h-[92vh]">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">Record Payment</h2>
            <div className="space-y-4">
              {/* Header fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Customer Name</label>
                  <input value={form.customer_name} onChange={e => setForm(p => ({ ...p, customer_name: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
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
                <button onClick={() => setModalOpen(false)} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
                <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                  {saving ? 'Saving...' : 'Record Payment'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
