"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import type { WeightTriple } from "@/lib/spinningUnits"

const STAGE_ORDER = ["opening", "carding", "drawing", "roving", "spinning", "winding"]

type Stage = {
  id: number
  number: string
  stage: string
  date: string
  input_kg: number
  output_kg: number
  waste_kg: number
  yield_pct: number
  status: string
}

type Lot = {
  id: number
  number: string
  yarn_spec_id: number
  start_date: string
  target_output_kg: number
  target_weight: WeightTriple
  output_kg: number
  output_weight: WeightTriple
  status: string
  material_cost: number
  labour_cost: number
  overhead_cost: number
  waste_cost: number
  total_cost: number
  cost_per_kg: number
  notes?: string | null
  stages: Stage[]
  bale_receipts: { id: number; number: string; date: string; net_kg: number }[]
  cone_outputs: { id: number; number: string; date: string; net_kg: number; cones_count: number }[]
}

export default function LotDetailPage() {
  const { id } = useParams<{ id: string }>()
  const fmt = useFmt()
  const [lot, setLot] = useState<Lot | null>(null)
  const [specName, setSpecName] = useState("")
  const [acting, setActing] = useState(false)

  const load = useCallback(async () => {
    const row = await apiFetch<Lot>(`/api/spinning/lots/${id}`).catch(() => null)
    if (!row) return
    setLot(row)
    const specs = await apiFetch<{ id: number; code: string; name: string }[]>("/api/spinning/yarn-specs").catch(() => [])
    const s = Array.isArray(specs) ? specs.find(x => x.id === row.yarn_spec_id) : undefined
    if (s) setSpecName(`${s.code} — ${s.name}`)
  }, [id])

  useEffect(() => { load() }, [load])

  async function action(path: "start" | "complete" | "close") {
    if (!lot) return
    setActing(true)
    try {
      await apiFetch(`/api/spinning/lots/${lot.id}/${path}`, { method: "PATCH" })
      load()
    } finally {
      setActing(false)
    }
  }

  if (!lot) return <div className="p-4 text-sm text-[var(--text-muted)]">Loading…</div>

  const stagesByName = Object.fromEntries(lot.stages.map(s => [s.stage, s]))
  const latestStageIdx = STAGE_ORDER.reduce((max, st, i) => (stagesByName[st] ? i : max), -1)

  return (
    <div className="p-4 max-w-4xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">{lot.number}</h1>
          <p className="text-sm text-[var(--text-muted)]">
            {specName || `Spec #${lot.yarn_spec_id}`} · started {fmtDate(lot.start_date)}
            {" · "}<span className="capitalize">{lot.status.replace("_", " ")}</span>
          </p>
        </div>
        <div className="flex gap-2 print:hidden">
          <Link href={`/spinning/reports/lot-control?lot=${lot.id}`} className="px-3 py-2 text-sm rounded-lg border border-[var(--border)]">
            Control panel
          </Link>
          {lot.status === "draft" && (
            <button onClick={() => action("start")} disabled={acting} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50">Start</button>
          )}
          {lot.status === "in_process" && (
            <button onClick={() => action("complete")} disabled={acting} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50">Complete</button>
          )}
          {lot.status === "completed" && (
            <button onClick={() => action("close")} disabled={acting} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50">Close</button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-3">
          <div className="text-xs text-[var(--text-muted)]">Target</div>
          <WeightTripleDisplay triple={lot.target_weight} />
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-3">
          <div className="text-xs text-[var(--text-muted)]">Output</div>
          <WeightTripleDisplay triple={lot.output_weight} />
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-3">
          <div className="text-xs text-[var(--text-muted)]">Total cost</div>
          <div className="font-medium tabular-nums">{fmt(lot.total_cost)}</div>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-3">
          <div className="text-xs text-[var(--text-muted)]">Cost / kg</div>
          <div className="font-medium tabular-nums">{fmt(lot.cost_per_kg)}</div>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
        <h2 className="text-sm font-semibold mb-4">Stage timeline</h2>
        <div className="flex flex-wrap gap-2">
          {STAGE_ORDER.map((st, i) => {
            const entry = stagesByName[st]
            const done = !!entry
            const current = i === latestStageIdx + 1 && lot.status === "in_process"
            return (
              <div key={st}
                className={`flex-1 min-w-[100px] rounded-lg border p-2 text-center text-xs ${
                  done ? "border-[var(--primary)] bg-[var(--primary)]/5" :
                  current ? "border-amber-500 bg-amber-500/5" :
                  "border-[var(--border)] opacity-60"
                }`}>
                <div className="font-medium capitalize">{st}</div>
                {entry ? (
                  <>
                    <div className="text-[var(--text-muted)] mt-1">{fmtDate(entry.date)}</div>
                    <div className="tabular-nums">{fmt(entry.yield_pct)}% yield</div>
                  </>
                ) : (
                  <div className="text-[var(--text-muted)] mt-1">—</div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {lot.stages.length > 0 && (
        <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-muted)]">
                <th className="px-3 py-2">SE #</th>
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Stage</th>
                <th className="px-3 py-2 text-right">Input kg</th>
                <th className="px-3 py-2 text-right">Output kg</th>
                <th className="px-3 py-2 text-right">Waste kg</th>
                <th className="px-3 py-2 text-right">Yield %</th>
              </tr>
            </thead>
            <tbody>
              {lot.stages.map(s => (
                <tr key={s.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2 whitespace-nowrap">{s.number}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{fmtDate(s.date)}</td>
                  <td className="px-3 py-2 capitalize">{s.stage}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(s.input_kg)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(s.output_kg)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(s.waste_kg)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(s.yield_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4 text-sm">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-3">
          <h3 className="font-medium mb-2">Bale receipts ({lot.bale_receipts.length})</h3>
          {lot.bale_receipts.length === 0 ? (
            <p className="text-[var(--text-muted)]">None linked</p>
          ) : (
            <ul className="space-y-1">
              {lot.bale_receipts.map(b => (
                <li key={b.id} className="flex justify-between">
                  <span>{b.number}</span>
                  <span className="text-[var(--text-muted)]">{fmtDate(b.date)} · {fmt(b.net_kg)} kg</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-3">
          <h3 className="font-medium mb-2">Cone outputs ({lot.cone_outputs.length})</h3>
          {lot.cone_outputs.length === 0 ? (
            <p className="text-[var(--text-muted)]">None yet</p>
          ) : (
            <ul className="space-y-1">
              {lot.cone_outputs.map(c => (
                <li key={c.id} className="flex justify-between">
                  <span>{c.number}</span>
                  <span className="text-[var(--text-muted)]">{fmtDate(c.date)} · {c.cones_count} cones · {fmt(c.net_kg)} kg</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {lot.notes && (
        <div className="text-sm text-[var(--text-muted)]">Notes: {lot.notes}</div>
      )}
    </div>
  )
}
