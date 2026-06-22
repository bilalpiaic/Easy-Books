"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useSettings } from "@/context/SettingsContext"

const PAYMENT_MODE: Record<number, string> = {
  1: "Cash", 2: "Card", 3: "Gift Voucher", 4: "Loyalty Card", 5: "Mixed", 6: "Cheque",
}

interface Line {
  description: string
  qty: string | number
  rate: string | number
  amount: string | number
  tax_rate?: string | number | null
}

interface Invoice {
  id: number
  number: string
  customer_name: string | null
  issue_date: string
  subtotal: string | number
  gst_rate: string | number
  gst_amount: string | number
  total: string | number
  currency: string
  payment_mode: number | null
  pra_fiscal_number: string | null
  lines: Line[]
}

const r2 = (v: string | number) => {
  const n = Number(v)
  return Number.isNaN(n) ? "0.00" : Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function ReceiptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const { settings } = useSettings()
  const [inv, setInv] = useState<Invoice | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Invoice>(`/api/invoices/${id}`)
      .then(d => {
        setInv(d)
        setTimeout(() => window.print(), 300)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!inv)  return <p className="p-4 text-[#1a1814]/60 text-sm">Loading receipt…</p>

  return (
    <>
      {/* Screen toolbar — hidden when printing */}
      <div className="print:hidden flex items-center justify-between bg-[#1a1814] text-white px-4 py-2 mb-4">
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm hover:text-[#ffd966]">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#b8943f] hover:bg-[#d4af60] text-black rounded-md text-sm font-semibold"
        >
          <Printer className="w-4 h-4" /> Print Receipt
        </button>
      </div>

      {/* Receipt body — 80mm width for thermal POS */}
      <div className="receipt-body bg-white mx-auto text-[#1a1814] font-mono text-xs" style={{ width: "80mm", padding: "4mm" }}>
        {/* Header */}
        <div className="text-center mb-3">
          <p className="font-bold text-sm">{settings.company_name}</p>
          {settings.pra_pos_id && <p className="text-[10px] text-[#1a1814]/60">POS ID: {settings.pra_pos_id}</p>}
        </div>

        <div className="border-t border-dashed border-[#1a1814]/30 my-2" />

        {/* Invoice meta */}
        <div className="mb-2 space-y-0.5">
          <div className="flex justify-between">
            <span className="text-[#1a1814]/60">Invoice</span>
            <span className="font-bold">{inv.number}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#1a1814]/60">Date</span>
            <span>{fmtDate(inv.issue_date)}</span>
          </div>
          {inv.customer_name && (
            <div className="flex justify-between">
              <span className="text-[#1a1814]/60">Customer</span>
              <span className="text-right max-w-[40mm] truncate">{inv.customer_name}</span>
            </div>
          )}
          {inv.payment_mode && (
            <div className="flex justify-between">
              <span className="text-[#1a1814]/60">Payment</span>
              <span>{PAYMENT_MODE[inv.payment_mode] ?? inv.payment_mode}</span>
            </div>
          )}
        </div>

        <div className="border-t border-dashed border-[#1a1814]/30 my-2" />

        {/* Line items */}
        <table className="w-full text-[10px] mb-2">
          <thead>
            <tr className="text-[#1a1814]/60">
              <th className="text-left font-normal">Item</th>
              <th className="text-right font-normal">Qty</th>
              <th className="text-right font-normal">Rate</th>
              <th className="text-right font-normal">Amt</th>
            </tr>
          </thead>
          <tbody>
            {inv.lines.map((ln, i) => (
              <tr key={i}>
                <td className="text-left">{ln.description}</td>
                <td className="text-right">{Number(ln.qty)}</td>
                <td className="text-right">{r2(ln.rate)}</td>
                <td className="text-right">{r2(ln.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="border-t border-dashed border-[#1a1814]/30 my-2" />

        {/* Totals */}
        <div className="space-y-0.5 mb-2">
          <div className="flex justify-between">
            <span className="text-[#1a1814]/60">Subtotal</span>
            <span>{r2(inv.subtotal)}</span>
          </div>
          {Number(inv.gst_rate) > 0 && (
            <div className="flex justify-between">
              <span className="text-[#1a1814]/60">GST ({Number(inv.gst_rate)}%)</span>
              <span>{r2(inv.gst_amount)}</span>
            </div>
          )}
          <div className="flex justify-between font-bold text-sm border-t border-[#1a1814]/20 pt-1 mt-1">
            <span>TOTAL {inv.currency}</span>
            <span>{r2(inv.total)}</span>
          </div>
        </div>

        {/* FIN */}
        {inv.pra_fiscal_number && (
          <>
            <div className="border-t border-dashed border-[#1a1814]/30 my-2" />
            <div className="text-center space-y-2">
              <p className="text-[9px] text-[#1a1814]/55 uppercase tracking-widest">PRA Fiscal Invoice No</p>
              <p className="font-bold text-sm tracking-wider">{inv.pra_fiscal_number}</p>
              <div className="flex justify-center mt-1">
                <QRCodeSVG value={inv.pra_fiscal_number} size={80} />
              </div>
            </div>
          </>
        )}

        <div className="border-t border-dashed border-[#1a1814]/30 my-2" />
        <p className="text-center text-[9px] text-[#1a1814]/50">Thank you for your business</p>
      </div>

      {/* 80mm page CSS — injected print style */}
      <style>{`
        @media print {
          @page { size: 80mm auto; margin: 0; }
          body > *:not(.receipt-body) { display: none !important; }
          .receipt-body { display: block !important; }
          .print\\:hidden { display: none !important; }
        }
      `}</style>
    </>
  )
}
