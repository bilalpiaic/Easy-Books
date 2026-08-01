"use client"

import Link from "next/link"
import { WifiOff } from "lucide-react"

export default function OfflinePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-5 px-6 bg-[#f6f3ee] text-[#1a1814]">
      <div className="w-14 h-14 rounded-2xl bg-[#b8943f] flex items-center justify-center shadow-sm">
        <WifiOff className="w-7 h-7 text-white" aria-hidden />
      </div>
      <div className="text-center max-w-sm space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-dm-sans), sans-serif" }}>
          You’re offline
        </h1>
        <p className="text-sm text-[#5c574e] leading-relaxed">
          Easy-Books needs a network connection to load live accounting data.
          Check your connection, then try again.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="px-4 py-2.5 rounded-lg bg-[#b8943f] text-white text-sm font-semibold hover:opacity-90 transition-opacity"
        >
          Retry
        </button>
        <Link
          href="/dashboard"
          className="px-4 py-2.5 rounded-lg border border-[#d4cfc4] bg-white text-sm font-semibold text-[#1a1814] hover:bg-[#efeae2] transition-colors"
        >
          Go to Dashboard
        </Link>
      </div>
    </main>
  )
}
