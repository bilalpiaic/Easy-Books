import { useState, useEffect, useCallback } from "react"
import { getCurrentUser } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"

const LS_KEY = "eb.pra_portal_mode"

/**
 * Single gate for PRA portal mode.
 *
 * Non-admin users on a PRA-enabled tenant are always in portal mode.
 * Admin/owner users can toggle between full accounting view and portal view
 * via the returned togglePortal() function (preference stored in localStorage).
 *
 * Returns:
 *   isPortal    — whether portal-mode UI should be active right now
 *   canToggle   — true for admin/owner on a PRA-enabled tenant
 *   togglePortal — flip the admin portal preference
 */
export function usePRAPortal(): {
  isPortal: boolean
  canToggle: boolean
  togglePortal: () => void
} {
  const { settings } = useSettings()
  const user = getCurrentUser()
  const role = user?.role ?? "viewer"
  const isPRAEnabled = settings.pra_enabled === "true"
  const isAdminOrOwner = role === "admin" || role === "owner"

  // Admin/owner portal preference — read from localStorage after mount to avoid SSR mismatch
  const [adminPortalOn, setAdminPortalOn] = useState(false)
  useEffect(() => {
    if (isAdminOrOwner && isPRAEnabled) {
      setAdminPortalOn(localStorage.getItem(LS_KEY) === "1")
    }
  }, [isAdminOrOwner, isPRAEnabled])

  const togglePortal = useCallback(() => {
    setAdminPortalOn(prev => {
      const next = !prev
      localStorage.setItem(LS_KEY, next ? "1" : "0")
      return next
    })
  }, [])

  const isPortal = isPRAEnabled && (isAdminOrOwner ? adminPortalOn : true)
  const canToggle = isPRAEnabled && isAdminOrOwner

  return { isPortal, canToggle, togglePortal }
}
