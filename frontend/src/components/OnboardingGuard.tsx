"use client"
import { useEffect } from "react"
import { useRouter, usePathname } from "next/navigation"
import { useModules } from "@/context/ModuleContext"
import { getCurrentUser } from "@/lib/auth"

/**
 * Redirects fresh accounts (only "base" installed, never onboarded) to /onboarding.
 * Per-user flag stored in localStorage so users who intentionally keep only base
 * are not redirected again after they dismiss onboarding.
 */
export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const { installedModules, loading } = useModules()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (loading) return
    if (pathname === "/onboarding") return  // already there

    const user = getCurrentUser()
    if (!user) return

    const flagKey = `eb.onboarded.${user.email}`
    if (localStorage.getItem(flagKey)) return

    const onlyBase = installedModules.size === 1 && installedModules.has("base")
    if (onlyBase) router.replace("/onboarding")
  }, [loading, installedModules, pathname, router])

  return <>{children}</>
}
