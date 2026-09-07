'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { PenTool, Plus, Trash2, Save, Copy, Star, Info, Lock } from 'lucide-react'
import { apiFetch } from '@/lib/api'

type Tab = 'fields' | 'forms' | 'print'
type Entity = 'invoice' | 'bill' | 'customer' | 'product' | 'vendor'
type PrintEntity = 'invoice' | 'bill'

const ENTITIES: Entity[] = ['invoice', 'bill', 'customer', 'product', 'vendor']
const PRINT_ENTITIES: PrintEntity[] = ['invoice', 'bill']

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

type Suggestion = {
  key: string
  label: string
  type: string
  hint: string
  added: boolean
  archived: boolean
  source: string
}

type CatalogField = {
  key: string
  label: string
  type: string
  kind: 'core' | 'custom'
  locked: boolean
  hint: string
}

type FieldCatalog = {
  entity: Entity
  cap: number
  used: number
  remaining: number
  suggestions: Suggestion[]
  form_fields: CatalogField[]
  existing_keys: string[]
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
          <p className="text-xs text-[var(--text-primary)]/50 mb-1">
            <Link href="/settings?tab=advanced" className="hover:text-[var(--primary)] hover:underline">
              Settings
            </Link>
            {" → "}Studio
          </p>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Studio</h1>
          <p className="text-sm text-[var(--text-primary)]/60">
            Extra columns, form layout, and print templates for every tenant. Install{" "}
            <Link href="/apps?tab=marketplace" className="text-[var(--primary)] underline">
              Weighbridge
            </Link>{" "}
            from Add-ons → Marketplace for gate pass + lot on invoices (traders, mills, and other
            segments). Marketplace listings apply a declarative bundle on Install — no partner code
            runs in-process.
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
  const [catalog, setCatalog] = useState<FieldCatalog | null>(null)
  const [form, setForm] = useState({ key: 'x.', label: '', type: 'text', show_on_print: false, required: false })

  const load = useCallback(() => {
    Promise.all([
      apiFetch<FieldDef[]>(`/api/studio/fields?entity=${entity}`),
      apiFetch<FieldCatalog>(`/api/studio/fields/catalog?entity=${entity}`),
    ]).then(([defs, cat]) => {
      setRows(defs)
      setCatalog(cat)
    }).catch(e => onError(String(e)))
  }, [entity, onError])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    setForm({ key: 'x.', label: '', type: 'text', show_on_print: false, required: false })
  }, [entity])

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

  const cap = catalog?.cap ?? 12
  const used = catalog?.used ?? rows.length
  const atCap = used >= cap

  return (
    <div className="space-y-4">
      <EntityPicker value={entity} onChange={setEntity} />
      <div className="flex items-start gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-page)] px-4 py-3 text-sm text-[var(--text-primary)]/70">
        <Info className="w-4 h-4 mt-0.5 text-[var(--primary)] flex-shrink-0" />
        <div>
          Extra columns on <span className="font-medium text-[var(--text-primary)]">{entity}</span>
          {" "}({used} of {cap} used). Pick a type hint from the list or type a new{" "}
          <code className="font-mono text-xs">x.*</code> key. Values never post to the GL.
          Hide or require shipped form fields on the <span className="font-medium">Form layout</span> tab.
        </div>
      </div>
      <div className="bg-white rounded-xl border border-[var(--border)] p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-semibold text-[var(--text-primary)]">Add field</div>
          <div className="text-xs text-[var(--text-primary)]/50">{used} / {cap}</div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <FieldKeyLov
            value={form.key}
            suggestions={catalog?.suggestions || []}
            disabled={atCap}
            onChange={(key, picked) => setForm(f => ({
              ...f,
              key,
              label: picked?.label ?? f.label,
              type: picked?.type ?? f.type,
            }))}
          />
          <input
            value={form.label}
            onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
            placeholder="Label"
            disabled={atCap}
            className="px-3 py-2 bg-[var(--bg-page)] rounded-lg text-sm"
          />
          <select
            value={form.type}
            onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
            disabled={atCap}
            className="px-3 py-2 bg-[var(--bg-page)] rounded-lg text-sm"
          >
            {['text', 'number', 'date', 'bool', 'enum'].map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <button
            onClick={add}
            disabled={atCap}
            className="flex items-center justify-center gap-2 px-3 py-2 bg-[var(--text-primary)] text-white rounded-lg text-sm font-medium disabled:opacity-40"
          >
            <Plus className="w-4 h-4" /> Add
          </button>
        </div>
        {atCap && (
          <p className="text-xs text-amber-800">This entity already has {cap} extra fields. Archive one to add another.</p>
        )}
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
              <div className="text-xs font-mono text-[var(--text-primary)]/50">{r.key} · {r.type}{r.required ? ' · required' : ''}</div>
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

function FieldKeyLov({
  value, suggestions, disabled, onChange,
}: {
  value: string
  suggestions: Suggestion[]
  disabled?: boolean
  onChange: (key: string, picked?: Suggestion) => void
}) {
  const [open, setOpen] = useState(false)
  const [hi, setHi] = useState(0)
  const wrapRef = useRef<HTMLDivElement>(null)

  const q = value.trim().toLowerCase()
  const filtered = useMemo(() => {
    return suggestions.filter(s => {
      if (!q || q === 'x.') return true
      return s.key.toLowerCase().includes(q) || s.label.toLowerCase().includes(q) || s.hint.toLowerCase().includes(q)
    })
  }, [suggestions, q])

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  useEffect(() => { setHi(0) }, [q, open])

  const pick = (s: Suggestion) => {
    if (s.added || s.archived) return
    onChange(s.key, s)
    setOpen(false)
  }

  return (
    <div ref={wrapRef} className="relative">
      <input
        value={value}
        disabled={disabled}
        onChange={e => { onChange(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={e => {
          if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) {
            setOpen(true)
            return
          }
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setHi(i => Math.min(i + 1, Math.max(filtered.length - 1, 0)))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setHi(i => Math.max(i - 1, 0))
          } else if (e.key === 'Enter') {
            const s = filtered[hi]
            if (s && !s.added && !s.archived) {
              e.preventDefault()
              pick(s)
            }
          } else if (e.key === 'Escape') {
            setOpen(false)
          }
        }}
        placeholder="x.gate_pass_no"
        className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-lg text-sm font-mono"
        autoComplete="off"
        aria-label="Field key"
        aria-autocomplete="list"
        aria-expanded={open}
      />
      {open && filtered.length > 0 && (
        <div className="absolute z-20 mt-1 w-full min-w-[18rem] sm:min-w-[22rem] max-h-64 overflow-auto rounded-lg border border-[var(--border)] bg-white shadow-lg">
          {filtered.map((s, i) => {
            const blocked = s.added || s.archived
            return (
              <button
                type="button"
                key={s.key}
                disabled={blocked}
                onMouseEnter={() => setHi(i)}
                onClick={() => pick(s)}
                className={`w-full text-left px-3 py-2 border-b border-[var(--border)] last:border-0 disabled:opacity-50 ${
                  i === hi ? 'bg-[var(--bg-page)]' : ''
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">{s.label}</span>
                  <span className="text-[10px] font-mono text-[var(--text-primary)]/50">{s.type}</span>
                </div>
                <div className="text-xs font-mono text-[var(--text-primary)]/50">{s.key}</div>
                <div className="text-[11px] text-[var(--text-primary)]/55 mt-0.5">
                  {s.added ? 'Already added' : s.archived ? 'Archived — key is taken' : s.hint}
                </div>
              </button>
            )
          })}
        </div>
      )}
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
  const [catalog, setCatalog] = useState<FieldCatalog | null>(null)
  const [draft, setDraft] = useState<Record<string, { visible: boolean; required: boolean }>>({})
  const [filter, setFilter] = useState('')

  const load = useCallback(() => {
    Promise.all([
      apiFetch<FormSchema>(`/api/studio/forms/${entity}`),
      apiFetch<FieldCatalog>(`/api/studio/fields/catalog?entity=${entity}`),
    ]).then(([s, cat]) => {
      setSchema(s)
      setCatalog(cat)
      const next: Record<string, { visible: boolean; required: boolean }> = {}
      for (const f of cat.form_fields) {
        const cfg = s.schema?.fields?.[f.key] || {}
        next[f.key] = { visible: cfg.visible !== false, required: cfg.required === true }
      }
      setDraft(next)
    }).catch(e => onError(String(e)))
  }, [entity, onError])

  useEffect(() => { load() }, [load])
  useEffect(() => { setFilter('') }, [entity])

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

  const q = filter.trim().toLowerCase()
  const rows = (catalog?.form_fields || []).filter(r => {
    if (!q) return true
    return r.key.toLowerCase().includes(q) || r.label.toLowerCase().includes(q) || r.hint.toLowerCase().includes(q)
  })
  const locked = new Set(schema?.locked || [])

  return (
    <div className="space-y-4">
      <EntityPicker value={entity} onChange={setEntity} />
      <div className="flex items-start gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-page)] px-4 py-3 text-sm text-[var(--text-primary)]/70">
        <Info className="w-4 h-4 mt-0.5 text-[var(--primary)] flex-shrink-0" />
        <div>
          Hide or require fields on the shipped {entity} form. Locked keys (dates, party, totals)
          stay visible so posting still balances. Extra <code className="font-mono text-xs">x.*</code> columns
          can be required here without touching the GL.
        </div>
      </div>
      <input
        value={filter}
        onChange={e => setFilter(e.target.value)}
        placeholder="Filter fields…"
        className="w-full px-3 py-2 bg-white border border-[var(--border)] rounded-lg text-sm"
      />
      <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
        {rows.length === 0 && (
          <div className="px-4 py-8 text-sm text-[var(--text-primary)]/50 text-center">No matching fields.</div>
        )}
        {rows.map(r => {
          const isLocked = locked.has(r.key) || r.locked
          const cfg = draft[r.key] || { visible: true, required: false }
          return (
            <div key={r.key} className="flex items-center justify-between gap-3 px-4 py-3 border-b border-[var(--border)] last:border-0">
              <div className="min-w-0">
                <div className="text-sm text-[var(--text-primary)] flex items-center gap-1.5">
                  {r.label}
                  {isLocked && <Lock className="w-3 h-3 text-[var(--text-primary)]/40" />}
                </div>
                <div className="text-xs font-mono text-[var(--text-primary)]/40">
                  {r.key} · {r.type}{r.kind === 'custom' ? ' · extra' : ''}
                </div>
                <div className="text-[11px] text-[var(--text-primary)]/50 mt-0.5">{r.hint}</div>
              </div>
              <div className="flex items-center gap-4 text-sm flex-shrink-0">
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
  const [cloneKey, setCloneKey] = useState('x.packing')
  const [cloneLabel, setCloneLabel] = useState('Packing')

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
