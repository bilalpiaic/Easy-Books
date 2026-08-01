"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import { CheckCircle } from "lucide-react"
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
import { MessageProvider } from "@/context/MessageContext"
import { OnboardingGuard } from "@/components/OnboardingGuard"
import { TabProvider } from "@/context/TabContext"
import NavBar from "@/components/NavBar"
import { BreadcrumbProvider } from "@/context/BreadcrumbContext"
import { resolveTitle } from "@/lib/navTitles"
import { apiFetch } from "@/lib/api"
import GlobalSearch from "@/components/GlobalSearch"
import UpdateAvailablePopup from "@/components/UpdateAvailablePopup"
import UpdateProgressScreen from "@/components/UpdateProgressScreen"
import AIChatButton from "@/components/AIChatButton"
import CalculatorButton from "@/components/CalculatorButton"
import OfflineBanner from "@/components/OfflineBanner"

const SKIP_KEY = "eb.update-skip"     // persisted per remote SHA
const SESSION_LATER_KEY = "eb.update-later-session" // session-only dismiss

interface UpdateStatus {
  status: "up_to_date" | "update_available" | "unknown"
  local:  string
  remote: string | null
  behind: boolean
}

interface JustUpdated { from: string; to: string; at: string }

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter()
  const pathname = usePathname()
  const [moreOpen, setMoreOpen] = useState(false)

  // ── Update popup ─────────────────────────────────────────────────────────────
  const [updateStatus,  setUpdateStatus]  = useState<UpdateStatus | null>(null)
  const [showPopup,     setShowPopup]     = useState(false)
  const [showProgress,  setShowProgress]  = useState(false)
  const [justUpdated,   setJustUpdated]   = useState<JustUpdated | null>(null)
  const [showToast,     setShowToast]     = useState(false)
  const checkedRef = useRef(false)

  // Check for post-update greeting (set before the page reload)
  useEffect(() => {
    const raw = localStorage.getItem("eb.just-updated")
    if (raw) {
      try {
        const data = JSON.parse(raw) as JustUpdated
        setJustUpdated(data)
        setShowToast(true)
        localStorage.removeItem("eb.just-updated")
        // Auto-dismiss toast after 8 s
        setTimeout(() => setShowToast(false), 8_000)
      } catch { /* corrupt entry */ }
    }
  }, [])

  // Auto-check on every mount (= every login/page load for admin/owner)
  useEffect(() => {
    if (checkedRef.current) return
    checkedRef.current = true

    const user = getCurrentUser()
    if (!user || (user.role !== "admin" && user.role !== "owner")) return

    apiFetch<UpdateStatus>("/api/system/update/status")
      .then(s => {
        setUpdateStatus(s)
        if (s.status === "update_available" && s.remote) {
          const skipRemote = localStorage.getItem(SKIP_KEY)
          const laterThis  = sessionStorage.getItem(SESSION_LATER_KEY)
          // Show popup unless user already skipped this SHA or said "later" this session
          if (skipRemote !== s.remote && !laterThis) {
            setShowPopup(true)
          }
        }
      })
      .catch(() => { /* silently ignore — never block the app */ })
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

  // ── Popup handlers ────────────────────────────────────────────────────────────
  const handleUpdateNow = () => {
    setShowPopup(false)
    setShowProgress(true)
  }

  const handleLater = () => {
    // Dismiss only for this session
    sessionStorage.setItem(SESSION_LATER_KEY, "1")
    setShowPopup(false)
  }

  const handleSkip = () => {
    // Dismiss permanently for this remote SHA
    if (updateStatus?.remote) {
      localStorage.setItem(SKIP_KEY, updateStatus.remote)
    }
    setShowPopup(false)
  }

  // ── Render ────────────────────────────────────────────────────────────────────
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
                  <TopNav />

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

                  <BottomNav onMore={() => setMoreOpen(true)} />
                  <MoreDrawer open={moreOpen} onClose={() => setMoreOpen(false)} />
                  <FAB />
                  <AIChatButton />
                  <CalculatorButton />
                  <GlobalSearch />
                </div>

                {/* Update available popup (shown after login check) */}
                {showPopup && updateStatus?.remote && (
                  <UpdateAvailablePopup
                    local={updateStatus.local}
                    remote={updateStatus.remote}
                    onUpdate={handleUpdateNow}
                    onLater={handleLater}
                    onSkip={handleSkip}
                  />
                )}

                {/* Full-page update animation */}
                {showProgress && (
                  <UpdateProgressScreen onClose={() => setShowProgress(false)} />
                )}

                {/* Post-update congratulations toast */}
                {showToast && justUpdated && (
                  <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[800] flex items-center gap-3 bg-[var(--bg-card)] border border-[var(--border)] shadow-2xl rounded-2xl px-5 py-3.5 animate-in slide-in-from-bottom-4 duration-500">
                    <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                      <CheckCircle className="w-4 h-4 text-green-600" />
                    </div>
                    <div>
                      <p className="text-[13px] font-semibold text-[var(--text-primary)]">
                        Updated successfully!
                      </p>
                      <p className="text-[11px] text-[var(--text-muted)]">
                        <span className="font-mono">{justUpdated.from}</span>
                        {" → "}
                        <span className="font-mono font-bold text-[var(--primary)]">{justUpdated.to}</span>
                        {" · Enjoy the new features"}
                      </p>
                    </div>
                    <button onClick={() => setShowToast(false)}
                      className="ml-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] text-lg leading-none transition-colors"
                      aria-label="Dismiss">×</button>
                  </div>
                )}
              </TabProvider>
            </BreadcrumbProvider>
          </PermissionProvider>
        </OnboardingGuard>
        </MessageProvider>
      </ModuleProvider>
    </SettingsProvider>
  )
}
