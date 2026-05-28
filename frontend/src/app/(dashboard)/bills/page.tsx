'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Plus, Download, Printer, Receipt } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import DocLink from '@/components/DocLink'
import FilterBar from '@/components/FilterBar'
import SortableHeader from '@/components/SortableHeader'
import BulkActionBar from '@/components/BulkActionBar'
import { apiFetch } from '@/lib/api'
import { downloadCSV } from '@/lib/utils'
import Pagination from '@/components/Pagination'
import SkeletonRow from '@/components/SkeletonRow'
import LineItemsTable, { LineItem, TaxCodeOption } from '@/components/LineItemsTable'

interface Bill {
  id: number
  number: string
  vendor_id: number | null
  vendor_name: string | null
  bill_date: string
  due_date: string
  subtotal: number
  gst_amount: number
  total: number
  status: string
  notes?: string | null
  internal_memo?: string | null
  lines?: LineItem[]
}

interface AgingBuckets {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
  items: { id: number; name: string; number: string; due_date: string; amount: number; days_past: number; bucket: string }[]
}

interface Vendor { id: number; name: string }
interface Account { id: number; code: string; name: string; type: string }
interface Product { id: number; name: string; code: string | null; unit: string; default_rate: number; product_type: string }
interface PaymentTerm { id: number; code: string; name: string; days: number }

interface BillForm {
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
  currency: string
  exchange_rate: string
}

const emptyForm: BillForm = {
  vendor_id: '', vendor_name: '', bill_date: new Date().toISOString().split('T')[0],
  due_date: '', payment_term_id: '', description: '', notes: '', internal_memo: '', gst_rate: '17',
  ap_account_id: '', expense_account_id: '',
  currency: 'PKR', exchange_rate: '1',
}

const statusColors: Record<string, string> = {
  draft:    'bg-gray-100 text-gray-700',
  received: 'bg-blue-100 text-blue-700',
  partial:  'bg-amber-100 text-amber-700',
  paid:     'bg-green-100 text-green-700',
  overdue:  'bg-red-100 text-red-700',
}

const PAGE_SIZE = 50
const BILL_STATUSES = ['draft', 'received', 'partial', 'paid', 'overdue']

