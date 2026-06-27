'use client'

import { useRef, useState } from 'react'
import { Upload, Download, CheckCircle, XCircle, AlertTriangle, FileText } from 'lucide-react'
import { apiBase } from '@/lib/api'
import { getAuthHeader } from '@/lib/auth'
import { useTranslation } from "react-i18next"

// ── Types ─────────────────────────────────────────────────────────────────────

type Entity = 'accounts' | 'customers' | 'vendors' | 'products' | 'transactions'

interface ValidationResult {
  valid_count: number
  total_rows: number
  errors: { row: number | null; message: string }[]
}

interface ImportResult {
  imported: number
  errors: { row: number | null; message: string }[]
}

// ── Entity metadata ───────────────────────────────────────────────────────────

const ENTITIES: { key: Entity; label: string; columns: string; notes?: string }[] = [
  {
    key: 'accounts',
    label: 'Accounts',
    columns: 'code, name, type, parent_code, is_group, is_memo',
    notes: 'type must be Asset / Liability / Equity / Revenue / Expense. Parent hierarchy is wired in a second pass — any parent_code not present is skipped with a warning.',
  },
  {
    key: 'customers',
    label: 'Customers',
    columns: 'name, email, phone, address, opening_balance',
  },
  {
    key: 'vendors',
    label: 'Vendors',
    columns: 'name, email, phone, address, opening_balance',
  },
  {
    key: 'products',
    label: 'Products',
    columns: 'code, name, unit, product_type, default_rate, reorder_level, category_name, is_deferred, recognition_months',
    notes: 'unit: pcs / kg / mtr / hrs / ltr / box / doz. product_type: stock / service. category_name must match an existing category.',
  },
  {
    key: 'transactions',
    label: 'Transactions',
    columns: 'date, description, account_code, debit, credit, voucher_type',
    notes: 'Rows sharing the same date + description form one journal entry. voucher_type: JV / SL / PU / CR / CP / CN / DN (default JV).',
  },
]

// ── Per-entity panel ──────────────────────────────────────────────────────────

