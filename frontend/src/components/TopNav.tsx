"use client"

import { createPortal } from "react-dom"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useCallback, useEffect, useRef, useState } from "react"
import {
  ChevronDown, ChevronLeft, ChevronRight,
  LogOut, UserCircle, LayoutGrid, Table2, Blocks, Sun, Moon, Search,
  PlusCircle, Scale, Stethoscope, Factory, Radio, LayoutDashboard, Settings,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getCurrentUser, removeAuthToken } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"
import { useModules } from "@/context/ModuleContext"
import { useTheme } from "@/context/ThemeContext"
import { TOP_NAV, SUB_NAV, getActiveSection, navVisible } from "@/lib/nav"
import type { TopNavSection } from "@/lib/nav"

const SECTION_OVERVIEW: Record<string, { href: string; label: string; icon: React.ElementType }> = {
  banking:       { href: "/banking",        label: "Banking Overview",    icon: LayoutGrid      },
  sales:         { href: "/receivable",     label: "Sales Overview",      icon: LayoutGrid      },
  purchases:     { href: "/payable",        label: "Purchases Overview",  icon: LayoutGrid      },
  accounting:    { href: "/entry",          label: "New Entry",           icon: PlusCircle      },
  reports:       { href: "/trial-balance",  label: "Trial Balance",       icon: Scale           },
  inventory:     { href: "/inventory",      label: "Inventory Overview",  icon: LayoutGrid      },
  payroll:       { href: "/hrm",            label: "Payroll Overview",    icon: LayoutGrid      },
  healthcare:    { href: "/healthcare",     label: "HC Overview",         icon: Stethoscope     },
  manufacturing: { href: "/manufacturing",  label: "Production Overview", icon: Factory         },
  telecom:       { href: "/telecom",        label: "Telecom Overview",    icon: Radio           },
  pra:           { href: "/pra-dashboard",  label: "PRA Dashboard",       icon: LayoutDashboard },
  system:        { href: "/settings",       label: "Settings",            icon: Settings        },
}

