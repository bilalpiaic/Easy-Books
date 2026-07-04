"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { X } from "lucide-react"
import { TOP_NAV, SUB_NAV, navVisible } from "@/lib/nav"
import { cn } from "@/lib/utils"
import { useModules } from "@/context/ModuleContext"
import { getCurrentUser } from "@/lib/auth"

interface Props {
  open: boolean
  onClose: () => void
}

export default function MoreDrawer({ open, onClose }: Props) {
  const pathname             = usePathname()
  const { installedModules } = useModules()
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    const user = getCurrentUser()
    if (user) setIsAdmin(user.role === "admin" || user.role === "owner")
  }, [])

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden print:hidden"
          onClick={onClose}
        />
      )}
      <div
        className={cn(
          "fixed bottom-0 inset-x-0 z-50 md:hidden print:hidden bg-[var(--bg-card)] border-t border-[var(--border)] rounded-t-2xl transition-transform duration-300",
          open ? "translate-y-0" : "translate-y-full"
        )}
        style={{ maxHeight: "80vh", overflowY: "auto" }}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <span className="text-sm font-bold text-[var(--text-primary)]">Menu</span>
          <button onClick={onClose} className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 space-y-4 pb-8">
          {TOP_NAV.map((section) => {
            const notInstalled = section.forModule && !installedModules.has(section.forModule)

            // Uninstalled module section — show as a single "Install" row
            if (notInstalled) {
              return (
                <div key={section.key}>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]/50 mb-2">
                    {section.label}
                  </p>
                  <Link
                    href="/apps"
                    onClick={onClose}
                    className="flex items-center justify-between px-3 py-2 rounded-lg text-sm text-[var(--text-muted)] hover:bg-[var(--bg-row-hover)] transition-colors"
                  >
                    <span className="opacity-60">Not installed</span>
                    <span className="text-[11px] text-[var(--primary)] font-semibold">+ Install</span>
                  </Link>
                </div>
              )
            }

            const items = (SUB_NAV[section.key] ?? []).filter(item => {
              if (!navVisible(item, installedModules)) return false
              if (item.adminOnly && !isAdmin) return false
              return true
            })
            if (!items.length) return null

            return (
              <div key={section.key}>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] mb-2">
                  {section.label}
                </p>
                <div className="space-y-1">
                  {items.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onClose}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                        pathname === item.href
                          ? "bg-[var(--primary-light)] text-[var(--primary)] font-semibold"
                          : "text-[var(--text-primary)] hover:bg-[var(--bg-row-hover)]"
                      )}
                    >
                      <item.icon className="w-4 h-4 shrink-0 opacity-70" />
                      {item.label}
                    </Link>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </>
  )
}
