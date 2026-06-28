"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import Link from "next/link"
import { X, Download } from "lucide-react"
import TopNav from "@/components/TopNav"
import SubNav from "@/components/SubNav"
import BottomNav from "@/components/BottomNav"
import MoreDrawer from "@/components/MoreDrawer"
import FAB from "@/components/FAB"
import TabBar from "@/components/TabBar"
import { isAuthenticated, getMustChangePwd, getCurrentUser } from "@/lib/auth"
import { SettingsProvider } from "@/context/SettingsContext"
import { PermissionProvider } from "@/context/PermissionContext"
import { ModuleProvider } from "@/context/ModuleContext"
import { OnboardingGuard } from "@/components/OnboardingGuard"
import { TabProvider } from "@/context/TabContext"
import NavBar from "@/components/NavBar"
import { BreadcrumbProvider } from "@/context/BreadcrumbContext"
import { resolveTitle } from "@/lib/navTitles"
import { apiFetch } from "@/lib/api"
import GlobalSearch from "@/components/GlobalSearch"

const DISMISS_KEY = "eb.update-banner-dismissed"

interface UpdateStatus {
  status: "up_to_date" | "update_available" | "unknown"
  local: string
  remote: string | null
  behind: boolean
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter()
  const pathname = usePathname()
  const [moreOpen, setMoreOpen] = useState(false)

  // ── Update banner ────────────────────────────────────────────────────────────
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null)
  const [bannerDismissed, setBannerDismissed] = useState(true) // hidden until checked
  const checkedRef = useRef(false)

  useEffect(() => {
    if (checkedRef.current) return
    checkedRef.current = true
    const user = getCurrentUser()
    if (!user || (user.role !== "admin" && user.role !== "owner")) return

    apiFetch<UpdateStatus>("/api/system/update/status")
      .then(s => {
        setUpdateStatus(s)
        if (s.status === "update_available") {
          const dismissed = localStorage.getItem(DISMISS_KEY)
          if (dismissed !== s.remote) setBannerDismissed(false)
        }
      })
      .catch(() => {/* silently ignore network errors */})
  }, [])

  // Auth gate
  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return }
    if (getMustChangePwd() && !pathname.startsWith("/profile")) {
      router.push("/profile?changePassword=1")
    }
  }, [router, pathname])

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

                  {/* Update available banner — admins/owners only, dismissible per-commit */}
                  {!bannerDismissed && updateStatus?.status === "update_available" && (
                    <div className="flex items-center justify-between gap-3 px-4 py-2 bg-[var(--primary)] text-white text-[13px] shrink-0 print:hidden">
                      <div className="flex items-center gap-2">
                        <Download className="w-3.5 h-3.5 shrink-0" />
                        <span>
                          New update available — commit{" "}
                          <span className="font-mono font-bold">{updateStatus.remote}</span>
                          {" "}(you have <span className="font-mono">{updateStatus.local}</span>).
                        </span>
                        <Link href="/settings?tab=updates"
                          className="underline underline-offset-2 font-semibold hover:opacity-80 transition-opacity whitespace-nowrap">
                          Update Now →
                        </Link>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          localStorage.setItem(DISMISS_KEY, updateStatus.remote ?? "")
                          setBannerDismissed(true)
                        }}
                        className="p-1 rounded hover:bg-white/20 transition-colors shrink-0"
                        aria-label="Dismiss update banner"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}

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
                  <BottomNav onMore={() => setMoreOpen(true)} />
                  <MoreDrawer open={moreOpen} onClose={() => setMoreOpen(false)} />
                  <FAB />
                  <GlobalSearch />
                </div>
              </TabProvider>
            </BreadcrumbProvider>
          </PermissionProvider>
        </OnboardingGuard>
      </ModuleProvider>
    </SettingsProvider>
  )
}
