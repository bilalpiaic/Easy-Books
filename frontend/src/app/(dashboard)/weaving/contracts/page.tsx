"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { RateKgLb } from "@/components/weaving/WeightDisplays"

type Contract = {
  id: number
  number: string
  customer_id: number
  start_date: string
  end_date?: string | null
  contract_meters: number
  assumed_yarn_rate_per_kg: number
  assumed_yarn_rate_per_lb: number
  weaving_rate: number
  expected_weaving_revenue: number
  status: string
}

type Customer = { id: number; name: string }

export default function ContractsListPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Contract[] | null>(null)
  const [customers, setCustomers] = useState<Record<number, string>>({})
  const [status, setStatus] = useState("")

  useEffect(() => {
    const qs = status ? `?status=${status}` : ""
    Promise.all([
      apiFetch<Contract[]>(`/api/weaving/contracts${qs}`).catch(() => []),
      apiFetch<{ items: Customer[] }>("/api/customers?limit=500").catch(() => ({ items: [] })),
    ]).then(([contracts, custs]) => {
      setRows(Array.isArray(contracts) ? contracts : [])
      const map: Record<number, string> = {}
      for (const c of custs.items ?? []) map[c.id] = c.name
      setCustomers(map)
    })
  }, [status])

  return (
    <div className="p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-2">
          <select
            value={status}
            onChange={e => setStatus(e.target.value)}
            className="px-3 py-2 text-sm border border-[var(--border)] rounded-lg"
          >
            <option value="">All statuses</option>
            {["draft", "in_process", "completed", "delayed", "cancelled"].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <Link href="/weaving/contracts/new"
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Contract
        </Link>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Contract #</th>
              <th className="px-3 py-2">Customer</th>
              <th className="px-3 py-2">Start</th>
              <th className="px-3 py-2 text-right">Meters</th>
              <th className="px-3 py-2">Yarn rate</th>
              <th className="px-3 py-2 text-right">Weaving rate</th>
              <th className="px-3 py-2 text-right">Expected rev.</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(c => (
              <tr key={c.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/weaving/contracts/${c.id}`} className="text-[var(--primary)]">{c.number}</Link>
                </td>
                <td className="px-3 py-2">{customers[c.customer_id] || `#${c.customer_id}`}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(c.start_date)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(c.contract_meters)}</td>
                <td className="px-3 py-2">
                  <RateKgLb ratePerKg={c.assumed_yarn_rate_per_kg} ratePerLbValue={c.assumed_yarn_rate_per_lb} />
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(c.weaving_rate)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(c.expected_weaving_revenue)}</td>
                <td className="px-3 py-2 capitalize">{c.status.replace("_", " ")}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-[var(--text-muted)]">No contracts yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
