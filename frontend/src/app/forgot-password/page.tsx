"use client"

import { useState } from "react"
import Link from "next/link"
import { apiBase, networkErrorMessage } from "@/lib/api"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [sent, setSent] = useState(false)
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)
    try {
      const response = await fetch(`${apiBase}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      if (!response.ok && response.status === 429) {
        throw new Error("Too many reset requests. Wait a few minutes and try again.")
      }
      if (!response.ok) {
        throw new Error("Could not submit that request. Try again shortly.")
      }
      setSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : networkErrorMessage(err, "Request failed"))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f6f3ee] font-sans flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-[#b8943f] rounded-xl mb-3 font-serif text-2xl font-bold text-black select-none">
            M
          </div>
          <h1 className="font-serif text-3xl text-[#1a1814]">Easy-Books</h1>
          <p className="text-sm text-[#1a1814]/70 mt-1">Reset your password</p>
        </div>
        <form onSubmit={submit} className="space-y-4 bg-white/60 border border-[#1a1814]/10 rounded-2xl p-6">
          {sent ? (
            <p className="text-sm text-[#1a1814]/80">
              If that account exists, we sent a reset link. Check your inbox (and spam), then
              return to <Link href="/login" className="underline">sign in</Link>.
            </p>
          ) : (
            <>
              <div>
                <label className="block text-xs font-medium text-[#1a1814]/70 mb-1">Email</label>
                <input
                  type="email"
                  className="w-full border border-[#1a1814]/15 rounded-lg px-3 py-2"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              {error && <p className="text-sm text-red-700">{error}</p>}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-[#b8943f] text-black font-medium rounded-lg py-2.5 disabled:opacity-50"
              >
                {isLoading ? "Sending…" : "Send reset link"}
              </button>
            </>
          )}
          <p className="text-center text-xs text-[#1a1814]/50">
            <Link href="/login" className="underline">Back to sign in</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
