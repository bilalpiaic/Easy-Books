import { getCurrentUser } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"

/**
 * Returns isPortal=true when the current user is a non-admin on a PRA-enabled tenant.
 * All portal-mode UI simplifications read from this single hook.
 */
export function usePRAPortal(): { isPortal: boolean } {
  const { settings } = useSettings()
  const user = getCurrentUser()
  const role = user?.role ?? "viewer"
  return {
    isPortal: settings.pra_enabled === "true" && role !== "admin" && role !== "owner",
  }
}
