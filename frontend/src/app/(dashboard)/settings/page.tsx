'use client'

import { Save, Bell, Globe, Lock, Unlock, Trash2, Plus, ClipboardList, Building2, Upload, CalendarDays, BookOpen } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '@/lib/api'
import { useSettings, AppSettings } from '@/context/SettingsContext'
import VersionBadge from '@/components/VersionBadge'

interface PaymentTerm {
  id: number
  code: string
  name: string
  days: number
}

interface Account {
  id: number
  code: string
  name: string
  type: string
}

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
  user_id: number
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
  const [auditTab, setAuditTab] = useState<'timeline' | 'by_user' | 'by_entity'>('timeline')
  const [auditDateFrom, setAuditDateFrom] = useState("")
  const [auditDateTo, setAuditDateTo] = useState("")
  const [logoUploading, setLogoUploading] = useState(false)
  const [logoError, setLogoError] = useState("")
  const logoInputRef = useRef<HTMLInputElement>(null)
  const [paymentTerms, setPaymentTerms] = useState<PaymentTerm[]>([])
  const [termForm, setTermForm] = useState({ code: "", name: "", days: "" })
  const [addingTerm, setAddingTerm] = useState(false)
  const [termSaving, setTermSaving] = useState(false)
  const [accounts, setAccounts] = useState<Account[]>([])

  useEffect(() => { setForm(ctxSettings) }, [ctxSettings])

  useEffect(() => {
    apiFetch<{ items: Account[] }>("/api/accounts?limit=500")
      .then(d => setAccounts(d.items))
      .catch(() => {})
  }, [])

  useEffect(() => {
    apiFetch<AccountingPeriod[]>("/api/periods")
      .then(setPeriods)
      .catch(() => {})
  }, [])

  useEffect(() => {
    apiFetch<PaymentTerm[]>("/api/payment-terms")
      .then(setPaymentTerms)
      .catch(() => {})
  }, [])

  useEffect(() => {
    const params = new URLSearchParams({ limit: "200" })
    if (auditFilter) params.set("entity_type", auditFilter)
    if (auditDateFrom) params.set("date_from", auditDateFrom)
    if (auditDateTo) params.set("date_to", auditDateTo)
    apiFetch<{ total: number; items: AuditLogEntry[] }>(`/api/audit-log?${params}`)
      .then(res => setAuditLogs(res.items))
      .catch(() => {})
  }, [auditFilter, auditDateFrom, auditDateTo])

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

  const handleAddTerm = async () => {
    if (!termForm.code || !termForm.name || termForm.days === "") return
    setTermSaving(true)
    try {
      const created = await apiFetch<PaymentTerm>("/api/payment-terms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: termForm.code, name: termForm.name, days: Number(termForm.days) }),
      })
      setPaymentTerms(prev => [...prev, created].sort((a, b) => a.days - b.days))
      setTermForm({ code: "", name: "", days: "" })
      setAddingTerm(false)
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setTermSaving(false)
    }
  }

  const handleDeleteTerm = async (term: PaymentTerm) => {
    if (!window.confirm(`Delete payment term "${term.name}"?`)) return
    try {
      await apiFetch(`/api/payment-terms/${term.id}`, { method: "DELETE" })
      setPaymentTerms(prev => prev.filter(t => t.id !== term.id))
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const handleLogoUpload = async (file: File) => {
    setLogoUploading(true)
    setLogoError("")
    try {
      const fd = new FormData()
      fd.append("file", file)
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/settings/logo`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail || "Upload failed")
      }
      const data = await res.json() as { logo_url: string }
      setForm(prev => ({ ...prev, logo_url: data.logo_url }))
      reload()
    } catch (err) {
      setLogoError((err as Error).message)
    } finally {
      setLogoUploading(false)
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
    <div className="space-y-6 p-4 sm:p-6 max-w-4xl">
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
          <div>
            <label className="block text-sm font-semibold text-black/85 mb-2">Business Tagline</label>
            <input
              type="text"
              value={form.business_tagline}
              onChange={e => handleChange("business_tagline", e.target.value)}
              placeholder="e.g., Easy-Books · Double-Entry Accounting"
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
            />
            <p className="text-xs text-black/60 mt-1">Appears below your company name in the header and printed documents</p>
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
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-3 text-black">
          <Building2 className="w-5 h-5 text-[#b8943f]" />
          Company Profile
        </h2>
        <p className="text-sm text-black/60 mb-6">Appears on printed invoices, bills, and reports.</p>

        {logoError && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{logoError}</div>
        )}

        {/* Logo upload */}
        <div className="mb-6">
          <label className="block text-sm font-semibold text-black/85 mb-2">Company Logo</label>
          <div className="flex items-center gap-4">
            {form.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`${process.env.NEXT_PUBLIC_API_URL || ""}${form.logo_url}`}
                alt="Company logo"
                className="h-16 w-auto object-contain border border-[#ede9e2] rounded-lg p-1 bg-white"
              />
            ) : (
              <div className="h-16 w-24 flex items-center justify-center border-2 border-dashed border-[#ede9e2] rounded-lg text-black/30 text-xs">
                No logo
              </div>
            )}
            <div>
              <input
                ref={logoInputRef}
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
                className="hidden"
                onChange={e => { if (e.target.files?.[0]) handleLogoUpload(e.target.files[0]) }}
              />
              <button
                onClick={() => logoInputRef.current?.click()}
                disabled={logoUploading}
                className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-medium hover:bg-[#f6f3ee] transition-colors disabled:opacity-50"
              >
                <Upload className="w-4 h-4" />
                {logoUploading ? "Uploading…" : "Upload Logo"}
              </button>
              <p className="text-xs text-black/50 mt-1">PNG, JPEG, SVG, WebP, GIF — max 5 MB</p>
            </div>
          </div>
        </div>

        {/* Address */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-black/85 mb-2">Address Line 1</label>
            <input
              type="text"
              value={form.address_line1}
              onChange={e => handleChange("address_line1", e.target.value)}
              placeholder="e.g., 123 Business Street"
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-black/85 mb-2">Address Line 2</label>
            <input
              type="text"
              value={form.address_line2}
              onChange={e => handleChange("address_line2", e.target.value)}
              placeholder="e.g., Suite 4, Floor 2"
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">City</label>
              <input
                type="text"
                value={form.city}
                onChange={e => handleChange("city", e.target.value)}
                placeholder="e.g., Karachi"
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Country</label>
              <input
                type="text"
                value={form.country}
                onChange={e => handleChange("country", e.target.value)}
                placeholder="e.g., Pakistan"
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Phone</label>
              <input
                type="text"
                value={form.phone}
                onChange={e => handleChange("phone", e.target.value)}
                placeholder="e.g., +92 21 1234567"
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Website</label>
              <input
                type="text"
                value={form.website}
                onChange={e => handleChange("website", e.target.value)}
                placeholder="e.g., www.mycompany.com"
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40"
              />
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

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 pt-6 border-t border-[#ede9e2]">
          {[
            { field: 'invoice_number_format' as const, label: 'Invoice Number Format', prefix: form.invoice_prefix || 'INV' },
            { field: 'bill_number_format' as const,    label: 'Bill Number Format',    prefix: form.bill_prefix || 'BILL' },
          ].map(({ field, label, prefix }) => {
            const fmt = form[field] || '{prefix}-{seq:04d}'
            const preview = fmt
              .replace('{prefix}', prefix)
              .replace('{YYYY}', new Date().getFullYear().toString())
              .replace('{MM}', String(new Date().getMonth() + 1).padStart(2, '0'))
              .replace(/\{seq(?::(\d+)d)?\}/g, (_, w) => String(1).padStart(w ? parseInt(w) : 4, '0'))
            return (
              <div key={field}>
                <label className="block text-sm font-semibold text-black/85 mb-2">{label}</label>
                <input
                  type="text"
                  value={form[field]}
                  onChange={e => handleChange(field, e.target.value)}
                  placeholder="{prefix}-{seq:04d}"
                  className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black placeholder-black/40 font-mono text-sm"
                />
                <p className="text-xs text-black/60 mt-1 font-mono">Preview: <span className="font-bold text-[#b8943f]">{preview}</span></p>
                <p className="text-[10px] text-black/40 mt-0.5">Tokens: <code>{'{prefix}'}</code> <code>{'{seq:04d}'}</code> <code>{'{YYYY}'}</code> <code>{'{MM}'}</code></p>
              </div>
            )
          })}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] p-8 shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold flex items-center gap-3 text-black">
            <CalendarDays className="w-5 h-5 text-[#b8943f]" />
            Payment Terms
          </h2>
          <button
            onClick={() => setAddingTerm(v => !v)}
            className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg text-sm font-medium hover:bg-[#a07c35] transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Term
          </button>
        </div>

        {addingTerm && (
          <div className="mb-6 p-4 bg-[#f6f3ee] rounded-xl grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Code</label>
              <input
                type="text"
                placeholder="e.g. NET30"
                value={termForm.code}
                onChange={e => setTermForm(p => ({ ...p, code: e.target.value.toUpperCase() }))}
                className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Name</label>
              <input
                type="text"
                placeholder="e.g. Net 30 Days"
                value={termForm.name}
                onChange={e => setTermForm(p => ({ ...p, name: e.target.value }))}
                className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Days</label>
              <input
                type="number"
                min="0"
                placeholder="30"
                value={termForm.days}
                onChange={e => setTermForm(p => ({ ...p, days: e.target.value }))}
                className="w-full px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              />
            </div>
            <button
              onClick={handleAddTerm}
              disabled={termSaving}
              className="px-4 py-2 bg-[#1a1814] text-white rounded-lg text-sm font-bold hover:bg-[#b8943f] transition-colors disabled:opacity-50"
            >
              {termSaving ? "Saving…" : "Create"}
            </button>
          </div>
        )}

        {paymentTerms.length === 0 ? (
          <p className="text-sm text-black/40 py-4">No payment terms defined.</p>
        ) : (
          <div className="divide-y divide-[#ede9e2]">
            {paymentTerms.map(term => (
              <div key={term.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs font-bold bg-[#f6f3ee] px-2 py-0.5 rounded text-[#b8943f]">{term.code}</span>
                  <span className="font-medium text-black">{term.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-black/60">{term.days === 0 ? "Due on receipt" : `${term.days} days`}</span>
                  <button
                    onClick={() => handleDeleteTerm(term)}
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
        <h2 className="text-xl font-semibold mb-2 flex items-center gap-3 text-black">
          <BookOpen className="w-5 h-5 text-[#b8943f]" />
          Default GL Accounts
        </h2>
        <p className="text-sm text-black/55 mb-6">Select the default accounts used when posting invoices and bills. Enter an account code (e.g. 1100) or leave blank to use the system default.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {([
            { key: 'default_ar_account',      label: 'Accounts Receivable (AR)', hint: 'Debited on invoice post', types: ['Asset'] },
            { key: 'default_ap_account',      label: 'Accounts Payable (AP)',    hint: 'Credited on bill post',    types: ['Liability'] },
            { key: 'default_revenue_account', label: 'Revenue Account',          hint: 'Credited on invoice post', types: ['Revenue'] },
            { key: 'default_cogs_account',    label: 'COGS / Expense Account',   hint: 'Debited on bill post',     types: ['Expense'] },
          ] as { key: keyof AppSettings; label: string; hint: string; types: string[] }[]).map(({ key, label, hint, types }) => (
            <div key={key}>
              <label className="block text-sm font-semibold text-black/85 mb-1">{label}</label>
              <p className="text-xs text-black/50 mb-2">{hint}</p>
              <select
                value={form[key] ?? ''}
                onChange={e => handleChange(key, e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black text-sm"
              >
                <option value="">— use system default —</option>
                {accounts.filter(a => types.includes(a.type)).map(a => (
                  <option key={a.id} value={a.code}>{a.code} — {a.name}</option>
                ))}
              </select>
            </div>
          ))}
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
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <h2 className="text-xl font-semibold flex items-center gap-3 text-black">
            <ClipboardList className="w-5 h-5 text-[#b8943f]" />
            Audit Log
          </h2>
          <div className="flex flex-wrap gap-2 items-center">
            <input type="date" value={auditDateFrom} onChange={e => setAuditDateFrom(e.target.value)}
              className="px-2 py-1.5 border border-[#ede9e2] rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              placeholder="From" />
            <input type="date" value={auditDateTo} onChange={e => setAuditDateTo(e.target.value)}
              className="px-2 py-1.5 border border-[#ede9e2] rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              placeholder="To" />
            <select value={auditFilter} onChange={e => setAuditFilter(e.target.value)}
              className="px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#b8943f]">
              <option value="">All entities</option>
              <option value="account">Accounts</option>
              <option value="customer">Customers</option>
              <option value="vendor">Vendors</option>
              <option value="invoice">Invoices</option>
              <option value="bill">Bills</option>
              <option value="transaction">Transactions</option>
            </select>
            <button
              onClick={() => {
                const headers = ['Timestamp','User','Action','Entity','Detail']
                const rows = auditLogs.map(l => [
                  new Date(l.timestamp).toLocaleString(), l.user_name, l.action,
                  `${l.entity_type}${l.entity_id ? ' #' + l.entity_id : ''}`, l.detail ?? ''
                ])
                const csv = [headers, ...rows].map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
                const a = document.createElement('a'); a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv)
                a.download = 'audit-log.csv'; a.click()
              }}
              className="px-3 py-1.5 text-xs font-bold border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee] transition-colors"
            >
              Export CSV
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-4 border-b border-[#ede9e2]">
          {(['timeline', 'by_user', 'by_entity'] as const).map(tab => (
            <button key={tab} onClick={() => setAuditTab(tab)}
              className={`px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors border-b-2 -mb-px ${
                auditTab === tab
                  ? 'text-[#b8943f] border-[#b8943f]'
                  : 'text-black/50 border-transparent hover:text-black/70'
              }`}>
              {tab === 'timeline' ? 'Timeline' : tab === 'by_user' ? 'By User' : 'By Entity'}
            </button>
          ))}
        </div>

        {auditLogs.length === 0 ? (
          <p className="text-sm text-black/40 py-4">No audit log entries found.</p>
        ) : auditTab === 'timeline' ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-[#f6f3ee]">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Timestamp</th>
                  <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">User</th>
                  <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Action</th>
                  <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Entity</th>
                  <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Detail</th>
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
                    <td className="px-4 py-3 text-black/70 capitalize">{log.entity_type}{log.entity_id ? ` #${log.entity_id}` : ''}</td>
                    <td className="px-4 py-3 font-mono text-xs text-black/50 max-w-xs truncate">{log.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : auditTab === 'by_user' ? (
          <div className="space-y-3">
            {Object.entries(
              auditLogs.reduce((acc, l) => { acc[l.user_name] = (acc[l.user_name] || []); acc[l.user_name].push(l); return acc }, {} as Record<string, AuditLogEntry[]>)
            ).map(([user, entries]) => (
              <div key={user} className="border border-[#ede9e2] rounded-xl overflow-hidden">
                <div className="px-4 py-2.5 bg-[#f6f3ee] flex items-center justify-between">
                  <span className="text-sm font-bold text-[#1a1814]">{user}</span>
                  <span className="text-xs text-black/50">{entries.length} action{entries.length !== 1 ? 's' : ''}</span>
                </div>
                <div className="divide-y divide-[#ede9e2] max-h-48 overflow-y-auto">
                  {entries.slice(0, 20).map(l => (
                    <div key={l.id} className="px-4 py-2 flex items-center gap-3 text-xs">
                      <span className="text-black/40 font-mono w-32 flex-shrink-0">{new Date(l.timestamp).toLocaleString()}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase flex-shrink-0 ${
                        l.action === 'CREATE' ? 'bg-green-100 text-green-700' : l.action === 'DELETE' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
                      }`}>{l.action}</span>
                      <span className="text-black/70 capitalize">{l.entity_type}{l.entity_id ? ` #${l.entity_id}` : ''}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {Object.entries(
              auditLogs.reduce((acc, l) => { acc[l.entity_type] = (acc[l.entity_type] || []); acc[l.entity_type].push(l); return acc }, {} as Record<string, AuditLogEntry[]>)
            ).sort((a, b) => b[1].length - a[1].length).map(([entity, entries]) => (
              <div key={entity} className="border border-[#ede9e2] rounded-xl overflow-hidden">
                <div className="px-4 py-2.5 bg-[#f6f3ee] flex items-center justify-between">
                  <span className="text-sm font-bold text-[#1a1814] capitalize">{entity}</span>
                  <span className="text-xs text-black/50">{entries.length} event{entries.length !== 1 ? 's' : ''}</span>
                </div>
                <div className="divide-y divide-[#ede9e2] max-h-48 overflow-y-auto">
                  {entries.slice(0, 20).map(l => (
                    <div key={l.id} className="px-4 py-2 flex items-center gap-3 text-xs">
                      <span className="text-black/40 font-mono w-32 flex-shrink-0">{new Date(l.timestamp).toLocaleString()}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase flex-shrink-0 ${
                        l.action === 'CREATE' ? 'bg-green-100 text-green-700' : l.action === 'DELETE' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
                      }`}>{l.action}</span>
                      <span className="text-black/50 truncate">{l.detail}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Backup & Restore (local / on-premise installs) */}
      <div className="bg-white border border-[#ede9e2] rounded-2xl p-6 space-y-3">
        <h2 className="text-lg font-serif text-[#1a1814]">Backup &amp; Restore</h2>
        <p className="text-xs text-[#1a1814]/60">
          Download a full copy of your data (database + uploads), or restore from a backup.
          Available on on-premise (SQLite) installs.
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={async () => {
              const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
              const res = await fetch(`${base}/api/backup/download`, {
                headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
              })
              if (!res.ok) { alert("Backup is only available on local SQLite installs."); return }
              const blob = await res.blob()
              const url = URL.createObjectURL(blob)
              const a = document.createElement("a")
              a.href = url; a.download = "easybooks-backup.zip"; a.click()
              URL.revokeObjectURL(url)
            }}
            className="px-4 py-2 bg-[#1a1814] text-white rounded-xl text-sm font-bold hover:bg-[#b8943f] hover:text-black transition-all"
          >
            Download Backup
          </button>
          <label className="px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold cursor-pointer hover:bg-[#f6f3ee]">
            Restore from Backup…
            <input
              type="file"
              accept=".zip"
              className="hidden"
              onChange={async (e) => {
                const f = e.target.files?.[0]; if (!f) return
                if (!confirm("Restore will overwrite current data. Continue?")) return
                const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
                const fd = new FormData(); fd.append("file", f)
                const res = await fetch(`${base}/api/backup/restore`, {
                  method: "POST",
                  headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
                  body: fd,
                })
                alert(res.ok
                  ? "Restored. Restart the app to load the restored data."
                  : "Restore failed — check the file is a valid Easy-Books backup.")
              }}
            />
          </label>
        </div>
      </div>

      {/* Sample / Demo Data (evaluation) */}
      <section className="bg-white border border-[#ede9e2] rounded-xl p-5 space-y-3">
        <h2 className="text-lg font-serif text-[#1a1814]">Sample / Demo Data</h2>
        <p className="text-sm text-[#1a1814]/60">
          Create 5 ready-made demo companies (one per business model) so you can explore Easy-Books
          with realistic data. They are <strong>separate</strong> from your own company and log in with
          <code className="mx-1 px-1 bg-[#f6f3ee] rounded">demo1234</code>
          (e.g. <code>demo.simple@easy-books.app</code>). Remove them any time.
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium hover:bg-[#a07f33] disabled:opacity-50"
            onClick={async (e) => {
              const btn = e.currentTarget; btn.disabled = true
              try {
                const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
                const res = await fetch(`${base}/api/admin/demo/seed`, {
                  method: "POST",
                  headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
                })
                alert(res.ok
                  ? "Demo companies loaded. Log out and sign in with demo1234 to explore them."
                  : "Could not load demo data (admin only).")
              } finally { btn.disabled = false }
            }}
          >Load demo companies</button>
          <button
            className="px-4 py-2 rounded-lg border border-[#ede9e2] text-sm font-medium hover:bg-[#faf8f4]"
            onClick={async () => {
              if (!confirm("Remove all 5 demo companies and their data? Your own company is not affected.")) return
              const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
              const res = await fetch(`${base}/api/admin/demo/seed`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
              })
              alert(res.ok ? "Demo companies removed." : "Could not remove demo data (admin only).")
            }}
          >Remove demo companies</button>
        </div>
      </section>

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

      <div className="flex justify-end pt-2">
        <VersionBadge />
      </div>
    </div>
  )
}
