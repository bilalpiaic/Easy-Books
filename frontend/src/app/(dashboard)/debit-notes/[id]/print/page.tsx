"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface Line { id: number; description: string; qty: number; rate: number; amount: number; unit: string | null }
interface DebitNote {
  id: number
  number: string
  bill_id: number
  vendor_id: number | null
  vendor_name: string | null
  issue_date: string
  description: string | null
  subtotal: number
  gst_amount: number
  total: number
  status: string
  lines: Line[]
}

const fmt = (v: number) => {
  const n = v || 0
  const abs = Math.abs(n)
  const s = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? `(${s})` : s
}

export default function DebitNotePrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const { id } = use(params)
  const router = useRouter()
  const [dn, setDn]       = useState<DebitNote | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<DebitNote>(`/api/debit-notes/${id}`)
      .then(d => { setDn(d); setTimeout(() => window.print(), 300) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!dn)   return <p className="p-4 text-[var(--text-primary)]/60 text-sm">Loading…</p>

  return (
    <div className="bg-white min-h-screen">
      <div className="print:hidden flex items-center justify-between bg-[var(--text-primary)] text-white px-4 py-2 mb-4">
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm hover:text-[var(--primary)]">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--primary)] hover:bg-[var(--primary-dark)] text-black rounded-md text-sm font-semibold"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-10">
        <PrintHeader title={`Debit Note ${dn.number}`} subtitle={`Issued ${fmtDate(dn.issue_date)} · ${dn.status.toUpperCase()}`} />

        <article className="text-[var(--text-primary)]">
          <header className="mb-6 print:hidden border-b border-[var(--border)] pb-4">
            <h1 className="text-lg sm:text-2xl font-bold">Debit Note {dn.number}</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Issued {fmtDate(dn.issue_date)} · {dn.status}</p>
          </header>

          <div className="grid grid-cols-2 gap-6 mb-6 text-sm">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.vendor', 'Vendor')}</div>
              <p className="font-semibold">{dn.vendor_name ?? "—"}</p>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Original Bill</div>
              <p className="font-semibold">Bill #{dn.bill_id}</p>
            </div>
          </div>

          {dn.description && (
            <p className="mb-4 text-sm text-[var(--text-primary)]/75">{dn.description}</p>
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
              {dn.lines.map(ln => (
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
              <Row label="Subtotal" value={fmt(dn.subtotal)} />
              {dn.gst_amount > 0 && <Row label="GST reversed" value={fmt(dn.gst_amount)} />}
              <div className="border-t border-[var(--text-primary)] pt-1.5 mt-1.5">
                <Row label="Total Return" value={fmt(dn.total)} bold />
              </div>
            </div>
          </div>

          <footer className="mt-12 pt-6 border-t border-[var(--border)] text-xs text-[var(--text-primary)]/55 leading-relaxed">
            <p>This debit note evidences a purchase return and reduces the outstanding balance on the referenced bill.</p>
            <p className="mt-1">GL: Dr Accounts Payable / Cr Inventory (at original cost) + Cr GST Input.</p>
          </footer>
        </article>
      </div>
    </div>
  )
}

function Row({ label, value, bold = false }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className={bold ? "font-bold" : "text-[var(--text-primary)]/65"}>{label}</span>
      <span className={`font-mono ${bold ? "font-bold text-base" : ""}`}>{value}</span>
    </div>
  )
}
