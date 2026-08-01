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
    matcher: ({ sameOrigin, url }) => sameOrigin && url.pathname.startsWith("/api/"),
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
