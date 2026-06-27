"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

// ── Types ─────────────────────────────────────────────────────────────────

interface Entry {
  account_id: number
  account_name: string
  account_type: string
  debit: string | number
  credit: string | number
}

interface Txn {
  id: number
  jv_number: string
  voucher_type: string
  date: string
  description: string | null
  reference: string | null
  party: string | null
  payment_method: string | null
  notes: string | null
  entries: Entry[]
}

// ── Helpers ───────────────────────────────────────────────────────────────

const fmt = (v: string | number) => {
  const n = Number(v)
  if (Number.isNaN(n) || n === 0) return ""
  const abs = Math.abs(n)
  const s = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? `(${s})` : s
}

const fmtAmt = (n: number) => {
  const abs = Math.abs(n)
  const s = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? `(${s})` : s
}

/** Convert a positive number to English words (up to 999,999,999). */
function amountInWords(amount: number): string {
  if (amount === 0) return "Zero Only"
  const ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
    "Eighteen", "Nineteen"]
  const tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

  function below1000(n: number): string {
    if (n === 0) return ""
    if (n < 20) return ones[n]
    if (n < 100) return tens[Math.floor(n / 10)] + (n % 10 ? " " + ones[n % 10] : "")
    return ones[Math.floor(n / 100)] + " Hundred" + (n % 100 ? " " + below1000(n % 100) : "")
  }

  const intPart = Math.floor(amount)
  const decPart = Math.round((amount - intPart) * 100)
  let result = ""
  if (intPart >= 1_000_000) result += below1000(Math.floor(intPart / 1_000_000)) + " Million "
  if (intPart % 1_000_000 >= 1_000) result += below1000(Math.floor((intPart % 1_000_000) / 1_000)) + " Thousand "
  result += below1000(intPart % 1_000)
  if (decPart > 0) result += " and " + below1000(decPart) + " Cents"
  return result.trim() + " Only"
}

// ── Shared sub-components ─────────────────────────────────────────────────

/** A table row for the JV meta header table (Voucher No, Date, etc.) */
function MetaRow({ k, v }: { k: string; v: string }) {
  return (
    <tr>
      <td className="px-3 py-1.5 text-[var(--text-primary)]/65 w-1/3 text-[11px] uppercase tracking-wider font-semibold">{k}</td>
      <td className="px-3 py-1.5 text-sm font-semibold">{v}</td>
    </tr>
  )
}

/** Signature line bar — gb-* classes apply greenbar print styling. */
function SignatureBar({ labels }: { labels: string[] }) {
  return (
    <div className="gb-sig flex justify-between mt-14 pt-5 border-t border-[var(--text-primary)]/20 text-xs text-[var(--text-primary)]/55">
      {labels.map(l => (
        <div key={l} className="gb-sig-item text-center w-40">
          <div className="gb-sig-line border-t border-[var(--text-primary)]/25 pt-1 mt-12">{l}</div>
        </div>
      ))}
    </div>
  )
}

// ── Voucher type labels ───────────────────────────────────────────────────

const VOUCHER_LABELS: Record<string, string> = {
  JV: "Journal Voucher",
  CO: "Contra Voucher",
  CP: "Cash Payment Voucher",
  BP: "Bank Payment Voucher",
  CR: "Cash Receipt Voucher",
  BR: "Bank Receipt Voucher",
  SL: "Sales Invoice",
  PR: "Purchase Invoice",
  CN: "Credit Note",
  DN: "Debit Note",
}

// ── TEMPLATE: Journal / Contra ────────────────────────────────────────────

