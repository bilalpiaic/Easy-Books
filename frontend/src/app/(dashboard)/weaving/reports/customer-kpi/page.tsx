"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import KpiCard from "@/components/dashboard/KpiCard"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { formatWeightTriple, type WeightTriple } from "@/lib/weavingUnits"

type Kpi = {
  portfolio: {
    total_contracts: number
    in_process: number
    completed: number
    delayed: number
    draft: number
    cancelled: number
    total_value: number
    yarn_received: WeightTriple
    yarn_used: WeightTriple
    yarn_balance: WeightTriple
  }
  contracts: {
    contract_id: number
    number: string
    customer_name: string
    status: string
    contract_meters: number
    expected_value: number
    yarn_received: WeightTriple
    yarn_used: WeightTriple
    yarn_balance: WeightTriple
  }[]
}

export default function CustomerKpiPage() {
  const fmt = useFmt()
  const [data, setData] = useState<Kpi | null>(null)

  useEffect(() => {
    apiFetch<Kpi>("/api/weaving/reports/customer-kpi").then(setData).catch(() => setData(null))
  }, [])

  const p = data?.portfolio

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title="Customer & Contract KPI" orientation="landscape" />
      <div className="print:hidden">
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Customer & Contract KPI</h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard title="Total contracts" value={p ? String(p.total_contracts) : null} />
        <KpiCard title="In process" value={p ? String(p.in_process) : null} tone="blue" />
        <KpiCard title="Completed" value={p ? String(p.completed) : null} tone="green" />
        <KpiCard title="Delayed" value={p ? String(p.delayed) : null} tone="amber" />
        <KpiCard title="Portfolio value" value={p ? fmt(p.total_value) : null} tone="emerald" />
        <KpiCard title="Yarn received" value={p ? formatWeightTriple(p.yarn_received) : null}
          sub={p ? `${p.yarn_received.lbs.toFixed(1)} lb · ${p.yarn_received.bags.toFixed(2)} bags` : undefined} />
        <KpiCard title="Yarn used" value={p ? formatWeightTriple(p.yarn_used) : null}
          sub={p ? `${p.yarn_used.lbs.toFixed(1)} lb · ${p.yarn_used.bags.toFixed(2)} bags` : undefined} />
        <KpiCard title="Yarn balance" value={p ? formatWeightTriple(p.yarn_balance) : null}
          sub={p ? `${p.yarn_balance.lbs.toFixed(1)} lb · ${p.yarn_balance.bags.toFixed(2)} bags` : undefined} />
      </div>

      <div className="table-freeze freeze-col rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Contract</th>
              <th className="px-3 py-2">Customer</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right">Meters</th>
              <th className="px-3 py-2 text-right">Value</th>
              <th className="px-3 py-2">Yarn received</th>
              <th className="px-3 py-2">Yarn used</th>
              <th className="px-3 py-2">Yarn balance</th>
            </tr>
          </thead>
          <tbody>
            {(data?.contracts ?? []).map(r => (
              <tr key={r.contract_id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/weaving/contracts/${r.contract_id}`} className="text-[var(--primary)]">{r.number}</Link>
                </td>
                <td className="px-3 py-2">{r.customer_name || "—"}</td>
                <td className="px-3 py-2 capitalize">{r.status.replace("_", " ")}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.contract_meters)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.expected_value)}</td>
                <td className="px-3 py-2"><WeightTripleDisplay triple={r.yarn_received} /></td>
                <td className="px-3 py-2"><WeightTripleDisplay triple={r.yarn_used} /></td>
                <td className="px-3 py-2"><WeightTripleDisplay triple={r.yarn_balance} /></td>
              </tr>
            ))}
            {!data?.contracts?.length && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-[var(--text-muted)]">No contracts</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
