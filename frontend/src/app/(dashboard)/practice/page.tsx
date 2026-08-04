"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Building2, Check, Loader2, Plus, Shield, Users } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { setAuthToken } from "@/lib/auth"
import { useFmt } from "@/context/SettingsContext"

interface PracticeClient {
  tenant_id: number
  name: string
  company_name: string
  role: string
  plan: string
  is_suspended: boolean
  is_active: boolean
  currency: string
  ar_outstanding: number
  ap_outstanding: number
  ar_overdue: number
  ap_overdue: number
}

interface SwitchResponse {
  access_token: string
  tenant_id: number
  tenant_name: string
}

interface Member {
  user_id: number
  email: string
  full_name: string
  role: string
}

interface ResourceDef {
  key: string
  label: string
  category: string
}

/** Practice firm dashboard — AR/AP per client + onboarding + permissions (#299). */
export default function PracticePage() {
  const fmt = useFmt()
  const [items, setItems] = useState<PracticeClient[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const [showCreate, setShowCreate] = useState(false)
  const [companyName, setCompanyName] = useState("")
  const [adminEmail, setAdminEmail] = useState("")
  const [creating, setCreating] = useState(false)

  const [permTenantId, setPermTenantId] = useState<number | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null)
  const [resources, setResources] = useState<ResourceDef[]>([])
  const [perms, setPerms] = useState<Record<string, string>>({})
  const [permBusy, setPermBusy] = useState(false)
  const [permMsg, setPermMsg] = useState<string | null>(null)

  const reload = useCallback(() => {
    setLoading(true)
    apiFetch<{ items: PracticeClient[] }>("/api/practice/dashboard")
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

  async function createClient() {
    if (!companyName.trim()) { setError("Company name is required"); return }
    setCreating(true)
    setError(null)
    try {
      await apiFetch("/api/practice/clients", {
        method: "POST",
        body: JSON.stringify({
          company_name: companyName.trim(),
          admin_email: adminEmail.trim() || null,
        }),
      })
      setShowCreate(false)
      setCompanyName("")
      setAdminEmail("")
      reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed")
    } finally {
      setCreating(false)
    }
  }

  async function openPermissions(tenantId: number) {
    setPermTenantId(tenantId)
    setPermMsg(null)
    setSelectedUserId(null)
    setPerms({})
    try {
      const [mem, res] = await Promise.all([
        apiFetch<{ items: Member[] }>(`/api/practice/clients/${tenantId}/members`),
        apiFetch<ResourceDef[]>("/api/permissions/resources"),
      ])
      setMembers(mem.items ?? [])
      setResources(res ?? [])
      if (mem.items?.[0]) {
        await loadUserPerms(tenantId, mem.items[0].user_id)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load permissions")
      setPermTenantId(null)
    }
  }

  async function loadUserPerms(tenantId: number, userId: number) {
    setSelectedUserId(userId)
    setPermBusy(true)
    setPermMsg(null)
    try {
      const data = await apiFetch<{ permissions: Record<string, string> }>(
        `/api/practice/clients/${tenantId}/permissions/${userId}`,
      )
      setPerms(data.permissions ?? {})
    } catch (e) {
      setPermMsg(e instanceof Error ? e.message : "Failed to load")
    } finally {
      setPermBusy(false)
    }
  }

  async function savePerm(resourceKey: string, accessLevel: string) {
    if (permTenantId == null || selectedUserId == null) return
    setPermBusy(true)
    setPermMsg(null)
    try {
      await apiFetch(`/api/practice/clients/${permTenantId}/permissions/${selectedUserId}`, {
        method: "PUT",
        body: JSON.stringify([{ resource_key: resourceKey, access_level: accessLevel }]),
      })
      setPerms(p => ({ ...p, [resourceKey]: accessLevel === "default" ? p[resourceKey] : accessLevel }))
      if (accessLevel === "default") {
        await loadUserPerms(permTenantId, selectedUserId)
      }
      setPermMsg("Saved")
    } catch (e) {
      setPermMsg(e instanceof Error ? e.message : "Save failed")
    } finally {
      setPermBusy(false)
    }
  }

  const categories = Array.from(new Set(resources.map(r => r.category)))
  const canManagePerms = (role: string) => role === "owner" || role === "admin"

  return (
    <div className="space-y-6 max-w-5xl">
      <header className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Building2 className="w-7 h-7 text-[var(--primary)] shrink-0 mt-0.5" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Practice clients</h1>
            <p className="text-sm text-[var(--text-primary)]/60 mt-1">
              Firm view of every company you can access — AR/AP snapshot, switch, and rights.
              Attach existing users from{" "}
              <Link href="/team" className="text-[var(--primary)] font-medium hover:underline">Team</Link>
              {" "}while inside a client, or create a new client below.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(v => !v)}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[var(--text-primary)] text-white text-sm font-bold hover:bg-[var(--primary)] hover:text-black transition print:hidden"
        >
          <Plus className="w-4 h-4" /> New client
        </button>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {showCreate && (
        <div className="bg-white border border-[var(--border)] rounded-2xl p-5 space-y-3 print:hidden">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/70">Create client company</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Company name *</label>
              <input
                value={companyName}
                onChange={e => setCompanyName(e.target.value)}
                placeholder="Acme Trading Ltd"
                className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
                Client admin email <span className="font-normal normal-case">(optional)</span>
              </label>
              <input
                type="email"
                value={adminEmail}
                onChange={e => setAdminEmail(e.target.value)}
                placeholder="owner@client.com"
                className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
              />
              <p className="text-[10px] text-[var(--text-muted)] mt-1">
                Existing users are attached as owner; new emails get an invite.
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={creating}
              onClick={createClient}
              className="px-4 py-2 rounded-xl bg-[var(--primary)] text-black text-sm font-bold hover:bg-[#d4af60] disabled:opacity-50"
            >
              {creating ? "Creating…" : "Create & attach me"}
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-[var(--text-muted)]">
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-primary)]/60 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--text-primary)]/60">No company memberships found.</p>
      ) : (
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl overflow-hidden">
          <div className="table-freeze">
            <table className="w-full text-sm min-w-[720px]">
              <thead className="bg-[var(--bg-page)] text-[var(--text-primary)]/70 text-xs uppercase tracking-wide">
                <tr>
                  <th className="text-left px-4 py-2.5 font-semibold">Company</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Role</th>
                  <th className="text-right px-4 py-2.5 font-semibold">AR</th>
                  <th className="text-right px-4 py-2.5 font-semibold">AR overdue</th>
                  <th className="text-right px-4 py-2.5 font-semibold">AP</th>
                  <th className="text-right px-4 py-2.5 font-semibold">AP overdue</th>
                  <th className="text-right px-4 py-2.5 font-semibold print:hidden">Actions</th>
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
                      <div className="text-[10px] text-[var(--text-muted)] font-mono">{m.currency}</div>
                      {m.is_suspended && (
                        <div className="text-xs text-amber-700 font-medium">Suspended</div>
                      )}
                    </td>
                    <td className="px-4 py-3 capitalize text-[var(--text-primary)]/80">{m.role}</td>
                    <td className="px-4 py-3 text-right font-mono">{fmt(Number(m.ar_outstanding))}</td>
                    <td className={`px-4 py-3 text-right font-mono ${Number(m.ar_overdue) > 0 ? "text-red-700 font-semibold" : ""}`}>
                      {fmt(Number(m.ar_overdue))}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">{fmt(Number(m.ap_outstanding))}</td>
                    <td className={`px-4 py-3 text-right font-mono ${Number(m.ap_overdue) > 0 ? "text-red-700 font-semibold" : ""}`}>
                      {fmt(Number(m.ap_overdue))}
                    </td>
                    <td className="px-4 py-3 text-right print:hidden">
                      <div className="inline-flex items-center gap-2">
                        {canManagePerms(m.role) && (
                          <button
                            type="button"
                            onClick={() => openPermissions(m.tenant_id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-[var(--border)] text-xs font-semibold hover:bg-[var(--bg-page)]"
                            title="Permissions"
                          >
                            <Shield className="w-3.5 h-3.5" /> Rights
                          </button>
                        )}
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
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {permTenantId != null && (
        <div className="bg-white border border-[var(--border)] rounded-2xl p-5 space-y-4 print:hidden">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/70 flex items-center gap-2">
              <Shield className="w-4 h-4" /> Cross-client permissions
            </h2>
            <button type="button" onClick={() => setPermTenantId(null)} className="text-xs text-[var(--text-muted)] hover:underline">
              Close
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {members.map(m => (
              <button
                key={m.user_id}
                type="button"
                onClick={() => loadUserPerms(permTenantId, m.user_id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
                  selectedUserId === m.user_id
                    ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--text-primary)]"
                    : "border-[var(--border)] hover:bg-[var(--bg-page)]"
                }`}
              >
                {m.full_name || m.email} <span className="opacity-60">({m.role})</span>
              </button>
            ))}
          </div>
          {permMsg && <p className="text-xs text-[var(--primary)]">{permMsg}</p>}
          {permBusy && !Object.keys(perms).length ? (
            <p className="text-sm text-[var(--text-muted)] flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading matrix…
            </p>
          ) : (
            <div className="space-y-4 max-h-[50vh] overflow-y-auto">
              {categories.map(cat => (
                <div key={cat}>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] mb-1.5">{cat}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {resources.filter(r => r.category === cat).map(r => (
                      <div key={r.key} className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-[var(--bg-page)] text-sm">
                        <span className="truncate">{r.label}</span>
                        <select
                          value={perms[r.key] || "view"}
                          disabled={permBusy || selectedUserId == null}
                          onChange={e => savePerm(r.key, e.target.value)}
                          className="text-xs bg-white border border-[var(--border)] rounded-lg px-2 py-1 outline-none focus:ring-1 focus:ring-[var(--primary)]"
                        >
                          <option value="edit">Edit</option>
                          <option value="view">View</option>
                          <option value="none">None</option>
                          <option value="default">Default</option>
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-[var(--text-primary)]/45 flex items-center gap-2">
        <Users className="w-3.5 h-3.5" />
        One-click Switch remints your session token for that client — no password re-entry.
      </p>
    </div>
  )
}
