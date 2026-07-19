"use client"
import { useState } from "react"
import { BookOpen, Package, Factory, Users, Radio, FileCheck, CheckCircle2, Lock, AlertTriangle, Stethoscope, Sparkles, Scissors, ShoppingCart } from "lucide-react"
import { useModules, type ModuleInfo } from "@/context/ModuleContext"

const ICON_MAP: Record<string, React.ElementType> = {
  BookOpen, Package, Factory, Users, Radio, FileCheck, Stethoscope, Sparkles, Scissors, ShoppingCart,
}

// Every backend MODULE_REGISTRY category (db.py) must be listed here or its
// modules are silently dropped from the page — they still count toward the
// "N of 9 installed" header and are still installable via the raw API, but
// have no card and no Install button anywhere in the UI. ai_assistant's
// "Intelligence" category was missing here for that exact reason.
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

export default function AppsPage() {
  const { modules, install, uninstall } = useModules()
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const handleInstall = async (id: string) => {
    setBusyId(id); setError(null); setSuccess(null)
    try {
      await install(id)
      const mod = modules.find(m => m.id === id)
      setSuccess(`${mod?.label ?? id} installed successfully.`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg || "Install failed. Check console for details.")
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
      setSuccess(`${mod?.label ?? id} uninstalled.`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg || "Uninstall failed. Check if other modules depend on this one.")
    } finally {
      setBusyId(null)
    }
  }

  const groups = categoryGroups(modules)
  const installedCount = modules.filter(m => m.installed).length

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Add-ons</h1>
        <p className="text-sm text-gray-500 mt-1">
          {installedCount} of {modules.length} modules installed.
          Install add-ons to unlock additional sections in your sidebar.
        </p>
      </div>

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
