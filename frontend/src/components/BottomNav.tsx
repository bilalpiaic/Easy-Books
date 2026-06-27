"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, FileSignature, Receipt, BarChart2, MoreHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"
import { getActiveSection } from "@/lib/nav"

const TABS = [
  { label: "Home",      href: "/dashboard",    icon: LayoutDashboard, section: "dashboard" },
  { label: "Sales",     href: "/customers",    icon: FileSignature,   section: "sales" },
  { label: "Purchases", href: "/vendors",      icon: Receipt,         section: "purchases" },
  { label: "Reports",   href: "/trial-balance",icon: BarChart2,       section: "reports" },
]

export default function BottomNav() {
  const pathname      = usePathname()
  const activeSection = getActiveSection(pathname)

  return (
    <nav className="bottom-nav md:hidden fixed bottom-0 inset-x-0 z-40 bg-[var(--bg-card)] border-t border-[var(--border)] flex items-stretch">
      {TABS.map(({ label, href, icon: Icon, section }) => {
        const active = activeSection === section
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-bold uppercase tracking-widest transition-colors",
              active
                ? "text-[var(--primary)]"
                : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            )}
          >
            <Icon className="w-5 h-5" />
            {label}
          </Link>
        )
      })}
      {/* More — placeholder until Phase 4 mobile drawer */}
      <Link
        href="/dashboard"
        className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
      >
        <MoreHorizontal className="w-5 h-5" />
        More
      </Link>
    </nav>
  )
}
