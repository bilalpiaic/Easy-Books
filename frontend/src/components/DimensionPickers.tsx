"use client"

/** Shared multi-dimension analytic pickers (#260). */

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

export interface AnalyticDimension {
  id: number
  code: string
  name: string
  required: boolean
  sort_order: number
  is_active: boolean
}

export interface AnalyticAccount {
  id: number
  code: string
  name: string
  type?: string
  dimension_id?: number | null
  is_active?: boolean
}

export type AnalyticSlots = {
  /** slot index 0–2 → analytic id as string ("" = none) */
  [slot: number]: string
}

export function slotsToPayload(slots: AnalyticSlots): {
  analytic_account_id: number | null
  analytic_2_id: number | null
  analytic_3_id: number | null
  analytic_ids: number[]
} {
  const ids = [0, 1, 2].map(i => {
    const v = slots[i]
    return v ? parseInt(v, 10) : null
  })
  return {
    analytic_account_id: ids[0],
    analytic_2_id: ids[1],
    analytic_3_id: ids[2],
    analytic_ids: ids.filter((x): x is number => x != null),
  }
}

export function useAnalyticDimensions() {
  const [dimensions, setDimensions] = useState<AnalyticDimension[]>([])
  const [accounts, setAccounts] = useState<AnalyticAccount[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      apiFetch<{ items: AnalyticDimension[] }>("/api/analytic-dimensions").catch(() => ({ items: [] })),
      apiFetch<{ items: AnalyticAccount[] } | AnalyticAccount[]>("/api/analytic-accounts?limit=500")
        .catch(() => ({ items: [] as AnalyticAccount[] })),
    ]).then(([dims, an]) => {
      if (cancelled) return
      setDimensions((dims.items ?? []).filter(d => d.is_active).sort((a, b) => a.sort_order - b.sort_order))
      const items = Array.isArray(an) ? an : (an.items ?? [])
      setAccounts(items.filter(a => a.is_active !== false))
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  return { dimensions, accounts, loading }
}

export function DimensionPickers({
  slots,
  onChange,
  className = "",
}: {
  slots: AnalyticSlots
  onChange: (next: AnalyticSlots) => void
  className?: string
}) {
  const { dimensions, accounts, loading } = useAnalyticDimensions()

  if (loading || dimensions.length === 0) {
    // Fall back to flat list when no dimensions configured yet
    if (!loading && accounts.length > 0 && dimensions.length === 0) {
      return (
        <div className={className}>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
            Analytic Account <span className="font-normal normal-case">(optional)</span>
          </label>
          <select
            value={slots[0] ?? ""}
            onChange={e => onChange({ ...slots, 0: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
          >
            <option value="">— none —</option>
            {accounts.map(a => (
              <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
            ))}
          </select>
        </div>
      )
    }
    return null
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {dimensions.map(dim => {
        const opts = accounts.filter(a => a.dimension_id == null || a.dimension_id === dim.id)
        return (
          <div key={dim.id}>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
              {dim.name}
              {dim.required
                ? <span className="text-red-600"> *</span>
                : <span className="font-normal normal-case"> (optional)</span>}
            </label>
            <select
              value={slots[dim.sort_order] ?? ""}
              onChange={e => onChange({ ...slots, [dim.sort_order]: e.target.value })}
              required={dim.required}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            >
              <option value="">{dim.required ? "— select —" : "— none —"}</option>
              {opts.map(a => (
                <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
              ))}
            </select>
          </div>
        )
      })}
    </div>
  )
}
