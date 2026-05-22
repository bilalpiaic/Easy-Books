'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Plus, Search, Download, Printer } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import { apiFetch } from '@/lib/api'
import { fmtPKR, downloadCSV } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'
import LineItemsTable, { LineItem } from '@/components/LineItemsTable'

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
}

interface AgingBuckets {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
  items: { id: number; name: string; number: string; due_date: string; amount: number; days_past: number; bucket: string }[]
}

interface Customer { id: number; name: string }
interface Account { id: number; code: string; name: string; type: string }
interface Product { id: number; name: string; code: string | null; unit: string; default_rate: number; product_type: string }

interface InvoiceForm {
  customer_id: string
  customer_name: string
  issue_date: string
  due_date: string
  description: string
  gst_rate: string
  ar_account_id: string
  revenue_account_id: string
}

const emptyForm: InvoiceForm = {
  customer_id: '', customer_name: '', issue_date: new Date().toISOString().split('T')[0],
  due_date: '', description: '', gst_rate: '17',
  ar_account_id: '', revenue_account_id: '',
}

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  sent: 'bg-blue-100 text-blue-700',
  paid: 'bg-green-100 text-green-700',
  overdue: 'bg-red-100 text-red-700',
}

const PAGE_SIZE = 50

export default function Invoices() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [aging, setAging] = useState<AgingBuckets | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<InvoiceForm>(emptyForm)
  const [lines, setLines] = useState<LineItem[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [customers, setCustomers] = useState<Customer[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [products, setProducts] = useState<Product[]>([])

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (search) params.set('search', search)
    apiFetch<{ total: number; items: Invoice[] }>(`/api/invoices?${params}`)
      .then(d => { setInvoices(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { setPage(1) }, [search])
  useEffect(load, [page, search])
  useEffect(() => {
    apiFetch<AgingBuckets>('/api/invoices/aging').then(setAging).catch(() => {})
  }, [])

  const openModal = () => {
    Promise.all([
      apiFetch<{ total: number; items: Customer[] }>('/api/customers?limit=200'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
      apiFetch<{ total: number; items: Product[] }>('/api/products?limit=500'),
    ]).then(([c, a, p]) => {
      setCustomers(c.items)
      setAccounts(a.items)
      setProducts(p.items)
    }).catch(() => {})
    setForm(emptyForm)
    setLines([])
    setFormError('')
    setModalOpen(true)
  }

  const subtotal = lines.reduce((s, l) => s + l.amount, 0)
  const gstAmount = Math.round(subtotal * (parseFloat(form.gst_rate) || 0) / 100 * 100) / 100
  const totalAmount = Math.round((subtotal + gstAmount) * 100) / 100

  const handleSave = async () => {
    if (lines.length === 0) { setFormError('Add at least one line item'); return }
    if (lines.some(l => !l.description.trim())) { setFormError('All lines must have a description'); return }
    if (!form.issue_date || !form.due_date) { setFormError('Both dates are required'); return }
    setSaving(true); setFormError('')
    try {
      await apiFetch('/api/invoices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: form.customer_id ? parseInt(form.customer_id) : null,
          customer_name: form.customer_name || null,
          issue_date: form.issue_date,
          due_date: form.due_date,
          description: form.description || null,
          lines: lines.map(l => ({
            product_id: l.product_id ?? null,
            description: l.description,
            qty: l.qty,
            unit: l.unit ?? null,
            rate: l.rate,
          })),
          gst_rate: parseFloat(form.gst_rate) || 0,
          ar_account_id: form.ar_account_id ? parseInt(form.ar_account_id) : null,
          revenue_account_id: form.revenue_account_id ? parseInt(form.revenue_account_id) : null,
        }),
      })
      setModalOpen(false); load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleStatusChange = async (inv: Invoice, status: string) => {
    try {
      await apiFetch(`/api/invoices/${inv.id}/status?status=${status}`, { method: 'PATCH' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const outstanding = invoices.filter(i => i.status !== 'paid').reduce((s, i) => s + i.total, 0)
  const paid = invoices.filter(i => i.status === 'paid').reduce((s, i) => s + i.total, 0)

  const arAccounts = accounts.filter(a => a.type === 'Asset')
  const revenueAccounts = accounts.filter(a => a.type === 'Revenue')

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
            title="Print"
          >
            <Printer className="w-4 h-4" />
            Print
          </button>
          <button onClick={openModal} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" />
            New Invoice
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Outstanding</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-2">{fmtPKR(outstanding)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Collected</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmtPKR(paid)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Invoices</p>
          <p className="text-2xl font-bold text-[#1a1814] mt-2">{total}</p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input type="text" placeholder="Search by invoice # or customer..." value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]" />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[700px]">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Invoice #</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Customer</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Issue Date</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/75">Due Date</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/75">Total</th>
              <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-black/75">Status</th>
              <th className="px-6 py-4"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {loading ? (
              <SkeletonRow cols={7} />
            ) : invoices.length === 0 ? (
              <tr><td colSpan={7} className="px-6 py-8 text-center text-black/40">No invoices found.</td></tr>
            ) : invoices.map(inv => (
              <tr key={inv.id} className="hover:bg-[#f6f3ee]/50">
                <td className="px-6 py-4 font-mono font-bold text-[#b8943f]">
                  <DocLink type="invoice" id={inv.id} label={inv.number} className="text-[#b8943f] font-bold" />
                </td>
                <td className="px-6 py-4">
                  {inv.customer_id && inv.customer_name
                    ? <DocLink type="customer" id={inv.customer_id} label={inv.customer_name} />
                    : (inv.customer_name ?? '—')}
                </td>
                <td className="px-6 py-4 text-black/70">{inv.issue_date}</td>
                <td className="px-6 py-4 text-black/70">{inv.due_date}</td>
                <td className="px-6 py-4 text-right font-mono">{fmtPKR(inv.total)}</td>
                <td className="px-6 py-4 text-center">
                  <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${statusColors[inv.status] ?? 'bg-gray-100 text-gray-700'}`}>
                    {inv.status}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end gap-2">
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
                      {['draft', 'sent', 'paid', 'overdue'].map(s => <option key={s} value={s}>{s}</option>)}
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
            {[['Current', aging.current], ['1–30 days', aging['1_30']], ['31–60 days', aging['31_60']], ['61–90 days', aging['61_90']], ['90+ days', aging.over_90]].map(([label, val]) => (
              <div key={String(label)} className="p-4 text-center">
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">{label}</p>
                <p className={`text-lg font-bold font-mono ${Number(val) > 0 ? 'text-red-600' : 'text-black/40'}`}>{fmtPKR(Number(val))}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl mx-4 p-8 overflow-y-auto max-h-[92vh]">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">New Invoice</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Customer</label>
                  <select value={form.customer_id}
                    onChange={e => { const c = customers.find(c => c.id === parseInt(e.target.value)); setForm(p => ({ ...p, customer_id: e.target.value, customer_name: c?.name ?? '' })) }}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                    <option value="">— Select or type name —</option>
                    {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Customer Name</label>
                  <input value={form.customer_name} onChange={e => setForm(p => ({ ...p, customer_name: e.target.value }))}
                    placeholder="or type manually"
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Issue Date</label>
                  <input type="date" value={form.issue_date} onChange={e => setForm(p => ({ ...p, issue_date: e.target.value }))}
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
                  placeholder="e.g. Consulting services — May 2026"
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-2">Line Items</label>
                <LineItemsTable lines={lines} onChange={setLines} products={products} />
              </div>

              <div className="bg-[#f6f3ee] rounded-xl p-4 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-black/60">Subtotal</span>
                  <span className="font-mono">{fmtPKR(subtotal)}</span>
                </div>
                <div className="flex justify-between items-center gap-2">
                  <span className="text-black/60">GST</span>
                  <div className="flex items-center gap-2">
                    <input type="number" min="0" max="100" step="0.5"
                      value={form.gst_rate}
                      onChange={e => setForm(p => ({ ...p, gst_rate: e.target.value }))}
                      className="w-16 text-right bg-white border border-[#ede9e2] rounded px-2 py-0.5 text-xs outline-none focus:ring-1 focus:ring-[#b8943f]"
                    />
                    <span className="text-black/60 text-xs">%</span>
                    <span className="font-mono">{fmtPKR(gstAmount)}</span>
                  </div>
                </div>
                <div className="flex justify-between border-t border-[#ede9e2] pt-2 font-bold">
                  <span>Total</span>
                  <span className="font-mono text-[#1a1814]">{fmtPKR(totalAmount)}</span>
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
              <p className="text-xs text-black/50">GL posting: Dr Accounts Receivable / Cr Revenue / Cr GST Payable</p>
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setModalOpen(false)} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
                <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                  {saving ? 'Posting...' : 'Post Invoice'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
