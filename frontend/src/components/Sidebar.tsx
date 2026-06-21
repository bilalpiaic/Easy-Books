"use client"

import { useEffect, useRef, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { X, ChevronRight, ChevronDown, Pin, PinOff, LogOut } from "lucide-react"
import { cn } from "@/lib/utils"
import { getCurrentUser, removeAuthToken } from "@/lib/auth"
import { apiFetch } from "@/lib/api"
import { NAV, ALL_SECTIONS } from "@/lib/nav"
import { useTranslation } from "react-i18next"

const SECTION_COLORS: Record<string, string> = {
  Overview:      "text-[#ffd966]",
  Ledger:        "text-blue-400",
  Receivable:    "text-green-400",
  Payable:       "text-orange-400",
  Inventory:     "text-amber-400",
  Manufacturing: "text-pink-400",
  Telecom:       "text-teal-400",
  Banking:       "text-purple-400",
  Reports:       "text-cyan-400",
  System:        "text-white/40",
}

const HUB_ROUTES: Record<string, string> = {
  Receivable: "/receivable",
  Payable:    "/payable",
  Inventory:  "/inventory",
  Banking:    "/banking",
}

// Hub hrefs only highlight on exact pathname match to avoid conflicting with sub-page nav items
const HUB_HREFS = new Set(Object.values(HUB_ROUTES))

type Me = { role?: string; tenant?: { business_model?: string } }

interface SidebarProps {
  /** Drawer is shown when true; closed when false. Caller controls. */
  open: boolean
  onClose: () => void
  /** When true (md+ only), the sidebar takes part in layout flow instead
   *  of overlaying. Mobile always overlays regardless. */
  pinned: boolean
  onTogglePinned: () => void
}

export default function Sidebar({ open, onClose, pinned, onTogglePinned }: SidebarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const { t } = useTranslation()
  const [orgName, setOrgName]     = useState("Easy-Books")
  const [userName, setUserName]   = useState("User")
  const [userInitial, setInitial] = useState("U")
  const [businessModel, setBusinessModel] = useState<string>("simple")
  const [role, setRole] = useState<string>(() => getCurrentUser()?.role ?? "viewer")

  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem("sidebar-collapsed") ?? "[]"))
    } catch { return new Set() }
  })

  const toggleSection = (section: string) => {
    setCollapsedSections(prev => {
      const next = new Set(prev)
      if (next.has(section)) { next.delete(section) } else { next.add(section) }
      localStorage.setItem("sidebar-collapsed", JSON.stringify([...next]))
      return next
    })
  }

  const [tooltip, setTooltip] = useState<{ section: string; y: number } | null>(null)
  const tooltipTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const openTooltip = (section: string, e: React.MouseEvent<HTMLButtonElement>) => {
    if (tooltipTimer.current) clearTimeout(tooltipTimer.current)
    const rect = e.currentTarget.getBoundingClientRect()
    setTooltip({ section, y: rect.top })
  }
  const closeTooltip = () => {
    tooltipTimer.current = setTimeout(() => setTooltip(null), 150)
  }
  const keepTooltip = () => {
    if (tooltipTimer.current) clearTimeout(tooltipTimer.current)
  }

  useEffect(() => {
    const user = getCurrentUser()
    if (user) {
      setUserName(user.full_name)
      setInitial(user.full_name.charAt(0).toUpperCase())
      setRole(user.role)
    }
    apiFetch<Record<string,string>>("/api/settings")
      .then(d => { if (d?.company_name) setOrgName(d.company_name) })
      .catch(() => {})
    apiFetch<Me>("/api/auth/me")
      .then(d => {
        if (d?.tenant?.business_model) setBusinessModel(d.tenant.business_model)
        if (d?.role) setRole(d.role)
      })
      .catch(() => {})
  }, [])

  // Auto-expand section whose child is the current route
  useEffect(() => {
    const active = NAV.find(i => pathname === i.href || (i.href !== "/dashboard" && pathname.startsWith(i.href + "/")))
    if (active) {
      setCollapsedSections(prev => {
        if (!prev.has(active.section)) return prev
        const next = new Set(prev)
        next.delete(active.section)
        localStorage.setItem("sidebar-collapsed", JSON.stringify([...next]))
        return next
      })
    }
  }, [pathname])

  const isAdmin = role === "admin" || role === "owner"
  const visibleNav = NAV.filter(i =>
    (!i.forModel || i.forModel === businessModel) && (!i.adminOnly || isAdmin)
  )
  const SECTIONS = ALL_SECTIONS.filter(s => visibleNav.some(i => i.section === s))

  const logout = () => {
    if (!window.confirm("Log out?")) return
    removeAuthToken(); router.push("/login")
  }

  const go = (href: string) => {
    router.push(href)
    // On mobile / unpinned mode, close the drawer after navigation so the
    // user can see the page. Pinned-mode keeps it open as a static panel.
    if (!pinned) onClose()
  }

  // ── A single drawer component used at every size ──────────────────────────
  // - When closed: a thin gold "open menu" tab is shown on the left edge so
  //   the user can always re-open without going via the header hamburger.
  // - When open + pinned (md+): the drawer sits in the document flow at 260px
  //   wide, content sits next to it.
  // - When open + unpinned: the drawer overlays content with a backdrop.

  const drawerWidth = "w-[220px]"

  return (
    <>
      {/* Static placeholder so flex/layout reserves the sidebar width when
          pinned. The actual drawer below is fixed-positioned. */}
      {pinned && open && (
        <div className={`hidden md:block ${drawerWidth} shrink-0`} aria-hidden />
      )}

      {/* Backdrop — only when overlaying (mobile OR unpinned) */}
      {open && (
        <button
          aria-label="Close menu"
          onClick={onClose}
          className={cn(
            // Starts at top-12 (below the 48px header) so the hamburger button
            // remains clickable even while the sidebar is open in overlay mode.
            "fixed inset-x-0 bottom-0 top-12 z-40 bg-black/60 backdrop-blur-sm transition-opacity",
            pinned && "md:hidden"
          )}
        />
      )}

      {/* The drawer itself */}
      <aside
        className={cn(
          "fixed top-0 left-0 h-full bg-[#1a1814] border-r border-white/5 z-50 flex flex-col shadow-2xl",
          drawerWidth,
          "transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "-translate-x-full"
        )}
        aria-hidden={!open}
      >
        {/* Header row inside drawer */}
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-white/10 shrink-0">
          <button
            onClick={() => { router.push("/dashboard"); if (!pinned) onClose() }}
            className="w-8 h-8 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-sm hover:bg-[#d4af60] transition-colors"
            title={orgName}
          >
            {orgName.charAt(0)}
          </button>
          <span className="flex-1 font-serif text-white text-sm truncate font-semibold" title={orgName}>
            {orgName}
          </span>
          {/* Pin toggle — only meaningful on md+ */}
          <button
            onClick={onTogglePinned}
            title={pinned ? "Unpin sidebar" : "Pin sidebar open"}
            className="hidden md:inline-flex w-7 h-7 items-center justify-center rounded-md text-white/40 hover:text-[#ffd966] hover:bg-white/5 transition"
          >
            {pinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={onClose}
            title="Close menu"
            className="w-7 h-7 inline-flex items-center justify-center rounded-md text-white/40 hover:text-white hover:bg-white/5 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2 scrollbar-hide">
          {SECTIONS.map(section => {
            const collapsed = collapsedSections.has(section)
            const sectionItems = visibleNav.filter(i => i.section === section)
            const sectionActive = sectionItems.some(i =>
              pathname === i.href || (!HUB_HREFS.has(i.href) && i.href !== "/dashboard" && pathname.startsWith(i.href + "/"))
            )
            return (
              <div key={section} className="mb-1">
                {/* Section header — always a collapse toggle */}
                <button
                  onClick={() => toggleSection(section)}
                  onMouseEnter={(e) => openTooltip(section, e)}
                  onMouseLeave={closeTooltip}
                  className={cn(
                    "w-full flex items-center justify-between px-3 pt-2.5 pb-1",
                    "text-[9px] font-bold uppercase tracking-[0.15em]",
                    "hover:opacity-80 transition-opacity group",
                    SECTION_COLORS[section],
                    sectionActive && !collapsed && "opacity-100"
                  )}
                >
                  <span>{t(`section.${section}`, section)}</span>
                  <ChevronDown
                    className={cn(
                      "w-3 h-3 opacity-40 group-hover:opacity-70 transition-all duration-200",
                      collapsed && "-rotate-90"
                    )}
                  />
                </button>

                {/* Animated children via CSS grid trick */}
                <div className={cn(
                  "grid transition-all duration-200 ease-out",
                  collapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]"
                )}>
                  <div className="overflow-hidden">
                    {sectionItems.map(item => {
                      const active = pathname === item.href || (!HUB_HREFS.has(item.href) && item.href !== "/dashboard" && pathname.startsWith(item.href + "/"))
                      return (
                        <button
                          key={item.href}
                          onClick={() => go(item.href)}
                          className={cn(
                            "w-full text-left flex items-center gap-2 px-3 py-1.5 text-[12px] font-medium transition-all border-l-2",
                            active
                              ? "bg-[#b8943f]/15 text-[#ffd966] border-[#b8943f]"
                              : "text-white/60 hover:text-white hover:bg-white/5 border-transparent"
                          )}
                        >
                          <item.icon className="w-3.5 h-3.5 flex-shrink-0" />
                          <span className="truncate flex-1">{t(`nav.${item.label}`, item.label)}</span>
                          {active && <ChevronRight className="w-3.5 h-3.5 opacity-60 flex-shrink-0" />}
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>
            )
          })}
        </nav>

        {/* Footer: user + logout */}
        <div className="px-4 py-3 border-t border-white/10 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-xs flex-shrink-0">
              {userInitial}
            </div>
            <div className="min-w-0">
              <p className="text-white text-xs font-medium truncate">{userName}</p>
              <p className="text-white/40 text-[10px]">Admin</p>
            </div>
          </div>
          <button
            onClick={logout}
            title="Log out"
            className="w-7 h-7 inline-flex items-center justify-center rounded-md text-white/40 hover:text-red-400 hover:bg-white/5 transition"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </aside>

      {/* Section tooltip — fixed so it escapes the sidebar's overflow-y-auto */}
      {tooltip && (() => {
        const items = visibleNav.filter(i => i.section === tooltip.section)
        const color = SECTION_COLORS[tooltip.section] ?? "text-white/60"
        return (
          <div
            style={{ top: tooltip.y, left: 224 }}
            onMouseEnter={keepTooltip}
            onMouseLeave={closeTooltip}
            className="fixed z-[200] pointer-events-auto"
          >
            {/* arrow pointing left */}
            <div className="absolute left-0 top-3 -translate-x-full border-[6px] border-transparent border-r-[#2a2521]" />
            <div className="bg-[#2a2521] border border-white/10 rounded-lg shadow-2xl py-1.5 min-w-[180px] max-w-[220px]">
              <p className={cn("px-3 pb-1 text-[9px] font-bold uppercase tracking-[0.15em] border-b border-white/8 mb-1", color)}>
                {t(`section.${tooltip.section}`, tooltip.section)}
              </p>
              {items.map(item => (
                <button
                  key={item.href}
                  onClick={() => { go(item.href); setTooltip(null) }}
                  className="w-full text-left flex items-center gap-2 px-3 py-1.5 text-[12px] text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                >
                  <item.icon className="w-3 h-3 flex-shrink-0 opacity-60" />
                  <span className="truncate">{t(`nav.${item.label}`, item.label)}</span>
                </button>
              ))}
            </div>
          </div>
        )
      })()}
    </>
  )
}
