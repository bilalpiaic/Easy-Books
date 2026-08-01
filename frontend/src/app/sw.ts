/// <reference lib="esnext" />
/// <reference lib="webworker" />
import { defaultCache } from "@serwist/turbopack/worker"
import type { PrecacheEntry, RuntimeCaching, SerwistGlobalConfig } from "serwist"
import { NetworkOnly, Serwist } from "serwist"

declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined
  }
}

declare const self: ServiceWorkerGlobalScope

const runtimeCaching: RuntimeCaching[] = [
  {
    // Never cache API traffic. Same-origin /api/* (proxied) AND the local
    // FastAPI host the installer opens (127.0.0.1:8000 / localhost:8000) —
    // otherwise Serwist's default cross-origin NetworkFirst can turn a brief
    // backend blip into a confusing "Failed to fetch" on login.
    matcher: ({ sameOrigin, url }) => {
      if (sameOrigin && url.pathname.startsWith("/api/")) return true
      if (!url.pathname.startsWith("/api/")) return false
      const host = url.hostname
      return (
        (host === "127.0.0.1" || host === "localhost" || host === "[::1]") &&
        (url.port === "8000" || url.port === "")
      )
    },
    handler: new NetworkOnly(),
  },
  ...defaultCache,
]

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  precacheOptions: {
    cleanupOutdatedCaches: true,
  },
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching,
  fallbacks: {
    entries: [
      {
        url: "/~offline",
        matcher({ request }) {
          return request.destination === "document"
        },
      },
    ],
  },
})

serwist.addEventListeners()
