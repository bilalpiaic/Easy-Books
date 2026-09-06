'use client'

import { Save, Bell, Globe, Lock, Unlock, Trash2, Plus, Building2, Upload, CalendarDays, BookOpen, RefreshCw, Layers, Sun, Moon, Monitor, Palette, Sparkles, X, KeyRound, Copy, Check, MessageCircle, LayoutDashboard, PenTool } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { apiFetch } from '@/lib/api'
import { fmtDate } from '@/lib/utils'
import { useSettings, AppSettings } from '@/context/SettingsContext'
import { useModules } from '@/context/ModuleContext'
import { getCurrentUser } from '@/lib/auth'
import {
  HOME_PREF_KEY,
  hasOperationsHome,
  type HomePreference,
} from '@/lib/dashboardHome'
import VersionBadge from '@/components/VersionBadge'
import UpdateModal from '@/components/UpdateModal'
import { useTheme, type ThemeMode, type ColorTheme } from '@/context/ThemeContext'
import { useLocale } from '@/context/LocaleContext'
import { LANGUAGES, type Language } from '@/i18n/config'
import { useTranslation } from "react-i18next"
import { useMessages } from "@/context/MessageContext"

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
  const { confirm, toast } = useMessages()
  const { t } = useTranslation()
  const router = useRouter()

  const { settings: ctxSettings, reload } = useSettings()
  const { installedModules } = useModules()
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
  const [praTesting, setPraTesting] = useState(false)
  const [praTestResult, setPraTestResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [praShowToken, setPraShowToken] = useState(false)
  const [uaeTesting, setUaeTesting] = useState(false)
  const [uaeTestResult, setUaeTestResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [uaeShowKey, setUaeShowKey] = useState(false)
  const [zatcaTesting, setZatcaTesting] = useState(false)
  const [zatcaTestResult, setZatcaTestResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [zatcaShowToken, setZatcaShowToken] = useState(false)
  const [peppolTesting, setPeppolTesting] = useState(false)
  const [peppolTestResult, setPeppolTestResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [peppolShowKey, setPeppolShowKey] = useState(false)

  useEffect(() => {
    setForm(ctxSettings)
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
      toast((err as Error).message, "error")
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
      toast((err as Error).message, "error")
    }
  }

  const handleDeletePeriod = async (period: AccountingPeriod) => {
    const ok = await confirm({
      title: `Delete period "${period.name || period.period_start}"?`,
      confirmLabel: "Delete",
      danger: true,
    })
    if (!ok) return
    try {
      await apiFetch(`/api/periods/${period.id}`, { method: "DELETE" })
      setPeriods(prev => prev.filter(p => p.id !== period.id))
    } catch (err) {
      toast((err as Error).message, "error")
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
      toast((err as Error).message, "error")
    } finally {
      setTermSaving(false)
    }
  }

  const handleDeleteTerm = async (term: PaymentTerm) => {
    const ok = await confirm({
      title: `Delete payment term "${term.name}"?`,
      confirmLabel: "Delete",
      danger: true,
    })
    if (!ok) return
    try {
      await apiFetch(`/api/payment-terms/${term.id}`, { method: "DELETE" })
      setPaymentTerms(prev => prev.filter(t => t.id !== term.id))
    } catch (err) {
      toast((err as Error).message, "error")
    }
  }

  const handleLogoUpload = async (file: File) => {
    setLogoUploading(true)
    setLogoError("")
    try {
      const fd = new FormData()
      fd.append("file", file)
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/settings/logo`, {
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

  const [tab, setTab] = useState("company")

  // Read ?tab= from URL on mount (avoids useSearchParams Suspense requirement)
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("tab")
    if (t === "studio") {
      router.replace("/settings/studio")
      return
    }
    if (t) setTab(t)
  }, [router])

  const isAdminOrOwner =
    getCurrentUser()?.role === "admin" || getCurrentUser()?.role === "owner"

  const TABS: { id: string; label: string; href?: string }[] = [
    { id: "company",     label: "Company"     },
    { id: "accounting",  label: "Accounting"  },
    { id: "preferences", label: "Preferences" },
    { id: "advanced",    label: "Advanced"    },
    ...(isAdminOrOwner ? [{ id: "studio", label: "Studio", href: "/settings/studio" }] : []),
    // Machine-to-machine keys are admin/owner territory (matches the
    // backend's AdminUserDep gate) — hide the tab entirely for others
    // rather than showing content that would just 403.
    ...(isAdminOrOwner ? [{ id: "api-keys", label: "API Keys" }] : []),
    { id: "updates",     label: "Updates"     },
  ]

  // Tabs that have the main settings form — show Save/Reset on these
  const FORM_TABS = new Set(["company", "accounting", "preferences"])

  return (
    <div className="space-y-6 p-4 sm:p-6 max-w-4xl">
      <div>
        <h1 className="text-xl sm:text-3xl font-bold text-black">Settings</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">Configure business and accounting settings</p>
      </div>

      {/* Tab bar — scroll on narrow screens so tabs never clip */}
      <div className="overflow-x-auto scrollbar-hide -mx-1 px-1 border-b border-[var(--border)]">
        <div className="flex gap-1 min-w-max">
          {TABS.map(t => (
            <button key={t.id} type="button" onClick={() => t.href ? router.push(t.href) : setTab(t.id)}
              className={`shrink-0 whitespace-nowrap px-3 sm:px-5 py-2 text-[13px] font-medium rounded-t-lg transition-colors ${
                tab === t.id
                  ? "bg-white border border-b-white border-[var(--border)] text-[var(--primary)] -mb-px"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              }`}>
              {t.label}
            </button>
          ))}
        </div>
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

      { tab === "company" && <>

      <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-3 text-black">
          <Globe className="w-5 h-5 text-[var(--primary)]" />
          Company Information
        </h2>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Company Name</label>
            <input
              type="text"
              value={form.company_name}
              onChange={e => handleChange('company_name', e.target.value)}
              className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Business Tagline</label>
            <input
              type="text"
              value={form.business_tagline}
              onChange={e => handleChange("business_tagline", e.target.value)}
              placeholder="e.g., Easy-Books · Double-Entry Accounting"
              className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
            />
            <p className="text-xs text-[var(--text-muted)] mt-1">Appears below your company name in the header and printed documents</p>
          </div>


          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Tax ID / EIN</label>
              <input
                type="text"
                value={form.tax_id}
                onChange={e => handleChange('tax_id', e.target.value)}
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">{t('col.currency', 'Currency')}</label>
              <select
                value={form.currency}
                onChange={e => handleChange('currency', e.target.value)}
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black"
              >
                <option value="PKR">PKR — Pakistani Rupee</option>
                <option value="USD">USD — US Dollar</option>
                <option value="EUR">EUR — Euro</option>
                <option value="GBP">GBP — British Pound</option>
                <option value="AED">AED — UAE Dirham</option>
                <option value="SAR">SAR — Saudi Riyal</option>
                <option value="INR">INR — Indian Rupee</option>
                <option value="CNY">CNY — Chinese Yuan</option>
                <option value="CAD">CAD — Canadian Dollar</option>
                <option value="AUD">AUD — Australian Dollar</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Decimal Places</label>
              <select
                value={form.decimal_places ?? "2"}
                onChange={e => handleChange('decimal_places', e.target.value)}
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black"
              >
                <option value="0">0 — Whole numbers (1,500)</option>
                <option value="2">2 — Standard (1,500.00)</option>
                <option value="4">4 — Extended (1,500.0000)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Fiscal Year Start</label>
              <select
                value={form.fiscal_year_start}
                onChange={e => handleChange('fiscal_year_start', e.target.value)}
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black"
              >
                <option>January</option>
                <option>April</option>
                <option>July</option>
                <option>October</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Week Starts On</label>
              <select
                value={form.week_start_day || "Monday"}
                onChange={e => handleChange('week_start_day', e.target.value)}
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black"
              >
                {["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"].map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <p className="text-xs text-[var(--text-muted)] mt-1">Used by report period presets (This/Last/Next Week).</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Financial Statement Date</label>
              <select
                value={form.financial_statement_date}
                onChange={e => handleChange('financial_statement_date', e.target.value)}
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black"
              >
                <option value="month_end">Month End</option>
                <option value="quarter_end">Quarter End</option>
                <option value="year_end">Year End</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Inventory Cost Method</label>
              <select
                value={form.cost_method || "wavg"}
                onChange={e => handleChange('cost_method', e.target.value)}
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black"
              >
                <option value="wavg">Weighted Average (IAS 2)</option>
                <option value="fifo">FIFO — First In, First Out</option>
              </select>
              <p className="text-xs text-[var(--text-muted)] mt-1">Affects cost of goods sold and inventory valuation. Change only at a period boundary.</p>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-3 text-black">
          <Building2 className="w-5 h-5 text-[var(--primary)]" />
          Company Profile
        </h2>
        <p className="text-sm text-[var(--text-muted)] mb-6">Appears on printed invoices, bills, and reports.</p>

        {logoError && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{logoError}</div>
        )}

        {/* Logo upload */}
        <div className="mb-6">
          <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Company Logo</label>
          <div className="flex items-center gap-4">
            {form.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}${form.logo_url}`}
                alt="Company logo"
                className="h-16 w-auto object-contain border border-[var(--border)] rounded-lg p-1 bg-white"
              />
            ) : (
              <div className="h-16 w-24 flex items-center justify-center border-2 border-dashed border-[var(--border)] rounded-lg text-[var(--border)] text-xs">
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
                className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-medium hover:bg-[var(--bg-page)] transition-colors disabled:opacity-50"
              >
                <Upload className="w-4 h-4" />
                {logoUploading ? "Uploading…" : "Upload Logo"}
              </button>
              <p className="text-xs text-[var(--text-muted)] mt-1">PNG, JPEG, SVG, WebP, GIF — max 5 MB</p>
            </div>
          </div>
        </div>

        {/* Address */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Address Line 1</label>
            <input
              type="text"
              value={form.address_line1}
              onChange={e => handleChange("address_line1", e.target.value)}
              placeholder="e.g., 123 Business Street"
              className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Address Line 2</label>
            <input
              type="text"
              value={form.address_line2}
              onChange={e => handleChange("address_line2", e.target.value)}
              placeholder="e.g., Suite 4, Floor 2"
              className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">City</label>
              <input
                type="text"
                value={form.city}
                onChange={e => handleChange("city", e.target.value)}
                placeholder="e.g., Karachi"
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Country</label>
              <input
                type="text"
                value={form.country}
                onChange={e => handleChange("country", e.target.value)}
                placeholder="e.g., Pakistan"
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Phone</label>
              <input
                type="text"
                value={form.phone}
                onChange={e => handleChange("phone", e.target.value)}
                placeholder="e.g., +92 21 1234567"
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Website</label>
              <input
                type="text"
                value={form.website}
                onChange={e => handleChange("website", e.target.value)}
                placeholder="e.g., www.mycompany.com"
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
              />
            </div>
          </div>
        </div>
      </div>

      </> }
      { tab === "accounting" && <>

      <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-6 text-black">Document Numbering</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Invoice Prefix</label>
            <input
              type="text"
              value={form.invoice_prefix}
              onChange={e => handleChange('invoice_prefix', e.target.value)}
              placeholder="e.g., INV"
              className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
            />
            <p className="text-xs text-[var(--text-muted)] mt-1 font-medium">Example: {form.invoice_prefix}-001</p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Bill Prefix</label>
            <input
              type="text"
              value={form.bill_prefix}
              onChange={e => handleChange('bill_prefix', e.target.value)}
              placeholder="e.g., BILL"
              className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40"
            />
            <p className="text-xs text-[var(--text-muted)] mt-1 font-medium">Example: {form.bill_prefix}-001</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 pt-6 border-t border-[var(--border)]">
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
                <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">{label}</label>
                <input
                  type="text"
                  value={form[field]}
                  onChange={e => handleChange(field, e.target.value)}
                  placeholder="{prefix}-{seq:04d}"
                  className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black placeholder-black/40 font-mono text-sm"
                />
                <p className="text-xs text-[var(--text-muted)] mt-1 font-mono">Preview: <span className="font-bold text-[var(--primary)]">{preview}</span></p>
                <p className="text-[10px] text-[var(--text-muted)] mt-0.5">Tokens: <code>{'{prefix}'}</code> <code>{'{seq:04d}'}</code> <code>{'{YYYY}'}</code> <code>{'{MM}'}</code></p>
              </div>
            )
          })}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold flex items-center gap-3 text-black">
            <CalendarDays className="w-5 h-5 text-[var(--primary)]" />
            Payment Terms
          </h2>
          <button
            onClick={() => setAddingTerm(v => !v)}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Term
          </button>
        </div>

        {addingTerm && (
          <div className="mb-6 p-4 bg-[var(--bg-page)] rounded-xl grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Code</label>
              <input
                type="text"
                placeholder="e.g. NET30"
                value={termForm.code}
                onChange={e => setTermForm(p => ({ ...p, code: e.target.value.toUpperCase() }))}
                className="w-full px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Name</label>
              <input
                type="text"
                placeholder="e.g. Net 30 Days"
                value={termForm.name}
                onChange={e => setTermForm(p => ({ ...p, name: e.target.value }))}
                className="w-full px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Days</label>
              <input
                type="number"
                min="0"
                placeholder="30"
                value={termForm.days}
                onChange={e => setTermForm(p => ({ ...p, days: e.target.value }))}
                className="w-full px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
              />
            </div>
            <button
              onClick={handleAddTerm}
              disabled={termSaving}
              className="px-4 py-2 bg-[var(--text-primary)] text-white rounded-lg text-sm font-bold hover:bg-[var(--primary)] transition-colors disabled:opacity-50"
            >
              {termSaving ? "Saving…" : "Create"}
            </button>
          </div>
        )}

        {paymentTerms.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)] py-4">No payment terms defined.</p>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {paymentTerms.map(term => (
              <div key={term.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs font-bold bg-[var(--bg-page)] px-2 py-0.5 rounded text-[var(--primary)]">{term.code}</span>
                  <span className="font-medium text-black">{term.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-[var(--text-muted)]">{term.days === 0 ? "Due on receipt" : `${term.days} days`}</span>
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

      <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-2 flex items-center gap-3 text-black">
          <BookOpen className="w-5 h-5 text-[var(--primary)]" />
          Default GL Accounts
        </h2>
        <p className="text-sm text-[var(--text-muted)] mb-6">Select the default accounts used when posting invoices and bills. Enter an account code (e.g. 1100) or leave blank to use the system default.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {([
            { key: 'default_ar_account',      label: 'Accounts Receivable (AR)', hint: 'Debited on invoice post', types: ['Asset'] },
            { key: 'default_ap_account',      label: 'Accounts Payable (AP)',    hint: 'Credited on bill post',    types: ['Liability'] },
            { key: 'default_revenue_account', label: 'Revenue Account',          hint: 'Credited on invoice post', types: ['Revenue'] },
            { key: 'default_cogs_account',    label: 'COGS / Expense Account',   hint: 'Debited on bill post',     types: ['Expense'] },
            { key: 'default_mfg_labour_account',    label: 'Manufacturing Labour',    hint: 'Stage entries + PO labour (spinning: Cr 5100). Processing uses contractor labor 5220.',    types: ['Expense'] },
            { key: 'default_mfg_overhead_account',  label: 'Manufacturing Overhead',  hint: 'Stage entries + PO overhead (spinning: Cr 5200). Processing shrinkage posts to 5215.',  types: ['Expense'] },
            { key: 'default_scrap_expense_account', label: 'Production Scrap Expense', hint: 'PO scrap/damage + spinning waste 5901–5904. Processing wastage sales credit 4160.', types: ['Expense'] },
          ] as { key: keyof AppSettings; label: string; hint: string; types: string[] }[]).map(({ key, label, hint, types }) => (
            <div key={key}>
              <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1">{label}</label>
              <p className="text-xs text-[var(--text-muted)] mb-2">{hint}</p>
              <select
                value={form[key] ?? ''}
                onChange={e => handleChange(key, e.target.value)}
                className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black text-sm"
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

      {/* ── ACCOUNTING TAB ends, PREFERENCES TAB begins ── */}
      </> }
      { tab === "preferences" && <>

      <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-3 text-black">
          <Bell className="w-5 h-5 text-[var(--primary)]" />
          Alerts &amp; email
        </h2>

        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-black">In-app Alerts</h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">Show the Alerts bell for overdue invoices, low stock, and pending approvals</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={form.in_app_alerts !== "false"}
              onChange={e => handleChange('in_app_alerts', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[var(--primary)]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)]"></div>
          </label>
        </div>

        <div className="flex items-center justify-between pt-4 mt-4 border-t border-[var(--border)]">
          <div>
            <h3 className="font-semibold text-black">Email reminders (customers)</h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">Send overdue invoice reminder emails to customers</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={form.email_notifications === "true"}
              onChange={e => handleChange('email_notifications', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[var(--primary)]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)]"></div>
          </label>
        </div>

        {form.email_notifications === "true" && (
          <div className="mt-6 pt-6 border-t border-[var(--border)]">
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Overdue Reminder Interval</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                value={form.overdue_reminder_interval_days}
                onChange={e => handleChange('overdue_reminder_interval_days', e.target.value)}
                className="w-24 px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black"
              />
              <span className="text-sm text-[var(--text-muted)]">days between reminder emails per overdue customer</span>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between pt-4 mt-4 border-t border-[var(--border)]">
          <div>
            <h3 className="font-semibold text-black">Block overselling (prevent negative stock on sales)</h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">When on, a sale that would drive a stock product below zero is rejected with an error. When off, the sale is allowed and stock goes negative (warn-only).</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer ml-6 flex-shrink-0">
            <input
              type="checkbox"
              checked={form.block_negative_stock === "true"}
              onChange={e => handleChange('block_negative_stock', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[var(--primary)]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)]"></div>
          </label>
        </div>

        {([
          ["stock_reservation_enabled", "Stock reservations (ATP)", "Open pick/pack holds reduce available-to-promise and block oversell."],
          ["inventory_landed_cost_enabled", "Landed cost allocation", "Allocate freight/duty onto receipt layers (IAS 2)."],
          ["inventory_lot_tracking_enabled", "Lot / serial tracking", "Allow products to require lot or serial numbers on receipt and sale."],
          ["inventory_nrv_enabled", "NRV write-downs", "Run net realisable value valuations and post write-down journals."],
        ] as const).map(([key, title, hint]) => (
          <div key={key} className="flex items-center justify-between pt-4 mt-4 border-t border-[var(--border)]">
            <div>
              <h3 className="font-semibold text-black">{title}</h3>
              <p className="text-sm text-[var(--text-muted)] mt-1">{hint}</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer ml-6 flex-shrink-0">
              <input
                type="checkbox"
                checked={form[key] !== "false"}
                onChange={e => handleChange(key, e.target.checked ? "true" : "false")}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[var(--primary)]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)]"></div>
            </label>
          </div>
        ))}

        <p className="text-xs text-[var(--text-muted)] pt-2">
          Landed cost &amp; NRV tools:{" "}
          <a href="/inventory/valuation" className="underline text-[var(--primary)]">Inventory → Valuation</a>
        </p>

        { installedModules.has("purchase_store") && <div className="flex items-center justify-between pt-4 mt-4 border-t border-[var(--border)]">
          <div>
            <h3 className="font-semibold text-black">Require purchase chain (Demand → Comparative → PO)</h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">New purchase orders must come from an approved comparative statement</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer ml-6 flex-shrink-0">
            <input
              type="checkbox"
              checked={form.require_purchase_chain === "true"}
              onChange={e => handleChange('require_purchase_chain', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[var(--primary)]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)]"></div>
          </label>
        </div> }

        { installedModules.has("purchase_store") && <div className="flex items-center justify-between pt-4 mt-4 border-t border-[var(--border)]">
          <div>
            <h3 className="font-semibold text-black">Require gate inward before billing</h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">Purchase orders can only be billed once Gate Inward entries cover every line.</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer ml-6 flex-shrink-0">
            <input
              type="checkbox"
              checked={form.require_gate_inward === "true"}
              onChange={e => handleChange('require_gate_inward', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[var(--primary)]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)]"></div>
          </label>
        </div> }

        { installedModules.has("spinning") && <div className="pt-4 mt-4 border-t border-[var(--border)]">
          <h3 className="font-semibold text-black">Yarn Spinning</h3>
          <p className="text-sm text-[var(--text-muted)] mt-1 mb-3">
            Bale receipt posts to <code className="text-xs px-1 bg-[var(--bg-page)] rounded">1200</code>;
            stage entries move WIP across <code className="text-xs px-1 bg-[var(--bg-page)] rounded">1201</code>–
            <code className="text-xs px-1 bg-[var(--bg-page)] rounded">1203</code> and credit labour/overhead above;
            cone output transfers to <code className="text-xs px-1 bg-[var(--bg-page)] rounded">1204</code>;
            dispatch posts COGS via the COGS account. Waste types map to{" "}
            <code className="text-xs px-1 bg-[var(--bg-page)] rounded">5901</code>–
            <code className="text-xs px-1 bg-[var(--bg-page)] rounded">5904</code>.
          </p>
          <Link
            href="/spinning"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[#faf8f4]"
          >
            Open Spinning hub →
          </Link>
        </div> }

        { installedModules.has("textile_processing") && <div className="pt-4 mt-4 border-t border-[var(--border)]">
          <h3 className="font-semibold text-black">Textile Processing</h3>
          <p className="text-sm text-[var(--text-muted)] mt-1 mb-3">
            Ballor / jobber unit: customer-owned grey lots stay in custody (
            <code className="text-xs px-1 bg-[var(--bg-page)] rounded">1210</code> /
            <code className="text-xs px-1 bg-[var(--bg-page)] rounded">2150</code>).
            Process billing credits <code className="text-xs px-1 bg-[var(--bg-page)] rounded">4150</code>;
            wastage sales credit <code className="text-xs px-1 bg-[var(--bg-page)] rounded">4160</code>;
            contractor labor bills debit <code className="text-xs px-1 bg-[var(--bg-page)] rounded">5220</code>;
            shrinkage posts to <code className="text-xs px-1 bg-[var(--bg-page)] rounded">5215</code>.
            Flow: sales order → grey lot → mending → kachi/pakki parchi → PPC stages → fresh dispatch → grey settlement.
          </p>
          <Link
            href="/processing"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[#faf8f4]"
          >
            Open Processing hub →
          </Link>
        </div> }

        <div className="flex items-center justify-between pt-4 mt-4 border-t border-[var(--border)]">
          <div>
            <h3 className="font-semibold text-black">Block self-approval (segregation of duties)</h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">When on, the person who submitted a document for approval cannot approve or reject it. Default on.</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer ml-6 flex-shrink-0">
            <input
              type="checkbox"
              checked={(form.approvals_block_self_approval ?? "true") !== "false"}
              onChange={e => handleChange('approvals_block_self_approval', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[var(--primary)]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)]"></div>
          </label>
        </div>

        <div className="flex items-center justify-between pt-4 mt-4 border-t border-[var(--border)]">
          <div>
            <h3 className="font-semibold text-black">Require close checklist before lock</h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">Block Soft Close / Year-End Close / Lock until all required month-end tasks are marked done. Default on.</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer ml-6 flex-shrink-0">
            <input
              type="checkbox"
              checked={(form.period_close_require_checklist ?? "true") !== "false"}
              onChange={e => handleChange('period_close_require_checklist', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[var(--primary)]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)]"></div>
          </label>
        </div>

        <div className="flex items-center justify-between pt-4 mt-4 border-t border-[var(--border)]">
          <div>
            <h3 className="font-semibold text-black">IFRS 16 leases</h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Right-of-use assets, lease liability schedules, period posting, and maturity disclosure.{" "}
              <a href="/leases" className="underline text-[var(--primary)]">Open Leases</a>
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer ml-6 flex-shrink-0">
            <input
              type="checkbox"
              checked={(form.leases_enabled ?? "true") !== "false"}
              onChange={e => handleChange('leases_enabled', e.target.checked ? "true" : "false")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[var(--primary)]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)]"></div>
          </label>
        </div>

        <div className="pt-4 mt-4 border-t border-[var(--border)]">
          <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">Customer portal custom domain</label>
          <input
            type="text"
            value={form.portal_custom_domain ?? ""}
            onChange={e => handleChange('portal_custom_domain', e.target.value)}
            placeholder="portal.yourcompany.com or https://portal.yourcompany.com"
            className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black"
          />
          <p className="text-xs text-[var(--text-primary)]/50 mt-1">
            Optional. Used when minting portal magic links so customers land on your branded host (DNS/Caddy must point here).
          </p>
        </div>

        <div className="pt-4 mt-4 border-t border-[var(--border)]">
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Display Density</label>
          <select
            value={form.ui_density}
            onChange={e => handleChange('ui_density', e.target.value)}
            className="ui-field w-full bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]"
          >
            <option value="comfortable">Comfortable</option>
            <option value="compact">Compact</option>
          </select>
        </div>

        <div className="pt-4 mt-4 border-t border-[var(--border)]">
          <label className="block text-sm font-semibold text-[var(--text-primary)] mb-2">User Rights Module</label>
          <select
            value={form.user_rights_enabled ?? "false"}
            onChange={e => handleChange('user_rights_enabled', e.target.value)}
            className="w-full px-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-black bg-white"
          >
            <option value="false">Disabled — all users access all data (default)</option>
            <option value="true">Enabled — enforce per-user permission matrix</option>
          </select>
          <p className="text-xs text-[var(--text-primary)]/50 mt-1">
            When enabled, access to each module is controlled per-user via Settings → Permissions.
          </p>
        </div>
      </div>

      {/* ── PREFERENCES TAB ends, ACCOUNTING continues (Periods) ── */}
      </> }
      { tab === "accounting" && <>

      <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold flex items-center gap-3 text-black">
            <Lock className="w-5 h-5 text-[var(--primary)]" />
            Accounting Periods
          </h2>
          <button
            onClick={() => setAddingPeriod(v => !v)}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Period
          </button>
        </div>

        {addingPeriod && (
          <div className="mb-6 p-4 bg-[var(--bg-page)] rounded-xl grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Name (optional)</label>
              <input
                type="text"
                placeholder="e.g. Q1 2026"
                value={periodForm.name}
                onChange={e => setPeriodForm(p => ({ ...p, name: e.target.value }))}
                className="w-full px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Start Date</label>
              <input
                type="date"
                value={periodForm.period_start}
                onChange={e => setPeriodForm(p => ({ ...p, period_start: e.target.value }))}
                className="w-full px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">End Date</label>
              <input
                type="date"
                value={periodForm.period_end}
                onChange={e => setPeriodForm(p => ({ ...p, period_end: e.target.value }))}
                className="w-full px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
              />
            </div>
            <button
              onClick={handleAddPeriod}
              className="px-4 py-2 bg-[var(--text-primary)] text-white rounded-lg text-sm font-bold hover:bg-[var(--primary)] transition-colors"
            >
              Create
            </button>
          </div>
        )}

        {periods.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)] py-4">No accounting periods defined. Add one to enable period locking.</p>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {periods.map(period => (
              <div key={period.id} className="flex items-center justify-between py-3">
                <div>
                  <span className="font-medium text-black">{period.name || `${period.period_start} — ${period.period_end}`}</span>
                  {period.name && <span className="ml-2 text-sm text-[var(--text-muted)]">{period.period_start} — {period.period_end}</span>}
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${period.is_locked ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    {period.is_locked ? 'Locked' : 'Open'}
                  </span>
                  <button
                    onClick={() => handleToggleLock(period)}
                    className="p-2 hover:bg-[var(--bg-page)] rounded-lg transition-colors"
                    title={period.is_locked ? "Unlock period" : "Lock period"}
                  >
                    {period.is_locked ? <Unlock className="w-4 h-4 text-[var(--primary)]" /> : <Lock className="w-4 h-4 text-[var(--text-primary)]/60" />}
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

      </> }
      { tab === "advanced" && <>

      {/* Backup & Restore (local / on-premise installs) */}
      <div className="bg-white border border-[var(--border)] rounded-2xl p-6 space-y-3">
        <h2 className="text-lg font-bold text-[var(--text-primary)]">Backup &amp; Restore</h2>
        <p className="text-xs text-[var(--text-primary)]/60">
          Download a full copy of your data (database + uploads), or restore from a backup.
          Available on on-premise (SQLite) installs.
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={async () => {
              const base = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
              const res = await fetch(`${base}/api/backup/download`, {
                headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
              })
              if (!res.ok) { toast("Backup is only available on local SQLite installs.", "error"); return }
              const blob = await res.blob()
              const url = URL.createObjectURL(blob)
              const a = document.createElement("a")
              a.href = url; a.download = "easybooks-backup.zip"; a.click()
              URL.revokeObjectURL(url)
            }}
            className="px-4 py-2 bg-[var(--text-primary)] text-white rounded-xl text-sm font-bold hover:bg-[var(--primary)] hover:text-black transition-all"
          >
            Download Backup
          </button>
          <label className="px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold cursor-pointer hover:bg-[var(--bg-page)]">
            Restore from Backup…
            <input
              type="file"
              accept=".zip"
              className="hidden"
              onChange={async (e) => {
                const f = e.target.files?.[0]; if (!f) return
                const ok = await confirm({
                  title: "Restore from backup?",
                  message: "Restore will overwrite current data.",
                  confirmLabel: "Restore",
                  danger: true,
                })
                if (!ok) return
                const base = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
                const fd = new FormData(); fd.append("file", f)
                const res = await fetch(`${base}/api/backup/restore`, {
                  method: "POST",
                  headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
                  body: fd,
                })
                toast(res.ok
                  ? "Restored. Restart the app to load the restored data."
                  : "Restore failed — check the file is a valid Easy-Books backup.",
                  res.ok ? "success" : "error")
              }}
            />
          </label>
        </div>
      </div>

      {/* Capabilities — Add-ons (replaces pre-login business-model picker) */}
      <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-2 flex items-center gap-3 text-black">
          <Layers className="w-5 h-5 text-[var(--primary)]" />
          Industry capabilities
        </h2>
        <p className="text-sm text-[var(--text-muted)] mb-4">
          Every company starts with Base Accounting. Inventory, Manufacturing, Yarn Spinning,
          Textile Processing, Healthcare, Telecom, PRA, and more are installed from{" "}
          <strong>System → Add-ons</strong> — not by switching a business model here.
          Industry packs unlock the <strong>Operations</strong> home dashboard alongside Financial.
        </p>
        <Link
          href="/apps"
          className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
        >
          Open Add-ons
        </Link>
      </div>

      {isAdminOrOwner && (
      <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm">
        <h2 className="text-xl font-semibold mb-2 flex items-center gap-3 text-black">
          <PenTool className="w-5 h-5 text-[var(--primary)]" />
          Studio
        </h2>
        <p className="text-sm text-[var(--text-muted)] mb-4">
          Extra fields, form layout, and print templates for invoices, bills, customers,
          products, and vendors. Marketplace listings (for example mill Weighbridge) can
          apply a bundle here; you can still edit the overlay. Values never post to the GL.
        </p>
        <Link
          href="/settings/studio"
          className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
        >
          Open Studio
        </Link>
      </div>
      )}

      {/* Dual-home dashboard preference (browser-local, mirrors /dashboard toggle) */}
      <HomeDashboardSettingsCard opsAvailable={hasOperationsHome(installedModules)} praInstalled={installedModules.has("pra")} />

      {/* ── Textile Processing — ops CoA cheat-sheet once the pack is installed ── */}
      {installedModules.has("textile_processing") && (
      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-[var(--text-primary)]">
              Textile Processing{" "}
              <span className="text-sm font-sans font-normal text-[var(--text-primary)]/50">
                (ballor / jobber printing unit)
              </span>
            </h2>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Customer-owned grey fabric is tracked as custody stock — it never hits your inventory
              valuation. Process charges, wastage sales, contractor labor, and shrinkage post to
              dedicated CoA leaves seeded with the pack.
            </p>
          </div>
          <Link
            href="/processing"
            className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--primary)] text-white text-sm font-medium hover:bg-[var(--primary-dark)]"
          >
            Open hub →
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
          {[
            { code: "1210", name: "Customer Goods on Hand", role: "Memo asset — grey on floor" },
            { code: "2150", name: "Customer Goods Liability", role: "Memo liability — owed back" },
            { code: "4150", name: "Processing Revenue", role: "Process / PPC billing" },
            { code: "4160", name: "Wastage Sales Revenue", role: "Sold process waste" },
            { code: "5220", name: "Contractor Labor Expense", role: "Labor bills / jobbers" },
            { code: "5215", name: "Process Shrinkage Expense", role: "Shrinkage write-off" },
          ].map(row => (
            <div key={row.code} className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2">
              <div className="font-mono text-xs font-bold text-[var(--primary)]">{row.code}</div>
              <div className="font-semibold text-[var(--text-primary)]">{row.name}</div>
              <div className="text-xs text-[var(--text-muted)]">{row.role}</div>
            </div>
          ))}
        </div>
        <p className="text-xs text-[var(--text-muted)]">
          Typical flow: Sales Order → Grey Lot → Mending → Kachi / Pakki Parchi → PPC Stages →
          Fresh Dispatch → Labor Bills → Grey Settlement. Demo login:{" "}
          <code className="px-1 bg-[var(--bg-page)] rounded border border-[var(--border)]">
            demo.processing@easy-books.app
          </code>{" "}
          / <code className="px-1 bg-[var(--bg-page)] rounded border border-[var(--border)]">demo1234</code>
        </p>
      </section>
      )}

      {/* ── PRA e-Invoice (Pakistan) — compliance switch once the PRA add-on is installed ── */}
      {installedModules.has("pra") && (
      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">PRA e-Invoice <span className="text-sm font-sans font-normal text-[var(--text-primary)]/50">(Punjab Revenue Authority, Pakistan)</span></h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-[var(--text-primary)]/70">{form.pra_enabled === "true" ? "Enabled" : "Disabled"}</span>
            <div
              onClick={() => handleChange("pra_enabled", form.pra_enabled === "true" ? "false" : "true")}
              className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${form.pra_enabled === "true" ? "bg-[var(--primary)]" : "bg-[var(--text-primary)]/20"}`}
            >
              <div className={`w-4 h-4 bg-white rounded-full mt-0.5 shadow transition-transform ${form.pra_enabled === "true" ? "translate-x-5" : "translate-x-0.5"}`} />
            </div>
          </label>
        </div>
        <p className="text-xs text-[var(--text-primary)]/50">
          When enabled, every new sales invoice is submitted to PRA eIMS in real-time and a Fiscal Invoice Number (FIN) is printed on the invoice.
          Register at <span className="font-mono">reg.pra.punjab.gov.pk</span> to obtain your POS ID and production token.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">PNTN / NTN</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. 1234567-8"
              autoComplete="off"
              value={form.pra_ntn} onChange={e => handleChange("pra_ntn", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">POS ID</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              placeholder="6-digit POS ID from PRA portal"
              autoComplete="off"
              value={form.pra_pos_id} onChange={e => handleChange("pra_pos_id", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Production API Token</label>
            <div className="flex gap-2">
              <input className="flex-1 border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-mono"
                type={praShowToken ? "text" : "password"}
                placeholder="Bearer token from POS Details tab"
                autoComplete="new-password"
                value={form.pra_api_token} onChange={e => handleChange("pra_api_token", e.target.value)} />
              <button type="button" onClick={() => setPraShowToken(v => !v)}
                className="px-3 py-2 border border-[var(--border)] rounded-lg text-xs text-[var(--text-primary)]/60 hover:border-[var(--primary)]/40">
                {praShowToken ? "Hide" : "Show"}
              </button>
            </div>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" className="rounded border-[var(--border)]"
            checked={form.pra_sandbox_mode === "true"}
            onChange={e => handleChange("pra_sandbox_mode", e.target.checked ? "true" : "false")} />
          <span className="text-[var(--text-primary)]/70">Use Sandbox (test) environment</span>
          <span className="text-xs text-[var(--text-primary)]/40 font-mono">ims.pral.com.pk/ims/sandbox/…</span>
        </label>
        <div className="flex items-center gap-3">
          <button
            onClick={async () => {
              setPraTesting(true); setPraTestResult(null)
              try {
                const r = await apiFetch<{ pra_code: string; pra_response: string; sandbox: boolean }>("/api/pra/test", { method: "POST" })
                const ok = r.pra_code === "100"
                setPraTestResult({ ok, msg: `Code ${r.pra_code}: ${r.pra_response}${r.sandbox ? " (sandbox)" : " (production)"}` })
              } catch (e: unknown) {
                setPraTestResult({ ok: false, msg: String((e as Error).message ?? e) })
              } finally { setPraTesting(false) }
            }}
            disabled={praTesting || !form.pra_pos_id}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--text-primary)] text-white hover:bg-[var(--text-primary)]/80 disabled:opacity-50 transition-colors"
          >
            {praTesting ? "Testing…" : "Test Connection"}
          </button>
          {praTestResult && (
            <span className={`text-sm ${praTestResult.ok ? "text-green-700" : "text-red-600"}`}>
              {praTestResult.ok ? "✓" : "✗"} {praTestResult.msg}
            </span>
          )}
        </div>
      </section>
      )}

      {/* ── UAE VAT e-Invoice — compliance switch once the UAE add-on is installed ── */}
      {installedModules.has("uae_vat") && (
      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">UAE VAT e-Invoice <span className="text-sm font-sans font-normal text-[var(--text-primary)]/50">(Federal Tax Authority)</span></h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-[var(--text-primary)]/70">{form.uae_vat_enabled === "true" ? "Enabled" : "Disabled"}</span>
            <div
              onClick={() => handleChange("uae_vat_enabled", form.uae_vat_enabled === "true" ? "false" : "true")}
              className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${form.uae_vat_enabled === "true" ? "bg-[var(--primary)]" : "bg-[var(--text-primary)]/20"}`}
            >
              <div className={`w-4 h-4 bg-white rounded-full mt-0.5 shadow transition-transform ${form.uae_vat_enabled === "true" ? "translate-x-5" : "translate-x-0.5"}`} />
            </div>
          </label>
        </div>
        <p className="text-xs text-[var(--text-primary)]/50">
          Installs UAE 5% VAT tax codes and VAT Payable/Receivable CoA leaves. Sandbox mode mints a synthetic FTA UUID without a live call; production Peppol wiring is reserved for a follow-up.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Tax Registration Number (TRN)</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              placeholder="15-digit TRN"
              autoComplete="off"
              value={form.uae_trn} onChange={e => handleChange("uae_trn", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Legal name</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              placeholder="Registered company name"
              autoComplete="off"
              value={form.uae_legal_name} onChange={e => handleChange("uae_legal_name", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">API key (future live connector)</label>
            <div className="flex gap-2">
              <input className="flex-1 border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-mono"
                type={uaeShowKey ? "text" : "password"}
                placeholder="Write-only — leave blank for sandbox stub"
                autoComplete="new-password"
                value={form.uae_api_key} onChange={e => handleChange("uae_api_key", e.target.value)} />
              <button type="button" onClick={() => setUaeShowKey(v => !v)}
                className="px-3 py-2 border border-[var(--border)] rounded-lg text-xs text-[var(--text-primary)]/60 hover:border-[var(--primary)]/40">
                {uaeShowKey ? "Hide" : "Show"}
              </button>
            </div>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" className="rounded border-[var(--border)]"
            checked={form.uae_sandbox_mode === "true"}
            onChange={e => handleChange("uae_sandbox_mode", e.target.checked ? "true" : "false")} />
          <span className="text-[var(--text-primary)]/70">Use Sandbox stub</span>
        </label>
        <div className="flex items-center gap-3">
          <button
            onClick={async () => {
              setUaeTesting(true); setUaeTestResult(null)
              try {
                const r = await apiFetch<{ ok: boolean; message: string; sandbox: boolean }>("/api/uae/test", { method: "POST" })
                setUaeTestResult({ ok: !!r.ok, msg: `${r.message}${r.sandbox ? " (sandbox)" : ""}` })
              } catch (e: unknown) {
                setUaeTestResult({ ok: false, msg: String((e as Error).message ?? e) })
              } finally { setUaeTesting(false) }
            }}
            disabled={uaeTesting || !form.uae_trn}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--text-primary)] text-white hover:bg-[var(--text-primary)]/80 disabled:opacity-50 transition-colors"
          >
            {uaeTesting ? "Testing…" : "Test Connection"}
          </button>
          {uaeTestResult && (
            <span className={`text-sm ${uaeTestResult.ok ? "text-green-700" : "text-red-600"}`}>
              {uaeTestResult.ok ? "✓" : "✗"} {uaeTestResult.msg}
            </span>
          )}
        </div>
      </section>
      )}

      {/* ── Saudi ZATCA e-Invoice — once the sa_zatca add-on is installed ── */}
      {installedModules.has("sa_zatca") && (
      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">Saudi ZATCA e-Invoice <span className="text-sm font-sans font-normal text-[var(--text-primary)]/50">(Fatoora Phase 2)</span></h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-[var(--text-primary)]/70">{form.zatca_enabled === "true" ? "Enabled" : "Disabled"}</span>
            <div
              onClick={() => handleChange("zatca_enabled", form.zatca_enabled === "true" ? "false" : "true")}
              className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${form.zatca_enabled === "true" ? "bg-[var(--primary)]" : "bg-[var(--text-primary)]/20"}`}
            >
              <div className={`w-4 h-4 bg-white rounded-full mt-0.5 shadow transition-transform ${form.zatca_enabled === "true" ? "translate-x-5" : "translate-x-0.5"}`} />
            </div>
          </label>
        </div>
        <p className="text-xs text-[var(--text-primary)]/50">
          Sandbox clear/report against the ZATCA developer portal. Configure your VAT number and (optionally) CSID token.
          Submission logs are under <Link href="/zatca/logs" className="underline text-[var(--text-link)]">ZATCA Logs</Link>.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">VAT Registration Number</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              placeholder="15-digit VAT"
              autoComplete="off"
              value={form.zatca_vat_number} onChange={e => handleChange("zatca_vat_number", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Commercial Registration (CR)</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              placeholder="CR number"
              autoComplete="off"
              value={form.zatca_cr_number} onChange={e => handleChange("zatca_cr_number", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Device / EGS ID</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              placeholder="EGS1-…"
              autoComplete="off"
              value={form.zatca_device_id} onChange={e => handleChange("zatca_device_id", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">CSID token (write-only)</label>
            <div className="flex gap-2">
              <input className="flex-1 border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-mono"
                type={zatcaShowToken ? "text" : "password"}
                placeholder="Basic auth token from Fatoora"
                autoComplete="new-password"
                value={form.zatca_csid_token} onChange={e => handleChange("zatca_csid_token", e.target.value)} />
              <button type="button" onClick={() => setZatcaShowToken(v => !v)}
                className="px-3 py-2 border border-[var(--border)] rounded-lg text-xs text-[var(--text-primary)]/60 hover:border-[var(--primary)]/40">
                {zatcaShowToken ? "Hide" : "Show"}
              </button>
            </div>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" className="rounded border-[var(--border)]"
            checked={form.zatca_sandbox_mode !== "false"}
            onChange={e => handleChange("zatca_sandbox_mode", e.target.checked ? "true" : "false")} />
          <span className="text-[var(--text-primary)]/70">Use Sandbox (developer portal)</span>
        </label>
        <div className="flex items-center gap-3">
          <button
            onClick={async () => {
              setZatcaTesting(true); setZatcaTestResult(null)
              try {
                const r = await apiFetch<{ ok: boolean; message: string; sandbox: boolean }>("/api/zatca/test", { method: "POST" })
                setZatcaTestResult({ ok: !!r.ok, msg: `${r.message}${r.sandbox ? " (sandbox)" : ""}` })
              } catch (e: unknown) {
                setZatcaTestResult({ ok: false, msg: String((e as Error).message ?? e) })
              } finally { setZatcaTesting(false) }
            }}
            disabled={zatcaTesting || !form.zatca_vat_number}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--text-primary)] text-white hover:bg-[var(--text-primary)]/80 disabled:opacity-50 transition-colors"
          >
            {zatcaTesting ? "Testing…" : "Test Connection"}
          </button>
          {zatcaTestResult && (
            <span className={`text-sm ${zatcaTestResult.ok ? "text-green-700" : "text-red-600"}`}>
              {zatcaTestResult.ok ? "✓" : "✗"} {zatcaTestResult.msg}
            </span>
          )}
        </div>
      </section>
      )}

      {/* ── India GST — once the in_gst add-on is installed ── */}
      {installedModules.has("in_gst") && (
      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">India GST <span className="text-sm font-sans font-normal text-[var(--text-primary)]/50">(CGST / SGST / IGST)</span></h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-[var(--text-primary)]/70">{form.in_gst_enabled !== "false" ? "Enabled" : "Disabled"}</span>
            <div
              onClick={() => handleChange("in_gst_enabled", form.in_gst_enabled === "false" ? "true" : "false")}
              className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${form.in_gst_enabled !== "false" ? "bg-[var(--primary)]" : "bg-[var(--text-primary)]/20"}`}
            >
              <div className={`w-4 h-4 bg-white rounded-full mt-0.5 shadow transition-transform ${form.in_gst_enabled !== "false" ? "translate-x-5" : "translate-x-0.5"}`} />
            </div>
          </label>
        </div>
        <p className="text-xs text-[var(--text-primary)]/50">
          Seeds CGST 9% / SGST 9% / IGST 18% tax codes. Place of supply compares your state code with the customer&apos;s.
          GSTR summaries are under <Link href="/india-gst/gstr" className="underline text-[var(--text-link)]">GSTR Report</Link>.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">GSTIN</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="15-character GSTIN"
              autoComplete="off"
              value={form.in_gstin} onChange={e => handleChange("in_gstin", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">State code (seller)</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="e.g. 27"
              maxLength={2}
              autoComplete="off"
              value={form.in_state_code} onChange={e => handleChange("in_state_code", e.target.value)} />
          </div>
        </div>
      </section>
      )}

      {/* ── Peppol / EU VAT e-Invoice — once the eu_peppol add-on is installed ── */}
      {installedModules.has("eu_peppol") && (
      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">Peppol / EU VAT e-Invoice <span className="text-sm font-sans font-normal text-[var(--text-primary)]/50">(BIS Billing 3.0)</span></h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-[var(--text-primary)]/70">{form.peppol_enabled === "true" ? "Enabled" : "Disabled"}</span>
            <div
              onClick={() => handleChange("peppol_enabled", form.peppol_enabled === "true" ? "false" : "true")}
              className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${form.peppol_enabled === "true" ? "bg-[var(--primary)]" : "bg-[var(--text-primary)]/20"}`}
            >
              <div className={`w-4 h-4 bg-white rounded-full mt-0.5 shadow transition-transform ${form.peppol_enabled === "true" ? "translate-x-5" : "translate-x-0.5"}`} />
            </div>
          </label>
        </div>
        <p className="text-xs text-[var(--text-primary)]/50">
          Export Peppol BIS Billing 3.0 UBL and submit via your Access Point (AP) sandbox or production URL.
          See <Link href="/guide#28b-peppol--eu-vat-e-invoice" className="underline text-[var(--text-link)]">AP credentials setup</Link>.
          Submission logs are under <Link href="/peppol/logs" className="underline text-[var(--text-link)]">Peppol Logs</Link>.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Participant ID</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="0088:1234567890123 or 9930:DE123456789"
              autoComplete="off"
              value={form.peppol_participant_id} onChange={e => handleChange("peppol_participant_id", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Access Point URL</label>
            <input className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="https://ap.example.com/v1/send"
              autoComplete="off"
              value={form.peppol_ap_url} onChange={e => handleChange("peppol_ap_url", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">AP API key (write-only)</label>
            <div className="flex gap-2">
              <input className="flex-1 border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-mono"
                type={peppolShowKey ? "text" : "password"}
                placeholder="Bearer token from your Access Point"
                autoComplete="new-password"
                value={form.peppol_api_key} onChange={e => handleChange("peppol_api_key", e.target.value)} />
              <button type="button" onClick={() => setPeppolShowKey(v => !v)}
                className="px-3 py-2 border border-[var(--border)] rounded-lg text-xs text-[var(--text-primary)]/60 hover:border-[var(--primary)]/40">
                {peppolShowKey ? "Hide" : "Show"}
              </button>
            </div>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" className="rounded border-[var(--border)]"
            checked={form.peppol_sandbox_mode !== "false"}
            onChange={e => handleChange("peppol_sandbox_mode", e.target.checked ? "true" : "false")} />
          <span className="text-[var(--text-primary)]/70">Use Sandbox Access Point</span>
        </label>
        <div className="flex items-center gap-3">
          <button
            onClick={async () => {
              setPeppolTesting(true); setPeppolTestResult(null)
              try {
                const r = await apiFetch<{ ok: boolean; message: string; sandbox: boolean }>("/api/peppol/test", { method: "POST" })
                setPeppolTestResult({ ok: !!r.ok, msg: `${r.message}${r.sandbox ? " (sandbox)" : ""}` })
              } catch (e: unknown) {
                setPeppolTestResult({ ok: false, msg: String((e as Error).message ?? e) })
              } finally { setPeppolTesting(false) }
            }}
            disabled={peppolTesting || !form.peppol_participant_id || !form.peppol_ap_url}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--text-primary)] text-white hover:bg-[var(--text-primary)]/80 disabled:opacity-50 transition-colors"
          >
            {peppolTesting ? "Testing…" : "Test Connection"}
          </button>
          {peppolTestResult && (
            <span className={`text-sm ${peppolTestResult.ok ? "text-green-700" : "text-red-600"}`}>
              {peppolTestResult.ok ? "✓" : "✗"} {peppolTestResult.msg}
            </span>
          )}
        </div>
      </section>
      )}

      {/* ── Appearance ── */}
      <AppearanceSection />

      {/* Sample / Demo Data (evaluation) — admin/owner */}
      {isAdminOrOwner && <DemoSampleDataSection />}

      {/* AI Assistant (#117) — provider keys, default model, rate limit */}
      { installedModules.has("ai_assistant") &&
        (getCurrentUser()?.role === "admin" || getCurrentUser()?.role === "owner") &&
        <AiAssistantSection /> }

      {/* WhatsApp Meta Cloud API (#237) — lab publish auto-send */}
      {(getCurrentUser()?.role === "admin" || getCurrentUser()?.role === "owner") &&
        <WhatsAppMetaSection /> }

      {/* Webhooks (#114) — outgoing event notifications */}
      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-3">
        <h2 className="text-lg font-bold text-[var(--text-primary)]">Webhooks</h2>
        <p className="text-sm text-[var(--text-primary)]/60">
          Push signed HTTP notifications (invoices, payments, stock alerts and more) to Zapier, Make,
          Slack, or your own systems the moment they happen.
        </p>
        <Link
          href="/settings/webhooks"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[#faf8f4]"
        >
          Manage webhook endpoints →
        </Link>
        <Link
          href="/settings/ops"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[#faf8f4] ml-2"
        >
          Queue DLQ & metrics →
        </Link>
      </section>

      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-3">
        <h2 className="text-lg font-bold text-[var(--text-primary)]">Billing</h2>
        <p className="text-sm text-[var(--text-primary)]/60">
          Plan limits, usage meters, and upgrades.
        </p>
        <Link
          href="/settings/billing"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[#faf8f4]"
        >
          Open billing →
        </Link>
      </section>

      <Security2FACard />

      </> }

      {/* API Keys tab (#113) — machine-to-machine access, admin/owner only
          (the tab itself is hidden for other roles) */}
      { tab === "api-keys" && isAdminOrOwner && <ApiKeysSection /> }

      {/* Updates tab */}
      { tab === "updates" && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm space-y-6">
            <h2 className="text-xl font-semibold flex items-center gap-3 text-black">
              <RefreshCw className="w-5 h-5 text-[var(--primary)]" />
              Software Updates
            </h2>
            <p className="text-sm text-[var(--text-muted)]">
              Keep Easy-Books up to date to get the latest features, bug fixes, and security improvements.
            </p>

            <div className="flex items-center justify-between p-4 bg-[var(--bg-page)] rounded-xl border border-[var(--border)]">
              <div>
                <p className="text-sm font-semibold text-[var(--text-primary)]">Installed Version</p>
                <div className="mt-1"><VersionBadge /></div>
              </div>
              <button
                onClick={() => setUpdateModalOpen(true)}
                className="flex items-center gap-2 px-5 py-2.5 bg-[var(--primary)] text-white rounded-lg font-medium hover:bg-[var(--primary-dark)] transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Check for Updates
              </button>
            </div>

            <div className="text-xs text-[var(--text-muted)] space-y-1">
              <p>• On <strong>script installs</strong> (install-and-run.sh / .ps1): Easy-Books pulls the latest code and rebuilds automatically.</p>
              <p>• On <strong>desktop (Electron)</strong>: the update downloads and installs in the background — you&apos;ll be prompted to restart.</p>
              <p>• On <strong>cloud / server</strong>: run <code className="px-1 bg-[var(--bg-page)] rounded text-[var(--text-primary)]">git pull && ./install-and-run.sh</code> on your server.</p>
            </div>
          </div>
        </div>
      )}

      {/* Save / Reset — only on tabs with form fields */}
      { FORM_TABS.has(tab) && (
        <div className="flex justify-end gap-3 pt-2">
          <button
            onClick={() => setForm(ctxSettings)}
            className="px-6 py-2 border border-[var(--border)] rounded-lg hover:bg-[var(--bg-page)] text-black font-medium transition-colors"
          >
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2 bg-[var(--primary)] text-white rounded-lg hover:bg-[var(--primary-dark)] font-medium transition-colors disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      )}

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
          ? "border-[var(--primary)] bg-[var(--bg-page)] text-[var(--primary)]"
          : "border-[var(--border)] bg-white text-[var(--text-primary)]/60 hover:border-[var(--primary)]/40"
      }`}
    >
      <Icon className="w-5 h-5" />
      {label}
    </button>
  )

  return (
    <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-5">
      <h2 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
        <Palette className="w-4 h-4 text-[var(--primary)]" /> Appearance
      </h2>

      {/* Light / Dark / System */}
      <div>
        <p className="text-xs font-semibold text-[var(--text-primary)]/55 uppercase tracking-wide mb-3">Display Mode</p>
        <div className="flex gap-3 flex-wrap">
          {modeBtn("light",  Sun,     "Light")}
          {modeBtn("dark",   Moon,    "Dark")}
          {modeBtn("system", Monitor, "System")}
        </div>
      </div>

      {/* Color theme swatches */}
      <div>
        <p className="text-xs font-semibold text-[var(--text-primary)]/55 uppercase tracking-wide mb-3">Color Theme</p>
        <div className="flex gap-3 flex-wrap">
          {COLOR_OPTIONS.map(({ id, label, accent }) => (
            <button
              key={id}
              onClick={() => setColorTheme(id)}
              title={label}
              className={`group flex flex-col items-center gap-1.5 px-3 py-2.5 rounded-xl border-2 transition-all ${
                colorTheme === id
                  ? "border-2 shadow-sm"
                  : "border-[var(--border)] hover:border-current"
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
              <span className="text-[10px] font-semibold text-[var(--text-primary)]/60 whitespace-nowrap">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Language */}
      <div>
        <p className="text-xs font-semibold text-[var(--text-primary)]/55 uppercase tracking-wide mb-3">Display Language</p>
        <div className="flex gap-3 flex-wrap">
          {LANGUAGES.map(lang => (
            <button
              key={lang.code}
              onClick={() => setLanguage(lang.code as Language)}
              className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl border-2 text-sm font-medium transition-all ${
                language === lang.code
                  ? "border-[var(--primary)] bg-[var(--bg-page)] text-[var(--primary)]"
                  : "border-[var(--border)] bg-white text-[var(--text-primary)]/60 hover:border-[var(--primary)]/40"
              }`}
            >
              <span className="text-lg leading-none">
                {lang.code === "en" ? "🇬🇧" : lang.code === "ur" ? "🇵🇰" : "🇨🇳"}
              </span>
              <span>{lang.nativeLabel}</span>
              <span className="text-xs text-[var(--text-primary)]/40">({lang.label})</span>
            </button>
          ))}
        </div>
        <p className="text-[11px] text-[var(--text-primary)]/40 mt-2">
          Urdu enables right-to-left (RTL) layout with Nastaliq script.
        </p>
      </div>

      <p className="text-[11px] text-[var(--text-primary)]/40">
        Appearance preferences are saved per account and synced across sessions.
      </p>
    </section>
  )
}

/* ── Sample / Demo Data — sequential per-tenant seed (Vercel-safe) ── */

type DemoStatusRow = {
  email: string
  company: string
  business_model: string
  exists: boolean
  loaded: boolean
  tenant_id: number | null
}

/** Fixed catalog order — always render these rows even if /demo/status is older or missing.
 *  Light tenants first so cloud Load succeeds early if a later specialty pack times out. */
const DEMO_CATALOG: { email: string; screen: string }[] = [
  { email: "demo.simple@easy-books.app", screen: "Simple books (shared AR/AP baseline)" },
  { email: "demo.services@easy-books.app", screen: "Services + deferred revenue" },
  { email: "demo.trader@easy-books.app", screen: "Trader + inventory" },
  { email: "demo.pra@easy-books.app", screen: "PRA Logs" },
  { email: "demo.telecom@easy-books.app", screen: "Telecom — Mobile Money, Devices, Postpaid" },
  { email: "demo.manufacturing@easy-books.app", screen: "Store Issues, Purchases chain, Weaving" },
  { email: "demo.hospital@easy-books.app", screen: "HC Store (Healthcare pharmacy)" },
  { email: "demo.processing@easy-books.app", screen: "Textile Processing — grey lots, mending, kachi/pakki, PPC, dispatch, settlements" },
  { email: "demo.spinning@easy-books.app", screen: "Spinning — setup, lots, bale receipt, all 6 stages, cones, dispatch, reports" },
]

function DemoSampleDataSection() {
  const { confirm, toast } = useMessages()
  const [rows, setRows] = useState<DemoStatusRow[]>([])
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)

  const refresh = async () => {
    setLoadingStatus(true)
    try {
      const data = await apiFetch<{ tenants: DemoStatusRow[] }>("/api/admin/demo/status")
      setRows(data.tenants)
    } catch {
      setRows([])
    } finally {
      setLoadingStatus(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const loadAll = async () => {
    if (busy) return
    setBusy(true)
    try {
      // Prefer DEMO_CATALOG order (light → heavy) so cloud Load succeeds early.
      // Append any status-only emails the catalog does not list yet.
      let statusEmails: string[] = rows.map(r => r.email)
      if (statusEmails.length === 0) {
        try {
          const data = await apiFetch<{ tenants: DemoStatusRow[] }>("/api/admin/demo/status")
          statusEmails = data.tenants.map(t => t.email)
          setRows(data.tenants)
        } catch {
          statusEmails = []
        }
      }
      const emails = DEMO_CATALOG.map(c => c.email)
      for (const email of statusEmails) {
        if (!emails.some(e => e.toLowerCase() === email.toLowerCase())) {
          emails.push(email)
        }
      }

      const total = emails.length
      for (let i = 0; i < total; i++) {
        const email = emails[i]
        setProgress(`Seeding ${i + 1}/${total} — ${email}`)
        let lastErr: Error | null = null
        // Idempotent seeder: on cloud timeouts, retry a few times so a
        // partially-written tenant can finish on warm invocations.
        for (let attempt = 1; attempt <= 3; attempt++) {
          try {
            if (attempt > 1) {
              setProgress(`Seeding ${i + 1}/${total} — ${email} (retry ${attempt}/3)`)
            }
            await apiFetch("/api/admin/demo/seed", {
              method: "POST",
              body: JSON.stringify({ email }),
            })
            lastErr = null
            break
          } catch (err) {
            lastErr = err as Error
            const msg = lastErr.message || ""
            const retryable =
              /timeout|timed out|can't reach the api|failed to fetch|HTTP 504|HTTP 503|HTTP 500/i.test(
                msg,
              )
            if (!retryable || attempt === 3) break
            await new Promise(r => setTimeout(r, 1500 * attempt))
          }
        }
        if (lastErr) {
          toast(
            `Failed on ${email}: ${lastErr.message}. Earlier companies may already be loaded — retry to continue.`,
            "error",
          )
          await refresh()
          return
        }
      }
      setProgress(null)
      await refresh()
      toast("QA demo companies loaded. They remain separate from your company.", "success")
    } catch (err) {
      toast((err as Error).message || "Could not load demo data (admin only).", "error")
    } finally {
      setBusy(false)
      setProgress(null)
    }
  }

  const removeAll = async () => {
    const ok = await confirm({
      title: "Remove demo companies?",
      message: "Remove all QA demo companies and their data? Your own company is not affected.",
      confirmLabel: "Remove",
      danger: true,
    })
    if (!ok) return
    setBusy(true)
    try {
      await apiFetch("/api/admin/demo/seed", { method: "DELETE" })
      await refresh()
      toast("Demo companies removed.", "success")
    } catch (err) {
      toast((err as Error).message || "Could not remove demo data (admin only).", "error")
    } finally {
      setBusy(false)
    }
  }

  const statusByEmail = new Map(rows.map(r => [r.email.toLowerCase(), r]))
  const displayRows = DEMO_CATALOG.map(item => {
    const st = statusByEmail.get(item.email.toLowerCase())
    return {
      email: item.email,
      screen: item.screen,
      exists: st?.exists ?? false,
      loaded: st?.loaded ?? false,
    }
  })
  // Surface any extra demo tenants the API returns that aren't in the catalog yet
  for (const st of rows) {
    if (DEMO_CATALOG.some(c => c.email.toLowerCase() === st.email.toLowerCase())) continue
    displayRows.push({
      email: st.email,
      screen: st.company || st.email,
      exists: st.exists,
      loaded: st.loaded,
    })
  }

  return (
    <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-3">
      <h2 className="text-lg font-bold text-[var(--text-primary)]">Sample / Demo Data</h2>
      <p className="text-sm text-[var(--text-primary)]/60">
        Load or remove the <strong>QA demo companies</strong> (separate tenants used for regression testing).
        Each company is seeded one-at-a-time so cloud deploys do not time out.
        Password for all:{" "}
        <code className="mx-1 px-1 bg-[var(--bg-page)] rounded">demo1234</code>
        — install industry packs from{" "}
        <Link href="/apps" className="text-[var(--primary)] underline">Add-ons</Link>
        {" "}with optional sample data. Your own company is never affected.
      </p>
      <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] overflow-hidden">
        <div className="px-3 py-2 border-b border-[var(--border)]">
          <p className="text-sm font-semibold text-[var(--text-primary)]">How to see specialty demo data</p>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            After Load, log out and sign in with the matching company below.
            {loadingStatus ? " Checking status…" : null}
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-[var(--text-muted)]">
                <th className="px-3 py-2 font-semibold">Screen / area</th>
                <th className="px-3 py-2 font-semibold">Login</th>
                <th className="px-3 py-2 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="text-[var(--text-primary)]">
              {displayRows.map(row => {
                const statusLabel = row.loaded ? "Loaded" : row.exists ? "Empty" : "Missing"
                const statusClass = row.loaded
                  ? "text-green-700 bg-green-50 border-green-200"
                  : row.exists
                    ? "text-amber-800 bg-amber-50 border-amber-200"
                    : "text-[var(--text-muted)] bg-white border-[var(--border)]"
                return (
                  <tr key={row.email} className="border-t border-[var(--border)]">
                    <td className="px-3 py-2 align-top">{row.screen}</td>
                    <td className="px-3 py-2 align-top">
                      <code className="text-xs px-1.5 py-0.5 bg-white rounded border border-[var(--border)] break-all">
                        {row.email}
                      </code>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <span className={`inline-block text-xs font-medium px-1.5 py-0.5 rounded border ${statusClass}`}>
                        {statusLabel}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
      {progress && (
        <p className="text-sm text-[var(--primary)] font-medium" aria-live="polite">
          {progress}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          className="px-4 py-2 rounded-lg bg-[var(--primary)] text-white text-sm font-medium hover:bg-[#a07f33] disabled:opacity-50"
          onClick={() => void loadAll()}
        >
          {busy && progress ? "Seeding…" : "Load demo companies"}
        </button>
        <button
          type="button"
          disabled={busy}
          className="px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[#faf8f4] disabled:opacity-50"
          onClick={() => void removeAll()}
        >
          Remove demo companies
        </button>
      </div>
    </section>
  )
}

/* ── AI Assistant settings (#117) — provider keys, default model, rate limit ── */
type AiKeyStatus = {
  anthropic: string | null
  openai: string | null
  gemini: string | null
  xai: string | null
}
type AiProviderId = keyof AiKeyStatus

const AI_PROVIDERS: {
  id: AiProviderId
  label: string
  short: string
  settingsKey: string
  models: string[]
}[] = [
  { id: "anthropic", label: "Anthropic (Claude)", short: "Claude", settingsKey: "ai_api_key_anthropic", models: ["claude-sonnet-5", "claude-sonnet-4-6", "claude-haiku-4-5"] },
  { id: "openai",    label: "OpenAI (GPT)",       short: "OpenAI", settingsKey: "ai_api_key_openai",    models: ["gpt-4o-mini", "gpt-4o"] },
  { id: "gemini",    label: "Google (Gemini)",    short: "Gemini", settingsKey: "ai_api_key_gemini",    models: ["gemini-flash-latest", "gemini-pro-latest", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"] },
  {
    id: "xai",
    label: "xAI / Cursor Grok",
    short: "Grok",
    settingsKey: "ai_api_key_xai",
    models: [
      "grok-4.5",
      "grok-4.5-latest",
      "grok-4",
      "grok-4-1-fast-reasoning",
      "grok-4-1-fast-non-reasoning",
      "grok-3-mini",
      "grok-code-fast",
    ],
  },
]

function AiAssistantSection() {
  const { confirm } = useMessages()
  const [keyStatus, setKeyStatus] = useState<AiKeyStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [newKeys, setNewKeys] = useState<Record<AiProviderId, string>>({
    anthropic: "", openai: "", gemini: "", xai: "",
  })
  const [defaultModel, setDefaultModel] = useState("")
  const [rateLimit, setRateLimit] = useState("")
  // Provider insertion tab — default to xAI / Cursor Grok so the new
  // key field is immediately visible instead of buried under other rows.
  const [providerTab, setProviderTab] = useState<AiProviderId>("xai")
  // Ollama (self-hosted): no secret key -- gated by a tenant-tagged model
  // list instead. ollamaModels/ollamaBaseUrl round-trip through the plain
  // (non-secret) GET/PATCH /api/settings, unlike the cloud provider keys
  // which are write-only and never re-read.
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState("")
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [ollamaTagInput, setOllamaTagInput] = useState("")
  const initial = useRef({ defaultModel: "", rateLimit: "", ollamaBaseUrl: "", ollamaModels: [] as string[] })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState("")
  const activeProvider = AI_PROVIDERS.find((p) => p.id === providerTab) ?? AI_PROVIDERS[0]
  const activeStatus = keyStatus?.[activeProvider.id] ?? null

  const loadKeyStatus = () => {
    setStatusLoading(true)
    apiFetch<AiKeyStatus>("/api/ai/key-status")
      .then(setKeyStatus)
      .catch(() => setKeyStatus(null))
      .finally(() => setStatusLoading(false))
  }

  useEffect(() => {
    loadKeyStatus()
    apiFetch<Record<string, string>>("/api/settings").then(s => {
      const dm = s.ai_default_model || ""
      const rl = s.ai_rate_limit_per_hour || ""
      const obu = s.ai_ollama_base_url || ""
      const om = (s.ai_ollama_models || "").split(",").map(t => t.trim()).filter(Boolean)
      setDefaultModel(dm)
      setRateLimit(rl)
      setOllamaBaseUrl(obu)
      setOllamaModels(om)
      initial.current = { defaultModel: dm, rateLimit: rl, ollamaBaseUrl: obu, ollamaModels: om }
    }).catch(() => {})
  }, [])

  const addOllamaTags = (raw: string) => {
    const tags = raw.split(",").map(t => t.trim()).filter(Boolean)
    if (tags.length === 0) return
    setOllamaModels(prev => Array.from(new Set([...prev, ...tags])))
    setOllamaTagInput("")
  }
  const removeOllamaTag = (tag: string) => {
    setOllamaModels(prev => prev.filter(t => t !== tag))
  }

  const handleClearKey = async (provider: AiProviderId, label: string) => {
    const ok = await confirm({
      title: `Clear the ${label} API key?`,
      confirmLabel: "Clear key",
      danger: true,
    })
    if (!ok) return
    setError("")
    try {
      await apiFetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [`ai_api_key_${provider}`]: "" }),
      })
      setNewKeys(prev => ({ ...prev, [provider]: "" }))
      loadKeyStatus()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError("")
    try {
      const payload: Record<string, string> = {}
      for (const p of AI_PROVIDERS) {
        if (newKeys[p.id]) payload[p.settingsKey] = newKeys[p.id]
      }
      if (defaultModel !== initial.current.defaultModel) payload.ai_default_model = defaultModel
      if (rateLimit !== initial.current.rateLimit) payload.ai_rate_limit_per_hour = rateLimit
      if (ollamaBaseUrl !== initial.current.ollamaBaseUrl) payload.ai_ollama_base_url = ollamaBaseUrl
      if (ollamaModels.join(",") !== initial.current.ollamaModels.join(",")) {
        payload.ai_ollama_models = ollamaModels.join(",")
      }

      if (Object.keys(payload).length > 0) {
        await apiFetch("/api/settings", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
      }
      setNewKeys({ anthropic: "", openai: "", gemini: "", xai: "" })
      initial.current = { defaultModel, rateLimit, ollamaBaseUrl, ollamaModels }
      loadKeyStatus()
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
      <h2 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-[var(--primary)]" /> AI Assistant
      </h2>
      <p className="text-xs text-[var(--text-primary)]/50">
        Add API keys for the AI providers you want to power the chat assistant. Keys are stored server-side
        only — they are never displayed again once saved.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      <div className="space-y-4">
        {/* Provider insertion tabs — Claude / OpenAI / Gemini / Grok */}
        <div className="flex flex-wrap gap-1.5">
          {AI_PROVIDERS.map((p) => {
            const active = p.id === providerTab
            const set = Boolean(keyStatus?.[p.id])
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => setProviderTab(p.id)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium border transition-colors ${
                  active
                    ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                    : "bg-white text-[var(--text-primary)]/70 border-[var(--border)] hover:border-[var(--primary)]/40"
                }`}
              >
                {p.short}
                {set ? " · ✓" : ""}
              </button>
            )
          })}
        </div>

        <div className="rounded-xl border border-[var(--border)] p-4 space-y-3 bg-[var(--bg-page)]/40">
          <div className="flex items-center justify-between gap-3">
            <div>
              <label className="block text-sm font-medium text-[var(--text-primary)]">
                {activeProvider.label}
              </label>
              <span className="text-xs font-mono text-[var(--text-primary)]/60">
                {statusLoading ? "…" : (activeStatus || "Not set")}
              </span>
            </div>
            <button
              type="button"
              onClick={() => handleClearKey(activeProvider.id, activeProvider.label)}
              disabled={!activeStatus}
              className="px-3 py-2 border border-[var(--border)] rounded-lg text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-40 whitespace-nowrap"
            >
              Clear
            </button>
          </div>
          <input
            type="password"
            autoComplete="off"
            placeholder={`Paste ${activeProvider.short} API key…`}
            value={newKeys[activeProvider.id]}
            onChange={e => setNewKeys(prev => ({ ...prev, [activeProvider.id]: e.target.value }))}
            className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm bg-white"
          />
          {activeProvider.id === "xai" && (
            <p className="text-xs text-[var(--text-primary)]/50">
              xAI / Cursor Grok key from{" "}
              <a href="https://console.x.ai/" target="_blank" rel="noreferrer" className="text-[var(--primary)] hover:underline">
                console.x.ai
              </a>
              . Unlocks grok-4.5 and related models in the chat picker.
            </p>
          )}
        </div>

        <div className="pt-4 border-t border-[var(--border)] space-y-2">
          <label className="block text-xs font-medium text-[var(--text-primary)]/60">
            Ollama (Local) — self-hosted, no API key needed
          </label>
          <input
            type="text"
            placeholder="Server URL — http://localhost:11434"
            value={ollamaBaseUrl}
            onChange={e => setOllamaBaseUrl(e.target.value)}
            className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          />
          <div className="flex flex-wrap gap-1.5 min-h-[1.75rem]">
            {ollamaModels.map(tag => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 bg-[var(--primary)]/10 text-[var(--primary)] text-xs font-medium rounded-full pl-2.5 pr-1.5 py-1"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => removeOllamaTag(tag)}
                  className="hover:bg-[var(--primary)]/20 rounded-full p-0.5"
                  aria-label={`Remove ${tag}`}
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
          <input
            type="text"
            placeholder="Tag a locally-pulled model and press Enter — e.g. llama3.1:8b"
            value={ollamaTagInput}
            onChange={e => setOllamaTagInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter" || e.key === ",") {
                e.preventDefault()
                addOllamaTags(ollamaTagInput)
              }
            }}
            onBlur={() => ollamaTagInput && addOllamaTags(ollamaTagInput)}
            className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          />
          <p className="text-xs text-[var(--text-primary)]/50">
            Tag names must exactly match what `ollama list` shows on your server. Run `ollama pull &lt;model&gt;` first if it isn&apos;t listed there yet.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-[var(--border)]">
        <div>
          <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Default Model</label>
          <select
            value={defaultModel}
            onChange={e => setDefaultModel(e.target.value)}
            className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          >
            <option value="">— system default —</option>
            {AI_PROVIDERS.map(p => p.models.map(m => {
              const value = `${p.id}/${m}`
              const disabled = !keyStatus?.[p.id]
              return (
                <option key={value} value={value} disabled={disabled}>
                  {p.label} — {m}{disabled ? " (no key)" : ""}
                </option>
              )
            }))}
            {ollamaModels.map(m => {
              const value = `ollama/${m}`
              return (
                <option key={value} value={value}>
                  Ollama (Local) — {m}
                </option>
              )
            })}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Rate Limit (requests/hour)</label>
          <input
            type="number"
            min="0"
            placeholder="20"
            value={rateLimit}
            onChange={e => setRateLimit(e.target.value)}
            className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        {saved && <span className="text-sm text-green-700">Saved</span>}
      </div>
    </section>
  )
}

/* ── WhatsApp Meta Cloud API (#237) — lab report auto-send ── */
type WaStatus = {
  configured: boolean
  token_tail: string | null
  phone_number_id_set: boolean
  phone_number_id: string
  template_name: string
  template_lang: string
}

function WhatsAppMetaSection() {
  const { confirm } = useMessages()
  const [status, setStatus] = useState<WaStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [token, setToken] = useState("")
  const [phoneId, setPhoneId] = useState("")
  const [templateName, setTemplateName] = useState("")
  const [templateLang, setTemplateLang] = useState("en")
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState("")

  const loadStatus = () => {
    setStatusLoading(true)
    apiFetch<WaStatus>("/api/settings/whatsapp-status")
      .then(s => {
        setStatus(s)
        setPhoneId(s.phone_number_id || "")
        setTemplateName(s.template_name || "")
        setTemplateLang(s.template_lang || "en")
      })
      .catch(() => setStatus(null))
      .finally(() => setStatusLoading(false))
  }

  useEffect(() => { loadStatus() }, [])

  const handleClearToken = async () => {
    const ok = await confirm({
      title: "Clear the Meta WhatsApp access token?",
      confirmLabel: "Clear token",
      danger: true,
    })
    if (!ok) return
    setError("")
    try {
      await apiFetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wa_meta_access_token: "" }),
      })
      setToken("")
      loadStatus()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError("")
    try {
      const payload: Record<string, string> = {
        wa_meta_phone_number_id: phoneId.trim(),
        wa_meta_template_name: templateName.trim(),
        wa_meta_template_lang: (templateLang.trim() || "en"),
      }
      if (token.trim()) payload.wa_meta_access_token = token.trim()
      await apiFetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      setToken("")
      loadStatus()
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
      <h2 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
        <MessageCircle className="w-4 h-4 text-[var(--primary)]" /> WhatsApp (Meta)
      </h2>
      <p className="text-xs text-[var(--text-primary)]/50">
        Optional Meta Cloud API for lab “report ready” notifications. Create an approved template in
        Meta Business Manager with body params {"{{1}}"} = order number and {"{{2}}"} = portal URL.
        Without credentials, publish still offers the manual wa.me share link.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-[160px_1fr_auto] gap-3 items-end">
        <div>
          <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Access token</label>
          <span className="text-xs font-mono text-[var(--text-primary)]/70">
            {statusLoading ? "…" : (status?.token_tail || "Not set")}
          </span>
        </div>
        <input
          type="password"
          autoComplete="off"
          placeholder="Paste new Meta access token…"
          value={token}
          onChange={e => setToken(e.target.value)}
          className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={handleClearToken}
          disabled={!status?.token_tail}
          className="px-3 py-2 border border-[var(--border)] rounded-lg text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-40 whitespace-nowrap"
        >
          Clear
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Phone number ID</label>
          <input
            type="text"
            value={phoneId}
            onChange={e => setPhoneId(e.target.value)}
            placeholder="Meta Phone Number ID"
            className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Template name</label>
          <input
            type="text"
            value={templateName}
            onChange={e => setTemplateName(e.target.value)}
            placeholder="lab_report_ready"
            className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-[var(--text-primary)]/60 mb-1">Template language</label>
          <input
            type="text"
            value={templateLang}
            onChange={e => setTemplateLang(e.target.value)}
            placeholder="en"
            className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          />
        </div>
      </div>

      <p className="text-xs text-[var(--text-primary)]/50">
        Status:{" "}
        {statusLoading
          ? "…"
          : status?.configured
            ? "Ready to send on lab publish"
            : "Not fully configured — wa.me fallback remains active"}
      </p>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        {saved && <span className="text-sm text-green-700">Saved</span>}
      </div>
    </section>
  )
}

/* ── API Keys (#113) — machine-to-machine access, admin/owner only ── */
interface ApiKeyRow {
  id: number
  name: string
  key_hint: string
  scopes: string[]
  last_used: string | null
  expires_at: string | null
  is_active: boolean
  created_at: string
}

function ApiKeysSection() {
  const { confirm } = useMessages()
  const [rows, setRows] = useState<ApiKeyRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [newName, setNewName] = useState("")
  const [creating, setCreating] = useState(false)
  // The raw key, held ONLY while the reveal modal is open — cleared the
  // moment it closes; the backend cannot return it again.
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const load = () => {
    setLoading(true)
    apiFetch<ApiKeyRow[]>("/api/auth/keys")
      .then(setRows)
      .catch(err => setError(err instanceof Error ? err.message : "Failed to load API keys."))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  const handleCreate = async () => {
    const name = newName.trim()
    if (!name || creating) return
    setCreating(true)
    setError("")
    try {
      const created = await apiFetch<ApiKeyRow & { key: string }>("/api/auth/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      })
      setCreatedKey(created.key)
      setCopied(false)
      setNewName("")
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create the key.")
    } finally {
      setCreating(false)
    }
  }

  const handleCopy = async () => {
    if (!createdKey) return
    try {
      await navigator.clipboard.writeText(createdKey)
      setCopied(true)
    } catch {
      // Clipboard unavailable (e.g. non-HTTPS) — the key is still visible to select manually.
    }
  }

  const handleRevoke = async (row: ApiKeyRow) => {
    const ok = await confirm({
      title: `Revoke the key "${row.name}"?`,
      message: "Anything using it stops working immediately.",
      confirmLabel: "Revoke",
      danger: true,
    })
    if (!ok) return
    setError("")
    try {
      await apiFetch(`/api/auth/keys/${row.id}`, { method: "DELETE" })
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke the key.")
    }
  }

  return (
    <div className="space-y-6">
      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
        <h2 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-[var(--primary)]" /> API Keys
        </h2>
        <p className="text-xs text-[var(--text-primary)]/50">
          API keys let scripts and integrations call the Easy-Books API with the same access as your
          account — send one as <code className="px-1 bg-[var(--bg-page)] rounded">Authorization: Bearer &lt;key&gt;</code>.
          A key is shown only once, at creation; revoking takes effect immediately.
        </p>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
        )}

        <div className="flex gap-2">
          <input
            type="text"
            placeholder='Key name — e.g. "Zapier integration"'
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleCreate() }}
            className="flex-1 border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={handleCreate}
            disabled={!newName.trim() || creating}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50 whitespace-nowrap"
          >
            <Plus className="w-4 h-4" /> Create Key
          </button>
        </div>

        {loading ? (
          <p className="text-sm text-[var(--text-muted)]">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">No API keys yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border)]">
                  <th className="py-2 pr-3">Name</th>
                  <th className="py-2 pr-3">Key</th>
                  <th className="py-2 pr-3">Created</th>
                  <th className="py-2 pr-3">Last used</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.id} className="border-b border-[var(--border)] last:border-0">
                    <td className="py-2 pr-3 font-medium text-[var(--text-primary)]">{row.name}</td>
                    <td className="py-2 pr-3 font-mono text-xs text-[var(--text-muted)] whitespace-nowrap">
                      eb_live_…{row.key_hint}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">{fmtDate(row.created_at)}</td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {row.last_used ? fmtDate(row.last_used) : "Never"}
                    </td>
                    <td className="py-2 pr-3">
                      {row.is_active
                        ? <span className="text-green-700 text-xs font-medium">Active</span>
                        : <span className="text-red-600 text-xs font-medium">Revoked</span>}
                    </td>
                    <td className="py-2 text-right">
                      {row.is_active && (
                        <button
                          type="button"
                          onClick={() => handleRevoke(row)}
                          className="px-3 py-1 border border-[var(--border)] rounded-lg text-xs font-medium text-red-600 hover:bg-red-50"
                        >
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Reveal-once modal */}
      {createdKey && (
        <div className="fixed inset-0 z-[950] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/30" onClick={() => setCreatedKey(null)} />
          <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-[var(--border)] p-5 space-y-4">
            <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-[var(--primary)]" /> Copy your new API key
            </h3>
            <p className="text-xs text-[var(--text-primary)]/60">
              This is the <strong>only time</strong> the full key is shown. Store it somewhere safe —
              once you close this window it cannot be retrieved again.
            </p>
            <div className="flex gap-2 items-center">
              <code className="flex-1 min-w-0 break-all text-xs bg-[var(--bg-page)] border border-[var(--border)] rounded-lg px-3 py-2">
                {createdKey}
              </code>
              <button
                type="button"
                onClick={handleCopy}
                aria-label="Copy key"
                className="shrink-0 p-2 rounded-lg border border-[var(--border)] hover:bg-[var(--bg-page)]"
              >
                {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setCreatedKey(null)}
                className="px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)]"
              >
                I&apos;ve saved it — close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Security2FACard() {
  const [secret, setSecret] = useState<string | null>(null)
  const [otpauth, setOtpauth] = useState<string | null>(null)
  const [code, setCode] = useState("")
  const [status, setStatus] = useState("")
  const [enabled, setEnabled] = useState(false)

  const setup = async () => {
    const r = await apiFetch<{ secret: string; otpauth_url: string }>(
      "/api/auth/totp/setup",
      { method: "POST" },
    )
    setSecret(r.secret)
    setOtpauth(r.otpauth_url)
    setStatus("Scan the otpauth URL in your authenticator app, then enter a code.")
  }
  const enable = async () => {
    await apiFetch("/api/auth/totp/enable", { method: "POST", body: JSON.stringify({ code }) })
    setEnabled(true)
    setStatus("2FA enabled.")
  }
  const disable = async () => {
    await apiFetch("/api/auth/totp/disable", { method: "POST", body: JSON.stringify({ code }) })
    setEnabled(false)
    setSecret(null)
    setStatus("2FA disabled.")
  }

  return (
    <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-3">
      <h2 className="text-lg font-bold text-[var(--text-primary)]">Security · 2FA</h2>
      <p className="text-sm text-[var(--text-primary)]/60">
        Protect your account with an authenticator app (TOTP).
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={setup} className="px-3 py-1.5 border rounded-lg text-sm">Set up 2FA</button>
        <button type="button" onClick={enable} className="px-3 py-1.5 bg-[#b8943f] rounded-lg text-sm">Enable</button>
        <button type="button" onClick={disable} className="px-3 py-1.5 border rounded-lg text-sm">Disable</button>
      </div>
      {secret && (
        <div className="text-xs break-all space-y-1">
          <div>Secret: <code>{secret}</code></div>
          {otpauth && <div>URI: <code>{otpauth}</code></div>}
        </div>
      )}
      <input
        className="border rounded-lg px-3 py-1.5 text-sm"
        placeholder="6-digit code"
        value={code}
        onChange={(e) => setCode(e.target.value)}
      />
      {status && <p className="text-sm text-[var(--text-muted)]">{status}{enabled ? " ✓" : ""}</p>}
    </section>
  )
}

/** Browser-local home preference — Financial / Operations / PRA (when installed). */
function HomeDashboardSettingsCard({
  opsAvailable,
  praInstalled,
}: {
  opsAvailable: boolean
  praInstalled: boolean
}) {
  const [home, setHome] = useState<HomePreference>("financial")

  useEffect(() => {
    const stored = localStorage.getItem(HOME_PREF_KEY) as HomePreference | null
    if (stored === "pra" || stored === "operations" || stored === "financial" || stored === "accounting") {
      setHome(stored === "accounting" ? "financial" : stored)
    }
  }, [])

  const choose = (next: HomePreference) => {
    if (next === "operations" && !opsAvailable) return
    if (next === "pra" && !praInstalled) return
    setHome(next)
    localStorage.setItem(HOME_PREF_KEY, next)
    if (next === "pra") localStorage.setItem("eb.pra_portal_mode", "1")
    else localStorage.setItem("eb.pra_portal_mode", "0")
  }

  return (
    <div className="bg-white rounded-xl border border-[var(--border)] p-4 sm:p-6 md:p-8 shadow-sm space-y-3">
      <h2 className="text-xl font-semibold mb-1 flex items-center gap-3 text-black">
        <LayoutDashboard className="w-5 h-5 text-[var(--primary)]" />
        Home dashboard
      </h2>
      <p className="text-sm text-[var(--text-muted)]">
        Choose which home opens after login. Financial is the P&amp;L / cash overview;
        Operations shows purpose-built KPIs for installed industry modules.
        Preference is stored in this browser (<code className="text-xs">eb.home_dashboard</code>).
        {opsAvailable && (
          <> Open it anytime via Dashboard → Operations or{" "}
            <Link href="/dashboard/operations" className="text-[var(--primary)] font-semibold hover:underline">
              /dashboard/operations
            </Link>.
          </>
        )}
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => choose("financial")}
          className={`px-3 py-1.5 rounded-lg text-sm font-semibold border transition-colors ${
            home === "financial"
              ? "bg-[var(--primary)] text-white border-[var(--primary)]"
              : "border-[var(--border)] text-[var(--text-primary)]/70 hover:border-[var(--primary)]/40"
          }`}
        >
          Financial
        </button>
        <button
          type="button"
          disabled={!opsAvailable}
          onClick={() => choose("operations")}
          className={`px-3 py-1.5 rounded-lg text-sm font-semibold border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
            home === "operations"
              ? "bg-[var(--primary)] text-white border-[var(--primary)]"
              : "border-[var(--border)] text-[var(--text-primary)]/70 hover:border-[var(--primary)]/40"
          }`}
          title={opsAvailable ? undefined : "Install an industry pack (Manufacturing, Spinning, Processing, Healthcare, …) to enable Operations"}
        >
          Operations
        </button>
        {praInstalled && (
          <button
            type="button"
            onClick={() => choose("pra")}
            className={`px-3 py-1.5 rounded-lg text-sm font-semibold border transition-colors ${
              home === "pra"
                ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                : "border-[var(--border)] text-[var(--text-primary)]/70 hover:border-[var(--primary)]/40"
            }`}
          >
            PRA Sales
          </button>
        )}
      </div>
      <p className="text-xs text-[var(--text-muted)]">
        You can also switch on the Dashboard page itself
        {opsAvailable ? " via the Financial | Operations toggle" : ""}.
        Staff access is controlled under{" "}
        <Link href="/settings/permissions" className="text-[var(--primary)] underline underline-offset-2">
          User Rights → Dashboard
        </Link>
        {" "}when the rights module is enabled.
      </p>
      <Link
        href={home === "pra" ? "/pra-dashboard" : home === "operations" ? "/dashboard?view=operations" : "/dashboard?view=financial"}
        className="inline-flex items-center gap-2 text-sm font-medium text-[var(--primary)] hover:underline"
      >
        Open home →
      </Link>
    </div>
  )
}
