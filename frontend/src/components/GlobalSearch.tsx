"use client"

import { createPortal } from "react-dom"
import { useEffect, useRef, useState, useCallback, useMemo } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  Search, X, LayoutGrid, Users, Truck, FileSignature, Receipt,
  BookOpen, Package, UserCog, ClipboardList, Layers, Zap, BarChart2,
  Clock, ArrowRight, Banknote, FileMinus, FilePlus,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { searchNav, SEARCH_PREFIXES, type NavResult } from "@/lib/navIndex"
import { useTabs } from "@/context/TabContext"

// ── Types ─────────────────────────────────────────────────────────────────────

interface ApiRow {
  id:      number
  label:   string
  sub:     string
  href:    string
  date?:   string
  amount?: number
  status?: string
}

interface ApiResults {
  customers?:          ApiRow[]
  vendors?:            ApiRow[]
  invoices?:           ApiRow[]
  bills?:              ApiRow[]
  accounts?:           ApiRow[]
  products?:           ApiRow[]
  employees?:          ApiRow[]
  transactions?:       ApiRow[]
  payments_received?:  ApiRow[]
  bill_payments?:      ApiRow[]
  credit_notes?:       ApiRow[]
  debit_notes?:        ApiRow[]
}

interface SearchItem {
  id:      string
  label:   string
  sub:     string
  href:    string
  icon:    React.ElementType
  date?:   string
  amount?: number
  status?: string
  badge?:  string  // group type label for the pill
}

interface Group { key: string; label: string; icon: React.ElementType; items: SearchItem[] }

// ── Constants ─────────────────────────────────────────────────────────────────

const RECENT_KEY = "eb.recent-searches"
const MAX_RECENT = 5

const TYPE_META: Record<string, { label: string; icon: React.ElementType }> = {
  nav:                { label: "Pages",              icon: LayoutGrid    },
  action:             { label: "Forms & Inputs",     icon: Zap           },
  report:             { label: "Reports & Analysis", icon: BarChart2     },
  tabs:               { label: "Open Tabs",          icon: Layers        },
  customers:          { label: "Customers",          icon: Users         },
  vendors:            { label: "Vendors",            icon: Truck         },
  invoices:           { label: "Invoices",           icon: FileSignature },
  bills:              { label: "Bills",              icon: Receipt       },
  payments_received:  { label: "Payments Received",  icon: Banknote      },
  bill_payments:      { label: "Bill Payments",      icon: Banknote      },
  credit_notes:       { label: "Credit Notes",       icon: FileMinus     },
  debit_notes:        { label: "Debit Notes",        icon: FilePlus      },
  accounts:           { label: "Accounts",           icon: BookOpen      },
  products:           { label: "Products",           icon: Package       },
  employees:          { label: "Employees",          icon: UserCog       },
  transactions:       { label: "Transactions",       icon: ClipboardList },
}

/** Entity types searched when the query is an amount (`amt:` or a bare number). */
const AMOUNT_TYPES =
  "invoices,bills,transactions,payments_received,bill_payments,credit_notes,debit_notes"

const STATUS_COLORS: Record<string, string> = {
  draft:     "bg-amber-100  text-amber-700  dark:bg-amber-900/30  dark:text-amber-400",
  posted:    "bg-blue-100   text-blue-700   dark:bg-blue-900/30   dark:text-blue-400",
  paid:      "bg-green-100  text-green-700  dark:bg-green-900/30  dark:text-green-400",
  partial:   "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  voided:    "bg-red-100    text-red-700    dark:bg-red-900/30    dark:text-red-400",
  cancelled: "bg-red-100    text-red-700    dark:bg-red-900/30    dark:text-red-400",
  // Voucher types
  JV:  "bg-slate-100  text-slate-600",
  SL:  "bg-blue-100   text-blue-700",
  PU:  "bg-purple-100 text-purple-700",
  CR:  "bg-green-100  text-green-700",
  CP:  "bg-green-100  text-green-700",
  BR:  "bg-green-100  text-green-700",
  BP:  "bg-orange-100 text-orange-700",
  CN:  "bg-rose-100   text-rose-700",
  DN:  "bg-rose-100   text-rose-700",
}

// ── Quick-action chips shown in empty state ────────────────────────────────────

const EMPTY_CHIPS: Array<{ label: string; href: string }> = [
  { label: "New Invoice",    href: "/invoices/new"          },
  { label: "New Bill",       href: "/bills/new"             },
  { label: "New Customer",   href: "/customers/new"         },
  { label: "New Entry",      href: "/entry"                 },
  { label: "Trial Balance",  href: "/trial-balance"         },
  { label: "Report Builder", href: "/reports/builder"       },
  { label: "Gate Inward",    href: "/purchases/gate-inward/new" },
  { label: "AI Assistant",   href: "/agent"                 },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function getRecent(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]") } catch { return [] }
}

