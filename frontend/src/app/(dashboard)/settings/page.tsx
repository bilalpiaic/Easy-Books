'use client'

import { Save, Bell, Globe, Lock, Unlock, Trash2, Plus, Building2, Upload, CalendarDays, BookOpen, RefreshCw, Briefcase, Sun, Moon, Monitor, Palette } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '@/lib/api'
import { useSettings, AppSettings } from '@/context/SettingsContext'
import VersionBadge from '@/components/VersionBadge'
import UpdateModal from '@/components/UpdateModal'
import { useTheme, type ThemeMode, type ColorTheme } from '@/context/ThemeContext'
import { useLocale } from '@/context/LocaleContext'
import { LANGUAGES, type Language } from '@/i18n/config'
import { useTranslation } from "react-i18next"

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

export default function SettingsPage() {
  const { t } = useTranslation()

  const { settings: ctxSettings, reload } = useSettings()
  const [form, setForm] = useState<AppSettings>(ctxSettings)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState("")

  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [periodForm, setPeriodForm] = useState({ name: "", period_start: "", period_end: "" })
  const [addingPeriod, setAddingPeriod] = useState(false)
  const [logoUploading, setLogoUploading] = useState(false)
  const [logoError, setLogoError] = useState("")
  const logoInputRef = useRef<HTMLInputElement>(null)
  const [paymentTerms, setPaymentTerms] = useState<PaymentTerm[]>([])
  const [termForm, setTermForm] = useState({ code: "", name: "", days: "" })
  const [addingTerm, setAddingTerm] = useState(false)
  const [termSaving, setTermSaving] = useState(false)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [updateModalOpen, setUpdateModalOpen] = useState(false)
  const [bmTarget, setBmTarget] = useState("")
  const [bmBusy, setBmBusy] = useState(false)
  const [bmConfirm, setBmConfirm] = useState(false)
  const [bmResult, setBmResult] = useState<string | null>(null)
  const [bmErr, setBmErr] = useState<string | null>(null)

  useEffect(() => {
    setForm(ctxSettings)
    setBmTarget(ctxSettings.business_model || "simple")
  }, [ctxSettings])

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
              <label className="block text-sm font-semibold text-black/85 mb-2">{t('col.currency', 'Currency')}</label>
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
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Decimal Places</label>
              <select
                value={form.decimal_places ?? "2"}
                onChange={e => handleChange('decimal_places', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black"
              >
                <option value="2">2 — Standard (1,500.00)</option>
                <option value="4">4 — Extended (1,500.0000)</option>
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
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Inventory Cost Method</label>
              <select
                value={form.cost_method || "wavg"}
                onChange={e => handleChange('cost_method', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black"
              >
                <option value="wavg">Weighted Average (IAS 2)</option>
                <option value="fifo">FIFO — First In, First Out</option>
              </select>
              <p className="text-xs text-black/60 mt-1">Affects cost of goods sold and inventory valuation. Change only at a period boundary.</p>
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

        <div className="flex items-center justify-between pt-4 mt-4 border-t border-[#ede9e2]">
          <div>
            <h3 className="font-semibold text-black">Block overselling (prevent negative stock on sales)</h3>
            <p className="text-sm text-black/65 mt-1">When on, a sale that would drive a stock product below zero is rejected with an error. When off, the sale is allowed and stock goes negative (warn-only).</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer ml-6 flex-shrink-0">
            <input
              type="checkbox"
              checked={form.block_negative_stock === "true"}
              onChange={e => handleChange('block_negative_stock', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[#b8943f]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#b8943f]"></div>
          </label>
        </div>

        <div className="pt-4 mt-4 border-t border-[#ede9e2]">
          <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Display Density</label>
          <select
            value={form.ui_density}
            onChange={e => handleChange('ui_density', e.target.value)}
            className="ui-field w-full bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
          >
            <option value="comfortable">Comfortable</option>
            <option value="compact">Compact</option>
          </select>
        </div>

        <div className="pt-4 mt-4 border-t border-[#ede9e2]">
          <label className="block text-sm font-semibold text-black/85 mb-2">User Rights Module</label>
          <select
            value={form.user_rights_enabled ?? "false"}
            onChange={e => handleChange('user_rights_enabled', e.target.value)}
            className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black bg-white"
          >
            <option value="false">Disabled — all users access all data (default)</option>
            <option value="true">Enabled — enforce per-user permission matrix</option>
          </select>
          <p className="text-xs text-[#1a1814]/50 mt-1">
            When enabled, access to each module is controlled per-user via Settings → Permissions.
          </p>
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

      {/* Business Model */}
      <div className="bg-white rounded-xl border border-[#ede9e2] p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-2 flex items-center gap-3 text-black">
          <Briefcase className="w-5 h-5 text-[#b8943f]" />
          Business Model
        </h2>
        <p className="text-sm text-black/60 mb-6">
          Switching business model adds the corresponding Chart of Accounts accounts. Existing accounts and all historical data are preserved — no records are removed.
        </p>

        <div className="flex items-end gap-4 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-semibold text-black/85 mb-2">Business Model</label>
            <select
              value={bmTarget}
              onChange={e => { setBmTarget(e.target.value); setBmResult(null); setBmErr(null) }}
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black"
            >
              <option value="simple">Simple — basic income &amp; expenses</option>
              <option value="services">Services — projects, deferred revenue</option>
              <option value="trader">Trader — buy &amp; sell goods</option>
              <option value="manufacturing">Manufacturing — BOM, production orders</option>
              <option value="telecom_franchise">Telecom Franchise — MSR/RSO/FCA chain</option>
            </select>
          </div>
          <button
            disabled={bmBusy || bmTarget === (ctxSettings.business_model || "simple")}
            onClick={() => { setBmConfirm(true); setBmErr(null) }}
            className="px-5 py-2 bg-[#b8943f] text-white rounded-lg text-sm font-medium hover:bg-[#a07c35] transition-colors disabled:opacity-40 whitespace-nowrap"
          >
            Apply Model
          </button>
        </div>

        {bmConfirm && (
          <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-sm font-medium text-amber-800 mb-3">
              Switch to <strong>{bmTarget}</strong>? New CoA accounts will be added for this business model. This cannot be undone automatically.
            </p>
            <div className="flex gap-3">
              <button
                disabled={bmBusy}
                onClick={async () => {
                  setBmBusy(true); setBmErr(null)
                  try {
                    await apiFetch("/api/settings/business-model", {
                      method: "PATCH",
                      body: JSON.stringify({ business_model: bmTarget }),
                    })
                    setBmResult(`Business model switched to "${bmTarget}". New accounts have been provisioned in your Chart of Accounts.`)
                    setBmConfirm(false)
                    reload()
                  } catch (e: unknown) {
                    setBmErr(e instanceof Error ? e.message : "Failed to switch business model")
                  } finally { setBmBusy(false) }
                }}
                className="px-4 py-1.5 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 disabled:opacity-50"
              >
                {bmBusy ? "Switching…" : "Confirm Switch"}
              </button>
              <button
                onClick={() => setBmConfirm(false)}
                className="px-4 py-1.5 border border-amber-300 text-amber-800 rounded-lg text-sm font-medium hover:bg-amber-100"
              >{t('common.cancel', 'Cancel')}</button>
            </div>
          </div>
        )}

        {bmResult && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
            {bmResult}
          </div>
        )}
        {bmErr && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {bmErr}
          </div>
        )}
      </div>

      {/* ── Appearance ── */}
      <AppearanceSection />

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

      <div className="flex items-center justify-end gap-4 pt-2">
        <button
          onClick={() => setUpdateModalOpen(true)}
          className="flex items-center gap-1.5 text-[11px] text-[#1a1814]/50 hover:text-[#b8943f] transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          Check for Updates
        </button>
        <VersionBadge />
      </div>

      {updateModalOpen && (
        <UpdateModal onClose={() => setUpdateModalOpen(false)} />
      )}
    </div>
  )
}

/* ── Appearance settings — theme mode + color palette ── */
const COLOR_OPTIONS: { id: ColorTheme; label: string; accent: string; ring: string }[] = [
  { id: "gold",  label: "Classic Gold",  accent: "#b8943f", ring: "#b8943f" },
  { id: "blue",  label: "Ocean Blue",    accent: "#2563eb", ring: "#2563eb" },
  { id: "green", label: "Ledger Green",  accent: "#16a34a", ring: "#16a34a" },
  { id: "rose",  label: "Ruby Rose",     accent: "#e11d48", ring: "#e11d48" },
  { id: "slate", label: "Slate Minimal", accent: "#475569", ring: "#475569" },
]

function AppearanceSection() {
  const { theme, colorTheme, setTheme, setColorTheme } = useTheme()
  const { language, setLanguage } = useLocale()

  const modeBtn = (t: ThemeMode, Icon: React.ElementType, label: string) => (
    <button
      key={t}
      onClick={() => setTheme(t)}
      className={`flex flex-col items-center gap-1.5 px-4 py-3 rounded-xl border-2 text-xs font-semibold transition-all ${
        theme === t
          ? "border-[#b8943f] bg-[#faf6ec] text-[#b8943f]"
          : "border-[#ede9e2] bg-white text-[#1a1814]/60 hover:border-[#b8943f]/40"
      }`}
    >
      <Icon className="w-5 h-5" />
      {label}
    </button>
  )

  return (
    <section className="bg-white border border-[#ede9e2] rounded-xl p-5 space-y-5">
      <h2 className="text-lg font-serif text-[#1a1814] flex items-center gap-2">
        <Palette className="w-4 h-4 text-[#b8943f]" /> Appearance
      </h2>

      {/* Light / Dark / System */}
      <div>
        <p className="text-xs font-semibold text-[#1a1814]/55 uppercase tracking-wide mb-3">Display Mode</p>
        <div className="flex gap-3 flex-wrap">
          {modeBtn("light",  Sun,     "Light")}
          {modeBtn("dark",   Moon,    "Dark")}
          {modeBtn("system", Monitor, "System")}
        </div>
      </div>

      {/* Color theme swatches */}
      <div>
        <p className="text-xs font-semibold text-[#1a1814]/55 uppercase tracking-wide mb-3">Color Theme</p>
        <div className="flex gap-3 flex-wrap">
          {COLOR_OPTIONS.map(({ id, label, accent }) => (
            <button
              key={id}
              onClick={() => setColorTheme(id)}
              title={label}
              className={`group flex flex-col items-center gap-1.5 px-3 py-2.5 rounded-xl border-2 transition-all ${
                colorTheme === id
                  ? "border-2 shadow-sm"
                  : "border-[#ede9e2] hover:border-current"
              }`}
              style={colorTheme === id ? { borderColor: accent } : {}}
            >
              <span
                className="w-7 h-7 rounded-full transition-all"
                style={{
                  backgroundColor: accent,
                  outline: colorTheme === id ? `3px solid ${accent}` : "3px solid transparent",
                  outlineOffset: "2px",
                }}
              />
              <span className="text-[10px] font-semibold text-[#1a1814]/60 whitespace-nowrap">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Language */}
      <div>
        <p className="text-xs font-semibold text-[#1a1814]/55 uppercase tracking-wide mb-3">Display Language</p>
        <div className="flex gap-3 flex-wrap">
          {LANGUAGES.map(lang => (
            <button
              key={lang.code}
              onClick={() => setLanguage(lang.code as Language)}
              className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl border-2 text-sm font-medium transition-all ${
                language === lang.code
                  ? "border-[#b8943f] bg-[#faf6ec] text-[#b8943f]"
                  : "border-[#ede9e2] bg-white text-[#1a1814]/60 hover:border-[#b8943f]/40"
              }`}
            >
              <span className="text-lg leading-none">
                {lang.code === "en" ? "🇬🇧" : lang.code === "ur" ? "🇵🇰" : "🇨🇳"}
              </span>
              <span>{lang.nativeLabel}</span>
              <span className="text-xs text-[#1a1814]/40">({lang.label})</span>
            </button>
          ))}
        </div>
        <p className="text-[11px] text-[#1a1814]/40 mt-2">
          Urdu enables right-to-left (RTL) layout with Nastaliq script.
        </p>
      </div>

      <p className="text-[11px] text-[#1a1814]/40">
        Appearance preferences are saved per account and synced across sessions.
      </p>
    </section>
  )
}
