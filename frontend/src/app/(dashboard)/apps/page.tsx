"use client"

import { useCallback, useEffect, useMemo, useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  BookOpen, Package, Factory, Users, Radio, FileCheck, CheckCircle2, Lock,
  AlertTriangle, Stethoscope, Sparkles, Scissors, ShoppingCart, LayoutGrid,
  List, Layers,
} from "lucide-react"
import { useModules, type ModuleInfo } from "@/context/ModuleContext"
import { ADDON_PACKS, HOME_PREF_KEY, type AddonPack } from "@/lib/addonPacks"
import { getCurrentUser } from "@/lib/auth"

const ICON_MAP: Record<string, React.ElementType> = {
  BookOpen, Package, Factory, Users, Radio, FileCheck, Stethoscope, Sparkles, Scissors, ShoppingCart,
}

type ViewMode = "tabs" | "list"
type Bucket = "default" | "recommended" | "optional"

const VIEW_KEY = "eb.addons.view"
const BUCKET_TABS: { id: Bucket; label: string; hint: string }[] = [
  { id: "default", label: "Default", hint: "Always on — core accounting" },
  { id: "recommended", label: "Recommended", hint: "Industry packs for a quick start" },
  { id: "optional", label: "Optional", hint: "Install modules one at a time" },
]

function readView(): ViewMode {
  if (typeof window === "undefined") return "tabs"
  return localStorage.getItem(VIEW_KEY) === "list" ? "list" : "tabs"
}

function ModuleIcon({ name, installed }: { name: string; installed?: boolean }) {
  const Icon = ICON_MAP[name] ?? Package
  return (
    <div className={`rounded-lg p-2 flex-shrink-0 ${
      installed ? "bg-[var(--primary)]/10 text-[var(--primary)]" : "bg-[var(--border)]/40 text-[var(--text-muted)]"
    }`}>
      <Icon className="w-4 h-4" />
    </div>
  )
}

function StatusPill({ mod }: { mod: ModuleInfo }) {
  if (mod.always) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-[var(--text-muted)] bg-[var(--border)]/40 rounded px-2 py-0.5 font-medium">
        <Lock className="w-3 h-3" /> Always on
      </span>
    )
  }
  if (mod.installed) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-[var(--primary)] font-medium">
        <CheckCircle2 className="w-3.5 h-3.5" /> Installed
      </span>
    )
  }
  return null
}

