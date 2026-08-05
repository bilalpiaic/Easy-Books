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

/**
 * Dual-home preference: Financial | Operations (+ PRA via usePRAPortal).
 * Syncs `?view=` on /dashboard with localStorage `eb.home_dashboard`.
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

    const q = searchParams.get("view")
    const stored = localStorage.getItem(HOME_PREF_KEY) as HomePreference | null

    let next: DashboardView = "financial"
    if (q === "operations" || q === "financial") {
      next = q
    } else if (stored === "operations" || stored === "financial") {
      next = stored
    } else if (stored === "accounting" || stored === "pra") {
      // PRA / legacy accounting → financial home (portal handled separately)
      next = "financial"
    } else {
      next = defaultViewForModel(businessModel)
    }

    if (next === "operations" && !opsAvailable) next = "financial"
    setViewState(next)
    setSettled(true)
  }, [modulesLoading, searchParams, opsAvailable, businessModel])

  const setView = useCallback((v: DashboardView) => {
    const next = v === "operations" && !opsAvailable ? "financial" : v
    setViewState(next)
    localStorage.setItem(HOME_PREF_KEY, next)
    // Keep PRA legacy key coherent when leaving ops/financial (don't clear pra)
    const params = new URLSearchParams(searchParams.toString())
    params.set("view", next)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }, [opsAvailable, searchParams, router, pathname])

  const subtitle = view === "operations"
    ? operationsSubtitle(installedModules, businessModel)
    : "Financial Overview"

  return { view, setView, opsAvailable, settled, subtitle, businessModel }
}
