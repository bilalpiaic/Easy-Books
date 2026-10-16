"use client"

import { useEffect, useState } from "react"
import { apiBase } from "@/lib/api"

export type DemoTrial = {
  applies?: boolean
  days?: number
  days_remaining?: number | null
  ends_at?: string | null
  expired?: boolean
  locked?: boolean
  licensed?: boolean
}

export type LicenseStatus = {
  install_id?: string | null
  licensed?: boolean
  skip_env?: boolean
  standalone?: boolean
  email?: string | null
  issued_at?: string | null
  expires_at?: string | null
  activated_at?: string | null
  data_dir?: string | null
  trial?: DemoTrial | null
}

export function trialIsLocked(trial?: DemoTrial | null): boolean {
  return Boolean(trial?.locked)
}

export async function fetchAuthProviders(): Promise<{
  google?: boolean
  microsoft?: boolean
  demo_login?: boolean
  demo_trial?: DemoTrial | null
}> {
  const r = await fetch(`${apiBase}/api/auth/oauth/providers`)
  if (!r.ok) return {}
  return r.json()
}

export async function fetchLicenseStatus(): Promise<LicenseStatus | null> {
  try {
    const r = await fetch(`${apiBase}/api/license/status`)
    if (!r.ok) return null
    return r.json()
  } catch {
    return null
  }
}

/** Full-page lock. Files on disk are not deleted. Paste a signed license to unlock. */
export function StandaloneTrialLock({ days = 15 }: { days?: number }) {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [token, setToken] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchLicenseStatus().then((s) => {
      if (!cancelled) setStatus(s)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const installId = status?.install_id || ""

  const copyId = async () => {
    if (!installId) return
    try {
      await navigator.clipboard.writeText(installId)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  const activate = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = token.trim()
    if (!trimmed || busy) return
    setBusy(true)
    setError("")
    try {
      const r = await fetch(`${apiBase}/api/license/activate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: trimmed }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) {
        const detail = body?.detail
        setError(typeof detail === "string" ? detail : "Could not activate this license.")
        return
      }
      window.location.reload()
    } catch {
      setError("Could not reach the API. Is Easy-Books running?")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f6f3ee] font-sans flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 bg-[#b8943f] rounded-xl mb-3 font-serif text-2xl font-bold text-black select-none">
          M
        </div>
        <h1 className="font-serif text-3xl text-[#1a1814]">Easy-Books</h1>
        <div className="mt-6 bg-white/60 border border-[#1a1814]/10 rounded-2xl p-6 text-left">
          <h2 className="font-serif text-xl text-[#1a1814] mb-2">Trial ended</h2>
          <p className="text-sm text-[#1a1814]/80">
            The {days}-day trial on this installation has ended. This copy of
            Easy-Books is locked.
          </p>
          <p className="text-sm text-[#1a1814]/80 mt-3">
            The source folder on this PC and your books in the data folder are{" "}
            <strong>not deleted</strong>. Send the install ID below to Easy-Books
            and paste the license token they issue.
          </p>

          {installId && (
            <div className="mt-4">
              <div className="text-xs uppercase tracking-wide text-[#1a1814]/50 mb-1">
                Install ID
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs break-all bg-white border border-[#1a1814]/10 rounded-lg px-2 py-1.5 text-[#1a1814]">
                  {installId}
                </code>
                <button
                  type="button"
                  onClick={copyId}
                  className="shrink-0 text-xs px-2 py-1.5 rounded-lg border border-[#1a1814]/15 hover:bg-white"
                >
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          )}

          <form onSubmit={activate} className="mt-4 space-y-2">
            <label className="block text-xs uppercase tracking-wide text-[#1a1814]/50">
              License token
            </label>
            <textarea
              value={token}
              onChange={(e) => setToken(e.target.value)}
              rows={3}
              placeholder="EB1.…"
              className="w-full text-xs font-mono bg-white border border-[#1a1814]/15 rounded-lg px-2 py-2 text-[#1a1814] placeholder:text-[#1a1814]/30"
            />
            {error && <p className="text-sm text-red-700">{error}</p>}
            <button
              type="submit"
              disabled={busy || !token.trim()}
              className="w-full px-4 py-2 rounded-lg text-sm font-medium bg-[#1a1814] text-white hover:bg-[#1a1814]/80 disabled:opacity-50"
            >
              {busy ? "Activating…" : "Activate license"}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
