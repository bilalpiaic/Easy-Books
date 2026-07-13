"use client"

import { useEffect, useMemo, useState } from "react"
import { ScrollText, Search, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import DocLink, { DocKind } from "@/components/DocLink"
import Pagination from "@/components/Pagination"
import SkeletonRow from "@/components/SkeletonRow"
import PrintHeader from "@/components/PrintHeader"
import DateRangePicker from "@/components/DateRangePicker"
import { useTranslation } from "react-i18next"

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

type View = "timeline" | "by_user" | "by_entity"

const PAGE_SIZE = 50
const FETCH_LIMIT = 500

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
  if (a.includes("reverse")) return "bg-purple-100 text-purple-700"
  if (a.includes("update") || a.includes("edit")) return "bg-amber-100 text-amber-700"
  return "bg-blue-100 text-blue-700"
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

function entityLabel(e: AuditEntry) {
  return `${e.entity_type.replace(/_/g, " ")}${e.entity_id != null ? ` #${e.entity_id}` : ""}`
}

function EntityCell({ entry }: { entry: AuditEntry }) {
  const kind = ENTITY_LINK[entry.entity_type]
  if (kind && entry.entity_id != null) {
    return <DocLink type={kind} id={entry.entity_id} label={entityLabel(entry)} className="text-[var(--primary)] font-medium" />
  }
  return <span className="text-[var(--text-primary)]/70">{entityLabel(entry)}</span>
}

function ActionBadge({ action }: { action: string }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide ${actionClass(action)}`}>
      {action}
    </span>
  )
}

export default function AuditLogPage() {
  const { t } = useTranslation()

  const [items, setItems] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [entityFilter, setEntityFilter] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [view, setView] = useState<View>("timeline")
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)

  // Re-fetch a generous batch whenever the filters change; all three views are
  // computed client-side from it (Timeline client-paginates, the groupings roll
  // it up by user / entity type).
  useEffect(() => {
    setIsLoading(true)
    setPage(1)
    const params = new URLSearchParams({ skip: "0", limit: String(FETCH_LIMIT) })
    if (entityFilter) params.set("entity_type", entityFilter)
    if (dateFrom) params.set("date_from", dateFrom)
    if (dateTo) params.set("date_to", dateTo)
    apiFetch<AuditResponse>(`/api/audit-log?${params}`)
      .then(d => { setItems(d.items); setTotal(d.total) })
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [entityFilter, dateFrom, dateTo])

  const byUser = useMemo(() => {
    const m = new Map<string, AuditEntry[]>()
    for (const e of items) { const a = m.get(e.user_name) ?? []; a.push(e); m.set(e.user_name, a) }
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length)
  }, [items])

  const byEntity = useMemo(() => {
    const m = new Map<string, AuditEntry[]>()
    for (const e of items) { const a = m.get(e.entity_type) ?? []; a.push(e); m.set(e.entity_type, a) }
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length)
  }, [items])

  const timelinePage = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const exportCsv = () => {
    const headers = ["Timestamp", "User", "Action", "Entity", "Detail"]
    const rows = items.map(l => [
      new Date(l.timestamp).toLocaleString(), l.user_name, l.action,
      entityLabel(l), prettyDetail(l.detail),
    ])
    const csv = [headers, ...rows].map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n")
    const a = document.createElement("a")
    a.href = "data:text/csv;charset=utf-8," + encodeURIComponent(csv)
    a.download = "audit-log.csv"; a.click()
  }

  const VIEWS: { key: View; label: string }[] = [
    { key: "timeline", label: "Timeline" },
    { key: "by_user", label: "By User" },
    { key: "by_entity", label: "By Type" },
  ]

  return (
    <div className="space-y-6">
      <PrintHeader title="Audit Log" orientation="landscape" />
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <ScrollText className="w-7 h-7 text-[var(--primary)]" /> Audit Log
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Every change made in your organisation, with a link to the affected record.</p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button onClick={exportCsv} className="px-4 py-2 text-sm font-bold border border-[var(--border)] rounded-lg hover:bg-[var(--bg-page)] transition-colors">{t('common.exportCsv', 'Export CSV')}</button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-3 w-4 h-4 text-[var(--text-muted)]" />
          <input
            type="text" placeholder="Filter by entity type (e.g. invoice)…"
            value={entityFilter} onChange={e => setEntityFilter(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
          />
        </div>
        <DateRangePicker start={dateFrom} end={dateTo} onStartChange={setDateFrom} onEndChange={setDateTo} label="Dates" />
      </div>

      {/* View tabs */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {VIEWS.map(v => (
          <button key={v.key} onClick={() => setView(v.key)}
            className={`px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors border-b-2 -mb-px ${
              view === v.key ? "text-[var(--primary)] border-[var(--primary)]" : "text-[var(--text-muted)] border-transparent hover:text-[var(--text-muted)]"
            }`}>
            {v.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm"><tbody className="divide-y divide-[var(--border)]"><SkeletonRow cols={5} /></tbody></table>
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)] py-8 text-center">No audit entries for these filters.</p>
      ) : view === "timeline" ? (
        <div className="bg-white rounded-xl border border-[var(--border)] overflow-hidden">
          <div className="overflow-x-auto table-freeze">
            <table className="w-full text-sm min-w-[760px]">
              <thead className="bg-[var(--bg-page)] border-b border-[var(--border)]">
                <tr>
                  <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">When</th>
                  <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">User</th>
                  <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Action</th>
                  <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Entity</th>
                  <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {timelinePage.map(e => (
                  <tr key={e.id} className="hover:bg-[var(--bg-page)]/50">
                    <td className="ui-td text-[var(--text-muted)] whitespace-nowrap">{new Date(e.timestamp).toLocaleString()}</td>
                    <td className="ui-td font-medium text-[var(--text-primary)]">{e.user_name}</td>
                    <td className="ui-td"><ActionBadge action={e.action} /></td>
                    <td className="ui-td"><EntityCell entry={e} /></td>
                    <td className="ui-td text-[var(--text-muted)] max-w-[360px] truncate" title={prettyDetail(e.detail)}>{prettyDetail(e.detail)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-[var(--border)] px-4">
            <Pagination page={page} pageSize={PAGE_SIZE} total={items.length} onPage={setPage} />
          </div>
          {total > items.length && (
            <p className="px-6 py-2 text-[11px] text-[var(--text-muted)] border-t border-[var(--border)]">
              Showing the most recent {items.length} of {total} entries — narrow the date range to see older activity.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {(view === "by_user" ? byUser : byEntity).map(([key, entries]) => (
            <div key={key} className="border border-[var(--border)] rounded-xl overflow-hidden bg-white">
              <div className="px-4 py-2.5 bg-[var(--bg-page)] flex items-center justify-between">
                <span className="text-sm font-bold text-[var(--text-primary)] capitalize">{key.replace(/_/g, " ")}</span>
                <span className="text-xs text-[var(--text-muted)]">{entries.length} {view === "by_user" ? "action" : "event"}{entries.length !== 1 ? "s" : ""}</span>
              </div>
              <div className="divide-y divide-[var(--border)] max-h-72 overflow-y-auto">
                {entries.slice(0, 50).map(e => (
                  <div key={e.id} className="px-4 py-2 flex items-center gap-3 text-xs">
                    <span className="text-[var(--text-muted)] w-40 flex-shrink-0">{new Date(e.timestamp).toLocaleString()}</span>
                    <ActionBadge action={e.action} />
                    {view === "by_user"
                      ? <EntityCell entry={e} />
                      : <span className="text-[var(--text-muted)] font-medium">{e.user_name}</span>}
                    <span className="text-[var(--text-muted)] truncate ml-auto">{prettyDetail(e.detail)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
