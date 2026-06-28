"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import { Settings, ChevronDown, LogOut, UserCircle, LayoutGrid, Table2, Blocks } from "lucide-react"
import { cn } from "@/lib/utils"
import { getCurrentUser, removeAuthToken } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"
import { useModules } from "@/context/ModuleContext"
import { TOP_NAV, SUB_NAV, getActiveSection } from "@/lib/nav"
import type { TopNavSection } from "@/lib/nav"

// Overview hub page for each section
const SECTION_OVERVIEW: Record<string, { href: string; label: string }> = {
  banking:       { href: "/banking",        label: "Banking Overview"    },
  sales:         { href: "/receivable",     label: "Sales Overview"      },
  purchases:     { href: "/payable",        label: "Purchases Overview"  },
  accounting:    { href: "/entry",          label: "New Entry"           },
  reports:       { href: "/trial-balance",  label: "Trial Balance"       },
  inventory:     { href: "/inventory",      label: "Inventory Overview"  },
  payroll:       { href: "/hrm",            label: "Payroll Overview"    },
  healthcare:    { href: "/healthcare",     label: "HC Overview"         },
  manufacturing: { href: "/manufacturing",  label: "Production Overview" },
  telecom:       { href: "/telecom",        label: "Telecom Overview"    },
  pra:           { href: "/pra-dashboard",  label: "PRA Dashboard"       },
}

const LEFT_KEYS  = new Set(["dashboard", "banking", "sales", "purchases"])
const RIGHT_KEYS = new Set(["accounting", "reports"])

