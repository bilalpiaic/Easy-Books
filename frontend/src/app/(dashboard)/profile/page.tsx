"use client"

import { Suspense, useCallback, useEffect, useRef, useState } from "react"
import { useSearchParams } from "next/navigation"
import { User as UserIcon, Save, KeyRound, Camera, Trash2, Loader2, CheckCircle2, ShieldCheck, UserCheck } from "lucide-react"
import { apiFetch, apiBase } from "@/lib/api"
import { getAuthHeader, setMustChangePwd, setMustSetupTotp } from "@/lib/auth"

interface Me {
  id: number
  email: string
  full_name: string
  phone: string | null
  avatar_url: string | null
  role: string
  must_change_password: boolean
  totp_enabled?: boolean
  totp_setup_required?: boolean
  totp_can_disable?: boolean
  created_at: string | null
  last_login_at: string | null
  tenant: { name: string; business_model: string }
}

const ROLE_LABEL: Record<string, string> = {
  owner: "Owner", admin: "Admin", accountant: "Accountant", viewer: "Viewer",
}

function fmtDate(s: string | null): string {
  if (!s) return "—"
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString()
}

/** Fetch an avatar with the Bearer header and render it as an object URL,
 *  since a plain <img src> can't carry the Authorization header. */
function useAuthedImage(path: string | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!path) { setUrl(null); return }
    let revoked = false
    let objectUrl: string | null = null
    fetch(`${apiBase}${path}`, { headers: { ...getAuthHeader() } })
      .then(r => (r.ok ? r.blob() : Promise.reject()))
      .then(b => { if (!revoked) { objectUrl = URL.createObjectURL(b); setUrl(objectUrl) } })
      .catch(() => setUrl(null))
    return () => { revoked = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [path])
  return url
}

function ProfilePageInner() {
  const params = useSearchParams()
  const forcePwd = params.get("changePassword") === "1"
  const forceTotp = params.get("setup2fa") === "1"

  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState<string | null>(null)
  const reload = useCallback(() => {
    apiFetch<Me>("/api/auth/me").then(setMe).catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [])
  useEffect(() => { reload() }, [reload])

  return (
    <div className="space-y-6 max-w-3xl">
      <header className="flex items-center gap-3">
        <UserIcon className="w-7 h-7 text-[var(--primary)]" />
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">My Profile</h1>
          <p className="text-sm text-[var(--text-primary)]/60">Your personal details, avatar, and password.</p>
        </div>
      </header>

      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {forcePwd && me?.must_change_password && (
        <div className="bg-amber-50 border border-amber-300 text-amber-900 rounded-xl px-4 py-3 text-sm flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" /> Your account uses a temporary password. Please set a new one below before continuing.
        </div>
      )}

      {forceTotp && me?.totp_setup_required && (
        <div className="bg-amber-50 border border-amber-300 text-amber-900 rounded-xl px-4 py-3 text-sm flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" /> This server requires authenticator 2FA for owners. Enable it below before posting invoices or bills.
        </div>
      )}

      {me && (
        <>
          <AvatarCard me={me} onChange={reload} />
          <ProfileCard me={me} onSaved={reload} />
          <OooSubstituteCard me={me} />
          <PasswordCard highlight={forcePwd && me.must_change_password} />
          <TotpEnrollCard me={me} highlight={forceTotp && !!me.totp_setup_required} onEnabled={reload} />
          <AccountInfoCard me={me} />
        </>
      )}
    </div>
  )
}

function Card({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <section className="bg-white border border-[var(--border)] rounded-2xl p-5 space-y-4">
      <h2 className="flex items-center gap-2 text-sm font-bold text-[var(--text-primary)]">
        <Icon className="w-4 h-4 text-[var(--primary)]" /> {title}
      </h2>
      {children}
    </section>
  )
}

function AvatarCard({ me, onChange }: { me: Me; onChange: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const imgUrl = useAuthedImage(me.avatar_url)
  const initials = (me.full_name || me.email).charAt(0).toUpperCase()

  async function upload(file: File) {
    setBusy(true); setErr(null)
    try {
      const fd = new FormData()
      fd.append("file", file)
      const res = await fetch(`${apiBase}/api/auth/me/avatar`, {
        method: "POST", headers: { ...getAuthHeader() }, body: fd,
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Upload failed")
      onChange()
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed")
    } finally { setBusy(false) }
  }

  async function remove() {
    setBusy(true); setErr(null)
    try {
      const res = await fetch(`${apiBase}/api/auth/me/avatar`, { method: "DELETE", headers: { ...getAuthHeader() } })
      if (!res.ok && res.status !== 204) throw new Error("Failed to remove")
      onChange()
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to remove")
    } finally { setBusy(false) }
  }

  return (
    <Card title="Avatar" icon={Camera}>
      <div className="flex items-center gap-5">
        <div className="w-20 h-20 rounded-full bg-[var(--primary)] flex items-center justify-center overflow-hidden shrink-0">
          {imgUrl
            ? <img src={imgUrl} alt="Avatar" className="w-full h-full object-cover" />
            : <span className="text-white text-2xl font-bold font-bold">{initials}</span>}
        </div>
        <div className="space-y-2">
          <div className="flex gap-2">
            <button
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--primary)] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />} Upload
            </button>
            {me.avatar_url && (
              <button onClick={remove} disabled={busy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[var(--bg-page)] transition disabled:opacity-60">
                <Trash2 className="w-4 h-4" /> Remove
              </button>
            )}
          </div>
          <p className="text-[11px] text-[var(--text-primary)]/45">PNG, JPEG, GIF or WebP · up to 5 MB.</p>
          {err && <p className="text-xs text-red-700">{err}</p>}
        </div>
        <input ref={fileRef} type="file" accept="image/*" className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = "" }} />
      </div>
    </Card>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-primary)]/55">{label}</span>
      {children}
    </label>
  )
}