function InstallControls({
  mod, busy, onInstall, onUninstall,
}: {
  mod: ModuleInfo
  busy: boolean
  onInstall: (id: string) => void
  onUninstall: (id: string) => void
}) {
  if (mod.always) return <StatusPill mod={mod} />
  if (mod.installed) {
    return (
      <div className="flex items-center gap-2">
        <StatusPill mod={mod} />
        <button
          type="button"
          onClick={() => onUninstall(mod.id)}
          disabled={busy}
          className="text-[11px] border border-red-200 text-red-600 rounded-md px-2.5 py-1 hover:bg-red-50 transition-colors disabled:opacity-50 font-medium"
        >
          {busy ? "…" : "Uninstall"}
        </button>
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={() => onInstall(mod.id)}
      disabled={busy}
      className="text-[11px] bg-[var(--primary)] text-white rounded-md px-3 py-1.5 hover:opacity-90 transition-opacity disabled:opacity-50 font-medium"
    >
      {busy ? "Installing…" : "Install"}
    </button>
  )
}

/** Compact tile for tabs grid / list rows. */
function ModuleTile({
  mod, busy, onInstall, onUninstall, detail,
}: {
  mod: ModuleInfo
  busy: boolean
  onInstall: (id: string) => void
  onUninstall: (id: string) => void
  detail?: boolean
}) {
  return (
    <div className={`flex gap-3 rounded-xl border bg-[var(--bg-card)] p-3.5 transition-colors ${
      mod.installed ? "border-[var(--primary)]/35" : "border-[var(--border)]"
    } ${detail ? "items-start" : "items-center"}`}>
      <ModuleIcon name={mod.icon} installed={mod.installed || mod.always} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="font-semibold text-sm text-[var(--text-primary)]">{mod.label}</h3>
          {mod.tier === "pro" && (
            <span className="text-[10px] uppercase tracking-wide text-[var(--primary)] font-semibold">Pro</span>
          )}
        </div>
        <p className={`text-xs text-[var(--text-muted)] mt-0.5 ${detail ? "" : "line-clamp-1"}`}>
          {mod.description}
        </p>
        {detail && mod.deps.length > 0 && (
          <p className="text-[11px] text-[var(--text-muted)] mt-1.5">
            Requires <span className="font-medium text-[var(--text-primary)]">{mod.deps.join(", ")}</span>
          </p>
        )}
        {detail && mod.nav_sections.length > 0 && (
          <p className="text-[11px] text-[var(--text-muted)] mt-1">
            Nav: {mod.nav_sections.join(" · ")}
          </p>
        )}
      </div>
      <div className="flex-shrink-0 self-center">
        <InstallControls mod={mod} busy={busy} onInstall={onInstall} onUninstall={onUninstall} />
      </div>
    </div>
  )
}

function PackTile({
  pack, busy, onInstall, detail,
}: {
  pack: AddonPack & { fullyInstalled: boolean }
  busy: boolean
  onInstall: (id: string) => void
  detail?: boolean
}) {
  return (
    <div className={`flex gap-3 rounded-xl border bg-[var(--bg-card)] p-3.5 ${
      pack.fullyInstalled ? "border-[var(--primary)]/35" : "border-[var(--border)]"
    } ${detail ? "items-start" : "items-center"}`}>
      <div className={`rounded-lg p-2 flex-shrink-0 ${
        pack.fullyInstalled ? "bg-[var(--primary)]/10 text-[var(--primary)]" : "bg-[var(--border)]/40 text-[var(--text-muted)]"
      }`}>
        <Layers className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <h3 className="font-semibold text-sm text-[var(--text-primary)]">{pack.label}</h3>
          <span className="text-[11px] text-[var(--text-muted)]">{pack.tagline}</span>
        </div>
        {detail ? (
          <ul className="mt-1.5 space-y-0.5">
            {pack.features.map(f => (
              <li key={f} className="text-xs text-[var(--text-muted)] flex gap-1.5">
                <span className="text-[var(--primary)]">·</span> {f}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-[var(--text-muted)] mt-0.5 line-clamp-1">
            {pack.features.join(" · ")}
          </p>
        )}
        <p className="text-[10px] text-[var(--text-muted)] mt-1.5">
          Includes {pack.modules.join(", ")}
        </p>
      </div>
      <div className="flex-shrink-0 self-center">
        {pack.fullyInstalled ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-[var(--primary)] font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" /> Installed
          </span>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => onInstall(pack.id)}
            className="text-[11px] bg-[var(--primary)] text-white rounded-md px-3 py-1.5 hover:opacity-90 transition-opacity disabled:opacity-50 font-medium"
          >
            {busy ? "Installing…" : "Install pack"}
          </button>
        )}
      </div>
    </div>
  )
}

function BucketSection({
  title, hint, children, count,
}: {
  title: string
  hint: string
  count: number
  children: React.ReactNode
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">{hint}</p>
        </div>
        <span className="text-[11px] text-[var(--text-muted)] tabular-nums">{count}</span>
      </div>
      <div className="space-y-2">{children}</div>
    </section>
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
  const [view, setView] = useState<ViewMode>("tabs")
  const [bucket, setBucket] = useState<Bucket>("default")
  const [seedSample, setSeedSample] = useState(() => {
    const email = getCurrentUser()?.email ?? ""
    return email.startsWith("demo.")
  })

  useEffect(() => { setView(readView()) }, [])
  useEffect(() => {
    if (welcome) setBucket("recommended")
  }, [welcome])

  const setViewPersist = (mode: ViewMode) => {
    setView(mode)
    localStorage.setItem(VIEW_KEY, mode)
  }

  const defaultMods = useMemo(() => modules.filter(m => m.always), [modules])
  const optionalMods = useMemo(() => modules.filter(m => !m.always), [modules])

  const packsWithStatus = useMemo(() => ADDON_PACKS.map(p => ({
    ...p,
    fullyInstalled: p.modules.every(m => installedModules.has(m)),
  })), [installedModules])

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

  const installedCount = modules.filter(m => m.installed).length
  const detail = view === "list"

  const renderDefault = () => (
    <div className={view === "tabs" ? "grid grid-cols-1 gap-2" : "space-y-2"}>
      {defaultMods.map(mod => (
        <ModuleTile
          key={mod.id}
          mod={mod}
          busy={busyId === mod.id}
          onInstall={handleInstall}
          onUninstall={handleUninstall}
          detail={detail}
        />
      ))}
    </div>
  )

  const renderRecommended = () => (
    <div className={view === "tabs" ? "grid grid-cols-1 md:grid-cols-2 gap-2" : "space-y-2"}>
      {packsWithStatus.map(pack => (
        <PackTile
          key={pack.id}
          pack={pack}
          busy={busyId === pack.id || (busyId !== null && pack.modules.includes(busyId))}
          onInstall={handlePack}
          detail={detail}
        />
      ))}
    </div>
  )

  const renderOptional = () => (
    <div className={view === "tabs" ? "grid grid-cols-1 md:grid-cols-2 gap-2" : "space-y-2"}>
      {optionalMods.map(mod => (
        <ModuleTile
          key={mod.id}
          mod={mod}
          busy={busyId === mod.id}
          onInstall={handleInstall}
          onUninstall={handleUninstall}
          detail={detail}
        />
      ))}
    </div>
  )

  return (
    <div className="max-w-4xl mx-auto space-y-5 p-4 md:p-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Add-ons</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            {installedCount} of {modules.length} modules installed
          </p>
        </div>
        <div
          className="inline-flex rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-0.5"
          role="group"
          aria-label="View mode"
        >
          <button
            type="button"
            onClick={() => setViewPersist("tabs")}
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
              view === "tabs"
                ? "bg-[var(--primary)] text-white"
                : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}
          >
            <LayoutGrid className="w-3.5 h-3.5" /> Tabs
          </button>
          <button
            type="button"
            onClick={() => setViewPersist("list")}
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
              view === "list"
                ? "bg-[var(--primary)] text-white"
                : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}
          >
            <List className="w-3.5 h-3.5" /> List
          </button>
        </div>
      </div>

      {welcome && (
        <div className="rounded-xl border border-[var(--primary)]/30 bg-[var(--primary)]/5 px-4 py-3 text-sm text-[var(--text-primary)]">
          Welcome — you start with <strong>Base Accounting</strong>.
          Open <strong>Recommended</strong> for an industry pack, or <strong>Optional</strong> for individual modules.
        </div>
      )}

      <label className="flex items-center gap-2 text-xs text-[var(--text-muted)] cursor-pointer select-none">
        <input
          type="checkbox"
          checked={seedSample}
          onChange={e => setSeedSample(e.target.checked)}
          className="rounded border-gray-300 text-[var(--primary)] focus:ring-[var(--primary)]"
        />
        Include sample data when installing
      </label>

      {praPrompt && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 space-y-2">
          <p className="text-sm font-semibold text-amber-900">Use PRA Sales as home?</p>
          <p className="text-xs text-amber-800/80">
            Retail counter view with today&apos;s invoices and PRA status. Switch anytime.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => choosePraHome(true)}
              className="text-xs bg-[var(--primary)] text-white rounded-lg px-3 py-1.5 font-medium"
            >
              Yes — PRA home
            </button>
            <button
              type="button"
              onClick={() => choosePraHome(false)}
              className="text-xs border border-amber-300 text-amber-900 rounded-lg px-3 py-1.5 font-medium bg-white"
            >
              Keep Accounting home
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2.5">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          {success}
        </div>
      )}

      {modules.length === 0 ? (
        <div className="text-center py-16 text-[var(--text-muted)] text-sm">Loading modules…</div>
      ) : view === "tabs" ? (
        <>
          <div className="flex gap-1 border-b border-[var(--border)] overflow-x-auto">
            {BUCKET_TABS.map(tab => {
              const count =
                tab.id === "default" ? defaultMods.length
                : tab.id === "recommended" ? packsWithStatus.length
                : optionalMods.length
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setBucket(tab.id)}
                  className={`relative px-3.5 py-2.5 text-sm font-medium whitespace-nowrap transition-colors ${
                    bucket === tab.id
                      ? "text-[var(--primary)]"
                      : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {tab.label}
                  <span className={`ml-1.5 text-[11px] tabular-nums ${
                    bucket === tab.id ? "text-[var(--primary)]/70" : "text-[var(--text-muted)]/70"
                  }`}>{count}</span>
                  {bucket === tab.id && (
                    <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-[var(--primary)]" />
                  )}
                </button>
              )
            })}
          </div>
          <p className="text-xs text-[var(--text-muted)] -mt-2">
            {BUCKET_TABS.find(t => t.id === bucket)?.hint}
          </p>
          {bucket === "default" && renderDefault()}
          {bucket === "recommended" && renderRecommended()}
          {bucket === "optional" && renderOptional()}
        </>
      ) : (
        <div className="space-y-8">
          <BucketSection title="Default" hint="Always on — core accounting" count={defaultMods.length}>
            {renderDefault()}
          </BucketSection>
          <BucketSection title="Recommended" hint="Industry packs for a quick start" count={packsWithStatus.length}>
            {renderRecommended()}
          </BucketSection>
          <BucketSection title="Optional" hint="Install modules one at a time" count={optionalMods.length}>
            {renderOptional()}
          </BucketSection>
        </div>
      )}
    </div>
  )
}

export default function AppsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-[var(--text-muted)]">Loading Add-ons…</div>}>
      <AppsPageInner />
    </Suspense>
  )
}
