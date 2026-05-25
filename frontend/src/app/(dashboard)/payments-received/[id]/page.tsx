"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { Printer, CheckCircle, ChevronRight } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtPKR } from "@/lib/utils"
import AttachmentPanel, { AttachmentPreviewPane, type Attachment as AttachmentT } from "@/components/AttachmentPanel"

interface Allocation {
  id: number
  invoice_id: number | null
  invoice_number: string | null
  amount: string | number
}
interface Payment {
  id: number
  customer_id: number | null
  customer_name: string | null
  payment_date: string
  amount: string | number
  method: string
  reference: string | null
  transaction_id: number | null
  allocations: Allocation[]
}

export default function PaymentReceivedDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [pay, setPay] = useState<Payment | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedAtt, setSelectedAtt] = useState<AttachmentT | null>(null)

  useEffect(() => {
    apiFetch<Payment>(`/api/payments-received/${id}`)
      .then(setPay)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error && !pay) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!pay)          return <p className="p-4 text-[#1a1814]/60 text-sm">Loading receipt…</p>

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <nav className="flex items-center gap-1.5 text-xs text-black/40">
        <Link href="/payments-received" className="hover:text-black/70 transition-colors">Payments Received</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-black/60">Receipt #{pay.id}</span>
      </nav>
      <div className="flex justify-end">
        <Link href={`/payments-received/${pay.id}/print`} className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee]">
          <Printer className="w-4 h-4" /> Print
        </Link>
      </div>

      <header className="bg-white border border-[#ede9e2] rounded-xl p-5 flex items-start gap-3">
        <CheckCircle className="w-7 h-7 text-[#b8943f] shrink-0 mt-1" />
        <div className="min-w-0">
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Cash Receipt #{pay.id}</h1>
          <p className="text-sm text-[#1a1814]/60">
            {pay.payment_date} · {pay.method}{pay.reference ? ` · ${pay.reference}` : ""}
          </p>
        </div>
      </header>

      <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="bg-white border border-[#ede9e2] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Received From</div>
          {pay.customer_id ? (
            <Link href={`/customers/${pay.customer_id}/ledger`} className="font-semibold text-[#1a1814] hover:text-[#b8943f] hover:underline">
              {pay.customer_name ?? `#${pay.customer_id}`}
            </Link>
          ) : <span className="font-semibold">{pay.customer_name ?? "—"}</span>}
        </div>
        <div className="bg-white border border-[#ede9e2] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Posted Voucher</div>
          {pay.transaction_id ? (
            <Link href={`/journal/${pay.transaction_id}`} className="font-mono text-sm text-[#b8943f] hover:underline">View JV →</Link>
          ) : <span className="text-sm text-[#1a1814]/55">No voucher</span>}
        </div>
      </section>

      <section className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#faf6ec]">
            <tr>
              <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Invoice</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Allocated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {pay.allocations.length === 0 ? (
              <tr><td colSpan={2} className="px-4 py-3 text-center text-[#1a1814]/55">No allocations</td></tr>
            ) : pay.allocations.map(a => (
              <tr key={a.id}>
                <td className="px-4 py-2">
                  {a.invoice_id ? (
                    <Link href={`/invoices/${a.invoice_id}`} className="font-mono text-[#b8943f] hover:underline">
                      {a.invoice_number ?? `INV-${a.invoice_id}`}
                    </Link>
                  ) : "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono">{fmtPKR(Number(a.amount))}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-[#faf6ec] border-t border-[#1a1814]">
            <tr>
              <td className="px-4 py-2 text-sm font-bold">Total received</td>
              <td className="px-4 py-2 text-right font-mono font-bold">{fmtPKR(Number(pay.amount))}</td>
            </tr>
          </tfoot>
        </table>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4 print:hidden">
        <AttachmentPanel parentType="payment_received" parentId={pay.id} embedded onSelect={setSelectedAtt} />
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-hidden min-h-[60vh]">
          <AttachmentPreviewPane att={selectedAtt} />
        </div>
      </section>
    </div>
  )
}
