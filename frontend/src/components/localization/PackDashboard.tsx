"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  PlusCircle, CheckCircle2, XCircle, Clock, FileSignature, ChevronRight,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt, useSettings } from "@/context/SettingsContext"
import { useModules } from "@/context/ModuleContext"
import { fmtDateJs } from "@/lib/utils"

export type PackInvoice = {
  id: number
  number: string
  customer_name: string
  issue_date: string
  total: number
  status?: string
  gst_amount?: number
  zatca_status?: string | null
  peppol_status?: string | null
  peppol_document_id?: string | null
  zatca_uuid?: string | null
  pra_status?: string
  pra_fiscal_number?: string | null
  /** Enriched client-side (e.g. UAE from logs) */
  pack_status?: string | null
  pack_ref?: string | null
}

type InvoiceList = { total: number; items: PackInvoice[] }

export type PackDashboardConfig = {
  moduleId: string
  title: string
  subtitle: string
  statusColumn: string
  logsHref: string
  logsLabel: string
  successStatuses: string[]
  failStatuses: string[]
  pendingStatuses: string[]
  /** Read status from invoice fields; override via enrichInvoices for log-based packs */
  statusOf: (inv: PackInvoice) => string | null | undefined
  refOf?: (inv: PackInvoice) => string | null | undefined
  refColumn?: string
  secondaryLinks?: { href: string; label: string }[]
  enrichInvoices?: (invoices: PackInvoice[]) => Promise<PackInvoice[]>
  /** When false, hide the failed-submission callout (filing packs). */
  showFailBanner?: boolean
}

function statusBadge(
  status: string | null | undefined,
  success: string[],
  fail: string[],
  pending: string[],
) {
  const s = (status || "—").toLowerCase()
  if (success.includes(s))
    return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-100 text-green-700">{status}</span>
  if (fail.includes(s))
    return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700">{status}</span>
  if (pending.includes(s))
    return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">{status}</span>
  return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">{status || "—"}</span>
}

