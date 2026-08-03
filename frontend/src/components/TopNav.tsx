"use client"

import { createPortal } from "react-dom"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
import {
  ChevronDown, LogOut, UserCircle, LayoutGrid, Table2, Blocks, Sun, Moon, Search,
  PlusCircle, Scale, Stethoscope, Factory, Radio, LayoutDashboard, Settings, Scissors,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getCurrentUser, removeAuthToken } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"
import { useModules } from "@/context/ModuleContext"
import { useTheme } from "@/context/ThemeContext"
import { TOP_NAV, SUB_NAV, getActiveSection, navVisible } from "@/lib/nav"
import type { TopNavSection } from "@/lib/nav"
import AlertsBell from "@/components/AlertsBell"
import ClientSwitcher from "@/components/ClientSwitcher"

const SECTION_OVERVIEW: Record<string, { href: string; label: string; icon: React.ElementType }> = {
  banking:       { href: "/banking",        label: "Banking Overview",    icon: LayoutGrid      },
  sales:         { href: "/receivable",     label: "Sales Overview",      icon: LayoutGrid      },
  purchases:     { href: "/purchases",      label: "Purchases Overview",  icon: LayoutGrid      },
  accounting:    { href: "/entry",          label: "New Entry",           icon: PlusCircle      },
  reports:       { href: "/trial-balance",  label: "Trial Balance",       icon: Scale           },
  inventory:     { href: "/inventory",      label: "Inventory Overview",  icon: LayoutGrid      },
  payroll:       { href: "/hrm",            label: "Payroll Overview",    icon: LayoutGrid      },
  healthcare:    { href: "/healthcare",     label: "HC Overview",         icon: Stethoscope     },
  weaving:       { href: "/weaving",         label: "Weaving Overview",     icon: Scissors        },
  manufacturing: { href: "/manufacturing",  label: "Production Overview", icon: Factory         },
  telecom:       { href: "/telecom",        label: "Telecom Overview",    icon: Radio           },
  pra:           { href: "/pra-dashboard",  label: "PRA Dashboard",       icon: LayoutDashboard },
  uae:           { href: "/uae",            label: "UAE Dashboard",       icon: LayoutDashboard },
  zatca:         { href: "/zatca",          label: "ZATCA Dashboard",     icon: LayoutDashboard },
  peppol:        { href: "/peppol",         label: "Peppol Dashboard",    icon: LayoutDashboard },
  india_gst:     { href: "/india-gst",      label: "GST Dashboard",       icon: LayoutDashboard },
  system:        { href: "/settings",       label: "Settings",            icon: Settings        },
  store:         { href: "/store/gate-outward", label: "Store Overview",  icon: LayoutGrid      },
}

/** Left strip — always-visible core tabs (md+), matches NAV_SECTION_ORDER prefix. */
const LEFT_KEYS  = new Set(["dashboard", "accounting", "reports", "banking", "sales", "purchases"])
/** Right strip — System always last. Module tabs sit in the centre add-on cluster. */
const RIGHT_KEYS = new Set(["system"])

/** Pixel budget for the two vertical separators around the add-on cluster. */
const ADDON_SEP_BUDGET = 18
/** Gap between flex children (`gap-0.5` = 2px). */
const TAB_GAP = 2

function tabLabel(section: TopNavSection, compact: boolean): string {
  if (compact && section.shortLabel) return section.shortLabel
  return section.label
}

