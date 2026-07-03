"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { useFmtCompact } from "@/context/SettingsContext"
import type { InventoryPerfItem } from "@/lib/inventorySummary"

type Metric = "units" | "revenue" | "margin"
type ViewMode = "product" | "category"

interface CategoryRow {
  name: string
  units: number
  revenue: number
  margin_pct: number | null
}

function buildCategoryRows(items: InventoryPerfItem[]): CategoryRow[] {
  const acc: Record<string, { units: number; revenue: number; cost: number }> = {}
  for (const item of items) {
    const key = item.category_name || "Uncategorized"
    if (!acc[key]) acc[key] = { units: 0, revenue: 0, cost: 0 }
    acc[key].units += Number(item.units_sold)
    acc[key].revenue += Number(item.sales_value ?? 0)
    acc[key].cost += Number(item.cogs ?? 0)
  }
  return Object.entries(acc).map(([name, v]) => ({
    name,
    units: v.units,
    revenue: v.revenue,
    margin_pct: v.revenue > 0 ? Math.round((v.revenue - v.cost) / v.revenue * 1000) / 10 : null,
  }))
}

const METRIC_LABELS: Record<Metric, string> = {
  units: "Units sold",
  revenue: "Sales value",
  margin: "Profitability",
}

export default function TopProductsWidget() {
  const fmt = useFmtCompact()
  const [items, setItems] = useState<InventoryPerfItem[] | null>(null)
  const [error, setError] = useState(false)
  const [metric, setMetric] = useState<Metric>("revenue")
  const [view, setView] = useState<ViewMode>("product")

  useEffect(() => {
    apiFetch<{ items: InventoryPerfItem[] }>("/api/reports/inventory-performance")
      .then(r => setItems(r.items))
      .catch(() => setError(true))
  }, [])

  const subtitle = `by ${METRIC_LABELS[metric].toLowerCase()}`

  const rows = (() => {
    if (!items) return []
    if (view === "category") {
      const cats = buildCategoryRows(items)
      const sorted = [...cats].sort((a, b) => {
        if (metric === "units") return b.units - a.units
        if (metric === "revenue") return b.revenue - a.revenue
        return (b.margin_pct ?? -Infinity) - (a.margin_pct ?? -Infinity)
      })
      return sorted.slice(0, 10).map(c => ({
        id: c.name,
        name: c.name,
        value: metric === "units" ? c.units : metric === "revenue" ? c.revenue : c.margin_pct,
      }))
    }
    const sorted = [...items].sort((a, b) => {
      if (metric === "units") return Number(b.units_sold) - Number(a.units_sold)
      if (metric === "revenue") return Number(b.sales_value ?? 0) - Number(a.sales_value ?? 0)
      return (Number(b.margin_pct ?? -Infinity)) - (Number(a.margin_pct ?? -Infinity))
    })
    return sorted.slice(0, 10).map(p => ({
      id: String(p.id),
      name: p.name,
      value: metric === "units" ? Number(p.units_sold) : metric === "revenue" ? Number(p.sales_value ?? 0) : p.margin_pct,
    }))
  })()

  const formatValue = (v: number | null | undefined) => {
    if (v == null) return "—"
    if (metric === "units") return Math.round(Number(v)).toLocaleString("en-PK")
    if (metric === "revenue") return fmt(Number(v))
    return `${v}%`
  }

  const btnBase = "px-2 py-0.5 rounded-full text-[10px] font-semibold transition-colors"
  const btnActive = "bg-[var(--primary)] text-white"
  const btnInactive = "bg-[var(--bg-page)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"

  return (
    <div className="h-full flex flex-col bg-white border border-[var(--border)] rounded-xl p-4 shadow-sm">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-1">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/55">Top Products</p>
          <p className="text-[10px] text-[var(--text-primary)]/40 mt-0.5">{subtitle}</p>
        </div>
        {/* Metric buttons */}
        <div className="flex gap-1 flex-shrink-0">
          {(["units", "revenue", "margin"] as Metric[]).map(m => (
            <button key={m} onClick={() => setMetric(m)} className={`${btnBase} ${metric === m ? btnActive : btnInactive}`}>
              {m === "units" ? "Units" : m === "revenue" ? "Value" : "Margin"}
            </button>
          ))}
        </div>
      </div>

      {/* View toggle */}
      <div className="flex gap-1 mb-3">
        {(["product", "category"] as ViewMode[]).map(v => (
          <button key={v} onClick={() => setView(v)}
            className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold border transition-colors ${
              view === v
                ? "bg-[var(--primary-light)] border-[var(--primary)] text-[var(--primary)]"
                : "border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}>
            {v === "product" ? "By product" : "By category"}
          </button>
        ))}
      </div>

      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !items ? (
        <div className="shimmer h-20 rounded-lg" />
      ) : rows.length === 0 ? (
        <div className="text-sm text-[var(--text-primary)]/40">No data yet.</div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto -mx-1 px-1">
          {rows.map((row, i) => (
            <div key={row.id} className="flex items-center gap-2 py-1.5 border-b border-[var(--border)] last:border-0 text-sm">
              <span className="text-[10px] font-bold text-[var(--primary)] w-4 flex-shrink-0">{i + 1}</span>
              <span className="flex-1 truncate text-[var(--text-primary)]/80">{row.name}</span>
              <span className="font-medium tabular-nums whitespace-nowrap">{formatValue(row.value as number | null)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
