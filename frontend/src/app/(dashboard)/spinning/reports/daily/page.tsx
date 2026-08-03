"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"

type DailyItem = {
  date: string
  input_kg: number
  output_kg: number
  waste_kg: number
  entries: {
    number: string
    stage: string
    spin_lot_id: number
    input_kg: number
    output_kg: number
    waste_kg: number
    yield_pct: number
  }[]
}

type Daily = { items: DailyItem[] }

function defaultRange() {
  const end = new Date()
  const start = new Date(end.getFullYear(), end.getMonth(), 1)
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
}

export default function DailyRegisterPage() {
  const fmt = useFmt()
  const initial = defaultRange()
  const [start, setStart] = useState(initial.start)
  const [end, setEnd] = useState(initial.end)
  const [data, setData] = useState<Daily | null>(null)

  useEffect(() => {
    const qs = new URLSearchParams()
    if (start) qs.set("start", start)
    if (end) qs.set("end", end)
    apiFetch<Daily>(`/api/spinning/reports/daily?${qs}`).then(setData).catch(() => setData(null))
  }, [start, end])

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title="Spinning Daily Register" orientation="landscape" />
      <div className="print:hidden">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">SE #</th>
              <th className="px-3 py-2">Stage</th>
              <th className="px-3 py-2">Lot ID</th>
              <th className="px-3 py-2 text-right">Input kg</th>
              <th className="px-3 py-2 text-right">Output kg</th>
              <th className="px-3 py-2 text-right">Waste kg</th>
              <th className="px-3 py-2 text-right">Yield %</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).flatMap(day =>
              day.entries.map((e, i) => (
                <tr key={`${day.date}-${e.number}-${i}`} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2 whitespace-nowrap">{fmtDate(day.date)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{e.number}</td>
                  <td className="px-3 py-2 capitalize">{e.stage}</td>
                  <td className="px-3 py-2 tabular-nums">{e.spin_lot_id}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(e.input_kg)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(e.output_kg)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(e.waste_kg)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(e.yield_pct)}</td>
                </tr>
              ))
            )}
            {!data?.items?.length && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-[var(--text-muted)]">No stage activity in range</td></tr>
            )}
          </tbody>
          {(data?.items?.length ?? 0) > 0 && (
            <tfoot>
              <tr className="border-t-2 border-[var(--border)] font-medium">
                <td colSpan={4} className="px-3 py-2">Totals</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {fmt((data?.items ?? []).reduce((s, d) => s + d.input_kg, 0))}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {fmt((data?.items ?? []).reduce((s, d) => s + d.output_kg, 0))}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {fmt((data?.items ?? []).reduce((s, d) => s + d.waste_kg, 0))}
                </td>
                <td className="px-3 py-2"></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}
