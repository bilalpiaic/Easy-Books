import type { CapacitorConfig } from "@capacitor/cli"

/**
 * Thin WebView around the existing Next.js PWA.
 *
 * Set CAPACITOR_SERVER_URL to your hosted frontend (SaaS) so the shell loads
 * the live PWA (Serwist + OfflineBanner) instead of the local www splash.
 * Leave it unset for a local splash that explains how to point at a server.
 */
const serverUrl = (process.env.CAPACITOR_SERVER_URL || "").trim()

const config: CapacitorConfig = {
  appId: "app.easybooks.mobile",
  appName: "Easy-Books",
  webDir: "www",
  backgroundColor: "#f6f3ee",
  plugins: {
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
    StatusBar: {
      style: "DARK",
      backgroundColor: "#f6f3ee",
    },
  },
}

if (serverUrl) {
  config.server = {
    url: serverUrl,
    cleartext: serverUrl.startsWith("http://"),
  }
}

export default config
