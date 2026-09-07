"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import {
  BookOpen, ChevronRight, Images, Search, Tag, Building2, Layers,
  GitBranch, BarChart2, Monitor, X, ExternalLink, ListOrdered,
} from "lucide-react"
import { useModules } from "@/context/ModuleContext"
import {
  CATALOG_KINDS,
  DEMO_TENANTS,
  allCatalogTags,
  catalogScreenshot,
  filterCatalog,
  type CatalogEntry,
  type CatalogKind,
  type DemoTenantKey,
} from "@/lib/workflowCatalog"

const KIND_ICON: Record<CatalogKind, typeof Images> = {
  tenant: Building2,
  segment: Layers,
  workflow: GitBranch,
  report: BarChart2,
  screen: Monitor,
}

const KIND_TONE: Record<CatalogKind, string> = {
  tenant: "bg-slate-800 text-white",
  segment: "bg-indigo-100 text-indigo-800",
  workflow: "bg-[var(--primary)]/15 text-[#7a5c1e]",
  report: "bg-emerald-100 text-emerald-800",
  screen: "bg-sky-100 text-sky-800",
}

function Snapshot({ entry, className }: { entry: CatalogEntry; className?: string }) {
  const [ok, setOk] = useState(true)
  return ok ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={catalogScreenshot(entry)}
      alt={entry.title}
      className={className}
      onError={() => setOk(false)}
    />
  ) : (
    <div className={`flex flex-col items-center justify-center gap-2 bg-[var(--bg-page)] text-[var(--text-primary)]/40 ${className ?? ""}`}>
      <Images className="w-8 h-8" />
      <span className="text-[10px] uppercase tracking-widest font-semibold">Snapshot pending</span>
    </div>
  )
}

