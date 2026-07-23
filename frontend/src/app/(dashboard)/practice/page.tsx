"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Building2, Check, Loader2, Users } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { setAuthToken } from "@/lib/auth"
import type { TenantMembershipItem } from "@/components/ClientSwitcher"

interface SwitchResponse {
  access_token: string
  tenant_id: number
  tenant_name: string
}

/** Practice clients list — v1 listing + switch (#220). */
export default function PracticePage() {
  const [items, setItems] = useState<TenantMembershipItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const reload = useCallback(() => {
    setLoading(true)
    apiFetch<{ items: TenantMembershipItem[] }>("/api/auth/tenants")
      .then(r => { setItems(r.items ?? []); setError(null) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { reload() }, [reload])

  async function switchTo(tenantId: number, isActive: boolean) {
    if (isActive || busyId != null) return
    setBusyId(tenantId)
    setError(null)
    try {
      const r = await apiFetch<SwitchResponse>("/api/auth/switch-tenant", {
        method: "POST",
        body: JSON.stringify({ tenant_id: tenantId }),
      })
      setAuthToken(r.access_token)
      window.location.href = "/dashboard"
    } catch (e) {
      setError(e instanceof Error ? e.message : "Switch failed")
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <header className="flex items-start gap-3">
        <Building2 className="w-7 h-7 text-[var(--primary)] shrink-0 mt-0.5" />
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Practice clients</h1>
          <p className="text-sm text-[var(--text-primary)]/60 mt-1">
            Companies you can access with this login. Switch to open a client&apos;s books.
            To attach an existing Easy-Books user to this company, invite their email from{" "}
            <Link href="/team" className="text-[var(--primary)] font-medium hover:underline">Team</Link>.
          </p>
        </div>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-primary)]/60 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--text-primary)]/60">No company memberships found.</p>
      ) : (
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] text-[var(--text-primary)]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2.5 font-semibold">Company</th>
                <th className="text-left px-4 py-2.5 font-semibold">Your role</th>
                <th className="text-left px-4 py-2.5 font-semibold">Plan</th>
                <th className="text-right px-4 py-2.5 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map(m => (
                <tr key={m.tenant_id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3">
                    <div className="font-medium text-[var(--text-primary)] flex items-center gap-2">
                      {m.company_name || m.name}
                      {m.is_active && (
                        <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--primary)]">
                          <Check className="w-3 h-3" /> Active
                        </span>
                      )}
                    </div>
                    {m.name && m.company_name && m.name !== m.company_name && (
                      <div className="text-xs text-[var(--text-primary)]/50">{m.name}</div>
                    )}
                    {m.is_suspended && (
                      <div className="text-xs text-amber-700 font-medium">Suspended</div>
                    )}
                  </td>
                  <td className="px-4 py-3 capitalize text-[var(--text-primary)]/80">{m.role}</td>
                  <td className="px-4 py-3 text-[var(--text-primary)]/60 capitalize">{m.plan || "—"}</td>
                  <td className="px-4 py-3 text-right">
                    {m.is_active ? (
                      <span className="text-xs text-[var(--text-primary)]/40">Current</span>
                    ) : (
                      <button
                        type="button"
                        disabled={busyId != null || m.is_suspended}
                        onClick={() => switchTo(m.tenant_id, m.is_active)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--primary)] text-black text-xs font-bold hover:bg-[#d4af60] transition disabled:opacity-50"
                      >
                        {busyId === m.tenant_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                        Switch
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-[var(--text-primary)]/45 flex items-center gap-2">
        <Users className="w-3.5 h-3.5" />
        Team invites for emails that already have an account attach them immediately — no new password required.
      </p>
    </div>
  )
}
