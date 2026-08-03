"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import KpiCard from "@/components/dashboard/KpiCard"

type WasteReport = {
  by_type: Record<string, { qty_kg: number; cost: number; count: number }>
  by_stage: Record<string, number>
  total_waste_kg: number
}

type WasteType = { id: number; code: string; name: string }

export default function WasteAnalysisPage() {
  const fmt = useFmt()
  const [data, setData] = useState<WasteReport | null>(null)
  const [types, setTypes] = useState<Record<number, string>>({})

  useEffect(() => {
    Promise.all([
      apiFetch<WasteReport>("/api/spinning/reports/waste").catch(() => null),
      apiFetch<WasteType[]>("/api/spinning/waste-types").catch(() => []),
    ]).then(([report, wt]) => {
      setData(report)
      const map: Record<number, string> = {}
      for (const t of Array.isArray(wt) ? wt : []) map[t.id] = `${t.code} — ${t.name}`
      setTypes(map)
    })
  }, [])

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title="Waste Analysis" orientation="landscape" />
      <div className="print:hidden">
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Waste Analysis</h1>
        <p className="text-sm text-[var(--text-muted)]">Posted waste by type and stage</p>
      </div>

      <KpiCard title="Total waste" value={data ? `${fmt(data.total_waste_kg)} kg` : null} tone="amber" />

      <div className="grid md:grid-cols-2 gap-4">
        <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <h2 className="text-sm font-semibold px-3 pt-3">By waste type</h2>
          <table className="w-full text-sm mt-2">
            <thead>
              <tr className="text-left text-[var(--text-muted)]">
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2 text-right">Qty kg</th>
                <th className="px-3 py-2 text-right">Cost</th>
                <th className="px-3 py-2 text-right">Count</th>
              </tr>
            </thead>
            <tbody>
              {data && Object.entries(data.by_type).map(([id, v]) => (
                <tr key={id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2">{types[Number(id)] || `#${id}`}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(v.qty_kg)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(v.cost)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{v.count}</td>
                </tr>
              ))}
              {!data?.by_type || Object.keys(data.by_type).length === 0 ? (
                <tr><td colSpan={4} className="px-3 py-8 text-center text-[var(--text-muted)]">No waste data</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <h2 className="text-sm font-semibold px-3 pt-3">By stage</h2>
          <table className="w-full text-sm mt-2">
            <thead>
              <tr className="text-left text-[var(--text-muted)]">
                <th className="px-3 py-2">Stage</th>
                <th className="px-3 py-2 text-right">Qty kg</th>
              </tr>
            </thead>
            <tbody>
              {data && Object.entries(data.by_stage).map(([stage, kg]) => (
                <tr key={stage} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2 capitalize">{stage}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(kg)}</td>
                </tr>
              ))}
              {!data?.by_stage || Object.keys(data.by_stage).length === 0 ? (
                <tr><td colSpan={2} className="px-3 py-8 text-center text-[var(--text-muted)]">No waste data</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
