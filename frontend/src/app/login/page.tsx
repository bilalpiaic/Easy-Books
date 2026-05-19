"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { setAuthToken } from "@/lib/auth"
import { apiBase } from "@/lib/api"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
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

      if (!response.ok) {
        throw new Error("Invalid email or password")
      }

      const data = await response.json()
      setAuthToken(data.access_token)
      router.push("/dashboard")
    } catch (err: any) {
      setError(err.message)
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
          <h2 className="text-2xl font-serif text-[#1a1814] mb-6">Welcome Back</h2>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 bg-white border border-[#1a1814]/10 rounded-xl focus:ring-2 focus:ring-[#b8943f] focus:border-transparent outline-none text-[#1a1814]"
                placeholder="you@example.com"
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
              {isLoading ? "Signing in..." : "Login"}
            </button>
          </form>

          <div className="mt-8 text-center text-sm text-[#1a1814]/40">
            Don't have an account?{" "}
            <a href="#" className="text-[#b8943f] font-bold hover:underline">
              Start Free Trial
            </a>
          </div>

        </div>
      </div>
    </div>
  )
}
