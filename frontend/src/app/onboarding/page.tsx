"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

/** Legacy package wall — industry choice now lives on System → Add-ons. */
export default function OnboardingRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace("/apps?welcome=1")
  }, [router])
  return (
    <div className="min-h-screen bg-[#f6f3ee] flex items-center justify-center text-sm text-[#1a1814]/50">
      Taking you to Add-ons…
    </div>
  )
}
