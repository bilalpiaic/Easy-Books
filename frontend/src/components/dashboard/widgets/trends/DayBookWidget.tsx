"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { BookOpen } from "lucide-react"
import { useFmt } from "@/context/SettingsContext"
import { fetchDayBook, type DayBookData } from "@/lib/dashboardTrends"

const VOUCHER_LABELS: Record<string, string> = {
  JV: "Journal", SL: "Sales", PU: "Purchase",
  CR: "Cash Receipt", CP: "Cash Payment", BR: "Bank Receipt", BP: "Bank Payment",
  CN: "Credit Note", DN: "Debit Note", PR: "Payroll",
}

function Heading({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/45 mt-3 mb-1.5 first:mt-0">
      {children}
    </p>
  )
}

function Row({ label, count, amount }: { label: string; count: number; amount?: string }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1 border-b border-[var(--border)]/60 last:border-0">
      <span className="text-xs text-[var(--text-primary)]/75 truncate">{label}</span>
      <span className="flex items-center gap-2 flex-shrink-0">
        <span className="text-[10px] font-semibold bg-[var(--bg-page)] text-[var(--text-muted)] rounded-full px-1.5 py-0.5">{count}</span>
        {amount !== undefined && <span className="text-xs font-semibold text-[var(--text-primary)] tabular-nums">{amount}</span>}
      </span>
    </div>
  )
}

/** Day Book: one day's activity under main headings — vouchers by type,
 *  source documents, and the audit-trail category view (financial and
 *  non-financial activity alike). */
export default function DayBookWidget() {
  const fmt = useFmt()
  const [date, setDate] = useState(() => new Date().toISOString().split("T")[0])
  const [book, setBook] = useState<DayBookData | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    setBook(null)
    setError(false)
    fetchDayBook(date)
      .then(b => { if (alive) setBook(b) })
      .catch(() => { if (alive) setError(true) })
    return () => { alive = false }
  }, [date])

  const docs = book ? [
    { label: "Invoices issued", ...book.documents.invoices },
    { label: "Bills recorded", ...book.documents.bills },
    { label: "Payments received", ...book.documents.payments_received },
    { label: "Payments made", ...book.documents.payments_made },
  ].filter(d => d.count > 0) : []

  const isEmpty = !!book && book.vouchers.length === 0 && docs.length === 0 && book.activity.length === 0

  return (
    <div className="h-full flex flex-col bg-white border border-[var(--border)] rounded-xl p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]/55 flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5 text-[#b8943f]" /> Day Book
          </p>
          <p className="text-[10px] text-[var(--text-primary)]/40 mt-0.5">All activity for the selected day</p>
        </div>
        <input
          type="date" value={date} onChange={e => e.target.value && setDate(e.target.value)}
          className="text-[11px] border border-[var(--border)] rounded-lg px-2 py-1 bg-white text-[var(--text-primary)] flex-shrink-0"
        />
      </div>

      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !book ? (
        <div className="shimmer flex-1 rounded-lg" />
      ) : isEmpty ? (
        <div className="flex-1 flex items-center justify-center text-sm text-[var(--text-primary)]/40">No activity on this day.</div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto pr-1">
          {book.vouchers.length > 0 && (
            <>
              <Heading>Vouchers</Heading>
              {book.vouchers.map(v => (
                <Row key={v.type} label={VOUCHER_LABELS[v.type] ?? v.type} count={v.count} amount={fmt(Number(v.total))} />
              ))}
              <div className="flex items-center justify-between gap-2 py-1 mt-0.5">
                <span className="text-xs font-bold text-[var(--text-primary)]/80">Total</span>
                <span className="flex items-center gap-2">
                  <span className="text-[10px] font-semibold bg-[var(--bg-page)] text-[var(--text-muted)] rounded-full px-1.5 py-0.5">{book.voucher_totals.count}</span>
                  <span className="text-xs font-bold text-[var(--text-primary)] tabular-nums">{fmt(Number(book.voucher_totals.total))}</span>
                </span>
              </div>
            </>
          )}

          {docs.length > 0 && (
            <>
              <Heading>Documents</Heading>
              {docs.map(d => (
                <Row key={d.label} label={d.label} count={d.count} amount={fmt(Number(d.total))} />
              ))}
            </>
          )}

          {book.activity.length > 0 && (
            <>
              <Heading>Activity by Category</Heading>
              <div className="flex flex-wrap gap-1.5">
                {book.activity.map(a => (
                  <span key={a.category} className="text-[10px] font-medium bg-[var(--bg-page)] text-[var(--text-primary)]/70 rounded-full px-2 py-0.5">
                    {a.category.replace(/_/g, " ")} · {a.count}
                  </span>
                ))}
              </div>
              <Link href="/audit" className="inline-block text-[11px] text-[#b8943f] font-semibold hover:text-[#8a6d2e] mt-2">
                Audit Log →
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  )
}
