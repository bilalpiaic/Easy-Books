'use client'

import { Save, Bell, Globe, Lock, Unlock, Trash2, Plus, ClipboardList } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'
import { useSettings, AppSettings } from '@/context/SettingsContext'

interface AccountingPeriod {
  id: number
  name: string
  period_start: string
  period_end: string
  is_locked: boolean
}

interface AuditLogEntry {
  id: number
  action: string
  entity_type: string
  entity_id: number | null
  detail: string | null
  timestamp: string
  user_name: string
}

export default function SettingsPage() {
  const { settings: ctxSettings, reload } = useSettings()
  const [form, setForm] = useState<AppSettings>(ctxSettings)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState("")

  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [periodForm, setPeriodForm] = useState({ name: "", period_start: "", period_end: "" })
  const [addingPeriod, setAddingPeriod] = useState(false)
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([])
  const [auditFilter, setAuditFilter] = useState("")

  useEffect(() => { setForm(ctxSettings) }, [ctxSettings])

  useEffect(() => {
    apiFetch<AccountingPeriod[]>("/api/periods")
      .then(setPeriods)
      .catch(() => {})
  }, [])

  useEffect(() => {
    const url = auditFilter ? `/api/audit-log?entity_type=${auditFilter}&limit=100` : "/api/audit-log?limit=100"
    apiFetch<{ total: number; items: AuditLogEntry[] }>(url)
      .then(res => setAuditLogs(res.items))
      .catch(() => {})
  }, [auditFilter])

  const handleAddPeriod = async () => {
    if (!periodForm.period_start || !periodForm.period_end) return
    try {
      const created = await apiFetch<AccountingPeriod>("/api/periods", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(periodForm),
      })
      setPeriods(prev => [...prev, created])
      setPeriodForm({ name: "", period_start: "", period_end: "" })
      setAddingPeriod(false)
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const handleToggleLock = async (period: AccountingPeriod) => {
    try {
      const updated = await apiFetch<AccountingPeriod>(`/api/periods/${period.id}/lock`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_locked: !period.is_locked }),
      })
      setPeriods(prev => prev.map(p => p.id === updated.id ? updated : p))
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const handleDeletePeriod = async (period: AccountingPeriod) => {
    if (!window.confirm(`Delete period "${period.name || period.period_start}"?`)) return
    try {
      await apiFetch(`/api/periods/${period.id}`, { method: "DELETE" })
      setPeriods(prev => prev.filter(p => p.id !== period.id))
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const handleChange = (field: keyof AppSettings, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    setError("")
    try {
      await apiFetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      })
      reload()
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 p-8 max-w-4xl">
      <div>
        <h1 className="text-3xl font-serif font-medium text-black">Settings</h1>
        <p className="text-sm text-black/70 mt-1">Configure business and accounting settings</p>
      </div>

      {saved && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-green-700 font-medium">
          Settings saved successfully
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 font-medium">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl border border-[#ede9e2] p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-3 text-black">
          <Globe className="w-5 h-5 text-[#b8943f]" />
          Company Information
        </h2>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-semibold text-black/85 mb-2">Company Name</label>
            <input
              type="text"
              value={form.company_name}
              onChange={e => handleChange('company_name', e.target.value)}
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Tax ID / EIN</label>
              <input
                type="text"
                value={form.tax_id}
                onChange={e => handleChange('tax_id', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Currency</label>
              <select
                value={form.currency}
                onChange={e => handleChange('currency', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black"
              >
                <option value="PKR">PKR — Pakistani Rupee</option>
                <option value="USD">USD — US Dollar</option>
                <option value="EUR">EUR — Euro</option>
                <option value="GBP">GBP — British Pound</option>
                <option value="AED">AED — UAE Dirham</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Fiscal Year Start</label>
              <select
                value={form.fiscal_year_start}
                onChange={e => handleChange('fiscal_year_start', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black"
              >
                <option>January</option>
                <option>April</option>
                <option>July</option>
                <option>October</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Financial Statement Date</label>
              <select
                value={form.financial_statement_date}
                onChange={e => handleChange('financial_statement_date', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black"
              >
                <option value="month_end">Month End</option>
                <option value="quarter_end">Quarter End</option>
                <option value="year_end">Year End</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-6 text-black">Document Numbering</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-semibold text-black/85 mb-2">Invoice Prefix</label>
            <input
              type="text"
              value={form.invoice_prefix}
              onChange={e => handleChange('invoice_prefix', e.target.value)}
              placeholder="e.g., INV"
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
            />
            <p className="text-xs text-black/60 mt-1 font-medium">Example: {form.invoice_prefix}-001</p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-black/85 mb-2">Bill Prefix</label>
            <input
              type="text"
              value={form.bill_prefix}
              onChange={e => handleChange('bill_prefix', e.target.value)}
              placeholder="e.g., BILL"
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
            />
            <p className="text-xs text-black/60 mt-1 font-medium">Example: {form.bill_prefix}-001</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-3 text-black">
          <Bell className="w-5 h-5 text-[#b8943f]" />
          Notifications
        </h2>

        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-black">Email Notifications</h3>
            <p className="text-sm text-black/65 mt-1">Receive alerts for overdue invoices and bills</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={form.email_notifications === "true"}
              onChange={e => handleChange('email_notifications', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[#b8943f]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#b8943f]"></div>
          </label>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] p-8 shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold flex items-center gap-3 text-black">
            <Lock className="w-5 h-5 text-[#b8943f]" />
            Accounting Periods
          </h2>
          <button
            onClick={() => setAddingPeriod(v => !v)}
            className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg text-sm font-medium hover:bg-[#a07c35] transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Period
          </button>
        </div>

        {addingPeriod && (
          <div className="mb-6 p-4 bg-[#f6f3ee] rounded-xl grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Name (optional)</label>
              <input
                type="text"
                placeholder="e.g. Q1 2026"
                value={periodForm.name}
                onChange={e => setPeriodForm(p => ({ ...p, name: e.target.value }))}
                className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Start Date</label>
              <input
                type="date"
                value={periodForm.period_start}
                onChange={e => setPeriodForm(p => ({ ...p, period_start: e.target.value }))}
                className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">End Date</label>
              <input
                type="date"
                value={periodForm.period_end}
                onChange={e => setPeriodForm(p => ({ ...p, period_end: e.target.value }))}
                className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              />
            </div>
            <button
              onClick={handleAddPeriod}
              className="px-4 py-2 bg-[#1a1814] text-white rounded-lg text-sm font-bold hover:bg-[#b8943f] transition-colors"
            >
              Create
            </button>
          </div>
        )}

        {periods.length === 0 ? (
          <p className="text-sm text-black/40 py-4">No accounting periods defined. Add one to enable period locking.</p>
        ) : (
          <div className="divide-y divide-[#ede9e2]">
            {periods.map(period => (
              <div key={period.id} className="flex items-center justify-between py-3">
                <div>
                  <span className="font-medium text-black">{period.name || `${period.period_start} — ${period.period_end}`}</span>
                  {period.name && <span className="ml-2 text-sm text-black/50">{period.period_start} — {period.period_end}</span>}
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${period.is_locked ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    {period.is_locked ? 'Locked' : 'Open'}
                  </span>
                  <button
                    onClick={() => handleToggleLock(period)}
                    className="p-2 hover:bg-[#f6f3ee] rounded-lg transition-colors"
                    title={period.is_locked ? "Unlock period" : "Lock period"}
                  >
                    {period.is_locked ? <Unlock className="w-4 h-4 text-[#b8943f]" /> : <Lock className="w-4 h-4 text-[#1a1814]/60" />}
                  </button>
                  <button
                    onClick={() => handleDeletePeriod(period)}
                    className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4 text-red-400 hover:text-red-600" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] p-8 shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold flex items-center gap-3 text-black">
            <ClipboardList className="w-5 h-5 text-[#b8943f]" />
            Audit Log
          </h2>
          <select
            value={auditFilter}
            onChange={e => setAuditFilter(e.target.value)}
            className="px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
          >
            <option value="">All entities</option>
            <option value="account">Accounts</option>
            <option value="customer">Customers</option>
            <option value="vendor">Vendors</option>
            <option value="invoice">Invoices</option>
            <option value="bill">Bills</option>
            <option value="transaction">Transactions</option>
          </select>
        </div>

        {auditLogs.length === 0 ? (
          <p className="text-sm text-black/40 py-4">No audit log entries yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#f6f3ee] text-left">
                  <th className="px-4 py-3 text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Timestamp</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">User</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Action</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Entity</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ede9e2]">
                {auditLogs.map(log => (
                  <tr key={log.id} className="hover:bg-[#f6f3ee]/50">
                    <td className="px-4 py-3 font-mono text-xs text-black/60">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3 text-black/80">{log.user_name}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        log.action === 'CREATE' ? 'bg-green-100 text-green-700' :
                        log.action === 'DELETE' ? 'bg-red-100 text-red-700' :
                        log.action === 'REVERSE' ? 'bg-purple-100 text-purple-700' :
                        'bg-blue-100 text-blue-700'
                      }`}>{log.action}</span>
                    </td>
                    <td className="px-4 py-3 text-black/70 capitalize">{log.entity_type} {log.entity_id ? `#${log.entity_id}` : ''}</td>
                    <td className="px-4 py-3 font-mono text-xs text-black/50 max-w-xs truncate">{log.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex justify-end gap-3">
        <button
          onClick={() => setForm(ctxSettings)}
          className="px-6 py-2 border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee] text-black font-medium transition-colors"
        >
          Reset
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35] font-medium transition-colors disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>
    </div>
  )
}
