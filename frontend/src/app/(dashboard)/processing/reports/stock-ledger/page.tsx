"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import PrintHeader from "@/components/PrintHeader"

export default function StockLedgerPage() {
  const [items, setItems] = useState<any[]>([])

  useEffect(() => {
    apiFetch<{ items: any[] }>("/api/textile-processing/reports/customer-stock-ledger")
      .then(d => setItems(d.items || [])).catch(() => setItems([]))
  }, [])

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <PrintHeader title="Customer Grey Stock Ledger" orientation="landscape" />
      <h1 className="text-xl font-semibold print:hidden">Customer Grey Stock Ledger</h1>
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Customer</th><th className="p-2">Quality / Blend / Width</th>
            <th className="p-2 text-right">Grey in</th><th className="p-2 text-right">Safi under unit</th>
            <th className="p-2 text-right">Rej pending</th><th className="p-2 text-right">Vis waste</th>
            <th className="p-2 text-right">Invis waste</th><th className="p-2 text-right">Dispatched</th>
            <th className="p-2 text-right">Closing</th>
          </tr></thead>
          <tbody>
            {items.map((r, i) => (
              <tr key={i} className="border-b border-[var(--border)]/60">
                <td className="p-2">{r.customer_name}</td>
                <td className="p-2">{r.quality_name} / {r.blend || "—"} / {r.width || "—"}</td>
                <td className="p-2 text-right">{r.grey_in_mtr}</td>
                <td className="p-2 text-right">{r.safi_under_unit_mtr}</td>
                <td className="p-2 text-right">{r.rejection_pending_lift_mtr}</td>
                <td className="p-2 text-right">{r.visible_wastage_mtr}</td>
                <td className="p-2 text-right">{r.invisible_wastage_mtr}</td>
                <td className="p-2 text-right">{r.dispatched_mtr}</td>
                <td className="p-2 text-right">{r.closing_under_unit_mtr}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
