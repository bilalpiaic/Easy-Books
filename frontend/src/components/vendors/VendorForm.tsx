'use client'

import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

export interface VendorFull {
  id: number
  name: string
  email: string | null
  phone: string | null
  address: string | null
  opening_balance: number
  is_active: boolean
}

interface FormState {
  name: string
  email: string
  phone: string
  address: string
  opening_balance: string
}

const emptyForm: FormState = { name: '', email: '', phone: '', address: '', opening_balance: '0' }

interface Props {
  mode: 'create' | 'edit'
  vendor?: VendorFull
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function VendorForm({ mode, vendor, onSaved, onCancel }: Props) {
  const [form, setForm] = useState<FormState>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  useEffect(() => {
    if (mode === 'edit' && vendor) {
      setForm({
        name: vendor.name,
        email: vendor.email ?? '',
        phone: vendor.phone ?? '',
        address: vendor.address ?? '',
        opening_balance: String(vendor.opening_balance),
      })
    }
  }, [mode, vendor])

  const handleSave = async () => {
    if (!form.name.trim()) { setFormError('Name is required.'); return }
    setSaving(true); setFormError('')
    try {
      const body = {
        name: form.name,
        email: form.email || null,
        phone: form.phone || null,
        address: form.address || null,
        opening_balance: parseFloat(form.opening_balance) || 0,
      }
      if (mode === 'edit' && vendor) {
        await apiFetch(`/api/vendors/${vendor.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
        onSaved(vendor.id)
      } else {
        const created = await apiFetch<VendorFull>('/api/vendors', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
        onSaved(created.id)
      }
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-[#ede9e2] p-8 max-w-lg mx-auto">
      <div className="space-y-4">
        {(['name', 'email', 'phone', 'address'] as const).map(field => (
          <div key={field}>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1 capitalize">{field}</label>
            <input
              value={form[field]}
              onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))}
              className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
              placeholder={field === 'name' ? 'Vendor name' : ''}
            />
          </div>
        ))}
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Opening Balance</label>
          <input
            type="number" step="0.01"
            value={form.opening_balance}
            onChange={e => setForm(p => ({ ...p, opening_balance: e.target.value }))}
            className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
          />
        </div>
        {formError && <p className="text-red-600 text-sm">{formError}</p>}
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onCancel} className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee]">Cancel</button>
          <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50">
            {saving ? 'Saving...' : mode === 'edit' ? 'Save Changes' : 'Add Vendor'}
          </button>
        </div>
      </div>
    </div>
  )
}
