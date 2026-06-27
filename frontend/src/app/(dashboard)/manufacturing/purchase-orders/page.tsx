"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ShoppingCart, Plus, CheckCircle, FileText, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import { EmptyStateGuide } from "@/components/guidance/EmptyStateGuide"
import PrintHeader from "@/components/PrintHeader"
import StatusBadge from "@/components/StatusBadge"
import { useTranslation } from "react-i18next"

interface PurchaseOrder {
  id: number
  number: string
  vendor_name: string | null
  order_date: string
  expected_date: string | null
  total: string
  status: string
}

const STATUSES = ["all", "draft", "approved", "billed", "cancelled"]

export default function PurchaseOrdersPage() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const [pos, setPos] = useState<PurchaseOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState("all")

  const refresh = (status: string) =>
    apiFetch<{ total: number; items: PurchaseOrder[] }>(
      `/api/purchase-orders?limit=100${status !== "all" ? `&status=${status}` : ""}`
    )
      .then(d => setPos(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))

  useEffect(() => {
    refresh(statusFilter).finally(() => setLoading(false))
  }, [statusFilter])

  if (loading) return <p className="text-sm text-[var(--text-primary)]/60">Loading…</p>

  return (
    <div className="space-y-5">
      <PrintHeader title="Purchase Orders" orientation="landscape" />
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <ShoppingCart className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Purchase Orders</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Send orders to vendors before goods arrive.</p>
          </div>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button
            onClick={() => downloadCSV('purchase-orders.csv', pos.map(p => ({ "PO #": p.number, Vendor: p.vendor_name ?? '', "Order Date": p.order_date, "Expected Date": p.expected_date ?? '', Total: p.total, Status: p.status })))}
            disabled={pos.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <Link
            href="/manufacturing/purchase-orders/new"
            className="flex items-center gap-2 px-4 py-2 bg-[var(--text-primary)] text-white rounded-lg text-sm font-bold hover:bg-[var(--primary)] hover:text-black transition-all"
          >
            <Plus className="w-4 h-4" />
            New PO
          </Link>
        </div>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Status filter tabs */}
      <div className="flex gap-2 flex-wrap">
        {STATUSES.map(s => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setLoading(true) }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize border transition-colors ${
              statusFilter === s
                ? "bg-[var(--text-primary)] text-white border-[var(--text-primary)]"
                : "bg-white text-[var(--text-primary)]/70 border-[var(--border)] hover:border-[var(--primary)]/50"
            }`}
          >
            {s === "all" ? "All" : s}
          </button>
        ))}
      </div>

      {pos.length === 0 ? (
        <EmptyStateGuide
          title="No purchase orders yet"
          description="Create a PO to track what you're ordering from a vendor before the goods arrive."
          steps={[
            "Create a PO with vendor name, order date, and line items.",
            "Approve it once reviewed.",
            "Convert to a Bill when the vendor invoice arrives.",
          ]}
        />
      ) : (
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] text-[var(--text-primary)]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">PO #</th>
                <th className="text-left px-4 py-2">{t('col.vendor', 'Vendor')}</th>
                <th className="text-left px-4 py-2">Order Date</th>
                <th className="text-left px-4 py-2">Expected</th>
                <th className="text-right px-4 py-2">{t('col.total', 'Total')}</th>
                <th className="text-center px-4 py-2">{t('col.status', 'Status')}</th>
                <th className="text-right px-4 py-2 w-16"></th>
              </tr>
            </thead>
            <tbody>
              {pos.map(po => (
                <tr key={po.id} className="border-t border-[var(--border)] hover:bg-[#faf8f4] transition-colors">
                  <td className="px-4 py-2 font-mono text-xs font-semibold text-[var(--primary)]">
                    <Link href={`/manufacturing/purchase-orders/${po.id}`}>{po.number}</Link>
                  </td>
                  <td className="px-4 py-2">{po.vendor_name ?? "—"}</td>
                  <td className="px-4 py-2">{po.order_date}</td>
                  <td className="px-4 py-2">{po.expected_date ?? "—"}</td>
                  <td className="px-4 py-2 text-right font-mono">{fmt(Number(po.total))}</td>
                  <td className="px-4 py-2 text-center">
                    <StatusBadge status={po.status} />
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      href={`/manufacturing/purchase-orders/${po.id}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-[var(--border)] text-xs font-semibold hover:bg-[var(--bg-page)] hover:border-[var(--primary)]/50 transition-colors"
                    >
                      {po.status === "draft" ? (
                        <><CheckCircle className="w-3 h-3" />Review</>
                      ) : (
                        <><FileText className="w-3 h-3" />View</>
                      )}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
