"use client"

import { useEffect, useState } from "react"
import { Plus, Undo2, Download, Printer } from "lucide-react"
import { downloadCSV } from "@/lib/utils"
import DocLink from "@/components/DocLink"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"

interface DebitNote {
  id: number
  number: string
  vendor_name: string | null
  issue_date: string
  total: number
  status: string
  bill_id: number
}

interface Vendor { id: number; name: string }
interface Bill { id: number; number: string; vendor_id: number | null; total: number }

interface DNForm {
  bill_id: string
  vendor_id: string
  issue_date: string
  description: string
  gst_amount: string
  lines: Array<{ product_id: string; description: string; qty: string; rate: string }>
}

const emptyForm: DNForm = {
  bill_id: '', vendor_id: '',
  issue_date: new Date().toISOString().split('T')[0],
  description: '', gst_amount: '0',
  lines: [{ product_id: '', description: '', qty: '1', rate: '0' }],
}

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600', posted: 'bg-blue-100 text-blue-700', applied: 'bg-green-100 text-green-700',
}

export default function DebitNotesPage() {
  const fmt = useFmt()
  const [items, setItems] = useState<DebitNote[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<DNForm>(emptyForm)
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [bills, setBills] = useState<Bill[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  function load() {
    setIsLoading(true)
    apiFetch<{ total: number; items: DebitNote[] }>('/api/debit-notes?limit=50')
      .then(d => { setItems(d.items); setTotal(d.total); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }
  useEffect(() => { load() }, [])

  async function openModal() {
    setForm(emptyForm)
    setFormError('')
    const [vData, bData] = await Promise.all([
      apiFetch<{ items: Vendor[] }>('/api/vendors?limit=200'),
      apiFetch<{ items: Bill[] }>('/api/bills?limit=200'),
    ])
    setVendors(vData.items ?? [])
    setBills(bData.items ?? [])
    setModalOpen(true)
  }

  const visibleBills = bills.filter(b => !form.vendor_id || String(b.vendor_id) === form.vendor_id)
  function addLine() { setForm(f => ({ ...f, lines: [...f.lines, { product_id: '', description: '', qty: '1', rate: '0' }] })) }
  function removeLine(i: number) { setForm(f => ({ ...f, lines: f.lines.filter((_, idx) => idx !== i) })) }
  function updateLine(i: number, field: string, value: string) {
    setForm(f => ({ ...f, lines: f.lines.map((l, idx) => idx === i ? { ...l, [field]: value } : l) }))
  }
  const subtotal = form.lines.reduce((s, l) => s + (parseFloat(l.qty) || 0) * (parseFloat(l.rate) || 0), 0)

  async function handleSave() {
    setFormError('')
    if (!form.bill_id) { setFormError('Select the original bill'); return }
    if (form.lines.some(l => !l.description.trim())) { setFormError('All lines need a description'); return }
    setSaving(true)
    try {
      await apiFetch('/api/debit-notes', {
        method: 'POST',
        body: JSON.stringify({
          bill_id: parseInt(form.bill_id),
          vendor_id: form.vendor_id ? parseInt(form.vendor_id) : null,
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
      setModalOpen(false); load()
    } catch (err) { setFormError((err as Error).message) } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6">
      <PrintHeader title="Debit Notes" />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Debit Notes / Purchase Returns</h1>
          <p className="text-[#1a1814]/60 text-sm mt-1">{total} total · returns goods to a vendor (IAS 2.11)</p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
          <button
            onClick={() => downloadCSV('debit-notes.csv', items.map(n => ({ Number: n.number, Vendor: n.vendor_name ?? '', Date: n.issue_date, Total: n.total, Status: n.status })))}
            disabled={items.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download size={16} /> CSV
          </button>
          <button onClick={openModal} className="flex items-center gap-2 px-4 py-2 bg-[#1a1814] text-white rounded-xl text-sm font-bold hover:bg-[#b8943f] hover:text-black transition-all">
            <Plus size={16} /> New Debit Note
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee]">
            <tr>{['Number', 'Vendor', 'Date', 'Total', 'Status'].map(h => (
              <th key={h} className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/50">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={5} className="ui-td text-center text-[#1a1814]/40 italic">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={5} className="ui-td text-center">
                <Undo2 className="w-8 h-8 mx-auto text-[#1a1814]/20 mb-3" />
                <p className="text-[#1a1814]/50 text-sm">No debit notes yet</p>
                <button onClick={openModal} className="mt-3 text-[#b8943f] text-sm underline">Record your first purchase return</button>
              </td></tr>
            ) : items.map(dn => (
              <tr key={dn.id} className="border-t border-[#1a1814]/5 hover:bg-[#f6f3ee]/50">
                <td className="ui-td font-mono font-bold"><DocLink type="debit_note" id={dn.id} label={dn.number} className="text-[#b8943f]" /></td>
                <td className="ui-td text-[#1a1814]/70">{dn.vendor_name ?? '—'}</td>
                <td className="ui-td text-[#1a1814]/70">{dn.issue_date}</td>
                <td className="ui-td font-mono">{fmt(dn.total)}</td>
                <td className="ui-td"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[dn.status] ?? 'bg-gray-100 text-gray-600'}`}>{dn.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b border-[#ede9e2] flex justify-between items-center">
              <h2 className="text-xl font-serif text-[#1a1814]">New Debit Note</h2>
              <button onClick={() => setModalOpen(false)} className="text-[#1a1814]/40 hover:text-[#1a1814] text-xl">✕</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Vendor</label>
                  <select value={form.vendor_id} onChange={e => setForm(f => ({ ...f, vendor_id: e.target.value, bill_id: '' }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                    <option value="">Select vendor</option>
                    {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Original Bill</label>
                  <select value={form.bill_id} onChange={e => setForm(f => ({ ...f, bill_id: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                    <option value="">Select bill</option>
                    {visibleBills.map(b => <option key={b.id} value={b.id}>{b.number} — {fmt(b.total)}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Issue Date</label>
                <input type="date" value={form.issue_date} onChange={e => setForm(f => ({ ...f, issue_date: e.target.value }))}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Reason</label>
                <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="e.g. Damaged goods returned"
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-2">Lines (returned qty)</label>
                <div className="space-y-2">
                  {form.lines.map((l, i) => (
                    <div key={i} className="grid grid-cols-12 gap-2 items-center">
                      <input value={l.description} onChange={e => updateLine(i, 'description', e.target.value)} placeholder="Description"
                        className="col-span-6 px-2 py-1.5 bg-[#f6f3ee] rounded-lg text-sm outline-none focus:ring-1 focus:ring-[#b8943f]" />
                      <input type="number" value={l.qty} onChange={e => updateLine(i, 'qty', e.target.value)} placeholder="Qty" min="0"
                        className="col-span-2 px-2 py-1.5 bg-[#f6f3ee] rounded-lg text-sm text-right outline-none focus:ring-1 focus:ring-[#b8943f]" />
                      <input type="number" value={l.rate} onChange={e => updateLine(i, 'rate', e.target.value)} placeholder="Rate" min="0"
                        className="col-span-3 px-2 py-1.5 bg-[#f6f3ee] rounded-lg text-sm text-right outline-none focus:ring-1 focus:ring-[#b8943f]" />
                      <button onClick={() => removeLine(i)} disabled={form.lines.length === 1}
                        className="col-span-1 text-red-400 hover:text-red-600 disabled:opacity-20 text-lg leading-none">×</button>
                    </div>
                  ))}
                </div>
                <button onClick={addLine} className="mt-2 text-xs text-[#b8943f] underline">+ Add line</button>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">GST to reverse</label>
                <input type="number" min="0" value={form.gst_amount} onChange={e => setForm(f => ({ ...f, gst_amount: e.target.value }))}
                  className="w-32 px-2 py-1.5 bg-[#f6f3ee] rounded-lg text-sm text-right outline-none focus:ring-1 focus:ring-[#b8943f]" />
              </div>
              <div className="flex justify-between font-bold text-sm border-t border-[#ede9e2] pt-3">
                <span>Total Return</span><span className="font-mono">{fmt(subtotal + (parseFloat(form.gst_amount) || 0))}</span>
              </div>
              <p className="text-xs text-black/40 italic">GL: Dr Accounts Payable / Cr Inventory (at original cost) + Cr GST Input. Stock is reduced.</p>
              {formError && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{formError}</p>}
              <button onClick={handleSave} disabled={saving}
                className="w-full py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                {saving ? 'Posting…' : 'Post Debit Note'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
