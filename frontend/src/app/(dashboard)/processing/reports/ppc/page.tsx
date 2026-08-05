"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

export default function PpcReportPage() {
  const [groupBy, setGroupBy] = useState("stage")
  const [data, setData] = useState<any>({ items: [], aggregates: [] })

  useEffect(() => {
    apiFetch(`/api/textile-processing/reports/ppc-stage?group_by=${groupBy}`)
      .then(setData).catch(() => setData({ items: [], aggregates: [] }))
  }, [groupBy])

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <PrintHeader title="PPC Stage Register" orientation="landscape" />
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-xl font-semibold">PPC Stage Reports</h1>
        <select className="border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          value={groupBy} onChange={e => setGroupBy(e.target.value)}>
          <option value="stage">By stage</option>
          <option value="lot">By lot</option>
          <option value="quality">By quality</option>
          <option value="customer">By customer</option>
        </select>
      </div>

      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Group</th>
            <th className="p-2 text-right">Count</th>
            <th className="p-2 text-right">Input</th>
            <th className="p-2 text-right">Output</th>
            <th className="p-2 text-right">Visible</th>
            <th className="p-2 text-right">Invisible</th>
            <th className="p-2 text-right">Labor</th>
          </tr></thead>
          <tbody>
            {(data.aggregates || []).map((a: any, i: number) => (
              <tr key={i} className="border-b border-[var(--border)]/60">
                <td className="p-2">{a.label}</td>
                <td className="p-2 text-right">{a.count}</td>
                <td className="p-2 text-right">{a.input_mtr?.toFixed?.(2) ?? a.input_mtr}</td>
                <td className="p-2 text-right">{a.output_mtr?.toFixed?.(2) ?? a.output_mtr}</td>
                <td className="p-2 text-right">{a.visible_wastage_mtr?.toFixed?.(2) ?? a.visible_wastage_mtr}</td>
                <td className="p-2 text-right">{a.invisible_wastage_mtr?.toFixed?.(2) ?? a.invisible_wastage_mtr}</td>
                <td className="p-2 text-right">{a.labor_amount?.toFixed?.(2) ?? a.labor_amount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="font-semibold">Detail lines</h2>
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Date</th><th className="p-2">Lot</th><th className="p-2">Customer</th>
            <th className="p-2">Process</th><th className="p-2 text-right">In</th>
            <th className="p-2 text-right">Out</th><th className="p-2 text-right">Vis</th>
            <th className="p-2 text-right">Invis</th>
          </tr></thead>
          <tbody>
            {(data.items || []).map((r: any) => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2 whitespace-nowrap">{r.lot_number}</td>
                <td className="p-2">{r.customer_name}</td>
                <td className="p-2">{r.process_name}</td>
                <td className="p-2 text-right">{r.input_mtr}</td>
                <td className="p-2 text-right">{r.output_mtr}</td>
                <td className="p-2 text-right">{r.visible_wastage_mtr}</td>
                <td className="p-2 text-right">{r.invisible_wastage_mtr}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
