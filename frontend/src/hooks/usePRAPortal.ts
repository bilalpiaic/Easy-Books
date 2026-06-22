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
 * `settled` is false until the localStorage read has completed after mount.
 * Callers that redirect based on isPortal MUST gate on `settled` to avoid a
 * redirect loop: the initial render always has isPortal=false (SSR-safe), and
 * the value updates once after mount — without the gate, two pages that
 * redirect in opposite directions will bounce back and forth indefinitely.
 */
export function usePRAPortal(): {
  isPortal: boolean
  canToggle: boolean
  togglePortal: () => void
  settled: boolean
} {
  const { settings } = useSettings()
  const user = getCurrentUser()
  const role = user?.role ?? "viewer"
  const isPRAEnabled = settings.pra_enabled === "true"
  const isAdminOrOwner = role === "admin" || role === "owner"

  const [adminPortalOn, setAdminPortalOn] = useState(false)
  const [settled, setSettled] = useState(false)

  useEffect(() => {
    if (isAdminOrOwner && isPRAEnabled) {
      setAdminPortalOn(localStorage.getItem(LS_KEY) === "1")
    }
    setSettled(true)
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

  return { isPortal, canToggle, togglePortal, settled }
}
