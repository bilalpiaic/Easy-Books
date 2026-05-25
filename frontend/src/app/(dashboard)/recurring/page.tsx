'use client'

import { useEffect, useState } from 'react'
import { Plus, RefreshCw, Play, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import { apiFetch } from '@/lib/api'

interface RecurringEntry {
  account_id: number
  debit: number
  credit: number
}

interface RecurringTemplate {
  id: number
  name: string
  description: string | null
  frequency: string
  next_run: string
  last_run: string | null
  is_active: boolean
  entries: RecurringEntry[]
}

interface Account { id: number; code: string; name: string }

interface TemplateForm {
  name: string
  description: string
  frequency: string
  next_run: string
  entries: RecurringEntry[]
}

const emptyForm: TemplateForm = {
  name: '', description: '', frequency: 'monthly',
  next_run: new Date().toISOString().split('T')[0],
  entries: [
    { account_id: 0, debit: 0, credit: 0 },
    { account_id: 0, debit: 0, credit: 0 },
  ],
}

const FREQ_LABELS: Record<string, string> = {
  daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly',
  quarterly: 'Quarterly', yearly: 'Yearly',
}

export default function RecurringPage() {
  const [templates, setTemplates] = useState<RecurringTemplate[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<TemplateForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [running, setRunning] = useState(false)
  const [lastRunResult, setLastRunResult] = useState<string | null>(null)
  const [now, setNow] = useState<Date | null>(null)

  const load = () => {
    setLoading(true)
    apiFetch<RecurringTemplate[]>('/api/recurring')
      .then(setTemplates)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setNow(new Date())
    load()
    apiFetch<{ items: Account[] }>('/api/accounts?limit=500')
      .then(d => setAccounts(d.items))
      .catch(() => {})
  }, [])

  const openCreate = () => {
    setForm(emptyForm)
    setFormError('')
    setModalOpen(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) { setFormError('Name is required'); return }
    if (form.entries.some(e => e.account_id === 0)) { setFormError('All entries must have an account'); return }
    const totalDebit = form.entries.reduce((s, e) => s + e.debit, 0)
    const totalCredit = form.entries.reduce((s, e) => s + e.credit, 0)
    if (Math.abs(totalDebit - totalCredit) > 0.001) {
      setFormError(`Debits (${totalDebit.toFixed(2)}) must equal Credits (${totalCredit.toFixed(2)})`); return
    }
    setSaving(true); setFormError('')
    try {
      await apiFetch('/api/recurring', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          description: form.description || null,
          frequency: form.frequency,
          next_run: form.next_run,
          entries: form.entries,
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

  const handleToggle = async (t: RecurringTemplate) => {
    try {
      await apiFetch(`/api/recurring/${t.id}?is_active=${!t.is_active}`, { method: 'PATCH' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const handleDelete = async (t: RecurringTemplate) => {
    if (!window.confirm(`Delete template "${t.name}"?`)) return
    try {
      await apiFetch(`/api/recurring/${t.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const handleRunDue = async () => {
    if (!window.confirm('Post all templates due today or earlier?')) return
    setRunning(true)
    setLastRunResult(null)
    try {
      const res = await apiFetch<{ posted: number }>('/api/recurring/run-due', { method: 'POST' })
      setLastRunResult(`${res.posted} transaction(s) posted.`)
      load()
    } catch (err) {
      setLastRunResult(`Error: ${(err as Error).message}`)
    } finally {
      setRunning(false)
    }
  }

  const updateEntry = (i: number, field: keyof RecurringEntry, value: string | number) => {
    setForm(p => {
      const entries = [...p.entries]
      entries[i] = { ...entries[i], [field]: field === 'account_id' ? Number(value) : parseFloat(String(value)) || 0 }
      return { ...p, entries }
    })
  }

  const addEntryRow = () => {
    setForm(p => ({ ...p, entries: [...p.entries, { account_id: 0, debit: 0, credit: 0 }] }))
  }

  const removeEntryRow = (i: number) => {
    setForm(p => ({ ...p, entries: p.entries.filter((_, idx) => idx !== i) }))
  }

  const totalDebit = form.entries.reduce((s, e) => s + e.debit, 0)
  const totalCredit = form.entries.reduce((s, e) => s + e.credit, 0)

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-medium flex items-center gap-2">
            <RefreshCw className="w-7 h-7 text-[#b8943f]" />
            Recurring Entries
          </h1>
          <p className="text-sm text-black/75 mt-1">Scheduled journal entries that post automatically</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRunDue}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-50"
          >
            <Play className="w-4 h-4" />
            {running ? 'Running…' : 'Run Due Now'}
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" />
            New Template
          </button>
        </div>
      </div>

      {lastRunResult && (
        <div className="px-4 py-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 font-medium">
          {lastRunResult}
        </div>
      )}

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Name</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Frequency</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Next Run</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Last Run</th>
              <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-black/60">Status</th>
              <th className="px-6 py-4" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-black/40 animate-pulse">Loading…</td>
              </tr>
            ) : templates.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center">
                  <p className="text-black/40 mb-3">No recurring templates yet.</p>
                  <button onClick={openCreate} className="text-sm text-[#b8943f] hover:underline font-medium">
                    + Create your first template
                  </button>
                </td>
              </tr>
            ) : templates.map(t => (
              <tr key={t.id} className={`hover:bg-[#f6f3ee]/50 ${!t.is_active ? 'opacity-50' : ''}`}>
                <td className="px-6 py-4">
                  <p className="font-medium">{t.name}</p>
                  {t.description && <p className="text-xs text-black/50 mt-0.5">{t.description}</p>}
                  <p className="text-xs text-black/40 mt-0.5">{t.entries.length} line(s)</p>
                </td>
                <td className="px-6 py-4">
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase bg-blue-100 text-blue-700">
                    {FREQ_LABELS[t.frequency] ?? t.frequency}
                  </span>
                </td>
                <td className={`px-6 py-4 font-mono text-sm ${now && new Date(t.next_run) <= now && t.is_active ? 'text-red-600 font-bold' : 'text-black/70'}`}>
                  {t.next_run}
                </td>
                <td className="px-6 py-4 font-mono text-sm text-black/50">{t.last_run ?? '—'}</td>
                <td className="px-6 py-4 text-center">
                  <button
                    onClick={() => handleToggle(t)}
                    title={t.is_active ? 'Deactivate' : 'Activate'}
                    className="inline-flex items-center gap-1.5 text-xs font-medium"
                  >
                    {t.is_active
                      ? <><ToggleRight className="w-5 h-5 text-green-500" /><span className="text-green-600">Active</span></>
                      : <><ToggleLeft className="w-5 h-5 text-black/30" /><span className="text-black/40">Inactive</span></>}
                  </button>
                </td>
                <td className="px-6 py-4">
                  <button onClick={() => handleDelete(t)} className="text-red-400 hover:text-red-600">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 p-8 overflow-y-auto max-h-[92vh]">
            <h2 className="text-2xl font-serif text-[#1a1814] mb-6">New Recurring Template</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Name</label>
                  <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                    placeholder="e.g. Monthly Office Rent"
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Frequency</label>
                  <select value={form.frequency} onChange={e => setForm(p => ({ ...p, frequency: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
                    {Object.entries(FREQ_LABELS).map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">First Run Date</label>
                  <input type="date" value={form.next_run} onChange={e => setForm(p => ({ ...p, next_run: e.target.value }))}
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Description (optional)</label>
                  <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                    placeholder="Internal note about this recurring entry"
                    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-2">Journal Lines</label>
                <div className="border border-[#ede9e2] rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-[#f6f3ee]">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-widest text-black/50">Account</th>
                        <th className="px-4 py-2 text-right text-xs font-bold uppercase tracking-widest text-black/50 w-28">Debit</th>
                        <th className="px-4 py-2 text-right text-xs font-bold uppercase tracking-widest text-black/50 w-28">Credit</th>
                        <th className="w-8" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#ede9e2]">
                      {form.entries.map((e, i) => (
                        <tr key={i}>
                          <td className="px-4 py-2">
                            <select
                              value={e.account_id || ''}
                              onChange={ev => updateEntry(i, 'account_id', ev.target.value)}
                              className="w-full px-2 py-1 bg-[#f6f3ee] rounded-lg outline-none focus:ring-1 focus:ring-[#b8943f] text-xs"
                            >
                              <option value="">— select account —</option>
                              {accounts.map(a => (
                                <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                              ))}
                            </select>
                          </td>
                          <td className="px-4 py-2">
                            <input type="number" min="0" step="0.01"
                              value={e.debit || ''}
                              onChange={ev => updateEntry(i, 'debit', ev.target.value)}
                              className="w-full px-2 py-1 bg-[#f6f3ee] rounded-lg outline-none focus:ring-1 focus:ring-[#b8943f] text-xs text-right font-mono" />
                          </td>
                          <td className="px-4 py-2">
                            <input type="number" min="0" step="0.01"
                              value={e.credit || ''}
                              onChange={ev => updateEntry(i, 'credit', ev.target.value)}
                              className="w-full px-2 py-1 bg-[#f6f3ee] rounded-lg outline-none focus:ring-1 focus:ring-[#b8943f] text-xs text-right font-mono" />
                          </td>
                          <td className="px-2 py-2">
                            {form.entries.length > 2 && (
                              <button onClick={() => removeEntryRow(i)} className="text-red-400 hover:text-red-600">×</button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-[#f6f3ee] border-t border-[#ede9e2]">
                      <tr>
                        <td className="px-4 py-2">
                          <button onClick={addEntryRow} className="text-xs text-[#b8943f] hover:underline font-medium">
                            + Add line
                          </button>
                        </td>
                        <td className={`px-4 py-2 text-right font-mono text-xs font-bold ${Math.abs(totalDebit - totalCredit) > 0.001 ? 'text-red-600' : 'text-green-600'}`}>
                          {totalDebit.toFixed(2)}
                        </td>
                        <td className={`px-4 py-2 text-right font-mono text-xs font-bold ${Math.abs(totalDebit - totalCredit) > 0.001 ? 'text-red-600' : 'text-green-600'}`}>
                          {totalCredit.toFixed(2)}
                        </td>
                        <td />
                      </tr>
                    </tfoot>
                  </table>
                </div>
                {Math.abs(totalDebit - totalCredit) > 0.001 && (
                  <p className="text-xs text-red-500 mt-1">Debits and credits must be equal</p>
                )}
              </div>

              {formError && <p className="text-red-600 text-sm">{formError}</p>}
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setModalOpen(false)} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">
                  Cancel
                </button>
                <button onClick={handleSave} disabled={saving}
                  className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
                  {saving ? 'Saving…' : 'Create Template'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
