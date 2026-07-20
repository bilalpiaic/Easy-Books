import { getAuthHeader } from "./auth"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export const apiBase = BASE

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      // Automatically set Content-Type for JSON bodies so FastAPI parses them correctly.
      ...(options.body && typeof options.body === "string"
        ? { "Content-Type": "application/json" }
        : {}),
      ...getAuthHeader(),
      ...(options.headers ?? {}),
    },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const detail = (data as { detail?: unknown }).detail
    let msg: string
    if (Array.isArray(detail)) {
      msg = (detail as { msg?: string }[]).map(d => d.msg ?? String(d)).join(", ")
    } else if (typeof detail === "string") {
      msg = detail
    } else if (detail && typeof detail === "object") {
      const d = detail as { message?: string; warnings?: string[] }
      const parts = [d.message, ...(d.warnings ?? [])].filter(Boolean)
      msg = parts.length ? parts.join(" — ") : `HTTP ${res.status}`
    } else {
      msg = `HTTP ${res.status}`
    }
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}