function EntityPanel({ entity }: { entity: typeof ENTITIES[number] }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [validating, setValidating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [error, setError] = useState('')

  const reset = () => {
    setFile(null)
    setValidation(null)
    setResult(null)
    setError('')
    if (fileRef.current) fileRef.current.value = ''
  }

  const downloadSample = async () => {
    const res = await fetch(`${apiBase}/api/import/${entity.key}/sample`, {
      headers: getAuthHeader(),
    })
    if (!res.ok) return
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sample_${entity.key}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const validate = async () => {
    if (!file) return
    setValidating(true); setError(''); setValidation(null); setResult(null)
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${apiBase}/api/import/${entity.key}/validate`, {
        method: 'POST', body: fd, headers: getAuthHeader(),
      })
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail ?? `HTTP ${res.status}`) }
      setValidation(await res.json())
    } catch (e) { setError((e as Error).message) } finally { setValidating(false) }
  }

  const doImport = async () => {
    if (!file) return
    setImporting(true); setError(''); setResult(null)
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${apiBase}/api/import/${entity.key}`, {
        method: 'POST', body: fd, headers: getAuthHeader(),
      })
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail ?? `HTTP ${res.status}`) }
      setResult(await res.json())
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
    } catch (e) { setError((e as Error).message) } finally { setImporting(false) }
  }

  const canImport = validation !== null && validation.valid_count > 0

  return (
    <div className="space-y-6">
      {/* Column guide */}
      <div className="bg-[var(--bg-page)] border border-[var(--border)] rounded-xl p-4">
        <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Required columns</p>
        <code className="text-sm text-[var(--text-primary)] font-mono break-all">{entity.columns}</code>
        {entity.notes && (
          <p className="text-xs text-[var(--text-primary)]/60 mt-2">{entity.notes}</p>
        )}
      </div>

      {/* Sample download */}
      <div className="flex items-center gap-3">
        <button
          onClick={downloadSample}
          className="flex items-center gap-2 px-4 py-2 border border-[var(--primary)] text-[var(--primary)] rounded-xl text-sm font-bold hover:bg-[var(--primary)]/10 transition-colors"
        >
          <Download className="w-4 h-4" />
          Download sample CSV
        </button>
        <span className="text-xs text-[var(--text-primary)]/50">Shows the correct column format with example rows</span>
      </div>

      {/* File picker */}
      <div>
        <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-2">
          Select CSV file
        </label>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 px-4 py-2 bg-[var(--text-primary)] text-white rounded-xl text-sm font-bold cursor-pointer hover:bg-[var(--primary)] hover:text-black transition-all">
            <Upload className="w-4 h-4" />
            Choose file
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={e => { reset(); const f = e.target.files?.[0] ?? null; setFile(f) }}
            />
          </label>
          {file && (
            <span className="text-sm text-[var(--text-primary)]/75 flex items-center gap-1">
              <FileText className="w-4 h-4" /> {file.name}
            </span>
          )}
        </div>
      </div>

      {/* Validate + Import actions */}
      {file && (
        <div className="flex flex-wrap gap-3">
          <button
            onClick={validate}
            disabled={validating}
            className="flex items-center gap-2 px-5 py-2.5 border border-[var(--text-primary)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-50"
          >
            {validating ? 'Validating…' : 'Validate'}
          </button>
          {canImport && (
            <button
              onClick={doImport}
              disabled={importing}
              className="flex items-center gap-2 px-5 py-2.5 bg-[var(--text-primary)] text-white rounded-xl text-sm font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50"
            >
              {importing ? 'Importing…' : `Import ${validation!.valid_count} row${validation!.valid_count !== 1 ? 's' : ''}`}
            </button>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Validation result */}
      {validation && (
        <div className="space-y-3">
          <div className={`flex items-center gap-2 p-3 rounded-xl text-sm font-bold ${
            validation.errors.length === 0
              ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
              : 'bg-amber-50 border border-amber-200 text-amber-800'
          }`}>
            {validation.errors.length === 0
              ? <CheckCircle className="w-4 h-4 shrink-0" />
              : <AlertTriangle className="w-4 h-4 shrink-0" />
            }
            {validation.valid_count} of {validation.total_rows} row{validation.total_rows !== 1 ? 's' : ''} valid
            {validation.errors.length > 0 && ` — ${validation.errors.length} error${validation.errors.length !== 1 ? 's' : ''}`}
          </div>

          {validation.errors.length > 0 && (
            <div className="border border-[var(--border)] rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-[var(--bg-page)]">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 w-16">Row</th>
                    <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Issue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {validation.errors.map((e, i) => (
                    <tr key={i} className="hover:bg-[var(--bg-page)]/50">
                      <td className="px-4 py-2 text-[var(--text-primary)]/50 font-mono">{e.row ?? '—'}</td>
                      <td className="px-4 py-2 text-red-700">{e.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Import result */}
      {result && (
        <div className="space-y-3">
          <div className={`flex items-center gap-2 p-3 rounded-xl text-sm font-bold ${
            result.imported > 0
              ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            {result.imported > 0
              ? <CheckCircle className="w-4 h-4 shrink-0" />
              : <XCircle className="w-4 h-4 shrink-0" />
            }
            {result.imported} record{result.imported !== 1 ? 's' : ''} imported successfully
            {result.errors.length > 0 && ` — ${result.errors.length} error${result.errors.length !== 1 ? 's' : ''} skipped`}
          </div>

          {result.errors.length > 0 && (
            <div className="border border-[var(--border)] rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-[var(--bg-page)]">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 w-16">Row</th>
                    <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Issue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {result.errors.map((e, i) => (
                    <tr key={i} className="hover:bg-[var(--bg-page)]/50">
                      <td className="px-4 py-2 text-[var(--text-primary)]/50 font-mono">{e.row ?? '—'}</td>
                      <td className="px-4 py-2 text-red-700">{e.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ImportsPage() {
  const { t } = useTranslation()

  const [active, setActive] = useState<Entity>('accounts')
  const entity = ENTITIES.find(e => e.key === active)!

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">CSV Bulk Import</h1>
        <p className="text-sm text-[var(--text-primary)]/60 mt-1">
          Upload a CSV file to bulk-create records. Validate first to check for errors before committing.
        </p>
      </div>

      {/* Entity tabs */}
      <div className="flex flex-wrap gap-2">
        {ENTITIES.map(e => (
          <button
            key={e.key}
            onClick={() => setActive(e.key)}
            className={`px-4 py-2 rounded-xl text-sm font-bold transition-colors ${
              active === e.key
                ? 'bg-[var(--text-primary)] text-white'
                : 'bg-[var(--bg-page)] text-[var(--text-primary)]/70 hover:bg-[var(--border)]'
            }`}
          >
            {e.label}
          </button>
        ))}
      </div>

      {/* Active entity panel */}
      <div className="bg-white border border-[var(--border)] rounded-2xl p-6">
        <h2 className="text-lg font-bold text-[var(--text-primary)] mb-5">{entity.label}</h2>
        <EntityPanel key={active} entity={entity} />
      </div>
    </div>
  )
}