export default function PackDashboard({ config }: { config: PackDashboardConfig }) {
  const router = useRouter()
  const fmt = useFmt()
  const { settings } = useSettings()
  const { installedModules, loading: modulesLoading } = useModules()
  const currency = settings.currency ?? "PKR"
  const installed = installedModules.has(config.moduleId)

  const [invoices, setInvoices] = useState<PackInvoice[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (modulesLoading) return
    if (!installed) router.replace("/dashboard")
  }, [modulesLoading, installed, router])

  useEffect(() => {
    if (modulesLoading || !installed) return
    let cancelled = false
    const today = new Date().toISOString().slice(0, 10)
    setLoading(true)
    apiFetch<InvoiceList>(`/api/invoices?date_from=${today}&date_to=${today}&limit=100&sort_by=issue_date&sort_dir=desc`)
      .then(async (d) => {
        const items = config.enrichInvoices
          ? await config.enrichInvoices(d.items)
          : d.items
        if (!cancelled) setInvoices(items)
      })
      .catch(() => { if (!cancelled) setInvoices([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- pack identity is moduleId
  }, [modulesLoading, installed, config.moduleId])

  const kpis = useMemo(() => {
    const todayCount = invoices.length
    const todaySales = invoices.reduce((s, i) => s + Number(i.total || 0), 0)
    const gstTotal = invoices.reduce((s, i) => s + Number(i.gst_amount || 0), 0)
    let ok = 0, fail = 0, pending = 0
    for (const inv of invoices) {
      const st = (config.statusOf(inv) || "").toLowerCase()
      if (config.successStatuses.includes(st)) ok++
      else if (config.failStatuses.includes(st)) fail++
      else if (config.pendingStatuses.includes(st)) pending++
    }
    return { todayCount, todaySales, gstTotal, ok, fail, pending }
  }, [invoices, config])

  const recent = invoices.slice(0, 8)
  const todayLabel = fmtDateJs(new Date())

  if (modulesLoading || !installed) {
    return <div className="p-8 text-center text-sm text-[var(--text-muted)]">Loading…</div>
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[var(--text-primary)]">{config.title}</h1>
          <p className="text-xs text-[var(--text-primary)]/50 mt-0.5">
            {config.subtitle} · {todayLabel}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {config.secondaryLinks?.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="px-3 py-2 rounded-xl border border-[var(--border)] text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-row-hover)]"
            >
              {l.label}
            </Link>
          ))}
          <Link
            href="/invoices/new"
            className="flex items-center gap-2 px-4 py-2.5 bg-[var(--primary)] hover:bg-[#a07830] text-white rounded-xl font-semibold text-sm transition-colors shadow-sm"
          >
            <PlusCircle className="w-4 h-4" />
            New Invoice
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)] shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Today&apos;s Sales</p>
          <p className="text-2xl font-bold text-[var(--primary)] mt-1 tabular-nums">{fmt(kpis.todaySales)}</p>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
            {kpis.todayCount} invoice{kpis.todayCount !== 1 ? "s" : ""} · {currency}
          </p>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)] shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Submitted / OK</p>
          <p className="text-2xl font-bold text-green-600 mt-1 tabular-nums">{kpis.ok}</p>
          <div className="flex items-center gap-1 mt-0.5">
            <CheckCircle2 className="w-3 h-3 text-green-500" />
            <p className="text-[11px] text-[var(--text-muted)]">of {kpis.todayCount}</p>
          </div>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)] shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Failed / Pending</p>
          <p className="text-2xl font-bold text-red-500 mt-1 tabular-nums">{kpis.fail}</p>
          <div className="flex items-center gap-1 mt-0.5">
            {kpis.pending > 0 ? (
              <>
                <Clock className="w-3 h-3 text-amber-500" />
                <p className="text-[11px] text-[var(--text-muted)]">{kpis.pending} pending</p>
              </>
            ) : (
              <p className="text-[11px] text-[var(--text-muted)]">0 pending</p>
            )}
          </div>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)] shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Tax on sales</p>
          <p className="text-2xl font-bold text-[var(--text-primary)] mt-1 tabular-nums">{fmt(kpis.gstTotal)}</p>
          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">GST / VAT on today&apos;s invoices</p>
        </div>
      </div>

      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <div className="flex items-center gap-2">
            <FileSignature className="w-4 h-4 text-[var(--primary)]" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Today&apos;s Invoices</h2>
          </div>
          <Link href="/invoices" className="flex items-center gap-1 text-xs text-[var(--primary)] hover:underline">
            View all <ChevronRight className="w-3 h-3" />
          </Link>
        </div>

        {loading ? (
          <div className="p-8 text-center text-sm text-[var(--text-muted)]">Loading…</div>
        ) : recent.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm text-[var(--text-muted)] mb-3">No invoices yet today</p>
            <Link
              href="/invoices/new"
              className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium"
            >
              <PlusCircle className="w-4 h-4" />
              Create first invoice
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--bg-page)]/60">
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Invoice #</th>
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Customer</th>
                  <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Amount</th>
                  <th className="text-center px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">{config.statusColumn}</th>
                  {config.refColumn && (
                    <th className="px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] hidden md:table-cell">
                      {config.refColumn}
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {recent.map((inv, idx) => (
                  <tr
                    key={inv.id}
                    className={`border-b border-[var(--border)] hover:bg-[var(--bg-page)]/60 cursor-pointer ${idx % 2 ? "bg-[var(--bg-page)]/30" : ""}`}
                    onClick={() => router.push(`/invoices/${inv.id}`)}
                  >
                    <td className="px-4 py-2.5 font-mono text-xs text-[var(--primary)] whitespace-nowrap">{inv.number}</td>
                    <td className="px-4 py-2.5 truncate max-w-[140px]">{inv.customer_name || "Walk-in"}</td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums">{fmt(Number(inv.total))}</td>
                    <td className="px-4 py-2.5 text-center">
                      {statusBadge(
                        config.statusOf(inv),
                        config.successStatuses,
                        config.failStatuses,
                        config.pendingStatuses,
                      )}
                    </td>
                    {config.refColumn && (
                      <td className="px-4 py-2.5 font-mono text-[10px] text-[var(--text-muted)] hidden md:table-cell">
                        {config.refOf?.(inv) ?? "—"}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {config.showFailBanner !== false && kpis.fail > 0 && (
        <div className="flex items-center gap-3 p-3 rounded-xl bg-red-50 border border-red-200">
          <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-red-700">
              {kpis.fail} invoice{kpis.fail !== 1 ? "s" : ""} failed {config.statusColumn} submission
            </p>
            <p className="text-xs text-red-500">Check submission logs to retry</p>
          </div>
          <Link href={config.logsHref} className="text-xs font-bold text-red-700 hover:underline whitespace-nowrap">
            {config.logsLabel} →
          </Link>
        </div>
      )}
    </div>
  )
}
