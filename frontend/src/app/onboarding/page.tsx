"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { BookOpen, Package, Factory, Users, Radio, FileCheck, Check, ArrowRight, Loader2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { getCurrentUser } from "@/lib/auth"

const ICON_MAP: Record<string, React.ElementType> = {
  BookOpen, Package, Factory, Users, Radio, FileCheck,
}

interface ModuleInfo {
  id: string
  label: string
  description: string
  icon: string
  deps: string[]
  always: boolean
  installed: boolean
}

const CATEGORY_LABELS: Record<string, string> = {
  Core: "Always included",
  Operations: "Operations",
  HR: "Human Resources",
  Industry: "Industry add-ons",
}

export default function OnboardingPage() {
  const router = useRouter()
  const [modules, setModules] = useState<ModuleInfo[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const [step, setStep] = useState<"choose" | "done">("choose")

  useEffect(() => {
    const user = getCurrentUser()
    if (!user) { router.replace("/login"); return }

    // If already onboarded, skip to dashboard
    if (localStorage.getItem(`eb.onboarded.${user.email}`)) {
      router.replace("/dashboard"); return
    }

    apiFetch<ModuleInfo[]>("/api/modules")
      .then(data => { if (Array.isArray(data)) setModules(data) })
      .catch(() => router.replace("/dashboard"))
  }, [router])

  const toggle = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        // Also deselect any modules that depend on this one
        next.delete(id)
        modules.forEach(m => {
          if (m.deps.includes(id)) next.delete(m.id)
        })
      } else {
        // Also select deps
        const mod = modules.find(m => m.id === id)
        mod?.deps.forEach(d => next.add(d))
        next.add(id)
      }
      return next
    })
  }

  const handleStart = async () => {
    setSaving(true)
    try {
      // Install each selected module sequentially (deps are resolved server-side too)
      for (const id of selected) {
        await apiFetch(`/api/modules/${id}/install`, { method: "POST" })
      }
      const user = getCurrentUser()
      if (user) localStorage.setItem(`eb.onboarded.${user.email}`, "1")
      setStep("done")
      setTimeout(() => router.replace("/dashboard"), 1200)
    } catch {
      setSaving(false)
    }
  }

  const handleSkip = () => {
    const user = getCurrentUser()
    if (user) localStorage.setItem(`eb.onboarded.${user.email}`, "1")
    router.replace("/dashboard")
  }

  const optionalModules = modules.filter(m => !m.always)
  const categories = [...new Set(
    modules.filter(m => !m.always).map(m => (
      m.id === "inventory" || m.id === "production" ? "Operations"
      : m.id === "hrm" ? "HR"
      : "Industry"
    ))
  )]

  const getCategoryModules = (cat: string) =>
    optionalModules.filter(m => {
      if (cat === "Operations") return m.id === "inventory" || m.id === "production"
      if (cat === "HR") return m.id === "hrm"
      return m.id === "telecom" || m.id === "pra"
    })

  if (step === "done") {
    return (
      <div className="min-h-screen bg-[#f6f3ee] flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-16 h-16 bg-[#b8943f] rounded-full flex items-center justify-center mx-auto">
            <Check className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-bold text-[#1a1814]">You&apos;re all set!</h2>
          <p className="text-sm text-[#1a1814]/60">Taking you to your dashboard…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#f6f3ee] flex flex-col">
      {/* Header */}
      <header className="flex items-center gap-3 px-6 py-4 border-b border-[#1a1814]/8 bg-white/60 backdrop-blur-sm">
        <div className="w-8 h-8 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-sm">
          E
        </div>
        <span className="font-serif font-semibold text-[#1a1814]">Easy-Books</span>
      </header>

      {/* Body */}
      <div className="flex-1 flex flex-col items-center justify-center py-12 px-4">
        <div className="w-full max-w-2xl space-y-8">

          {/* Hero text */}
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold font-serif text-[#1a1814]">
              Welcome to Easy-Books
            </h1>
            <p className="text-[#1a1814]/60 text-base">
              Choose the modules you need. You can always add or remove them later from the Apps page.
            </p>
          </div>

          {/* Base module — always included */}
          <div className="bg-[#b8943f]/10 border border-[#b8943f]/30 rounded-xl px-5 py-4 flex items-center gap-4">
            <div className="w-10 h-10 bg-[#b8943f] rounded-lg flex items-center justify-center flex-shrink-0">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1">
              <p className="font-semibold text-[#1a1814] text-sm">Base Accounting</p>
              <p className="text-xs text-[#1a1814]/55">GL, Chart of Accounts, invoicing, AR/AP, banking & all financial reports. Always active.</p>
            </div>
            <div className="flex-shrink-0 w-6 h-6 bg-[#b8943f] rounded-full flex items-center justify-center">
              <Check className="w-3.5 h-3.5 text-white" />
            </div>
          </div>

          {/* Optional modules by category */}
          {modules.length > 0 && (["Operations", "HR", "Industry"] as const).map(cat => {
            const mods = getCategoryModules(cat)
            if (mods.length === 0) return null
            return (
              <div key={cat} className="space-y-3">
                <h2 className="text-xs font-bold uppercase tracking-widest text-[#1a1814]/40">
                  {CATEGORY_LABELS[cat] ?? cat}
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {mods.map(mod => {
                    const Icon = ICON_MAP[mod.icon] ?? Package
                    const isSelected = selected.has(mod.id)
                    const depsMissing = mod.deps.filter(d => d !== "base" && !selected.has(d))
                    return (
                      <button
                        key={mod.id}
                        onClick={() => toggle(mod.id)}
                        className={`text-left rounded-xl border p-4 flex items-start gap-3 transition-all ${
                          isSelected
                            ? "bg-white border-[#b8943f] shadow-sm shadow-[#b8943f]/20"
                            : "bg-white border-[#1a1814]/10 hover:border-[#b8943f]/50"
                        }`}
                      >
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${
                          isSelected ? "bg-[#b8943f] text-white" : "bg-[#1a1814]/6 text-[#1a1814]/50"
                        }`}>
                          <Icon className="w-4.5 h-4.5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-[#1a1814] text-sm">{mod.label}</span>
                            {depsMissing.length > 0 && (
                              <span className="text-[10px] text-amber-600 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">
                                needs {depsMissing.join(", ")}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-[#1a1814]/50 mt-0.5 line-clamp-2">{mod.description}</p>
                        </div>
                        <div className={`w-5 h-5 rounded-full border-2 flex-shrink-0 mt-0.5 flex items-center justify-center transition-colors ${
                          isSelected ? "bg-[#b8943f] border-[#b8943f]" : "border-[#1a1814]/20"
                        }`}>
                          {isSelected && <Check className="w-3 h-3 text-white" />}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            )
          })}

          {/* Actions */}
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={handleSkip}
              disabled={saving}
              className="text-sm text-[#1a1814]/40 hover:text-[#1a1814]/70 transition-colors"
            >
              Skip for now
            </button>
            <button
              onClick={handleStart}
              disabled={saving}
              className="flex items-center gap-2 bg-[#b8943f] hover:bg-[#a07832] text-white font-semibold text-sm px-6 py-2.5 rounded-lg transition-colors disabled:opacity-60"
            >
              {saving
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Setting up…</>
                : <>{selected.size > 0 ? `Install ${selected.size} module${selected.size > 1 ? "s" : ""} & ` : ""}Get Started <ArrowRight className="w-4 h-4" /></>
              }
            </button>
          </div>

        </div>
      </div>
    </div>
  )
}
