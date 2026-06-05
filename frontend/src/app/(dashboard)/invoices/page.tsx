'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Plus, Download, Printer, FileSignature } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import FilterBar from '@/components/FilterBar'
import SortableHeader from '@/components/SortableHeader'
import BulkActionBar from '@/components/BulkActionBar'
import { apiFetch } from '@/lib/api'
import { useFmt, useSettings } from '@/context/SettingsContext'
import { downloadCSV } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'
import LineItemsTable, { LineItem, TaxCodeOption } from '@/components/LineItemsTable'

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
  description: string | null
  notes: string | null
  internal_memo: string | null
  lines?: LineItem[]
}

interface AgingBuckets {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
  items: { id: number; name: string; number: string; due_date: string; amount: number; days_past: number; bucket: string }[]
}

interface Customer { id: number; name: string }
interface Account { id: number; code: string; name: string; type: string }
interface Product { id: number; name: string; code: string | null; unit: string; default_rate: number; product_type: string; stock_qty?: number }
interface PaymentTerm { id: number; code: string; name: string; days: number }

interface InvoiceForm {
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
}

const emptyForm: InvoiceForm = {
  customer_id: '', customer_name: '', issue_date: new Date().toISOString().split('T')[0],
  due_date: '', payment_term_id: '', description: '', notes: '', internal_memo: '', gst_rate: '17',
  ar_account_id: '', revenue_account_id: '',
  currency: 'PKR', exchange_rate: '1',
}

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  sent: 'bg-blue-100 text-blue-700',
  paid: 'bg-green-100 text-green-700',
  overdue: 'bg-red-100 text-red-700',
  partial: 'bg-amber-100 text-amber-700',
}

const PAGE_SIZE = 50
const INVOICE_STATUSES = ['draft', 'sent', 'partial', 'paid', 'overdue']

