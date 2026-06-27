"use client"

import { useState } from "react"
import { Loader2, CheckCircle2 } from "lucide-react"
import { apiFetch } from "@/lib/api"

export interface SelectOption {
  value: string
  label: string
}

export type FieldDef =
  | {
      kind: "text" | "number" | "date"
      name: string
      label: string
      required?: boolean
      default?: string
      placeholder?: string
      step?: string
      help?: string
    }
  | {
      kind: "select"
      name: string
      label: string
      required?: boolean
      default?: string
      options: SelectOption[]
      help?: string
    }

interface ActionFormProps {
  /** POST target, e.g. "/api/telecom/tracker/deposits". */
  endpoint: string
  fields: FieldDef[]
  submitLabel: string
  /** Called after a successful POST so the caller can refetch lists. */
  onSuccess?: (result: unknown) => void
  /** Optional short message shown after success (defaults to JV summary). */
  successText?: (result: unknown) => string
}

function initialValues(fields: FieldDef[]): Record<string, string> {
  return Object.fromEntries(fields.map(f => [f.name, f.default ?? ""]))
}

function coerce(fields: FieldDef[], values: Record<string, string>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const f of fields) {
    const raw = values[f.name]
    if (raw === "" || raw === undefined) continue          // omit empties → backend defaults
    out[f.name] = f.kind === "number" ? Number(raw) : raw
  }
  return out
}

/** Default success summary: surface the GL JV number when the API returns one. */
function defaultSuccess(result: unknown): string {
  const r = result as { transaction?: { jv_number?: string }; jv_number?: string }
  const jv = r?.transaction?.jv_number ?? r?.jv_number
  return jv ? `Posted — JV ${jv}` : "Saved."
}

export function ActionForm({
  endpoint, fields, submitLabel, onSuccess, successText,
}: ActionFormProps) {
  const [values, setValues] = useState<Record<string, string>>(() => initialValues(fields))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const set = (name: string, v: string) =>
    setValues(prev => ({ ...prev, [name]: v }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setOk(null)
    try {
      const result = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(coerce(fields, values)),
      })
      setOk((successText ?? defaultSuccess)(result))
      setValues(initialValues(fields))
      onSuccess?.(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="bg-white border border-[var(--border)] rounded-2xl p-4 space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {fields.map(f => (
          <label key={f.name} className="block">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-primary)]/55">
              {f.label}{f.required && <span className="text-red-500"> *</span>}
            </span>
            {f.kind === "select" ? (
              <select
                value={values[f.name]}
                required={f.required}
                onChange={e => set(f.name, e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm focus:border-[var(--primary)] focus:outline-none"
              >
                <option value="">Select…</option>
                {f.options.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            ) : (
              <input
                type={f.kind}
                value={values[f.name]}
                required={f.required}
                placeholder={f.placeholder}
                step={f.kind === "number" ? (f.step ?? "0.01") : undefined}
                onChange={e => set(f.name, e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm focus:border-[var(--primary)] focus:outline-none"
              />
            )}
            {f.help && <span className="block mt-0.5 text-[10px] text-[var(--text-primary)]/45">{f.help}</span>}
          </label>
        ))}
      </div>

      {error && (
        <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
      )}
      {ok && (
        <p className="flex items-center gap-1.5 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
          <CheckCircle2 className="w-4 h-4" /> {ok}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--primary)] text-black text-sm font-bold hover:bg-[#d4af60] transition-colors disabled:opacity-60"
      >
        {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
        {submitLabel}
      </button>
    </form>
  )
}
