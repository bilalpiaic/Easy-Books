"use client"

import { use, useEffect, useState } from "react"
import { Printer, ArrowLeft } from "lucide-react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import PrintHeader from "@/components/PrintHeader"

interface POLine {
  id: number
  description: string
  qty: string
  unit: string | null
  rate: string
  amount: string
}

interface PurchaseOrder {
  id: number
  number: string
  vendor_id: number | null
  vendor_name: string | null
  order_date: string
  expected_date: string | null
  description: string | null
  notes: string | null
  subtotal: string
  total: string
  status: string
  lines: POLine[]
}

const fmtNum = (v: string | number) => {
  const n = Number(v)
  if (isNaN(n)) return String(v)
  const abs = Math.abs(n)
  const s = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? `(${s})` : s
}

const STATUS_LABEL: Record<string, string> = {
  draft:     "DRAFT",
  approved:  "APPROVED",
  billed:    "BILLED",
  cancelled: "CANCELLED",
}

export default function PurchaseOrderPrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [po, setPo] = useState<PurchaseOrder | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<PurchaseOrder>(`/api/purchase-orders/${id}`)
      .then(setPo)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-6 text-red-600 text-sm">{error}</p>
  if (!po)   return <p className="p-6 text-[#1a1814]/50 text-sm">Loading…</p>

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 text-[#1a1814]">
      {/* Screen-only toolbar */}
      <div className="flex items-center justify-between mb-6 print:hidden">
        <Link
          href={`/manufacturing/purchase-orders/${id}`}
          className="flex items-center gap-1.5 text-sm text-[#1a1814]/60 hover:text-[#b8943f]"
        >
          <ArrowLeft className="w-4 h-4" /> Back to PO
        </Link>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-xl text-sm font-bold hover:bg-[#a07c35] transition-colors"
        >
          <Printer className="w-4 h-4" /> Print
        </button>
      </div>

      <PrintHeader title="Purchase Order" />

      {/* PO header */}
      <div className="flex items-start justify-between mt-6 mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">PURCHASE ORDER</h1>
          <p className="text-sm text-[#1a1814]/60 mt-1 font-mono">{po.number}</p>
        </div>
        <span className="px-3 py-1 border border-[#b8943f] rounded-full text-xs font-bold text-[#b8943f] print:border-black print:text-black">
          {STATUS_LABEL[po.status] ?? po.status.toUpperCase()}
        </span>
      </div>

      {/* Vendor + dates */}
      <div className="grid grid-cols-2 gap-6 mb-6 text-sm">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-[#1a1814]/50 mb-1">Vendor</p>
          <p className="font-semibold">{po.vendor_name ?? "—"}</p>
        </div>
        <div className="text-right">
          <div className="mb-1">
            <span className="text-xs font-bold uppercase tracking-widest text-[#1a1814]/50">Order Date: </span>
            <span>{po.order_date}</span>
          </div>
          {po.expected_date && (
            <div>
              <span className="text-xs font-bold uppercase tracking-widest text-[#1a1814]/50">Expected: </span>
              <span>{po.expected_date}</span>
            </div>
          )}
        </div>
      </div>

      {po.description && (
        <p className="text-sm mb-5 text-[#1a1814]/75">{po.description}</p>
      )}

      {/* Line items */}
      <table className="w-full text-sm border-collapse mb-6">
        <thead>
          <tr className="border-b-2 border-[#1a1814]">
            <th className="text-left py-2 font-bold uppercase tracking-wide text-xs">Description</th>
            <th className="text-right py-2 w-16 font-bold uppercase tracking-wide text-xs">Qty</th>
            <th className="text-left py-2 w-16 pl-2 font-bold uppercase tracking-wide text-xs">Unit</th>
            <th className="text-right py-2 w-24 font-bold uppercase tracking-wide text-xs">Unit Rate</th>
            <th className="text-right py-2 w-28 font-bold uppercase tracking-wide text-xs">Amount</th>
          </tr>
        </thead>
        <tbody>
          {po.lines.map(ln => (
            <tr key={ln.id} className="border-b border-[#ede9e2]">
              <td className="py-2">{ln.description}</td>
              <td className="py-2 text-right font-mono">{fmtNum(ln.qty)}</td>
              <td className="py-2 pl-2 text-[#1a1814]/60">{ln.unit ?? "pcs"}</td>
              <td className="py-2 text-right font-mono">{fmtNum(ln.rate)}</td>
              <td className="py-2 text-right font-mono font-semibold">{fmtNum(ln.amount)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-[#1a1814]">
            <td colSpan={4} className="py-2 text-right text-xs font-bold uppercase tracking-widest">Total</td>
            <td className="py-2 text-right font-mono font-bold">{fmtNum(po.total)}</td>
          </tr>
        </tfoot>
      </table>

      {po.notes && (
        <div className="border border-[#ede9e2] rounded-lg px-4 py-3 text-sm text-[#1a1814]/70 mb-6">
          <p className="font-semibold text-xs uppercase tracking-widest mb-1">Notes</p>
          <p>{po.notes}</p>
        </div>
      )}

      <p className="text-xs text-[#1a1814]/45 text-center mt-8 print:mt-12">
        This is a purchase order — not a tax invoice. Goods/services are subject to receipt inspection and acceptance.
      </p>
    </div>
  )
}
