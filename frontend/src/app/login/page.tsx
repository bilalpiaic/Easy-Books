"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { setAuthToken } from "@/lib/auth"
import { apiBase } from "@/lib/api"

interface DemoOption {
  label: string
  email: string
  model: string
  blurb: string
}

const DEMO_OPTIONS: DemoOption[] = [
  { label: "Simple",        email: "demo.simple@easy-books.app",        model: "simple",        blurb: "Solo or micro-business — just the essentials" },
  { label: "Services",      email: "demo.services@easy-books.app",      model: "services",      blurb: "Agencies & consultancies — recurring revenue + deferred" },
  { label: "Trader",        email: "demo.trader@easy-books.app",        model: "trader",        blurb: "Buy-and-resell — inventory + COGS" },
  { label: "Manufacturing", email: "demo.manufacturing@easy-books.app", model: "manufacturing", blurb: "Value-addition on customer goods — BoMs, GRN, PO lifecycle" },
]
const DEMO_PASSWORD = "demo1234"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)
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
      router.push("/dashboard")
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

  return (
    <div className="min-h-screen bg-[#f6f3ee] flex items-center justify-center p-4 sm:p-6 font-sans">
      <div className="w-full max-w-md sm:max-w-2xl grid gap-6 sm:grid-cols-2">
        {/* ── Left: regular login ─────────────────────────────────── */}
        <div className="sm:order-1">
          <div className="text-center mb-6 sm:text-left">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-[#b8943f] rounded-2xl mb-3 font-serif text-2xl font-bold text-black">
              M
            </div>
            <h1 className="text-3xl font-serif text-[#1a1814] leading-tight">Easy-Books</h1>
            <p className="text-[#1a1814]/60 text-sm">SaaS Bookkeeping for Enterprises</p>
          </div>

          <div className="bg-white p-6 sm:p-7 rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5">
            <h2 className="text-xl font-serif text-[#1a1814] mb-4">Welcome Back</h2>
            <form onSubmit={handleLogin} className="space-y-3">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2.5 bg-white border border-[#1a1814]/10 rounded-xl focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814] text-sm"
                  placeholder="you@example.com"
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
                  className="w-full px-3 py-2.5 bg-white border border-[#1a1814]/10 rounded-xl focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814] text-sm"
                  placeholder="••••••••"
                  required
                />
              </div>
              {error && <p className="text-red-600 text-xs">{error}</p>}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-[#1a1814] text-white font-bold py-3 rounded-xl hover:bg-[#b8943f] hover:text-[#1a1814] transition-colors mt-3 disabled:opacity-50 text-sm"
              >
                {isLoading ? "Signing in..." : "Login"}
              </button>
            </form>
            <div className="mt-5 text-center text-xs text-[#1a1814]/45">
              Don&apos;t have an account?{" "}
              <Link href="/signup" className="text-[#b8943f] font-bold hover:underline">
                Start Free Trial
              </Link>
            </div>
          </div>
        </div>

        {/* ── Right: demo tenants ─────────────────────────────────── */}
        <div className="sm:order-2">
          <div className="bg-gradient-to-br from-[#1a1814] to-[#2d2620] text-white rounded-3xl p-6 sm:p-7 shadow-xl shadow-black/10 h-full flex flex-col">
            <div className="flex items-center gap-2 mb-3">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#ffd966]">
                Live Demo
              </p>
            </div>
            <h2 className="text-xl font-serif text-white mb-1">Try Easy-Books in seconds</h2>
            <p className="text-xs text-white/55 mb-5 leading-relaxed">
              Four pre-seeded demo tenants — one per business model — each with
              12 customers, 12 vendors, 12 invoices, 12 bills, and full
              transaction history. Click one to log in:
            </p>

            <div className="space-y-2 flex-1">
              {DEMO_OPTIONS.map(o => (
                <button
                  key={o.email}
                  type="button"
                  disabled={isLoading}
                  onClick={() => doLogin(o.email, DEMO_PASSWORD)}
                  className="w-full text-left bg-white/5 hover:bg-[#b8943f]/20 border border-white/10 hover:border-[#b8943f]/60 rounded-xl px-3 py-2.5 transition-all disabled:opacity-50 group"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-white group-hover:text-[#ffd966]">
                      {o.label}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider text-white/40 group-hover:text-[#ffd966]">
                      {o.model}
                    </span>
                  </div>
                  <p className="text-[11px] text-white/50 mt-0.5 leading-tight">{o.blurb}</p>
                </button>
              ))}
            </div>

            <p className="text-[10px] text-white/35 mt-4 leading-relaxed">
              Demo password:{" "}
              <code className="text-white/55 font-mono bg-white/5 px-1 py-0.5 rounded">
                demo1234
              </code>{" "}
              · You can edit data freely — it persists until re-seeded.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