function BillsInner() {
  const searchParams = useSearchParams()
  const [bills, setBills]       = useState<Bill[]>([])
  const [total, setTotal]       = useState(0)
  const [page, setPage]         = useState(1)
  const [search, setSearch]     = useState('')
  const [status, setStatus]     = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo]     = useState('')
  const [sortBy, setSortBy]     = useState('bill_date')
  const [sortDir, setSortDir]   = useState<'asc' | 'desc'>('desc')
  const [loading, setLoading]   = useState(true)
  const [aging, setAging]       = useState<AgingBuckets | null>(null)
  const [modalOpen, setModalOpen]   = useState(false)
  const [editBill, setEditBill]     = useState<Bill | null>(null)
  const [form, setForm]             = useState<BillForm>(emptyForm)
  const [lines, setLines]           = useState<LineItem[]>([])
  const [saving, setSaving]         = useState(false)
  const [formError, setFormError]   = useState('')
  const [vendors, setVendors]       = useState<Vendor[]>([])
  const [accounts, setAccounts]     = useState<Account[]>([])
  const [products, setProducts]     = useState<Product[]>([])
  const [paymentTerms, setPaymentTerms] = useState<PaymentTerm[]>([])
  const [taxCodes, setTaxCodes]         = useState<TaxCodeOption[]>([])
  const [selectedIds, setSelectedIds]   = useState<Set<number>>(new Set())

  const handleBulkAction = async (action: string) => {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    if (action === 'delete' && !window.confirm(`Delete ${ids.length} draft bill(s)?`)) return
    if (action === 'void' && !window.confirm(`Void ${ids.length} bill(s)?`)) return
    try {
      const res = await apiFetch<{ affected: number; errors: string[] }>('/api/bills/bulk', {
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

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({
      skip: String((page - 1) * PAGE_SIZE),
      limit: String(PAGE_SIZE),
      sort_by: sortBy,
      sort_dir: sortDir,
    })
    if (search)   params.set('search',    search)
    if (status)   params.set('status',    status)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo)   params.set('date_to',   dateTo)
    apiFetch<{ total: number; items: Bill[] }>(`/api/bills?${params}`)
      .then(d => { setBills(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  const handleSort = (field: string, dir: 'asc' | 'desc') => {
    setSortBy(field); setSortDir(dir); setPage(1)
  }

  useEffect(() => { setPage(1) }, [search, status, dateFrom, dateTo])
  useEffect(load, [page, search, status, dateFrom, dateTo, sortBy, sortDir])
  useEffect(() => {
    apiFetch<AgingBuckets>('/api/bills/aging').then(setAging).catch(() => {})
  }, [])

  const openCreate = () => {
    loadModalData()
    setEditBill(null)
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

  const openEdit = (bill: Bill) => {
    loadModalData()
    setEditBill(bill)
    setForm({
      vendor_id: String(bill.vendor_id ?? ''),
      vendor_name: bill.vendor_name ?? '',
      bill_date: bill.bill_date,
      due_date: bill.due_date,
      payment_term_id: '',
      description: '', notes: '', internal_memo: '',
      gst_rate: '17',
      ap_account_id: '',
      expense_account_id: '',
    })
    // Fetch full bill with lines
    apiFetch<Bill & { gst_rate: number; description: string; ap_account_id: number | null; expense_account_id: number | null; payment_term_id: number | null }>(`/api/bills/${bill.id}`)
      .then(full => {
        setForm({
          vendor_id: String(full.vendor_id ?? ''),
          vendor_name: full.vendor_name ?? '',
          bill_date: full.bill_date,
          due_date: full.due_date,
          payment_term_id: full.payment_term_id ? String(full.payment_term_id) : '',
          description: full.description ?? '',
          notes: full.notes ?? '',
          internal_memo: full.internal_memo ?? '',
          gst_rate: String(full.gst_rate ?? 17),
          ap_account_id: full.ap_account_id ? String(full.ap_account_id) : '',
          expense_account_id: full.expense_account_id ? String(full.expense_account_id) : '',
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
      apiFetch<{ total: number; items: Vendor[] }>('/api/vendors?limit=200'),
      apiFetch<{ total: number; items: Account[] }>('/api/accounts?limit=500'),
      apiFetch<{ total: number; items: Product[] }>('/api/products?limit=500'),
      apiFetch<PaymentTerm[]>('/api/payment-terms'),
      apiFetch<{ total: number; items: TaxCodeOption[] }>('/api/tax-codes?limit=100'),
    ]).then(([v, a, p, terms, tc]) => {
      setVendors(v.items)
      setAccounts(a.items)
      setProducts(p.items)
      setPaymentTerms(terms)
      setTaxCodes(tc.items)
    }).catch(() => {})
  }

  // Auto-open edit modal if navigated with ?edit=<id>
  useEffect(() => {
    const editId = searchParams.get('edit')
    if (editId && bills.length > 0) {
      const bill = bills.find(b => String(b.id) === editId)
      if (bill && bill.status === 'draft') openEdit(bill)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, bills])

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
    if (lines.length === 0)                       { setFormError('Add at least one line item'); return }
    if (lines.some(l => !l.description.trim()))   { setFormError('All lines must have a description'); return }
    if (!form.bill_date || (!form.due_date && !form.payment_term_id)) {
      setFormError('Bill date required; provide either a due date or a payment term'); return
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
      currency: form.currency || settings.currency,
      exchange_rate: parseFloat(form.exchange_rate) || 1,
      expense_account_id: form.expense_account_id ? parseInt(form.expense_account_id) : null,
    }
    try {
      if (editBill) {
        await apiFetch(`/api/bills/${editBill.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      } else {
        await apiFetch('/api/bills', {
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

  const handleStatusChange = async (b: Bill, newStatus: string) => {
    try {
      await apiFetch(`/api/bills/${b.id}/status?status=${newStatus}`, { method: 'PATCH' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const payable = bills.filter(b => b.status !== 'paid').reduce((s, b) => s + b.total, 0)
  const paid    = bills.filter(b => b.status === 'paid').reduce((s, b) => s + b.total, 0)

  const apAccounts      = accounts.filter(a => a.type === 'Liability')
  const expenseAccounts = accounts.filter(a => a.type === 'Expense')

  return (
    <div className="space-y-6">
      <PrintHeader title="Bills" orientation="landscape" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif font-medium">Bills</h1>
          <p className="text-sm text-black/75 mt-1">Vendor bills and purchase liabilities</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => downloadCSV('bills.csv', bills.map(b => ({ Number: b.number, Vendor: b.vendor_name, Date: b.bill_date, Due: b.due_date, Subtotal: b.subtotal, GST: b.gst_amount, Total: b.total, Status: b.status })))}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Download className="w-4 h-4" /> Export
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" /> New Bill
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Payable</p>
          <p className="text-2xl font-bold text-orange-600 mt-2">{fmt(payable)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Paid</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmt(paid)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Bills</p>
          <p className="text-2xl font-bold text-[#1a1814] mt-2">{total}</p>
        </div>
      </div>

      <FilterBar
        search={search} onSearch={setSearch}
        statuses={BILL_STATUSES} status={status} onStatus={setStatus}
        dateFrom={dateFrom} dateTo={dateTo}
        onDateFrom={setDateFrom} onDateTo={setDateTo}
        placeholder="Search by bill # or vendor…"
      />

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="sticky top-0 z-10 bg-[#f6f3ee] border-b border-[#ede9e2]">
              <tr>
                <th className="px-4 py-4 w-10">
                  <input type="checkbox"
                    className="rounded border-[#ede9e2] accent-[#b8943f]"
                    checked={bills.length > 0 && bills.every(b => selectedIds.has(b.id))}
                    onChange={e => setSelectedIds(e.target.checked ? new Set(bills.map(b => b.id)) : new Set())}
                  />
                </th>
                <SortableHeader label="Bill #"     field="number"      sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Vendor"     field="vendor_name" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Bill Date"  field="bill_date"   sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Due Date"   field="due_date"    sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-left" />
                <SortableHeader label="Total"      field="total"       sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-right" />
                <SortableHeader label="Status"     field="status"      sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="text-center" />
                <th className="px-6 py-4" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {loading ? (
                <SkeletonRow cols={8} />
              ) : bills.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-16 text-center">
                    <div className="inline-flex flex-col items-center gap-3">
                      <Receipt className="w-10 h-10 text-black/20" />
                      <p className="text-sm text-black/40 font-medium">No bills yet</p>
                      <button onClick={openCreate} className="px-4 py-2 bg-[#b8943f] text-white text-sm font-medium rounded-lg hover:bg-[#a07835] transition-colors">
                        + Record Bill
                      </button>
                    </div>
                  </td>
                </tr>
              ) : bills.map(b => (
                <tr key={b.id} className={`hover:bg-[#f6f3ee]/50 ${b.status === 'overdue' ? 'bg-red-50/30' : ''} ${selectedIds.has(b.id) ? 'bg-[#ffd966]/10' : ''}`}>
                  <td className="px-4 py-4 w-10">
                    <input type="checkbox"
                      className="rounded border-[#ede9e2] accent-[#b8943f]"
                      checked={selectedIds.has(b.id)}
                      onChange={e => setSelectedIds(prev => {
                        const next = new Set(prev)
                        e.target.checked ? next.add(b.id) : next.delete(b.id)
                        return next
                      })}
                    />
                  </td>
                  <td className="px-6 py-4 font-mono font-bold text-[#b8943f]">
                    <DocLink type="bill" id={b.id} label={b.number} className="text-[#b8943f] font-bold" />
                  </td>
                  <td className="px-6 py-4">
                    {b.vendor_id && b.vendor_name
                      ? <DocLink type="vendor" id={b.vendor_id} label={b.vendor_name} />
                      : (b.vendor_name ?? '—')}
                  </td>
                  <td className="px-6 py-4 text-black/70">{b.bill_date}</td>
                  <td className={`px-6 py-4 ${b.status === 'overdue' ? 'text-red-600 font-medium' : 'text-black/70'}`}>{b.due_date}</td>
                  <td className="px-6 py-4 text-right font-mono">{fmt(b.total)}</td>
                  <td className="px-6 py-4 text-center">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${statusColors[b.status] ?? 'bg-gray-100 text-gray-700'}`}>
                      {b.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      {b.status === 'draft' && (
                        <button
                          onClick={() => openEdit(b)}
                          className="text-xs px-2 py-1 border border-[#b8943f]/40 text-[#b8943f] rounded hover:bg-[#faf6ec]"
                        >
                          Edit
                        </button>
                      )}
                      <Link
                        href={`/bills/${b.id}/print`}
                        title="Print this bill"
                        className="p-1.5 rounded border border-[#ede9e2] hover:bg-[#faf6ec] text-[#1a1814]/55 hover:text-[#b8943f]"
                      >
                        <Printer className="w-3.5 h-3.5" />
                      </Link>
                      <select
                        value={b.status}
                        onChange={e => handleStatusChange(b, e.target.value)}
                        className="text-xs border border-[#ede9e2] rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#b8943f]"
                      >
                        {BILL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
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
            <h3 className="text-xs font-bold uppercase tracking-widest text-black/75">AP Aging Analysis</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-[#ede9e2]">
            {([['Current', aging.current], ['1–30 days', aging['1_30']], ['31–60 days', aging['31_60']], ['61–90 days', aging['61_90']], ['90+ days', aging.over_90]] as [string, number][]).map(([label, val]) => (
              <div key={label} className="p-4 text-center">
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">{label}</p>
                <p className={`text-lg font-bold font-mono ${Number(val) > 0 ? 'text-orange-600' : 'text-black/40'}`}>{fmt(Number(val))}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <BulkActionBar
        count={selectedIds.size}
        actions={[
          { label: 'Mark Received', onClick: () => handleBulkAction('mark_received') },
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
              {editBill ? `Edit Bill ${editBill.number}` : 'New Bill'}
            </h2>
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
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Bill Date</label>
                  <input type="date" value={form.bill_date} onChange={e => setForm(p => ({ ...p, bill_date: e.target.value }))}
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
                        const due = term && p.bill_date
                          ? new Date(new Date(p.bill_date).getTime() + term.days * 86400000).toISOString().split('T')[0]
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
                  placeholder="e.g. Office supplies — May 2026"
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
                <LineItemsTable lines={lines} onChange={setLines} products={products} taxCodes={taxCodes} showTax />
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
                    placeholder="Printed on the bill for the vendor"
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
                  {saving ? 'Posting...' : (editBill ? 'Save Changes' : 'Post Bill')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Bills() {
  return <Suspense><BillsInner /></Suspense>
}
