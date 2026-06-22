"use client"
import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

export interface ModuleInfo {
  id: string
  label: string
  description: string
  category: string
  icon: string
  deps: string[]
  always: boolean
  tier: "free" | "pro" | "enterprise"
  nav_sections: string[]
  installed: boolean
  installed_at: string | null
  expires_at: string | null
}

interface ModuleContextValue {
  modules: ModuleInfo[]
  installedModules: Set<string>
  loading: boolean
  install: (id: string) => Promise<void>
  uninstall: (id: string) => Promise<void>
  refresh: () => Promise<void>
}

const ModuleContext = createContext<ModuleContextValue>({
  modules: [],
  installedModules: new Set(["base"]),
  loading: true,
  install: async () => {},
  uninstall: async () => {},
  refresh: async () => {},
})

export function ModuleProvider({ children }: { children: React.ReactNode }) {
  const [modules, setModules] = useState<ModuleInfo[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch<ModuleInfo[]>("/api/modules")
      if (Array.isArray(data)) setModules(data)
    } catch {
      // unauthenticated — keep defaults
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const install = useCallback(async (id: string) => {
    await apiFetch(`/api/modules/${id}/install`, { method: "POST" })
    await refresh()
  }, [refresh])

  const uninstall = useCallback(async (id: string) => {
    await apiFetch(`/api/modules/${id}/uninstall`, { method: "POST" })
    await refresh()
  }, [refresh])

  const installedModules = new Set(modules.filter(m => m.installed).map(m => m.id))
  // base is always present even before the fetch resolves
  installedModules.add("base")

  return (
    <ModuleContext.Provider value={{ modules, installedModules, loading, install, uninstall, refresh }}>
      {children}
    </ModuleContext.Provider>
  )
}

export function useModules() {
  return useContext(ModuleContext)
}