function InvoicesInner() {
  const fmt = useFmt()
  const { settings } = useSettings()
  const searchParams = useSearchParams()
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sortBy, setSortBy] = useState('issue_date')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [loading, setLoading] = useState(true)
  const [aging, setAging] = useState<AgingBuckets | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editInvoice, setEditInvoice] = useState<Invoice | null>(null)
  const [form, setForm] = useState<InvoiceForm>(emptyForm)
  const [lines, setLines] = useState<LineItem[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [customers, setCustomers] = useState<Customer[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [paymentTerms, setPaymentTerms] = useState<PaymentTerm[]>([])
  const [taxCodes, setTaxCodes] = useState<TaxCodeOption[]>([])
  const [customerBalance, setCustomerBalance] = useState<number | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({
      skip: String((page - 1) * PAGE_SIZE),
      limit: String(PAGE_SIZE),
      sort_by: sortBy,
      sort_dir: sortDir,
    })
    if (search) params.set('search', search)
    if (status) params.set('status', status)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    apiFetch<{ total: number; items: Invoice[] }>(`/api/invoices?${params}`)
      .then(d => { setInvoices(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  const handleSort = (field: string, dir: 'asc' | 'desc') => {
    setSortBy(field); setSortDir(dir); setPage(1)
  }

  useEffect(() => { setPage(1) }, [search, status, dateFrom, dateTo])
  useEffect(load, [page, search, status, dateFrom, dateTo, sortBy, sortDir])
  useEffect(() => {
    apiFetch<AgingBuckets>('/api/invoices/aging').then(setAging).catch(() => {})
  }, [])

  const openCreate = () => {
    loadModalData()
    setEditInvoice(null)
    setForm(emptyForm)
    setLines([])
    setFormError('')
    setModalOpen(true)
  }

  useEffect(() => {
    const h = () => openCreate()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openEdit = (inv: Invoice) => {
    loadModalData()
    setEditInvoice(inv)
    setForm({
      customer_id: String(inv.customer_id ?? ''),
      customer_name: inv.customer_name ?? '',
      issue_date: inv.issue_date,
      due_date: inv.due_date,
      payment_term_id: '',
      description: '', notes: '', internal_memo: '',
      gst_rate: '17',
      ar_account_id: '',
      revenue_account_id: '',
      currency: 'PKR', exchange_rate: '1',
    })
    // Fetch full invoice with lines
    apiFetch<Invoice & { gst_rate: number; ar_account_id: number | null; revenue_account_id: number | null; payment_term_id: number | null }>(`/api/invoices/${inv.id}`)
      .then(full => {
        setForm({
          customer_id: String(full.customer_id ?? ''),
          customer_name: full.customer_name ?? '',
          issue_date: full.issue_date,
          due_date: full.due_date,
          payment_term_id: full.payment_term_id ? String(full.payment_term_id) : '',
          description: full.description ?? '',
          notes: full.notes ?? '',
          internal_memo: full.internal_memo ?? '',
          gst_rate: String(full.gst_rate ?? 17),
          ar_account_id: full.ar_account_id ? String(full.ar_account_id) : '',
          revenue_account_id: full.revenue_account_id ? String(full.revenue_account_id) : '',
          currency: (full as Invoice & { currency?: string }).currency ?? 'PKR',
          exchange_rate: String((full as Invoice & { exchange_rate?: number }).exchange_rate ?? 1),
        })
        setLines((full.lines ?? []).map((l: LineItem & { tax_code_id?: number | null }) => ({
          product_id: l.product_id ?? undefined,
          description: l.description,
          qty: Number(l.qty),
          unit: l.unit ?? 'pcs',
          rate: Number(l.rate),
          amount: Number(l.amount),
          tax_code_id: l.tax_code_id ?? null,
        })))
      })
      .catch(() => {})
    setFormError('')
    setModalOpen(true)
  }

  const loadModalData = () => {
    Promise.all([
      apiFetch<{ total: number; items: Customer[] }>('/api/customers?limit=200'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
      apiFetch<{ total: number; items: Product[] }>('/api/products?limit=500'),
      apiFetch<PaymentTerm[]>('/api/payment-terms'),
      apiFetch<{ total: number; items: TaxCodeOption[] }>('/api/tax-codes?limit=100'),
    ]).then(([c, a, p, terms, tc]) => {
      setCustomers(c.items)
      setAccounts(a.items)
      setProducts(p.items)
      setPaymentTerms(terms)
      setTaxCodes(tc.items)
    }).catch(() => {})
  }

  // Auto-open edit modal if navigated with ?edit=<id>
  useEffect(() => {
    const editId = searchParams.get('edit')
    if (editId && invoices.length > 0) {
      const inv = invoices.find(i => String(i.id) === editId)
      if (inv && inv.status === 'draft') openEdit(inv)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, invoices])

  const handleBulkAction = async (action: string) => {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    if (action === 'delete' && !window.confirm(`Delete ${ids.length} draft invoice(s)?`)) return
    if (action === 'void' && !window.confirm(`Void ${ids.length} invoice(s)?`)) return
    try {
      const res = await apiFetch<{ affected: number; errors: string[] }>('/api/invoices/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids, action }),
      })
      if (res.errors.length > 0) alert(res.errors.join('\n'))
      setSelectedIds(new Set())
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

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

  const handleSave = async () => {
    if (lines.length === 0) { setFormError('Add at least one line item'); return }
    if (lines.some(l => !l.description.trim())) { setFormError('All lines must have a description'); return }
    if (!form.issue_date || (!form.due_date && !form.payment_term_id)) {
      setFormError('Issue date required; provide either a due date or a payment term'); return
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
        tax_code_id: l.tax_code_id ?? null,
      })),
      gst_rate: parseFloat(form.gst_rate) || 0,
      ar_account_id: form.ar_account_id ? parseInt(form.ar_account_id) : null,
      revenue_account_id: form.revenue_account_id ? parseInt(form.revenue_account_id) : null,
      currency: form.currency || settings.currency,
      exchange_rate: parseFloat(form.exchange_rate) || 1,
    }
    try {
      if (editInvoice) {
        await apiFetch(`/api/invoices/${editInvoice.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      } else {
        await apiFetch('/api/invoices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      }
      setModalOpen(false); load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleStatusChange = async (inv: Invoice, newStatus: string) => {
    try {
      await apiFetch(`/api/invoices/${inv.id}/status?status=${newStatus}`, { method: 'PATCH' })
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
          >
            <Printer className="w-4 h-4" />
            Print
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" />
            New Invoice
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Outstanding</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-2">{fmt(outstanding)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Collected</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmt(paid)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Invoices</p>
          <p className="text-2xl font-bold text-[#1a1814] mt-2">{total}</p>
        </div>
      </div>

      <FilterBar
        search={search} onSearch={setSearch}
        statuses={INVOICE_STATUSES} status={status} onStatus={setStatus}
        dateFrom={dateFrom} dateTo={dateTo}
        onDateFrom={setDateFrom} onDateTo={setDateTo}
        placeholder="Search by invoice # or customer…"
      />

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="sticky top-0 z-10 bg-[#f6f3ee] border-b border-[#ede9e2]">
              <tr>
                <th className="px-4 py-4 w-10">
                  <input type="checkbox"
                    className="rounded border-[#ede9e2] accent-[#b8943f]"
                    checked={invoices.length > 0 && invoices.every(i => selectedIds.has(i.id))}
                    onChange={e => setSelectedIds(e.target.checked ? new Set(invoices.map(i => i.id)) : new Set())}
                  />
                </th>
                <SortableHeader label="Invoice #"  field="number"        sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Customer"   field="customer_name" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Issue Date" field="issue_date"    sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Due Date"   field="due_date"      sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Total"      field="total"         sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-right" />
                <SortableHeader label="Status"     field="status"        sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-center" />
                <th className="ui-th" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {loading ? (
                <SkeletonRow cols={8} />
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-16 text-center">
                    <div className="inline-flex flex-col items-center gap-3">
                      <FileSignature className="w-10 h-10 text-black/20" />
                      <p className="text-sm text-black/40 font-medium">No invoices yet</p>
                      <button onClick={openCreate} className="px-4 py-2 bg-[#b8943f] text-white text-sm font-medium rounded-lg hover:bg-[#a07835] transition-colors">
                        + Create Invoice
                      </button>
                    </div>
                  </td>
                </tr>
              ) : invoices.map(inv => (
                <tr key={inv.id} className={`hover:bg-[#f6f3ee]/50 ${inv.status === 'overdue' ? 'bg-red-50/30' : ''} ${selectedIds.has(inv.id) ? 'bg-[#ffd966]/10' : ''}`}>
                  <td className="px-4 py-4 w-10">
                    <input type="checkbox"
                      className="rounded border-[#ede9e2] accent-[#b8943f]"
                      checked={selectedIds.has(inv.id)}
                      onChange={e => setSelectedIds(prev => {
                        const next = new Set(prev)
                        e.target.checked ? next.add(inv.id) : next.delete(inv.id)
                        return next
                      })}
                    />
                  </td>
                  <td className="ui-td font-mono font-bold text-[#b8943f]">
                    <DocLink type="invoice" id={inv.id} label={inv.number} className="text-[#b8943f] font-bold" />
                  </td>
                  <td className="ui-td">
                    {inv.customer_id && inv.customer_name
                      ? <DocLink type="customer" id={inv.customer_id} label={inv.customer_name} />
                      : (inv.customer_name ?? '—')}
                  </td>
                  <td className="ui-td text-black/70">{inv.issue_date}</td>
                  <td className={`ui-td ${inv.status === 'overdue' ? 'text-red-600 font-medium' : 'text-black/70'}`}>{inv.due_date}</td>
                  <td className="ui-td text-right font-mono">{fmt(inv.total)}</td>
                  <td className="ui-td text-center">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${statusColors[inv.status] ?? 'bg-gray-100 text-gray-700'}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td className="ui-td">
                    <div className="flex items-center justify-end gap-2">
                      {inv.status === 'draft' && (
                        <button
                          onClick={() => openEdit(inv)}
                          className="text-xs px-2 py-1 border border-[#b8943f]/40 text-[#b8943f] rounded hover:bg-[#faf6ec]"
                        >
                          Edit
                        </button>
                      )}
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
                        {INVOICE_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
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
            {([['Current', aging.current], ['1–30 days', aging['1_30']], ['31–60 days', aging['31_60']], ['61–90 days', aging['61_90']], ['90+ days', aging.over_90]] as [string, number][]).map(([label, val]) => (
              <div key={label} className="p-4 text-center">
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">{label}</p>
                <p className={`text-lg font-bold font-mono ${Number(val) > 0 ? 'text-red-600' : 'text-black/40'}`}>{fmt(Number(val))}</p>
              </div>
            ))}
          </div>
          {aging.items && aging.items.filter(i => i.days_past > 0).length > 0 && (
            <div className="border-t border-[#ede9e2] overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-[#f6f3ee]">
                  <tr>
                    <th className="px-4 py-2 text-left font-bold uppercase tracking-widest text-black/50">Invoice</th>
                    <th className="px-4 py-2 text-left font-bold uppercase tracking-widest text-black/50">Customer</th>
                    <th className="px-4 py-2 text-left font-bold uppercase tracking-widest text-black/50">Due</th>
                    <th className="px-4 py-2 text-right font-bold uppercase tracking-widest text-black/50">Amount</th>
                    <th className="px-4 py-2 text-right font-bold uppercase tracking-widest text-red-600">Days Overdue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ede9e2]">
                  {aging.items.filter(i => i.days_past > 0).sort((a, b) => b.days_past - a.days_past).slice(0, 10).map(item => (
                    <tr key={item.id} className="hover:bg-red-50/30">
                      <td className="px-4 py-2 font-mono font-bold text-[#b8943f]">{item.number}</td>
                      <td className="px-4 py-2 text-black/70">{item.name}</td>
                      <td className="px-4 py-2 text-black/60">{item.due_date}</td>
                      <td className="px-4 py-2 text-right font-mono">{fmt(item.amount)}</td>
                      <td className="px-4 py-2 text-right font-bold text-red-600">{item.days_past}d</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <BulkActionBar
        count={selectedIds.size}
        actions={[
          { label: 'Mark Sent', onClick: () => handleBulkAction('mark_sent') },
          { label: 'Void', onClick: () => handleBulkAction('void'), variant: 'danger' },
          { label: 'Delete', onClick: () => handleBulkAction('delete'), variant: 'danger' },
        ]}
        onClear={() => setSelectedIds(new Set())}
      />

      {/* Create / Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl mx-4 p-8 overflow-y-auto max-h-[92vh]">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">
              {editInvoice ? `Edit Invoice ${editInvoice.number}` : 'New Invoice'}
            </h2>
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
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Description</label>
                <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                  placeholder="e.g. Consulting services — May 2026"
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
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
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-2">Line Items</label>
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
              <p className="text-xs text-black/50">GL posting: Dr Accounts Receivable / Cr Revenue / Cr GST Payable</p>
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setModalOpen(false)} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
                <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                  {saving ? 'Saving…' : editInvoice ? 'Save Changes' : 'Post Invoice'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Invoices() {
  return <Suspense><InvoicesInner /></Suspense>
}
