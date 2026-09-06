"use client"

import { useCallback, useEffect, useState } from "react"
import { useSearchParams, useRouter, usePathname } from "next/navigation"
import { useModules } from "@/context/ModuleContext"
import { apiFetch } from "@/lib/api"
import {
  HOME_PREF_KEY,
  type DashboardView,
  type HomePreference,
  hasOperationsHome,
  defaultViewForModel,
  operationsSubtitle,
} from "@/lib/dashboardHome"

const OPS_PATH = "/dashboard/operations"

function isOpsPath(pathname: string): boolean {
  return pathname === OPS_PATH || pathname.startsWith(`${OPS_PATH}/`)
}

/**
 * Dual-home preference: Financial | Operations (+ PRA via usePRAPortal).
 * Operations is a real route (`/dashboard/operations`) so it appears in
 * SubNav / sidebar / Ctrl+K — not only a tiny toggle on `/dashboard`.
 */
export function useHomeDashboard(): {
  view: DashboardView
  setView: (v: DashboardView) => void
  opsAvailable: boolean
  settled: boolean
  subtitle: string
  businessModel: string | undefined
} {
  const { installedModules, loading: modulesLoading } = useModules()
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()
  const [businessModel, setBusinessModel] = useState<string | undefined>(undefined)
  const [view, setViewState] = useState<DashboardView>("financial")
  const [settled, setSettled] = useState(false)

  const opsAvailable = hasOperationsHome(installedModules)

  useEffect(() => {
    apiFetch<{ tenant?: { business_model?: string } }>("/api/auth/me")
      .then(me => setBusinessModel(me?.tenant?.business_model))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (modulesLoading) return

    const onOpsPath = isOpsPath(pathname)
    const onDashHome = pathname === "/dashboard" || onOpsPath
    const q = searchParams.get("view")
    const stored = typeof window !== "undefined"
      ? (localStorage.getItem(HOME_PREF_KEY) as HomePreference | null)
      : null

    let next: DashboardView = "financial"
    let explicit = false
    if (onOpsPath) {
      next = "operations"
      explicit = true
    } else if (q === "operations" || q === "financial") {
      next = q
      explicit = true
    } else if (stored === "operations" || stored === "financial") {
      next = stored
    } else if (stored === "accounting" || stored === "pra") {
      next = "financial"
    } else {
      next = defaultViewForModel(businessModel)
    }

    if (next === "operations" && !opsAvailable) {
      next = "financial"
      explicit = false
    }
    setViewState(next)
    setSettled(true)

    if (explicit && typeof window !== "undefined") {
      localStorage.setItem(HOME_PREF_KEY, next)
    }

    if (!onDashHome) return

    if (next === "operations" && opsAvailable && !onOpsPath) {
      router.replace(OPS_PATH)
    } else if (next === "financial" && onOpsPath) {
      router.replace("/dashboard?view=financial")
    }
  }, [modulesLoading, searchParams, opsAvailable, businessModel, pathname, router])

  const setView = useCallback((v: DashboardView) => {
    const next = v === "operations" && !opsAvailable ? "financial" : v
    setViewState(next)
    localStorage.setItem(HOME_PREF_KEY, next)
    if (next === "operations") {
      router.replace(OPS_PATH)
    } else {
      router.replace("/dashboard?view=financial")
    }
  }, [opsAvailable, router])

  const subtitle = view === "operations"
    ? operationsSubtitle(installedModules, businessModel)
    : "Financial Overview"

  return { view, setView, opsAvailable, settled, subtitle, businessModel }
}
