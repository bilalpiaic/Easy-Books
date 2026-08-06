"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"

interface Item {
  product_id: number
  product_code?: string
  product_name: string
  qty: number
  value: number
}

interface Warehouse {
  location_id: number
  code: string
  name: string
  type: string
  items: Item[]
  total_qty: number
  total_value: number
}

export default function StockByWarehousePage() {
  const fmt = useFmt()
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ warehouses: Warehouse[] }>("/api/reports/stock-by-warehouse")
      .then((r) => setWarehouses(r.warehouses || []))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [])

  return (
    <div className="space-y-6 max-w-5xl">
      <PrintHeader title="Stock by Warehouse" orientation="landscape" />
      <div className="print:hidden">
        <h1 className="text-2xl font-bold">Stock by Warehouse</h1>
        <p className="text-sm text-[var(--text-primary)]/55">On-hand qty from location layers (own + in transit).</p>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-3 py-2 text-sm">{error}</div>}

      {warehouses.map((w) => (
        <div key={w.location_id} className="space-y-2">
          <h2 className="text-lg font-semibold">
            {w.code} — {w.name}
            <span className="ml-2 text-xs font-normal text-[var(--text-primary)]/50 capitalize">{w.type.replace("_", " ")}</span>
          </h2>
          <div className="table-freeze overflow-x-auto bg-white border border-[var(--text-primary)]/10 rounded-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-[var(--text-primary)]/60">
                  <th className="px-3 py-2">Product</th>
                  <th className="px-3 py-2 text-right">Qty</th>
                  <th className="px-3 py-2 text-right">Value</th>
                </tr>
              </thead>
              <tbody>
                {w.items.map((it) => (
                  <tr key={it.product_id} className="border-b border-[var(--text-primary)]/5">
                    <td className="px-3 py-2">{it.product_name}</td>
                    <td className="px-3 py-2 text-right">{it.qty}</td>
                    <td className="px-3 py-2 text-right">{fmt(it.value)}</td>
                  </tr>
                ))}
                {!w.items.length && (
                  <tr><td colSpan={3} className="px-3 py-4 text-center text-[var(--text-primary)]/40">Empty</td></tr>
                )}
              </tbody>
              <tfoot>
                <tr className="border-t font-medium">
                  <td className="px-3 py-2">Total</td>
                  <td className="px-3 py-2 text-right">{w.total_qty}</td>
                  <td className="px-3 py-2 text-right">{fmt(w.total_value)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      ))}

      {!warehouses.length && !error && (
        <p className="text-sm text-[var(--text-primary)]/50">No warehouse stock yet.</p>
      )}
    </div>
  )
}
