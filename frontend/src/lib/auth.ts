export const getAuthToken = () => {
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token")
  }
  return null
}

export const setAuthToken = (token: string) => {
  localStorage.setItem("access_token", token)
}

export const removeAuthToken = () => {
  localStorage.removeItem("access_token")
  localStorage.removeItem("eb.must_change_pwd")
}

export const setMustChangePwd = (v: boolean) => {
  if (v) localStorage.setItem("eb.must_change_pwd", "1")
  else localStorage.removeItem("eb.must_change_pwd")
}

export const getMustChangePwd = (): boolean =>
  typeof window !== "undefined" && localStorage.getItem("eb.must_change_pwd") === "1"

export const isAuthenticated = () => {
  return !!getAuthToken()
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
