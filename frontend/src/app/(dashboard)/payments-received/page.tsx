'use client'

import { useEffect, useState } from 'react'
import { Plus, Search } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { fmtPKR } from '@/lib/utils'
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

interface Invoice { id: number; number: string; customer_name: string | null; total: number }
interface Account { id: number; code: string; name: string; type: string }

interface PayForm {
  invoice_id: string
  customer_name: string
  payment_date: string
  amount: string
  method: string
  reference: string
  cash_account_id: string
}

const emptyForm: PayForm = {
  invoice_id: '', customer_name: '', payment_date: new Date().toISOString().split('T')[0],
  amount: '', method: 'cash', reference: '', cash_account_id: '',
}

const PAGE_SIZE = 50

export default function PaymentsReceived() {
  const [payments, setPayments] = useState<Payment[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<PayForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [invoices, setInvoices] = useState<Invoice[]>([])
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

  const openModal = () => {
    Promise.all([
      apiFetch<{ total: number; items: Invoice[] }>('/api/invoices?limit=200&status=sent'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
    ]).then(([inv, acc]) => { setInvoices(inv.items); setAccounts(acc.items) }).catch(() => {})
    setForm(emptyForm); setFormError(''); setModalOpen(true)
  }

  const handleSave = async () => {
    if (!form.amount || parseFloat(form.amount) <= 0) { setFormError('Amount must be > 0'); return }
    if (!form.payment_date) { setFormError('Date is required'); return }
    setSaving(true); setFormError('')
    try {
      await apiFetch('/api/payments-received', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          invoice_id: form.invoice_id ? parseInt(form.invoice_id) : null,
          customer_name: form.customer_name || null,
          payment_date: form.payment_date,
          amount: parseFloat(form.amount),
          method: form.method,
          reference: form.reference || null,
          cash_account_id: form.cash_account_id ? parseInt(form.cash_account_id) : null,
        }),
      })
      setModalOpen(false); load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const filtered = payments.filter(p =>
    !search ||
    (p.customer_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
    (p.reference ?? '').toLowerCase().includes(search.toLowerCase())
  )

  const cashAccounts = accounts.filter(a => a.type === 'Asset')

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-medium">Payments Received</h1>
          <p className="text-sm text-black/75 mt-1">Record customer payments and track cash receipts</p>
        </div>
        <button onClick={openModal} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
          <Plus className="w-4 h-4" />
          Record Payment
        </button>
      </div>

      <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
        <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Received (this page)</p>
        <p className="text-3xl font-bold text-green-600 mt-2">{fmtPKR(filtered.reduce((s, p) => s + p.amount, 0))}</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input type="text" placeholder="Search by customer or reference..." value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]" />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Date</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Customer</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Reference</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Method</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/75">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {loading ? (
              <tr><td colSpan={5} className="px-6 py-8 text-center text-black/40">Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-8 text-center text-black/40">No payments recorded.</td></tr>
            ) : filtered.map(p => (
              <tr key={p.id} className="hover:bg-[#f6f3ee]/50">
                <td className="px-6 py-4 text-black/70">{p.payment_date}</td>
                <td className="px-6 py-4 font-medium">{p.customer_name ?? '—'}</td>
                <td className="px-6 py-4 font-mono text-sm text-black/60">{p.reference ?? '—'}</td>
                <td className="px-6 py-4 capitalize text-black/70">{p.method.replace('_', ' ')}</td>
                <td className="px-6 py-4 text-right font-mono font-bold text-green-700">{fmtPKR(p.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-[#ede9e2] px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-8">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">Record Payment</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Invoice (optional)</label>
                <select value={form.invoice_id}
                  onChange={e => { const inv = invoices.find(i => i.id === parseInt(e.target.value)); setForm(p => ({ ...p, invoice_id: e.target.value, customer_name: inv?.customer_name ?? p.customer_name, amount: inv ? String(inv.total) : p.amount })) }}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                  <option value="">— No specific invoice —</option>
                  {invoices.map(i => <option key={i.id} value={i.id}>{i.number} — {i.customer_name} ({fmtPKR(i.total)})</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Customer Name</label>
                <input value={form.customer_name} onChange={e => setForm(p => ({ ...p, customer_name: e.target.value }))}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Payment Date</label>
                  <input type="date" value={form.payment_date} onChange={e => setForm(p => ({ ...p, payment_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Amount</label>
                  <input type="number" step="0.01" value={form.amount} onChange={e => setForm(p => ({ ...p, amount: e.target.value }))}
                    placeholder="0.00" className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
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
