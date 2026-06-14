"use client"

import { useEffect, useState } from "react"
import { Plus, Receipt, Download } from "lucide-react"
import { downloadCSV } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { useSettings } from "@/context/SettingsContext"
import DocLink from "@/components/DocLink"

interface CreditNote {
  id: number
  number: string
  customer_name: string | null
  issue_date: string
  total: number
  status: string
  invoice_id: number | null
}

interface Customer { id: number; name: string }
interface Invoice { id: number; number: string; total: number }
interface Product { id: number; name: string; product_type: string }

interface CNForm {
  invoice_id: string
  customer_id: string
  customer_name: string
  issue_date: string
  description: string
  gst_amount: string
  lines: Array<{ product_id: string; description: string; qty: string; rate: string }>
}

const emptyForm: CNForm = {
  invoice_id: '',
  customer_id: '',
  customer_name: '',
  issue_date: new Date().toISOString().split('T')[0],
  description: '',
  gst_amount: '0',
  lines: [{ product_id: '', description: '', qty: '1', rate: '0' }],
}

const statusColors: Record<string, string> = {
  draft:   'bg-gray-100 text-gray-600',
  posted:  'bg-blue-100 text-blue-700',
  applied: 'bg-green-100 text-green-700',
}

export default function CreditNotesPage() {
  const fmt = useFmt()
  const { settings } = useSettings()
  const [items, setItems] = useState<CreditNote[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<CNForm>(emptyForm)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  function load() {
    setIsLoading(true)
    apiFetch<{ total: number; items: CreditNote[] }>('/api/credit-notes?limit=50')
      .then(d => { setItems(d.items); setTotal(d.total); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }

  useEffect(() => { load() }, [])

  async function openModal() {
    setForm(emptyForm)
    setFormError('')
    const [custData, invData, prodData] = await Promise.all([
      apiFetch<{ items: Customer[] }>('/api/customers?limit=200'),
      apiFetch<{ items: Invoice[] }>('/api/invoices?limit=200&status=posted,partial,sent'),
      apiFetch<{ items: Product[] }>('/api/products?limit=200'),
    ])
    setCustomers(custData.items ?? [])
    setInvoices(invData.items ?? [])
    setProducts(prodData.items ?? [])
    setModalOpen(true)
  }

  function addLine() {
    setForm(f => ({ ...f, lines: [...f.lines, { product_id: '', description: '', qty: '1', rate: '0' }] }))
  }

  function removeLine(i: number) {
    setForm(f => ({ ...f, lines: f.lines.filter((_, idx) => idx !== i) }))
  }

  function updateLine(i: number, field: string, value: string) {
    setForm(f => ({
      ...f,
      lines: f.lines.map((l, idx) => idx === i ? { ...l, [field]: value } : l),
    }))
  }

  const subtotal = form.lines.reduce((s, l) => s + (parseFloat(l.qty) || 0) * (parseFloat(l.rate) || 0), 0)

  async function handleSave() {
    setFormError('')
    if (form.lines.some(l => !l.description.trim())) {
      setFormError('All lines must have a description')
      return
    }
    if (!form.issue_date) { setFormError('Issue date is required'); return }
    setSaving(true)
    try {
      await apiFetch('/api/credit-notes', {
        method: 'POST',
        body: JSON.stringify({
          invoice_id: form.invoice_id ? parseInt(form.invoice_id) : null,
          customer_id: form.customer_id ? parseInt(form.customer_id) : null,
          customer_name: form.customer_name || null,
          issue_date: form.issue_date,
          description: form.description || null,
          gst_amount: parseFloat(form.gst_amount) || 0,
          lines: form.lines.map(l => ({
            product_id: l.product_id ? parseInt(l.product_id) : null,
            description: l.description,
            qty: parseFloat(l.qty) || 1,
            rate: parseFloat(l.rate) || 0,
          })),
        }),
      })
      setModalOpen(false)
      load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Credit Notes</h1>
          <p className="text-[#1a1814]/60 text-sm mt-1">{total} total</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => downloadCSV('credit-notes.csv', items.map(n => ({ Number: n.number, Customer: n.customer_name ?? '', Date: n.issue_date, Total: n.total, Status: n.status })))}
            disabled={items.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download size={16} /> CSV
          </button>
          <button onClick={openModal}
            className="flex items-center gap-2 px-4 py-2 bg-[#1a1814] text-white rounded-xl text-sm font-bold hover:bg-[#b8943f] hover:text-black transition-all">
            <Plus size={16} /> New Credit Note
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee]">
            <tr>
              {['Number', 'Customer', 'Date', 'Total', 'Status'].map(h => (
                <th key={h} className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/50">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={5} className="ui-td text-center text-[#1a1814]/40 italic">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="ui-td text-center">
                  <Receipt className="w-8 h-8 mx-auto text-[#1a1814]/20 mb-3" />
                  <p className="text-[#1a1814]/50 text-sm">No credit notes yet</p>
                  <button onClick={openModal} className="mt-3 text-[#b8943f] text-sm underline">Issue your first credit note</button>
                </td>
              </tr>
            ) : items.map(cn => (
              <tr key={cn.id} className="border-t border-[#1a1814]/5 hover:bg-[#f6f3ee]/50">
                <td className="ui-td font-mono font-bold"><DocLink type="credit_note" id={cn.id} label={cn.number} className="text-[#b8943f]" /></td>
                <td className="ui-td text-[#1a1814]/70">{cn.customer_name ?? '—'}</td>
                <td className="ui-td text-[#1a1814]/70">{cn.issue_date}</td>
                <td className="ui-td font-mono">{fmt(cn.total)}</td>
                <td className="ui-td">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[cn.status] ?? 'bg-gray-100 text-gray-600'}`}>
                    {cn.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b border-[#ede9e2] flex justify-between items-center">
              <h2 className="text-xl font-serif text-[#1a1814]">New Credit Note</h2>
              <button onClick={() => setModalOpen(false)} className="text-[#1a1814]/40 hover:text-[#1a1814] text-xl">✕</button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Customer</label>
                <select value={form.customer_id}
                  onChange={e => {
                    const id = e.target.value
                    const name = customers.find(c => String(c.id) === id)?.name ?? ''
                    setForm(f => ({ ...f, customer_id: id, customer_name: name }))
                  }}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                  <option value="">Select customer</option>
                  {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Original Invoice (optional)</label>
                  <select value={form.invoice_id} onChange={e => setForm(f => ({ ...f, invoice_id: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                    <option value="">No linked invoice</option>
                    {invoices
                      .filter(inv => !form.customer_id || true) // show all; filter by customer optionally
                      .map(inv => <option key={inv.id} value={inv.id}>{inv.number} — {fmt(inv.total)}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Issue Date</label>
                  <input type="date" value={form.issue_date} onChange={e => setForm(f => ({ ...f, issue_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Reason</label>
                <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="e.g. Return — defective goods"
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-2">Lines</label>
                <p className="text-[10px] text-black/40 mb-2">Pick a stock product to also restock inventory + reverse COGS (sales return).</p>
                <div className="space-y-2">
                  {form.lines.map((l, i) => (
                    <div key={i} className="grid grid-cols-12 gap-2 items-center">
                      <select value={l.product_id}
                        onChange={e => {
                          const pid = e.target.value
                          const p = products.find(x => String(x.id) === pid)
                          updateLine(i, 'product_id', pid)
                          if (p && !form.lines[i].description) updateLine(i, 'description', p.name)
                        }}
                        className="col-span-3 px-2 py-1.5 bg-[#f6f3ee] rounded-lg text-xs outline-none focus:ring-1 focus:ring-[#b8943f]">
                        <option value="">(no product)</option>
                        {products.map(p => <option key={p.id} value={p.id}>{p.name}{p.product_type === 'stock' ? ' ⬡' : ''}</option>)}
                      </select>
                      <input value={l.description} onChange={e => updateLine(i, 'description', e.target.value)}
                        placeholder="Description"
                        className="col-span-4 px-2 py-1.5 bg-[#f6f3ee] rounded-lg text-sm outline-none focus:ring-1 focus:ring-[#b8943f]" />
                      <input type="number" value={l.qty} onChange={e => updateLine(i, 'qty', e.target.value)}
                        placeholder="Qty" min="0"
                        className="col-span-2 px-2 py-1.5 bg-[#f6f3ee] rounded-lg text-sm text-right outline-none focus:ring-1 focus:ring-[#b8943f]" />
                      <input type="number" value={l.rate} onChange={e => updateLine(i, 'rate', e.target.value)}
                        placeholder="Rate" min="0"
                        className="col-span-2 px-2 py-1.5 bg-[#f6f3ee] rounded-lg text-sm text-right outline-none focus:ring-1 focus:ring-[#b8943f]" />
                      <button onClick={() => removeLine(i)} disabled={form.lines.length === 1}
                        className="col-span-1 text-red-400 hover:text-red-600 disabled:opacity-20 text-lg leading-none">×</button>
                    </div>
                  ))}
                </div>
                <button onClick={addLine} className="mt-2 text-xs text-[#b8943f] underline">+ Add line</button>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">GST to reverse</label>
                <input type="number" min="0" value={form.gst_amount}
                  onChange={e => setForm(f => ({ ...f, gst_amount: e.target.value }))}
                  className="w-32 px-2 py-1.5 bg-[#f6f3ee] rounded-lg text-sm text-right outline-none focus:ring-1 focus:ring-[#b8943f]" />
                <span className="text-[10px] text-black/40">optional — reverses output GST on a sales return</span>
              </div>
              <div className="flex justify-between font-bold text-sm border-t border-[#ede9e2] pt-3">
                <span>Total Credit</span>
                <span className="font-mono text-red-600">({fmt(subtotal + (parseFloat(form.gst_amount) || 0))})</span>
              </div>
              <p className="text-xs text-black/40 italic">
                GL: Dr Sales Revenue (+ Dr GST Payable) / Cr Accounts Receivable. Stock lines also Dr Inventory / Cr COGS and restock.
              </p>
              {formError && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{formError}</p>}
              <button onClick={handleSave} disabled={saving}
                className="w-full py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                {saving ? 'Issuing…' : 'Issue Credit Note'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
