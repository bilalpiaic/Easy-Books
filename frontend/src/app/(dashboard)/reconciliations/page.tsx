'use client'

import { useEffect, useState } from 'react'
import { Plus, CheckCircle, XCircle, Printer, Download } from 'lucide-react'
import PrintHeader from '@/components/PrintHeader'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV, fmtDate } from '@/lib/utils'

interface Reconciliation {
  id: number
  bank_account_id: number
  bank_account_name: string
  period_start: string
  period_end: string
  statement_balance: number
  status: string
}

interface RecLine {
  id: number
  journal_entry_id: number
  is_matched: boolean
  debit: number
  credit: number
  date: string
  description: string
}

interface RecDetail extends Reconciliation { lines: RecLine[] }
interface BankAccount { id: number; name: string }
interface GLAccount { id: number; code: string; name: string; is_group: boolean }
interface NewRecForm { bank_account_id: string; period_start: string; period_end: string; statement_balance: string }
interface AdjForm { description: string; account_id: string; date: string }

const emptyForm: NewRecForm = {
  bank_account_id: '',
  period_start: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0],
  period_end: new Date().toISOString().split('T')[0],
  statement_balance: '',
}

export default function Reconciliations() {
  const fmt = useFmt()
  const [recs, setRecs] = useState<Reconciliation[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<NewRecForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([])
  const [detail, setDetail] = useState<RecDetail | null>(null)
  const [glAccounts, setGlAccounts] = useState<GLAccount[]>([])
  const [adjOpen, setAdjOpen] = useState(false)
  const [adjForm, setAdjForm] = useState<AdjForm>({ description: '', account_id: '', date: '' })
  const [adjSaving, setAdjSaving] = useState(false)
  const [adjError, setAdjError] = useState('')

  const load = () => {
    setLoading(true)
    apiFetch<Reconciliation[]>('/api/reconciliations')
      .then(setRecs)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const openNew = () => {
    apiFetch<BankAccount[]>('/api/bank-accounts').then(setBankAccounts).catch(() => {})
    setForm(emptyForm); setFormError(''); setModalOpen(true)
  }

  const handleCreate = async () => {
    if (!form.bank_account_id || !form.statement_balance) { setFormError('Bank account and statement balance are required'); return }
    setSaving(true); setFormError('')
    try {
      await apiFetch('/api/reconciliations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bank_account_id: parseInt(form.bank_account_id),
          period_start: form.period_start,
          period_end: form.period_end,
          statement_balance: parseFloat(form.statement_balance),
        }),
      })
      setModalOpen(false); load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const openDetail = (rec: Reconciliation) => {
    apiFetch<RecDetail>(`/api/reconciliations/${rec.id}`).then(setDetail).catch(() => {})
    apiFetch<{ items: GLAccount[] }>('/api/accounts?limit=500')
      .then(r => setGlAccounts((r.items ?? []).filter(a => !a.is_group)))
      .catch(() => {})
    setAdjOpen(false)
    setAdjError('')
  }

  const toggleLine = async (recId: number, lineId: number, val: boolean) => {
    await apiFetch(`/api/reconciliations/${recId}/lines/${lineId}?is_matched=${val}`, { method: 'PATCH' }).catch(() => {})
    apiFetch<RecDetail>(`/api/reconciliations/${recId}`).then(setDetail).catch(() => {})
  }

  const closeRec = async (recId: number) => {
    await apiFetch(`/api/reconciliations/${recId}/close`, { method: 'POST' }).catch(() => {})
    setDetail(null); load()
  }

  const matchedBalance = detail ? detail.lines.filter(l => l.is_matched).reduce((s, l) => s + l.debit - l.credit, 0) : 0
  const difference = detail ? detail.statement_balance - matchedBalance : 0

  const openAdj = () => {
    setAdjForm({
      description: difference > 0 ? 'Bank interest income' : 'Bank charges',
      account_id: '',
      date: detail?.period_end ?? new Date().toISOString().split('T')[0],
    })
    setAdjError('')
    setAdjOpen(true)
  }

  const handlePostAdj = async () => {
    if (!adjForm.account_id) { setAdjError('Select an account'); return }
    setAdjSaving(true); setAdjError('')
    try {
      await apiFetch(`/api/reconciliations/${detail!.id}/adjustment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: adjForm.description,
          account_id: parseInt(adjForm.account_id),
          date: adjForm.date,
        }),
      })
      apiFetch<RecDetail>(`/api/reconciliations/${detail!.id}`).then(setDetail).catch(() => {})
      setAdjOpen(false)
    } catch (err) {
      setAdjError((err as Error).message)
    } finally {
      setAdjSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <PrintHeader title="Reconciliations" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif font-medium">Reconciliations</h1>
          <p className="text-sm text-black/75 mt-1">Bank reconciliation and cash verification</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => downloadCSV('reconciliations.csv', recs.map(r => ({ "Account": r.bank_account_name, "Period Start": r.period_start, "Period End": r.period_end, "Statement Balance": r.statement_balance, Status: r.status })))}
            disabled={recs.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
            title="Print"
          >
            <Printer className="w-4 h-4" />
            Print
          </button>
          <button onClick={openNew} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" />
            New Reconciliation
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Completed</p>
          <p className="text-3xl font-bold text-green-600 mt-2">{recs.filter(r => r.status === 'closed').length}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/75 uppercase tracking-widest font-bold">Open</p>
          <p className="text-3xl font-bold text-blue-600 mt-2">{recs.filter(r => r.status === 'open').length}</p>
        </div>
      </div>

      <div className="space-y-3">
        {loading ? (
          <div className="text-center py-12 text-black/40">Loading...</div>
        ) : recs.length === 0 ? (
          <div className="text-center py-12 text-black/40">No reconciliations yet. Create one to verify your cash balance.</div>
        ) : recs.map(rec => (
          <div key={rec.id} className="bg-white rounded-lg border border-[#ede9e2] p-6">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold">{rec.bank_account_name}</h3>
                <p className="text-xs text-black/60 mt-1">{rec.period_start} — {rec.period_end}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${rec.status === 'closed' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
                  {rec.status}
                </span>
                {rec.status === 'open' && (
                  <button onClick={() => openDetail(rec)} className="text-[#b8943f] font-bold text-sm hover:underline">Open</button>
                )}
              </div>
            </div>
            <div className="mt-3 text-sm text-black/60">
              Statement balance: <span className="font-mono font-bold text-black">{fmt(rec.statement_balance)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* New Reconciliation Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-8">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">New Reconciliation</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Bank Account</label>
                <select value={form.bank_account_id} onChange={e => setForm(p => ({ ...p, bank_account_id: e.target.value }))}
                  className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]">
                  <option value="">— Select —</option>
                  {bankAccounts.map(ba => <option key={ba.id} value={ba.id}>{ba.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Period Start</label>
                  <input type="date" value={form.period_start} onChange={e => setForm(p => ({ ...p, period_start: e.target.value }))}
                    className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Period End</label>
                  <input type="date" value={form.period_end} onChange={e => setForm(p => ({ ...p, period_end: e.target.value }))}
                    className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Bank Statement Balance</label>
                <input type="number" step="0.01" value={form.statement_balance} onChange={e => setForm(p => ({ ...p, statement_balance: e.target.value }))}
                  placeholder="Ending balance on bank statement"
                  className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
              </div>
              {formError && <p className="text-red-600 text-sm">{formError}</p>}
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setModalOpen(false)} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
                <button onClick={handleCreate} disabled={saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                  {saving ? 'Creating...' : 'Create'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reconciliation Detail */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setDetail(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 p-8 overflow-y-auto max-h-[90vh]">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-2">Reconcile: {detail.bank_account_name}</h2>
            <p className="text-sm text-black/60 mb-6">{detail.period_start} — {detail.period_end}</p>

            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-[#f6f3ee] rounded-xl p-4 text-center">
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">Statement</p>
                <p className="text-lg font-bold font-mono">{fmt(detail.statement_balance)}</p>
              </div>
              <div className="bg-[#f6f3ee] rounded-xl p-4 text-center">
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">Matched GL</p>
                <p className="text-lg font-bold font-mono">{fmt(matchedBalance)}</p>
              </div>
              <div className={`rounded-xl p-4 text-center ${Math.abs(difference) < 0.01 ? 'bg-green-50' : 'bg-red-50'}`}>
                <p className="text-xs text-black/50 uppercase tracking-widest mb-1">Difference</p>
                <p className={`text-lg font-bold font-mono ${Math.abs(difference) < 0.01 ? 'text-green-600' : 'text-red-600'}`}>{fmt(difference)}</p>
              </div>
            </div>

            {Math.abs(difference) >= 0.01 && (
              <div className="mb-6 border border-amber-200 rounded-xl bg-amber-50 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-amber-800">
                    {difference > 0 ? 'Unrecorded credit (bank interest / refund)' : 'Unrecorded debit (bank charges / fee)'}
                  </span>
                  <button
                    onClick={() => adjOpen ? setAdjOpen(false) : openAdj()}
                    className="text-xs font-bold text-amber-700 hover:underline"
                  >
                    {adjOpen ? 'Cancel' : 'Post Adjustment'}
                  </button>
                </div>
                {adjOpen && (
                  <div className="mt-3 pt-3 border-t border-amber-200 space-y-3">
                    <div>
                      <label className="block text-xs font-bold uppercase tracking-widest text-amber-900/70 mb-1">Description</label>
                      <input type="text" value={adjForm.description}
                        onChange={e => setAdjForm(f => ({ ...f, description: e.target.value }))}
                        className="w-full ui-field bg-white rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-widest text-amber-900/70 mb-1">
                          {difference > 0 ? 'Credit account (income)' : 'Debit account (expense)'}
                        </label>
                        <select value={adjForm.account_id}
                          onChange={e => setAdjForm(f => ({ ...f, account_id: e.target.value }))}
                          className="w-full ui-field bg-white rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]">
                          <option value="">— Select —</option>
                          {glAccounts.map(a => (
                            <option key={a.id} value={a.id}>{a.code} {a.name}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-widest text-amber-900/70 mb-1">Date</label>
                        <input type="date" value={adjForm.date}
                          onChange={e => setAdjForm(f => ({ ...f, date: e.target.value }))}
                          className="w-full ui-field bg-white rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
                      </div>
                    </div>
                    {adjError && <p className="text-red-600 text-sm">{adjError}</p>}
                    <button onClick={handlePostAdj} disabled={adjSaving}
                      className="w-full py-2 bg-[#1a1814] text-white rounded-xl font-bold text-sm hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                      {adjSaving ? 'Posting…' : `Post adjustment (${fmt(Math.abs(difference))})`}
                    </button>
                  </div>
                )}
              </div>
            )}

            <div className="overflow-x-auto mb-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-[#f6f3ee]">
                    <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">Date</th>
                    <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">Description</th>
                    <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Debit</th>
                    <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Credit</th>
                    <th className="ui-th text-center text-xs font-bold uppercase tracking-widest text-black/60">Clear</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ede9e2]">
                  {detail.lines.length === 0 ? (
                    <tr><td colSpan={5} className="ui-td text-center text-black/40">No GL entries for this period/account.</td></tr>
                  ) : detail.lines.map(ln => (
                    <tr key={ln.id} className={ln.is_matched ? 'bg-green-50/60' : ''}>
                      <td className="ui-td text-black/60">{fmtDate(ln.date)}</td>
                      <td className="ui-td max-w-xs truncate">{ln.description}</td>
                      <td className="ui-td text-right font-mono">{ln.debit > 0 ? fmt(ln.debit) : '—'}</td>
                      <td className="ui-td text-right font-mono">{ln.credit > 0 ? fmt(ln.credit) : '—'}</td>
                      <td className="ui-td text-center">
                        <button onClick={() => toggleLine(detail.id, ln.id, !ln.is_matched)}>
                          {ln.is_matched
                            ? <CheckCircle className="w-5 h-5 text-green-600 mx-auto" />
                            : <XCircle className="w-5 h-5 text-black/20 mx-auto hover:text-[#b8943f]" />}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end gap-3">
              <button onClick={() => setDetail(null)} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Close</button>
              <button
                onClick={() => closeRec(detail.id)}
                disabled={Math.abs(difference) >= 0.01}
                className="px-6 py-3 bg-green-600 text-white rounded-xl font-bold hover:bg-green-700 disabled:opacity-40"
              >
                Close Reconciliation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
