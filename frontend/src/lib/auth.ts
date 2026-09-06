const TOKEN_KEY = "access_token"
const MUST_CHANGE_KEY = "eb.must_change_pwd"
const MUST_SETUP_TOTP_KEY = "eb.must_setup_totp"
/** Tab/window session marker — cleared when the browser session ends. */
const SESSION_KEY = "eb.auth_session"

export const getAuthToken = () => {
  if (typeof window !== "undefined") {
    return localStorage.getItem(TOKEN_KEY)
  }
  return null
}

export const setAuthToken = (token: string) => {
  localStorage.setItem(TOKEN_KEY, token)
  markAuthSession()
}

export const removeAuthToken = () => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(MUST_CHANGE_KEY)
  localStorage.removeItem(MUST_SETUP_TOTP_KEY)
  clearAuthSession()
}

export const setMustChangePwd = (v: boolean) => {
  if (v) localStorage.setItem(MUST_CHANGE_KEY, "1")
  else localStorage.removeItem(MUST_CHANGE_KEY)
}

export const getMustChangePwd = (): boolean =>
  typeof window !== "undefined" && localStorage.getItem(MUST_CHANGE_KEY) === "1"

export const setMustSetupTotp = (v: boolean) => {
  if (v) localStorage.setItem(MUST_SETUP_TOTP_KEY, "1")
  else localStorage.removeItem(MUST_SETUP_TOTP_KEY)
}

export const getMustSetupTotp = (): boolean =>
  typeof window !== "undefined" && localStorage.getItem(MUST_SETUP_TOTP_KEY) === "1"

export function markAuthSession() {
  if (typeof window === "undefined") return
  try {
    sessionStorage.setItem(SESSION_KEY, "1")
  } catch { /* private mode */ }
}

export function clearAuthSession() {
  if (typeof window === "undefined") return
  try {
    sessionStorage.removeItem(SESSION_KEY)
  } catch { /* private mode */ }
}

export function hasAuthSession(): boolean {
  if (typeof window === "undefined") return false
  try {
    return sessionStorage.getItem(SESSION_KEY) === "1"
  } catch {
    return false
  }
}

/**
 * Drop a leftover JWT when this browser tab/session never completed login.
 * Cold start, new Electron window, and post-update always require /login.
 */
export function reconcileAuthOnLoad() {
  if (typeof window === "undefined") return
  if (localStorage.getItem(TOKEN_KEY) && !hasAuthSession()) {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(MUST_CHANGE_KEY)
    localStorage.removeItem(MUST_SETUP_TOTP_KEY)
  }
}

export const isAuthenticated = () => {
  if (typeof window === "undefined") return false
  reconcileAuthOnLoad()
  return !!getAuthToken() && hasAuthSession()
}

export const getAuthHeader = (): HeadersInit => {
  const token = getAuthToken()
  if (token) {
    return { Authorization: `Bearer ${token}` }
  }
  return {}
}

export interface CurrentUser {
  email: string
  full_name: string
  role: string
}

export function getCurrentUser(): CurrentUser | null {
  const token = getAuthToken()
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split(".")[1]))
    return {
      email: payload.sub ?? "",
      full_name: payload.full_name ?? payload.sub ?? "User",
      role: payload.role ?? "viewer",
    }
  } catch {
    return null
  }
}
