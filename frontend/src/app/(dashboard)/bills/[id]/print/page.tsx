"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import PrintHeader from "@/components/PrintHeader"

interface BillLine {
  id: number
  product_id: number | null
  description: string
  qty: string | number
  unit: string | null
  rate: string | number
  amount: string | number
}
interface Bill {
  id: number
  number: string
  vendor_id: number | null
  vendor_name: string | null
  bill_date: string
  due_date: string
  description: string | null
  subtotal: string | number
  gst_rate: string | number
  gst_amount: string | number
  total: string | number
  currency: string
  status: string
  lines: BillLine[]
}

const fmt = (v: string | number) => {
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function BillPrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [bill, setBill]   = useState<Bill | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Bill>(`/api/bills/${id}`)
      .then(d => { setBill(d); setTimeout(() => window.print(), 300) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!bill) return <p className="p-4 text-[#1a1814]/60 text-sm">Loading bill…</p>

  return (
    <div className="bg-white min-h-screen">
      <div className="print:hidden flex items-center justify-between bg-[#1a1814] text-white px-4 py-2 mb-4">
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm hover:text-[#ffd966]">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#b8943f] hover:bg-[#d4af60] text-black rounded-md text-sm font-semibold"
        >
          <Printer className="w-4 h-4" /> Print
        </button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-10">
        <PrintHeader title={`Bill ${bill.number}`} subtitle={`Dated ${bill.bill_date} · Due ${bill.due_date}`} />

        <article className="text-[#1a1814]">
          <header className="mb-6 print:hidden border-b border-[#ede9e2] pb-4">
            <h1 className="text-2xl font-serif font-semibold">Bill {bill.number}</h1>
            <p className="text-sm text-[#1a1814]/60">Dated {bill.bill_date} · Due {bill.due_date}</p>
          </header>

          <div className="grid grid-cols-2 gap-6 mb-6 text-sm">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Vendor</div>
              <p className="font-semibold">{bill.vendor_name ?? "—"}</p>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Status</div>
              <p className="font-semibold uppercase">{bill.status}</p>
              <p className="text-xs text-[#1a1814]/55 mt-1">Currency: {bill.currency}</p>
            </div>
          </div>

          {bill.description && (
            <p className="mb-4 text-sm text-[#1a1814]/75">{bill.description}</p>
          )}

          <table className="w-full text-sm border border-[#ede9e2] mb-6">
            <thead className="bg-[#faf6ec]">
              <tr>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Description</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-20">Qty</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Rate</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {bill.lines.map(ln => (
                <tr key={ln.id}>
                  <td className="px-3 py-2">{ln.description}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.qty)} {ln.unit ?? ""}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.rate)}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="flex justify-end">
            <div className="w-full sm:w-72 space-y-1.5 text-sm">
              <Row label="Subtotal" value={fmt(bill.subtotal)} />
              {Number(bill.gst_rate) > 0 && (
                <Row label={`GST (${fmt(bill.gst_rate)}%)`} value={fmt(bill.gst_amount)} />
              )}
              <div className="border-t border-[#1a1814] pt-1.5 mt-1.5">
                <Row label="Total" value={fmt(bill.total)} bold />
              </div>
            </div>
          </div>

          <footer className="mt-12 pt-6 border-t border-[#ede9e2] text-xs text-[#1a1814]/55 leading-relaxed">
            <p>All amounts in {bill.currency}. Posted to vendor ledger and AP.</p>
          </footer>
        </article>
      </div>
    </div>
  )
}

function Row({ label, value, bold = false }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className={`${bold ? "font-bold" : "text-[#1a1814]/65"}`}>{label}</span>
      <span className={`font-mono ${bold ? "font-bold text-base" : ""}`}>{value}</span>
    </div>
  )
}
