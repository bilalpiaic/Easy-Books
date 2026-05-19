"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { setAuthToken } from "@/lib/auth"
import { apiBase } from "@/lib/api"

export default function SignupPage() {
  const [fullName, setFullName] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (password.length < 6) {
      setError("Password must be at least 6 characters")
      return
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match")
      return
    }

    setIsLoading(true)

    try {
      const signupRes = await fetch(`${apiBase}/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          company_name: companyName,
        }),
      })

      if (!signupRes.ok) {
        const data = await signupRes.json().catch(() => ({}))
        throw new Error(data.detail ?? "Signup failed")
      }

      const formData = new FormData()
      formData.append("username", email)
      formData.append("password", password)

      const loginRes = await fetch(`${apiBase}/api/auth/login`, {
        method: "POST",
        body: formData,
      })

      if (!loginRes.ok) {
        throw new Error("Account created — please log in")
      }

      const data = await loginRes.json()
      setAuthToken(data.access_token)
      router.push("/dashboard")
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Signup failed")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f6f3ee] flex items-center justify-center p-6 font-sans">
      <div className="max-w-md w-full">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-[#b8943f] rounded-2xl mb-6 font-serif text-3xl font-bold text-black">
            M
          </div>
          <h1 className="text-4xl font-serif text-[#1a1814] mb-2">Easy-Books</h1>
          <p className="text-[#1a1814]/60">SaaS Bookkeeping for Enterprises</p>
        </div>

        <div className="bg-white p-8 rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5">
          <h2 className="text-2xl font-serif text-[#1a1814] mb-6">Start Free Trial</h2>

          <form onSubmit={handleSignup} className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">
                Full Name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-4 py-3 bg-white border border-[#1a1814]/10 rounded-xl focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814]"
                placeholder="Jane Smith"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">
                Company Name
              </label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full px-4 py-3 bg-white border border-[#1a1814]/10 rounded-xl focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814]"
                placeholder="Acme Inc."
                required
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 bg-white border border-[#1a1814]/10 rounded-xl focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814]"
                placeholder="you@company.com"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 bg-white border border-[#1a1814]/10 rounded-xl focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814]"
                placeholder="••••••••"
                minLength={6}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">
                Confirm Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-4 py-3 bg-white border border-[#1a1814]/10 rounded-xl focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814]"
                placeholder="••••••••"
                minLength={6}
                required
              />
            </div>

            {error && (
              <p className="text-red-500 text-sm mt-2">{error}</p>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-[#1a1814] text-white font-bold py-4 rounded-xl hover:bg-[#b8943f] hover:text-[#1a1814] transition-colors mt-6 disabled:opacity-50"
            >
              {isLoading ? "Creating account..." : "Create Account"}
            </button>
          </form>

          <div className="mt-8 text-center text-sm text-[#1a1814]/40">
            Already have an account?{" "}
            <Link href="/login" className="text-[#b8943f] font-bold hover:underline">
              Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
