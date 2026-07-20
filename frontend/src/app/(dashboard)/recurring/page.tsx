'use client'

import { useEffect, useState } from 'react'
import { Plus, RefreshCw, Play, Trash2, ToggleLeft, ToggleRight, Pencil, Download, Printer } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useDp } from '@/context/SettingsContext'
import { downloadCSV } from '@/lib/utils'
import DocLink from '@/components/DocLink'
import PrintHeader from '@/components/PrintHeader'
import { useTranslation } from "react-i18next"
import { useMessages } from "@/context/MessageContext"

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
  const { confirm, toast } = useMessages()
  const { t: tr } = useTranslation()

  const [templates, setTemplates] = useState<RecurringTemplate[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<TemplateForm>(emptyForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [running, setRunning] = useState(false)
  const [lastRunResult, setLastRunResult] = useState<string | null>(null)
  const [now, setNow] = useState<Date | null>(null)
  const dp = useDp()

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
    setEditingId(null)
    setForm(emptyForm)
    setFormError('')
    setModalOpen(true)
  }

  const openEdit = (t: RecurringTemplate) => {
    setEditingId(t.id)
    setForm({
      name: t.name,
      description: t.description ?? '',
      frequency: t.frequency,
      next_run: t.next_run,
      entries: t.entries.map(e => ({ ...e })),
    })
    setFormError('')
    setModalOpen(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) { setFormError('Name is required'); return }
    if (form.entries.some(e => e.account_id === 0)) { setFormError('All entries must have an account'); return }
    const totalDebit = form.entries.reduce((s, e) => s + e.debit, 0)
    const totalCredit = form.entries.reduce((s, e) => s + e.credit, 0)
    if (Math.abs(totalDebit - totalCredit) > 0.001) {
      setFormError(`Debits (${totalDebit.toFixed(dp)}) must equal Credits (${totalCredit.toFixed(dp)})`); return
    }
    setSaving(true); setFormError('')
    try {
      const body = JSON.stringify({
        name: form.name,
        description: form.description || null,
        frequency: form.frequency,
        next_run: form.next_run,
        entries: form.entries,
      })
      if (editingId != null) {
        await apiFetch(`/api/recurring/${editingId}`, { method: 'PUT', body })
      } else {
        await apiFetch('/api/recurring', { method: 'POST', body })
      }
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
      toast((err as Error).message, "error")
    }
  }

  const handleDelete = async (t: RecurringTemplate) => {
    const ok = await confirm({
      title: `Delete template "${t.name}"?`,
      confirmLabel: "Delete",
      danger: true,
    })
    if (!ok) return
    try {
      await apiFetch(`/api/recurring/${t.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      toast((err as Error).message, "error")
    }
  }

  const handleRunDue = async () => {
    const ok = await confirm({
      title: "Post all templates due today or earlier?",
      confirmLabel: "Post due",
    })
    if (!ok) return
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
      <PrintHeader title="Recurring Entries" />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold flex items-center gap-2">
            <RefreshCw className="w-7 h-7 text-[var(--primary)]" />
            Recurring Entries
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Scheduled journal entries that post automatically</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{tr('common.print', 'Print')}</button>
          <button
            onClick={() => downloadCSV('recurring-templates.csv', templates.map(tmpl => ({ Name: tmpl.name, Description: tmpl.description ?? '', Frequency: FREQ_LABELS[tmpl.frequency] ?? tmpl.frequency, "Next Run": tmpl.next_run, "Last Run": tmpl.last_run ?? '', Active: tmpl.is_active ? 'Yes' : 'No' })))}
            disabled={templates.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={handleRunDue}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-50"
          >
            <Play className="w-4 h-4" />
            {running ? 'Running…' : 'Run Due Now'}
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg hover:bg-[var(--primary-dark)]">
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

      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-[var(--bg-page)] border-b border-[var(--border)]">
            <tr>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Name</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Frequency</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Next Run</th>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Last Run</th>
              <th className="ui-th text-center text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">{tr('col.status', 'Status')}</th>
              <th className="ui-th" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-[var(--text-muted)] animate-pulse">Loading…</td>
              </tr>
            ) : templates.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center">
                  <p className="text-[var(--text-muted)] mb-3">No recurring templates yet.</p>
                  <button onClick={openCreate} className="text-sm text-[var(--primary)] hover:underline font-medium">
                    + Create your first template
                  </button>
                </td>
              </tr>
            ) : templates.map(tmpl => (
              <tr key={tmpl.id} className={`hover:bg-[var(--bg-page)]/50 ${!tmpl.is_active ? 'opacity-50' : ''}`}>
                <td className="ui-td">
                  <p className="font-medium">{tmpl.name}</p>
                  {tmpl.description && <p className="text-xs text-[var(--text-muted)] mt-0.5">{tmpl.description}</p>}
                  <p className="text-xs text-[var(--text-muted)] mt-0.5 flex flex-wrap gap-x-2">
                    {tmpl.entries.map((e, i) => {
                      const acc = accounts.find(a => a.id === e.account_id)
                      return acc
                        ? <DocLink key={i} type="account" id={acc.code} label={`${acc.code} ${acc.name}`} className="text-xs text-[var(--text-muted)]" />
                        : <span key={i}>line {i + 1}</span>
                    })}
                  </p>
                </td>
                <td className="ui-td">
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase bg-blue-100 text-blue-700">
                    {FREQ_LABELS[tmpl.frequency] ?? tmpl.frequency}
                  </span>
                </td>
                <td className={`ui-td font-mono text-sm ${now && new Date(tmpl.next_run) <= now && tmpl.is_active ? 'text-red-600 font-bold' : 'text-[var(--text-muted)]'}`}>
                  {tmpl.next_run}
                </td>
                <td className="ui-td font-mono text-sm text-[var(--text-muted)]">{tmpl.last_run ?? '—'}</td>
                <td className="ui-td text-center">
                  <button
                    onClick={() => handleToggle(tmpl)}
                    title={tmpl.is_active ? 'Deactivate' : 'Activate'}
                    className="inline-flex items-center gap-1.5 text-xs font-medium"
                  >
                    {tmpl.is_active
                      ? <><ToggleRight className="w-5 h-5 text-green-500" /><span className="text-green-600">{tr('status.active', 'Active')}</span></>
                      : <><ToggleLeft className="w-5 h-5 text-[var(--border)]" /><span className="text-[var(--text-muted)]">{tr('status.inactive', 'Inactive')}</span></>}
                  </button>
                </td>
                <td className="ui-td">
                  <div className="flex items-center gap-2 justify-end">
                    <button onClick={() => openEdit(tmpl)} title="Edit template" className="text-[var(--text-primary)]/40 hover:text-[var(--primary)]">
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleDelete(tmpl)} title="Delete template" className="text-red-400 hover:text-red-600">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {/* Create modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 p-8 overflow-y-auto max-h-[92vh]">
            <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-6">
              {editingId != null ? 'Edit Recurring Template' : 'New Recurring Template'}
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Name</label>
                  <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                    placeholder="e.g. Monthly Office Rent"
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Frequency</label>
                  <select value={form.frequency} onChange={e => setForm(p => ({ ...p, frequency: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
                    {Object.entries(FREQ_LABELS).map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">First Run Date</label>
                  <input type="date" value={form.next_run} onChange={e => setForm(p => ({ ...p, next_run: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Description (optional)</label>
                  <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                    placeholder="Internal note about this recurring entry"
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-2">Journal Lines</label>
                <div className="border border-[var(--border)] rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-[var(--bg-page)]">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">{tr('col.account', 'Account')}</th>
                        <th className="px-4 py-2 text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)] w-28">{tr('col.debit', 'Debit')}</th>
                        <th className="px-4 py-2 text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)] w-28">{tr('col.credit', 'Credit')}</th>
                        <th className="w-8" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {form.entries.map((e, i) => (
                        <tr key={i}>
                          <td className="px-4 py-2">
                            <select
                              value={e.account_id || ''}
                              onChange={ev => updateEntry(i, 'account_id', ev.target.value)}
                              className="w-full px-2 py-1 bg-[var(--bg-page)] rounded-lg outline-none focus:ring-1 focus:ring-[var(--primary)] text-xs"
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
                              className="w-full px-2 py-1 bg-[var(--bg-page)] rounded-lg outline-none focus:ring-1 focus:ring-[var(--primary)] text-xs text-right font-mono" />
                          </td>
                          <td className="px-4 py-2">
                            <input type="number" min="0" step="0.01"
                              value={e.credit || ''}
                              onChange={ev => updateEntry(i, 'credit', ev.target.value)}
                              className="w-full px-2 py-1 bg-[var(--bg-page)] rounded-lg outline-none focus:ring-1 focus:ring-[var(--primary)] text-xs text-right font-mono" />
                          </td>
                          <td className="px-2 py-2">
                            {form.entries.length > 2 && (
                              <button onClick={() => removeEntryRow(i)} className="text-red-400 hover:text-red-600">×</button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-[var(--bg-page)] border-t border-[var(--border)]">
                      <tr>
                        <td className="px-4 py-2">
                          <button onClick={addEntryRow} className="text-xs text-[var(--primary)] hover:underline font-medium">
                            + Add line
                          </button>
                        </td>
                        <td className={`px-4 py-2 text-right font-mono text-xs font-bold ${Math.abs(totalDebit - totalCredit) > 0.001 ? 'text-red-600' : 'text-green-600'}`}>
                          {totalDebit.toFixed(dp)}
                        </td>
                        <td className={`px-4 py-2 text-right font-mono text-xs font-bold ${Math.abs(totalDebit - totalCredit) > 0.001 ? 'text-red-600' : 'text-green-600'}`}>
                          {totalCredit.toFixed(dp)}
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
                <button onClick={() => setModalOpen(false)} className="px-6 py-3 border border-[var(--text-primary)]/10 rounded-xl font-bold hover:bg-[var(--bg-page)]">{tr('common.cancel', 'Cancel')}</button>
                <button onClick={handleSave} disabled={saving}
                  className="px-6 py-3 bg-[var(--text-primary)] text-white rounded-xl font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50">
                  {saving ? 'Saving…' : editingId != null ? 'Save Changes' : 'Create Template'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
