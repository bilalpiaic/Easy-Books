"use client"

import { useEffect } from "react"
import { useRouter, usePathname } from "next/navigation"
import TopNav from "@/components/TopNav"
import SubNav from "@/components/SubNav"
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

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter()
  const pathname = usePathname()

  // Auth gate
  useEffect(() => {
    if (!isAuthenticated()) router.push("/login")
  }, [router])

  // Browser tab title
  useEffect(() => {
    document.title = `${resolveTitle(pathname)} — Easy-Books`
  }, [pathname])

  // Keyboard shortcut: press N (outside inputs) → open-new-modal event
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      ) return
      if (e.key === "n" || e.key === "N") {
        e.preventDefault()
        window.dispatchEvent(new CustomEvent("kbd:new"))
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  return (
    <SettingsProvider>
      <ModuleProvider>
        <OnboardingGuard>
          <PermissionProvider>
            <BreadcrumbProvider>
              <TabProvider>
                <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg-page)]">
                  {/* Fixed top navbar */}
                  <TopNav />
                  {/* Body: sub-nav + main content */}
                  <div className="flex flex-1 overflow-hidden">
                    <SubNav />
                    <main className="flex-1 flex flex-col overflow-hidden">
                      <TabBar />
                      <div className="flex-1 overflow-y-auto p-4 pb-20 md:pb-4">
                        <NavBar />
                        {children}
                      </div>
                    </main>
                  </div>
                  {/* Mobile bottom tab bar */}
                  <BottomNav />
                </div>
              </TabProvider>
            </BreadcrumbProvider>
          </PermissionProvider>
        </OnboardingGuard>
      </ModuleProvider>
    </SettingsProvider>
  )
}
