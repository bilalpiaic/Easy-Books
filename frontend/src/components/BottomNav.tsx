"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, FileSignature, PlusCircle, Receipt, MoreHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"

interface Props {
  onMore: () => void
}

const tabs = [
  { label: "Home",     href: "/dashboard",  icon: LayoutDashboard },
  { label: "Invoices", href: "/invoices",   icon: FileSignature },
  { label: "Entry",    href: "/entry",      icon: PlusCircle },
  { label: "Bills",    href: "/bills",      icon: Receipt },
]

export default function BottomNav({ onMore }: Props) {
  const pathname = usePathname()

  return (
    <nav className="bottom-nav md:hidden fixed bottom-0 inset-x-0 z-40 bg-[#1a1814] border-t border-white/10 flex items-stretch">
      {tabs.map(({ label, href, icon: Icon }) => {
        const active = pathname === href
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-bold uppercase tracking-widest transition-colors",
              active ? "text-[#ffd966]" : "text-white/50 hover:text-white/80"
            )}
          >
            <Icon className={cn("w-5 h-5", active && "drop-shadow-[0_0_6px_rgba(255,217,102,0.6)]")} />
            {label}
          </Link>
        )
      })}
      <button
        onClick={onMore}
        className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-bold uppercase tracking-widest text-white/50 hover:text-white/80 transition-colors"
      >
        <MoreHorizontal className="w-5 h-5" />
        More
      </button>
    </nav>
  )
}
