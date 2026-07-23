"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { Building2, Check, ChevronDown, Loader2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { setAuthToken } from "@/lib/auth"
import { cn } from "@/lib/utils"

export interface TenantMembershipItem {
  tenant_id: number
  name: string
  company_name: string
  role: string
  plan: string
  is_suspended: boolean
  is_active: boolean
}

interface SwitchResponse {
  access_token: string
  tenant_id: number
  tenant_name: string
}

/** Company name + multi-client switcher for practice accountants (#220). */
export default function ClientSwitcher({
  fallbackName,
  className,
}: {
  fallbackName: string
  className?: string
}) {
  const [items, setItems] = useState<TenantMembershipItem[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  const load = useCallback(() => {
    apiFetch<{ items: TenantMembershipItem[] }>("/api/auth/tenants")
      .then(r => setItems(r.items ?? []))
      .catch(() => setItems([]))
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onDoc)
    return () => document.removeEventListener("mousedown", onDoc)
  }, [open])

  const active = items.find(i => i.is_active)
  const label = active?.company_name || active?.name || fallbackName
  const multi = items.length > 1

  async function switchTo(tenantId: number) {
    if (busy || active?.tenant_id === tenantId) {
      setOpen(false)
      return
    }
    setBusy(true)
    setErr(null)
    try {
      const r = await apiFetch<SwitchResponse>("/api/auth/switch-tenant", {
        method: "POST",
        body: JSON.stringify({ tenant_id: tenantId }),
      })
      setAuthToken(r.access_token)
      // Hard navigate so every tenant-scoped React context remounts clean.
      window.location.href = "/dashboard"
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Switch failed")
      setBusy(false)
    }
  }

  if (!multi) {
    return (
      <span className={cn("text-[var(--nav-text)] text-[13px] font-semibold truncate max-w-[100px] sm:max-w-[130px]", className)}>
        {label}
      </span>
    )
  }

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        disabled={busy}
        title="Switch company"
        className="flex items-center gap-1 max-w-[120px] sm:max-w-[160px] text-[var(--nav-text)] text-[13px] font-semibold hover:bg-[var(--nav-hover)] rounded-md px-1.5 py-0.5 transition-colors"
      >
        <span className="truncate">{label}</span>
        {busy
          ? <Loader2 className="w-3 h-3 shrink-0 animate-spin opacity-70" />
          : <ChevronDown className={cn("w-3 h-3 shrink-0 transition-transform", open && "rotate-180")} />}
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-xl py-1 min-w-[240px] max-w-[320px] z-[100]">
          <div className="px-3 py-2 border-b border-[var(--border-light)]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-primary)]/45">
              Your companies
            </div>
          </div>
          {err && <p className="px-3 py-2 text-xs text-red-600">{err}</p>}
          <ul className="max-h-64 overflow-y-auto py-1">
            {items.map(m => (
              <li key={m.tenant_id}>
                <button
                  type="button"
                  disabled={busy || m.is_suspended}
                  onClick={() => switchTo(m.tenant_id)}
                  className={cn(
                    "w-full text-left flex items-start gap-2 px-3 py-2 text-[13px] transition-colors",
                    m.is_active
                      ? "bg-[var(--primary)]/10 text-[var(--text-primary)]"
                      : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]",
                    m.is_suspended && "opacity-40 cursor-not-allowed",
                  )}
                >
                  <Building2 className="w-3.5 h-3.5 mt-0.5 shrink-0 opacity-60" />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium truncate">{m.company_name || m.name}</span>
                    <span className="block text-[11px] text-[var(--text-primary)]/50 truncate">
                      {m.role}{m.is_suspended ? " · suspended" : ""}
                    </span>
                  </span>
                  {m.is_active && <Check className="w-3.5 h-3.5 shrink-0 text-[var(--primary)] mt-0.5" />}
                </button>
              </li>
            ))}
          </ul>
          <div className="border-t border-[var(--border-light)] px-3 py-2">
            <Link
              href="/practice"
              onClick={() => setOpen(false)}
              className="text-[12px] font-medium text-[var(--primary)] hover:underline"
            >
              Manage practice clients →
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
