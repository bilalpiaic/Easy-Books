"use client"

import { Suspense, useCallback, useEffect, useRef, useState } from "react"
import { useSearchParams } from "next/navigation"
import { User as UserIcon, Save, KeyRound, Camera, Trash2, Loader2, CheckCircle2, ShieldCheck } from "lucide-react"
import { apiFetch, apiBase } from "@/lib/api"
import { getAuthHeader } from "@/lib/auth"
import { useTranslation } from "react-i18next"

interface Me {
  id: number
  email: string
  full_name: string
  phone: string | null
  avatar_url: string | null
  role: string
  must_change_password: boolean
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
  const { t } = useTranslation()
    return () => { revoked = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [path])
  return url
}

function ProfilePageInner() {
  const params = useSearchParams()
  const forcePwd = params.get("changePassword") === "1"

  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState<string | null>(null)
  const reload = useCallback(() => {
    apiFetch<Me>("/api/auth/me").then(setMe).catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [])
  useEffect(() => { reload() }, [reload])

  return (
    <div className="space-y-6 max-w-3xl">
      <header className="flex items-center gap-3">
        <UserIcon className="w-7 h-7 text-[#b8943f]" />
        <div>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">My Profile</h1>
          <p className="text-sm text-[#1a1814]/60">Your personal details, avatar, and password.</p>
        </div>
      </header>

      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {forcePwd && me?.must_change_password && (
        <div className="bg-amber-50 border border-amber-300 text-amber-900 rounded-xl px-4 py-3 text-sm flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" /> Your account uses a temporary password. Please set a new one below before continuing.
        </div>
      )}

      {me && (
        <>
          <AvatarCard me={me} onChange={reload} />
          <ProfileCard me={me} onSaved={reload} />
          <PasswordCard highlight={forcePwd && me.must_change_password} />
          <AccountInfoCard me={me} />
        </>
      )}
    </div>
  )
}

function Card({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <section className="bg-white border border-[#ede9e2] rounded-2xl p-5 space-y-4">
      <h2 className="flex items-center gap-2 text-sm font-bold text-[#1a1814]">
        <Icon className="w-4 h-4 text-[#b8943f]" /> {title}
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
        <div className="w-20 h-20 rounded-full bg-[#b8943f] flex items-center justify-center overflow-hidden shrink-0">
          {imgUrl
            ? <img src={imgUrl} alt="Avatar" className="w-full h-full object-cover" />
            : <span className="text-white text-2xl font-serif font-bold">{initials}</span>}
        </div>
        <div className="space-y-2">
          <div className="flex gap-2">
            <button
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#b8943f] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />} Upload
            </button>
            {me.avatar_url && (
              <button onClick={remove} disabled={busy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#ede9e2] text-sm font-medium hover:bg-[#f6f3ee] transition disabled:opacity-60">
                <Trash2 className="w-4 h-4" /> Remove
              </button>
            )}
          </div>
          <p className="text-[11px] text-[#1a1814]/45">PNG, JPEG, GIF or WebP · up to 5 MB.</p>
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
      <span className="text-[11px] font-semibold uppercase tracking-wide text-[#1a1814]/55">{label}</span>
      {children}
    </label>
  )
}

const inputCls = "mt-1 w-full rounded-lg border border-[#ede9e2] bg-white px-3 py-2 text-sm focus:border-[#b8943f] focus:outline-none"

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
          <Field label="Email"><input className={`${inputCls} bg-[#faf8f4] text-[#1a1814]/60`} value={me.email} disabled /></Field>
        </div>
        {err && <p className="text-sm text-red-700">{err}</p>}
        {ok && <p className="flex items-center gap-1.5 text-sm text-emerald-700"><CheckCircle2 className="w-4 h-4" /> Saved.</p>}
        <button type="submit" disabled={busy}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save changes
        </button>
      </form>
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
      setOk(true); setCur(""); setNext(""); setConfirm("")
    } catch (e) { setErr(e instanceof Error ? e.message : "Failed to change password") }
    finally { setBusy(false) }
  }

  return (
    <section className={`bg-white border rounded-2xl p-5 space-y-4 ${highlight ? "border-amber-300 ring-1 ring-amber-200" : "border-[#ede9e2]"}`}>
      <h2 className="flex items-center gap-2 text-sm font-bold text-[#1a1814]">
        <KeyRound className="w-4 h-4 text-[#b8943f]" /> Change password
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
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />} Update password
        </button>
      </form>
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
            <dt className="text-xs text-[#1a1814]/55">{k}</dt>
            <dd className="text-sm font-medium text-[#1a1814]">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

export default function ProfilePage() {
  return <Suspense><ProfilePageInner /></Suspense>
}
