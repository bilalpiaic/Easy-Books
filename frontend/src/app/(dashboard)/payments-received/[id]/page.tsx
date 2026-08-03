"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { Printer, CheckCircle, ChevronRight } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt, useSettings } from "@/context/SettingsContext"
import AttachmentPanel, { AttachmentPreviewPane, type Attachment as AttachmentT } from "@/components/AttachmentPanel"
import { fxGainLossLabel, isForeignCurrency } from "@/lib/fx"
import { useTranslation } from "react-i18next"

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
  currency?: string | null
  exchange_rate?: string | number | null
  method: string
  reference: string | null
  transaction_id: number | null
  allocations: Allocation[]
  cash_base?: string | number | null
  cleared_base?: string | number | null
  realised_fx?: string | number | null
  is_fx?: boolean
}

export default function PaymentReceivedDetail({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const fmt = useFmt()
  const { settings } = useSettings()
  const baseCurrency = settings.currency || "USD"
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
  if (!pay)          return <p className="p-4 text-[var(--text-primary)]/60 text-sm">Loading receipt…</p>

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <nav className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
        <Link href="/payments-received" className="hover:text-[var(--text-muted)] transition-colors">Payments Received</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-[var(--text-muted)]">Receipt #{pay.id}</span>
      </nav>
      <div className="flex justify-end print:hidden">
        <Link href={`/payments-received/${pay.id}/print`} className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)]">
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</Link>
      </div>

      <header className="bg-white border border-[var(--border)] rounded-xl p-5 flex items-start gap-3">
        <CheckCircle className="w-7 h-7 text-[var(--primary)] shrink-0 mt-1" />
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Cash Receipt #{pay.id}</h1>
          <p className="text-sm text-[var(--text-primary)]/60">
            {pay.payment_date} · {pay.method}{pay.reference ? ` · ${pay.reference}` : ""}
            {pay.currency ? ` · ${pay.currency}` : ""}
            {pay.exchange_rate != null && Number(pay.exchange_rate) !== 1
              ? ` @ ${Number(pay.exchange_rate).toFixed(4)}`
              : ""}
          </p>
        </div>
      </header>

      <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="bg-white border border-[var(--border)] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Received From</div>
          {pay.customer_id ? (
            <Link href={`/customers/${pay.customer_id}/ledger`} className="font-semibold text-[var(--text-primary)] hover:text-[var(--primary)] hover:underline">
              {pay.customer_name ?? `#${pay.customer_id}`}
            </Link>
          ) : <span className="font-semibold">{pay.customer_name ?? "—"}</span>}
        </div>
        <div className="bg-white border border-[var(--border)] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Posted Voucher</div>
          {pay.transaction_id ? (
            <Link href={`/journal/${pay.transaction_id}`} className="font-mono text-sm text-[var(--primary)] hover:underline">View JV →</Link>
          ) : <span className="text-sm text-[var(--text-primary)]/55">No voucher</span>}
        </div>
      </section>

      <section className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)]">
            <tr>
              <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Invoice</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Allocated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {pay.allocations.length === 0 ? (
              <tr><td colSpan={2} className="px-4 py-3 text-center text-[var(--text-primary)]/55">No allocations</td></tr>
            ) : pay.allocations.map(a => (
              <tr key={a.id}>
                <td className="px-4 py-2">
                  {a.invoice_id ? (
                    <Link href={`/invoices/${a.invoice_id}`} className="font-mono text-[var(--primary)] hover:underline">
                      {a.invoice_number ?? `INV-${a.invoice_id}`}
                    </Link>
                  ) : "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono">{fmt(Number(a.amount))}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-[var(--bg-page)] border-t border-[var(--text-primary)]">
            <tr>
              <td className="px-4 py-2 text-sm font-bold">
                Total received{pay.currency ? ` (${pay.currency})` : ""}
              </td>
              <td className="px-4 py-2 text-right font-mono font-bold">{fmt(Number(pay.amount))}</td>
            </tr>
            {pay.currency && isForeignCurrency(pay.currency, baseCurrency) && pay.cash_base != null && (
              <>
                <tr>
                  <td className="px-4 py-1.5 text-xs text-[var(--text-muted)]">Cash in {baseCurrency}</td>
                  <td className="px-4 py-1.5 text-right font-mono text-xs">{fmt(Number(pay.cash_base))}</td>
                </tr>
                {pay.cleared_base != null && (
                  <tr>
                    <td className="px-4 py-1.5 text-xs text-[var(--text-muted)]">AR cleared ({baseCurrency})</td>
                    <td className="px-4 py-1.5 text-right font-mono text-xs">{fmt(Number(pay.cleared_base))}</td>
                  </tr>
                )}
                {pay.realised_fx != null && (
                  <tr>
                    <td className="px-4 py-1.5 text-xs text-[var(--text-muted)]">Realised FX (4903)</td>
                    <td className={`px-4 py-1.5 text-right font-mono text-xs font-semibold ${Number(pay.realised_fx) > 0 ? "text-green-700" : Number(pay.realised_fx) < 0 ? "text-red-700" : ""}`}>
                      {fxGainLossLabel(Number(pay.realised_fx), "receipt")}
                    </td>
                  </tr>
                )}
              </>
            )}
          </tfoot>
        </table>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4 print:hidden">
        <AttachmentPanel parentType="payment_received" parentId={pay.id} embedded onSelect={setSelectedAtt} />
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden min-h-[60vh]">
          <AttachmentPreviewPane att={selectedAtt} />
        </div>
      </section>
    </div>
  )
}
