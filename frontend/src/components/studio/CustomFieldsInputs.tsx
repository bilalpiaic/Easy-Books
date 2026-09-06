'use client'

import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

export type CustomFieldEntity = 'invoice' | 'bill' | 'customer' | 'product' | 'vendor'

export type CustomFieldType = 'text' | 'number' | 'date' | 'enum' | 'bool'

export type CustomFieldDef = {
  id: number
  entity: CustomFieldEntity
  key: string
  label: string
  type: CustomFieldType
  enum_values: string[] | null
  required: boolean
  show_on_form: boolean
  show_on_print: boolean
  show_on_list: boolean
  sort_order: number
  archived_at: string | null
}

export type CustomFieldValues = Record<string, unknown>

export async function fetchStudioFields(entity: CustomFieldEntity): Promise<CustomFieldDef[]> {
  const rows = await apiFetch<CustomFieldDef[]>(`/api/studio/fields?entity=${entity}`)
  return (rows || []).filter(d => !d.archived_at)
}

export function formatCustomValue(def: CustomFieldDef, values: CustomFieldValues | undefined): string {
  const raw = values?.[def.key]
  if (raw == null || raw === '') return '—'
  if (def.type === 'bool') return raw ? 'Yes' : 'No'
  return String(raw)
}

export function CustomFieldsInputs({
  entity,
  values,
  onChange,
}: {
  entity: CustomFieldEntity
  values: CustomFieldValues
  onChange: (next: CustomFieldValues) => void
}) {
  const [defs, setDefs] = useState<CustomFieldDef[]>([])

  useEffect(() => {
    fetchStudioFields(entity)
      .then(rows => setDefs(rows.filter(d => d.show_on_form)))
      .catch(() => setDefs([]))
  }, [entity])

  if (defs.length === 0) return null

  const setKey = (key: string, value: unknown) => {
    const next = { ...values }
    if (value === '' || value === undefined) delete next[key]
    else next[key] = value
    onChange(next)
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {defs.map(def => {
        const raw = values[def.key]
        const label = (
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
            {def.label}
            {def.required ? <span className="text-red-600"> *</span> : null}
          </label>
        )
        const fieldClass =
          'w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm'
        if (def.type === 'bool') {
          return (
            <div key={def.key} className="flex items-center gap-2 pt-5">
              <input
                id={def.key}
                type="checkbox"
                checked={Boolean(raw)}
                onChange={e => setKey(def.key, e.target.checked)}
                className="rounded border-[var(--border)] accent-[var(--primary)]"
              />
              <label htmlFor={def.key} className="text-sm text-[var(--text-primary)]">
                {def.label}
                {def.required ? <span className="text-red-600"> *</span> : null}
              </label>
            </div>
          )
        }
        if (def.type === 'enum') {
          return (
            <div key={def.key}>
              {label}
              <select
                value={raw == null ? '' : String(raw)}
                required={def.required}
                onChange={e => setKey(def.key, e.target.value)}
                className={fieldClass}
              >
                <option value="">—</option>
                {(def.enum_values || []).map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
          )
        }
        if (def.type === 'number') {
          return (
            <div key={def.key}>
              {label}
              <input
                type="number"
                step="any"
                required={def.required}
                value={raw == null ? '' : String(raw)}
                onChange={e => setKey(def.key, e.target.value === '' ? '' : Number(e.target.value))}
                className={fieldClass}
              />
            </div>
          )
        }
        return (
          <div key={def.key}>
            {label}
            <input
              type={def.type === 'date' ? 'date' : 'text'}
              required={def.required}
              value={raw == null ? '' : String(raw)}
              onChange={e => setKey(def.key, e.target.value)}
              className={fieldClass}
            />
          </div>
        )
      })}
    </div>
  )
}
