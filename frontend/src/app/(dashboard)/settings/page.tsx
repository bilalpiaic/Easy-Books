'use client'

import { Save, Bell, Globe } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'
import { useSettings, AppSettings } from '@/context/SettingsContext'

export default function SettingsPage() {
  const { settings: ctxSettings, reload } = useSettings()
  const [form, setForm] = useState<AppSettings>(ctxSettings)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => { setForm(ctxSettings) }, [ctxSettings])

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
