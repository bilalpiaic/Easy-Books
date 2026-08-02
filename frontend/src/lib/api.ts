import { getAuthHeader } from "./auth"

// Prefer 127.0.0.1 over "localhost" — on Windows, localhost often resolves to
// IPv6 ::1 while the installer binds uvicorn to 127.0.0.1 only, which surfaces
// in the browser as a generic "Failed to fetch" on login.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"

export const apiBase = BASE

/** Human-readable message when fetch itself fails (backend down / wrong host). */
export function networkErrorMessage(err: unknown, fallback = "Request failed"): string {
  const raw = err instanceof Error ? err.message : String(err ?? "")
  if (/failed to fetch|networkerror|load failed|network request failed/i.test(raw)) {
    return `Can't reach the API at ${BASE}. The backend may still be starting — wait a few seconds and try again. If it keeps failing, check the Easy-Books backend log (backend.err.log in your .easy-books data folder).`
  }
  return raw || fallback
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.detail = detail
  }
}

function detailMessage(detail: unknown, status: number): string {
  if (Array.isArray(detail)) {
    return (detail as { msg?: string }[]).map(d => d.msg ?? String(d)).join(", ")
  }
  if (typeof detail === "string") return detail
  if (detail && typeof detail === "object") {
    const d = detail as {
      message?: string
      error?: string
      warnings?: string[]
      used?: number
      limit?: number
      plan?: string
    }
    if (d.message) {
      const quota =
        d.limit != null && d.used != null
          ? ` (${d.used}/${d.limit}${d.plan ? ` · ${d.plan}` : ""})`
          : ""
      return `${d.message}${quota}`
    }
    if (d.error) {
      const quota =
        d.limit != null && d.used != null
          ? ` — ${d.used}/${d.limit}`
          : ""
      return `${String(d.error).replace(/_/g, " ")}${quota}`
    }
    const parts = [...(d.warnings ?? [])].filter(Boolean)
    if (parts.length) return parts.join(" — ")
  }
  return `HTTP ${status}`
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
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
  } catch (err) {
    throw new Error(networkErrorMessage(err))
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const detail = (data as { detail?: unknown }).detail
    const msg = detailMessage(detail, res.status)
    if (
      typeof window !== "undefined" &&
      (res.status === 402 || res.status === 429) &&
      detail &&
      typeof detail === "object" &&
      "error" in (detail as object)
    ) {
      window.dispatchEvent(
        new CustomEvent("eb:quota", {
          detail: { status: res.status, ...(detail as object), message: msg },
        }),
      )
    }
    throw new ApiError(msg, res.status, detail)
  }
  return res.json() as Promise<T>
}
