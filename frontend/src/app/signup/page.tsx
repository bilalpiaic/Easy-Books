"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { setAuthToken } from "@/lib/auth"
import { apiBase } from "@/lib/api"
import { BusinessModelPicker, type BusinessModel } from "@/components/BusinessModelPicker"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { FieldHint } from "@/components/guidance/FieldHint"

type Step = "model" | "account"

export default function SignupPage() {
  const [step, setStep] = useState<Step>("model")
  const [businessModel, setBusinessModel] = useState<BusinessModel>("simple")

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

    if (password.length < 8) {
      setError("Password must be at least 8 characters")
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
          business_model: businessModel,
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
    <div className="min-h-screen bg-[#f6f3ee] flex items-center justify-center p-4 sm:p-6 font-sans">
      <div className="max-w-2xl w-full">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-[#b8943f] rounded-2xl mb-4 font-serif text-2xl font-bold text-black">
            E
          </div>
          <h1 className="text-3xl sm:text-4xl font-serif text-[#1a1814] mb-1">Easy-Books</h1>
          <p className="text-sm text-[#1a1814]/60">Multi-tenant double-entry accounting</p>
        </div>

        {/* Step progress */}
        <div className="flex items-center justify-center gap-2 mb-5">
          <div className={`flex items-center gap-2 ${step === "model" ? "text-[#b8943f]" : "text-[#1a1814]/40"}`}>
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold ${step === "model" ? "bg-[#b8943f] text-white" : "bg-[#1a1814]/10 text-[#1a1814]/50"}`}>1</div>
            <span className="text-xs font-semibold uppercase tracking-wider">Business type</span>
          </div>
          <div className="w-8 h-px bg-[#1a1814]/15" />
          <div className={`flex items-center gap-2 ${step === "account" ? "text-[#b8943f]" : "text-[#1a1814]/40"}`}>
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold ${step === "account" ? "bg-[#b8943f] text-white" : "bg-[#1a1814]/10 text-[#1a1814]/50"}`}>2</div>
            <span className="text-xs font-semibold uppercase tracking-wider">Your account</span>
          </div>
        </div>

        <div className="bg-white p-6 sm:p-7 rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5">
          {step === "model" ? (
            <>
              <h2 className="text-xl font-serif text-[#1a1814] mb-1">What type of business is this?</h2>
              <p className="text-xs text-[#1a1814]/55 mb-4">
                Pick the closest match. We&apos;ll pre-configure your Chart of Accounts and only show
                you the features you&apos;ll actually use. You can change this later.
              </p>

              <HelpCallout title="Not sure which one to pick?" tone="tip" defaultOpen>
                <p className="mb-1.5">
                  Choose the option that best describes <em>most</em> of what your business does today.
                  Each model adds the right accounts to your books:
                </p>
                <ul className="list-disc pl-4 space-y-0.5">
                  <li><strong>Simple</strong> — you invoice clients and pay bills; no stock.</li>
                  <li><strong>Services</strong> — you bill for time or projects, not physical goods.</li>
                  <li><strong>Trader</strong> — you buy and resell physical goods (inventory).</li>
                  <li><strong>Manufacturing</strong> — you make products, or process customer-supplied goods for a fee.</li>
                </ul>
                <p className="mt-2 text-[10px] text-[#1a1814]/45">
                  Switching later via Settings adds the missing accounts but never removes existing ones,
                  so your books stay intact.
                </p>
              </HelpCallout>

              <div className="mt-4">
                <BusinessModelPicker value={businessModel} onChange={setBusinessModel} />
              </div>

              <button
                type="button"
                onClick={() => setStep("account")}
                className="mt-5 w-full bg-[#1a1814] text-white font-bold py-3.5 rounded-xl hover:bg-[#b8943f] hover:text-[#1a1814] transition-colors flex items-center justify-center gap-2"
              >
                Continue
                <ChevronRight className="w-4 h-4" />
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setStep("model")}
                className="flex items-center gap-1 text-xs text-[#1a1814]/55 hover:text-[#b8943f] transition-colors mb-3"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Back to business type
              </button>
              <h2 className="text-xl font-serif text-[#1a1814] mb-1">Create your account</h2>
              <p className="text-xs text-[#1a1814]/55 mb-4">
                Selected: <strong className="text-[#b8943f]">{businessModel.charAt(0).toUpperCase() + businessModel.slice(1)}</strong>
              </p>

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
                  <FieldHint>
                    Becomes your tenant&apos;s display name. You can change it later in Settings.
                  </FieldHint>
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
                  <FieldHint>
                    Used for login. Becomes the first <em>owner</em> of your books — you can invite more users later.
                  </FieldHint>
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
                    minLength={8}
                    required
                  />
                  <FieldHint>Minimum 8 characters. Stored as bcrypt hash, not in plaintext.</FieldHint>
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
                    minLength={8}
                    required
                  />
                </div>

                {error && (
                  <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full bg-[#1a1814] text-white font-bold py-4 rounded-xl hover:bg-[#b8943f] hover:text-[#1a1814] transition-colors mt-2 disabled:opacity-50"
                >
                  {isLoading ? "Creating account..." : "Create Account"}
                </button>
              </form>
            </>
          )}

          <div className="mt-7 text-center text-sm text-[#1a1814]/45">
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
