"use client"

import Link from "next/link"
import { VOUCHER_TYPES, voucherTypeBadgeClass } from "@/lib/voucherTypes"
import { useFmt, useCurrency } from "@/context/SettingsContext"

// ─── Types ────────────────────────────────────────────────────────────────────

export interface LedgerEntry {
  date: string
  transaction_id: number
  jv_number: string
  voucher_type: string | null
  description: string
  debit: number
  credit: number
  balance: number
}

export interface LedgerPayload {
  code: string
  name: string
  type?: string
  opening_balance: number | string
  closing_balance: number | string
  entries: LedgerEntry[]
}

interface LedgerEntriesTableProps {
  payload: LedgerPayload
  /** When set, only rows whose voucher_type matches this value are shown.
   *  Rows are hidden (filter is a view concern); running balance values
   *  remain as computed by the server — they reflect the full ledger. */
  voucherFilter: string
}

/**
 * Shared ledger entries table used by Cash Book and Bank Book.
 *
 * Renders:
 *   Date | JV # + voucher badge | Description | Debit | Credit | Balance
 * with Opening and Closing balance rows at top and bottom.
 *
 * Running balance values are taken directly from the server payload.
 * When a voucher filter is active, non-matching rows are hidden but their
 * balances remain unchanged (filter is display-only, not a recalculation).
 */
export default function LedgerEntriesTable({ payload, voucherFilter }: LedgerEntriesTableProps) {
  const fmt      = useFmt()
  const currency = useCurrency()

  const visibleEntries = voucherFilter
    ? payload.entries.filter(e => e.voucher_type === voucherFilter)
    : payload.entries

  const totalDebit  = visibleEntries.reduce((s, e) => s + (e.debit  || 0), 0)
  const totalCredit = visibleEntries.reduce((s, e) => s + (e.credit || 0), 0)
  const closing     = Number(payload.closing_balance ?? 0)
  const opening     = Number(payload.opening_balance ?? 0)

  return (
    <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
      {/* Account header strip */}
      <div className="bg-[#f6f3ee] px-6 py-4 border-b border-[#ede9e2] flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm text-[#b8943f]">{payload.code}</span>
          <span className="font-serif text-lg text-[#1a1814]">{payload.name}</span>
          {payload.type && (
            <span className="text-[10px] text-[#1a1814]/40 border border-[#ede9e2] rounded px-1.5 py-0.5">
              {payload.type}
            </span>
          )}
        </div>
        <div className="flex items-center gap-6 text-right">
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/50">
              {voucherFilter ? "Filtered Debit" : "Total Debit"}
            </p>
            <p className="font-mono text-sm font-semibold">{fmt(totalDebit)}</p>
          </div>
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/50">
              {voucherFilter ? "Filtered Credit" : "Total Credit"}
            </p>
            <p className="font-mono text-sm font-semibold">{fmt(totalCredit)}</p>
          </div>
          <div className="border-l border-[#ede9e2] pl-6">
            <p className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/50">Closing Balance</p>
            <p className={`font-mono font-bold text-base ${closing < 0 ? "text-red-600" : "text-[#1a1814]"}`}>
              {fmt(closing)}
            </p>
          </div>
        </div>
      </div>

      {/* Transactions table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Date</th>
              <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-36">Voucher</th>
              <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Description</th>
              <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Debit ({currency})</th>
              <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Credit ({currency})</th>
              <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Balance ({currency})</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#f6f3ee]">
            {/* Opening balance row */}
            <tr className="bg-[#f6f3ee] text-[#1a1814]/70 text-xs font-semibold">
              <td className="px-4 py-2" colSpan={3}>Opening Balance</td>
              <td className="px-4 py-2 text-right font-mono" colSpan={2} />
              <td className="px-4 py-2 text-right font-mono">{fmt(opening)}</td>
            </tr>

            {visibleEntries.length === 0 ? (
              <tr>
                <td colSpan={6} className="ui-td py-8 text-center text-sm text-[#1a1814]/40 italic">
                  {voucherFilter
                    ? `No ${VOUCHER_TYPES[voucherFilter] ?? voucherFilter} entries in this period.`
                    : "No transactions in this period."}
                </td>
              </tr>
            ) : (
              visibleEntries.map((entry, idx) => (
                <tr key={idx} className="hover:bg-[#faf8f4]">
                  <td className="px-4 py-2.5 text-black/60">{entry.date}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <Link
                        href={`/journal/${entry.transaction_id}`}
                        className="font-mono text-xs text-[#b8943f] hover:underline underline-offset-2"
                      >
                        {entry.jv_number}
                      </Link>
                      {entry.voucher_type && (
                        <span
                          className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${voucherTypeBadgeClass(entry.voucher_type)}`}
                          title={VOUCHER_TYPES[entry.voucher_type] ?? entry.voucher_type}
                        >
                          {entry.voucher_type}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-black/65 max-w-xs truncate">{entry.description}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-sm">
                    {entry.debit > 0 ? fmt(entry.debit) : <span className="text-black/20">—</span>}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-sm">
                    {entry.credit > 0 ? fmt(entry.credit) : <span className="text-black/20">—</span>}
                  </td>
                  <td className={`px-4 py-2.5 text-right font-mono text-sm font-semibold ${entry.balance < 0 ? "text-red-600" : ""}`}>
                    {fmt(entry.balance)}
                  </td>
                </tr>
              ))
            )}

            {/* Closing balance row */}
            <tr className="bg-[#faf8f4] font-bold text-[#1a1814]">
              <td className="px-4 py-2" colSpan={3}>Closing Balance</td>
              <td className="px-4 py-2 text-right font-mono" colSpan={2} />
              <td className="px-4 py-2 text-right font-mono">{fmt(closing)}</td>
            </tr>
          </tbody>
          <tfoot className="border-t-2 border-[#1a1814]/10">
            <tr className="bg-[#faf6ec]">
              <td colSpan={3} className="ui-td text-xs font-bold text-[#1a1814]/55 uppercase tracking-widest">
                {visibleEntries.length} transaction{visibleEntries.length !== 1 ? "s" : ""}
                {voucherFilter && payload.entries.length !== visibleEntries.length
                  ? ` (filtered from ${payload.entries.length})`
                  : ""}
              </td>
              <td className="ui-td text-right font-mono font-bold">{fmt(totalDebit)}</td>
              <td className="ui-td text-right font-mono font-bold">{fmt(totalCredit)}</td>
              <td className={`ui-td text-right font-mono font-bold ${closing < 0 ? "text-red-600" : ""}`}>
                {fmt(closing)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}
