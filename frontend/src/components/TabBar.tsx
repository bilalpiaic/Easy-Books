"use client"

import { useRef } from "react"
import { useRouter } from "next/navigation"
import { X, Home } from "lucide-react"
import { cn } from "@/lib/utils"
import { useTabs, type Tab } from "@/context/TabContext"

function TabItem({ tab, active, onClose }: {
  tab: Tab
  active: boolean
  onClose: (href: string) => void
}) {
  const router = useRouter()
  const isHome = tab.href === "/dashboard"

  return (
    <div
      className={cn(
        "group relative flex items-center gap-1.5 px-3 h-full shrink-0 max-w-[180px] min-w-[72px]",
        "border-r border-[#ddd8d0] cursor-pointer select-none",
        "transition-colors duration-100",
        active
          ? "bg-white text-[#1a1814] shadow-[inset_0_-2px_0_#b8943f]"
          : "bg-[#f0ede6] text-[#1a1814]/60 hover:bg-[#e8e4dc] hover:text-[#1a1814]"
      )}
      onClick={() => router.push(tab.href)}
      title={tab.title}
    >
      {isHome && <Home className="w-3 h-3 shrink-0 opacity-70" />}
      <span className="text-[11px] font-medium truncate flex-1 leading-none">
        {tab.title}
      </span>
      {!isHome && (
        <button
          onClick={e => { e.stopPropagation(); onClose(tab.href) }}
          className={cn(
            "w-4 h-4 shrink-0 flex items-center justify-center rounded",
            "opacity-0 group-hover:opacity-100 hover:bg-black/10 transition-opacity",
            active && "opacity-40 hover:opacity-100"
          )}
          title="Close tab"
        >
          <X className="w-2.5 h-2.5" />
        </button>
      )}
    </div>
  )
}

export default function TabBar() {
  const { tabs, activeHref, closeTab } = useTabs()
  const scrollRef = useRef<HTMLDivElement>(null)

  // Only render when there are 2+ tabs — a single tab is the normal single-page state
  if (tabs.length < 2) return null

  return (
    <div
      ref={scrollRef}
      className="hidden md:flex items-stretch h-[30px] shrink-0 overflow-x-auto bg-[#f0ede6] border-b border-[#ddd8d0] scrollbar-hide print:hidden"
    >
      {tabs.map(tab => (
        <TabItem
          key={tab.id}
          tab={tab}
          active={tab.href === activeHref}
          onClose={closeTab}
        />
      ))}
    </div>
  )
}
