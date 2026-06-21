"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ShoppingCart, Plus, CheckCircle, FileText, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import { EmptyStateGuide } from "@/components/guidance/EmptyStateGuide"
import PrintHeader from "@/components/PrintHeader"

interface PurchaseOrder {
  id: number
  number: string
  vendor_name: string | null
  order_date: string
  expected_date: string | null
  total: string
  status: string
}

const STATUS_TONE: Record<string, string> = {
  draft:     "bg-slate-100 text-slate-700",
  approved:  "bg-blue-100 text-blue-800",
  billed:    "bg-emerald-100 text-emerald-800",
  cancelled: "bg-red-100 text-red-800",
}

const STATUSES = ["all", "draft", "approved", "billed", "cancelled"]

export default function PurchaseOrdersPage() {
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

  if (loading) return <p className="text-sm text-[#1a1814]/60">Loading…</p>

  return (
    <div className="space-y-5">
      <PrintHeader title="Purchase Orders" orientation="landscape" />
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <ShoppingCart className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Purchase Orders</h1>
            <p className="text-sm text-[#1a1814]/60">Send orders to vendors before goods arrive.</p>
          </div>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
          <button
            onClick={() => downloadCSV('purchase-orders.csv', pos.map(p => ({ "PO #": p.number, Vendor: p.vendor_name ?? '', "Order Date": p.order_date, "Expected Date": p.expected_date ?? '', Total: p.total, Status: p.status })))}
            disabled={pos.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <Link
            href="/manufacturing/purchase-orders/new"
            className="flex items-center gap-2 px-4 py-2 bg-[#1a1814] text-white rounded-lg text-sm font-bold hover:bg-[#b8943f] hover:text-black transition-all"
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
                ? "bg-[#1a1814] text-white border-[#1a1814]"
                : "bg-white text-[#1a1814]/70 border-[#ede9e2] hover:border-[#b8943f]/50"
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
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#faf6ec] text-[#1a1814]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">PO #</th>
                <th className="text-left px-4 py-2">Vendor</th>
                <th className="text-left px-4 py-2">Order Date</th>
                <th className="text-left px-4 py-2">Expected</th>
                <th className="text-right px-4 py-2">Total</th>
                <th className="text-center px-4 py-2">Status</th>
                <th className="text-right px-4 py-2 w-16"></th>
              </tr>
            </thead>
            <tbody>
              {pos.map(po => (
                <tr key={po.id} className="border-t border-[#ede9e2] hover:bg-[#faf8f4] transition-colors">
                  <td className="px-4 py-2 font-mono text-xs font-semibold text-[#b8943f]">
                    <Link href={`/manufacturing/purchase-orders/${po.id}`}>{po.number}</Link>
                  </td>
                  <td className="px-4 py-2">{po.vendor_name ?? "—"}</td>
                  <td className="px-4 py-2">{po.order_date}</td>
                  <td className="px-4 py-2">{po.expected_date ?? "—"}</td>
                  <td className="px-4 py-2 text-right font-mono">{fmt(Number(po.total))}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-semibold capitalize ${STATUS_TONE[po.status] ?? "bg-gray-100 text-gray-700"}`}>
                      {po.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      href={`/manufacturing/purchase-orders/${po.id}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-[#ede9e2] text-xs font-semibold hover:bg-[#faf6ec] hover:border-[#b8943f]/50 transition-colors"
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
