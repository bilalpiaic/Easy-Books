"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface Allocation {
  id: number
  bill_id: number | null
  bill_number: string | null
  amount: string | number
}
interface BillPayment {
  id: number
  bill_id: number | null
  vendor_name: string | null
  payment_date: string
  amount: string | number
  method: string
  reference: string | null
  allocations: Allocation[]
}

const fmt = (v: string | number) => {
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  const abs = Math.abs(n)
  const s = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? `(${s})` : s
}

export default function VoucherPrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const { id } = use(params)
  const router = useRouter()
  const [pay, setPay]     = useState<BillPayment | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<BillPayment>(`/api/bill-payments/${id}`)
      .then(d => { setPay(d); setTimeout(() => window.print(), 300) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!pay)  return <p className="p-4 text-[#1a1814]/60 text-sm">Loading voucher…</p>

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
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-10">
        <PrintHeader title={`Payment Voucher #${pay.id}`} subtitle={`Paid on ${fmtDate(pay.payment_date)}`} />

        <article className="text-[#1a1814]">
          <header className="mb-6 print:hidden border-b border-[#ede9e2] pb-4">
            <h1 className="text-2xl font-serif font-semibold">Voucher #{pay.id}</h1>
            <p className="text-sm text-[#1a1814]/60">Paid on {fmtDate(pay.payment_date)}</p>
          </header>

          <div className="grid grid-cols-2 gap-6 mb-6 text-sm">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Paid To</div>
              <p className="font-semibold">{pay.vendor_name ?? "—"}</p>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Method</div>
              <p className="font-semibold uppercase">{pay.method}</p>
              {pay.reference && (
                <p className="text-xs text-[#1a1814]/55 mt-1">Ref: {pay.reference}</p>
              )}
            </div>
          </div>

          <div className="bg-[#faf6ec] border border-[#ede9e2] rounded p-5 mb-6 flex items-end justify-between">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Amount Paid</span>
            <span className="text-3xl font-bold font-mono text-[#1a1814]">{fmt(pay.amount)}</span>
          </div>

          {pay.allocations.length > 0 ? (
            <>
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-2">Applied To</h2>
              <table className="w-full text-sm border border-[#ede9e2] mb-6">
                <thead className="bg-[#faf6ec]">
                  <tr>
                    <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Bill</th>
                    <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">{t('col.amount', 'Amount')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ede9e2]">
                  {pay.allocations.map(a => (
                    <tr key={a.id}>
                      <td className="px-3 py-2 font-mono">{a.bill_number ?? `#${a.bill_id}`}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmt(a.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : pay.bill_id ? (
            <p className="text-xs text-[#1a1814]/55 mb-6">Applied directly to bill #{pay.bill_id}.</p>
          ) : null}

          <div className="flex justify-between mt-16 pt-6 border-t border-[#ede9e2] text-xs text-[#1a1814]/55">
            <div className="text-center w-40">
              <div className="border-t border-[#1a1814]/30 pt-1">Prepared By</div>
            </div>
            <div className="text-center w-40">
              <div className="border-t border-[#1a1814]/30 pt-1">Approved By</div>
            </div>
            <div className="text-center w-40">
              <div className="border-t border-[#1a1814]/30 pt-1">Received By</div>
            </div>
          </div>
        </article>
      </div>
    </div>
  )
}
