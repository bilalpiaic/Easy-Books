/** Capacitor native-shell helpers (#307). */

export type CapacitorBridge = {
  isNativePlatform?: () => boolean
}

export function isCapacitorNative(win: Window | undefined = typeof window === "undefined" ? undefined : window): boolean {
  if (!win) return false
  const cap = (win as Window & { Capacitor?: CapacitorBridge }).Capacitor
  return typeof cap?.isNativePlatform === "function" && cap.isNativePlatform()
}
