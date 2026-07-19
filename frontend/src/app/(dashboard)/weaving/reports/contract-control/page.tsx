"use client"

import { Suspense, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import KpiCard from "@/components/dashboard/KpiCard"
import { RateKgLb, WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { formatWeightTriple, type WeightTriple } from "@/lib/weavingUnits"

type ContractOpt = { id: number; number: string }
type Control = {
  contract: {
    id: number
    number: string
    status: string
    contract_meters: number
    assumed_yarn_rate_per_kg: number
    assumed_yarn_rate_per_lb: number
    weaving_rate: number
    start_date: string
    end_date?: string | null
  }
  progress_pct: number
  yarn_received: WeightTriple
  yarn_sized: WeightTriple
  yarn_used: WeightTriple
  yarn_balance: WeightTriple
  grey_meters: number
  dispatch_meters: number
  finished_stock_m: number
  activity: {
    date: string
    type: string
    number: string
    kg?: number
    lbs?: number
    bags?: number
    meters?: number
  }[]
}

function ContractControlInner() {
  const fmt = useFmt()
  const sp = useSearchParams()
  const [contracts, setContracts] = useState<ContractOpt[]>([])
  const [contractId, setContractId] = useState(sp.get("contract") || "")
  const [data, setData] = useState<Control | null>(null)

  useEffect(() => {
    apiFetch<ContractOpt[]>("/api/weaving/contracts").then(c => {
      const list = Array.isArray(c) ? c : []
      setContracts(list)
      if (!contractId && list[0]) setContractId(String(list[0].id))
    }).catch(() => setContracts([]))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!contractId) { setData(null); return }
    apiFetch<Control>(`/api/weaving/reports/contract-control?contract_id=${contractId}`)
      .then(setData)
      .catch(() => setData(null))
  }, [contractId])

  const c = data?.contract

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title="Contract Control Panel" orientation="landscape" />
      <div className="flex flex-wrap items-center gap-3 print:hidden">
        <label className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Contract</label>
        <select
          value={contractId}
          onChange={e => setContractId(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--border)] rounded-lg"
        >
          <option value="">Select…</option>
          {contracts.map(x => <option key={x.id} value={x.id}>{x.number}</option>)}
        </select>
        {c && (
          <Link href={`/weaving/contracts/${c.id}`} className="text-sm text-[var(--primary)]">Open contract</Link>
        )}
      </div>

      {!contractId ? (
        <p className="text-sm text-[var(--text-muted)]">Select a contract to view the control panel.</p>
      ) : !data ? (
        <p className="text-sm text-[var(--text-muted)]">Loading…</p>
      ) : (
        <>
          <div className="text-sm text-[var(--text-muted)]">
            {c!.number} · <span className="capitalize">{c!.status.replace("_", " ")}</span>
            {" · "}{fmtDate(c!.start_date)}
            {c!.end_date ? ` → ${fmtDate(c!.end_date)}` : ""}
            {" · "}Yarn rate <RateKgLb ratePerKg={c!.assumed_yarn_rate_per_kg} ratePerLbValue={c!.assumed_yarn_rate_per_lb} />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KpiCard title="Progress" value={`${fmt(data.progress_pct)}%`} tone="blue" />
            <KpiCard title="Yarn received" value={formatWeightTriple(data.yarn_received)}
              sub={`${data.yarn_received.lbs.toFixed(1)} lb · ${data.yarn_received.bags.toFixed(2)} bags`} />
            <KpiCard title="Yarn sized" value={formatWeightTriple(data.yarn_sized)}
              sub={`${data.yarn_sized.lbs.toFixed(1)} lb · ${data.yarn_sized.bags.toFixed(2)} bags`} />
            <KpiCard title="Yarn used" value={formatWeightTriple(data.yarn_used)} />
            <KpiCard title="Yarn balance" value={formatWeightTriple(data.yarn_balance)} tone="green" />
            <KpiCard title="Grey meters" value={fmt(data.grey_meters)} />
            <KpiCard title="Dispatched m" value={fmt(data.dispatch_meters)} />
            <KpiCard title="Finished stock m" value={fmt(data.finished_stock_m)} />
          </div>

          <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--text-muted)]">
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Doc #</th>
                  <th className="px-3 py-2">Yarn (Kg/Lbs/Bags)</th>
                  <th className="px-3 py-2 text-right">Meters</th>
                </tr>
              </thead>
              <tbody>
                {data.activity.map((a, i) => (
                  <tr key={`${a.number}-${i}`} className="border-t border-[var(--border)]">
                    <td className="px-3 py-2 whitespace-nowrap">{fmtDate(a.date)}</td>
                    <td className="px-3 py-2 capitalize">{a.type.replace("_", " ")}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{a.number}</td>
                    <td className="px-3 py-2">
                      {a.kg != null ? <WeightTripleDisplay kg={a.kg} lbs={a.lbs} bags={a.bags} /> : "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{a.meters != null ? fmt(a.meters) : "—"}</td>
                  </tr>
                ))}
                {!data.activity.length && (
                  <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--text-muted)]">No activity</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

export default function ContractControlPage() {
  return (
    <Suspense fallback={<div className="p-4 text-sm text-[var(--text-muted)]">Loading…</div>}>
      <ContractControlInner />
    </Suspense>
  )
}
