"use client"

import { useEffect, useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { setAuthToken, setMustChangePwd, setMustSetupTotp, isAuthenticated, reconcileAuthOnLoad } from "@/lib/auth"
import { apiBase, networkErrorMessage } from "@/lib/api"

const DEMO_EMAIL = "demo.simple@easy-books.app"
const DEMO_PASSWORD = "demo1234"

function LoginForm() {
  const search = useSearchParams()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [otp, setOtp] = useState("")
  const [partialToken, setPartialToken] = useState("")
  const [needsTotp, setNeedsTotp] = useState(false)
  const [providers, setProviders] = useState<{ google?: boolean; microsoft?: boolean; demo_login?: boolean }>({})
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const router = useRouter()

  useEffect(() => {
    reconcileAuthOnLoad()
    // Mid-session visit to /login (already signed in this tab) → dashboard
    if (isAuthenticated()) {
      router.replace("/dashboard")
      return
    }
    if (search.get("demo") === "1") {
      setEmail(DEMO_EMAIL)
      setPassword(DEMO_PASSWORD)
    }
    const ssoToken = search.get("token")
    if (search.get("sso") === "1" && ssoToken) {
      setAuthToken(ssoToken)
      router.push("/dashboard")
    }
    const partial = search.get("partial")
    if (search.get("totp") === "1" && partial) {
      setPartialToken(partial)
      setNeedsTotp(true)
    }
    fetch(`${apiBase}/api/auth/oauth/providers`)
      .then((r) => r.json())
      .then(setProviders)
      .catch(() => {})
  }, [search, router])

  const finishLogin = (data: {
    access_token: string
    must_change_password?: boolean
    totp_setup_required?: boolean
  }) => {
    setAuthToken(data.access_token)
    setMustChangePwd(!!data.must_change_password)
    setMustSetupTotp(!!data.totp_setup_required)
    if (data.must_change_password) {
      router.push("/profile?changePassword=1")
    } else if (data.totp_setup_required) {
      router.push("/profile?setup2fa=1")
    } else {
      router.push("/dashboard")
    }
  }

  const doLogin = async (user: string, pass: string) => {
    const formData = new FormData()
    formData.append("username", user)
    formData.append("password", pass)
    let response: Response
    try {
      response = await fetch(`${apiBase}/api/auth/login`, {
        method: "POST",
        body: formData,
      })
    } catch (err) {
      throw new Error(networkErrorMessage(err, "Login failed"))
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      // Keep 401 copy stable (form is email, API says "username"). Other
      // statuses still surface API detail (demo-disabled, deactivated, throttle).
      if (response.status === 401) {
        throw new Error("Invalid email or password")
      }
      throw new Error(typeof body.detail === "string" ? body.detail : "Invalid email or password")
    }
    const data = await response.json()
    if (data.requires_totp) {
      setPartialToken(data.partial_token)
      setNeedsTotp(true)
      return
    }
    finishLogin(data)
  }

  const verifyTotp = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError("")
    try {
      const response = await fetch(`${apiBase}/api/auth/totp/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ partial_token: partialToken, code: otp }),
      })
      if (!response.ok) throw new Error("Invalid authenticator code")
      finishLogin(await response.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : "OTP failed")
    } finally {
      setIsLoading(false)
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
          <h1 className="font-serif text-3xl text-[#1a1814]">Easy-Books</h1>
          <p className="text-sm text-[#1a1814]/70 mt-1">Sign in to continue</p>
        </div>

        {needsTotp ? (
          <form onSubmit={verifyTotp} className="space-y-4 bg-white/60 border border-[#1a1814]/10 rounded-2xl p-6">
            <p className="text-sm text-[#1a1814]/80">Enter the 6-digit code from your authenticator app.</p>
            <input
              className="w-full border border-[#1a1814]/15 rounded-lg px-3 py-2 tracking-widest text-center text-lg"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              autoFocus
            />
            {error && <p className="text-sm text-red-700">{error}</p>}
            <button
              type="submit"
              disabled={isLoading || otp.length < 6}
              className="w-full bg-[#b8943f] text-black font-medium rounded-lg py-2.5 disabled:opacity-50"
            >
              {isLoading ? "Verifying…" : "Verify"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleLogin} className="space-y-4 bg-white/60 border border-[#1a1814]/10 rounded-2xl p-6">
            <div>
              <label className="block text-xs font-medium text-[#1a1814]/70 mb-1">Email</label>
              <input
                type="email"
                className="w-full border border-[#1a1814]/15 rounded-lg px-3 py-2"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#1a1814]/70 mb-1">Password</label>
              <input
                type="password"
                className="w-full border border-[#1a1814]/15 rounded-lg px-3 py-2"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-red-700">{error}</p>}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-[#b8943f] text-black font-medium rounded-lg py-2.5 disabled:opacity-50"
            >
              {isLoading ? "Signing in…" : "Sign in"}
            </button>
            {providers.demo_login !== false && (
              <button
                type="button"
                onClick={tryDemo}
                disabled={demoLoading}
                className="w-full border border-[#1a1814]/20 rounded-lg py-2 text-sm"
              >
                {demoLoading ? "Opening demo…" : "Try demo"}
              </button>
            )}
            {(providers.google || providers.microsoft) && (
              <div className="pt-2 space-y-2 border-t border-[#1a1814]/10">
                {providers.google && (
                  <a
                    href={`${apiBase}/api/auth/oauth/google`}
                    className="block w-full text-center border border-[#1a1814]/20 rounded-lg py-2 text-sm"
                  >
                    Continue with Google
                  </a>
                )}
                {providers.microsoft && (
                  <a
                    href={`${apiBase}/api/auth/oauth/microsoft`}
                    className="block w-full text-center border border-[#1a1814]/20 rounded-lg py-2 text-sm"
                  >
                    Continue with Microsoft
                  </a>
                )}
              </div>
            )}
            <p className="text-center text-xs text-[#1a1814]/50">
              No account? <Link href="/signup" className="underline">Sign up</Link>
            </p>
          </form>
        )}
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
