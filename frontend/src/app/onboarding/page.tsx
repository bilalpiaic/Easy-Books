"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  BookOpen, Briefcase, ShoppingCart, Factory,
  Radio, Stethoscope, FileCheck, Check, Loader2, Settings2,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { getCurrentUser } from "@/lib/auth"

interface Package {
  id: string
  label: string
  tagline: string
  icon: React.ElementType
  accent: string
  modules: string[]   // IDs to install (base is always installed; omit it)
  features: string[]
}

const PACKAGES: Package[] = [
  {
    id: "simple",
    label: "Simple",
    tagline: "Solo & micro-business",
    icon: BookOpen,
    accent: "#b8943f",
    modules: [],
    features: ["Chart of Accounts", "Invoicing & AR/AP", "Bank reconciliation", "Financial statements"],
  },
  {
    id: "services",
    label: "Services",
    tagline: "Agencies & consultancies",
    icon: Briefcase,
    accent: "#7c9b6b",
    modules: [],
    features: ["Everything in Simple", "Recurring invoices", "Deferred revenue (IFRS-15)", "AR aging & statements"],
  },
  {
    id: "trader",
    label: "Trader",
    tagline: "Buy & resell",
    icon: ShoppingCart,
    accent: "#5b8fa8",
    modules: ["inventory"],
    features: ["Everything in Simple", "Inventory (FIFO)", "Purchase orders & GRN", "COGS auto-posting"],
  },
  {
    id: "manufacturing",
    label: "Manufacturing",
    tagline: "Value-addition",
    icon: Factory,
    accent: "#8a6a9a",
    modules: ["inventory", "production"],
    features: ["Everything in Trader", "Bills of Materials", "Production orders", "Material consumption"],
  },
  {
    id: "telecom_franchise",
    label: "Telecom Franchise",
    tagline: "Operator franchise",
    icon: Radio,
    accent: "#c07a3a",
    modules: ["inventory", "telecom"],
    features: ["Everything in Simple", "Franchise tracker chain", "RSO / DSO agents", "FCA targets & commissions"],
  },
  {
    id: "hospital",
    label: "Healthcare",
    tagline: "Hospital & clinic",
    icon: Stethoscope,
    accent: "#5a9a7a",
    modules: ["hrm", "inventory", "healthcare"],
    features: ["Patient OPD & IPD", "Lab orders & results", "Pharmacy dispense", "Ward & bed management"],
  },
  {
    id: "pra_einvoice",
    label: "PRA e-Invoice",
    tagline: "Pakistani retail — PKR",
    icon: FileCheck,
    accent: "#a05a5a",
    modules: ["pra"],
    features: ["Everything in Simple", "PRA sandbox integration", "e-Invoice portal", "Buyer NTN / CNIC"],
  },
]

