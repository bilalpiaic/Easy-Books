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
      <nav className="py-3">
        {items.map(item => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/")
          const Icon   = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 py-[7px] text-[13px] transition-colors border-l-[3px]",
                active
                  ? "bg-[var(--primary-light)] border-[var(--primary)] text-[var(--text-primary)] font-semibold pl-[13px] pr-4"
                  : "border-transparent text-[var(--text-muted)] hover:bg-[var(--bg-page)] hover:text-[var(--text-primary)] pl-[13px] pr-4"
              )}
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{item.label}</span>
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
