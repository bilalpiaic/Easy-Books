"use client"

import {
  createContext, useCallback, useContext, useEffect, useRef, useState,
} from "react"
import { usePathname, useRouter } from "next/navigation"
import { resolveTitle } from "@/lib/navTitles"

export interface Tab {
  id: string      // unique key — same as href for deduplication
  href: string
  title: string
}

interface TabContextValue {
  tabs: Tab[]
  activeHref: string
  closeTab: (href: string) => void
}

const HOME: Tab = { id: "/dashboard", href: "/dashboard", title: "Home" }
const MAX_TABS = 12

const TabCtx = createContext<TabContextValue>({
  tabs: [HOME],
  activeHref: "/dashboard",
  closeTab: () => {},
})

export function TabProvider({ children }: { children: React.ReactNode }) {
  const pathname    = usePathname() ?? "/dashboard"
  const router      = useRouter()
  const [tabs, setTabs] = useState<Tab[]>([HOME])

  // Track the previous active href so we can find a good fallback on close
  const prevHref = useRef<string>(pathname)
  useEffect(() => { prevHref.current = pathname }, [pathname])

  // Auto-register / focus a tab whenever the route changes
  useEffect(() => {
    if (!pathname) return
    const title = resolveTitle(pathname)

    setTabs(prev => {
      const exists = prev.findIndex(t => t.href === pathname)
      if (exists !== -1) {
        // Already open — refresh the title in case it was a placeholder
        return prev.map((t, i) => i === exists ? { ...t, title } : t)
      }
      const next: Tab[] = [...prev, { id: pathname, href: pathname, title }]
      // Evict oldest non-home tab when over the limit
      if (next.length > MAX_TABS) {
        const firstNonHome = next.findIndex(t => t.href !== HOME.href)
        if (firstNonHome !== -1) next.splice(firstNonHome, 1)
      }
      return next
    })
  }, [pathname])

  const closeTab = useCallback(
    (href: string) => {
      if (href === HOME.href) return   // Home is permanent

      setTabs(prev => {
        const idx = prev.findIndex(t => t.href === href)
        const next = prev.filter(t => t.href !== href)
        const safe = next.length > 0 ? next : [HOME]

        // Navigate away only if we're closing the currently active tab
        if (href === pathname) {
          const fallback = prev[idx - 1] ?? prev[idx + 1] ?? HOME
          // Use setTimeout so the state update fires before navigation
          setTimeout(() => router.push(fallback.href), 0)
        }

        return safe
      })
    },
    [pathname, router],
  )

  return (
    <TabCtx.Provider value={{ tabs, activeHref: pathname, closeTab }}>
      {children}
    </TabCtx.Provider>
  )
}

export const useTabs = () => useContext(TabCtx)
