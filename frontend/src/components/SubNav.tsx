"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import { SUB_NAV, getActiveSection } from "@/lib/nav"
import { useModules } from "@/context/ModuleContext"
import { getCurrentUser } from "@/lib/auth"

export default function SubNav() {
  const pathname             = usePathname()
  const { installedModules } = useModules()
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    const user = getCurrentUser()
    if (user) setIsAdmin(user.role === "admin" || user.role === "owner")
  }, [])

  const activeSection = getActiveSection(pathname)
  const items = (SUB_NAV[activeSection] ?? []).filter(item => {
    if (item.forModule && !installedModules.has(item.forModule)) return false
    if (item.adminOnly && !isAdmin) return false
    return true
  })

  return (
    <aside className="hidden md:flex w-[200px] flex-col bg-[var(--bg-card)] border-r border-[var(--border)] shrink-0 overflow-y-auto print:hidden">
      {activeSection && (
        <div className="px-4 pt-4 pb-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            {activeSection}
          </p>
        </div>
      )}
      <nav className="pb-4">
        {items.map(item => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/")
          const Icon   = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 py-[9px] text-[13px] transition-all duration-150 border-l-[3px]",
                active
                  ? "bg-[var(--primary-light)] border-[var(--primary)] text-[var(--text-primary)] font-semibold pl-[13px] pr-4"
                  : "border-transparent text-[var(--text-muted)] hover:bg-[var(--bg-page)] hover:text-[var(--text-primary)] hover:border-[var(--border)] pl-[13px] pr-4"
              )}
            >
              <Icon className="w-[14px] h-[14px] shrink-0 opacity-80" />
              <span className="truncate leading-none">{item.label}</span>
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