const LEFT_KEYS  = new Set(["dashboard", "banking", "sales", "purchases"])
const RIGHT_KEYS = new Set(["accounting", "reports", "system"])

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

  // open: which section key is expanded (or "__more__"), panelAnchor: the button's rect
  const [open, setOpen]               = useState<string | null>(null)
  const [panelAnchor, setPanelAnchor] = useState<DOMRect | null>(null)

  // Portal requires document — guard against SSR
  const [mounted, setMounted] = useState(false)

  // Scroll state for nav strip indicators
  const navScrollRef                    = useRef<HTMLDivElement>(null)
  const userRef                         = useRef<HTMLDivElement>(null)
  const [canScrollLeft, setCanScrollLeft]   = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)

  const activeSection = getActiveSection(pathname)

  // ── One-time effects ────────────────────────────────────────────────────────
  useEffect(() => setMounted(true), [])

  useEffect(() => {
    const user = getCurrentUser()
    if (user) {
      setUserName(user.full_name)
      setInitial(user.full_name.charAt(0).toUpperCase())
      setIsAdmin(user.role === "admin" || user.role === "owner")
    }
  }, [])

  // Close user dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userRef.current && !userRef.current.contains(e.target as Node)) {
        setUserOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  // Close section panel on route change
  useEffect(() => { setOpen(null); setPanelAnchor(null) }, [pathname])

  // ── Nav scroll indicators ───────────────────────────────────────────────────
  const checkScroll = useCallback(() => {
    const el = navScrollRef.current
    if (!el) return
    setCanScrollLeft(el.scrollLeft > 2)
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 2)
  }, [])

  useEffect(() => {
    checkScroll()
    const el = navScrollRef.current
    if (!el) return
    el.addEventListener("scroll", checkScroll, { passive: true })
    const ro = new ResizeObserver(checkScroll)
    ro.observe(el)
    return () => { el.removeEventListener("scroll", checkScroll); ro.disconnect() }
  }, [checkScroll])

  // ── Nav data ─────────────────────────────────────────────────────────────────
  const leftNav       = TOP_NAV.filter(s => LEFT_KEYS.has(s.key))
  const rightNav      = TOP_NAV.filter(s => RIGHT_KEYS.has(s.key))
  const installedMods = TOP_NAV.filter(s => !!s.forModule && installedModules.has(s.forModule!))

  const handleLogout = () => { removeAuthToken(); router.push("/login") }

  // Toggle open dropdown — captures button rect for portal positioning
  const toggle = (key: string, e: React.MouseEvent<HTMLButtonElement>) => {
    if (open === key) {
      setOpen(null); setPanelAnchor(null)
    } else {
      setPanelAnchor(e.currentTarget.getBoundingClientRect())
      setOpen(key)
    }
  }

  const closePanel = () => { setOpen(null); setPanelAnchor(null) }

  // ── Dropdown content builders ───────────────────────────────────────────────

  function buildSectionItems(sectionKey: string) {
    const ov    = SECTION_OVERVIEW[sectionKey]
    const items = (SUB_NAV[sectionKey] ?? []).filter(item => {
      if (!navVisible(item, installedModules)) return false
      if (item.adminOnly && !isAdmin) return false
      if (ov && item.href === ov.href) return false
      return true
    })
    // The overview link renders through the same template as every other
    // item (#132) — a distinct icon/bold first row read as a section
    // heading, so users skipped it.
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

  // ── Portal panel (one shared portal for all dropdowns) ────────────────────
  function renderPortal() {
    if (!mounted || !open || !panelAnchor) return null

    const isMore  = open === "__more__"
    const content = isMore ? buildMoreItems() : buildSectionItems(open)
    const top     = panelAnchor.bottom + 4
    // More ▾ aligns right edge to button right edge; others align left edge
    const style: React.CSSProperties = isMore
      ? { top, right: Math.max(8, window.innerWidth - panelAnchor.right) }
      : { top, left: Math.min(panelAnchor.left, window.innerWidth - 230) }

    return createPortal(
      <>
        {/* Full-screen backdrop — click it to close */}
        <div className="fixed inset-0 z-[99]" onClick={closePanel} />
        <div
          className="fixed bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-xl py-1 min-w-[210px] z-[100]"
          style={style}
        >
          {content}
        </div>
      </>,
      document.body
    )
  }

  // ── Tab renderer ──────────────────────────────────────────────────────────
  function renderTab(section: TopNavSection) {
    const isActive = activeSection === section.key
    const isOpen   = open === section.key
    const cls = cn(
      "flex items-center gap-0.5 px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap transition-colors cursor-pointer shrink-0",
      isActive
        ? "bg-[var(--nav-active)] text-[var(--nav-text)] font-semibold"
        : "text-[var(--nav-sub)] hover:bg-[var(--nav-hover)] hover:text-[var(--nav-text)]"
    )

    if (section.key === "dashboard") {
      return (
        <Link key={section.key} href="/dashboard" className={cls}>
          {section.label}
        </Link>
      )
    }

    return (
      <button key={section.key} type="button"
        onClick={(e) => toggle(section.key, e)} className={cls}>
        {section.label}
        <ChevronDown className={cn("w-3 h-3 transition-transform duration-150", isOpen && "rotate-180")} />
      </button>
    )
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <header className="h-[52px] bg-[var(--nav-bg)] flex items-center px-3 gap-1 shrink-0 z-50 relative print:hidden">

        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-2 mr-2 shrink-0">
          <div className="w-7 h-7 bg-[var(--primary)] rounded-md flex items-center justify-center text-white text-[11px] font-black select-none">
            EB
          </div>
          <span className="text-[var(--nav-text)] text-[13px] font-semibold hidden sm:block truncate max-w-[130px]">
            {settings.company_name || "Easy-Books"}
          </span>
        </Link>

        {/* Desktop nav — scrollable strip */}
        <div className="hidden md:flex items-center flex-1 min-w-0 relative">

          {/* Left scroll arrow */}
          {canScrollLeft && (
            <button type="button" aria-label="Scroll nav left"
              onClick={() => navScrollRef.current?.scrollBy({ left: -200, behavior: "smooth" })}
              className="absolute left-0 top-0 bottom-0 w-7 z-10 flex items-center justify-center bg-gradient-to-r from-[var(--nav-bg)] via-[var(--nav-bg)]/80 to-transparent text-[var(--nav-dim)] hover:text-[var(--nav-text)] transition-colors">
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Scrollable tab strip — overflow-x here is safe because dropdowns use portal */}
          <div ref={navScrollRef}
            className="flex items-center gap-0.5 overflow-x-auto flex-1 scrollbar-hide px-1"
            style={{ scrollBehavior: "smooth" }}>

            {leftNav.map(s => renderTab(s))}

            {installedMods.length > 0 && (
              <span className="w-px h-4 bg-[var(--nav-sep)] mx-1 shrink-0" aria-hidden />
            )}
            {installedMods.map(s => renderTab(s))}
            {installedMods.length > 0 && (
              <span className="w-px h-4 bg-[var(--nav-sep)] mx-1 shrink-0" aria-hidden />
            )}

            {rightNav.map(s => renderTab(s))}
          </div>

          {/* Right scroll arrow */}
          {canScrollRight && (
            <button type="button" aria-label="Scroll nav right"
              onClick={() => navScrollRef.current?.scrollBy({ left: 200, behavior: "smooth" })}
              className="absolute right-[72px] top-0 bottom-0 w-7 z-10 flex items-center justify-center bg-gradient-to-l from-[var(--nav-bg)] via-[var(--nav-bg)]/80 to-transparent text-[var(--nav-dim)] hover:text-[var(--nav-text)] transition-colors">
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          )}

          {/* More ▾ — fixed at right, NOT inside scroll container */}
          <button type="button"
            onClick={(e) => toggle("__more__", e)}
            className={cn(
              "flex items-center gap-1 px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap transition-colors cursor-pointer shrink-0 ml-1",
              open === "__more__"
                ? "bg-[var(--nav-hover)] text-[var(--nav-text)]"
                : "text-[var(--nav-dim)] hover:bg-[var(--nav-hover)] hover:text-[var(--nav-text)]"
            )}>
            More
            <ChevronDown className={cn("w-3 h-3 transition-transform duration-150", open === "__more__" && "rotate-180")} />
          </button>
        </div>

        {/* Right side — search + theme toggle + avatar */}
        <div className="flex items-center gap-1.5 ml-auto shrink-0">

          <button type="button"
            onClick={() => window.dispatchEvent(new CustomEvent("search:open"))}
            title="Search (Ctrl+K)"
            className="w-7 h-7 flex items-center justify-center rounded-full text-[var(--nav-dim)] hover:text-[var(--nav-text)] hover:bg-[var(--nav-icon-hover)] transition-colors">
            <Search className="w-4 h-4" />
          </button>

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

      {/* Portal-rendered dropdown panel — lives at body level, never clipped */}
      {renderPortal()}
    </>
  )
}
