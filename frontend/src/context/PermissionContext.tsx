"use client"
import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react"
import { apiFetch } from "@/lib/api"

interface PermissionData {
  permissions: Record<string, string>  // resource_key → "none" | "view" | "edit"
  my_data_only: boolean
  module_enabled: boolean
}

interface PermissionCtx {
  can: (resource: string, level?: "view" | "edit") => boolean
  myDataOnly: boolean
  moduleEnabled: boolean
  loading: boolean
  refresh: () => void
}

const PermissionContext = createContext<PermissionCtx>({
  can: () => true,
  myDataOnly: false,
  moduleEnabled: false,
  loading: false,
  refresh: () => {},
})

function isAuthenticated() {
  if (typeof window === "undefined") return false
  try {
    if (sessionStorage.getItem("eb.auth_session") !== "1") return false
  } catch {
    return false
  }
  return !!localStorage.getItem("access_token")
}

export function PermissionProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<PermissionData | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(() => {
    if (!isAuthenticated()) return
    setLoading(true)
    apiFetch<PermissionData>("/api/permissions/me")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const can = useCallback((resource: string, level: "view" | "edit" = "view"): boolean => {
    if (!data || !data.module_enabled) return true  // module off → full access
    const eff = data.permissions[resource] ?? "edit"
    if (level === "view") return eff !== "none"
    return eff === "edit"
  }, [data])

  return (
    <PermissionContext.Provider value={{
      can,
      myDataOnly: data?.my_data_only ?? false,
      moduleEnabled: data?.module_enabled ?? false,
      loading,
      refresh: load,
    }}>
      {children}
    </PermissionContext.Provider>
  )
}

export function usePermission() {
  return useContext(PermissionContext)
}
