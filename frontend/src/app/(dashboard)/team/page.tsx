"use client"

import { useCallback, useEffect, useState } from "react"
import { Users, UserPlus, Mail, Loader2, Copy, Check, KeyRound, ShieldAlert, Trash2, RotateCcw, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { getCurrentUser } from "@/lib/auth"
import { downloadCSV } from "@/lib/utils"

interface Member {
  id: number
  email: string
  full_name: string | null
  role: string
  is_active: boolean
  must_change_password: boolean
  last_login_at: string | null
}
interface Invite {
  id: number
  email: string
  role: string
  token: string
  expires_at: string
  expired: boolean
}

const ROLES = ["viewer", "accountant", "admin", "owner"] as const
const ROLE_DESC: Record<string, string> = {
  viewer: "Read-only access",
  accountant: "Create & edit financial data",
  admin: "Manage users, close periods, delete",
  owner: "Full control incl. owner management",
}

function fmtDate(s: string | null): string {
  if (!s) return "Never"
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString()
}

export default function TeamPage() {
  const meRole = getCurrentUser()?.role ?? "viewer"
  const meEmail = getCurrentUser()?.email ?? ""
  const isOwner = meRole === "owner"
  const canManage = meRole === "owner" || meRole === "admin"

  const [members, setMembers] = useState<Member[]>([])
  const [invites, setInvites] = useState<Invite[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const reload = useCallback(() => {
    Promise.all([
      apiFetch<{ items: Member[] }>("/api/users"),
      apiFetch<{ items: Invite[] }>("/api/users/invites"),
    ])
      .then(([u, i]) => { setMembers(u.items); setInvites(i.items); setError(null) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])
  useEffect(() => { reload() }, [reload])

  if (!canManage) {
    return (
      <div className="max-w-xl bg-amber-50 border border-amber-300 text-amber-900 rounded-2xl px-5 py-6 flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold">Admin access required</p>
          <p className="text-sm mt-1">Only owners and admins can manage team members. Your role is <b>{meRole}</b>.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Users className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Team</h1>
            <p className="text-sm text-[#1a1814]/60">Manage who can access this organisation and what they can do.</p>
          </div>
        </div>
        <button onClick={() => downloadCSV('team-members.csv', members.map(m => ({ Name: m.full_name ?? '', Email: m.email, Role: m.role, Status: m.is_active ? 'Active' : 'Inactive', "Last Login": m.last_login_at ?? '' })))} disabled={members.length === 0} className="inline-flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold hover:bg-[#f6f3ee] disabled:opacity-40">
          <Download className="w-4 h-4" /> CSV
        </button>
      </header>

      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}
      {loading ? <p className="text-sm text-[#1a1814]/60">Loading…</p> : (
        <>
          <MembersTable members={members} meEmail={meEmail} isOwner={isOwner} onChange={reload} />
          <AddMember isOwner={isOwner} onChange={reload} />
          <Invites invites={invites} isOwner={isOwner} onChange={reload} />
        </>
      )}
    </div>
  )
}

function RoleBadge({ role }: { role: string }) {
  const tone = role === "owner" ? "bg-[#b8943f]/15 text-[#7a5c1e]"
    : role === "admin" ? "bg-purple-50 text-purple-800"
    : role === "accountant" ? "bg-blue-50 text-blue-800"
    : "bg-slate-100 text-slate-700"
  return <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${tone}`}>{role}</span>
}

function MembersTable({ members, meEmail, isOwner, onChange }: {
  members: Member[]; meEmail: string; isOwner: boolean; onChange: () => void
}) {
  const [busyId, setBusyId] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [resetInfo, setResetInfo] = useState<{ email: string; pwd: string } | null>(null)

  async function patch(id: number, body: Record<string, unknown>) {
    setBusyId(id); setErr(null)
    try {
      await apiFetch(`/api/users/${id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      })
      onChange()
    } catch (e) { setErr(e instanceof Error ? e.message : "Update failed") }
    finally { setBusyId(null) }
  }

  async function resetPwd(id: number, email: string) {
    setBusyId(id); setErr(null)
    try {
      const r = await apiFetch<{ temporary_password: string }>(`/api/users/${id}/reset-password`, { method: "POST" })
      setResetInfo({ email, pwd: r.temporary_password })
    } catch (e) { setErr(e instanceof Error ? e.message : "Reset failed") }
    finally { setBusyId(null) }
  }

  const roleOptions = ROLES.filter(r => r !== "owner" || isOwner)

  return (
    <section className="space-y-2">
      <h2 className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50">Members ({members.length})</h2>
      {err && <p className="text-sm text-red-700">{err}</p>}
      {resetInfo && <CopyBanner label={`Temporary password for ${resetInfo.email}`} value={resetInfo.pwd} onClose={() => setResetInfo(null)} />}
      <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#faf6ec] text-[#1a1814]/70 text-xs uppercase tracking-wide">
            <tr>
              <th className="text-left px-4 py-2 font-semibold">Member</th>
              <th className="text-left px-4 py-2 font-semibold">Role</th>
              <th className="text-left px-4 py-2 font-semibold">Status</th>
              <th className="text-left px-4 py-2 font-semibold">Last login</th>
              <th className="text-right px-4 py-2 font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map(m => {
              const isSelf = m.email === meEmail
              const locked = busyId === m.id
              return (
                <tr key={m.id} className="border-t border-[#ede9e2]">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-[#1a1814]">{m.full_name || "—"}{isSelf && <span className="text-[10px] text-[#1a1814]/40"> (you)</span>}</div>
                    <div className="text-xs text-[#1a1814]/55">{m.email}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    {isSelf ? <RoleBadge role={m.role} /> : (
                      <select
                        value={m.role}
                        disabled={locked}
                        onChange={e => patch(m.id, { role: e.target.value })}
                        className="rounded-lg border border-[#ede9e2] bg-white px-2 py-1 text-xs focus:border-[#b8943f] focus:outline-none"
                        title={ROLE_DESC[m.role]}
                      >
                        {roleOptions.map(r => <option key={r} value={r}>{r}</option>)}
                        {/* keep showing owner if the member already is one but we can't grant it */}
                        {m.role === "owner" && !isOwner && <option value="owner">owner</option>}
                      </select>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {m.is_active
                      ? <span className="text-emerald-700 text-xs font-semibold">Active</span>
                      : <span className="text-[#1a1814]/45 text-xs font-semibold">Inactive</span>}
                    {m.must_change_password && <span className="block text-[10px] text-amber-700">temp password</span>}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-[#1a1814]/60">{fmtDate(m.last_login_at)}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center justify-end gap-1.5">
                      {locked && <Loader2 className="w-3.5 h-3.5 animate-spin text-[#b8943f]" />}
                      {!isSelf && (m.is_active
                        ? <button onClick={() => patch(m.id, { is_active: false })} disabled={locked}
                            title="Deactivate" className="p-1.5 rounded-md text-[#1a1814]/50 hover:text-red-600 hover:bg-red-50 transition"><Trash2 className="w-4 h-4" /></button>
                        : <button onClick={() => patch(m.id, { is_active: true })} disabled={locked}
                            title="Reactivate" className="p-1.5 rounded-md text-[#1a1814]/50 hover:text-emerald-600 hover:bg-emerald-50 transition"><RotateCcw className="w-4 h-4" /></button>)}
                      <button onClick={() => resetPwd(m.id, m.email)} disabled={locked}
                        title="Reset password" className="p-1.5 rounded-md text-[#1a1814]/50 hover:text-[#b8943f] hover:bg-[#faf6ec] transition"><KeyRound className="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function AddMember({ isOwner, onChange }: { isOwner: boolean; onChange: () => void }) {
  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [role, setRole] = useState("viewer")
  const [mode, setMode] = useState<"create" | "invite">("create")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [created, setCreated] = useState<{ label: string; value: string } | null>(null)

  const roleOptions = ROLES.filter(r => r !== "owner" || isOwner)
  const inputCls = "mt-1 w-full rounded-lg border border-[#ede9e2] bg-white px-3 py-2 text-sm focus:border-[#b8943f] focus:outline-none"

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null); setCreated(null)
    try {
      if (mode === "create") {
        const r = await apiFetch<{ temporary_password: string; email: string }>("/api/users", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, full_name: name, role }),
        })
        setCreated({ label: `Temporary password for ${r.email}`, value: r.temporary_password })
      } else {
        const r = await apiFetch<{ accept_path: string }>("/api/users/invites", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, role }),
        })
        const link = `${window.location.origin}${r.accept_path}`
        setCreated({ label: `Invite link for ${email}`, value: link })
      }
      setEmail(""); setName(""); setRole("viewer"); onChange()
    } catch (e) { setErr(e instanceof Error ? e.message : "Failed") }
    finally { setBusy(false) }
  }

  return (
    <section className="bg-white border border-[#ede9e2] rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold text-[#1a1814]"><UserPlus className="w-4 h-4 text-[#b8943f]" /> Add a member</h2>
        <div className="flex rounded-lg border border-[#ede9e2] overflow-hidden text-xs">
          <button onClick={() => setMode("create")} className={`px-3 py-1.5 font-medium ${mode === "create" ? "bg-[#b8943f] text-black" : "text-[#1a1814]/60"}`}>Create account</button>
          <button onClick={() => setMode("invite")} className={`px-3 py-1.5 font-medium ${mode === "invite" ? "bg-[#b8943f] text-black" : "text-[#1a1814]/60"}`}>Send invite</button>
        </div>
      </div>

      {created && <CopyBanner label={created.label} value={created.value} onClose={() => setCreated(null)} />}

      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="block sm:col-span-1">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#1a1814]/55">Email</span>
            <input type="email" required className={inputCls} value={email} onChange={e => setEmail(e.target.value)} />
          </label>
          {mode === "create" && (
            <label className="block">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-[#1a1814]/55">Full name</span>
              <input required className={inputCls} value={name} onChange={e => setName(e.target.value)} />
            </label>
          )}
          <label className="block">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#1a1814]/55">Role</span>
            <select className={inputCls} value={role} onChange={e => setRole(e.target.value)}>
              {roleOptions.map(r => <option key={r} value={r}>{r} — {ROLE_DESC[r]}</option>)}
            </select>
          </label>
        </div>
        {err && <p className="text-sm text-red-700">{err}</p>}
        <p className="text-[11px] text-[#1a1814]/45">
          {mode === "create"
            ? "Creates the account immediately with a temporary password (shown once). The user must change it at first login."
            : "Generates a one-time invite link valid for 7 days. Share it with the recipient — they set their own password."}
        </p>
        <button type="submit" disabled={busy}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : mode === "create" ? <UserPlus className="w-4 h-4" /> : <Mail className="w-4 h-4" />}
          {mode === "create" ? "Create account" : "Generate invite link"}
        </button>
      </form>
    </section>
  )
}

