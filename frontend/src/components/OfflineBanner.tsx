"use client"

import { useEffect, useState } from "react"
import { WifiOff } from "lucide-react"

export default function OfflineBanner() {
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    const sync = () => setOffline(!navigator.onLine)
    sync()
    window.addEventListener("online", sync)
    window.addEventListener("offline", sync)
    return () => {
      window.removeEventListener("online", sync)
      window.removeEventListener("offline", sync)
    }
  }, [])

  if (!offline) return null

  return (
    <div
      role="status"
      className="print:hidden shrink-0 z-[60] flex items-center justify-center gap-2 bg-amber-700 text-white text-[12px] font-medium px-3 py-2"
    >
      <WifiOff className="w-3.5 h-3.5 shrink-0" aria-hidden />
      You’re offline — data may be unavailable until you reconnect.
    </div>
  )
}
