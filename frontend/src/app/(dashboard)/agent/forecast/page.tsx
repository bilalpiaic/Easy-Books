"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

export default function ForecastPage() {
  const [tab, setTab] = useState<"revenue" | "cash" | "risk" | "budget">("revenue")
  const [data, setData] = useState<unknown>(null)

  useEffect(() => {
    const path = {
      revenue: "/api/agent/forecast/revenue",
      cash: "/api/agent/forecast/cash-flow",
      risk: "/api/agent/forecast/customer-risk",
      budget: "/api/agent/forecast/budget-variance",
    }[tab]
    apiFetch(path).then(setData).catch(() => setData(null))
  }, [tab])

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-4">
      <h1 className="font-serif text-2xl">Forecasts</h1>
      <div className="flex gap-2 flex-wrap print:hidden">
        {(["revenue", "cash", "risk", "budget"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 rounded text-sm capitalize ${tab === t ? "bg-[#b8943f]" : "border"}`}
          >
            {t === "cash" ? "Cash flow" : t === "risk" ? "Customer risk" : t}
          </button>
        ))}
      </div>
      <pre className="text-xs bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 overflow-auto max-h-[70vh]">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  )
}
