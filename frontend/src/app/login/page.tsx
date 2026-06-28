"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { setAuthToken, setMustChangePwd } from "@/lib/auth"
import { apiBase } from "@/lib/api"

export default function LoginPage() {
  const [email, setEmail]       = useState("")
  const [password, setPassword] = useState("")
  const [error, setError]       = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError("")
    try {
      const formData = new FormData()
      formData.append("username", email)
      formData.append("password", password)
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
      } else if (data.onboarding_required) {
        router.push("/onboarding")
      } else {
        router.push("/dashboard")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f6f3ee] font-sans flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm">

        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-[#b8943f] rounded-xl mb-3 font-serif text-2xl font-bold text-black select-none">
            M
          </div>
          <h1 className="text-3xl font-serif text-[#1a1814] leading-tight">Easy-Books</h1>
          <p className="text-[#1a1814]/50 text-sm mt-1">SaaS Bookkeeping for Enterprises</p>
        </div>

        {/* Login card */}
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
              disabled={isLoading}
              className="w-full bg-[#1a1814] text-white font-semibold py-2.5 rounded-lg hover:bg-[#b8943f] hover:text-[#1a1814] transition-all mt-1 disabled:opacity-50 text-sm"
            >
              {isLoading ? "Signing in…" : "Sign In"}
            </button>
          </form>
        </div>

        {/* Footer links */}
        <div className="mt-5 space-y-3 text-center">
          <Link
            href="/demo"
            className="flex items-center justify-center gap-2 w-full border border-[#1a1814]/12 bg-white rounded-xl py-2.5 text-sm font-medium text-[#1a1814]/70 hover:text-[#b8943f] hover:border-[#b8943f]/40 transition-all"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Explore with a live demo →
          </Link>
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