export default function CatalogPage() {
  const { installedModules } = useModules()
  const [kind, setKind] = useState<CatalogKind | "all">("all")
  const [tag, setTag] = useState<string | null>(null)
  const [tenant, setTenant] = useState<DemoTenantKey | "all">("all")
  const [q, setQ] = useState("")
  const [active, setActive] = useState<CatalogEntry | null>(null)
  const [lightbox, setLightbox] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const k = params.get("kind") as CatalogKind | "all" | null
    if (k && CATALOG_KINDS.some(x => x.id === k)) setKind(k)
    if (params.get("tag")) setTag(params.get("tag"))
    const t = params.get("tenant") as DemoTenantKey | "all" | null
    if (t && (t === "all" || t in DEMO_TENANTS)) setTenant(t)
    if (params.get("q")) setQ(params.get("q") ?? "")
    const id = params.get("id")
    if (id) {
      const hit = filterCatalog({}).find(e => e.id === id)
      if (hit) setActive(hit)
    }
  }, [])

  const tags = useMemo(() => allCatalogTags(), [])
  const items = useMemo(
    () => filterCatalog({ kind, tag, tenant, q }),
    [kind, tag, tenant, q],
  )

  const counts = useMemo(() => {
    const all = filterCatalog({ tag, tenant, q })
    const c: Record<string, number> = { all: all.length }
    for (const k of CATALOG_KINDS) {
      if (k.id === "all") continue
      c[k.id] = all.filter(e => e.kind === k.id).length
    }
    return c
  }, [tag, tenant, q])

  const onSelect = useCallback((e: CatalogEntry) => {
    setActive(e)
    setLightbox(false)
    const url = new URL(window.location.href)
    url.searchParams.set("id", e.id)
    window.history.replaceState({}, "", url)
  }, [])

  const installed = (e: CatalogEntry) =>
    e.modules.every(m => m === "base" || installedModules.has(m))

  return (
    <div className="space-y-5 p-4 sm:p-6 max-w-7xl">
      <nav className="flex items-center gap-1.5 text-xs text-[var(--text-primary)]/50">
        <Link href="/settings" className="hover:text-[var(--primary)]">Settings</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-[var(--text-primary)]/80 font-medium">Catalog</span>
      </nav>

      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-[var(--text-primary)] flex items-center justify-center flex-shrink-0">
          <BookOpen className="w-5 h-5 text-[#ffd966]" />
        </div>
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold text-[var(--text-primary)]">Workflow catalog</h1>
          <p className="text-xs text-[var(--text-primary)]/55 mt-0.5 leading-relaxed">
            Snapshots and explanations for every demo tenant, nav segment, end-to-end workflow, report, and screen.
            Filter by tag or company; open a card to read how it posts to the GL.
          </p>
        </div>
      </div>

      <div className="relative">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-primary)]/40" />
        <input
          type="search"
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="Search invoices, spinning lots, ZATCA, trial balance…"
          className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-[var(--border)] bg-white text-sm text-[var(--text-primary)] placeholder:text-[var(--text-primary)]/35 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
        />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {CATALOG_KINDS.map(k => (
          <button
            key={k.id}
            type="button"
            data-kind={k.id}
            onClick={() => setKind(k.id)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
              kind === k.id
                ? "bg-[var(--text-primary)] text-white border-[var(--text-primary)]"
                : "bg-white text-[var(--text-primary)]/70 border-[var(--border)] hover:border-[var(--primary)]"
            }`}
          >
            {k.label}
            <span className="ml-1.5 opacity-60">{counts[k.id] ?? 0}</span>
          </button>
        ))}
      </div>

      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/45 mb-2 flex items-center gap-1.5">
          <Building2 className="w-3 h-3" /> Demo tenants
        </p>
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setTenant("all")}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-medium border ${
              tenant === "all" ? "bg-[var(--primary)] text-white border-[var(--primary)]" : "bg-white border-[var(--border)] text-[var(--text-primary)]/70"
            }`}
          >
            All companies
          </button>
          {(Object.keys(DEMO_TENANTS) as DemoTenantKey[]).map(key => (
            <button
              key={key}
              type="button"
              onClick={() => setTenant(tenant === key ? "all" : key)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-medium border ${
                tenant === key ? "bg-[var(--primary)] text-white border-[var(--primary)]" : "bg-white border-[var(--border)] text-[var(--text-primary)]/70"
              }`}
            >
              {DEMO_TENANTS[key].label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/45 mb-2 flex items-center gap-1.5">
          <Tag className="w-3 h-3" /> Tags
        </p>
        <div className="flex flex-wrap gap-1.5">
          {tags.map(({ tag: t, count }) => (
            <button
              key={t}
              type="button"
              onClick={() => setTag(tag === t ? null : t)}
              className={`px-2 py-0.5 rounded-full text-[11px] border ${
                tag === t
                  ? "bg-[#7a5c1e] text-white border-[#7a5c1e]"
                  : "bg-[var(--bg-page)] text-[var(--text-primary)]/70 border-[var(--border)] hover:border-[var(--primary)]"
              }`}
            >
              {t}
              <span className="ml-1 opacity-50">{count}</span>
            </button>
          ))}
        </div>
      </div>

      <p className="text-xs text-[var(--text-primary)]/50">
        {items.length} {items.length === 1 ? "entry" : "entries"}
        {tag ? ` tagged “${tag}”` : ""}
        {tenant !== "all" ? ` · ${DEMO_TENANTS[tenant].label}` : ""}
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {items.map(e => {
          const Icon = KIND_ICON[e.kind]
          return (
            <button
              key={e.id}
              type="button"
              onClick={() => onSelect(e)}
              className={`text-left bg-white border rounded-2xl overflow-hidden shadow-sm hover:border-[var(--primary)] hover:shadow-md transition-all ${
                active?.id === e.id ? "border-[var(--primary)] ring-2 ring-[var(--primary)]/30" : "border-[var(--border)]"
              }`}
            >
              <div className="aspect-[16/9] bg-[var(--bg-page)] overflow-hidden border-b border-[var(--border)]">
                <Snapshot entry={e} className="w-full h-full object-cover object-top" />
              </div>
              <div className="p-3 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="text-sm font-bold text-[var(--text-primary)] leading-snug">{e.title}</h2>
                  <span className={`shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide ${KIND_TONE[e.kind]}`}>
                    <Icon className="w-3 h-3" />
                    {e.kind}
                  </span>
                </div>
                <p className="text-[11px] text-[var(--text-primary)]/60 leading-relaxed line-clamp-2">{e.explanation}</p>
                <div className="flex flex-wrap gap-1">
                  {e.tags.slice(0, 4).map(t => (
                    <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-page)] text-[var(--text-primary)]/55">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {items.length === 0 && (
        <div className="text-center py-16 text-sm text-[var(--text-primary)]/50">
          No catalog entries match those filters.
        </div>
      )}

      {active && (
        <div className="fixed inset-0 z-[80] flex justify-end">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="Close" onClick={() => { setActive(null); setLightbox(false) }} />
          <aside className="relative w-full max-w-xl h-full bg-white shadow-2xl overflow-y-auto">
            <div className="sticky top-0 z-10 bg-white border-b border-[var(--border)] px-5 py-3 flex items-center justify-between">
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--primary)]">{active.kind} · {active.segment}</p>
                <h2 className="text-base font-bold text-[var(--text-primary)] truncate">{active.title}</h2>
              </div>
              <button type="button" onClick={() => setActive(null)} className="p-1.5 rounded-lg hover:bg-[var(--bg-page)]">
                <X className="w-4 h-4" />
              </button>
            </div>

            <button type="button" onClick={() => setLightbox(true)} className="block w-full aspect-[16/10] bg-[var(--bg-page)] border-b border-[var(--border)]">
              <Snapshot entry={active} className="w-full h-full object-cover object-top" />
            </button>

            <div className="p-5 space-y-4">
              <p className="text-sm text-[var(--text-primary)]/80 leading-relaxed">{active.explanation}</p>

              {active.steps && active.steps.length > 0 && (
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--primary)] mb-2 flex items-center gap-1.5">
                    <ListOrdered className="w-3 h-3" /> How it works
                  </p>
                  <ol className="space-y-2">
                    {active.steps.map((step, i) => (
                      <li key={i} className="flex gap-3 text-sm text-[var(--text-primary)]/80 leading-relaxed">
                        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[var(--primary)] text-white text-[10px] font-bold flex items-center justify-center mt-0.5">
                          {i + 1}
                        </span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {active.gl && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-page)] px-4 py-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a5c1e] mb-1">GL posting</p>
                  <p className="font-mono text-xs text-[var(--text-primary)]/80 leading-relaxed">{active.gl}</p>
                </div>
              )}

              <div className="flex flex-wrap gap-1.5">
                {active.tags.map(t => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => { setTag(t); setKind("all") }}
                    className="text-[11px] px-2 py-0.5 rounded-full bg-[var(--bg-page)] border border-[var(--border)] text-[var(--text-primary)]/70 hover:border-[var(--primary)]"
                  >
                    {t}
                  </button>
                ))}
              </div>

              <div className="text-[11px] text-[var(--text-primary)]/50 space-y-1">
                <p>Shown on: {active.tenants.map(t => DEMO_TENANTS[t].label).join(", ")}</p>
                <p>Modules: {active.modules.join(", ")}</p>
                {!installed(active) && (
                  <p className="text-amber-700">This tenant does not have the required module installed — open Add-ons to enable it, or switch to a demo company that includes it.</p>
                )}
              </div>

              {active.captureTenant !== "anon" && (
                <p className="text-[11px] text-[var(--text-primary)]/45">
                  Snapshot captured as {DEMO_TENANTS[active.captureTenant].email}
                </p>
              )}

              <div className="flex flex-wrap gap-2 pt-2">
                <Link
                  href={active.href}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--primary)] text-white text-sm font-medium hover:bg-[var(--primary-dark)]"
                >
                  Open live screen <ExternalLink className="w-3.5 h-3.5" />
                </Link>
                <Link
                  href="/workflow"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[var(--bg-page)]"
                >
                  GL flowcharts
                </Link>
                <Link
                  href="/guide"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[var(--border)] text-sm font-medium hover:bg-[var(--bg-page)]"
                >
                  User guide
                </Link>
              </div>
            </div>
          </aside>
        </div>
      )}

      {lightbox && active && (
        <div className="fixed inset-0 z-[90] bg-black/80 flex items-center justify-center p-4" onClick={() => setLightbox(false)}>
          <Snapshot entry={active} className="max-w-full max-h-full object-contain rounded-lg shadow-2xl" />
        </div>
      )}
    </div>
  )
}