export default function TopNav() {
  const pathname             = usePathname()
  const router               = useRouter()
  const { settings }         = useSettings()
  const { installedModules } = useModules()

  const [userName, setUserName] = useState("User")
  const [initial, setInitial]   = useState("U")
  const [isAdmin, setIsAdmin]   = useState(false)
  const [open, setOpen]         = useState<string | null>(null)
  const [userOpen, setUserOpen] = useState(false)

  const navRef  = useRef<HTMLElement>(null)
  const userRef = useRef<HTMLDivElement>(null)

  const activeSection = getActiveSection(pathname)

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
      if (navRef.current && !navRef.current.contains(e.target as Node)) setOpen(null)
      if (userRef.current && !userRef.current.contains(e.target as Node)) setUserOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  useEffect(() => { setOpen(null) }, [pathname])

  const leftNav       = TOP_NAV.filter(s => LEFT_KEYS.has(s.key))
  const rightNav      = TOP_NAV.filter(s => RIGHT_KEYS.has(s.key))
  const installedMods = TOP_NAV.filter(s => !!s.forModule && installedModules.has(s.forModule!))

  const handleLogout = () => { removeAuthToken(); router.push("/login") }
  const toggle = (key: string) => setOpen(prev => prev === key ? null : key)

  // Renders the dropdown panel for a section — called inline, not as a component
  function renderPanel(sectionKey: string) {
    const ov    = SECTION_OVERVIEW[sectionKey]
    const items = (SUB_NAV[sectionKey] ?? []).filter(item => {
      if (item.forModule && !installedModules.has(item.forModule)) return false
      if (item.adminOnly && !isAdmin) return false
      if (ov && item.href === ov.href) return false
      return true
    })
    return (
      <div className="absolute top-full left-0 mt-1 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-xl py-1 min-w-[210px] z-[100]">
        {ov && (
          <Link href={ov.href} onClick={() => setOpen(null)}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 text-[13px] font-semibold transition-colors border-b border-[var(--border-light)]",
              pathname === ov.href || pathname.startsWith(ov.href + "/")
                ? "text-[var(--primary)] bg-[var(--primary-light)]"
                : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
            )}>
            <LayoutGrid className="w-3.5 h-3.5 shrink-0 opacity-60" />
            {ov.label}
          </Link>
        )}
        {items.map(item => (
          <Link key={item.href} href={item.href} onClick={() => setOpen(null)}
            className={cn(
              "block px-4 py-[7px] text-[13px] transition-colors",
              pathname === item.href || pathname.startsWith(item.href + "/")
                ? "text-[var(--primary)] font-semibold bg-[var(--primary-light)]"
                : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
            )}>
            {item.label}
          </Link>
        ))}
      </div>
    )
  }

  // Renders a single tab — inline function so it shares closures but is NOT a React component
  function renderTab(section: TopNavSection, dimmed = false) {
    const isActive = activeSection === section.key
    const isOpen   = open === section.key
    const cls = cn(
      "flex items-center gap-0.5 px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap transition-colors cursor-pointer",
      isActive
        ? "bg-[var(--nav-active)] text-white font-semibold"
        : dimmed
          ? "text-[rgba(255,255,255,0.55)] hover:bg-[var(--nav-hover)] hover:text-white"
          : "text-[rgba(255,255,255,0.75)] hover:bg-[var(--nav-hover)] hover:text-white"
    )

    if (section.key === "dashboard") {
      return (
        <Link key={section.key} href="/dashboard" className={cls}>
          {section.label}
        </Link>
      )
    }

    return (
      <div key={section.key} className="relative">
        <button type="button" onClick={() => toggle(section.key)} className={cls}>
          {section.label}
          <ChevronDown className={cn("w-3 h-3 transition-transform duration-150", isOpen && "rotate-180")} />
        </button>
        {isOpen && renderPanel(section.key)}
      </div>
    )
  }

  return (
    <header ref={navRef}
      className="h-[52px] bg-[var(--nav-bg)] flex items-center px-4 gap-1 shrink-0 z-50 relative print:hidden">

      {/* Logo */}
      <Link href="/dashboard" className="flex items-center gap-2 mr-3 shrink-0">
        <div className="w-7 h-7 bg-[var(--primary)] rounded-md flex items-center justify-center text-white text-[11px] font-black select-none">
          EB
        </div>
        <span className="text-white text-[13px] font-semibold hidden sm:block truncate max-w-[140px]">
          {settings.company_name || "Easy-Books"}
        </span>
      </Link>

      {/* Desktop nav */}
      <nav className="hidden md:flex items-center gap-0.5 flex-1 min-w-0">

        {/* Left core: Dashboard · Banking · Sales · Purchases */}
        {leftNav.map(s => renderTab(s))}

        {/* Tenant add-on tabs — inline between Purchases and Accounting */}
        {installedMods.length > 0 && <span className="w-px h-4 bg-white/20 mx-1 shrink-0" aria-hidden />}
        {installedMods.map(s => renderTab(s))}
        {installedMods.length > 0 && <span className="w-px h-4 bg-white/20 mx-1 shrink-0" aria-hidden />}

        {/* Right core: Accounting · Reports */}
        {rightNav.map(s => renderTab(s))}

        {/* More ▾ — custom reports + add-ons shortcut */}
        <div className="relative">
          <button type="button" onClick={() => toggle("__more__")}
            className={cn(
              "flex items-center gap-1 px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap transition-colors cursor-pointer",
              open === "__more__"
                ? "bg-[var(--nav-hover)] text-white"
                : "text-[rgba(255,255,255,0.55)] hover:bg-[var(--nav-hover)] hover:text-white"
            )}>
            More <ChevronDown className={cn("w-3 h-3 transition-transform duration-150", open === "__more__" && "rotate-180")} />
          </button>
          {open === "__more__" && (
            <div className="absolute top-full right-0 mt-1 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-xl py-1 min-w-[220px] z-[100]">
              <p className="px-4 pt-2 pb-1 text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                Custom Reports
              </p>
              <Link href="/reports/builder" onClick={() => setOpen(null)}
                className={cn(
                  "flex items-center gap-2.5 px-4 py-2.5 text-[13px] font-semibold transition-colors border-b border-[var(--border-light)]",
                  pathname.startsWith("/reports/builder")
                    ? "text-[var(--primary)] bg-[var(--primary-light)]"
                    : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                )}>
                <Table2 className="w-3.5 h-3.5 shrink-0 opacity-60" />
                Report Builder
              </Link>
              <Link href="/reports/builder" onClick={() => setOpen(null)}
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
                  <Link href="/apps" onClick={() => setOpen(null)}
                    className="flex items-center gap-2.5 px-4 py-2 text-[13px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] transition-colors">
                    <Blocks className="w-3.5 h-3.5 shrink-0 opacity-50" />
                    Manage Add-ons
                  </Link>
                </>
              )}
            </div>
          )}
        </div>
      </nav>

      {/* Right side */}
      <div className="flex items-center gap-1.5 ml-auto shrink-0">
        <Link href="/settings" title="Settings"
          className="p-1.5 rounded-md text-[rgba(255,255,255,0.70)] hover:text-white hover:bg-[var(--nav-hover)] transition-colors">
          <Settings className="w-4 h-4" />
        </Link>

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
  )
}