export default function OnboardingPage() {
  const router = useRouter()
  const [installing, setInstalling] = useState<string | null>(null)
  const [error, setError] = useState("")
  const [done, setDone] = useState(false)

  useEffect(() => {
    const user = getCurrentUser()
    if (!user) { router.replace("/login"); return }
    if (localStorage.getItem(`eb.onboarded.${user.email}`)) {
      router.replace("/dashboard")
    }
  }, [router])

  const selectPackage = async (pkg: Package) => {
    setInstalling(pkg.id)
    setError("")
    try {
      for (const id of pkg.modules) {
        await apiFetch(`/api/modules/${id}/install`, { method: "POST" })
      }
      const user = getCurrentUser()
      if (user) localStorage.setItem(`eb.onboarded.${user.email}`, "1")
      setDone(true)
      setTimeout(() => router.replace("/dashboard"), 1100)
    } catch {
      setError("Setup failed — please try again or skip to configure manually.")
      setInstalling(null)
    }
  }

  const skip = () => {
    const user = getCurrentUser()
    if (user) localStorage.setItem(`eb.onboarded.${user.email}`, "1")
    router.replace("/dashboard")
  }

  if (done) {
    return (
      <div className="min-h-screen bg-[#f6f3ee] flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-16 h-16 bg-[#b8943f] rounded-full flex items-center justify-center mx-auto">
            <Check className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-bold text-[#1a1814]">All set!</h2>
          <p className="text-sm text-[#1a1814]/55">Taking you to your dashboard…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#f6f3ee] flex flex-col">
      {/* Header */}
      <header className="flex items-center gap-3 px-6 py-4 border-b border-[#1a1814]/8 bg-white/60 backdrop-blur-sm">
        <div className="w-8 h-8 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-sm select-none">
          E
        </div>
        <span className="font-serif font-semibold text-[#1a1814]">Easy-Books</span>
      </header>

      {/* Body */}
      <div className="flex-1 flex flex-col items-center py-12 px-4">
        <div className="w-full max-w-3xl space-y-8">

          {/* Hero */}
          <div className="text-center space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[#b8943f]/80">Step 1 of 1</p>
            <h1 className="text-3xl font-bold font-serif text-[#1a1814]">
              What kind of business are you?
            </h1>
            <p className="text-[#1a1814]/55 text-sm">
              We&apos;ll activate the right features for your industry. You can always add or remove modules later.
            </p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm text-center">
              {error}
            </div>
          )}

          {/* Package cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {PACKAGES.map(pkg => {
              const Icon = pkg.icon
              const isInstalling = installing === pkg.id
              const isDisabled = !!installing
              return (
                <button
                  key={pkg.id}
                  onClick={() => selectPackage(pkg)}
                  disabled={isDisabled}
                  className="text-left bg-white border border-[#1a1814]/8 hover:border-[#b8943f]/40 rounded-2xl p-5 flex flex-col gap-3.5 transition-all hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed group"
                >
                  {/* Icon + label */}
                  <div className="flex items-start gap-3">
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors"
                      style={{ backgroundColor: pkg.accent + "18" }}
                    >
                      <Icon className="w-5 h-5" style={{ color: pkg.accent }} />
                    </div>
                    <div className="min-w-0 pt-0.5">
                      <p className="font-bold text-[#1a1814] text-sm">{pkg.label}</p>
                      <p className="text-[11px] text-[#1a1814]/45 mt-0.5">{pkg.tagline}</p>
                    </div>
                  </div>

                  {/* Features */}
                  <ul className="space-y-1.5 flex-1">
                    {pkg.features.map(f => (
                      <li key={f} className="flex items-center gap-2 text-[12px] text-[#1a1814]/55">
                        <span
                          className="w-1 h-1 rounded-full flex-shrink-0"
                          style={{ backgroundColor: pkg.accent }}
                        />
                        {f}
                      </li>
                    ))}
                  </ul>

                  {/* Action */}
                  <div
                    className="flex items-center justify-center gap-1.5 py-2 rounded-lg text-[12px] font-semibold border transition-colors"
                    style={{
                      backgroundColor: pkg.accent + "12",
                      color: pkg.accent,
                      borderColor: pkg.accent + "30",
                    }}
                  >
                    {isInstalling
                      ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Setting up…</>
                      : <>Select {pkg.label}</>
                    }
                  </div>
                </button>
              )
            })}
          </div>

          {/* Footer actions */}
          <div className="flex items-center justify-between pt-2 border-t border-[#1a1814]/8">
            <button
              onClick={skip}
              disabled={!!installing}
              className="flex items-center gap-1.5 text-sm text-[#1a1814]/40 hover:text-[#1a1814]/70 transition-colors disabled:opacity-40"
            >
              Skip — I&apos;ll start with base accounting
            </button>
            <a
              href="/add-ons"
              className="flex items-center gap-1.5 text-sm text-[#1a1814]/40 hover:text-[#1a1814]/70 transition-colors"
            >
              <Settings2 className="w-3.5 h-3.5" />
              Customize modules manually
            </a>
          </div>

        </div>
      </div>
    </div>
  )
}
