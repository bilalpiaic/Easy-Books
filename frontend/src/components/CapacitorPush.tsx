"use client"

import { useEffect } from "react"
import { apiFetch } from "@/lib/api"
import { isCapacitorNative } from "@/lib/capacitorNative"

/**
 * Registers the Capacitor push plugin when running inside the iOS/Android
 * shell. No-op in the browser PWA (OfflineBanner + Serwist still apply).
 */
export default function CapacitorPush() {
  useEffect(() => {
    if (!isCapacitorNative()) return
    let cancelled = false

    ;(async () => {
      try {
        const { PushNotifications } = await import("@capacitor/push-notifications")
        const perm = await PushNotifications.requestPermissions()
        if (cancelled || perm.receive !== "granted") return
        await PushNotifications.register()

        await PushNotifications.addListener("registration", async ({ value }) => {
          if (!value) return
          const platform =
            typeof navigator !== "undefined" && /android/i.test(navigator.userAgent)
              ? "android"
              : "ios"
          try {
            await apiFetch("/api/devices", {
              method: "POST",
              body: JSON.stringify({ token: value, platform }),
            })
          } catch (err) {
            console.warn("[capacitor] device register failed", err)
          }
        })

        await PushNotifications.addListener("pushNotificationActionPerformed", (event) => {
          const href = (event.notification?.data as { href?: string } | undefined)?.href
          if (href && href.startsWith("/")) {
            window.location.assign(href)
          }
        })
      } catch (err) {
        console.warn("[capacitor] push plugin unavailable", err)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [])

  return null
}
