"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import Pagination from "@/components/Pagination"

type SILine = { id: number; product_id: number; qty: number; unit_cost: number }

type StoreIssue = {
  id: number; number: string; issue_date: string
  location_name?: string; debit_account_name?: string; analytic_account_name?: string
  lines: SILine[]
}

const PAGE_SIZE = 50

export default function StoreIssueListPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<StoreIssue[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  useEffect(() => {
    const params = new URLSearchParams({
      skip: String((page - 1) * PAGE_SIZE),
      limit: String(PAGE_SIZE),
    })
    apiFetch<{ total: number; items: StoreIssue[] }>(`/api/store-issues?${params}`)
      .then(d => { setRows(d.items); setTotal(d.total) })
      .catch(() => { setRows([]); setTotal(0) })
  }, [page])

  const cost = (si: StoreIssue) => si.lines.reduce((sum, l) => sum + Number(l.qty) * Number(l.unit_cost), 0)

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-end print:hidden">
        <Link href="/store/issues/new"
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Store Issue
        </Link>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">SI #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Location</th>
              <th className="px-3 py-2">Debit Account</th>
              <th className="px-3 py-2">Analytic Account</th>
              <th className="px-3 py-2 text-right">Cost</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(si => (
              <tr key={si.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap">
                  <Link href={`/store/issues/${si.id}`} className="text-[var(--primary)]">{si.number}</Link>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(si.issue_date)}</td>
                <td className="px-3 py-2">{si.location_name || "—"}</td>
                <td className="px-3 py-2">{si.debit_account_name || "—"}</td>
                <td className="px-3 py-2">{si.analytic_account_name || "—"}</td>
                <td className="px-3 py-2 text-right">{fmt(cost(si))}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">
                No store issues recorded yet.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
    </div>
  )
}
