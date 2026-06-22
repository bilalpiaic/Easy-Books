"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import Sidebar from "@/components/Sidebar"
import Header from "@/components/Header"
import BottomNav from "@/components/BottomNav"
import TabBar from "@/components/TabBar"
import { isAuthenticated } from "@/lib/auth"
import { SettingsProvider } from "@/context/SettingsContext"
import { PermissionProvider } from "@/context/PermissionContext"
import { ModuleProvider } from "@/context/ModuleContext"
import { OnboardingGuard } from "@/components/OnboardingGuard"
import { TabProvider } from "@/context/TabContext"
import NavBar from "@/components/NavBar"
import { BreadcrumbProvider } from "@/context/BreadcrumbContext"
import { resolveTitle } from "@/lib/navTitles"
import { useTranslation } from "react-i18next"

const LS_KEY_PINNED = "eb_sidebar_pinned"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { t } = useTranslation()

  const router   = useRouter()
  const pathname = usePathname()
  const [open, setOpen]     = useState(false)
  const [pinned, setPinned] = useState(false)

  // Auth gate + hydrate pinned preference from localStorage.
  // "1" = explicitly pinned, "0" = explicitly unpinned, null = no preference.
  // No preference on a wide screen → auto-pin (desktop default). Explicit "0"
  // (user unpinned) is respected so we don't fight their preference.
  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login")
      return
    }
    const pref = typeof window !== "undefined" ? localStorage.getItem(LS_KEY_PINNED) : null
    if (pref === "1") {
      setPinned(true)
      setOpen(true)
    }
    // Default: collapsed — user opens/pins when they choose
  }, [router])

  // Browser tab title — use the shared resolver
  useEffect(() => {
    document.title = `${resolveTitle(pathname)} — Easy-Books`
  }, [pathname])

  // Keyboard shortcut: press N (outside inputs) → open-new-modal event
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable) return
      if (e.key === "n" || e.key === "N") {
        e.preventDefault()
        window.dispatchEvent(new CustomEvent("kbd:new"))
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  const onOpen        = useCallback(() => setOpen(true), [])
  const onClose       = useCallback(() => setOpen(false), [])
  const onTogglePinned = useCallback(() => {
    setPinned(prev => {
      const next = !prev
      if (typeof window !== "undefined") {
        // Save "1" (pinned) or "0" (explicitly unpinned) so auto-pin on wide
        // screens doesn't re-pin after the user has chosen to unpin.
        localStorage.setItem(LS_KEY_PINNED, next ? "1" : "0")
      }
      if (next) setOpen(true)
      return next
    })
  }, [])

  return (
    <SettingsProvider>
      <ModuleProvider>
      <OnboardingGuard>
      <PermissionProvider>
      <BreadcrumbProvider>
      <TabProvider>
        <div className="flex h-screen overflow-hidden bg-[#f6f3ee]">
          <Sidebar
            open={open}
            onClose={onClose}
            pinned={pinned}
            onTogglePinned={onTogglePinned}
          />
          <div className="flex-1 flex flex-col min-w-0">
            <Header onOpenMenu={onOpen} />
            <TabBar />
            <main className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 pb-20 md:pb-6 w-full">
              {/* No max-width constraint — pages decide their own width. */}
              <NavBar />
              {children}
            </main>
          </div>
          <BottomNav onMore={onOpen} />
        </div>
      </TabProvider>
      </BreadcrumbProvider>
      </PermissionProvider>
      </OnboardingGuard>
      </ModuleProvider>
    </SettingsProvider>
  )
}
