"use client"

import { Suspense, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import KpiCard from "@/components/dashboard/KpiCard"

type LotOpt = { id: number; number: string }
type Control = {
  lot: {
    id: number
    number: string
    status: string
    target_output_kg: number
    output_kg: number
    total_cost: number
    cost_per_kg: number
  }
  bale_in_kg: number
  cone_out_kg: number
  waste_kg: number
  yield_pct: number
  plan_variance_kg: number
  stage_progress: {
    stage: string
    input_kg: number
    output_kg: number
    yield_pct: number
    entries: number
  }[]
}

function LotControlInner() {
  const fmt = useFmt()
  const sp = useSearchParams()
  const [lots, setLots] = useState<LotOpt[]>([])
  const [lotId, setLotId] = useState(sp.get("lot") || "")
  const [data, setData] = useState<Control | null>(null)

  useEffect(() => {
    apiFetch<LotOpt[]>("/api/spinning/lots").then(list => {
      const rows = Array.isArray(list) ? list : []
      setLots(rows)
      if (!lotId && rows[0]) setLotId(String(rows[0].id))
    }).catch(() => setLots([]))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!lotId) { setData(null); return }
    apiFetch<Control>(`/api/spinning/reports/lot-control/${lotId}`)
      .then(setData)
      .catch(() => setData(null))
  }, [lotId])

  const lot = data?.lot

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title="Lot Control Panel" orientation="landscape" />
      <div className="flex flex-wrap items-center gap-3 print:hidden">
        <label className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Spin lot</label>
        <select value={lotId} onChange={e => setLotId(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--border)] rounded-lg">
          <option value="">Select…</option>
          {lots.map(x => <option key={x.id} value={x.id}>{x.number}</option>)}
        </select>
        {lot && (
          <Link href={`/spinning/lots/${lot.id}`} className="text-sm text-[var(--primary)]">Open lot</Link>
        )}
      </div>

      {!lotId ? (
        <p className="text-sm text-[var(--text-muted)]">Select a lot to view the control panel.</p>
      ) : !data ? (
        <p className="text-sm text-[var(--text-muted)]">Loading…</p>
      ) : (
        <>
          <div className="text-sm text-[var(--text-muted)]">
            {lot!.number} · <span className="capitalize">{lot!.status.replace("_", " ")}</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KpiCard title="Bale in" value={`${fmt(data.bale_in_kg)} kg`} tone="blue" />
            <KpiCard title="Cone out" value={`${fmt(data.cone_out_kg)} kg`} tone="green" />
            <KpiCard title="Waste" value={`${fmt(data.waste_kg)} kg`} tone="amber" />
            <KpiCard title="Yield" value={`${fmt(data.yield_pct)}%`} />
            <KpiCard title="Target output" value={`${fmt(lot!.target_output_kg)} kg`} />
            <KpiCard title="Actual output" value={`${fmt(lot!.output_kg)} kg`} />
            <KpiCard title="Plan variance" value={`${fmt(data.plan_variance_kg)} kg`} />
            <KpiCard title="Cost / kg" value={fmt(lot!.cost_per_kg)} tone="emerald" />
          </div>

          <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--text-muted)]">
                  <th className="px-3 py-2">Stage</th>
                  <th className="px-3 py-2 text-right">Input kg</th>
                  <th className="px-3 py-2 text-right">Output kg</th>
                  <th className="px-3 py-2 text-right">Yield %</th>
                  <th className="px-3 py-2 text-right">Entries</th>
                </tr>
              </thead>
              <tbody>
                {data.stage_progress.map(s => (
                  <tr key={s.stage} className="border-t border-[var(--border)]">
                    <td className="px-3 py-2 capitalize">{s.stage}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmt(s.input_kg)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmt(s.output_kg)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmt(s.yield_pct)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{s.entries}</td>
                  </tr>
                ))}
                {!data.stage_progress.length && (
                  <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--text-muted)]">No stage entries</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

export default function LotControlPage() {
  return (
    <Suspense fallback={<div className="p-4 text-sm text-[var(--text-muted)]">Loading…</div>}>
      <LotControlInner />
    </Suspense>
  )
}
