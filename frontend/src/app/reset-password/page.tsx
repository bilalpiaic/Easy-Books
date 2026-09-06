"use client"

import { Suspense, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { apiBase, apiFetch, networkErrorMessage } from "@/lib/api"

function ResetPasswordForm() {
  const params = useSearchParams()
  const router = useRouter()
  const token = params.get("token") ?? ""
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [tokenOk, setTokenOk] = useState<boolean | null>(token ? null : false)

  useEffect(() => {
    if (!token) {
      setTokenOk(false)
      setError("This reset link is invalid or has expired")
      return
    }
    fetch(`${apiBase}/api/auth/reset-password/${encodeURIComponent(token)}`)
      .then((r) => {
        if (!r.ok) throw new Error("invalid")
        setTokenOk(true)
      })
      .catch((err) => {
        setTokenOk(false)
        const raw = err instanceof Error ? err.message : ""
        setError(
          /failed to fetch|networkerror|load failed/i.test(raw)
            ? networkErrorMessage(err, "Could not reach the server")
            : "This reset link is invalid or has expired",
        )
      })
  }, [token])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    if (password.length < 8) {
      setError("Password must be at least 8 characters")
      return
    }
    if (password !== confirm) {
      setError("Passwords do not match")
      return
    }
    setIsLoading(true)
    try {
      await apiFetch("/api/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      })
      router.push("/login")
    } catch (err) {
      setError(networkErrorMessage(err, "This reset link is invalid or has expired"))
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
          <p className="text-sm text-[#1a1814]/70 mt-1">Choose a new password</p>
        </div>
        <form onSubmit={submit} className="space-y-4 bg-white/60 border border-[#1a1814]/10 rounded-2xl p-6">
          {tokenOk === false ? (
            <>
              <p className="text-sm text-red-700">{error || "This reset link is invalid or has expired"}</p>
              <p className="text-center text-xs text-[#1a1814]/50">
                <Link href="/forgot-password" className="underline">Request a new link</Link>
              </p>
            </>
          ) : (
            <>
              <div>
                <label className="block text-xs font-medium text-[#1a1814]/70 mb-1">New password</label>
                <input
                  type="password"
                  className="w-full border border-[#1a1814]/15 rounded-lg px-3 py-2"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#1a1814]/70 mb-1">Confirm password</label>
                <input
                  type="password"
                  className="w-full border border-[#1a1814]/15 rounded-lg px-3 py-2"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={8}
                />
              </div>
              {error && <p className="text-sm text-red-700">{error}</p>}
              <button
                type="submit"
                disabled={isLoading || tokenOk !== true}
                className="w-full bg-[#b8943f] text-black font-medium rounded-lg py-2.5 disabled:opacity-50"
              >
                {isLoading ? "Saving…" : "Update password"}
              </button>
              <p className="text-center text-xs text-[#1a1814]/50">
                <Link href="/login" className="underline">Back to sign in</Link>
              </p>
            </>
          )}
        </form>
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#f6f3ee]" />}>
      <ResetPasswordForm />
    </Suspense>
  )
}
