"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import { Settings, ChevronDown, LogOut, UserCircle, Plus } from "lucide-react"
import { cn } from "@/lib/utils"
import { getCurrentUser, removeAuthToken } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"
import { useModules } from "@/context/ModuleContext"
import { TOP_NAV, getActiveSection, getSectionHref } from "@/lib/nav"

export default function TopNav() {
  const pathname        = usePathname()
  const router          = useRouter()
  const { settings }    = useSettings()
  const { installedModules } = useModules()

  const [userName, setUserName]   = useState("User")
  const [userInitial, setInitial] = useState("U")
  const [moreOpen, setMoreOpen]   = useState(false)
  const [userOpen, setUserOpen]   = useState(false)

  const moreRef = useRef<HTMLDivElement>(null)
  const userRef = useRef<HTMLDivElement>(null)

  const activeSection = getActiveSection(pathname)

  useEffect(() => {
    const user = getCurrentUser()
    if (user) {
      setUserName(user.full_name)
      setInitial(user.full_name.charAt(0).toUpperCase())
    }
  }, [])

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false)
      if (userRef.current && !userRef.current.contains(e.target as Node)) setUserOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  // Left core tabs: always shown before module tabs
  const LEFT_KEYS  = new Set(["dashboard", "banking", "sales", "purchases"])
  // Right core tabs: always shown after module tabs
  const RIGHT_KEYS = new Set(["accounting", "reports"])

  const leftNav       = TOP_NAV.filter(s => LEFT_KEYS.has(s.key))
  const rightNav      = TOP_NAV.filter(s => RIGHT_KEYS.has(s.key))
  const installedMods = TOP_NAV.filter(s => !!s.forModule && installedModules.has(s.forModule!))
  const availableMods = TOP_NAV.filter(s => !!s.forModule && !installedModules.has(s.forModule!))

  const handleLogout = () => {
    removeAuthToken()
    router.push("/login")
  }

  return (
    <header className="h-[52px] bg-[var(--nav-bg)] flex items-center px-4 gap-1 shrink-0 z-50 relative print:hidden">

      {/* ── Logo ─────────────────────────────────────── */}
      <Link href="/dashboard" className="flex items-center gap-2 mr-3 shrink-0">
        <div className="w-7 h-7 bg-[var(--primary)] rounded-md flex items-center justify-center text-white text-[11px] font-black select-none">
          EB
        </div>
        <span className="text-white text-[13px] font-semibold hidden sm:block truncate max-w-[140px]">
          {settings.company_name || "Easy-Books"}
        </span>
      </Link>

      {/* ── Desktop nav — hidden on mobile (BottomNav + MoreDrawer handle mobile) ── */}
      <nav className="hidden md:flex items-center gap-0.5 flex-1 overflow-x-auto scrollbar-hide">

        {/* Left core: Dashboard · Banking · Sales · Purchases */}
        {leftNav.map(section => (
          <Link key={section.key} href={getSectionHref(section.key)}
            className={cn(
              "px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap transition-colors",
              activeSection === section.key
                ? "bg-[var(--nav-active)] text-white font-semibold"
                : "text-[rgba(255,255,255,0.70)] hover:bg-[var(--nav-hover)] hover:text-white"
            )}
          >
            {section.label}
          </Link>
        ))}

        {/* ── Installed add-on tabs (tenant-specific, between Purchases & Accounting) ── */}
        {installedMods.length > 0 && (
          <span className="w-px h-4 bg-white/20 mx-1 shrink-0" aria-hidden />
        )}
        {installedMods.map(section => (
          <Link key={section.key} href={getSectionHref(section.key)}
            className={cn(
              "px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap transition-colors",
              activeSection === section.key
                ? "bg-[var(--nav-active)] text-white font-semibold"
                : "text-[rgba(255,255,255,0.85)] hover:bg-[var(--nav-hover)] hover:text-white"
            )}
          >
            {section.label}
          </Link>
        ))}
        {installedMods.length > 0 && (
          <span className="w-px h-4 bg-white/20 mx-1 shrink-0" aria-hidden />
        )}

        {/* Right core: Accounting · Reports */}
        {rightNav.map(section => (
          <Link key={section.key} href={getSectionHref(section.key)}
            className={cn(
              "px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap transition-colors",
              activeSection === section.key
                ? "bg-[var(--nav-active)] text-white font-semibold"
                : "text-[rgba(255,255,255,0.70)] hover:bg-[var(--nav-hover)] hover:text-white"
            )}
          >
            {section.label}
          </Link>
        ))}

        {/* ── More ▾ — uninstalled add-ons (discovery) ── */}
        <div ref={moreRef} className="relative">
          <button
            onClick={() => setMoreOpen(o => !o)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md text-[13px] whitespace-nowrap text-[rgba(255,255,255,0.55)] hover:bg-[var(--nav-hover)] hover:text-white transition-colors"
          >
            Add-ons <ChevronDown className="w-3 h-3" />
          </button>
          {moreOpen && (
            <div className="absolute top-full left-0 mt-1 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-lg py-1 min-w-[200px] z-50">
              {installedMods.length > 0 && (
                <>
                  <p className="px-4 pt-1 pb-0.5 text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                    Installed
                  </p>
                  {installedMods.map(section => (
                    <Link key={section.key} href={getSectionHref(section.key)}
                      onClick={() => setMoreOpen(false)}
                      className={cn(
                        "block px-4 py-2 text-[13px] transition-colors",
                        activeSection === section.key
                          ? "text-[var(--primary)] font-semibold bg-[var(--primary-light)]"
                          : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                      )}
                    >
                      {section.label}
                    </Link>
                  ))}
                  {availableMods.length > 0 && (
                    <div className="border-t border-[var(--border-light)] mt-1" />
                  )}
                </>
              )}
              {availableMods.length > 0 && (
                <>
                  <p className="px-4 pt-1 pb-0.5 text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                    Available
                  </p>
                  {availableMods.map(section => (
                    <Link key={section.key} href="/apps"
                      onClick={() => setMoreOpen(false)}
                      className="flex items-center justify-between px-4 py-2 text-[13px] text-[var(--text-muted)] hover:bg-[var(--bg-page)] transition-colors"
                    >
                      <span>{section.label}</span>
                      <span className="flex items-center gap-0.5 text-[10px] text-[var(--primary)] font-semibold">
                        <Plus className="w-2.5 h-2.5" />Install
                      </span>
                    </Link>
                  ))}
                </>
              )}
              <div className="border-t border-[var(--border-light)] mt-1 pt-1">
                <Link href="/apps" onClick={() => setMoreOpen(false)}
                  className="block px-4 py-1.5 text-[11px] text-[var(--text-muted)] hover:text-[var(--primary)] transition-colors">
                  Manage Add-ons →
                </Link>
              </div>
            </div>
          )}
        </div>
      </nav>

      {/* ── Right side — ml-auto pushes to far right on mobile (nav hidden) + desktop ── */}
      <div className="flex items-center gap-1.5 ml-auto shrink-0">
        <Link
          href="/settings"
          title="Settings"
          className="p-1.5 rounded-md text-[rgba(255,255,255,0.70)] hover:text-white hover:bg-[var(--nav-hover)] transition-colors"
        >
          <Settings className="w-4 h-4" />
        </Link>

        {/* User avatar + dropdown */}
        <div ref={userRef} className="relative">
          <button
            onClick={() => setUserOpen(o => !o)}
            title={userName}
            className="w-7 h-7 bg-[var(--primary)] rounded-full flex items-center justify-center text-white text-[11px] font-bold hover:bg-[var(--primary-dark)] transition-colors"
          >
            {userInitial}
          </button>
          {userOpen && (
            <div className="absolute top-full right-0 mt-1 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-lg py-1 min-w-[160px] z-50">
              <div className="px-4 py-2.5 border-b border-[var(--border-light)]">
                <div className="text-[13px] font-semibold text-[var(--text-primary)] truncate">{userName}</div>
              </div>
              <Link
                href="/profile"
                onClick={() => setUserOpen(false)}
                className="flex items-center gap-2 px-4 py-2 text-[13px] text-[var(--text-primary)] hover:bg-[var(--bg-page)] transition-colors"
              >
                <UserCircle className="w-3.5 h-3.5" /> My Profile
              </Link>
              <button
                onClick={handleLogout}
                className="w-full text-left flex items-center gap-2 px-4 py-2 text-[13px] text-[var(--danger)] hover:bg-[var(--bg-page)] transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" /> Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
