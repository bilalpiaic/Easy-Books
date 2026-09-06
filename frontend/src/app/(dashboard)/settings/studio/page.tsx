'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { PenTool, Plus, Trash2, Save, Copy, Star } from 'lucide-react'
import { apiFetch } from '@/lib/api'

type Tab = 'fields' | 'forms' | 'print'
type Entity = 'invoice' | 'bill' | 'customer' | 'product' | 'vendor'
type PrintEntity = 'invoice' | 'bill'

const ENTITIES: Entity[] = ['invoice', 'bill', 'customer', 'product', 'vendor']
const PRINT_ENTITIES: PrintEntity[] = ['invoice', 'bill']

const CORE_EDITABLE: Record<Entity, { key: string; label: string }[]> = {
  invoice: [
    { key: 'notes', label: 'Notes' },
    { key: 'internal_memo', label: 'Internal memo' },
    { key: 'description', label: 'Description' },
    { key: 'discount_pct', label: 'Line discount %' },
  ],
  bill: [
    { key: 'notes', label: 'Notes' },
    { key: 'internal_memo', label: 'Internal memo' },
    { key: 'description', label: 'Description' },
    { key: 'discount_pct', label: 'Line discount %' },
  ],
  customer: [
    { key: 'email', label: 'Email' },
    { key: 'phone', label: 'Phone' },
    { key: 'address', label: 'Address' },
  ],
  vendor: [
    { key: 'email', label: 'Email' },
    { key: 'phone', label: 'Phone' },
    { key: 'address', label: 'Address' },
  ],
  product: [
    { key: 'code', label: 'Code' },
    { key: 'unit', label: 'Unit' },
    { key: 'default_rate', label: 'Sale price' },
  ],
}

type FieldDef = {
  id: number
  entity: Entity
  key: string
  label: string
  type: string
  required: boolean
  show_on_form: boolean
  show_on_print: boolean
  show_on_list: boolean
  archived_at: string | null
}

type FormSchema = {
  schema: { fields: Record<string, { visible?: boolean; required?: boolean }> }
  locked: string[]
}

type PrintTpl = {
  id: number | null
  entity: string
  key: string
  label: string
  html: string | null
  is_builtin: boolean
  is_default: boolean
}

