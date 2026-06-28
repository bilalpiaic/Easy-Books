"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  BookOpen, Briefcase, ShoppingCart, Factory,
  Radio, Stethoscope, FileCheck, ArrowLeft, ArrowRight, Loader2,
} from "lucide-react"
import { setAuthToken, setMustChangePwd } from "@/lib/auth"
import { apiBase } from "@/lib/api"

const DEMO_PASSWORD = "demo1234"

const DEMOS = [
  {
    id: "simple",
    label: "Simple",
    tagline: "Solo & micro-business",
    email: "demo.simple@easy-books.app",
    icon: BookOpen,
    accent: "#b8943f",
    features: ["Core GL & Chart of Accounts", "Invoicing & AR/AP", "Bank reconciliation", "Financial reports"],
  },
  {
    id: "services",
    label: "Services",
    tagline: "Agencies & consultancies",
    email: "demo.services@easy-books.app",
    icon: Briefcase,
    accent: "#7c9b6b",
    features: ["Recurring revenue", "Deferred revenue (IFRS-15)", "AR/AP aging", "Customer statements"],
  },
  {
    id: "trader",
    label: "Trader",
    tagline: "Buy & resell",
    email: "demo.trader@easy-books.app",
    icon: ShoppingCart,
    accent: "#5b8fa8",
    features: ["Inventory tracking (FIFO)", "Purchase orders & GRN", "COGS auto-posting", "Stock valuation"],
  },
  {
    id: "manufacturing",
    label: "Manufacturing",
    tagline: "Value-addition",
    email: "demo.manufacturing@easy-books.app",
    icon: Factory,
    accent: "#8a6a9a",
    features: ["Bills of Materials", "Production orders", "Raw material consumption", "Fixed assets & FX"],
  },
  {
    id: "telecom",
    label: "Telecom Franchise",
    tagline: "Operator franchise",
    email: "demo.telecom@easy-books.app",
    icon: Radio,
    accent: "#c07a3a",
    features: ["Bank → Tracker → MSR chain", "RSO / DSO agent management", "FCA franchise targets", "Commission ledger"],
  },
  {
    id: "healthcare",
    label: "Healthcare",
    tagline: "Hospital & clinic",
    email: "demo.hospital@easy-books.app",
    icon: Stethoscope,
    accent: "#5a9a7a",
    features: ["OPD tokens & visits", "IPD admissions & discharge", "Lab orders & results", "Pharmacy dispense"],
  },
  {
    id: "pra",
    label: "PRA e-Invoice",
    tagline: "Pakistani retail — PKR",
    email: "demo.pra@easy-books.app",
    icon: FileCheck,
    accent: "#a05a5a",
    features: ["PRA sandbox integration", "e-Invoice portal view", "Buyer NTN / CNIC fields", "PKR currency"],
  },
]

export default function DemoPortalPage() {
  const router = useRouter()
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState("")

  const enter = async (email: string, id: string) => {
    setLoading(id)
    setError("")
    try {
      const form = new FormData()
      form.append("username", email)
      form.append("password", DEMO_PASSWORD)
      const res = await fetch(`${apiBase}/api/auth/login`, { method: "POST", body: form })
      if (!res.ok) throw new Error("Demo unavailable — the server may still be starting up. Try again shortly.")
      const data = await res.json()
      setAuthToken(data.access_token)
      setMustChangePwd(false)
      router.push("/dashboard")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed")
      setLoading(null)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a1814] via-[#221d16] to-[#2d2620] flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-5 sm:px-8 py-4 border-b border-white/5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-sm select-none">
            M
          </div>
          <span className="font-serif font-semibold text-white">Easy-Books</span>
          <span className="hidden sm:inline text-white/20 text-xs ml-1">· Demo Portal</span>
        </div>
        <Link
          href="/login"
          className="flex items-center gap-1.5 text-white/40 hover:text-white/80 text-sm transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Login
        </Link>
      </header>

      {/* Hero */}
      <div className="text-center px-4 pt-10 pb-8">
        <div className="inline-flex items-center gap-2 bg-[#b8943f]/10 border border-[#b8943f]/25 rounded-full px-3.5 py-1 mb-5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-[#ffd966]">
            Live Demo Environment
          </span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-serif text-white mb-3">
          Explore Easy-Books
        </h1>
        <p className="text-white/50 text-sm sm:text-base max-w-md mx-auto leading-relaxed">
          Seven fully-seeded companies — one per business model.
          Click a card to enter instantly. No signup required.
        </p>
        {error && (
          <p className="mt-4 text-red-300 text-sm bg-red-950/50 border border-red-700/40 rounded-xl px-4 py-2.5 inline-block max-w-sm">
            {error}
          </p>
        )}
      </div>

      {/* Cards grid */}
      <div className="flex-1 px-4 sm:px-6 pb-14 max-w-5xl mx-auto w-full">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {DEMOS.map(demo => {
            const Icon = demo.icon
            const isEntering = loading === demo.id
            return (
              <div
                key={demo.id}
                className="bg-white/[0.04] hover:bg-white/[0.07] border border-white/8 rounded-2xl p-5 flex flex-col gap-4 transition-all"
              >
                {/* Icon + labels */}
                <div className="flex items-start gap-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: demo.accent + "20" }}
                  >
                    <Icon className="w-5 h-5" style={{ color: demo.accent }} />
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-white text-sm">{demo.label}</p>
                    <p className="text-[11px] text-white/40 mt-0.5">{demo.tagline}</p>
                  </div>
                </div>

                {/* Feature list */}
                <ul className="space-y-1.5 flex-1">
                  {demo.features.map(f => (
                    <li key={f} className="flex items-center gap-2 text-[12px] text-white/50">
                      <span
                        className="w-1 h-1 rounded-full flex-shrink-0"
                        style={{ backgroundColor: demo.accent }}
                      />
                      {f}
                    </li>
                  ))}
                </ul>

                {/* CTA */}
                <button
                  onClick={() => enter(demo.email, demo.id)}
                  disabled={!!loading}
                  className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-sm font-semibold border transition-all disabled:opacity-40 cursor-pointer"
                  style={{
                    backgroundColor: demo.accent + "18",
                    color: demo.accent,
                    borderColor: demo.accent + "35",
                  }}
                >
                  {isEntering
                    ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Entering…</>
                    : <>Enter Demo <ArrowRight className="w-3.5 h-3.5" /></>
                  }
                </button>
              </div>
            )
          })}
        </div>

        {/* Password hint */}
        <p className="text-center text-white/20 text-xs mt-10">
          All demo accounts use password{" "}
          <code className="text-white/35 font-mono bg-white/5 px-1.5 py-0.5 rounded">
            {DEMO_PASSWORD}
          </code>
          {" "}· Demo data resets periodically
        </p>
      </div>
    </div>
  )
}
