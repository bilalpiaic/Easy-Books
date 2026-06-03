"use client"

import { useEffect, useState } from "react"
import { ScrollText, Search } from "lucide-react"
import { apiFetch } from "@/lib/api"
import DocLink, { DocKind } from "@/components/DocLink"
import Pagination from "@/components/Pagination"
import SkeletonRow from "@/components/SkeletonRow"

interface AuditEntry {
  id: number
  action: string
  entity_type: string
  entity_id: number | null
  detail: string | null
  timestamp: string
  user_name: string
  user_id: number
}

interface AuditResponse {
  total: number
  items: AuditEntry[]
}

const PAGE_SIZE = 50

// Audit entity_type → DocLink kind (only those with a viewable record page).
const ENTITY_LINK: Record<string, DocKind> = {
  invoice: "invoice",
  bill: "bill",
  payment_received: "payment_received",
  bill_payment: "bill_payment",
  credit_note: "credit_note",
  debit_note: "debit_note",
  customer: "customer",
  vendor: "vendor",
  product: "product",
  account: "account",
  fixed_asset: "fixed_asset",
  grn: "grn",
  production_order: "production_order",
  transaction: "jv",
  manual_jv: "jv",
}

function actionClass(action: string) {
  const a = action.toLowerCase()
  if (a.includes("create")) return "bg-green-100 text-green-700"
  if (a.includes("delete") || a.includes("remove") || a.includes("purge")) return "bg-red-100 text-red-700"
  if (a.includes("update") || a.includes("edit")) return "bg-amber-100 text-amber-700"
  return "bg-gray-100 text-gray-700"
}

function prettyDetail(detail: string | null): string {
  if (!detail) return "—"
  try {
    const obj = JSON.parse(detail)
    return Object.entries(obj)
      .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
      .join(" · ")
  } catch {
    return detail
  }
}

function EntityCell({ entry }: { entry: AuditEntry }) {
  const kind = ENTITY_LINK[entry.entity_type]
  const label = `${entry.entity_type.replace(/_/g, " ")}${entry.entity_id != null ? ` #${entry.entity_id}` : ""}`
  if (kind && entry.entity_id != null) {
    return <DocLink type={kind} id={entry.entity_id} label={label} className="text-[#b8943f] font-medium" />
  }
  return <span className="text-[#1a1814]/70">{label}</span>
}

export default function AuditLogPage() {
  const [items, setItems] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [entityFilter, setEntityFilter] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => { setPage(1) }, [entityFilter, dateFrom, dateTo])

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (entityFilter) params.set("entity_type", entityFilter)
    if (dateFrom) params.set("date_from", dateFrom)
    if (dateTo) params.set("date_to", dateTo)
    apiFetch<AuditResponse>(`/api/audit-log?${params}`)
      .then(d => { setItems(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [page, entityFilter, dateFrom, dateTo])

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814] flex items-center gap-2">
            <ScrollText className="w-7 h-7 text-[#b8943f]" /> Audit Log
          </h1>
          <p className="text-sm text-black/60 mt-1">Every change made in your organisation, with a link to the affected record.</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
          <input
            type="text" placeholder="Filter by entity type (e.g. invoice)…"
            value={entityFilter} onChange={e => setEntityFilter(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
          />
        </div>
        <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
          className="px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]" title="From" />
        <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
          className="px-3 py-2 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]" title="To" />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[760px]">
            <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
              <tr>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">When</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">User</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Action</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Entity</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {isLoading ? (
                <SkeletonRow cols={5} />
              ) : items.length === 0 ? (
                <tr><td colSpan={5} className="px-6 py-16 text-center text-black/40">No audit entries for these filters.</td></tr>
              ) : items.map(e => (
                <tr key={e.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="px-6 py-3 text-black/60 whitespace-nowrap">{new Date(e.timestamp).toLocaleString()}</td>
                  <td className="px-6 py-3 font-medium text-[#1a1814]">{e.user_name}</td>
                  <td className="px-6 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide ${actionClass(e.action)}`}>
                      {e.action}
                    </span>
                  </td>
                  <td className="px-6 py-3"><EntityCell entry={e} /></td>
                  <td className="px-6 py-3 text-black/60 max-w-[360px] truncate" title={prettyDetail(e.detail)}>{prettyDetail(e.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="border-t border-[#ede9e2] px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>
    </div>
  )
}