/** Greedy fit: keep add-ons from the front until the next would overflow. */
function fitAddonCount(
  available: number,
  widths: number[],
  orderedKeys: string[],
  promoteKey: string | null,
): { visibleKeys: string[]; overflowKeys: string[] } {
  if (widths.length === 0 || available <= 0) {
    return { visibleKeys: [], overflowKeys: orderedKeys.slice() }
  }

  const widthByKey = new Map(orderedKeys.map((k, i) => [k, widths[i] ?? 90]))

  // Promote active overflow candidate to the front of the fit order.
  let order = orderedKeys.slice()
  if (promoteKey && order.includes(promoteKey)) {
    order = [promoteKey, ...order.filter(k => k !== promoteKey)]
  }

  let used = ADDON_SEP_BUDGET
  const visible: string[] = []
  for (const key of order) {
    const w = (widthByKey.get(key) ?? 90) + (visible.length > 0 ? TAB_GAP : 0)
    if (used + w > available) break
    used += w
    visible.push(key)
  }

  // If promotion didn't fit (tiny viewport), force-show it by dropping the last.
  if (promoteKey && order.includes(promoteKey) && !visible.includes(promoteKey)) {
    const pw = widthByKey.get(promoteKey) ?? 90
    if (visible.length === 0) {
      if (ADDON_SEP_BUDGET + pw <= available) visible.push(promoteKey)
    } else {
      while (visible.length > 0) {
        const trial = [...visible.slice(0, -1), promoteKey]
        let t = ADDON_SEP_BUDGET
        let ok = true
        for (let i = 0; i < trial.length; i++) {
          t += (widthByKey.get(trial[i]) ?? 90) + (i > 0 ? TAB_GAP : 0)
          if (t > available) { ok = false; break }
        }
        if (ok) {
          visible.length = 0
          visible.push(...trial)
          break
        }
        visible.pop()
      }
      if (!visible.includes(promoteKey) && ADDON_SEP_BUDGET + pw <= available) {
        visible.length = 0
        visible.push(promoteKey)
      }
    }
  }

  const visSet = new Set(visible)
  // Preserve TOP_NAV order in the overflow list (not promote order).
  const overflow = orderedKeys.filter(k => !visSet.has(k))
  return { visibleKeys: visible, overflowKeys: overflow }
}

