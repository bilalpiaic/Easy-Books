'use client'

import { useEffect, useState } from 'react'
import { Plus, Search, Download } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { fmtPKR, downloadCSV } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'

interface Bill {
  id: number
  number: string
  vendor_name: string | null
  bill_date: string
  due_date: string
  subtotal: number
  gst_amount: number
  total: number
  status: string
}

interface Vendor { id: number; name: string }
interface Account { id: number; code: string; name: string; type: string }
interface AgingBuckets {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
}

interface BillForm {
  vendor_id: string
  vendor_name: string
  bill_date: string
  due_date: string
  description: string
  subtotal: string
  gst_rate: string
  ap_account_id: string
  expense_account_id: string
}

const emptyForm: BillForm = {
  vendor_id: '', vendor_name: '', bill_date: new Date().toISOString().split('T')[0],
  due_date: '', description: '', subtotal: '', gst_rate: '17',
  ap_account_id: '', expense_account_id: '',
}

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  received: 'bg-blue-100 text-blue-700',
  paid: 'bg-green-100 text-green-700',
  overdue: 'bg-red-100 text-red-700',
}

const PAGE_SIZE = 50

export default function Bills() {
  const [bills, setBills] = useState<Bill[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<BillForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [aging, setAging] = useState<AgingBuckets | null>(null)

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (search) params.set('search', search)
    apiFetch<{ total: number; items: Bill[] }>(`/api/bills?${params}`)
      .then(d => { setBills(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { setPage(1) }, [search])
  useEffect(load, [page, search])
  useEffect(() => {
    apiFetch<AgingBuckets>('/api/bills/aging').then(setAging).catch(() => {})
  }, [])

  const openModal = () => {
    Promise.all([
      apiFetch<{ total: number; items: Vendor[] }>('/api/vendors?limit=200'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
    ]).then(([v, a]) => { setVendors(v.items); setAccounts(a.items) }).catch(() => {})
    setForm(emptyForm); setFormError(''); setModalOpen(true)
  }

  const gstAmount = Math.round((parseFloat(form.subtotal) || 0) * (parseFloat(form.gst_rate) || 0) / 100)
  const totalAmount = (parseFloat(form.subtotal) || 0) + gstAmount

  const handleSave = async () => {
    if (!form.subtotal || parseFloat(form.subtotal) <= 0) { setFormError('Subtotal must be > 0'); return }
    if (!form.bill_date || !form.due_date) { setFormError('Both dates are required'); return }
    setSaving(true); setFormError('')
    try {
      await apiFetch('/api/bills', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vendor_id: form.vendor_id ? parseInt(form.vendor_id) : null,
          vendor_name: form.vendor_name || null,
          bill_date: form.bill_date,
          due_date: form.due_date,
          description: form.description || null,
          subtotal: parseFloat(form.subtotal),
          gst_rate: parseFloat(form.gst_rate) || 0,
          ap_account_id: form.ap_account_id ? parseInt(form.ap_account_id) : null,
          expense_account_id: form.expense_account_id ? parseInt(form.expense_account_id) : null,
        }),
      })
      setModalOpen(false); load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleStatusChange = async (b: Bill, status: string) => {
    try {
      await apiFetch(`/api/bills/${b.id}/status?status=${status}`, { method: 'PATCH' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const payable = bills.filter(b => b.status !== 'paid').reduce((s, b) => s + b.total, 0)
  const paid = bills.filter(b => b.status === 'paid').reduce((s, b) => s + b.total, 0)

  const apAccounts = accounts.filter(a => a.type === 'Liability')
  const expenseAccounts = accounts.filter(a => a.type === 'Expense')

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-medium">Bills</h1>
          <p className="text-sm text-black/75 mt-1">Vendor bills and purchase liabilities</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => downloadCSV('bills.csv', bills.map(b => ({ Number: b.number, Vendor: b.vendor_name, Date: b.bill_date, Due: b.due_date, Subtotal: b.subtotal, GST: b.gst_amount, Total: b.total, Status: b.status })))}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button onClick={openModal} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" />
            New Bill
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Payable</p>
          <p className="text-2xl font-bold text-orange-600 mt-2">{fmtPKR(payable)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Paid</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmtPKR(paid)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Bills</p>
          <p className="text-2xl font-bold text-[#1a1814] mt-2">{total}</p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input type="text" placeholder="Search bills..." value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]" />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Bill #</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Vendor</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Bill Date</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Due Date</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/75">Total</th>
              <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-black/75">Status</th>
              <th className="px-6 py-4"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {loading ? (
              <SkeletonRow cols={7} />
            ) : bills.length === 0 ? (
              <tr><td colSpan={7} className="px-6 py-8 text-center text-black/40">No bills found.</td></tr>
            ) : bills.map(b => (
              <tr key={b.id} className="hover:bg-[#f6f3ee]/50">
                <td className="px-6 py-4 font-mono font-bold text-[#b8943f]">{b.number}</td>
                <td className="px-6 py-4">{b.vendor_name ?? '—'}</td>
                <td className="px-6 py-4 text-black/70">{b.bill_date}</td>
                <td className="px-6 py-4 text-black/70">{b.due_date}</td>
                <td className="px-6 py-4 text-right font-mono">{fmtPKR(b.total)}</td>
                <td className="px-6 py-4 text-center">
                  <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${statusColors[b.status] ?? 'bg-gray-100 text-gray-700'}`}>
                    {b.status}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <select value={b.status} onChange={e => handleStatusChange(b, e.target.value)}
                    className="text-xs border border-[#ede9e2] rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#b8943f]">
                    {['draft', 'received', 'paid', 'overdue'].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-[#ede9e2] px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>

      {aging && (
        <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
          <div className="px-6 py-4 border-b border-[#ede9e2]">
            <h3 className="text-xs font-bold uppercase tracking-widest text-black/75">AP Aging Analysis</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-[#ede9e2]">
            {[['Current', aging.current], ['1–30 days', aging['1_30']], ['31–60 days', aging['31_60']], ['61–90 days', aging['61_90']], ['90+ days', aging.over_90]].map(([label, val]) => (
              <div key={String(label)} className="p-4 text-center">
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">{label}</p>
                <p className={`text-lg font-bold font-mono ${Number(val) > 0 ? 'text-orange-600' : 'text-black/40'}`}>{fmtPKR(Number(val))}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-8 overflow-y-auto max-h-[90vh]">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">New Bill</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Vendor</label>
                  <select value={form.vendor_id}
                    onChange={e => { const v = vendors.find(v => v.id === parseInt(e.target.value)); setForm(p => ({ ...p, vendor_id: e.target.value, vendor_name: v?.name ?? '' })) }}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                    <option value="">— Select or type name —</option>
                    {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Vendor Name</label>
                  <input value={form.vendor_name} onChange={e => setForm(p => ({ ...p, vendor_name: e.target.value }))}
                    placeholder="or type manually"
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Bill Date</label>
                  <input type="date" value={form.bill_date} onChange={e => setForm(p => ({ ...p, bill_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
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
                  placeholder="e.g. Office supplies — May 2026"
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Subtotal (pre-tax)</label>
                  <input type="number" step="0.01" value={form.subtotal} onChange={e => setForm(p => ({ ...p, subtotal: e.target.value }))}
                    placeholder="0.00"
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">GST Rate (%)</label>
                  <input type="number" step="0.01" value={form.gst_rate} onChange={e => setForm(p => ({ ...p, gst_rate: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
              </div>
              <div className="bg-[#f6f3ee] rounded-xl p-4 text-sm font-mono flex justify-between">
                <span>GST: {fmtPKR(gstAmount)}</span>
                <span className="font-bold">Total: {fmtPKR(totalAmount)}</span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">AP Account</label>
                  <select value={form.ap_account_id} onChange={e => setForm(p => ({ ...p, ap_account_id: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                    <option value="">Auto (2000)</option>
                    {apAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Expense Account</label>
                  <select value={form.expense_account_id} onChange={e => setForm(p => ({ ...p, expense_account_id: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                    <option value="">Auto (5000)</option>
                    {expenseAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                  </select>
                </div>
              </div>
              {formError && <p className="text-red-600 text-sm">{formError}</p>}
              <p className="text-xs text-black/50">GL posting: Dr Expense / Dr GST Receivable / Cr Accounts Payable</p>
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setModalOpen(false)} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
                <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                  {saving ? 'Posting...' : 'Post Bill'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
