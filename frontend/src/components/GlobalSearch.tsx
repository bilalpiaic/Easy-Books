"use client"

import { createPortal } from "react-dom"
import { useEffect, useRef, useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  Search, X, LayoutGrid, Users, Truck, FileSignature,
  Receipt, BookOpen, Package, UserCog, ClipboardList,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { searchNav, type NavResult } from "@/lib/navIndex"

// ── types ─────────────────────────────────────────────────────────────────────

interface ApiRow { id: number; label: string; sub: string; href: string }

interface ApiResults {
  customers:    ApiRow[]
  vendors:      ApiRow[]
  invoices:     ApiRow[]
  bills:        ApiRow[]
  accounts:     ApiRow[]
  products:     ApiRow[]
  employees:    ApiRow[]
  transactions: ApiRow[]
}

interface SearchItem {
  id:    string
  label: string
  sub:   string
  href:  string
  icon:  React.ElementType
}

interface Group { key: string; label: string; items: SearchItem[] }

// ── highlight ─────────────────────────────────────────────────────────────────

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

// ── API icon map ──────────────────────────────────────────────────────────────

const TYPE_META: Record<string, { label: string; icon: React.ElementType }> = {
  nav:          { label: "Navigation",   icon: LayoutGrid   },
  customers:    { label: "Customers",    icon: Users        },
  vendors:      { label: "Vendors",      icon: Truck        },
  invoices:     { label: "Invoices",     icon: FileSignature},
  bills:        { label: "Bills",        icon: Receipt      },
  accounts:     { label: "Accounts",     icon: BookOpen     },
  products:     { label: "Products",     icon: Package      },
  employees:    { label: "Employees",    icon: UserCog      },
  transactions: { label: "Transactions", icon: ClipboardList},
}

// ── component ─────────────────────────────────────────────────────────────────

export default function GlobalSearch() {
  const router = useRouter()

  const [open,          setOpen]          = useState(false)
  const [mounted,       setMounted]       = useState(false)
  const [query,         setQuery]         = useState("")
  const [debouncedQ,    setDebouncedQ]    = useState("")
  const [apiResults,    setApiResults]    = useState<ApiResults | null>(null)
  const [loading,       setLoading]       = useState(false)
  const [focusedIndex,  setFocusedIndex]  = useState(0)

  const inputRef = useRef<HTMLInputElement>(null)

  // ── lifecycle ──────────────────────────────────────────────────────────────

  useEffect(() => setMounted(true), [])

  // Global Ctrl+K / ⌘K + custom event from TopNav button
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault()
        setOpen(o => !o)
      }
      if (e.key === "Escape") setOpen(false)
    }
    const onEvent = () => setOpen(true)
    window.addEventListener("keydown", onKey)
    window.addEventListener("search:open", onEvent)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.removeEventListener("search:open", onEvent)
    }
  }, [])

  // Focus input when palette opens
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 30)
      setQuery("")
      setDebouncedQ("")
      setApiResults(null)
      setFocusedIndex(0)
    }
  }, [open])

  // Debounce query → debouncedQ (150 ms)
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(query), 150)
    return () => clearTimeout(t)
  }, [query])

  // Fetch from API when debounced query changes (min 2 chars for data)
  useEffect(() => {
    if (debouncedQ.length < 2) {
      setApiResults(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    apiFetch<ApiResults>(`/api/search?q=${encodeURIComponent(debouncedQ)}&limit=5`)
      .then(data  => { if (!cancelled) { setApiResults(data); setLoading(false) } })
      .catch(()   => { if (!cancelled)   setLoading(false) })
    return () => { cancelled = true }
  }, [debouncedQ])

  // ── build groups ───────────────────────────────────────────────────────────

  const buildGroups = useCallback((): Group[] => {
    const groups: Group[] = []

    // Nav (static, shown for any query length ≥ 1)
    if (query.length >= 1) {
      const navItems = searchNav(query).map(r => ({
        id:   r.id,
        label: r.label,
        sub:   r.sub,
        href:  r.href,
        icon:  LayoutGrid,
      }))
      if (navItems.length) groups.push({ key: "nav", label: "Navigation", items: navItems })
    }

    // API results
    if (apiResults) {
      const order: (keyof ApiResults)[] = [
        "customers","vendors","invoices","bills","accounts","products","employees","transactions"
      ]
      for (const key of order) {
        const rows = apiResults[key]
        if (!rows?.length) continue
        const meta = TYPE_META[key]
        groups.push({
          key,
          label: meta.label,
          items: rows.map(r => ({
            id:    `${key}:${r.id}`,
            label: r.label,
            sub:   r.sub,
            href:  r.href,
            icon:  meta.icon,
          })),
        })
      }
    }

    return groups
  }, [query, apiResults])

  const groups = buildGroups()

  // Flat list for keyboard navigation
  const allItems: SearchItem[] = groups.flatMap(g => g.items)

  // ── keyboard navigation ────────────────────────────────────────────────────

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setFocusedIndex(i => Math.min(i + 1, allItems.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setFocusedIndex(i => Math.max(i - 1, 0))
    } else if (e.key === "Enter" && allItems[focusedIndex]) {
      e.preventDefault()
      router.push(allItems[focusedIndex].href)
      setOpen(false)
    }
  }

  // Reset focused index when results change
  useEffect(() => setFocusedIndex(0), [groups.length])

  // ── render ─────────────────────────────────────────────────────────────────

  if (!mounted || !open) return null

  let itemCounter = -1

  return createPortal(
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-[200] backdrop-blur-sm"
        onClick={() => setOpen(false)} />

      {/* Palette */}
      <div className="fixed left-1/2 top-[12%] -translate-x-1/2 w-full max-w-[640px] z-[201] mx-4"
        style={{ maxWidth: "min(640px, calc(100vw - 32px))" }}>
        <div className="bg-[var(--bg-card)] rounded-xl shadow-2xl border border-[var(--border)] overflow-hidden">

          {/* Input row */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--border)]">
            <Search className="w-4 h-4 text-[var(--text-muted)] shrink-0" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Search customers, invoices, accounts, pages…"
              className="flex-1 bg-transparent text-[14px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <div className="flex items-center gap-1.5 shrink-0">
              {loading && (
                <span className="w-3.5 h-3.5 border-2 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
              )}
              {query && (
                <button type="button" onClick={() => { setQuery(""); setApiResults(null) }}
                  className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
              <kbd className="hidden sm:flex items-center px-1.5 py-0.5 text-[10px] font-mono border border-[var(--border)] rounded text-[var(--text-muted)]">
                Esc
              </kbd>
            </div>
          </div>

          {/* Results */}
          <div className="max-h-[400px] overflow-y-auto overscroll-contain">
            {!query && (
              <div className="px-4 py-8 text-center text-[13px] text-[var(--text-muted)]">
                Type to search across customers, invoices, accounts, pages, and more
              </div>
            )}

            {query && !loading && groups.length === 0 && (
              <div className="px-4 py-8 text-center text-[13px] text-[var(--text-muted)]">
                No results for <span className="font-semibold text-[var(--text-primary)]">&ldquo;{query}&rdquo;</span>
              </div>
            )}

            {groups.map(group => {
              const Icon = TYPE_META[group.key]?.icon ?? LayoutGrid
              return (
                <div key={group.key}>
                  <div className="flex items-center gap-2 px-4 pt-3 pb-1">
                    <Icon className="w-3 h-3 text-[var(--text-muted)]" />
                    <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                      {group.label}
                    </span>
                  </div>
                  {group.items.map(item => {
                    itemCounter++
                    const idx = itemCounter
                    const ItemIcon = item.icon
                    return (
                      <Link key={item.id} href={item.href}
                        onClick={() => setOpen(false)}
                        onMouseEnter={() => setFocusedIndex(idx)}
                        className={cn(
                          "flex items-center gap-3 px-4 py-2.5 transition-colors cursor-pointer",
                          focusedIndex === idx
                            ? "bg-[var(--primary-light)] text-[var(--primary)]"
                            : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                        )}>
                        <div className={cn(
                          "w-7 h-7 rounded-md flex items-center justify-center shrink-0",
                          focusedIndex === idx ? "bg-[var(--primary)]/15" : "bg-[var(--bg-page)]"
                        )}>
                          <ItemIcon className="w-3.5 h-3.5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] font-medium truncate">
                            <Highlight text={item.label} query={query} />
                          </div>
                          {item.sub && (
                            <div className="text-[11px] text-[var(--text-muted)] truncate">
                              {item.sub}
                            </div>
                          )}
                        </div>
                        <span className="text-[10px] text-[var(--text-muted)] shrink-0 hidden sm:block">↵</span>
                      </Link>
                    )
                  })}
                </div>
              )
            })}
          </div>

          {/* Footer hints */}
          {allItems.length > 0 && (
            <div className="flex items-center gap-4 px-4 py-2.5 border-t border-[var(--border)] text-[11px] text-[var(--text-muted)]">
              <span><kbd className="font-mono">↑↓</kbd> navigate</span>
              <span><kbd className="font-mono">↵</kbd> open</span>
              <span><kbd className="font-mono">Esc</kbd> close</span>
            </div>
          )}
        </div>
      </div>
    </>,
    document.body
  )
}
