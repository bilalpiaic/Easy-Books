"use client"

import { useEffect, useState } from "react"
import { useFmt } from "@/context/SettingsContext"
import { apiFetch } from "@/lib/api"
import { summarizeInventory, type InventoryPerfItem } from "@/lib/inventorySummary"

export default function InventorySummaryWidget() {
  const fmt = useFmt()
  const [items, setItems] = useState<InventoryPerfItem[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiFetch<{ items: InventoryPerfItem[] }>("/api/reports/inventory-performance")
      .then(r => setItems(r.items))
      .catch(() => setError(true))
  }, [])

  const t = items ? summarizeInventory(items) : null

  return (
    <div className="h-full flex flex-col bg-white border border-[var(--border)] rounded-xl p-4 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/55 mb-3">Inventory Summary</p>
      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !t ? (
        <div className="shimmer h-16 rounded-lg" />
      ) : (
        <div className="flex-1 grid grid-cols-3 gap-2 items-center">
          <Figure label="Stock Value" value={fmt(t.totalValue)} />
          <Figure label="Stock Items" value={String(t.itemCount)} />
          <Figure label="Low Stock" value={String(t.lowStock)} warn={t.lowStock > 0} />
        </div>
      )}
    </div>
  )
}

function Figure({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="text-center min-w-0">
      <p className={`text-lg font-bold leading-none truncate ${warn ? "text-amber-600" : "text-[var(--text-primary)]"}`}>{value}</p>
      <p className="text-[10px] text-[var(--text-primary)]/55 mt-1 uppercase tracking-wide">{label}</p>
    </div>
  )
}
