"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { SUB_NAV, getActiveSection } from "@/lib/nav"
import { useModules } from "@/context/ModuleContext"
import { getCurrentUser } from "@/lib/auth"

const PINNED_KEY  = "eb.subnav.pinned"
const COLLAPSED_W = 52
const EXPANDED_W  = 200

export default function SubNav() {
  const pathname             = usePathname()
  const { installedModules } = useModules()

  const [isAdmin, setIsAdmin] = useState(false)
  const [pinned,  setPinned]  = useState(false)
  const [hovered, setHovered] = useState(false)

  useEffect(() => {
    const user = getCurrentUser()
    if (user) setIsAdmin(user.role === "admin" || user.role === "owner")
    setPinned(localStorage.getItem(PINNED_KEY) === "1")
  }, [])

  const activeSection = getActiveSection(pathname)
  const items = (SUB_NAV[activeSection] ?? []).filter(item => {
    if (item.forModule && !installedModules.has(item.forModule)) return false
    if (item.adminOnly && !isAdmin) return false
    return true
  })

  // No sub-items for this section → render nothing
  if (!items.length) return null

  const expanded = pinned || hovered

  const togglePin = () => {
    const next = !pinned
    setPinned(next)
    localStorage.setItem(PINNED_KEY, next ? "1" : "0")
  }

  return (
    <aside
      className="hidden md:flex flex-col bg-[var(--bg-card)] border-r border-[var(--border)] shrink-0 overflow-hidden print:hidden"
      style={{
        width: expanded ? EXPANDED_W : COLLAPSED_W,
        transition: "width 180ms ease-in-out",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Section label — fades in when expanded */}
      <div className="h-10 flex items-end pb-1.5 overflow-hidden">
        <p
          className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)] whitespace-nowrap pl-4"
          style={{
            opacity:   expanded ? 1 : 0,
            transform: expanded ? "translateX(0)" : "translateX(-6px)",
            transition: "opacity 140ms ease-in-out, transform 140ms ease-in-out",
          }}>
          {activeSection}
        </p>
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden pb-2">
        {items.map(item => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/")
          const Icon   = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              title={!expanded ? item.label : undefined}
              className={cn(
                "flex items-center text-[13px] transition-colors duration-150 border-l-[3px] py-[9px]",
                expanded ? "gap-2.5 pl-[13px] pr-4" : "justify-center px-0",
                active
                  ? "bg-[var(--primary-light)] border-[var(--primary)] text-[var(--text-primary)] font-semibold"
                  : "border-transparent text-[var(--text-muted)] hover:bg-[var(--bg-page)] hover:text-[var(--text-primary)] hover:border-[var(--border)]"
              )}
            >
              <Icon className={cn(
                "shrink-0 opacity-80",
                expanded ? "w-[14px] h-[14px]" : "w-[16px] h-[16px]"
              )} />
              {/* Label: max-width animation keeps layout stable during transition */}
              <span
                className="truncate leading-none whitespace-nowrap"
                style={{
                  maxWidth:   expanded ? 140 : 0,
                  opacity:    expanded ? 1 : 0,
                  transition: "max-width 180ms ease-in-out, opacity 120ms ease-in-out",
                  overflow:   "hidden",
                  display:    "inline-block",
                }}>
                {item.label}
              </span>
            </Link>
          )
        })}
      </nav>

      {/* Pin / unpin toggle at the bottom */}
      <div
        className="border-t border-[var(--border)] py-2.5 flex"
        style={{ justifyContent: expanded ? "flex-end" : "center", paddingRight: expanded ? 10 : 0 }}>
        <button
          type="button"
          onClick={togglePin}
          title={pinned ? "Unpin sidebar" : "Pin sidebar open"}
          className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-page)] transition-colors"
        >
          {pinned
            ? <ChevronLeft  className="w-3.5 h-3.5" />
            : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
      </div>
    </aside>
  )
}
