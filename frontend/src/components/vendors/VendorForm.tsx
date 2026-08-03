'use client'

import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'
import { useModules } from '@/context/ModuleContext'

export interface VendorFull {
  id: number
  name: string
  email: string | null
  phone: string | null
  address: string | null
  opening_balance: number
  is_active: boolean
  payment_term_id: number | null
  gstin?: string | null
  state_code?: string | null
}

interface PaymentTerm { id: number; code: string; name: string; days: number }

interface FormState {
  name: string
  email: string
  phone: string
  address: string
  opening_balance: string
  payment_term_id: string
  gstin: string
  state_code: string
}

const emptyForm: FormState = {
  name: '', email: '', phone: '', address: '', opening_balance: '0', payment_term_id: '',
  gstin: '', state_code: '',
}

interface Props {
  mode: 'create' | 'edit'
  vendor?: VendorFull
  onSaved: (id: number) => void
  onCancel: () => void
}

export default function VendorForm({ mode, vendor, onSaved, onCancel }: Props) {
  const { installedModules } = useModules()
  const showGst = installedModules.has('in_gst')
  const [form, setForm]           = useState<FormState>(emptyForm)
  const [terms, setTerms]         = useState<PaymentTerm[]>([])
  const [saving, setSaving]       = useState(false)
  const [formError, setFormError] = useState('')

  useEffect(() => {
    apiFetch<PaymentTerm[]>('/api/payment-terms').then(setTerms).catch(() => {})
  }, [])

  useEffect(() => {
    if (mode === 'edit' && vendor) {
      setForm({
        name: vendor.name,
        email: vendor.email ?? '',
        phone: vendor.phone ?? '',
        address: vendor.address ?? '',
        opening_balance: String(vendor.opening_balance),
        payment_term_id: vendor.payment_term_id ? String(vendor.payment_term_id) : '',
        gstin: vendor.gstin ?? '',
        state_code: vendor.state_code ?? '',
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
        payment_term_id: form.payment_term_id ? parseInt(form.payment_term_id) : null,
        gstin: form.gstin || null,
        state_code: form.state_code || null,
      }
      if (mode === 'edit' && vendor) {
        await apiFetch(`/api/vendors/${vendor.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        onSaved(vendor.id)
      } else {
        const created = await apiFetch<VendorFull>('/api/vendors', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        onSaved(created.id)
      }
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-[var(--border)] p-8 max-w-lg mx-auto">
      <div className="space-y-4">
        {(['name', 'email', 'phone', 'address'] as const).map(field => (
          <div key={field}>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1 capitalize">{field}</label>
            <input
              value={form[field]}
              onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))}
              className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]"
              placeholder={field === 'name' ? 'Vendor name' : ''}
            />
          </div>
        ))}
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Opening Balance</label>
          <input
            type="number" step="0.01"
            value={form.opening_balance}
            onChange={e => setForm(p => ({ ...p, opening_balance: e.target.value }))}
            className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]"
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
            Default Payment Terms
          </label>
          <select
            value={form.payment_term_id}
            onChange={e => setForm(p => ({ ...p, payment_term_id: e.target.value }))}
            className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]"
          >
            <option value="">None (set per bill)</option>
            {terms.map(t => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.days} days)
              </option>
            ))}
          </select>
          {terms.length === 0 && (
            <p className="text-xs text-[var(--text-primary)]/50 mt-1">
              No terms configured — add them in Settings → Payment Terms.
            </p>
          )}
          <p className="text-xs text-[var(--text-primary)]/50 mt-1">
            Applied to new bills for this vendor when no term is chosen on the bill.
          </p>
        </div>

        {showGst && (
          <div className="border-t border-[var(--border)] pt-4 space-y-3">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/40">India GST</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">GSTIN</label>
                <input
                  value={form.gstin}
                  onChange={e => setForm(p => ({ ...p, gstin: e.target.value }))}
                  placeholder="15-character GSTIN"
                  className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">State code</label>
                <input
                  value={form.state_code}
                  onChange={e => setForm(p => ({ ...p, state_code: e.target.value }))}
                  placeholder="e.g. 27"
                  maxLength={2}
                  className="w-full ui-field bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] font-mono"
                />
              </div>
            </div>
          </div>
        )}
        {formError && <p className="text-red-600 text-sm">{formError}</p>}
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onCancel} className="px-6 py-3 border border-[var(--text-primary)]/10 rounded-xl font-bold hover:bg-[var(--bg-page)]">Cancel</button>
          <button onClick={handleSave} disabled={saving} className="px-6 py-3 bg-[var(--text-primary)] text-white rounded-xl font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50">
            {saving ? 'Saving...' : mode === 'edit' ? 'Save Changes' : 'Add Vendor'}
          </button>
        </div>
      </div>
    </div>
  )
}