const inputCls = "mt-1 w-full rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm focus:border-[var(--primary)] focus:outline-none"

function ProfileCard({ me, onSaved }: { me: Me; onSaved: () => void }) {
  const [fullName, setFullName] = useState(me.full_name ?? "")
  const [phone, setPhone] = useState(me.phone ?? "")
  const [busy, setBusy] = useState(false)
  const [ok, setOk] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null); setOk(false)
    try {
      await apiFetch("/api/auth/me", {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: fullName, phone }),
      })
      setOk(true); onSaved()
    } catch (e) { setErr(e instanceof Error ? e.message : "Save failed") }
    finally { setBusy(false) }
  }

  return (
    <Card title="Personal details" icon={UserIcon}>
      <form onSubmit={save} className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Full name"><input className={inputCls} value={fullName} onChange={e => setFullName(e.target.value)} required /></Field>
          <Field label="Phone"><input className={inputCls} value={phone} onChange={e => setPhone(e.target.value)} placeholder="Optional" /></Field>
          <Field label="Email"><input className={`${inputCls} bg-[#faf8f4] text-[var(--text-primary)]/60`} value={me.email} disabled /></Field>
        </div>
        {err && <p className="text-sm text-red-700">{err}</p>}
        {ok && <p className="flex items-center gap-1.5 text-sm text-emerald-700"><CheckCircle2 className="w-4 h-4" /> Saved.</p>}
        <button type="submit" disabled={busy}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--primary)] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save changes
        </button>
      </form>
    </Card>
  )
}

