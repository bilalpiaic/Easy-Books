import { useState, useEffect, useCallback } from "react"
import { getCurrentUser } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"
import { useModules } from "@/context/ModuleContext"
import { HOME_PREF_KEY } from "@/lib/addonPacks"

const LS_PORTAL = "eb.pra_portal_mode"

/**
 * PRA portal / home mode.
 *
 * Requires the `pra` add-on installed. `pra_enabled` remains the compliance
 * API switch (set in Settings once the module is on).
 *
 * Preference `eb.home_dashboard` = `pra` | `accounting` drives login landing.
 * `eb.pra_portal_mode` keeps slim portal nav when on the PRA Sales home.
 */
export function usePRAPortal(): {
  isPortal: boolean
  canToggle: boolean
  togglePortal: () => void
  settled: boolean
  praModuleInstalled: boolean
} {
  const { settings } = useSettings()
  const { installedModules, loading: modulesLoading } = useModules()
  const user = getCurrentUser()
  const role = user?.role ?? "viewer"
  const praModuleInstalled = installedModules.has("pra")
  const isPRAEnabled = settings.pra_enabled === "true" || praModuleInstalled
  const isAdminOrOwner = role === "admin" || role === "owner"

  const [portalOn, setPortalOn] = useState(false)
  const [settled, setSettled] = useState(false)

  useEffect(() => {
    if (modulesLoading) return
    if (!praModuleInstalled) {
      setPortalOn(false)
      setSettled(true)
      return
    }
    const home = localStorage.getItem(HOME_PREF_KEY)
    const legacy = localStorage.getItem(LS_PORTAL)
    // Prefer explicit home preference; fall back to legacy portal flag;
    // default non-admins to PRA Sales when module is installed.
    if (home === "pra" || (!home && legacy === "1") || (!home && legacy === null && !isAdminOrOwner)) {
      setPortalOn(true)
    } else {
      setPortalOn(false)
    }
    setSettled(true)
  }, [praModuleInstalled, modulesLoading, isAdminOrOwner])

  const togglePortal = useCallback(() => {
    setPortalOn(prev => {
      const next = !prev
      localStorage.setItem(LS_PORTAL, next ? "1" : "0")
      localStorage.setItem(HOME_PREF_KEY, next ? "pra" : "accounting")
      return next
    })
  }, [])

  const isPortal = praModuleInstalled && isPRAEnabled && portalOn
  const canToggle = praModuleInstalled

  return { isPortal, canToggle, togglePortal, settled, praModuleInstalled }
}
