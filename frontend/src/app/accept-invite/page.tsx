"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2, UserPlus, AlertTriangle } from "lucide-react"
import { apiBase } from "@/lib/api"
import { setAuthToken } from "@/lib/auth"

interface InviteInfo { email: string; role: string; company_name: string }

function AcceptInviteInner() {
  const params = useSearchParams()
  const router = useRouter()
  const token = params.get("token") ?? ""

  const [info, setInfo] = useState<InviteInfo | null>(null)
  const [loadErr, setLoadErr] = useState<string | null>(null)
  const [fullName, setFullName] = useState("")
  const [pwd, setPwd] = useState("")
  const [confirm, setConfirm] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!token) { setLoadErr("No invite token provided."); return }
    fetch(`${apiBase}/api/auth/invite/${token}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error("This invite is invalid or has expired."))))
      .then(setInfo)
      .catch(e => setLoadErr(e instanceof Error ? e.message : "Failed to load invite"))
  }, [token])

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null)
    if (pwd.length < 8) { setErr("Password must be at least 8 characters"); return }
    if (pwd !== confirm) { setErr("Passwords do not match"); return }
    setBusy(true)
    try {
      const res = await fetch(`${apiBase}/api/auth/accept-invite`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, full_name: fullName, password: pwd }),
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Failed to accept invite")
      const data = await res.json()
      setAuthToken(data.access_token)
      router.push("/dashboard")
    } catch (e) { setErr(e instanceof Error ? e.message : "Failed") }
    finally { setBusy(false) }
  }

  const inputCls = "mt-1 w-full rounded-lg border border-[#ede9e2] bg-white px-3 py-2 text-sm focus:border-[#b8943f] focus:outline-none"

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f6f3ee] px-4">
      <div className="w-full max-w-md bg-white border border-[#ede9e2] rounded-2xl shadow-sm p-7">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-9 h-9 bg-[#b8943f] rounded-lg flex items-center justify-center">
            <UserPlus className="w-5 h-5 text-black" />
          </div>
          <h1 className="text-xl font-serif font-semibold text-[#1a1814]">Accept your invite</h1>
        </div>

        {loadErr ? (
          <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" /> {loadErr}
          </div>
        ) : !info ? (
          <p className="text-sm text-[#1a1814]/60 flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading invite…</p>
        ) : (
          <>
            <p className="text-sm text-[#1a1814]/70 mb-4">
              You&apos;ve been invited to join <b>{info.company_name}</b> as a <b>{info.role}</b>.
              Set your name and password to activate <b>{info.email}</b>.
            </p>
            <form onSubmit={submit} className="space-y-3">
              <label className="block">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-[#1a1814]/55">Full name</span>
                <input required className={inputCls} value={fullName} onChange={e => setFullName(e.target.value)} />
              </label>
              <label className="block">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-[#1a1814]/55">Password</span>
                <input type="password" required className={inputCls} value={pwd} onChange={e => setPwd(e.target.value)} />
              </label>
              <label className="block">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-[#1a1814]/55">Confirm password</span>
                <input type="password" required className={inputCls} value={confirm} onChange={e => setConfirm(e.target.value)} />
              </label>
              {err && <p className="text-sm text-red-700">{err}</p>}
              <button type="submit" disabled={busy}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#b8943f] text-black text-sm font-bold hover:bg-[#d4af60] transition disabled:opacity-60">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />} Activate account
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#f6f3ee]"><Loader2 className="w-5 h-5 animate-spin text-[#b8943f]" /></div>}>
      <AcceptInviteInner />
    </Suspense>
  )
}
