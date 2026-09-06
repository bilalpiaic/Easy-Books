import { apiFetch } from "./api"

export type BootstrapMe = {
  id: number
  role?: string
  tenant?: { business_model?: string }
}

export type BootstrapPermissions = {
  permissions: Record<string, string>
  my_data_only: boolean
  module_enabled: boolean
}

export type BootstrapPayload = {
  me: BootstrapMe
  settings: Record<string, string>
  modules: Array<{ id: string; installed: boolean } & Record<string, unknown>>
  permissions: BootstrapPermissions
}

let inflight: Promise<BootstrapPayload> | null = null
let cached: BootstrapPayload | null = null

export function peekBootstrap(): BootstrapPayload | null {
  return cached
}

export function clearBootstrapCache(): void {
  cached = null
  inflight = null
}

/** Shared SPA shell load. Concurrent callers share one in-flight GET. */
export function loadBootstrap(force = false): Promise<BootstrapPayload> {
  if (!force && cached) return Promise.resolve(cached)
  if (!force && inflight) return inflight
  const req = apiFetch<BootstrapPayload>("/api/auth/bootstrap").then(data => {
    cached = data
    return data
  })
  inflight = req
  return req.finally(() => {
    if (inflight === req) inflight = null
  })
}
