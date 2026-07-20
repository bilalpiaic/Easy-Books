"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

/** Legacy multi-tenant demo portal — redirect to single-demo login. */
export default function DemoPortalRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace("/login?demo=1")
  }, [router])
  return (
    <div className="min-h-screen bg-[#f6f3ee] flex items-center justify-center text-sm text-[#1a1814]/50">
      Opening demo…
    </div>
  )
}