export default function TopNav() {
  const pathname             = usePathname()
  const router               = useRouter()
  const { settings }         = useSettings()
  const { installedModules } = useModules()
  const { resolvedTheme, setTheme } = useTheme()

  const [userName, setUserName] = useState("User")
  const [initial, setInitial]   = useState("U")
  const [isAdmin, setIsAdmin]   = useState(false)
  const [userOpen, setUserOpen] = useState(false)

  const [open, setOpen]               = useState<string | null>(null)
  const [panelAnchor, setPanelAnchor] = useState<DOMRect | null>(null)
  const [moreExpanded, setMoreExpanded] = useState<string | null>(null)

  const [mounted, setMounted] = useState(false)

  const userRef       = useRef<HTMLDivElement>(null)
  const stripRef      = useRef<HTMLDivElement>(null)
  const leftRef       = useRef<HTMLDivElement>(null)
  const rightRef      = useRef<HTMLDivElement>(null)
  const moreRef       = useRef<HTMLButtonElement>(null)
  const measureRef    = useRef<HTMLDivElement>(null)

  const [addonWidths, setAddonWidths] = useState<number[]>([])
  const [budget, setBudget]           = useState(0)

  const activeSection = getActiveSection(pathname, installedModules)

  const leftNav  = useMemo(() => TOP_NAV.filter(s => LEFT_KEYS.has(s.key)), [])
  const rightNav = useMemo(() => TOP_NAV.filter(s => RIGHT_KEYS.has(s.key)), [])
  const installedMods = useMemo(
    () => TOP_NAV.filter(s => !!s.forModule && installedModules.has(s.forModule!)),
    [installedModules],
  )

  const promoteKey =
    installedMods.some(s => s.key === activeSection) ? activeSection : null

  const { visibleKeys, overflowKeys } = useMemo(() => {
    const keys = installedMods.map(s => s.key)
    return fitAddonCount(budget, addonWidths, keys, promoteKey)
  }, [budget, addonWidths, installedMods, promoteKey])

  const visibleAddons = useMemo(
    () => visibleKeys.map(k => installedMods.find(s => s.key === k)!).filter(Boolean),
    [visibleKeys, installedMods],
  )
  const overflowAddons = useMemo(
    () => overflowKeys.map(k => installedMods.find(s => s.key === k)!).filter(Boolean),
    [overflowKeys, installedMods],
  )

  // ── Measure addon tab natural widths (hidden row) ──────────────────────────
  useLayoutEffect(() => {
    const el = measureRef.current
    if (!el) { setAddonWidths([]); return }
    const kids = Array.from(el.children) as HTMLElement[]
    setAddonWidths(kids.map(k => Math.ceil(k.getBoundingClientRect().width)))
  }, [installedMods])

  // ── Available width for the add-on cluster ─────────────────────────────────
  const recomputeBudget = useCallback(() => {
    const strip = stripRef.current
    if (!strip) return
    const leftW  = leftRef.current?.offsetWidth ?? 0
    const rightW = rightRef.current?.offsetWidth ?? 0
    const moreW  = moreRef.current?.offsetWidth ?? 72
    // strip contains left + addons + right + more; budget is what's left for addons
    const avail = strip.clientWidth - leftW - rightW - moreW - 8
    setBudget(Math.max(0, avail))
  }, [])

  useLayoutEffect(() => {
    recomputeBudget()
    const strip = stripRef.current
    if (!strip) return
    const ro = new ResizeObserver(() => recomputeBudget())
    ro.observe(strip)
    if (leftRef.current) ro.observe(leftRef.current)
    if (rightRef.current) ro.observe(rightRef.current)
    if (moreRef.current) ro.observe(moreRef.current)
    return () => ro.disconnect()
  }, [recomputeBudget, leftNav, rightNav, installedMods.length])

  useEffect(() => setMounted(true), [])

  useEffect(() => {
    const user = getCurrentUser()
    if (user) {
      setUserName(user.full_name)
      setInitial(user.full_name.charAt(0).toUpperCase())
      setIsAdmin(user.role === "admin" || user.role === "owner")
    }
  }, [])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userRef.current && !userRef.current.contains(e.target as Node)) {
        setUserOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  useEffect(() => {
    setOpen(null)
    setPanelAnchor(null)
    setMoreExpanded(null)
  }, [pathname])

  const handleLogout = () => { removeAuthToken(); router.push("/login") }

  const toggle = (key: string, e: React.MouseEvent<HTMLButtonElement>) => {
    if (open === key) {
      setOpen(null); setPanelAnchor(null); setMoreExpanded(null)
    } else {
      setPanelAnchor(e.currentTarget.getBoundingClientRect())
      setOpen(key)
      if (key !== "__more__") setMoreExpanded(null)
    }
  }

  const closePanel = () => { setOpen(null); setPanelAnchor(null); setMoreExpanded(null) }

  function buildSectionItems(sectionKey: string) {
    const ov    = SECTION_OVERVIEW[sectionKey]
    const items = (SUB_NAV[sectionKey] ?? []).filter(item => {
      if (!navVisible(item, installedModules)) return false
      if (item.adminOnly && !isAdmin) return false
      if (ov && item.href === ov.href) return false
      return true
    })
    return (
      <>
        {[...(ov ? [ov] : []), ...items].map(item => (
          <Link key={item.href} href={item.href} onClick={closePanel}
            className={cn(
              "flex items-center gap-2.5 px-4 py-[7px] text-[13px] transition-colors",
              pathname === item.href || pathname.startsWith(item.href + "/")
                ? "text-[var(--primary)] font-semibold bg-[var(--primary-light)]"
                : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
            )}>
            <item.icon className="w-3.5 h-3.5 shrink-0 opacity-60" />
            {item.label}
          </Link>
        ))}
      </>
    )
  }

  function buildMoreItems() {
    return (
      <>
        {overflowAddons.length > 0 && (
          <>
            <p className="px-4 pt-2 pb-1 text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
              Sections
            </p>
            {overflowAddons.map(section => {
              const expanded = moreExpanded === section.key
              const isActive = activeSection === section.key
              return (
                <div key={section.key}>
                  <button
                    type="button"
                    onClick={() => setMoreExpanded(expanded ? null : section.key)}
                    className={cn(
                      "w-full flex items-center justify-between gap-2 px-4 py-2 text-[13px] transition-colors",
                      isActive
                        ? "text-[var(--primary)] font-semibold bg-[var(--primary-light)]"
                        : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                    )}
                  >
                    <span>{section.label}</span>
                    <ChevronDown className={cn(
                      "w-3 h-3 opacity-50 transition-transform duration-150",
                      expanded && "rotate-180",
                    )} />
                  </button>
                  {expanded && (
                    <div className="bg-[var(--bg-page)]/60 border-y border-[var(--border-light)] py-0.5 mb-0.5">
                      {buildSectionItems(section.key)}
                    </div>
                  )}
                </div>
              )
            })}
            <div className="border-t border-[var(--border-light)] mt-1" />
          </>
        )}

        <p className="px-4 pt-2 pb-1 text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
          Custom Reports
        </p>
        <Link href="/reports/builder" onClick={closePanel}
          className={cn(
            "flex items-center gap-2.5 px-4 py-2.5 text-[13px] font-semibold transition-colors border-b border-[var(--border-light)]",
            pathname.startsWith("/reports/builder")
              ? "text-[var(--primary)] bg-[var(--primary-light)]"
              : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
          )}>
          <Table2 className="w-3.5 h-3.5 shrink-0 opacity-60" />
          Report Builder
        </Link>
        <Link href="/reports/builder" onClick={closePanel}
          className="flex items-center gap-2.5 px-4 py-2 text-[13px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] transition-colors">
          <LayoutGrid className="w-3.5 h-3.5 shrink-0 opacity-50" />
          Saved Reports
        </Link>
        {isAdmin && (
          <>
            <div className="border-t border-[var(--border-light)] mt-1 pt-1" />
            <p className="px-4 pt-1 pb-0.5 text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
              Add-ons
            </p>
            <Link href="/apps" onClick={closePanel}
              className="flex items-center gap-2.5 px-4 py-2 text-[13px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] transition-colors">
              <Blocks className="w-3.5 h-3.5 shrink-0 opacity-50" />
              Manage Add-ons
            </Link>
          </>
        )}
      </>
    )
  }

  function renderPortal() {
    if (!mounted || !open || !panelAnchor) return null

    const isMore  = open === "__more__"
    const content = isMore ? buildMoreItems() : buildSectionItems(open)
    const top     = panelAnchor.bottom + 4
    const style: React.CSSProperties = isMore
      ? { top, right: Math.max(8, window.innerWidth - panelAnchor.right) }
      : { top, left: Math.min(panelAnchor.left, window.innerWidth - 230) }

    return createPortal(
      <>
        <div className="fixed inset-0 z-[99]" onClick={closePanel} />
        <div
          className={cn(
            "fixed bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-xl py-1 z-[100]",
            isMore && overflowAddons.length > 0 ? "min-w-[240px] max-h-[min(70vh,480px)] overflow-y-auto" : "min-w-[210px]",
          )}
          style={style}
        >
          {content}
        </div>
      </>,
      document.body
    )
  }

  function renderTab(section: TopNavSection, compact = false) {
    const isActive = activeSection === section.key
    const isOpen   = open === section.key
    const label    = tabLabel(section, compact)
    const cls = cn(
      "flex items-center gap-0.5 px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap transition-colors cursor-pointer shrink-0",
      isActive
        ? "bg-[var(--nav-active)] text-[var(--nav-text)] font-semibold"
        : "text-[var(--nav-sub)] hover:bg-[var(--nav-hover)] hover:text-[var(--nav-text)]"
    )

    if (section.key === "dashboard") {
      return (
        <Link key={section.key} href="/dashboard" className={cls}>
          {label}
        </Link>
      )
    }

    return (
      <button key={section.key} type="button"
        onClick={(e) => toggle(section.key, e)} className={cls}>
        {label}
        <ChevronDown className={cn("w-3 h-3 transition-transform duration-150", isOpen && "rotate-180")} />
      </button>
    )
  }

  const moreHighlightsOverflow = overflowAddons.some(s => s.key === activeSection)

  return (
    <>
      <header className="h-[52px] bg-[var(--nav-bg)] flex items-center px-3 gap-1 shrink-0 z-50 relative print:hidden">

        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-2 mr-2 shrink-0">
          <div className="w-7 h-7 bg-[var(--primary)] rounded-md flex items-center justify-center text-white text-[11px] font-black select-none">
            EB
          </div>
        </Link>
        <ClientSwitcher fallbackName={settings.company_name || "Easy-Books"} className="mr-2" />

        {/* Desktop nav — priority strip + More overflow (no horizontal scroll) */}
        <div ref={stripRef} className="hidden md:flex items-center flex-1 min-w-0">

          <div ref={leftRef} className="flex items-center gap-0.5 shrink-0">
            {leftNav.map(s => renderTab(s))}
          </div>

          {visibleAddons.length > 0 && (
            <>
              <span className="w-px h-4 bg-[var(--nav-sep)] mx-1 shrink-0" aria-hidden />
              <div className="flex items-center gap-0.5 min-w-0">
                {visibleAddons.map(s => renderTab(s, true))}
              </div>
              <span className="w-px h-4 bg-[var(--nav-sep)] mx-1 shrink-0" aria-hidden />
            </>
          )}

          <div ref={rightRef} className="flex items-center gap-0.5 shrink-0">
            {rightNav.map(s => renderTab(s))}
          </div>

          <button ref={moreRef} type="button"
            onClick={(e) => toggle("__more__", e)}
            className={cn(
              "flex items-center gap-1 px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap transition-colors cursor-pointer shrink-0 ml-1",
              open === "__more__" || moreHighlightsOverflow
                ? "bg-[var(--nav-hover)] text-[var(--nav-text)]"
                : "text-[var(--nav-dim)] hover:bg-[var(--nav-hover)] hover:text-[var(--nav-text)]"
            )}>
            More
            {overflowAddons.length > 0 && (
              <span className="text-[10px] opacity-60 tabular-nums">+{overflowAddons.length}</span>
            )}
            <ChevronDown className={cn("w-3 h-3 transition-transform duration-150", open === "__more__" && "rotate-180")} />
          </button>
        </div>

        {/* Off-screen measure row — natural widths of every installed add-on tab */}
        <div
          ref={measureRef}
          aria-hidden
          className="fixed left-[-9999px] top-0 flex items-center gap-0.5 opacity-0 pointer-events-none"
        >
          {installedMods.map(s => (
            <span
              key={s.key}
              className="flex items-center gap-0.5 px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap shrink-0"
            >
              {tabLabel(s, true)}
              <ChevronDown className="w-3 h-3" />
            </span>
          ))}
        </div>

        {/* Right side — search + theme toggle + avatar */}
        <div className="flex items-center gap-1.5 ml-auto shrink-0">

          <button type="button"
            onClick={() => window.dispatchEvent(new CustomEvent("search:open"))}
            title="Search (Ctrl+K)"
            className="w-7 h-7 flex items-center justify-center rounded-full text-[var(--nav-dim)] hover:text-[var(--nav-text)] hover:bg-[var(--nav-icon-hover)] transition-colors">
            <Search className="w-4 h-4" />
          </button>

          <AlertsBell />

          <button type="button"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            title={resolvedTheme === "dark" ? "Light mode" : "Dark mode"}
            className="w-7 h-7 flex items-center justify-center rounded-full text-[var(--nav-dim)] hover:text-[var(--nav-text)] hover:bg-[var(--nav-icon-hover)] transition-colors">
            {resolvedTheme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          <div ref={userRef} className="relative">
            <button type="button" onClick={() => setUserOpen(o => !o)} title={userName}
              className="w-7 h-7 bg-[var(--primary)] rounded-full flex items-center justify-center text-white text-[11px] font-bold hover:bg-[var(--primary-dark)] transition-colors cursor-pointer">
              {initial}
            </button>
            {userOpen && (
              <div className="absolute top-full right-0 mt-1 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-xl py-1 min-w-[160px] z-[100]">
                <div className="px-4 py-2.5 border-b border-[var(--border-light)]">
                  <div className="text-[13px] font-semibold text-[var(--text-primary)] truncate">{userName}</div>
                </div>
                <Link href="/profile" onClick={() => setUserOpen(false)}
                  className="flex items-center gap-2 px-4 py-2 text-[13px] text-[var(--text-primary)] hover:bg-[var(--bg-page)] transition-colors">
                  <UserCircle className="w-3.5 h-3.5" /> My Profile
                </Link>
                <button type="button" onClick={handleLogout}
                  className="w-full text-left flex items-center gap-2 px-4 py-2 text-[13px] text-[var(--danger)] hover:bg-[var(--bg-page)] transition-colors">
                  <LogOut className="w-3.5 h-3.5" /> Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {renderPortal()}
    </>
  )
}
