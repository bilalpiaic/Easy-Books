"use client"

import { use, useEffect, useState } from "react"
import { Receipt, Printer } from "lucide-react"
import { useBreadcrumb } from "@/context/BreadcrumbContext"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import DocLink from "@/components/DocLink"

interface Line { id: number; description: string; qty: number; rate: number; amount: number; unit: string | null }
interface CreditNoteDetail {
  id: number
  number: string
  invoice_id: number | null
  customer_id: number | null
  customer_name: string | null
  issue_date: string
  description: string | null
  subtotal: number
  gst_amount: number
  total: number
  status: string
  transaction_id: number | null
  lines: Line[]
}

export default function CreditNoteDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const fmt = useFmt()
  const [cn, setCn] = useState<CreditNoteDetail | null>(null)
  const [loading, setLoading] = useState(true)
  useBreadcrumb(cn ? cn.number : undefined)

  useEffect(() => {
    apiFetch<CreditNoteDetail>(`/api/credit-notes/${id}`)
      .then(d => { setCn(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [id])

  if (loading) return <div className="text-center py-20 text-[#1a1814]/50">Loading…</div>
  if (!cn) return <div className="text-center py-20 text-[#1a1814]/50">Credit note not found.</div>

  return (
    <div className="max-w-3xl mx-auto space-y-6">

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#1a1814] flex items-center justify-center flex-shrink-0">
            <Receipt className="w-5 h-5 text-[#ffd966]" />
          </div>
          <div>
            <h1 className="text-2xl font-serif text-[#1a1814]">{cn.number}</h1>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mt-0.5">Credit Note / Sales Return · {cn.status}</p>
          </div>
        </div>
        <button onClick={() => window.print()} className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] text-[#1a1814]/60 print:hidden" title="Print">
          <Printer className="w-5 h-5" />
        </button>
      </div>

      <div className="bg-white border border-[#ede9e2] rounded-xl p-5 grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[#1a1814]/50">Customer</p>
          <p className="mt-0.5">{cn.customer_id
            ? <DocLink type="customer" id={cn.customer_id} label={cn.customer_name ?? "Customer"} />
            : (cn.customer_name ?? "—")}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[#1a1814]/50">Original Invoice</p>
          <p className="mt-0.5">{cn.invoice_id
            ? <DocLink type="invoice" id={cn.invoice_id} label={`Invoice #${cn.invoice_id}`} />
            : "—"}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[#1a1814]/50">Issue Date</p>
          <p className="mt-0.5 text-[#1a1814]/70">{cn.issue_date}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[#1a1814]/50">Journal Entry</p>
          <p className="mt-0.5">{cn.transaction_id
            ? <DocLink type="jv" id={cn.transaction_id} label={`JV-${String(cn.transaction_id).padStart(5, "0")}`} />
            : "—"}</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee]">
            <tr>{["Description", "Qty", "Rate", "Amount"].map(h => (
              <th key={h} className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/50">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {cn.lines.map(l => (
              <tr key={l.id} className="border-t border-[#1a1814]/5">
                <td className="px-4 py-2">{l.description}</td>
                <td className="px-4 py-2 font-mono">{l.qty}</td>
                <td className="px-4 py-2 font-mono">{fmt(l.rate)}</td>
                <td className="px-4 py-2 font-mono">{fmt(l.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-3 border-t border-[#ede9e2] text-sm space-y-1">
          <div className="flex justify-between"><span className="text-[#1a1814]/60">Subtotal</span><span className="font-mono">{fmt(cn.subtotal)}</span></div>
          {cn.gst_amount > 0 && <div className="flex justify-between"><span className="text-[#1a1814]/60">GST reversed</span><span className="font-mono">{fmt(cn.gst_amount)}</span></div>}
          <div className="flex justify-between font-bold border-t border-[#ede9e2] pt-1"><span>Total Credit</span><span className="font-mono text-red-600">({fmt(cn.total)})</span></div>
        </div>
      </div>
      <p className="text-xs text-[#1a1814]/40 italic">GL: Dr Sales Revenue (+ Dr GST Payable) / Cr Accounts Receivable. Stock lines also Dr Inventory / Cr COGS.</p>
    </div>
  )
}
