"use client"

import { useCallback, useEffect, useMemo, useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  BookOpen, Package, Factory, Users, Radio, FileCheck, CheckCircle2, Lock,
  AlertTriangle, Stethoscope, Sparkles, Scissors, ShoppingCart, Layers,
} from "lucide-react"
import { useModules, type ModuleInfo } from "@/context/ModuleContext"
import { ADDON_PACKS, HOME_PREF_KEY } from "@/lib/addonPacks"
import { getCurrentUser } from "@/lib/auth"

const ICON_MAP: Record<string, React.ElementType> = {
  BookOpen, Package, Factory, Users, Radio, FileCheck, Stethoscope, Sparkles, Scissors, ShoppingCart,
}

const CATEGORY_ORDER = ["Core", "Accounting", "Operations", "HR", "Industry", "Intelligence"]

function categoryGroups(modules: ModuleInfo[]): [string, ModuleInfo[]][] {
  const map = new Map<string, ModuleInfo[]>()
  for (const m of modules) {
    if (!map.has(m.category)) map.set(m.category, [])
    map.get(m.category)!.push(m)
  }
  return CATEGORY_ORDER.filter(c => map.has(c)).map(c => [c, map.get(c)!])
}

function ModuleCard({ mod, onInstall, onUninstall, busy }: {
  mod: ModuleInfo
  onInstall: (id: string) => void
  onUninstall: (id: string) => void
  busy: boolean
}) {
  const Icon = ICON_MAP[mod.icon] ?? Package

  return (
    <div className={`bg-white rounded-xl border p-5 flex flex-col gap-3 shadow-sm transition-shadow hover:shadow-md ${mod.installed ? "border-[var(--primary)]/40" : "border-gray-200"}`}>
      <div className="flex items-start gap-3">
        <div className={`rounded-lg p-2.5 flex-shrink-0 ${mod.installed ? "bg-[var(--primary)]/10 text-[var(--primary)]" : "bg-gray-100 text-gray-500"}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-[var(--text-primary)] text-sm">{mod.label}</h3>
            {mod.always && <span title="Required — cannot be uninstalled"><Lock className="w-3.5 h-3.5 text-gray-400" /></span>}
            {mod.installed && !mod.always && <CheckCircle2 className="w-3.5 h-3.5 text-[var(--primary)]" />}
          </div>
          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{mod.description}</p>
        </div>
      </div>

      {mod.deps.length > 0 && (
        <p className="text-[11px] text-gray-400">
          Requires: <span className="font-medium">{mod.deps.join(", ")}</span>
        </p>
      )}

      <div className="mt-auto">
        {mod.always ? (
          <span className="inline-block text-xs bg-gray-100 text-gray-500 rounded px-2.5 py-1 font-medium">Always Active</span>
        ) : mod.installed ? (
          <button
            onClick={() => onUninstall(mod.id)}
            disabled={busy}
            className="text-xs border border-red-200 text-red-600 rounded px-3 py-1.5 hover:bg-red-50 transition-colors disabled:opacity-50 font-medium"
          >
            {busy ? "Working…" : "Uninstall"}
          </button>
        ) : (
          <button
            onClick={() => onInstall(mod.id)}
            disabled={busy}
            className="text-xs bg-[var(--primary)] text-white rounded px-3 py-1.5 hover:bg-[#a07832] transition-colors disabled:opacity-50 font-medium"
          >
            {busy ? "Installing…" : "Install"}
          </button>
        )}
      </div>
    </div>
  )
}

function AppsPageInner() {
  const { modules, installedModules, install, uninstall } = useModules()
  const router = useRouter()
  const search = useSearchParams()
  const welcome = search.get("welcome") === "1"

  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [praPrompt, setPraPrompt] = useState(false)
  // Demo tenants default to including sample rows; real signups opt in.
  const [seedSample, setSeedSample] = useState(() => {
    const email = getCurrentUser()?.email ?? ""
    return email.startsWith("demo.")
  })

  const handleInstall = useCallback(async (id: string) => {
    setBusyId(id); setError(null); setSuccess(null)
    try {
      await install(id, { seedSample })
      const mod = modules.find(m => m.id === id)
      setSuccess(`${mod?.label ?? id} installed successfully.`)
      if (id === "pra") setPraPrompt(true)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg || "Install failed. Check console for details.")
    } finally {
      setBusyId(null)
    }
  }, [install, modules, seedSample])

  const handlePack = async (packId: string) => {
    const pack = ADDON_PACKS.find(p => p.id === packId)
    if (!pack) return
    setBusyId(packId); setError(null); setSuccess(null)
    try {
      for (const mid of pack.modules) {
        if (!installedModules.has(mid)) await install(mid, { seedSample })
      }
      setSuccess(`${pack.label} pack installed.`)
      if (pack.modules.includes("pra")) setPraPrompt(true)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg || "Pack install failed.")
    } finally {
      setBusyId(null)
    }
  }

  const handleUninstall = async (id: string) => {
    const mod = modules.find(m => m.id === id)
    if (!window.confirm(`Uninstall "${mod?.label ?? id}"?\n\nThe sidebar will update immediately. Your data is not deleted.`)) return
    setBusyId(id); setError(null); setSuccess(null)
    try {
      await uninstall(id)
      if (id === "pra") {
        localStorage.setItem(HOME_PREF_KEY, "accounting")
        localStorage.setItem("eb.pra_portal_mode", "0")
      }
      setSuccess(`${mod?.label ?? id} uninstalled.`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg || "Uninstall failed. Check if other modules depend on this one.")
    } finally {
      setBusyId(null)
    }
  }

  const choosePraHome = (usePra: boolean) => {
    localStorage.setItem(HOME_PREF_KEY, usePra ? "pra" : "accounting")
    localStorage.setItem("eb.pra_portal_mode", usePra ? "1" : "0")
    setPraPrompt(false)
    router.push(usePra ? "/pra-dashboard" : "/dashboard")
  }

  const groups = categoryGroups(modules)
  const installedCount = modules.filter(m => m.installed).length

  const packsWithStatus = useMemo(() => ADDON_PACKS.map(p => ({
    ...p,
    fullyInstalled: p.modules.every(m => installedModules.has(m)),
  })), [installedModules])

  return (
    <div className="max-w-5xl mx-auto space-y-8 p-4 md:p-0">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Add-ons</h1>
        <p className="text-sm text-gray-500 mt-1">
          {installedCount} of {modules.length} modules installed.
          Start with Base Accounting, then install what your business needs.
        </p>
      </div>

      {welcome && (
        <div className="rounded-xl border border-[var(--primary)]/30 bg-[var(--primary)]/5 px-4 py-3 text-sm text-[var(--text-primary)]">
          Welcome! Your company starts with <strong>Base Accounting</strong>.
          Pick a recommended pack below, or install individual modules.
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]/70 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={seedSample}
          onChange={e => setSeedSample(e.target.checked)}
          className="rounded border-gray-300 text-[var(--primary)] focus:ring-[var(--primary)]"
        />
        Include sample data when installing
        <span className="text-xs text-gray-400">(demo tenants on by default)</span>
      </label>

      {praPrompt && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 space-y-3">
          <p className="text-sm font-semibold text-amber-900">Use PRA Sales Dashboard as your home?</p>
          <p className="text-xs text-amber-800/80">
            The retail counter view shows today&apos;s invoices and PRA submission status.
            You can switch back to the full Accounting dashboard anytime.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => choosePraHome(true)}
              className="text-xs bg-[var(--primary)] text-white rounded-lg px-3 py-2 font-medium"
            >
              Yes — PRA Sales home
            </button>
            <button
              type="button"
              onClick={() => choosePraHome(false)}
              className="text-xs border border-amber-300 text-amber-900 rounded-lg px-3 py-2 font-medium bg-white"
            >
              Keep Accounting home
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          {success}
        </div>
      )}

      <section>
        <div className="flex items-center gap-2 mb-3">
          <Layers className="w-4 h-4 text-[var(--primary)]" />
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest">Recommended packs</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {packsWithStatus.map(pack => (
            <div
              key={pack.id}
              className={`bg-white rounded-xl border p-5 flex flex-col gap-3 shadow-sm ${
                pack.fullyInstalled ? "border-[var(--primary)]/40" : "border-gray-200"
              }`}
            >
              <div>
                <h3 className="font-semibold text-sm text-[var(--text-primary)]">{pack.label}</h3>
                <p className="text-[11px] text-gray-400 mt-0.5">{pack.tagline}</p>
              </div>
              <ul className="text-xs text-gray-500 space-y-1 flex-1">
                {pack.features.map(f => (
                  <li key={f} className="flex gap-1.5">
                    <span className="text-[var(--primary)]">·</span> {f}
                  </li>
                ))}
              </ul>
              <p className="text-[10px] text-gray-400">
                Modules: {pack.modules.join(", ")}
              </p>
              {pack.fullyInstalled ? (
                <span className="inline-flex items-center gap-1 text-xs text-[var(--primary)] font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Installed
                </span>
              ) : (
                <button
                  type="button"
                  disabled={busyId !== null}
                  onClick={() => handlePack(pack.id)}
                  className="text-xs bg-[var(--primary)] text-white rounded px-3 py-1.5 hover:bg-[#a07832] transition-colors disabled:opacity-50 font-medium self-start"
                >
                  {busyId === pack.id ? "Installing…" : "Install pack"}
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      {groups.map(([category, mods]) => (
        <section key={category}>
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">{category}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {mods.map(mod => (
              <ModuleCard
                key={mod.id}
                mod={mod}
                onInstall={handleInstall}
                onUninstall={handleUninstall}
                busy={busyId === mod.id}
              />
            ))}
          </div>
        </section>
      ))}

      {modules.length === 0 && (
        <div className="text-center py-16 text-gray-400">Loading modules…</div>
      )}
    </div>
  )
}

export default function AppsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-gray-400">Loading Add-ons…</div>}>
      <AppsPageInner />
    </Suspense>
  )
}
