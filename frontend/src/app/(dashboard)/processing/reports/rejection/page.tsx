"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

export default function RejectionRegisterPage() {
  const [items, setItems] = useState<any[]>([])
  const [openOnly, setOpenOnly] = useState(false)

  useEffect(() => {
    const q = openOnly ? "?open_balance_only=true" : ""
    apiFetch<{ items: any[] }>(`/api/textile-processing/reports/customer-rejection-register${q}`)
      .then(d => setItems(d.items || [])).catch(() => setItems([]))
  }, [openOnly])

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <PrintHeader title="Customer Rejection Register" orientation="landscape" />
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-xl font-semibold">Customer Rejection Register</h1>
        <label className="text-sm flex items-center gap-2">
          <input type="checkbox" checked={openOnly} onChange={e => setOpenOnly(e.target.checked)} />
          Open balance only
        </label>
      </div>
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Date</th><th className="p-2">Note #</th><th className="p-2">Customer</th>
            <th className="p-2">Lot</th><th className="p-2">Quality</th>
            <th className="p-2 text-right">Issued</th><th className="p-2 text-right">Lifted</th>
            <th className="p-2 text-right">Balance</th><th className="p-2">Status</th><th className="p-2">OGPs</th>
          </tr></thead>
          <tbody>
            {items.map(r => (
              <tr key={r.note_id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2 whitespace-nowrap">{r.note_number}</td>
                <td className="p-2">{r.customer_name}</td>
                <td className="p-2 whitespace-nowrap">{r.lot_number}</td>
                <td className="p-2">{r.quality_name} {r.blend || ""} {r.width || ""}</td>
                <td className="p-2 text-right">{r.issued_mtr}</td>
                <td className="p-2 text-right">{r.lifted_mtr}</td>
                <td className="p-2 text-right">{r.balance_mtr}</td>
                <td className="p-2">{r.status}</td>
                <td className="p-2 text-xs">{(r.ogps || []).map((o: any) => o.number).join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
