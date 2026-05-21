"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Sidebar from "@/components/Sidebar"
import Header from "@/components/Header"
import BottomNav from "@/components/BottomNav"
import { isAuthenticated } from "@/lib/auth"
import { SettingsProvider } from "@/context/SettingsContext"

const LS_KEY_PINNED = "eb_sidebar_pinned"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const [open, setOpen]     = useState(false)
  const [pinned, setPinned] = useState(false)

  // Auth gate + hydrate pinned preference from localStorage. Also auto-open
  // the drawer on first render if the screen is wide enough — so desktop
  // users see the menu by default.
  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login")
      return
    }
    const pinnedSaved = typeof window !== "undefined" && localStorage.getItem(LS_KEY_PINNED) === "1"
    const isWide      = typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches
    if (pinnedSaved) {
      setPinned(true)
      setOpen(true)
    } else if (isWide) {
      setOpen(true)
    }
  }, [router])

  const onOpen        = useCallback(() => setOpen(true), [])
  const onClose       = useCallback(() => setOpen(false), [])
  const onTogglePinned = useCallback(() => {
    setPinned(prev => {
      const next = !prev
      if (typeof window !== "undefined") {
        if (next) localStorage.setItem(LS_KEY_PINNED, "1")
        else localStorage.removeItem(LS_KEY_PINNED)
      }
      // Re-open after pinning so the change is visible right away
      if (next) setOpen(true)
      return next
    })
  }, [])

  return (
    <SettingsProvider>
      <div className="flex h-screen overflow-hidden bg-[#f6f3ee]">
        <Sidebar
          open={open}
          onClose={onClose}
          pinned={pinned}
          onTogglePinned={onTogglePinned}
        />
        <div className="flex-1 flex flex-col min-w-0">
          <Header onOpenMenu={onOpen} />
          <main className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 pb-20 md:pb-6 w-full">
            {/* No max-width constraint — pages decide their own width.
                Tables/dashboards fill the viewport; narrative content can
                wrap itself with `max-w-prose` where readability matters. */}
            {children}
          </main>
        </div>
        <BottomNav onMore={onOpen} />
      </div>
    </SettingsProvider>
  )
}
