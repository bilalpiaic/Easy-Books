"use client"

/**
 * Pull a weighbridge ticket onto any stock-movement form.
 * Hidden unless the Weighbridge module is installed (every tenant can
 * install it; mills have it pre-installed).
 */

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Scale, X } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useModules } from "@/context/ModuleContext"
import { fmtDate } from "@/lib/utils"

export type WbTicketSnap = {
  id: number
  number: string
  ticket_date: string
  direction: string
  vehicle_no: string
  driver_name: string | null
  party_type?: string
  party_id?: number | null
  party_name: string | null
  commodity: string | null
  lot_ref: string | null
  gross_kg: number
  tare_kg: number
  net_kg: number
  status: string
}

type Pickable = { items: WbTicketSnap[] }

type Props = {
  direction: "inbound" | "outbound"
  value: number | null
  onChange: (ticket: WbTicketSnap | null) => void
  compact?: boolean
  /** Saved document — show linked tickets instead of the picker. */
  docType?: string
  docId?: number
  readOnly?: boolean
}

export function WeighbridgeLinked({ docType, docId }: { docType: string; docId: number }) {
  const { installedModules } = useModules()
  const [items, setItems] = useState<WbTicketSnap[]>([])
  useEffect(() => {
    if (!installedModules.has("weighbridge") || !docId) return
    apiFetch<{ items: WbTicketSnap[] }>(
      `/api/weighbridge/links?doc_type=${encodeURIComponent(docType)}&doc_id=${docId}`,
    )
      .then(d => setItems(Array.isArray(d.items) ? d.items : []))
      .catch(() => setItems([]))
  }, [installedModules, docType, docId])
  if (!installedModules.has("weighbridge") || items.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs print:block">
      <Scale className="w-3.5 h-3.5 text-[var(--primary)]" />
      {items.map(t => (
        <Link
          key={t.id}
          href={`/weighbridge/tickets/${t.id}`}
          className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[var(--text-primary)] hover:border-[var(--primary)]"
        >
          {t.number} · {t.vehicle_no}
          {t.net_kg ? ` · ${Number(t.net_kg).toFixed(0)} kg` : ""}
        </Link>
      ))}
    </div>
  )
}

export default function WeighbridgeAttach({
  direction,
  value,
  onChange,
  compact,
  docType,
  docId,
  readOnly,
}: Props) {
  const { installedModules } = useModules()
  const enabled = installedModules.has("weighbridge")
  const [q, setQ] = useState("")
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<WbTicketSnap[]>([])
  const [selected, setSelected] = useState<WbTicketSnap | null>(null)
  const [loading, setLoading] = useState(false)

  const search = useCallback(async (term: string) => {
    if (!enabled) return
    setLoading(true)
    try {
      const qs = new URLSearchParams({ direction, limit: "12" })
      if (term.trim()) qs.set("q", term.trim())
      const d = await apiFetch<Pickable>(`/api/weighbridge/pickable?${qs}`)
      setItems(Array.isArray(d.items) ? d.items : [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [direction, enabled])

  useEffect(() => {
    if (!enabled || readOnly) return
    const t = window.setTimeout(() => search(q), 180)
    return () => window.clearTimeout(t)
  }, [q, search, enabled, readOnly])

  useEffect(() => {
    if (value == null) setSelected(null)
  }, [value])

  if (!enabled) return null
  if (readOnly && docType && docId) {
    return <WeighbridgeLinked docType={docType} docId={docId} />
  }

  function pick(t: WbTicketSnap) {
    setSelected(t)
    setOpen(false)
    setQ("")
    onChange(t)
  }

  function clear() {
    setSelected(null)
    onChange(null)
  }

  const box = compact
    ? "border border-[var(--border)] rounded-lg p-2 space-y-1.5 bg-[var(--bg)]"
    : "border border-[var(--border)] rounded-xl p-3 space-y-2 bg-[var(--bg-page)]"

  return (
    <div className={`${box} print:hidden`}>
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-[var(--text-muted)]">
        <Scale className="w-3.5 h-3.5 text-[var(--primary)]" />
        Weighbridge {direction}
      </div>
      {selected ? (
        <div className="flex items-start justify-between gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-card)] px-2.5 py-2">
          <div className="min-w-0 text-sm">
            <p className="font-semibold text-[var(--text-primary)] truncate">
              {selected.number} · {selected.vehicle_no}
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              {fmtDate(selected.ticket_date)}
              {selected.net_kg ? ` · net ${Number(selected.net_kg).toFixed(2)} kg` : ""}
              {selected.lot_ref ? ` · ${selected.lot_ref}` : ""}
              {selected.driver_name ? ` · ${selected.driver_name}` : ""}
            </p>
          </div>
          <button type="button" onClick={clear} className="p-1 text-[var(--text-muted)] hover:text-red-600" aria-label="Clear ticket">
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <input
            value={q}
            onChange={e => { setQ(e.target.value); setOpen(true) }}
            onFocus={() => { setOpen(true); if (!items.length) search("") }}
            placeholder="Search ticket / vehicle / lot…"
            className="w-full px-3 py-2 text-sm border border-[var(--border)] rounded-lg bg-[var(--bg-card)] outline-none focus:ring-2 focus:ring-[var(--primary)]"
          />
          {open && (
            <div className="absolute z-20 mt-1 w-full max-h-56 overflow-auto rounded-lg border border-[var(--border)] bg-[var(--bg-card)] shadow-lg">
              {loading && <p className="px-3 py-2 text-xs text-[var(--text-muted)]">Searching…</p>}
              {!loading && items.length === 0 && (
                <p className="px-3 py-2 text-xs text-[var(--text-muted)]">
                  No {direction} tickets. Record a weigh first.
                </p>
              )}
              {items.map(t => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => pick(t)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--bg-page)] border-t border-[var(--border)] first:border-t-0"
                >
                  <span className="font-medium">{t.number}</span>
                  <span className="text-[var(--text-muted)]"> · {t.vehicle_no}</span>
                  {t.net_kg ? <span className="text-[var(--text-muted)]"> · {Number(t.net_kg).toFixed(0)} kg</span> : null}
                  {t.lot_ref ? <span className="block text-[11px] text-[var(--text-muted)]">{t.lot_ref}</span> : null}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
