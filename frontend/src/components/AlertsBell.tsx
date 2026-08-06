"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  Bell, CheckCheck, AlertTriangle, Package, ClipboardCheck, Info, X, MessageSquareWarning, Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { useSettings } from "@/context/SettingsContext"

interface AlertRow {
  id: number
  kind: string
  severity: string
  title: string
  body?: string | null
  href?: string | null
  created_at?: string | null
  read_at?: string | null
  unread: boolean
}

function relativeTime(iso?: string | null): string {
  if (!iso) return ""
  const t = new Date(iso.endsWith("Z") ? iso : iso + "Z").getTime()
  if (Number.isNaN(t)) return ""
  const sec = Math.max(0, Math.floor((Date.now() - t) / 1000))
  if (sec < 60) return "just now"
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`
  if (sec < 86400 * 7) return `${Math.floor(sec / 86400)}d ago`
  return new Date(t).toLocaleDateString()
}

function KindIcon({ kind, severity }: { kind: string; severity: string }) {
  const cls = severity === "critical"
    ? "text-red-600"
    : severity === "info"
      ? "text-blue-600"
      : "text-amber-600"
  if (kind === "low_stock") return <Package className={cn("w-3.5 h-3.5", cls)} />
  if (kind === "approval_needed") return <ClipboardCheck className={cn("w-3.5 h-3.5", cls)} />
  if (kind === "overdue_invoice") return <AlertTriangle className={cn("w-3.5 h-3.5", cls)} />
  if (kind === "invoice_dispute") return <MessageSquareWarning className={cn("w-3.5 h-3.5", cls)} />
  if (kind === "system") return <Sparkles className={cn("w-3.5 h-3.5", cls)} />
  return <Info className={cn("w-3.5 h-3.5", cls)} />
}

export default function AlertsBell() {
  const router = useRouter()
  const { settings } = useSettings()
  const enabled = (settings.in_app_alerts ?? "true") !== "false"

  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(0)
  const [items, setItems] = useState<AlertRow[]>([])
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const fetchCount = useCallback(() => {
    if (!enabled) { setCount(0); return }
    apiFetch<{ count: number; enabled?: boolean }>("/api/alerts/unread-count")
      .then(d => setCount(d.enabled === false ? 0 : d.count))
      .catch(() => { /* ignore */ })
  }, [enabled])

  const fetchList = useCallback(() => {
    if (!enabled) return
    setLoading(true)
    apiFetch<{ items: AlertRow[] }>("/api/alerts?limit=30")
      .then(d => setItems(d.items ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [enabled])

  // Sync shipped app updates into this user's Alerts inbox (no popup).
  // Covers login + mid-session deploys; mark-as-read in the bell is the ack.
  const syncUpdateNotices = useCallback(() => {
    if (!enabled) return
    apiFetch<{ items?: unknown[] }>("/api/system/update/notices")
      .then(() => fetchCount())
      .catch(() => { /* never block the app */ })
  }, [enabled, fetchCount])

  useEffect(() => {
    if (!enabled) return
    syncUpdateNotices()
    fetchCount()
    const countTimer = setInterval(fetchCount, 60_000)
    const noticeTimer = setInterval(syncUpdateNotices, 180_000)
    const onRefresh = () => fetchCount()
    window.addEventListener("alerts:refresh", onRefresh)
    return () => {
      clearInterval(countTimer)
      clearInterval(noticeTimer)
      window.removeEventListener("alerts:refresh", onRefresh)
    }
  }, [enabled, fetchCount, syncUpdateNotices])

  useEffect(() => {
    if (open) {
      syncUpdateNotices()
      fetchList()
      fetchCount()
    }
  }, [open, fetchList, fetchCount, syncUpdateNotices])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onDoc)
    return () => document.removeEventListener("mousedown", onDoc)
  }, [open])

  if (!enabled) return null

  const markRead = async (id: number) => {
    try {
      await apiFetch(`/api/alerts/${id}/read`, { method: "PATCH" })
      setItems(prev => prev.map(a => a.id === id ? { ...a, unread: false, read_at: new Date().toISOString() } : a))
      setCount(c => Math.max(0, c - 1))
    } catch { /* ignore */ }
  }

  const markAll = async () => {
    try {
      await apiFetch("/api/alerts/read-all", { method: "POST" })
      setItems(prev => prev.map(a => ({ ...a, unread: false, read_at: a.read_at ?? new Date().toISOString() })))
      setCount(0)
    } catch { /* ignore */ }
  }

  const openAlert = async (a: AlertRow) => {
    if (a.unread) await markRead(a.id)
    // App-update / system notices: body is already in the row — reading acks them.
    if (a.kind === "system" || !a.href || a.href === "/alerts") return
    setOpen(false)
    router.push(a.href)
  }

  const badge = count > 9 ? "9+" : count > 0 ? String(count) : null

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        title="Alerts"
        className="relative w-7 h-7 flex items-center justify-center rounded-full text-[var(--nav-dim)] hover:text-[var(--nav-text)] hover:bg-[var(--nav-icon-hover)] transition-colors"
      >
        <Bell className="w-4 h-4" />
        {badge && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] px-0.5 rounded-full bg-red-600 text-white text-[9px] font-bold flex items-center justify-center leading-none">
            {badge}
          </span>
        )}
      </button>

      {open && (
        <div
          className={cn(
            "bg-[var(--bg-card)] border border-[var(--border)] rounded-xl shadow-xl z-[100] overflow-hidden",
            // SM: pin to viewport under the header so a near-full-width sheet
            // doesn't overflow left of the bell (theme + avatar sit to its right).
            "fixed left-3 right-3 top-[56px] w-auto max-w-none",
            // md+: classic dropdown anchored to the bell's right edge
            "md:absolute md:left-auto md:right-0 md:top-full md:mt-1 md:w-[360px] md:max-w-[calc(100vw-24px)]",
          )}
        >
          <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[var(--border)]">
            <div className="text-[13px] font-semibold text-[var(--text-primary)]">Alerts</div>
            <div className="flex items-center gap-1">
              {count > 0 && (
                <button
                  type="button"
                  onClick={markAll}
                  className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-[var(--text-muted)] hover:text-[var(--primary)] hover:bg-[var(--bg-page)] transition-colors"
                >
                  <CheckCheck className="w-3 h-3" /> Mark all read
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1 rounded-md text-[var(--text-muted)] hover:bg-[var(--bg-page)]"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div className="max-h-[380px] overflow-y-auto">
            {loading && items.length === 0 && (
              <div className="px-4 py-8 text-center text-[12px] text-[var(--text-muted)]">Loading…</div>
            )}
            {!loading && items.length === 0 && (
              <div className="px-4 py-10 text-center">
                <Bell className="w-7 h-7 mx-auto mb-2 text-[var(--text-muted)]/40" />
                <p className="text-[13px] text-[var(--text-muted)]">You&apos;re all caught up</p>
              </div>
            )}
            {items.map(a => (
              <button
                key={a.id}
                type="button"
                onClick={() => openAlert(a)}
                className={cn(
                  "w-full text-left flex gap-2.5 px-3.5 py-2.5 border-b border-[var(--border-light)] last:border-0 transition-colors",
                  a.unread
                    ? "bg-[var(--primary)]/5 hover:bg-[var(--primary)]/10"
                    : "hover:bg-[var(--bg-page)]",
                )}
              >
                <div className="mt-0.5 w-7 h-7 rounded-md bg-[var(--bg-page)] flex items-center justify-center shrink-0">
                  <KindIcon kind={a.kind} severity={a.severity} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start gap-1.5">
                    <span className={cn(
                      "text-[12.5px] leading-snug truncate",
                      a.unread ? "font-semibold text-[var(--text-primary)]" : "text-[var(--text-primary)]",
                    )}>
                      {a.title}
                    </span>
                    {a.unread && (
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-[var(--primary)] shrink-0" />
                    )}
                  </div>
                  {a.body && (
                    <div className={cn(
                      "text-[11px] text-[var(--text-muted)] mt-0.5",
                      a.kind === "system" ? "whitespace-normal line-clamp-3" : "truncate",
                    )}>
                      {a.body}
                    </div>
                  )}
                  <div className="text-[10px] text-[var(--text-muted)] mt-0.5">{relativeTime(a.created_at)}</div>
                </div>
              </button>
            ))}
          </div>

          <div className="border-t border-[var(--border)] px-3.5 py-2">
            <Link
              href="/alerts"
              onClick={() => setOpen(false)}
              className="block text-center text-[12px] font-medium text-[var(--primary)] hover:underline"
            >
              View all alerts
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