export default function StudioPage() {
  const [tab, setTab] = useState<Tab>('fields')
  const [entity, setEntity] = useState<Entity>('invoice')
  const [printEntity, setPrintEntity] = useState<PrintEntity>('invoice')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const flash = (ok: string) => {
    setErr('')
    setMsg(ok)
    setTimeout(() => setMsg(''), 2500)
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-[var(--primary)]/10 rounded-lg">
          <PenTool className="w-6 h-6 text-[var(--primary)]" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Studio</h1>
          <p className="text-sm text-[var(--text-primary)]/60">
            Custom fields, form layout, and print templates. Mill tenants: install{" "}
            <Link href="/apps?tab=marketplace" className="text-[var(--primary)] underline">
              Weighbridge
            </Link>{" "}
            from Add-ons → Marketplace (gate pass + lot on invoices). Marketplace listings apply a
            declarative bundle on Install — no partner code runs in-process.
          </p>
        </div>
      </div>

      <div className="flex gap-2 print:hidden">
        {([
          ['fields', 'Fields'],
          ['forms', 'Form layout'],
          ['print', 'Print'],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${
              tab === id
                ? 'bg-[var(--primary)] text-white'
                : 'bg-white border border-[var(--border)] text-[var(--text-primary)]'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {msg && <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{err}</div>}

      {tab === 'fields' && (
        <FieldsTab entity={entity} setEntity={setEntity} flash={flash} onError={setErr} />
      )}
      {tab === 'forms' && (
        <FormsTab entity={entity} setEntity={setEntity} flash={flash} onError={setErr} />
      )}
      {tab === 'print' && (
        <PrintTab entity={printEntity} setEntity={setPrintEntity} flash={flash} onError={setErr} />
      )}
    </div>
  )
}

function FieldsTab({
  entity, setEntity, flash, onError,
}: {
  entity: Entity
  setEntity: (e: Entity) => void
  flash: (s: string) => void
  onError: (s: string) => void
}) {
  const [rows, setRows] = useState<FieldDef[]>([])
  const [form, setForm] = useState({ key: 'x.', label: '', type: 'text', show_on_print: false, required: false })

  const load = useCallback(() => {
    apiFetch<FieldDef[]>(`/api/studio/fields?entity=${entity}`)
      .then(setRows)
      .catch(e => onError(String(e)))
  }, [entity, onError])

  useEffect(() => { load() }, [load])

  const add = async () => {
    try {
      await apiFetch('/api/studio/fields', {
        method: 'POST',
        body: JSON.stringify({
          entity,
          key: form.key,
          label: form.label,
          type: form.type,
          required: form.required,
          show_on_print: form.show_on_print,
          show_on_form: true,
        }),
      })
      setForm({ key: 'x.', label: '', type: 'text', show_on_print: false, required: false })
      flash('Field added')
      load()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : String(e))
    }
  }

  const archive = async (id: number) => {
    try {
      await apiFetch(`/api/studio/fields/${id}`, { method: 'DELETE' })
      flash('Field archived')
      load()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="space-y-4">
      <EntityPicker value={entity} onChange={setEntity} />
      <div className="bg-white rounded-xl border border-[var(--border)] p-4 space-y-3">
        <div className="text-sm font-semibold text-[var(--text-primary)]">Add field</div>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <input
            value={form.key}
            onChange={e => setForm(f => ({ ...f, key: e.target.value }))}
            placeholder="x.gate_pass_no"
            className="px-3 py-2 bg-[var(--bg-page)] rounded-lg text-sm font-mono"
          />
          <input
            value={form.label}
            onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
            placeholder="Label"
            className="px-3 py-2 bg-[var(--bg-page)] rounded-lg text-sm"
          />
          <select
            value={form.type}
            onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
            className="px-3 py-2 bg-[var(--bg-page)] rounded-lg text-sm"
          >
            {['text', 'number', 'date', 'bool', 'enum'].map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <button
            onClick={add}
            className="flex items-center justify-center gap-2 px-3 py-2 bg-[var(--text-primary)] text-white rounded-lg text-sm font-medium"
          >
            <Plus className="w-4 h-4" /> Add
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]/70">
          <input type="checkbox" checked={form.required} onChange={e => setForm(f => ({ ...f, required: e.target.checked }))} />
          Required
        </label>
        <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]/70">
          <input type="checkbox" checked={form.show_on_print} onChange={e => setForm(f => ({ ...f, show_on_print: e.target.checked }))} />
          Show on print
        </label>
      </div>
      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        {rows.length === 0 && (
          <div className="px-4 py-8 text-sm text-[var(--text-primary)]/50 text-center">No custom fields for {entity}.</div>
        )}
        {rows.map(r => (
          <div key={r.id} className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] last:border-0">
            <div>
              <div className="text-sm font-medium text-[var(--text-primary)]">{r.label}</div>
              <div className="text-xs font-mono text-[var(--text-primary)]/50">{r.key} · {r.type}</div>
            </div>
            <button onClick={() => archive(r.id)} className="p-2 text-red-600 hover:bg-red-50 rounded-lg" title="Archive">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

function FormsTab({
  entity, setEntity, flash, onError,
}: {
  entity: Entity
  setEntity: (e: Entity) => void
  flash: (s: string) => void
  onError: (s: string) => void
}) {
  const [schema, setSchema] = useState<FormSchema | null>(null)
  const [defs, setDefs] = useState<FieldDef[]>([])
  const [draft, setDraft] = useState<Record<string, { visible: boolean; required: boolean }>>({})

  const load = useCallback(() => {
    Promise.all([
      apiFetch<FormSchema>(`/api/studio/forms/${entity}`),
      apiFetch<FieldDef[]>(`/api/studio/fields?entity=${entity}`),
    ]).then(([s, f]) => {
      setSchema(s)
      setDefs(f)
      const next: Record<string, { visible: boolean; required: boolean }> = {}
      const keys = [
        ...CORE_EDITABLE[entity].map(c => c.key),
        ...f.map(d => d.key),
      ]
      for (const k of keys) {
        const cfg = s.schema?.fields?.[k] || {}
        next[k] = { visible: cfg.visible !== false, required: cfg.required === true }
      }
      setDraft(next)
    }).catch(e => onError(String(e)))
  }, [entity, onError])

  useEffect(() => { load() }, [load])

  const save = async () => {
    const fields: Record<string, { visible: boolean; required: boolean }> = {}
    for (const [k, cfg] of Object.entries(draft)) {
      fields[k] = { visible: cfg.visible, required: cfg.required }
    }
    try {
      await apiFetch(`/api/studio/forms/${entity}`, {
        method: 'PUT',
        body: JSON.stringify({ role: '*', schema: { version: 1, fields } }),
      })
      flash('Form layout saved')
      load()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : String(e))
    }
  }

  const rows = [
    ...CORE_EDITABLE[entity],
    ...defs.map(d => ({ key: d.key, label: d.label })),
  ]
  const locked = new Set(schema?.locked || [])

  return (
    <div className="space-y-4">
      <EntityPicker value={entity} onChange={setEntity} />
      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        {rows.map(r => {
          const isLocked = locked.has(r.key)
          const cfg = draft[r.key] || { visible: true, required: false }
          return (
            <div key={r.key} className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] last:border-0">
              <div>
                <div className="text-sm text-[var(--text-primary)]">{r.label}</div>
                <div className="text-xs font-mono text-[var(--text-primary)]/40">{r.key}{isLocked ? ' · locked' : ''}</div>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <label className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    disabled={isLocked}
                    checked={cfg.visible}
                    onChange={e => setDraft(d => ({ ...d, [r.key]: { ...cfg, visible: e.target.checked } }))}
                  />
                  Visible
                </label>
                <label className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    disabled={isLocked || !cfg.visible}
                    checked={cfg.required}
                    onChange={e => setDraft(d => ({ ...d, [r.key]: { ...cfg, required: e.target.checked } }))}
                  />
                  Required
                </label>
              </div>
            </div>
          )
        })}
      </div>
      <button
        onClick={save}
        className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium"
      >
        <Save className="w-4 h-4" /> Save layout
      </button>
    </div>
  )
}

function PrintTab({
  entity, setEntity, flash, onError,
}: {
  entity: PrintEntity
  setEntity: (e: PrintEntity) => void
  flash: (s: string) => void
  onError: (s: string) => void
}) {
  const [rows, setRows] = useState<PrintTpl[]>([])
  const [editing, setEditing] = useState<PrintTpl | null>(null)
  const [cloneKey, setCloneKey] = useState('x.mill_packing')
  const [cloneLabel, setCloneLabel] = useState('Mill packing')

  const load = useCallback(() => {
    apiFetch<PrintTpl[]>(`/api/studio/print-templates?entity=${entity}`)
      .then(setRows)
      .catch(e => onError(String(e)))
  }, [entity, onError])

  useEffect(() => { load() }, [load])

  const clone = async () => {
    try {
      await apiFetch('/api/studio/print-templates', {
        method: 'POST',
        body: JSON.stringify({ entity, key: cloneKey, label: cloneLabel }),
      })
      flash('Template cloned')
      load()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : String(e))
    }
  }

  const makeDefault = async (key: string) => {
    try {
      await apiFetch('/api/studio/print-templates/default', {
        method: 'PUT',
        body: JSON.stringify({ entity, key }),
      })
      flash('Default print template updated')
      load()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : String(e))
    }
  }

  const saveHtml = async () => {
    if (!editing?.id) return
    try {
      await apiFetch(`/api/studio/print-templates/${editing.id}`, {
        method: 'PUT',
        body: JSON.stringify({ html: editing.html }),
      })
      flash('Template saved')
      setEditing(null)
      load()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : String(e))
    }
  }

  const remove = async (id: number) => {
    try {
      await apiFetch(`/api/studio/print-templates/${id}`, { method: 'DELETE' })
      flash('Template deleted')
      if (editing?.id === id) setEditing(null)
      load()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {PRINT_ENTITIES.map(e => (
          <button
            key={e}
            onClick={() => setEntity(e)}
            className={`px-3 py-1.5 rounded-lg text-sm ${
              entity === e ? 'bg-[var(--text-primary)] text-white' : 'bg-white border border-[var(--border)]'
            }`}
          >
            {e}
          </button>
        ))}
      </div>
      <div className="bg-white rounded-xl border border-[var(--border)] p-4 flex flex-wrap gap-2 items-end">
        <div>
          <div className="text-xs text-[var(--text-primary)]/50 mb-1">Clone key</div>
          <input value={cloneKey} onChange={e => setCloneKey(e.target.value)} className="px-3 py-2 bg-[var(--bg-page)] rounded-lg text-sm font-mono" />
        </div>
        <div>
          <div className="text-xs text-[var(--text-primary)]/50 mb-1">Label</div>
          <input value={cloneLabel} onChange={e => setCloneLabel(e.target.value)} className="px-3 py-2 bg-[var(--bg-page)] rounded-lg text-sm" />
        </div>
        <button onClick={clone} className="flex items-center gap-2 px-3 py-2 bg-[var(--text-primary)] text-white rounded-lg text-sm">
          <Copy className="w-4 h-4" /> Clone standard
        </button>
      </div>
      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        {rows.map(r => (
          <div key={`${r.key}-${r.id}`} className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] last:border-0">
            <div>
              <div className="text-sm font-medium text-[var(--text-primary)]">
                {r.label} {r.is_default ? <span className="text-[var(--primary)] text-xs">default</span> : null}
              </div>
              <div className="text-xs font-mono text-[var(--text-primary)]/50">
                {r.key}{r.is_builtin ? ' · built-in' : ''}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => makeDefault(r.key)} className="p-2 hover:bg-[var(--bg-page)] rounded-lg" title="Set default">
                <Star className={`w-4 h-4 ${r.is_default ? 'text-[var(--primary)]' : 'text-[var(--text-primary)]/40'}`} />
              </button>
              {!r.is_builtin && r.id && (
                <>
                  <button onClick={() => setEditing(r)} className="text-xs px-2 py-1 border border-[var(--border)] rounded-lg">Edit HTML</button>
                  <button onClick={() => remove(r.id!)} className="p-2 text-red-600 hover:bg-red-50 rounded-lg">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
      {editing && (
        <div className="bg-white rounded-xl border border-[var(--border)] p-4 space-y-2">
          <div className="text-sm font-semibold">Edit {editing.label}</div>
          <textarea
            value={editing.html || ''}
            onChange={e => setEditing({ ...editing, html: e.target.value })}
            rows={16}
            className="w-full font-mono text-xs px-3 py-2 bg-[var(--bg-page)] rounded-lg"
          />
          <button onClick={saveHtml} className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm">
            <Save className="w-4 h-4" /> Save HTML
          </button>
        </div>
      )}
    </div>
  )
}

function EntityPicker({ value, onChange }: { value: Entity; onChange: (e: Entity) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {ENTITIES.map(e => (
        <button
          key={e}
          onClick={() => onChange(e)}
          className={`px-3 py-1.5 rounded-lg text-sm ${
            value === e ? 'bg-[var(--text-primary)] text-white' : 'bg-white border border-[var(--border)]'
          }`}
        >
          {e}
        </button>
      ))}
    </div>
  )
}
