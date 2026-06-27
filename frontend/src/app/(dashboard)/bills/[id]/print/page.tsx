"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface BillLine {
  id: number
  product_id: number | null
  description: string
  qty: string | number
  unit: string | null
  rate: string | number
  amount: string | number
  hs_code: string | null
}
interface Bill {
  id: number
  number: string
  vendor_id: number | null
  vendor_name: string | null
  bill_date: string
  due_date: string
  description: string | null
  notes: string | null
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
  const abs = Math.abs(n)
  const s = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? `(${s})` : s
}

export default function BillPrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

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
  if (!bill) return <p className="p-4 text-[var(--text-primary)]/60 text-sm">Loading bill…</p>

  return (
    <div className="bg-white min-h-screen">
      <div className="print:hidden flex items-center justify-between bg-[var(--text-primary)] text-white px-4 py-2 mb-4">
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm hover:text-[#ffd966]">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--primary)] hover:bg-[#d4af60] text-black rounded-md text-sm font-semibold"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-10">
        <PrintHeader title={`Bill ${bill.number}`} subtitle={`Dated ${fmtDate(bill.bill_date)} · Due ${fmtDate(bill.due_date)}`} />

        <article className="text-[var(--text-primary)]">
          <header className="mb-6 print:hidden border-b border-[var(--border)] pb-4">
            <h1 className="text-lg sm:text-2xl font-bold">Bill {bill.number}</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Dated {fmtDate(bill.bill_date)} · Due {fmtDate(bill.due_date)}</p>
          </header>

          <div className="grid grid-cols-2 gap-6 mb-6 text-sm">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.vendor', 'Vendor')}</div>
              <p className="font-semibold">{bill.vendor_name ?? "—"}</p>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.status', 'Status')}</div>
              <p className="font-semibold uppercase">{bill.status}</p>
              <p className="text-xs text-[var(--text-primary)]/55 mt-1">Currency: {bill.currency}</p>
            </div>
          </div>

          {bill.description && (
            <p className="mb-4 text-sm text-[var(--text-primary)]/75">{bill.description}</p>
          )}

          <table className="w-full text-sm border border-[var(--border)] mb-6">
            <thead className="bg-[var(--bg-page)]">
              <tr>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">{t('col.description', 'Description')}</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-20">Qty</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-28">Rate</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-28">{t('col.amount', 'Amount')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {bill.lines.map(ln => (
                <tr key={ln.id}>
                  <td className="px-3 py-2">
                    <div>{ln.description}</div>
                    {ln.hs_code && <div className="text-[10px] text-[var(--text-primary)]/45 font-mono mt-0.5">HS: {ln.hs_code}</div>}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.qty)} {ln.unit ?? ""}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.rate)}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Notes (vendor-facing) */}
          {bill.notes && (
            <div className="mb-4 text-sm border-l-2 border-[var(--primary)]/40 pl-3 text-[var(--text-primary)]/70 whitespace-pre-wrap">
              {bill.notes}
            </div>
          )}

          <div className="flex justify-end">
            <div className="w-full sm:w-72 space-y-1.5 text-sm">
              <Row label="Subtotal" value={fmt(bill.subtotal)} />
              {Number(bill.gst_rate) > 0 && (
                <Row label={`GST (${fmt(bill.gst_rate)}%)`} value={fmt(bill.gst_amount)} />
              )}
              <div className="border-t border-[var(--text-primary)] pt-1.5 mt-1.5">
                <Row label="Total" value={fmt(bill.total)} bold />
              </div>
            </div>
          </div>

          <footer className="mt-12 pt-6 border-t border-[var(--border)] text-xs text-[var(--text-primary)]/55 leading-relaxed">
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
      <span className={`${bold ? "font-bold" : "text-[var(--text-primary)]/65"}`}>{label}</span>
      <span className={`font-mono ${bold ? "font-bold text-base" : ""}`}>{value}</span>
    </div>
  )
}
