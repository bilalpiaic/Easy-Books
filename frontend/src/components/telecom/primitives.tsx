"use client"

import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

// ── Tabs ──────────────────────────────────────────────────────────────────────

export function Tabs({ tabs }: { tabs: { id: string; label: string; content: React.ReactNode }[] }) {
  const [active, setActive] = useState(tabs[0]?.id)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5 border-b border-[var(--border)]">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            className={
              "px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors " +
              (active === t.id
                ? "border-[var(--primary)] text-[var(--text-primary)]"
                : "border-transparent text-[var(--text-primary)]/55 hover:text-[var(--text-primary)]")
            }
          >
            {t.label}
          </button>
        ))}
      </div>
      {tabs.find(t => t.id === active)?.content}
    </div>
  )
}

// ── Formatting ─────────────────────────────────────────────────────────────

/** Format a decimal-string / number as a 2dp grouped amount. "—" when empty. */
export function money(v?: string | number | null): string {
  if (v === null || v === undefined || v === "") return "—"
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// ── Data fetching ────────────────────────────────────────────────────────────

interface ListResponse<T> {
  items: T[]
  total: number
}

/** Fetch a `{ items, total }` list endpoint. Returns rows + a refetch fn. */
export function useTelecomList<T>(path: string): {
  items: T[]
  loading: boolean
  error: string | null
  refetch: () => void
} {
  const [items, setItems] = useState<T[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(() => {
    setLoading(true)
    apiFetch<ListResponse<T>>(path)
      .then(d => { setItems(d.items ?? []); setError(null) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [path])

  useEffect(() => { refetch() }, [refetch])

  return { items, loading, error, refetch }
}

// ── Layout primitives ────────────────────────────────────────────────────────

interface TileProps {
  icon: React.ElementType
  label: string
  value: string
  hint?: string
  /** When set, the tile becomes a link (e.g. to the account's ledger). */
  href?: string
}

export function Tile({ icon: Icon, label, value, hint, href }: TileProps) {
  const inner = (
    <>
      <div className="w-10 h-10 rounded-lg bg-[var(--bg-page)] border border-[var(--primary)]/30 flex items-center justify-center shrink-0">
        <Icon className="w-5 h-5 text-[var(--primary)]" />
      </div>
      <div className="min-w-0">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-primary)]/55">{label}</div>
        <div className="text-lg font-bold text-[var(--text-primary)] truncate">{value}</div>
        {hint && <div className="text-[10px] text-[var(--text-primary)]/45 truncate">{hint}</div>}
      </div>
    </>
  )
  const cls = "bg-white border border-[var(--border)] rounded-xl px-4 py-3 flex items-center gap-3"
  if (href) {
    return (
      <a href={href} className={`${cls} hover:border-[var(--primary)]/60 transition-colors`}>{inner}</a>
    )
  }
  return <div className={cls}>{inner}</div>
}

export function Section({ title, children, action }: {
  title: string
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]/50">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

export function PageHeader({ icon: Icon, title, subtitle }: {
  icon: React.ElementType
  title: string
  subtitle: string
}) {
  return (
    <header className="flex items-center gap-3">
      <Icon className="w-7 h-7 text-[var(--primary)]" />
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">{title}</h1>
        <p className="text-sm text-[var(--text-primary)]/60">{subtitle}</p>
      </div>
    </header>
  )
}

export function ErrorBanner({ error }: { error: string | null }) {
  if (!error) return null
  return (
    <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
      {error}
    </div>
  )
}

// ── Simple table ──────────────────────────────────────────────────────────────

export interface Column<T> {
  header: string
  cell: (row: T) => React.ReactNode
  mono?: boolean
}

export function DataTable<T>({ columns, rows, empty }: {
  columns: Column<T>[]
  rows: T[]
  empty?: string
}) {
  if (rows.length === 0) {
    return (
      <div className="bg-white border border-[var(--border)] rounded-2xl px-4 py-8 text-center text-sm text-[var(--text-primary)]/50">
        {empty ?? "Nothing here yet."}
      </div>
    )
  }
  return (
    <div className="bg-white border border-[var(--border)] rounded-2xl overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-[var(--bg-page)] text-[var(--text-primary)]/70 text-xs uppercase tracking-wide">
          <tr>
            {columns.map((c, i) => (
              <th key={i} className="text-left px-4 py-2 font-semibold whitespace-nowrap">{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="border-t border-[var(--border)]">
              {columns.map((c, ci) => (
                <td key={ci} className={`px-4 py-2 ${c.mono ? "font-mono text-xs" : ""}`}>
                  {c.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
