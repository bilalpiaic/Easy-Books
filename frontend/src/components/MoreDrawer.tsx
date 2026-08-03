"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { ChevronDown, X } from "lucide-react"
import { mobileMoreSections, MOBILE_MORE_SECTION_ORDER, SUB_NAV, navVisible, getActiveSection, getSectionHref } from "@/lib/nav"
import { cn } from "@/lib/utils"
import { useModules } from "@/context/ModuleContext"
import { getCurrentUser } from "@/lib/auth"

interface Props {
  open: boolean
  onClose: () => void
}

const STORAGE_KEY = "eb.more.collapsed"

/** Sections left expanded on first visit (before any user toggle). */
const DEFAULT_EXPANDED = new Set([
  "dashboard",
  "accounting",
  "reports",
  "banking",
])

const MOBILE_MORE_KEYS_EXCEPT_DEFAULT = MOBILE_MORE_SECTION_ORDER.filter(
  k => !DEFAULT_EXPANDED.has(k)
)

function loadCollapsed(sectionKeys: string[]): Set<string> {
  if (typeof window === "undefined") return new Set()
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const arr = JSON.parse(raw) as string[]
      return new Set(Array.isArray(arr) ? arr : [])
    }
  } catch { /* fall through */ }
  // First visit: collapse everything that is not a daily-use priority section
  return new Set(sectionKeys.filter(k => !DEFAULT_EXPANDED.has(k)))
}

export default function MoreDrawer({ open, onClose }: Props) {
  const pathname             = usePathname()
  const { installedModules } = useModules()
  const [isAdmin, setIsAdmin] = useState(false)
  const sections = useMemo(() => mobileMoreSections(), [])
  // SSR-safe default: priority sections expanded; localStorage applied after mount
  const [collapsed, setCollapsed] = useState<Set<string>>(
    () => new Set(MOBILE_MORE_KEYS_EXCEPT_DEFAULT)
  )

  const activeKey = getActiveSection(pathname, installedModules)

  useEffect(() => {
    const user = getCurrentUser()
    if (user) setIsAdmin(user.role === "admin" || user.role === "owner")
  }, [])

  useEffect(() => {
    setCollapsed(loadCollapsed(sections.map(s => s.key)))
  }, [sections])

  // When the drawer opens, ensure the active route's section is expanded
  useEffect(() => {
    if (!open || !activeKey) return
    setCollapsed(prev => {
      if (!prev.has(activeKey)) return prev
      const next = new Set(prev)
      next.delete(activeKey)
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]))
      return next
    })
  }, [open, activeKey])

  const toggle = (key: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]))
      return next
    })
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden print:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Menu"
        className={cn(
          "fixed bottom-0 inset-x-0 z-50 md:hidden print:hidden bg-[var(--bg-card)] border-t border-[var(--border)] rounded-t-2xl transition-transform duration-300 flex flex-col",
          open ? "translate-y-0" : "translate-y-full pointer-events-none"
        )}
        style={{ maxHeight: "min(85dvh, 85vh)" }}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] shrink-0">
          <div className="flex flex-col">
            <span className="text-sm font-bold text-[var(--text-primary)]">Menu</span>
            <span className="text-[10px] text-[var(--text-muted)]">Tap a heading to expand</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 -mr-1 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-row-hover)]"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="overflow-y-auto overscroll-contain px-2 py-2 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
          {sections.map((section) => {
            const notInstalled = section.forModule && !installedModules.has(section.forModule)
            const isActiveSection = activeKey === section.key
            const isCollapsed = collapsed.has(section.key) && !notInstalled

            if (notInstalled) {
              return (
                <div key={section.key} className="mb-1">
                  <div className="flex items-center justify-between px-3 py-2.5">
                    <span className="text-[11px] font-bold uppercase tracking-widest text-[var(--text-muted)]/60">
                      {section.shortLabel ?? section.label}
                    </span>
                    <Link
                      href="/apps"
                      onClick={onClose}
                      className="text-[11px] font-semibold text-[var(--primary)] px-2 py-1 rounded-md hover:bg-[var(--primary-light)]"
                    >
                      + Install
                    </Link>
                  </div>
                </div>
              )
            }

            const items = (SUB_NAV[section.key] ?? []).filter(item => {
              if (!navVisible(item, installedModules)) return false
              if (item.adminOnly && !isAdmin) return false
              return true
            })
            if (!items.length) return null

            const overviewHref = getSectionHref(section.key)

            return (
              <div key={section.key} className="mb-0.5">
                <button
                  type="button"
                  onClick={() => toggle(section.key)}
                  aria-expanded={!isCollapsed}
                  className={cn(
                    "w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl text-left transition-colors",
                    isActiveSection
                      ? "bg-[var(--primary-light)]/60 text-[var(--primary)]"
                      : "text-[var(--text-primary)] hover:bg-[var(--bg-row-hover)]"
                  )}
                >
                  <span className="text-[11px] font-bold uppercase tracking-widest">
                    {section.shortLabel ?? section.label}
                  </span>
                  <ChevronDown
                    className={cn(
                      "w-4 h-4 shrink-0 opacity-50 transition-transform duration-200",
                      isCollapsed && "-rotate-90"
                    )}
                  />
                </button>

                <div
                  className={cn(
                    "grid transition-all duration-200 ease-out",
                    isCollapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]"
                  )}
                >
                  <div className="overflow-hidden">
                    <div className="pb-2 pt-0.5 space-y-0.5 pl-1">
                      {/* Section hub shortcut when it differs from the first child */}
                      {overviewHref && !items.some(i => i.href === overviewHref) && (
                        <Link
                          href={overviewHref}
                          onClick={onClose}
                          className={cn(
                            "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                            pathname === overviewHref
                              ? "bg-[var(--primary-light)] text-[var(--primary)] font-semibold"
                              : "text-[var(--text-muted)] hover:bg-[var(--bg-row-hover)] hover:text-[var(--text-primary)]"
                          )}
                        >
                          Overview
                        </Link>
                      )}
                      {items.map((item) => (
                        <Link
                          key={item.href}
                          href={item.href}
                          onClick={onClose}
                          className={cn(
                            "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors min-h-11",
                            pathname === item.href || pathname.startsWith(item.href + "/")
                              ? "bg-[var(--primary-light)] text-[var(--primary)] font-semibold"
                              : "text-[var(--text-primary)] hover:bg-[var(--bg-row-hover)]"
                          )}
                        >
                          <item.icon className="w-4 h-4 shrink-0 opacity-70" />
                          <span className="truncate">{item.label}</span>
                        </Link>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </>
  )
}
