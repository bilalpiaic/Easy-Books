"use client"

import { apiBase } from "@/lib/api"

export type DemoTrial = {
  applies?: boolean
  days?: number
  days_remaining?: number | null
  ends_at?: string | null
  expired?: boolean
  locked?: boolean
}

export function trialIsLocked(trial?: DemoTrial | null): boolean {
  return Boolean(trial?.expired || trial?.locked)
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

/** Full-page lock. Files on disk are not deleted. */
export function StandaloneTrialLock({ days = 15 }: { days?: number }) {
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
            <strong>not deleted</strong>. Contact Easy-Books to license this
            install and continue with the same data.
          </p>
        </div>
      </div>
    </div>
  )
}
