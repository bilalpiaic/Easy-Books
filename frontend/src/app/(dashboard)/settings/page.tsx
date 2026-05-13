'use client'

import { Save, Bell, Lock, Globe } from 'lucide-react'
import { useState } from 'react'

interface SettingsData {
  company_name: string
  tax_id: string
  fiscal_year_start: string
  currency: string
  email_notifications: boolean
  invoice_prefix: string
  bill_prefix: string
  financial_statement_date: string
}

export default function Settings() {
  const [settings, setSettings] = useState<SettingsData>({
    company_name: 'Malik Enterprises',
    tax_id: '12-3456789',
    fiscal_year_start: 'January',
    currency: 'PKR',
    email_notifications: true,
    invoice_prefix: 'INV',
    bill_prefix: 'BILL',
    financial_statement_date: 'month_end'
  })

  const [saved, setSaved] = useState(false)

  const handleChange = (field: keyof SettingsData, value: any) => {
    setSettings(prev => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    // TODO: Send to API
    console.log('Saving settings...', settings)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <div className="space-y-6 p-8 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-serif font-medium">Settings</h1>
        <p className="text-sm text-black/50 mt-1">Configure business and accounting settings</p>
      </div>

      {/* Success Message */}
      {saved && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-green-700">
          ✓ Settings saved successfully
        </div>
      )}

      {/* Company Settings */}
      <div className="bg-white rounded-xl border border-[#ede9e2] p-8">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-3">
          <Globe className="w-5 h-5 text-[#b8943f]" />
          Company Information
        </h2>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium mb-2">Company Name</label>
            <input
              type="text"
              value={settings.company_name}
              onChange={(e) => handleChange('company_name', e.target.value)}
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium mb-2">Tax ID / EIN</label>
              <input
                type="text"
                value={settings.tax_id}
                onChange={(e) => handleChange('tax_id', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Currency</label>
              <select
                value={settings.currency}
                onChange={(e) => handleChange('currency', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              >
                <option>PKR</option>
                <option>USD</option>
                <option>EUR</option>
                <option>GBP</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium mb-2">Fiscal Year Start</label>
              <select
                value={settings.fiscal_year_start}
                onChange={(e) => handleChange('fiscal_year_start', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              >
                <option>January</option>
                <option>April</option>
                <option>July</option>
                <option>October</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Financial Statement Date</label>
              <select
                value={settings.financial_statement_date}
                onChange={(e) => handleChange('financial_statement_date', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
              >
                <option value="month_end">Month End</option>
                <option value="quarter_end">Quarter End</option>
                <option value="year_end">Year End</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Document Settings */}
      <div className="bg-white rounded-xl border border-[#ede9e2] p-8">
        <h2 className="text-xl font-semibold mb-6">Document Numbering</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium mb-2">Invoice Prefix</label>
            <input
              type="text"
              value={settings.invoice_prefix}
              onChange={(e) => handleChange('invoice_prefix', e.target.value)}
              placeholder="e.g., INV"
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
            />
            <p className="text-xs text-black/50 mt-1">Example: INV-001, INV-002</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Bill Prefix</label>
            <input
              type="text"
              value={settings.bill_prefix}
              onChange={(e) => handleChange('bill_prefix', e.target.value)}
              placeholder="e.g., BILL"
              className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
            />
            <p className="text-xs text-black/50 mt-1">Example: BILL-001, BILL-002</p>
          </div>
        </div>
      </div>

      {/* Notification Settings */}
      <div className="bg-white rounded-xl border border-[#ede9e2] p-8">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-3">
          <Bell className="w-5 h-5 text-[#b8943f]" />
          Notifications
        </h2>

        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium">Email Notifications</h3>
            <p className="text-sm text-black/50 mt-1">Receive alerts for overdue invoices and bills</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={settings.email_notifications}
              onChange={(e) => handleChange('email_notifications', e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[#b8943f]/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#b8943f]"></div>
          </label>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end gap-3">
        <button className="px-6 py-2 border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee]">
          Cancel
        </button>
        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-6 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]"
        >
          <Save className="w-4 h-4" />
          Save Settings
        </button>
      </div>

      {/* Help Section */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 Settings Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Ensure all company information is accurate and up-to-date</li>
          <li>✓ Use consistent document numbering for audit trails</li>
          <li>✓ Configure fiscal year to match your tax filing period</li>
          <li>✓ Enable email notifications to stay on top of outstanding items</li>
          <li>✓ Back up settings regularly</li>
        </ul>
      </div>
    </div>
  )
}
