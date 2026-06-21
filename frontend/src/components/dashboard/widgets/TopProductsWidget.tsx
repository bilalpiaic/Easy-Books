"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { topByUnitsSold, type InventoryPerfItem } from "@/lib/inventorySummary"
import { useTranslation } from "react-i18next"

export default function TopProductsWidget() {
  const { t } = useTranslation()

  const [items, setItems] = useState<InventoryPerfItem[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiFetch<{ items: InventoryPerfItem[] }>("/api/reports/inventory-performance")
      .then(r => setItems(r.items))
      .catch(() => setError(true))
  }, [])

  const top = items ? topByUnitsSold(items, 5) : []

  return (
    <div className="h-full flex flex-col bg-white border border-[#ede9e2] rounded-xl p-4 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-2">Top Products</p>
      <p className="text-[10px] text-[#1a1814]/40 -mt-1 mb-2">by units sold</p>
      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !items ? (
        <div className="shimmer h-20 rounded-lg" />
      ) : top.length === 0 ? (
        <div className="text-sm text-[#1a1814]/40">No products yet.</div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto -mx-1 px-1">
          {top.map((p, i) => (
            <div key={p.id} className="flex items-center gap-2 py-1.5 border-b border-[#ede9e2] last:border-0 text-sm">
              <span className="text-[10px] font-bold text-[#b8943f] w-4 flex-shrink-0">{i + 1}</span>
              <span className="flex-1 truncate text-[#1a1814]/80">{p.name}</span>
              <span className="font-medium tabular-nums whitespace-nowrap">{Number(p.units_sold)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
