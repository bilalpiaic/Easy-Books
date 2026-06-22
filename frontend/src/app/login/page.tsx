"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ChevronDown, ChevronUp, Zap } from "lucide-react"
import { setAuthToken } from "@/lib/auth"
import { apiBase } from "@/lib/api"

interface DemoOption {
  label: string
  email: string
  model: string
  blurb: string
}

const DEMO_OPTIONS: DemoOption[] = [
  { label: "Simple",        email: "demo.simple@easy-books.app",        model: "simple",        blurb: "Solo / micro-business — essentials only" },
  { label: "Services",      email: "demo.services@easy-books.app",      model: "services",      blurb: "Agencies & consultancies — recurring revenue" },
  { label: "Trader",        email: "demo.trader@easy-books.app",        model: "trader",        blurb: "Buy-and-resell — inventory + COGS" },
  { label: "Manufacturing", email: "demo.manufacturing@easy-books.app", model: "manufacturing", blurb: "Value-addition — BoMs, GRN, PO lifecycle" },
  { label: "Telecom Franchise", email: "demo.telecom@easy-books.app", model: "telecom_franchise", blurb: "Operator franchise — Tracker, RSO chain, FCA targets" },
  { label: "PRA e-Invoice (Portal)", email: "demo.pra+accountant@easy-books.app", model: "pra_einvoice", blurb: "Sales portal view — simplified sidebar, invoice queue, thermal receipt. Owner: demo.pra@easy-books.app" },
]
const DEMO_PASSWORD = "demo1234"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [demoOpenMobile, setDemoOpenMobile] = useState(false)
  const router = useRouter()

  const doLogin = async (e: string, p: string) => {
    setIsLoading(true)
    setError("")
    try {
      const formData = new FormData()
      formData.append("username", e)
      formData.append("password", p)
      const response = await fetch(`${apiBase}/api/auth/login`, {
        method: "POST",
        body: formData,
      })
      if (!response.ok) throw new Error("Invalid email or password")
      const data = await response.json()
      setAuthToken(data.access_token)
      // Admin-created accounts carry a temporary password — force a change.
      router.push(data.must_change_password ? "/profile?changePassword=1" : "/dashboard")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed")
    } finally {
      setIsLoading(false)
    }
  }

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault()
    doLogin(email, password)
  }

  // ── Reusable demo block (rendered differently mobile vs desktop) ──
  const demoButtons = (
    <div className="space-y-2">
      {DEMO_OPTIONS.map(o => (
        <button
          key={o.email}
          type="button"
          disabled={isLoading}
          onClick={() => doLogin(o.email, DEMO_PASSWORD)}
          className="w-full text-left bg-white/5 hover:bg-[#b8943f]/20 border border-white/10 hover:border-[#b8943f]/60 rounded-xl px-3 py-2.5 transition-all disabled:opacity-50 group"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-white group-hover:text-[#ffd966]">
              {o.label}
            </span>
            <span className="text-[10px] uppercase tracking-wider text-white/40 group-hover:text-[#ffd966] shrink-0">
              {o.model}
            </span>
          </div>
          <p className="text-[11px] text-white/50 mt-0.5 leading-tight line-clamp-2">
            {o.blurb}
          </p>
        </button>
      ))}
    </div>
  )

  return (
    <div className="min-h-screen bg-[#f6f3ee] font-sans flex items-start sm:items-center justify-center px-3 py-4 sm:p-6">
      <div className="w-full max-w-sm sm:max-w-md md:max-w-3xl md:grid md:grid-cols-[1fr_320px] md:gap-6">
        {/* ── Left column: brand + login form ──────────────────────────── */}
        <div>
          {/* Brand header — compact on mobile */}
          <div className="text-center md:text-left mb-4 md:mb-6">
            <div className="inline-flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 bg-[#b8943f] rounded-xl mb-2 font-serif text-xl sm:text-2xl font-bold text-black">
              M
            </div>
            <h1 className="text-2xl sm:text-3xl font-serif text-[#1a1814] leading-tight">
              Easy-Books
            </h1>
            <p className="text-[#1a1814]/60 text-xs sm:text-sm">
              SaaS Bookkeeping for Enterprises
            </p>
          </div>

          {/* Login card */}
          <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-lg shadow-black/5 border border-[#1a1814]/5">
            <h2 className="text-lg sm:text-xl font-serif text-[#1a1814] mb-3">
              Welcome Back
            </h2>
            <form onSubmit={handleLogin} className="space-y-3">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2.5 bg-white border border-[#1a1814]/10 rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814] text-sm"
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2.5 bg-white border border-[#1a1814]/10 rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814] text-sm"
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                />
              </div>
              {error && (
                <p className="text-red-600 text-xs bg-red-50 border border-red-200 rounded-lg px-2.5 py-1.5">
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-[#1a1814] text-white font-semibold py-2.5 sm:py-3 rounded-lg hover:bg-[#b8943f] hover:text-[#1a1814] active:scale-[0.99] transition-all mt-2 disabled:opacity-50 text-sm"
              >
                {isLoading ? "Signing in…" : "Login"}
              </button>
            </form>
            <div className="mt-4 text-center text-xs text-[#1a1814]/45">
              Don&apos;t have an account?{" "}
              <Link href="/signup" className="text-[#b8943f] font-bold hover:underline">
                Start Free Trial
              </Link>
            </div>
          </div>

          {/* ── Mobile-only: collapsible demo accordion ──────────────── */}
          <div className="md:hidden mt-3">
            <button
              type="button"
              onClick={() => setDemoOpenMobile(o => !o)}
              className="w-full bg-[#1a1814] text-white rounded-2xl px-4 py-3 flex items-center justify-between gap-2"
            >
              <span className="flex items-center gap-2 min-w-0">
                <Zap className="w-4 h-4 text-[#ffd966] shrink-0" />
                <span className="text-sm font-semibold truncate">Try a live demo</span>
                <span className="text-[10px] text-white/50 hidden xs:inline">no signup needed</span>
              </span>
              {demoOpenMobile
                ? <ChevronUp className="w-4 h-4 shrink-0" />
                : <ChevronDown className="w-4 h-4 shrink-0" />}
            </button>
            {demoOpenMobile && (
              <div className="bg-gradient-to-br from-[#1a1814] to-[#2d2620] text-white rounded-2xl p-4 mt-2 shadow-lg">
                <p className="text-[11px] text-white/55 mb-3 leading-relaxed">
                  Pick one of six pre-seeded tenants. Each has 12+ customers,
                  vendors, invoices and bills.
                </p>
                {demoButtons}
                <p className="text-[10px] text-white/35 mt-3 leading-relaxed">
                  Password:{" "}
                  <code className="text-white/55 font-mono bg-white/5 px-1 py-0.5 rounded">
                    {DEMO_PASSWORD}
                  </code>
                </p>
              </div>
            )}
          </div>
        </div>

        {/* ── Right column (desktop only): demo panel ─────────────────── */}
        <aside className="hidden md:flex flex-col bg-gradient-to-br from-[#1a1814] to-[#2d2620] text-white rounded-2xl p-5 shadow-lg shadow-black/10 md:self-start md:sticky md:top-6">
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <p className="text-[10px] font-bold uppercase tracking-widest text-[#ffd966]">
              Live Demo
            </p>
          </div>
          <h2 className="text-lg font-serif mb-1">Try in seconds</h2>
          <p className="text-[11px] text-white/55 mb-4 leading-relaxed">
            Six pre-seeded tenants — one per business model. Each has 12+
            customers, vendors, invoices and bills.
          </p>
          {demoButtons}
          <p className="text-[10px] text-white/35 mt-3 leading-relaxed">
            Password:{" "}
            <code className="text-white/55 font-mono bg-white/5 px-1 py-0.5 rounded">
              {DEMO_PASSWORD}
            </code>
          </p>
        </aside>
      </div>
    </div>
  )
}