function Invites({ invites, isOwner, onChange }: { invites: Invite[]; isOwner: boolean; onChange: () => void }) {
  const [busyId, setBusyId] = useState<number | null>(null)
  async function revoke(id: number) {
    setBusyId(id)
    try { await apiFetch(`/api/users/invites/${id}`, { method: "DELETE" }); onChange() }
    finally { setBusyId(null) }
  }
  if (invites.length === 0) return null
  return (
    <section className="space-y-2">
      <h2 className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50">Pending invites ({invites.length})</h2>
      <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#faf6ec] text-[#1a1814]/70 text-xs uppercase tracking-wide">
            <tr>
              <th className="text-left px-4 py-2 font-semibold">Email</th>
              <th className="text-left px-4 py-2 font-semibold">Role</th>
              <th className="text-left px-4 py-2 font-semibold">Link</th>
              <th className="text-right px-4 py-2 font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {invites.map(iv => (
              <tr key={iv.id} className="border-t border-[#ede9e2]">
                <td className="px-4 py-2.5">{iv.email}{iv.expired && <span className="text-[10px] text-red-600"> (expired)</span>}</td>
                <td className="px-4 py-2.5"><RoleBadge role={iv.role} /></td>
                <td className="px-4 py-2.5">
                  <CopyButton value={`${typeof window !== "undefined" ? window.location.origin : ""}/accept-invite?token=${iv.token}`} />
                </td>
                <td className="px-4 py-2.5 text-right">
                  <button onClick={() => revoke(iv.id)} disabled={busyId === iv.id}
                    className="p-1.5 rounded-md text-[#1a1814]/50 hover:text-red-600 hover:bg-red-50 transition" title="Revoke">
                    {busyId === iv.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-[#ede9e2] text-xs hover:bg-[#f6f3ee] transition"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "Copied" : "Copy link"}
    </button>
  )
}

function CopyBanner({ label, value, onClose }: { label: string; value: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-sm">
      <p className="text-emerald-900 font-semibold text-xs uppercase tracking-wide">{label}</p>
      <div className="mt-1.5 flex items-center gap-2">
        <code className="flex-1 bg-white border border-emerald-200 rounded-lg px-3 py-1.5 text-xs break-all">{value}</code>
        <button onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 transition shrink-0">
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />} {copied ? "Copied" : "Copy"}
        </button>
        <button onClick={onClose} className="text-emerald-700/60 hover:text-emerald-900 text-xs px-1">✕</button>
      </div>
      <p className="mt-1 text-[11px] text-emerald-800/70">Copy this now — it won&apos;t be shown again.</p>
    </div>
  )
}
