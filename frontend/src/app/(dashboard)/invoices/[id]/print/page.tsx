"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface InvoiceLine {
  id: number
  product_id: number | null
  description: string
  qty: string | number
  unit: string | null
  rate: string | number
  amount: string | number
  hs_code: string | null
  pct_code: string | null
  tax_rate: string | number | null
}
interface Invoice {
  id: number
  number: string
  customer_id: number | null
  customer_name: string | null
  issue_date: string
  due_date: string
  description: string | null
  notes: string | null
  subtotal: string | number
  gst_rate: string | number
  gst_amount: string | number
  total: string | number
  currency: string
  status: string
  lines: InvoiceLine[]
  pra_fiscal_number?: string | null
  buyer_ntn?: string | null
  buyer_cnic?: string | null
  payment_mode?: number | null
}

const fmt = (v: string | number) => {
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  const abs = Math.abs(n)
  const s = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? `(${s})` : s
}

export default function InvoicePrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const { id } = use(params)
  const router = useRouter()
  const [inv, setInv]     = useState<Invoice | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Invoice>(`/api/invoices/${id}`)
      .then(d => {
        setInv(d)
        // Auto-trigger the print dialog once the data is in the DOM
        setTimeout(() => window.print(), 300)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error)  return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!inv)   return <p className="p-4 text-[#1a1814]/60 text-sm">Loading invoice…</p>

  return (
    <div className="bg-white min-h-screen">
      {/* Screen-only toolbar */}
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
        <PrintHeader title={`Invoice ${inv.number}`} subtitle={`Issued ${fmtDate(inv.issue_date)} · Due ${fmtDate(inv.due_date)}`} />

        {/* Document body */}
        <article className="text-[#1a1814]">
          <div className="mb-6 hidden print:block">
            {/* PrintHeader already shown above; this leaves space below */}
          </div>

          {/* On-screen document title (the PrintHeader handles the printed one) */}
          <header className="mb-6 print:hidden border-b border-[#ede9e2] pb-4">
            <h1 className="text-lg sm:text-2xl font-serif font-semibold">Invoice {inv.number}</h1>
            <p className="text-sm text-[#1a1814]/60">Issued {fmtDate(inv.issue_date)} · Due {fmtDate(inv.due_date)}</p>
            {inv.pra_fiscal_number && (
              <p className="text-xs text-[#1a1814]/60 mt-0.5">PRA Fiscal Invoice No: <span className="font-mono">{inv.pra_fiscal_number}</span></p>
            )}
          </header>
          {/* PRA Fiscal Invoice Number badge */}
          {inv.pra_fiscal_number && (
            <div className="mb-4 border border-[#b8943f]/40 rounded-lg px-4 py-2 bg-[#faf6ec]">
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-0.5">Fiscal Invoice No (PRA)</p>
              <p className="text-sm font-bold font-mono text-[#b8943f]">{inv.pra_fiscal_number}</p>
            </div>
          )}

          {/* Customer block */}
          <div className="grid grid-cols-2 gap-6 mb-6 text-sm">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Bill To</div>
              <p className="font-semibold">{inv.customer_name ?? "—"}</p>
              {inv.buyer_ntn && (
                <p className="text-xs text-[#1a1814]/60 font-mono mt-0.5">NTN: {inv.buyer_ntn}</p>
              )}
              {inv.buyer_cnic && (
                <p className="text-xs text-[#1a1814]/60 font-mono mt-0.5">CNIC: {inv.buyer_cnic}</p>
              )}
            </div>
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">{t('col.status', 'Status')}</div>
              <p className="font-semibold uppercase">{inv.status}</p>
              <p className="text-xs text-[#1a1814]/55 mt-1">Currency: {inv.currency}</p>
            </div>
          </div>

          {inv.description && (
            <p className="mb-4 text-sm text-[#1a1814]/75">{inv.description}</p>
          )}

          {/* Lines */}
          <table className="w-full text-sm border border-[#ede9e2] mb-6">
            <thead className="bg-[#faf6ec]">
              <tr>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">{t('col.description', 'Description')}</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-20">Qty</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Rate</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">{t('col.amount', 'Amount')}</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-20 hidden print:table-cell">PCT Code</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-16 hidden print:table-cell">Tax %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {inv.lines.map(ln => (
                <tr key={ln.id}>
                  <td className="px-3 py-2">
                    <div>{ln.description}</div>
                    {ln.hs_code && <div className="text-[10px] text-[#1a1814]/45 font-mono mt-0.5">HS: {ln.hs_code}</div>}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.qty)} {ln.unit ?? ""}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.rate)}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.amount)}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs hidden print:table-cell">{ln.pct_code ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs hidden print:table-cell">{ln.tax_rate != null ? `${ln.tax_rate}%` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Notes (customer-facing) */}
          {inv.notes && (
            <div className="mb-4 text-sm border-l-2 border-[#b8943f]/40 pl-3 text-[#1a1814]/70 whitespace-pre-wrap">
              {inv.notes}
            </div>
          )}

          {/* Totals */}
          <div className="flex justify-end">
            <div className="w-full sm:w-72 space-y-1.5 text-sm">
              <Row label="Subtotal" value={fmt(inv.subtotal)} />
              {Number(inv.gst_rate) > 0 && (
                <Row label={`GST (${fmt(inv.gst_rate)}%)`} value={fmt(inv.gst_amount)} />
              )}
              <div className="border-t border-[#1a1814] pt-1.5 mt-1.5">
                <Row label="Total" value={fmt(inv.total)} bold />
              </div>
            </div>
          </div>

          <footer className="mt-12 pt-6 border-t border-[#ede9e2] text-xs text-[#1a1814]/55 leading-relaxed">
            <p>Thank you for your business. Please remit payment by the due date shown above.</p>
            <p className="mt-1">All amounts in {inv.currency}.</p>
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
