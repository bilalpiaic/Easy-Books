"use client"

import { useEffect, useState } from "react"
import { Plus, Wallet } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"

type Tab = "customer" | "vendor"

interface Advance {
  id: number
  number: string
  date: string
  amount: number
  applied_amount: number
  remaining: number
  status: string
  customer_id?: number
  vendor_id?: number
}
interface Party { id: number; name: string }
interface Doc { id: number; number: string; total: number; customer_id?: number | null; vendor_id?: number | null }

export default function AdvancesPage() {
  const fmt = useFmt()
  const [tab, setTab] = useState<Tab>("customer")
  const [rows, setRows] = useState<Advance[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [parties, setParties] = useState<Party[]>([])
  const [docs, setDocs] = useState<Doc[]>([])

  // record modal
  const [recOpen, setRecOpen] = useState(false)
  const [recForm, setRecForm] = useState({ party_id: '', date: new Date().toISOString().split('T')[0], amount: '', notes: '' })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  // apply modal
  const [applyFor, setApplyFor] = useState<Advance | null>(null)
  const [applyForm, setApplyForm] = useState({ target_id: '', amount: '' })

  function load() {
    setIsLoading(true)
    apiFetch<Advance[]>(`/api/advances/${tab}`)
      .then(d => { setRows(d); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }
  useEffect(() => { load() /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [tab])

  async function openRecord() {
    setRecForm({ party_id: '', date: new Date().toISOString().split('T')[0], amount: '', notes: '' })
    setErr('')
    const url = tab === "customer" ? '/api/customers?limit=200' : '/api/vendors?limit=200'
    const d = await apiFetch<{ items: Party[] }>(url)
    setParties(d.items ?? [])
    setRecOpen(true)
  }

  async function saveRecord() {
    setErr('')
    if (!recForm.party_id || !recForm.amount) { setErr('Party and amount are required'); return }
    setSaving(true)
    try {
      await apiFetch(`/api/advances/${tab}`, {
        method: 'POST',
        body: JSON.stringify({
          party_id: parseInt(recForm.party_id),
          date: recForm.date,
          amount: parseFloat(recForm.amount),
          notes: recForm.notes || null,
        }),
      })
      setRecOpen(false); load()
    } catch (e) { setErr((e as Error).message) } finally { setSaving(false) }
  }

  async function openApply(adv: Advance) {
    setApplyFor(adv)
    setApplyForm({ target_id: '', amount: String(adv.remaining) })
    setErr('')
    const url = tab === "customer"
      ? '/api/invoices?limit=200&status=posted,partial,sent'
      : '/api/bills?limit=200'
    const d = await apiFetch<{ items: Doc[] }>(url)
    const partyId = tab === "customer" ? adv.customer_id : adv.vendor_id
    const key: keyof Doc = tab === "customer" ? "customer_id" : "vendor_id"
    setDocs((d.items ?? []).filter(x => !partyId || x[key] === partyId))
  }

  async function saveApply() {
    if (!applyFor) return
    setErr('')
    if (!applyForm.target_id || !applyForm.amount) { setErr('Select a document and amount'); return }
    setSaving(true)
    try {
      await apiFetch(`/api/advances/${tab}/${applyFor.id}/apply`, {
        method: 'POST',
        body: JSON.stringify({ target_id: parseInt(applyForm.target_id), amount: parseFloat(applyForm.amount) }),
      })
      setApplyFor(null); load()
    } catch (e) { setErr((e as Error).message) } finally { setSaving(false) }
  }

  const statusColors: Record<string, string> = {
    open: 'bg-blue-100 text-blue-700', partial: 'bg-amber-100 text-amber-700', applied: 'bg-green-100 text-green-700',
  }
  const docNoun = tab === "customer" ? "invoice" : "bill"

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Advances</h1>
          <p className="text-[#1a1814]/60 text-sm mt-1">Prepayments received from customers / paid to vendors</p>
        </div>
        <button onClick={openRecord} className="flex items-center gap-2 px-4 py-2 bg-[#1a1814] text-white rounded-xl text-sm font-bold hover:bg-[#b8943f] hover:text-black transition-all">
          <Plus size={16} /> Record {tab === "customer" ? "Customer" : "Vendor"} Advance
        </button>
      </div>

      <div className="flex gap-1 border-b border-[#ede9e2]">
        {(["customer", "vendor"] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-all ${tab === t ? 'border-[#b8943f] text-[#b8943f]' : 'border-transparent text-[#1a1814]/55 hover:text-[#1a1814]'}`}>
            {t === "customer" ? "From Customers" : "To Vendors"}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee]">
            <tr>{['Number', 'Date', 'Amount', 'Applied', 'Remaining', 'Status', ''].map((h, i) => (
              <th key={i} className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/50">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={7} className="ui-td py-10 text-center text-[#1a1814]/40 italic">Loading...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={7} className="ui-td py-16 text-center">
                <Wallet className="w-8 h-8 mx-auto text-[#1a1814]/20 mb-3" />
                <p className="text-[#1a1814]/50 text-sm">No {tab} advances yet</p>
                <button onClick={openRecord} className="mt-3 text-[#b8943f] text-sm underline">Record one</button>
              </td></tr>
            ) : rows.map(a => (
              <tr key={a.id} className="border-t border-[#1a1814]/5 hover:bg-[#f6f3ee]/50">
                <td className="ui-td font-mono text-[#b8943f] font-bold">{a.number}</td>
                <td className="ui-td text-[#1a1814]/70">{a.date}</td>
                <td className="ui-td font-mono">{fmt(a.amount)}</td>
                <td className="ui-td font-mono text-[#1a1814]/50">{fmt(a.applied_amount)}</td>
                <td className="ui-td font-mono font-bold">{fmt(a.remaining)}</td>
                <td className="ui-td"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[a.status] ?? 'bg-gray-100'}`}>{a.status}</span></td>
                <td className="ui-td text-right">
                  {a.remaining > 0 && (
                    <button onClick={() => openApply(a)} className="text-xs text-[#b8943f] underline">Apply to {docNoun}</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Record modal */}
      {recOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl">
            <div className="p-6 border-b border-[#ede9e2] flex justify-between items-center">
              <h2 className="text-xl font-serif text-[#1a1814]">Record {tab === "customer" ? "Customer" : "Vendor"} Advance</h2>
              <button onClick={() => setRecOpen(false)} className="text-[#1a1814]/40 hover:text-[#1a1814] text-xl">✕</button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">{tab === "customer" ? "Customer" : "Vendor"}</label>
                <select value={recForm.party_id} onChange={e => setRecForm(f => ({ ...f, party_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                  <option value="">Select…</option>
                  {parties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Date</label>
                  <input type="date" value={recForm.date} onChange={e => setRecForm(f => ({ ...f, date: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Amount</label>
                  <input type="number" min="0" value={recForm.amount} onChange={e => setRecForm(f => ({ ...f, amount: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
              </div>
              <p className="text-xs text-black/40 italic">
                {tab === "customer"
                  ? "GL: Dr Bank / Cr 2310 Customer Advances (liability)."
                  : "GL: Dr 1260 Advances to Vendors (asset) / Cr Bank."}
              </p>
              {err && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{err}</p>}
              <button onClick={saveRecord} disabled={saving}
                className="w-full py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                {saving ? 'Saving…' : 'Record Advance'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Apply modal */}
      {applyFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl">
            <div className="p-6 border-b border-[#ede9e2] flex justify-between items-center">
              <h2 className="text-xl font-serif text-[#1a1814]">Apply {applyFor.number}</h2>
              <button onClick={() => setApplyFor(null)} className="text-[#1a1814]/40 hover:text-[#1a1814] text-xl">✕</button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-sm text-[#1a1814]/60">Remaining: <span className="font-mono font-bold">{fmt(applyFor.remaining)}</span></p>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Apply to {docNoun}</label>
                <select value={applyForm.target_id} onChange={e => setApplyForm(f => ({ ...f, target_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                  <option value="">Select {docNoun}…</option>
                  {docs.map(d => <option key={d.id} value={d.id}>{d.number} — {fmt(d.total)}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Amount</label>
                <input type="number" min="0" value={applyForm.amount} onChange={e => setApplyForm(f => ({ ...f, amount: e.target.value }))}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
              </div>
              <p className="text-xs text-black/40 italic">
                {tab === "customer"
                  ? "GL: Dr 2310 Customer Advances / Cr Accounts Receivable — settles the invoice."
                  : "GL: Dr Accounts Payable / Cr 1260 Advances to Vendors — settles the bill."}
              </p>
              {err && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{err}</p>}
              <button onClick={saveApply} disabled={saving}
                className="w-full py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                {saving ? 'Applying…' : 'Apply Advance'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