function JvTemplate({ txn }: { txn: Txn }) {
  const { t } = useTranslation()
  const totalDr = txn.entries.reduce((s, e) => s + (Number(e.debit)  || 0), 0)
  const totalCr = txn.entries.reduce((s, e) => s + (Number(e.credit) || 0), 0)

  return (
    <article className="text-[var(--text-primary)]">
      {/* Meta fields */}
      <table className="w-full text-sm border border-[var(--border)] mb-5">
        <tbody className="divide-y divide-[var(--border)]">
          <MetaRow k="Voucher No" v={txn.jv_number} />
          <MetaRow k="Date"       v={fmtDate(txn.date)} />
          {txn.description && <MetaRow k="Description" v={txn.description} />}
          {txn.reference   && <MetaRow k="Reference"   v={txn.reference} />}
          {txn.party       && <MetaRow k="Party"       v={txn.party} />}
        </tbody>
      </table>

      {/* Debit / Credit entries */}
      <table className="w-full text-sm border border-[var(--border)] mb-5">
        <thead className="bg-[var(--bg-page)]">
          <tr>
            <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">{t('col.account', 'Account')}</th>
            <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-24">Type</th>
            <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-32">{t('col.debit', 'Debit')}</th>
            <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-32">{t('col.credit', 'Credit')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {txn.entries.map((e, i) => (
            <tr key={i}>
              <td className="px-3 py-2">{e.account_name}</td>
              <td className="px-3 py-2 text-[10px] text-[var(--text-primary)]/55 uppercase">{e.account_type}</td>
              <td className="px-3 py-2 text-right font-mono">{fmt(e.debit)}</td>
              <td className="px-3 py-2 text-right font-mono">{fmt(e.credit)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-[var(--text-primary)] bg-[var(--bg-page)]">
            <td colSpan={2} className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Totals</td>
            <td className="px-3 py-2 text-right font-mono font-bold">{fmtAmt(totalDr)}</td>
            <td className="px-3 py-2 text-right font-mono font-bold">{fmtAmt(totalCr)}</td>
          </tr>
        </tfoot>
      </table>

      {txn.notes && (
        <div className="mb-5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.notes', 'Notes')}</p>
          <p className="text-sm whitespace-pre-wrap">{txn.notes}</p>
        </div>
      )}

      <SignatureBar labels={["Prepared By", "Approved By"]} />
    </article>
  )
}

// ── TEMPLATE: Payment Voucher (CP / BP) ───────────────────────────────────
// Dr entries = items paid for; Cr entry = cash/bank paid from

function PvTemplate({ txn }: { txn: Txn }) {
  const { t } = useTranslation()
  const payToEntries = txn.entries.filter(e => Number(e.debit)  > 0)
  const payFromEntry = txn.entries.find(e  => Number(e.credit) > 0)
  const total        = payToEntries.reduce((s, e) => s + Number(e.debit), 0)
  const isBank       = txn.voucher_type === "BP"

  return (
    <article className="text-[var(--text-primary)]">

      {/* ── Voucher No / Date strip ── */}
      <div className="gb-meta-strip flex justify-between items-start mb-5 pb-4 border-b-2 border-[var(--text-primary)]">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Voucher No</p>
          <p className="text-xl font-mono font-bold">{txn.jv_number}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Date</p>
          <p className="text-xl font-mono font-bold">{fmtDate(txn.date)}</p>
        </div>
      </div>

      {/* ── Paid To / Description ── */}
      <div className="gb-box mb-5 p-3 bg-[var(--bg-page)] rounded-lg">
        <p className="gb-box-label text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">
          {txn.party ? "Paid To" : "Description"}
        </p>
        <p className="gb-box-value text-base font-semibold">{txn.party ?? txn.description ?? "—"}</p>
        {txn.party && txn.description && (
          <p className="gb-box-sub text-sm text-[var(--text-primary)]/60 mt-0.5">{txn.description}</p>
        )}
        {txn.reference && (
          <p className="gb-box-sub text-xs text-[var(--text-primary)]/50 mt-0.5">Ref: {txn.reference}</p>
        )}
      </div>

      {/* ── Pay-to line items ── */}
      <table className="w-full text-sm border border-[var(--border)] mb-5">
        <thead className="bg-[var(--bg-page)]">
          <tr>
            <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-8">#</th>
            <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Account / Particulars</th>
            <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-36">{t('col.amount', 'Amount')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {payToEntries.map((e, i) => (
            <tr key={i}>
              <td className="px-3 py-2 text-[var(--text-primary)]/40 text-xs">{i + 1}</td>
              <td className="px-3 py-2">{e.account_name}</td>
              <td className="px-3 py-2 text-right font-mono">{fmt(e.debit)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-[var(--text-primary)] bg-[var(--bg-page)]">
            <td colSpan={2} className="px-3 py-2 font-bold text-sm">Total Amount</td>
            <td className="px-3 py-2 text-right font-mono font-bold text-base">{fmtAmt(total)}</td>
          </tr>
        </tfoot>
      </table>

      {/* ── Amount in words ── */}
      <div className="gb-amount-box mb-5 p-3 border border-[var(--border)] rounded-lg">
        <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">Amount in Words</p>
        <p className="text-sm font-medium italic">{amountInWords(total)}</p>
      </div>

      {/* ── Paid From (cash/bank) ── */}
      <div className="gb-from-strip mb-5 flex items-center gap-4 p-3 bg-[var(--text-primary)]/5 rounded-lg border border-[var(--border)]">
        <div className="flex-1">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">
            {isBank ? "Paid via Bank Account" : "Paid via Cash Account"}
          </p>
          <p className="text-sm font-semibold">{payFromEntry?.account_name ?? "—"}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">Paid Amount</p>
          <p className="text-base font-mono font-bold">{fmtAmt(total)}</p>
        </div>
      </div>

      {txn.notes && (
        <div className="mb-5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.notes', 'Notes')}</p>
          <p className="text-sm whitespace-pre-wrap">{txn.notes}</p>
        </div>
      )}

      <SignatureBar labels={["Received By", "Prepared By", "Approved By"]} />
    </article>
  )
}

// ── TEMPLATE: Receipt Voucher (CR / BR) ───────────────────────────────────
// Dr entry = cash/bank received into; Cr entries = income/sources

function RvTemplate({ txn }: { txn: Txn }) {
  const { t } = useTranslation()
  const receivedIntoEntry   = txn.entries.find(e  => Number(e.debit)  > 0)
  const receivedFromEntries = txn.entries.filter(e => Number(e.credit) > 0)
  const total               = receivedFromEntries.reduce((s, e) => s + Number(e.credit), 0)
  const isBank              = txn.voucher_type === "BR"

  return (
    <article className="text-[var(--text-primary)]">

      {/* ── Voucher No / Date strip ── */}
      <div className="gb-meta-strip flex justify-between items-start mb-5 pb-4 border-b-2 border-[var(--text-primary)]">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Voucher No</p>
          <p className="text-xl font-mono font-bold">{txn.jv_number}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Date</p>
          <p className="text-xl font-mono font-bold">{fmtDate(txn.date)}</p>
        </div>
      </div>

      {/* ── Received From / Description ── */}
      <div className="gb-box mb-5 p-3 bg-[var(--bg-page)] rounded-lg">
        <p className="gb-box-label text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">
          {txn.party ? "Received From" : "Description"}
        </p>
        <p className="gb-box-value text-base font-semibold">{txn.party ?? txn.description ?? "—"}</p>
        {txn.party && txn.description && (
          <p className="gb-box-sub text-sm text-[var(--text-primary)]/60 mt-0.5">{txn.description}</p>
        )}
        {txn.reference && (
          <p className="gb-box-sub text-xs text-[var(--text-primary)]/50 mt-0.5">Ref: {txn.reference}</p>
        )}
      </div>

      {/* ── Received-from line items ── */}
      <table className="w-full text-sm border border-[var(--border)] mb-5">
        <thead className="bg-[var(--bg-page)]">
          <tr>
            <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-8">#</th>
            <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Account / Particulars</th>
            <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-36">{t('col.amount', 'Amount')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {receivedFromEntries.map((e, i) => (
            <tr key={i}>
              <td className="px-3 py-2 text-[var(--text-primary)]/40 text-xs">{i + 1}</td>
              <td className="px-3 py-2">{e.account_name}</td>
              <td className="px-3 py-2 text-right font-mono">{fmt(e.credit)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-[var(--text-primary)] bg-[var(--bg-page)]">
            <td colSpan={2} className="px-3 py-2 font-bold text-sm">Total Amount</td>
            <td className="px-3 py-2 text-right font-mono font-bold text-base">{fmtAmt(total)}</td>
          </tr>
        </tfoot>
      </table>

      {/* ── Amount in words ── */}
      <div className="gb-amount-box mb-5 p-3 border border-[var(--border)] rounded-lg">
        <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">Amount in Words</p>
        <p className="text-sm font-medium italic">{amountInWords(total)}</p>
      </div>

      {/* ── Received Into (cash/bank) ── */}
      <div className="gb-from-strip mb-5 flex items-center gap-4 p-3 bg-[var(--text-primary)]/5 rounded-lg border border-[var(--border)]">
        <div className="flex-1">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">
            {isBank ? "Received into Bank Account" : "Received into Cash Account"}
          </p>
          <p className="text-sm font-semibold">{receivedIntoEntry?.account_name ?? "—"}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">Received Amount</p>
          <p className="text-base font-mono font-bold">{fmtAmt(total)}</p>
        </div>
      </div>

      {txn.notes && (
        <div className="mb-5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.notes', 'Notes')}</p>
          <p className="text-sm whitespace-pre-wrap">{txn.notes}</p>
        </div>
      )}

      <SignatureBar labels={["Received By", "Prepared By", "Approved By"]} />
    </article>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function VoucherPrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const { id } = use(params)
  const router  = useRouter()
  const [txn,   setTxn]   = useState<Txn | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Txn>(`/api/transactions/${id}`)
      .then(d => { setTxn(d); setTimeout(() => window.print(), 300) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!txn)  return <p className="p-4 text-[var(--text-primary)]/60 text-sm">Loading voucher…</p>

  const vt    = txn.voucher_type ?? "JV"
  const title = VOUCHER_LABELS[vt] ?? "Voucher"
  const isPv  = ["CP", "BP"].includes(vt)
  const isRv  = ["CR", "BR"].includes(vt)

  return (
    <div className="bg-white min-h-screen">
      {/* Screen-only toolbar */}
      <div className="print:hidden flex items-center justify-between bg-[var(--text-primary)] text-white px-4 py-2 mb-4">
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm hover:text-[#ffd966]">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <span className="text-sm font-semibold text-white/70">{title} — {txn.jv_number}</span>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--primary)] hover:bg-[#d4af60] text-black rounded-md text-sm font-semibold"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-10">
        <PrintHeader title={title} subtitle={`Voucher No: ${txn.jv_number}  ·  Date: ${fmtDate(txn.date)}`} />

        {isPv ? <PvTemplate txn={txn} /> :
         isRv ? <RvTemplate txn={txn} /> :
                <JvTemplate txn={txn} />}
      </div>
    </div>
  )
}
