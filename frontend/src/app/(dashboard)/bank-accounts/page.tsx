'use client'

import { useEffect, useState } from 'react'
import { Plus, Eye, EyeOff, Trash2, Printer } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'

interface BankAccount {
  id: number
  name: string
  bank_name: string | null
  account_number: string | null
  coa_account_id: number | null
  is_active: boolean
  balance: number
}

interface CoaAccount { id: number; code: string; name: string; type: string }

interface BankForm {
  name: string
  bank_name: string
  account_number: string
  coa_account_id: string
}

const emptyForm: BankForm = { name: '', bank_name: '', account_number: '', coa_account_id: '' }

export default function BankAccounts() {
  const fmt = useFmt()
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [hideBalance, setHideBalance] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editAccount, setEditAccount] = useState<BankAccount | null>(null)
  const [form, setForm] = useState<BankForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [coaAccounts, setCoaAccounts] = useState<CoaAccount[]>([])

  const load = () => {
    setLoading(true)
    apiFetch<BankAccount[]>('/api/bank-accounts')
      .then(setAccounts)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const openAdd = () => {
    apiFetch<{ total: number; items: CoaAccount[] }>('/api/accounts?limit=500')
      .then(d => setCoaAccounts(d.items.filter(a => a.type === 'Asset')))
      .catch(() => {})
    setEditAccount(null); setForm(emptyForm); setFormError(''); setModalOpen(true)
  }

  useEffect(() => {
    const h = () => openAdd()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openEdit = (ba: BankAccount) => {
    apiFetch<{ total: number; items: CoaAccount[] }>('/api/accounts?limit=500')
      .then(d => setCoaAccounts(d.items.filter(a => a.type === 'Asset')))
      .catch(() => {})
    setEditAccount(ba)
    setForm({ name: ba.name, bank_name: ba.bank_name ?? '', account_number: ba.account_number ?? '', coa_account_id: ba.coa_account_id ? String(ba.coa_account_id) : '' })
    setFormError(''); setModalOpen(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) { setFormError('Name is required'); return }
    setSaving(true); setFormError('')
    try {
      const body = { name: form.name, bank_name: form.bank_name || null, account_number: form.account_number || null, coa_account_id: form.coa_account_id ? parseInt(form.coa_account_id) : null }
      if (editAccount) {
        await apiFetch(`/api/bank-accounts/${editAccount.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      } else {
        await apiFetch('/api/bank-accounts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      }
      setModalOpen(false); load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (ba: BankAccount) => {
    if (!window.confirm(`Delete bank account "${ba.name}"?`)) return
    try {
      await apiFetch(`/api/bank-accounts/${ba.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const totalBalance = accounts.filter(a => a.is_active).reduce((s, a) => s + a.balance, 0)

  return (
    <div className="space-y-6">
      <PrintHeader title="Bank Accounts" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif font-medium">Bank Accounts</h1>
          <p className="text-sm text-black/75 mt-1">Monitor bank balances and track cash positions</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => setHideBalance(!hideBalance)} className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee]">
            {hideBalance ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            {hideBalance ? 'Show' : 'Hide'} Balance
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
            title="Print"
          >
            <Printer className="w-4 h-4" />
            Print
          </button>
          <button onClick={openAdd} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" />
            Add Account
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
        <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Total Cash Position</p>
        <p className={`text-3xl font-bold mt-2 ${totalBalance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {hideBalance ? '••••••' : fmt(totalBalance)}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {loading ? (
          <div className="text-center py-12 text-black/40">Loading...</div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-12 text-black/40">No bank accounts configured. Add one to track balances.</div>
        ) : accounts.map(ba => (
          <div key={ba.id} className="bg-white rounded-lg border border-[#ede9e2] p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="font-semibold text-lg">{ba.name}</h3>
                <p className="text-xs text-black/60 mt-1">{ba.bank_name ?? ''}{ba.bank_name && ba.account_number ? ' • ' : ''}{ba.account_number ?? ''}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${ba.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                  {ba.is_active ? 'active' : 'inactive'}
                </span>
                <button onClick={() => openEdit(ba)} className="text-[#b8943f] text-sm font-bold hover:underline">Edit</button>
                <button onClick={() => handleDelete(ba)} className="text-red-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
            <div>
              <p className="text-xs text-black/60 uppercase tracking-widest font-bold">GL Balance</p>
              <p className={`text-2xl font-bold mt-1 ${ba.balance >= 0 ? 'text-[#b8943f]' : 'text-red-600'}`}>
                {hideBalance ? '••••••' : fmt(ba.balance)}
              </p>
            </div>
          </div>
        ))}
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-8">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">{editAccount ? 'Edit Bank Account' : 'Add Bank Account'}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Account Name</label>
                <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="e.g. Main Operating Account"
                  className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Bank Name</label>
                  <input value={form.bank_name} onChange={e => setForm(p => ({ ...p, bank_name: e.target.value }))}
                    placeholder="e.g. HBL"
                    className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Account Number</label>
                  <input value={form.account_number} onChange={e => setForm(p => ({ ...p, account_number: e.target.value }))}
                    className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Linked GL Account (CoA)</label>
                <select value={form.coa_account_id} onChange={e => setForm(p => ({ ...p, coa_account_id: e.target.value }))}
                  className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]">
                  <option value="">— No GL link —</option>
                  {coaAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                </select>
              </div>
              {formError && <p className="text-red-600 text-sm">{formError}</p>}
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setModalOpen(false)} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
                <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