function addRecent(q: string) {
  if (!q || q.length < 2) return
  const prev = getRecent().filter(r => r !== q)
  localStorage.setItem(RECENT_KEY, JSON.stringify([q, ...prev].slice(0, MAX_RECENT)))
}

function parsePrefix(raw: string): { prefix: string | null; q: string } {
  const m = raw.match(/^([a-z]+):\s*(.*)$/i)
  if (m) {
    const key = m[1].toLowerCase()
    if (key in SEARCH_PREFIXES) return { prefix: key, q: m[2] }
  }
  return { prefix: null, q: raw }
}

// ── Highlight ─────────────────────────────────────────────────────────────────

function Highlight({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-[var(--primary)]/20 text-[var(--primary)] font-bold rounded-sm not-italic">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600"
  return (
    <span className={cn("shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide", cls)}>
      {status}
    </span>
  )
}

// ── Amount pill ───────────────────────────────────────────────────────────────

function AmountPill({ amount }: { amount: number }) {
  return (
    <span className="shrink-0 text-[11px] font-mono text-[var(--text-muted)] tabular-nums">
      {amount.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
    </span>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function GlobalSearch() {
  const router     = useRouter()
  const { tabs }   = useTabs()

  const [open,         setOpen]         = useState(false)
  const [mounted,      setMounted]      = useState(false)
  const [query,        setQuery]        = useState("")
  const [debouncedQ,   setDebouncedQ]   = useState("")
  const [apiResults,   setApiResults]   = useState<ApiResults | null>(null)
  const [loading,      setLoading]      = useState(false)
  const [focusedIndex, setFocusedIndex] = useState(0)
  const [recent,       setRecent]       = useState<string[]>([])

  const inputRef = useRef<HTMLInputElement>(null)

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  useEffect(() => { setMounted(true); setRecent(getRecent()) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); setOpen(o => !o) }
      if (e.key === "Escape") setOpen(false)
    }
    const onEvent = () => setOpen(true)
    window.addEventListener("keydown", onKey)
    window.addEventListener("search:open", onEvent)
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("search:open", onEvent) }
  }, [])

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 30)
      setQuery(""); setDebouncedQ(""); setApiResults(null); setFocusedIndex(0)
      setRecent(getRecent())
    }
  }, [open])

  // Debounce 150 ms
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(query), 150)
    return () => clearTimeout(t)
  }, [query])

  // API fetch — respects prefix-derived `types` param
  useEffect(() => {
    const { prefix, q: cleanQ } = parsePrefix(debouncedQ)
    const apiType = prefix ? SEARCH_PREFIXES[prefix] : null

    // Skip API for nav-only or tab-only prefixes
    const skipApi = apiType === "__nav__" || apiType === "__tabs__" ||
                    apiType === "__reports__" || apiType === "__actions__"

    if (cleanQ.length < 2 || skipApi) {
      setApiResults(null); setLoading(false); return
    }

    let cancelled = false
    setLoading(true)

    // Map prefix → `types` param (only real entity types / amount bundle)
    let entityTypes = ""
    if (apiType === "__amount__") entityTypes = AMOUNT_TYPES
    else if (apiType && !apiType.startsWith("__")) entityTypes = apiType

    apiFetch<ApiResults>(
      `/api/search?q=${encodeURIComponent(cleanQ)}&limit=8${entityTypes ? `&types=${entityTypes}` : ""}`
    )
      .then(data  => { if (!cancelled) { setApiResults(data); setLoading(false) } })
      .catch(()   => { if (!cancelled)   setLoading(false) })
    return () => { cancelled = true }
  }, [debouncedQ])

  // ── Build groups ───────────────────────────────────────────────────────────

  const groups = useMemo<Group[]>(() => {
    const { prefix, q: cleanQ } = parsePrefix(query)
    const apiType  = prefix ? SEARCH_PREFIXES[prefix] : null

    const showTabs    = !prefix || apiType === "__tabs__"
    const showNav     = !prefix || apiType === "__nav__" || apiType === "__reports__" || apiType === "__actions__"
    const showApi     = !prefix || (apiType && !apiType.startsWith("__")) || apiType === "__amount__"

    const result: Group[] = []

    // 1. Open tabs (match by title or href)
    if (showTabs && cleanQ.length >= 1) {
      const lc = cleanQ.toLowerCase()
      const matchedTabs = tabs.filter(t =>
        t.title.toLowerCase().includes(lc) || t.href.toLowerCase().includes(lc)
      )
      if (matchedTabs.length) {
        result.push({
          key: "tabs", label: "Open Tabs", icon: Layers,
          items: matchedTabs.map(t => ({
            id:    `tab:${t.href}`,
            label: t.title,
            sub:   t.href,
            href:  t.href,
            icon:  Layers,
          })),
        })
      }
    }

    // 2. Static pages / forms / reports (prefix alone = browse that layer)
    const typedLayer =
      apiType === "__reports__" ? "report" as const :
      apiType === "__actions__" ? "action" as const :
      apiType === "__nav__"     ? "nav" as const :
      undefined
    const wantStatic = showNav && (cleanQ.length >= 1 || !!typedLayer)

    if (wantStatic) {
      const navResults = searchNav(cleanQ, typedLayer ? 40 : 18, typedLayer ? { type: typedLayer } : undefined)

      const byType: Record<string, NavResult[]> = {}
      for (const r of navResults) {
        ;(byType[r.type] ??= []).push(r)
      }

      for (const [type, items] of Object.entries(byType)) {
        const meta = TYPE_META[type]
        if (!meta) continue
        result.push({
          key: `nav_${type}`, label: meta.label, icon: meta.icon,
          items: items.map(r => ({
            id: r.id, label: r.label, sub: r.sub, href: r.href, icon: meta.icon,
          })),
        })
      }
    }

    // 3. API results
    if (showApi && apiResults) {
      const apiOrder = [
        "invoices", "bills", "payments_received", "bill_payments",
        "credit_notes", "debit_notes",
        "customers", "vendors", "accounts", "products", "employees", "transactions",
      ] as const
      for (const key of apiOrder) {
        const rows = apiResults[key as keyof ApiResults]
        if (!rows?.length) continue
        const meta = TYPE_META[key]
        result.push({
          key, label: meta.label, icon: meta.icon,
          items: rows.map(r => ({
            id:    `${key}:${r.id}`,
            label: r.label,
            sub:   r.sub,
            href:  r.href,
            icon:  meta.icon,
            date:   r.date,
            amount: r.amount,
            status: r.status,
          })),
        })
      }
    }

    return result
  }, [query, apiResults, tabs])

  const allItems: SearchItem[] = useMemo(() => groups.flatMap(g => g.items), [groups])

  // ── Keyboard nav ───────────────────────────────────────────────────────────

  const navigate = useCallback((href: string) => {
    addRecent(parsePrefix(query).q || query)
    setRecent(getRecent())
    router.push(href)
    setOpen(false)
  }, [query, router])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown")  { e.preventDefault(); setFocusedIndex(i => Math.min(i + 1, allItems.length - 1)) }
    else if (e.key === "ArrowUp") { e.preventDefault(); setFocusedIndex(i => Math.max(i - 1, 0)) }
    else if (e.key === "Enter" && allItems[focusedIndex]) { e.preventDefault(); navigate(allItems[focusedIndex].href) }
  }

  useEffect(() => setFocusedIndex(0), [groups.length])

  // ── Render ─────────────────────────────────────────────────────────────────

  if (!mounted || !open) return null

  let itemCounter = -1
  const isEmpty   = !query

  return createPortal(
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-[200] backdrop-blur-sm" onClick={() => setOpen(false)} />

      {/* Palette */}
      <div
        className="fixed left-1/2 top-[8%] -translate-x-1/2 z-[201]"
        style={{ width: "min(680px, calc(100vw - 32px))" }}>
        <div className="bg-[var(--bg-card)] rounded-2xl shadow-2xl border border-[var(--border)] overflow-hidden">

          {/* ── Input row ─────────────────────────────────────────────────── */}
          <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[var(--border)]">
            <Search className="w-4 h-4 text-[var(--text-muted)] shrink-0" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Search pages, forms, amounts… or inv:, amt:, form:, rpt:"
              className="flex-1 bg-transparent text-[14px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <div className="flex items-center gap-1.5 shrink-0">
              {loading && (
                <span className="w-3.5 h-3.5 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
              )}
              {query ? (
                <button type="button" onClick={() => { setQuery(""); setApiResults(null) }}
                  className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors rounded">
                  <X className="w-3.5 h-3.5" />
                </button>
              ) : null}
              <kbd className="hidden sm:flex items-center px-1.5 py-0.5 text-[10px] font-mono border border-[var(--border)] rounded text-[var(--text-muted)]">Esc</kbd>
            </div>
          </div>

          {/* ── Results or empty state ────────────────────────────────────── */}
          <div className="max-h-[480px] overflow-y-auto overscroll-contain">

            {/* Empty state */}
            {isEmpty && (
              <div className="px-4 pt-4 pb-5 space-y-4">
                {/* Recent searches */}
                {recent.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <Clock className="w-3 h-3 text-[var(--text-muted)]" />
                      <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                        Recent Searches
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {recent.map(r => (
                        <button key={r} type="button"
                          onClick={() => setQuery(r)}
                          className="px-2.5 py-1 rounded-lg border border-[var(--border)] text-[12px] text-[var(--text-secondary)] hover:border-[var(--primary)] hover:text-[var(--primary)] transition-colors">
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Quick actions */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="w-3 h-3 text-[var(--text-muted)]" />
                    <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                      Quick Actions
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {EMPTY_CHIPS.map(c => (
                      <Link key={c.href} href={c.href} onClick={() => setOpen(false)}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-[var(--border)] text-[12px] text-[var(--text-secondary)] hover:border-[var(--primary)] hover:text-[var(--primary)] transition-colors">
                        <ArrowRight className="w-3 h-3" /> {c.label}
                      </Link>
                    ))}
                  </div>
                </div>

                {/* Prefix hint */}
                <div className="pt-1 pb-1 border-t border-[var(--border)]">
                  <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">
                    <span className="font-semibold text-[var(--text-secondary)]">Tip:</span>{" "}
                    Browse by layer —{" "}
                    {["form:", "rpt:", "amt:", "inv:", "nav:", "tab:"].map(p => (
                      <button key={p} type="button" onClick={() => setQuery(p)}
                        className="inline-block font-mono text-[10px] bg-[var(--bg-page)] border border-[var(--border)] rounded px-1 py-0.5 mr-1 hover:border-[var(--primary)] hover:text-[var(--primary)] transition-colors">
                        {p}
                      </button>
                    ))}
                  </p>
                </div>
              </div>
            )}

            {/* No results */}
            {!isEmpty && !loading && groups.length === 0 && (
              <div className="px-4 py-10 text-center">
                <Search className="w-8 h-8 text-[var(--text-muted)]/30 mx-auto mb-2" />
                <p className="text-[13px] text-[var(--text-muted)]">
                  No results for{" "}
                  <span className="font-semibold text-[var(--text-primary)]">&ldquo;{query}&rdquo;</span>
                </p>
                <p className="text-[11px] text-[var(--text-muted)] mt-1">
                  Try a different term or use a prefix like <kbd className="font-mono text-[10px]">inv:</kbd>
                </p>
              </div>
            )}

            {/* Result groups */}
            {groups.map(group => {
              const GroupIcon = group.icon
              return (
                <div key={group.key}>
                  <div className="flex items-center gap-2 px-4 pt-3 pb-1">
                    <GroupIcon className="w-3 h-3 text-[var(--text-muted)]" />
                    <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                      {group.label}
                    </span>
                  </div>

                  {group.items.map(item => {
                    itemCounter++
                    const idx      = itemCounter
                    const ItemIcon = item.icon
                    const focused  = focusedIndex === idx

                    return (
                      <button key={item.id} type="button"
                        onClick={() => navigate(item.href)}
                        onMouseEnter={() => setFocusedIndex(idx)}
                        className={cn(
                          "w-full flex items-center gap-3 px-4 py-2.5 transition-colors cursor-pointer text-left",
                          focused
                            ? "bg-[var(--primary-light)] text-[var(--primary)]"
                            : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                        )}>

                        {/* Icon */}
                        <div className={cn(
                          "w-7 h-7 rounded-md flex items-center justify-center shrink-0",
                          focused ? "bg-[var(--primary)]/15" : "bg-[var(--bg-page)]"
                        )}>
                          <ItemIcon className="w-3.5 h-3.5" />
                        </div>

                        {/* Label + sub */}
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] font-medium truncate">
                            <Highlight text={item.label} query={parsePrefix(query).q || query} />
                          </div>
                          {item.sub && (
                            <div className="text-[11px] text-[var(--text-muted)] truncate">
                              {item.sub}
                            </div>
                          )}
                        </div>

                        {/* Right-side metadata */}
                        <div className="flex items-center gap-1.5 shrink-0">
                          {item.amount !== undefined && <AmountPill amount={item.amount} />}
                          {item.status && <StatusBadge status={item.status} />}
                          {!item.status && !item.amount && (
                            <span className="text-[10px] text-[var(--text-muted)] hidden sm:block">↵</span>
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )
            })}
          </div>

          {/* ── Footer ────────────────────────────────────────────────────── */}
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-[var(--border)] text-[11px] text-[var(--text-muted)]">
            <div className="flex items-center gap-3">
              <span><kbd className="font-mono">↑↓</kbd> navigate</span>
              <span><kbd className="font-mono">↵</kbd> open</span>
              <span><kbd className="font-mono">Esc</kbd> close</span>
            </div>
            {tabs.length > 1 && (
              <button type="button" onClick={() => setQuery("tab: ")}
                className="flex items-center gap-1 hover:text-[var(--primary)] transition-colors">
                <Layers className="w-3 h-3" />
                {tabs.length} open tabs
              </button>
            )}
          </div>
        </div>
      </div>
    </>,
    document.body
  )
}