function OooSubstituteCard({ me }: { me: Me }) {
  type Sub = {
    id: number
    substitute_user_id: number
    starts_on: string
    ends_on: string
    is_active: boolean
  }
  type TeamUser = { id: number; full_name: string; email: string; role: string }

  const [rows, setRows] = useState<Sub[]>([])
  const [team, setTeam] = useState<TeamUser[]>([])
  const [substituteId, setSubstituteId] = useState("")
  const [startsOn, setStartsOn] = useState("")
  const [endsOn, setEndsOn] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [ok, setOk] = useState(false)

  const load = useCallback(() => {
    apiFetch<Sub[]>("/api/approvals/substitutes/me").then(setRows).catch(() => setRows([]))
    apiFetch<{ items: TeamUser[] } | TeamUser[]>("/api/users")
      .then((data) => {
        const list = Array.isArray(data) ? data : (data.items ?? [])
        setTeam(list.filter((u) => u.id !== me.id))
      })
      .catch(() => setTeam([]))
  }, [me.id])

  useEffect(() => { load() }, [load])

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setErr(null); setOk(false); setBusy(true)
    try {
      await apiFetch("/api/approvals/substitutes", {
        method: "POST",
        body: JSON.stringify({
          substitute_user_id: Number(substituteId),
          starts_on: startsOn,
          ends_on: endsOn,
          is_active: true,
        }),
      })
      setOk(true)
      setSubstituteId(""); setStartsOn(""); setEndsOn("")
      load()
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed to save")
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: number) {
    setErr(null)
    try {
      await apiFetch(`/api/approvals/substitutes/${id}`, { method: "DELETE" })
      load()
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed to delete")
    }
  }

  const nameFor = (id: number) => {
    const u = team.find((t) => t.id === id)
    return u ? `${u.full_name} (${u.email})` : `User #${id}`
  }

  return (
    <Card title="Out-of-office approver" icon={UserCheck}>
      <p className="text-sm text-[var(--text-muted)]">
        Designate a colleague who can approve documents assigned to you while you are away.
      </p>
      <form onSubmit={save} className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label="Substitute">
            {team.length > 0 ? (
              <select className={inputCls} value={substituteId} onChange={(e) => setSubstituteId(e.target.value)} required>
                <option value="">Select teammate…</option>
                {team.map((u) => (
                  <option key={u.id} value={u.id}>{u.full_name} · {u.role}</option>
                ))}
              </select>
            ) : (
              <input
                type="number"
                className={inputCls}
                value={substituteId}
                onChange={(e) => setSubstituteId(e.target.value)}
                placeholder="Teammate user ID"
                required
              />
            )}
          </Field>
          <Field label="From">
            <input type="date" className={inputCls} value={startsOn} onChange={(e) => setStartsOn(e.target.value)} required />
          </Field>
          <Field label="To">
            <input type="date" className={inputCls} value={endsOn} onChange={(e) => setEndsOn(e.target.value)} required />
          </Field>
        </div>
        {err && <p className="text-sm text-red-700">{err}</p>}
        {ok && <p className="flex items-center gap-1.5 text-sm text-emerald-700"><CheckCircle2 className="w-4 h-4" /> Saved.</p>}
        <button type="submit" disabled={busy || !substituteId}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--primary)] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Set substitute
        </button>
      </form>
      {rows.length > 0 && (
        <ul className="divide-y divide-[#f0ece4] border-t border-[var(--border)] pt-3 space-y-0">
          {rows.map((r) => (
            <li key={r.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                {nameFor(r.substitute_user_id)} · {r.starts_on} → {r.ends_on}
                {!r.is_active && <span className="text-[var(--text-muted)]"> (inactive)</span>}
              </span>
              <button type="button" className="text-red-700 text-xs" onClick={() => remove(r.id)}>Remove</button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function PasswordCard({ highlight }: { highlight: boolean }) {
  const [cur, setCur] = useState("")
  const [next, setNext] = useState("")
  const [confirm, setConfirm] = useState("")
  const [busy, setBusy] = useState(false)
  const [ok, setOk] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setOk(false)
    if (next.length < 8) { setErr("New password must be at least 8 characters"); return }
    if (next !== confirm) { setErr("New password and confirmation do not match"); return }
    setBusy(true)
    try {
      await apiFetch("/api/auth/change-password", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: cur, new_password: next }),
      })
      setMustChangePwd(false)
      setOk(true); setCur(""); setNext(""); setConfirm("")
    } catch (e) { setErr(e instanceof Error ? e.message : "Failed to change password") }
    finally { setBusy(false) }
  }

  return (
    <section className={`bg-white border rounded-2xl p-5 space-y-4 ${highlight ? "border-amber-300 ring-1 ring-amber-200" : "border-[var(--border)]"}`}>
      <h2 className="flex items-center gap-2 text-sm font-bold text-[var(--text-primary)]">
        <KeyRound className="w-4 h-4 text-[var(--primary)]" /> Change password
      </h2>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label="Current password"><input type="password" className={inputCls} value={cur} onChange={e => setCur(e.target.value)} required /></Field>
          <Field label="New password"><input type="password" className={inputCls} value={next} onChange={e => setNext(e.target.value)} required /></Field>
          <Field label="Confirm new"><input type="password" className={inputCls} value={confirm} onChange={e => setConfirm(e.target.value)} required /></Field>
        </div>
        {err && <p className="text-sm text-red-700">{err}</p>}
        {ok && <p className="flex items-center gap-1.5 text-sm text-emerald-700"><CheckCircle2 className="w-4 h-4" /> Password updated.</p>}
        <button type="submit" disabled={busy}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--primary)] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />} Update password
        </button>
      </form>
    </section>
  )
}

