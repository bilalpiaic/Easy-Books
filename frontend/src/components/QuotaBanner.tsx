"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AlertTriangle, X } from "lucide-react"

type QuotaDetail = {
  status: number
  error?: string
  message?: string
  used?: number
  limit?: number
  plan?: string
}

export default function QuotaBanner() {
  const [info, setInfo] = useState<QuotaDetail | null>(null)

  useEffect(() => {
    const onQuota = (e: Event) => {
      const ce = e as CustomEvent<QuotaDetail>
      setInfo(ce.detail)
    }
    window.addEventListener("eb:quota", onQuota)
    return () => window.removeEventListener("eb:quota", onQuota)
  }, [])

  if (!info) return null

  const title =
    info.status === 402
      ? "Plan quota exceeded"
      : "Rate limit reached"
  const body =
    info.message ||
    (info.error ? String(info.error).replace(/_/g, " ") : "Upgrade your plan to continue.")

  return (
    <div className="print:hidden sticky top-0 z-[60] bg-amber-50 border-b border-amber-200 px-4 py-2.5">
      <div className="max-w-5xl mx-auto flex items-start gap-3 text-sm text-amber-950">
        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-amber-700" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{title}</p>
          <p className="text-amber-900/80 mt-0.5">
            {body}
            {info.plan ? ` · Current plan: ${info.plan}` : ""}
            {" · "}
            <Link href="/settings/billing" className="underline font-medium">
              Billing & plan
            </Link>
          </p>
        </div>
        <button
          type="button"
          aria-label="Dismiss"
          onClick={() => setInfo(null)}
          className="p-1 rounded hover:bg-amber-100"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
