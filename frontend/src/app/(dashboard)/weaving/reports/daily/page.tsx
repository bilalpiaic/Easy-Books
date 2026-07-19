"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
import KpiCard from "@/components/dashboard/KpiCard"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { formatWeightTriple, type WeightTriple } from "@/lib/weavingUnits"

type Daily = {
  kpis: {
    yarn_received: WeightTriple
    yarn_sized: WeightTriple
    fabric_produced_m: number
    fabric_delivered_m: number
    avg_efficiency_pct: number
    weaving_charges: number
    net_receivable: number
  }
  activity: {
    date: string
    type: string
    number: string
    contract_id: number
    kg?: number
    lbs?: number
    bags?: number
    meters?: number
    amount?: number
    efficiency_pct?: number
  }[]
  efficiency_by_shift: { id: number; name: string; avg_efficiency_pct: number }[]
  efficiency_by_operator: { id: number; name: string; avg_efficiency_pct: number }[]
  efficiency_by_loom: { id: number; name: string; avg_efficiency_pct: number }[]
}

function defaultRange() {
  const end = new Date()
  const start = new Date(end.getFullYear(), end.getMonth(), 1)
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
}

export default function DailyOpsPage() {
  const fmt = useFmt()
  const initial = defaultRange()
  const [start, setStart] = useState(initial.start)
  const [end, setEnd] = useState(initial.end)
  const [data, setData] = useState<Daily | null>(null)

  useEffect(() => {
    const qs = new URLSearchParams()
    if (start) qs.set("start", start)
    if (end) qs.set("end", end)
    apiFetch<Daily>(`/api/weaving/reports/daily?${qs}`).then(setData).catch(() => setData(null))
  }, [start, end])

  const k = data?.kpis

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title="Daily Operations Dashboard" orientation="landscape" />
      <div className="print:hidden">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard title="Yarn received" value={k ? formatWeightTriple(k.yarn_received) : null} tone="blue"
          sub={k ? `${k.yarn_received.lbs.toFixed(1)} lb` : undefined} />
        <KpiCard title="Yarn sized" value={k ? formatWeightTriple(k.yarn_sized) : null} tone="amber"
          sub={k ? `${k.yarn_sized.lbs.toFixed(1)} lb` : undefined} />
        <KpiCard title="Fabric produced" value={k ? `${fmt(k.fabric_produced_m)} m` : null} />
        <KpiCard title="Delivered" value={k ? `${fmt(k.fabric_delivered_m)} m` : null} />
        <KpiCard title="Avg efficiency" value={k ? `${fmt(k.avg_efficiency_pct)}%` : null} />
        <KpiCard title="Weaving charges" value={k ? fmt(k.weaving_charges) : null} />
        <KpiCard title="Net receivable" value={k ? fmt(k.net_receivable) : null} tone="green" />
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Doc #</th>
              <th className="px-3 py-2">Weight</th>
              <th className="px-3 py-2 text-right">Meters</th>
              <th className="px-3 py-2 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {(data?.activity ?? []).map((a, i) => (
              <tr key={`${a.number}-${i}`} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(a.date)}</td>
                <td className="px-3 py-2 capitalize">{a.type.replace("_", " ")}</td>
                <td className="px-3 py-2 whitespace-nowrap">{a.number}</td>
                <td className="px-3 py-2">
                  {a.kg != null ? <WeightTripleDisplay kg={a.kg} lbs={a.lbs} bags={a.bags} /> : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{a.meters != null ? fmt(a.meters) : "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums">{a.amount != null ? fmt(a.amount) : "—"}</td>
              </tr>
            ))}
            {!data?.activity?.length && (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">No activity in range</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {[
          ["By shift", data?.efficiency_by_shift],
          ["By operator", data?.efficiency_by_operator],
          ["By loom", data?.efficiency_by_loom],
        ].map(([title, rows]) => (
          <div key={title as string} className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-3">
            <h3 className="text-sm font-semibold mb-2">{title as string}</h3>
            <ul className="text-sm space-y-1">
              {(rows as { name: string; avg_efficiency_pct: number }[] | undefined)?.map(r => (
                <li key={r.name} className="flex justify-between">
                  <span>{r.name}</span>
                  <span className="tabular-nums">{fmt(r.avg_efficiency_pct)}%</span>
                </li>
              )) ?? <li className="text-[var(--text-muted)]">—</li>}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
