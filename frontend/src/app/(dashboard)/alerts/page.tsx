"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  Bell, CheckCheck, AlertTriangle, Package, ClipboardCheck, Info, MessageSquareWarning, Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { useSettings } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"

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

function KindIcon({ kind, severity }: { kind: string; severity: string }) {
  const cls = severity === "critical"
    ? "text-red-600"
    : severity === "info"
      ? "text-blue-600"
      : "text-amber-600"
  if (kind === "low_stock") return <Package className={cn("w-4 h-4", cls)} />
  if (kind === "approval_needed") return <ClipboardCheck className={cn("w-4 h-4", cls)} />
  if (kind === "overdue_invoice") return <AlertTriangle className={cn("w-4 h-4", cls)} />
  if (kind === "invoice_dispute") return <MessageSquareWarning className={cn("w-4 h-4", cls)} />
  if (kind === "system") return <Sparkles className={cn("w-4 h-4", cls)} />
  return <Info className={cn("w-4 h-4", cls)} />
}

function fmtWhen(iso?: string | null): string {
  if (!iso) return ""
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z")
  if (Number.isNaN(d.getTime())) return ""
  const dd = String(d.getDate()).padStart(2, "0")
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  const yy = String(d.getFullYear()).slice(-2)
  const hh = String(d.getHours()).padStart(2, "0")
  const mi = String(d.getMinutes()).padStart(2, "0")
  return `${dd}-${mm}-${yy} ${hh}:${mi}`
}

export default function AlertsPage() {
  const router = useRouter()
  const { settings } = useSettings()
  const enabled = (settings.in_app_alerts ?? "true") !== "false"
  const [items, setItems] = useState<AlertRow[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [unreadOnly, setUnreadOnly] = useState(false)

  const load = useCallback(() => {
    if (!enabled) { setLoading(false); setItems([]); return }
    setLoading(true)
    const q = unreadOnly ? "&unread_only=true" : ""
    apiFetch<{ total: number; items: AlertRow[] }>(`/api/alerts?limit=100${q}`)
      .then(d => { setItems(d.items ?? []); setTotal(d.total ?? 0) })
      .catch(() => { setItems([]); setTotal(0) })
      .finally(() => setLoading(false))
  }, [enabled, unreadOnly])

  useEffect(() => { load() }, [load])

  const markRead = async (id: number) => {
    await apiFetch(`/api/alerts/${id}/read`, { method: "PATCH" })
    load()
  }

  const markAll = async () => {
    await apiFetch("/api/alerts/read-all", { method: "POST" })
    load()
  }

  const openAlert = async (a: AlertRow) => {
    if (a.unread) await markRead(a.id)
    // System / app-update notices: reading acks them; body stays on this page.
    if (a.kind === "system" || !a.href || a.href === "/alerts") return
    router.push(a.href)
  }

  if (!enabled) {
    return (
      <div className="p-6">
        <PrintHeader title="Alerts" />
        <p className="text-sm text-[var(--text-muted)] mt-4">
          In-app alerts are turned off for this company. Enable them under Settings → Preferences.
        </p>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-start justify-between gap-4 mb-4 print:hidden">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)] flex items-center gap-2">
            <Bell className="w-5 h-5 text-[var(--primary)]" /> Alerts
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Overdue invoices, low stock, pending approvals, and app updates for your account.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <label className="flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)] cursor-pointer">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={e => setUnreadOnly(e.target.checked)}
              className="rounded border-[var(--border)]"
            />
            Unread only
          </label>
          <button
            type="button"
            onClick={markAll}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-[12px] font-medium hover:bg-[var(--bg-page)]"
          >
            <CheckCheck className="w-3.5 h-3.5" /> Mark all read
          </button>
        </div>
      </div>

      <PrintHeader title="Alerts" subtitle={`${total} alert${total === 1 ? "" : "s"}`} />

      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl overflow-hidden">
        {loading && (
          <div className="px-4 py-10 text-center text-sm text-[var(--text-muted)]">Loading…</div>
        )}
        {!loading && items.length === 0 && (
          <div className="px-4 py-12 text-center">
            <Bell className="w-8 h-8 mx-auto mb-2 text-[var(--text-muted)]/30" />
            <p className="text-sm text-[var(--text-muted)]">You&apos;re all caught up</p>
          </div>
        )}
        {items.map(a => (
          <button
            key={a.id}
            type="button"
            onClick={() => openAlert(a)}
            className={cn(
              "w-full text-left flex gap-3 px-4 py-3 border-b border-[var(--border-light)] last:border-0 transition-colors",
              a.unread ? "bg-[var(--primary)]/5 hover:bg-[var(--primary)]/10" : "hover:bg-[var(--bg-page)]",
            )}
          >
            <div className="mt-0.5 w-9 h-9 rounded-lg bg-[var(--bg-page)] flex items-center justify-center shrink-0">
              <KindIcon kind={a.kind} severity={a.severity} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={cn("text-sm", a.unread ? "font-semibold" : "font-medium")}>{a.title}</span>
                {a.unread && <span className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]" />}
              </div>
              {a.body && <p className="text-[12px] text-[var(--text-muted)] mt-0.5">{a.body}</p>}
              <p className="text-[11px] text-[var(--text-muted)] mt-1">{fmtWhen(a.created_at)}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
