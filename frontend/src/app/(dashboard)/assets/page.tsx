"use client"

import { useEffect, useState } from "react"
import { Plus, Building2, Play, Archive, Download, Printer } from "lucide-react"
import { downloadCSV } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import DocLink from "@/components/DocLink"
import PrintHeader from "@/components/PrintHeader"

interface FixedAsset {
  id: number
  name: string
  code: string | null
  acquisition_date: string
  acquisition_cost: number
  accumulated_depreciation: number
  book_value: number
  method: string
  useful_life_months: number
  is_disposed: boolean
  last_depreciation_date: string | null
}

interface Account { id: number; code: string; name: string }

interface AssetForm {
  name: string
  code: string
  asset_account_id: string
  accum_depr_account_id: string
  depr_expense_account_id: string
  acquisition_date: string
  acquisition_cost: string
  salvage_value: string
  useful_life_months: string
  method: string
  funding_account_id: string | null
}

const emptyForm: AssetForm = {
  name: '', code: '',
  asset_account_id: '', accum_depr_account_id: '', depr_expense_account_id: '',
  acquisition_date: new Date().toISOString().split('T')[0],
  acquisition_cost: '', salvage_value: '0',
  useful_life_months: '60', method: 'straight_line',
  funding_account_id: null,
}

export default function AssetsPage() {
  const fmt = useFmt()
  const [items, setItems] = useState<FixedAsset[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<AssetForm>(emptyForm)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deprDate, setDeprDate] = useState(new Date().toISOString().split('T')[0])
  const [deprTarget, setDeprTarget] = useState<number | null>(null)

  function load() {
    setIsLoading(true)
    apiFetch<{ total: number; items: FixedAsset[] }>('/api/assets?limit=100')
      .then(d => { setItems(d.items); setTotal(d.total); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }

  useEffect(() => { load() }, [])

  async function openModal() {
    setForm(emptyForm)
    setFormError('')
    const coa = await apiFetch<{ items: Account[] }>('/api/accounts?limit=300')
    setAccounts(coa.items ?? [])
    setModalOpen(true)
  }

  async function handleSave() {
    setFormError('')
    if (!form.name.trim()) { setFormError('Name is required'); return }
    if (!form.acquisition_cost || parseFloat(form.acquisition_cost) <= 0) {
      setFormError('Acquisition cost must be > 0'); return
    }
    setSaving(true)
    try {
      await apiFetch('/api/assets', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          asset_account_id: parseInt(form.asset_account_id),
          accum_depr_account_id: parseInt(form.accum_depr_account_id),
          depr_expense_account_id: parseInt(form.depr_expense_account_id),
          acquisition_cost: parseFloat(form.acquisition_cost),
          salvage_value: parseFloat(form.salvage_value) || 0,
          useful_life_months: parseInt(form.useful_life_months),
          funding_account_id: form.funding_account_id ? parseInt(form.funding_account_id) : null,
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

  async function disposeAsset(assetId: number, name: string) {
    if (!confirm(`Mark "${name}" as disposed? This cannot be undone.`)) return
    try {
      await apiFetch(`/api/assets/${assetId}/dispose`, { method: 'PATCH' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  async function runDepreciation(assetId: number) {
    try {
      const result = await apiFetch<{ jv_number?: string; depreciation_amount?: number; message?: string }>(
        `/api/assets/${assetId}/depreciate`,
        { method: 'POST', body: JSON.stringify({ depreciation_date: deprDate }) },
      )
      alert(result.message ?? `Depreciation posted: ${fmt(result.depreciation_amount ?? 0)} (${result.jv_number})`)
      load()
    } catch (err) {
      alert((err as Error).message)
    }
    setDeprTarget(null)
  }

  const accountOptions = accounts.map(a => (
    <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
  ))

  return (
    <div className="space-y-6">
      <PrintHeader title="Fixed Assets" />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Fixed Assets</h1>
          <p className="text-[#1a1814]/60 text-sm mt-1">{total} assets · IAS 16</p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
          <button
            onClick={() => downloadCSV('fixed-assets.csv', items.map(a => ({ Name: a.name, Code: a.code ?? '', "Acquisition Date": a.acquisition_date, "Acquisition Cost": a.acquisition_cost, "Accum. Depr.": a.accumulated_depreciation, "Book Value": a.book_value, Method: a.method, "Useful Life (months)": a.useful_life_months, Status: a.is_disposed ? "Disposed" : "Active" })))}
            disabled={items.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download size={16} /> CSV
          </button>
          <button onClick={openModal}
            className="flex items-center gap-2 px-4 py-2 bg-[#1a1814] text-white rounded-xl text-sm font-bold hover:bg-[#b8943f] hover:text-black transition-all">
            <Plus size={16} /> New Asset
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee]">
            <tr>
              {['Name', 'Date', 'Cost', 'Accum. Depr', 'Book Value', 'Method', 'Actions'].map(h => (
                <th key={h} className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/50">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={7} className="ui-td text-center text-[#1a1814]/40 italic">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="ui-td text-center">
                  <Building2 className="w-8 h-8 mx-auto text-[#1a1814]/20 mb-3" />
                  <p className="text-[#1a1814]/50 text-sm">No fixed assets yet</p>
                  <button onClick={openModal} className="mt-3 text-[#b8943f] text-sm underline">Register your first asset</button>
                </td>
              </tr>
            ) : items.map(a => (
              <tr key={a.id} className={`border-t border-[#1a1814]/5 hover:bg-[#f6f3ee]/50${a.is_disposed ? ' opacity-50' : ''}`}>
                <td className="ui-td font-medium">
                  <DocLink type="fixed_asset" id={a.id} label={a.name} className="font-medium" />
                  {a.code && <span className="ml-2 text-xs text-[#1a1814]/40">{a.code}</span>}
                  {a.is_disposed && <span className="ml-2 text-[10px] bg-[#1a1814]/10 text-[#1a1814]/50 rounded px-1.5 py-0.5 uppercase tracking-wide">Disposed</span>}
                </td>
                <td className="ui-td text-[#1a1814]/60">{a.acquisition_date}</td>
                <td className="ui-td font-mono">{fmt(a.acquisition_cost)}</td>
                <td className="ui-td font-mono text-red-500">({fmt(a.accumulated_depreciation)})</td>
                <td className="ui-td font-mono font-bold">{fmt(a.book_value)}</td>
                <td className="ui-td text-xs text-[#1a1814]/50 capitalize">{a.method.replace('_', ' ')}</td>
                <td className="ui-td">
                  {a.is_disposed ? null : deprTarget === a.id ? (
                    <div className="flex items-center gap-2">
                      <input type="date" value={deprDate} onChange={e => setDeprDate(e.target.value)}
                        className="border rounded px-2 py-1 text-xs" />
                      <button onClick={() => runDepreciation(a.id)}
                        className="px-2 py-1 bg-[#1a1814] text-white rounded text-xs">Post</button>
                      <button onClick={() => setDeprTarget(null)} className="text-xs text-[#1a1814]/40">✕</button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <button onClick={() => setDeprTarget(a.id)}
                        className="flex items-center gap-1 text-xs text-[#b8943f] hover:underline">
                        <Play size={12} /> Depreciate
                      </button>
                      <button onClick={() => disposeAsset(a.id, a.name)}
                        className="flex items-center gap-1 text-xs text-[#1a1814]/40 hover:text-red-600 hover:underline">
                        <Archive size={12} /> Dispose
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b border-[#ede9e2] flex justify-between items-center">
              <h2 className="text-xl font-serif text-[#1a1814]">Register Fixed Asset</h2>
              <button onClick={() => setModalOpen(false)} className="text-[#1a1814]/40 hover:text-[#1a1814] text-xl">✕</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Asset Name</label>
                  <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Office Laptop"
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Asset Code (optional)</label>
                  <input value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))} placeholder="e.g. FA-001"
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Asset GL Account</label>
                <select value={form.asset_account_id} onChange={e => setForm(f => ({ ...f, asset_account_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                  <option value="">Select account…</option>
                  {accountOptions}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Accumulated Depreciation Account (1090)</label>
                <select value={form.accum_depr_account_id} onChange={e => setForm(f => ({ ...f, accum_depr_account_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                  <option value="">Select account…</option>
                  {accountOptions}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Depreciation Expense Account (5050)</label>
                <select value={form.depr_expense_account_id} onChange={e => setForm(f => ({ ...f, depr_expense_account_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                  <option value="">Select account…</option>
                  {accountOptions}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Acquisition Date</label>
                  <input type="date" value={form.acquisition_date} onChange={e => setForm(f => ({ ...f, acquisition_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Acquisition Cost</label>
                  <input type="number" min="0" value={form.acquisition_cost} onChange={e => setForm(f => ({ ...f, acquisition_cost: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Salvage Value</label>
                  <input type="number" min="0" value={form.salvage_value} onChange={e => setForm(f => ({ ...f, salvage_value: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Useful Life (months)</label>
                  <input type="number" min="1" value={form.useful_life_months} onChange={e => setForm(f => ({ ...f, useful_life_months: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Method</label>
                  <select value={form.method} onChange={e => setForm(f => ({ ...f, method: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                    <option value="straight_line">Straight Line</option>
                    <option value="reducing_balance">Reducing Balance</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
                  Funded By <span className="font-normal normal-case">(optional — posts acquisition JV)</span>
                </label>
                <select
                  value={form.funding_account_id ?? ""}
                  onChange={e => setForm(f => ({ ...f, funding_account_id: e.target.value || null }))}
                  className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
                >
                  <option value="">— no GL entry —</option>
                  {accountOptions}
                </select>
              </div>
              {formError && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{formError}</p>}
              <button onClick={handleSave} disabled={saving}
                className="w-full py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                {saving ? 'Registering…' : 'Register Asset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
