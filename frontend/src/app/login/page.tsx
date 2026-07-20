"use client"

import { useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { setAuthToken, setMustChangePwd } from "@/lib/auth"
import { apiBase } from "@/lib/api"

const DEMO_EMAIL = "demo.simple@easy-books.app"
const DEMO_PASSWORD = "demo1234"

function LoginForm() {
  const search = useSearchParams()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const router = useRouter()

  useEffect(() => {
    if (search.get("demo") === "1") {
      setEmail(DEMO_EMAIL)
      setPassword(DEMO_PASSWORD)
    }
  }, [search])

  const doLogin = async (user: string, pass: string) => {
    const formData = new FormData()
    formData.append("username", user)
    formData.append("password", pass)
    const response = await fetch(`${apiBase}/api/auth/login`, {
      method: "POST",
      body: formData,
    })
    if (!response.ok) throw new Error("Invalid email or password")
    const data = await response.json()
    setAuthToken(data.access_token)
    setMustChangePwd(!!data.must_change_password)
    if (data.must_change_password) {
      router.push("/profile?changePassword=1")
    } else {
      router.push("/dashboard")
    }
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError("")
    try {
      await doLogin(email, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed")
    } finally {
      setIsLoading(false)
    }
  }

  const tryDemo = async () => {
    setDemoLoading(true)
    setError("")
    try {
      await doLogin(DEMO_EMAIL, DEMO_PASSWORD)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Demo unavailable — the server may still be starting up. Try again shortly.",
      )
      setDemoLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f6f3ee] font-sans flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-[#b8943f] rounded-xl mb-3 font-serif text-2xl font-bold text-black select-none">
            M
          </div>
          <h1 className="text-3xl font-serif text-[#1a1814] leading-tight">Easy-Books</h1>
          <p className="text-[#1a1814]/50 text-sm mt-1">SaaS Bookkeeping for Enterprises</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg shadow-black/5 border border-[#1a1814]/5 p-6">
          <h2 className="text-lg font-serif text-[#1a1814] mb-4">Sign in to your account</h2>

          <form onSubmit={handleLogin} className="space-y-3.5">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full px-3 py-2.5 bg-white border border-[#1a1814]/10 rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814] text-sm"
                placeholder="you@company.com"
                autoComplete="email"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
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
              disabled={isLoading || demoLoading}
              className="w-full bg-[#1a1814] text-white font-semibold py-2.5 rounded-lg hover:bg-[#b8943f] hover:text-[#1a1814] transition-all mt-1 disabled:opacity-50 text-sm"
            >
              {isLoading ? "Signing in…" : "Sign In"}
            </button>
          </form>
        </div>

        <div className="mt-5 space-y-3 text-center">
          <button
            type="button"
            onClick={tryDemo}
            disabled={demoLoading || isLoading}
            className="flex items-center justify-center gap-2 w-full border border-[#1a1814]/12 bg-white rounded-xl py-2.5 text-sm font-medium text-[#1a1814]/70 hover:text-[#b8943f] hover:border-[#b8943f]/40 transition-all disabled:opacity-50"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            {demoLoading ? "Opening demo…" : "Try the live demo"}
          </button>
          <p className="text-[11px] text-[#1a1814]/35">
            One sample company with Base Accounting. Install industry add-ons inside the app.
          </p>
          <p className="text-xs text-[#1a1814]/40">
            New to Easy-Books?{" "}
            <Link href="/signup" className="text-[#b8943f] font-semibold hover:underline">
              Start a free trial
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#f6f3ee]" />}>
      <LoginForm />
    </Suspense>
  )
}
