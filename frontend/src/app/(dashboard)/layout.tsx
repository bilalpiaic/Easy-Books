"use client"

import { useEffect, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import TopNav from "@/components/TopNav"
import SubNav from "@/components/SubNav"
import BottomNav from "@/components/BottomNav"
import MoreDrawer from "@/components/MoreDrawer"
import FAB from "@/components/FAB"
import TabBar from "@/components/TabBar"
import { isAuthenticated, getMustChangePwd, getMustSetupTotp, reconcileAuthOnLoad } from "@/lib/auth"
import { SettingsProvider } from "@/context/SettingsContext"
import { PermissionProvider } from "@/context/PermissionContext"
import { ModuleProvider } from "@/context/ModuleContext"
import { MessageProvider } from "@/context/MessageContext"
import { OnboardingGuard } from "@/components/OnboardingGuard"
import { TabProvider } from "@/context/TabContext"
import NavBar from "@/components/NavBar"
import { BreadcrumbProvider } from "@/context/BreadcrumbContext"
import { resolveTitle } from "@/lib/navTitles"
import GlobalSearch from "@/components/GlobalSearch"
import AIChatButton from "@/components/AIChatButton"
import CalculatorButton from "@/components/CalculatorButton"
import OfflineBanner from "@/components/OfflineBanner"
import CapacitorPush from "@/components/CapacitorPush"
import QuotaBanner from "@/components/QuotaBanner"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter()
  const pathname = usePathname()
  const [moreOpen, setMoreOpen] = useState(false)

  // Auth gate — cold start / post-update have no session marker → login
  useEffect(() => {
    reconcileAuthOnLoad()
    if (!isAuthenticated()) { router.replace("/login"); return }
    if (getMustChangePwd() && !pathname.startsWith("/profile")) {
      router.replace("/profile?changePassword=1")
      return
    }
    if (getMustSetupTotp() && !pathname.startsWith("/profile")) {
      router.replace("/profile?setup2fa=1")
    }
  }, [router, pathname])

  // Browser tab title
  useEffect(() => {
    document.title = `${resolveTitle(pathname)} — Easy-Books`
  }, [pathname])

  // Keyboard shortcut: N → open-new-modal
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" || target.isContentEditable) return
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
        <MessageProvider>
        <OnboardingGuard>
          <PermissionProvider>
            <BreadcrumbProvider>
              <TabProvider>
                <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg-page)]">
                  <OfflineBanner />
                  <CapacitorPush />
                  <QuotaBanner />
                  <TopNav />

                  <div className="flex flex-1 overflow-hidden">
                    <SubNav />
                    <main className="flex-1 flex flex-col overflow-hidden">
                      <TabBar />
                      <div className="flex-1 overflow-y-auto p-2 pb-20 md:p-4 md:pb-4">
                        <NavBar />
                        {children}
                      </div>
                    </main>
                  </div>

                  <BottomNav onMore={() => setMoreOpen(true)} />
                  <MoreDrawer open={moreOpen} onClose={() => setMoreOpen(false)} />
                  <FAB />
                  <AIChatButton />
                  <CalculatorButton />
                  <GlobalSearch />
                </div>
              </TabProvider>
            </BreadcrumbProvider>
          </PermissionProvider>
        </OnboardingGuard>
        </MessageProvider>
      </ModuleProvider>
    </SettingsProvider>
  )
}