function TotpEnrollCard({
  me,
  highlight,
  onEnabled,
}: {
  me: Me
  highlight: boolean
  onEnabled: () => void
}) {
  const [secret, setSecret] = useState<string | null>(null)
  const [otpauth, setOtpauth] = useState<string | null>(null)
  const [code, setCode] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [ok, setOk] = useState(false)

  async function setup() {
    setErr(null); setOk(false); setBusy(true)
    try {
      const r = await apiFetch<{ secret: string; otpauth_url: string }>("/api/auth/totp/setup", { method: "POST" })
      setSecret(r.secret)
      setOtpauth(r.otpauth_url)
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Setup failed")
    } finally {
      setBusy(false)
    }
  }

  async function enable(e: React.FormEvent) {
    e.preventDefault()
    setErr(null); setBusy(true)
    try {
      await apiFetch("/api/auth/totp/enable", { method: "POST", body: JSON.stringify({ code }) })
      setMustSetupTotp(false)
      setOk(true)
      setCode("")
      onEnabled()
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Invalid code")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={`bg-white border rounded-2xl p-5 space-y-4 ${highlight ? "border-amber-300 ring-1 ring-amber-200" : "border-[var(--border)]"}`}>
      <h2 className="flex items-center gap-2 text-sm font-bold text-[var(--text-primary)]">
        <ShieldCheck className="w-4 h-4 text-[var(--primary)]" /> Authenticator 2FA
      </h2>
      {me.totp_enabled ? (
        <p className="text-sm text-emerald-800">
          2FA is enabled{me.totp_can_disable === false ? " and required for owners on this server." : "."}
        </p>
      ) : (
        <>
          <p className="text-sm text-[var(--text-primary)]/60">
            Scan the secret with an authenticator app, then enter a 6-digit code to enable 2FA.
          </p>
          <button
            type="button"
            onClick={setup}
            disabled={busy}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[var(--bg-page)] disabled:opacity-60"
          >
            {busy && !secret ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
            Set up 2FA
          </button>
          {secret && (
            <div className="text-xs break-all space-y-1 bg-[var(--bg-page)] rounded-lg p-3">
              <div>Secret: <code>{secret}</code></div>
              {otpauth && <div>URI: <code>{otpauth}</code></div>}
            </div>
          )}
          <form onSubmit={enable} className="flex flex-wrap items-end gap-2">
            <Field label="6-digit code">
              <input
                className={inputCls}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                inputMode="numeric"
                maxLength={6}
                placeholder="000000"
                required
              />
            </Field>
            <button
              type="submit"
              disabled={busy || code.length < 6}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--primary)] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />} Enable
            </button>
          </form>
        </>
      )}
      {err && <p className="text-sm text-red-700">{err}</p>}
      {ok && <p className="flex items-center gap-1.5 text-sm text-emerald-700"><CheckCircle2 className="w-4 h-4" /> 2FA enabled.</p>}
    </section>
  )
}

function AccountInfoCard({ me }: { me: Me }) {
  const rows: [string, string][] = [
    ["Role", ROLE_LABEL[me.role] ?? me.role],
    ["Organisation", me.tenant.name],
    ["Member since", fmtDate(me.created_at)],
    ["Last login", fmtDate(me.last_login_at)],
  ]
  return (
    <Card title="Account" icon={ShieldCheck}>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between border-b border-[#f0ece4] pb-2">
            <dt className="text-xs text-[var(--text-primary)]/55">{k}</dt>
            <dd className="text-sm font-medium text-[var(--text-primary)]">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

export default function ProfilePage() {
  return <Suspense><ProfilePageInner /></Suspense>
}
