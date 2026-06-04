"use client"

import { useEffect, useState, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { ChevronRight, BookOpen, Printer, Download } from "lucide-react"
import { downloadCSV } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"

interface Account {
  id: number
  code: string
  name: string
  type: string
}

interface LedgerEntry {
  date: string
  transaction_id: number
  jv_number: string
  description: string
  debit: number
  credit: number
  balance: number
}

interface LedgerAccount {
  code: string
  name: string
  type: string
  entries: LedgerEntry[]
  running_balance: number
  opening_balance: number | string
  closing_balance: number | string
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

function LedgerPageInner() {
  const fmt = useFmt()
  const searchParams = useSearchParams()
  const range = defaultRange()

  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountSearch, setAccountSearch] = useState("")
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null)
  const [showDropdown, setShowDropdown] = useState(false)

  // Initialise date range from query params (Trial Balance drill-down carries start/end)
  const [start, setStart] = useState(searchParams.get("start") ?? range.start)
  const [end, setEnd]     = useState(searchParams.get("end")   ?? range.end)
  const [ledgerData, setLedgerData] = useState<LedgerAccount | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  // Initialise account from ?account=CODE query param (Trial Balance passes code)
  useEffect(() => {
    const code = searchParams.get("account")
    apiFetch<{ total: number; items: Account[] }>("/api/accounts?limit=500")
      .then(d => {
        setAccounts(d.items)
        if (code) {
          // match by code first (exact), then fall back to name substring
          const match = d.items.find(a => a.code === code) ?? d.items.find(a => a.name === code)
          if (match) setSelectedAccount(match)
        }
      })
      .catch(() => {})
  }, [searchParams])

  // Fetch ledger for the selected account whenever account / date range changes
  useEffect(() => {
    if (!selectedAccount) { setLedgerData(null); return }
    setIsLoading(true)
    const params = new URLSearchParams({ start, end, account_id: String(selectedAccount.id), limit: "1000" })
    apiFetch<{ total: number; items: LedgerAccount[] }>(`/api/reports/ledger?${params}`)
      .then(data => { setLedgerData(data.items[0] ?? null); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [selectedAccount, start, end])

  const filteredAccounts = accounts.filter(a =>
    `${a.code} ${a.name}`.toLowerCase().includes(accountSearch.toLowerCase())
  )

  const closing = ledgerData?.running_balance ?? 0

  return (
    <div>
      <PrintHeader
        title={selectedAccount ? `Ledger — ${selectedAccount.code} ${selectedAccount.name}` : "General Ledger"}
        subtitle={`Period: ${start} — ${end}`}
        orientation="landscape"
      />

      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-black/40 mb-4 print:hidden">
        <Link href="/coa" className="hover:text-[#b8943f] transition-colors">Chart of Accounts</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-black/70 font-medium">
          {selectedAccount ? `${selectedAccount.code} — ${selectedAccount.name}` : "General Ledger"}
        </span>
      </nav>

      {/* Page title + actions */}
      <div className="flex items-center justify-between gap-3 mb-5 print:hidden">
        <div className="flex items-center gap-3">
          <BookOpen className="w-5 h-5 text-[#b8943f]" />
          <div>
            <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">General Ledger</h1>
            <p className="text-xs text-[#1a1814]/55">Select an account to view its transaction history with running balance</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {selectedAccount && ledgerData && (
            <button
              onClick={() => downloadCSV(
                `ledger-${selectedAccount.code}-${start}-${end}.csv`,
                ledgerData.entries.map(e => ({
                  Date: e.date,
                  "JV #": e.jv_number,
                  Description: e.description,
                  Debit: e.debit || "",
                  Credit: e.credit || "",
                  Balance: e.balance,
                }))
              )}
              className="p-2.5 bg-white border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60"
              title="Export CSV"
            >
              <Download className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={() => window.print()}
            disabled={!selectedAccount || !ledgerData}
            className="p-2.5 bg-white border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 disabled:opacity-30 disabled:cursor-not-allowed"
            title={selectedAccount && ledgerData ? "Print ledger" : "Select an account first"}
          >
            <Printer className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white border border-[#ede9e2] rounded-xl p-4 mb-5 space-y-3 print:hidden">
        {/* Account LOV */}
        <div className="relative">
          <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
            Account
          </label>
          <div
            className="flex items-center gap-2 px-3 py-2.5 border border-[#ede9e2] rounded-lg bg-white cursor-pointer hover:border-[#b8943f] transition-colors"
            onClick={() => setShowDropdown(v => !v)}
          >
            {selectedAccount ? (
              <>
                <span className="font-mono text-xs text-[#b8943f] shrink-0">{selectedAccount.code}</span>
                <span className="text-sm text-[#1a1814] flex-1 min-w-0 truncate">{selectedAccount.name}</span>
                <span className="text-[10px] text-[#1a1814]/40 shrink-0">{selectedAccount.type}</span>
                <button
                  onClick={e => { e.stopPropagation(); setSelectedAccount(null); setAccountSearch("") }}
                  className="text-[#1a1814]/40 hover:text-red-500 ml-1 shrink-0"
                  title="Clear"
                >✕</button>
              </>
            ) : (
              <span className="text-sm text-[#1a1814]/40">Select account…</span>
            )}
          </div>

          {showDropdown && (
            <div className="absolute z-30 left-0 right-0 mt-1 bg-white border border-[#ede9e2] rounded-xl shadow-lg max-h-72 flex flex-col">
              <div className="p-2 border-b border-[#ede9e2]">
                <input
                  autoFocus
                  type="text"
                  placeholder="Search code or name…"
                  value={accountSearch}
                  onChange={e => setAccountSearch(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#b8943f]"
                  onClick={e => e.stopPropagation()}
                />
              </div>
              <div className="overflow-y-auto flex-1">
                {filteredAccounts.length === 0 ? (
                  <p className="text-center py-6 text-sm text-[#1a1814]/40">No accounts match</p>
                ) : (
                  filteredAccounts.map(a => (
                    <button
                      key={a.id}
                      className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-[#faf6ec] transition-colors"
                      onClick={() => { setSelectedAccount(a); setShowDropdown(false); setAccountSearch("") }}
                    >
                      <span className="font-mono text-xs text-[#b8943f] w-16 shrink-0">{a.code}</span>
                      <span className="text-sm text-[#1a1814] flex-1 min-w-0 truncate">{a.name}</span>
                      <span className="text-[10px] text-[#1a1814]/40 shrink-0">{a.type}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Date range */}
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
      </div>

      {/* Close dropdown on outside click */}
      {showDropdown && (
        <div className="fixed inset-0 z-20" onClick={() => setShowDropdown(false)} />
      )}

      {/* Empty state */}
      {!selectedAccount && (
        <div className="bg-white border border-[#ede9e2] rounded-xl py-20 text-center print:hidden">
          <BookOpen className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]/50">Select an account above to view its ledger</p>
          <p className="text-xs text-[#1a1814]/35 mt-1">Transaction history with running balance will appear here</p>
        </div>
      )}

      {/* Loading */}
      {selectedAccount && isLoading && (
        <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden animate-pulse">
          <div className="bg-[#f6f3ee] px-6 py-4 h-14" />
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-4 bg-[#f0ece4] rounded" />)}
          </div>
        </div>
      )}

      {/* No data for selected account */}
      {selectedAccount && !isLoading && !ledgerData && (
        <div className="bg-white border border-[#ede9e2] rounded-xl py-12 text-center">
          <p className="text-sm text-[#1a1814]/50">
            No transactions for <span className="font-mono text-[#b8943f]">{selectedAccount.code}</span> in the selected period.
          </p>
        </div>
      )}

      {/* Ledger table */}
      {ledgerData && !isLoading && (
        <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
          {/* Account header */}
          <div className="bg-[#f6f3ee] px-6 py-4 border-b border-[#ede9e2] flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm text-[#b8943f]">{ledgerData.code}</span>
              <span className="font-serif text-lg text-[#1a1814]">{ledgerData.name}</span>
              <span className="text-[10px] text-[#1a1814]/40 border border-[#ede9e2] rounded px-1.5 py-0.5">{ledgerData.type}</span>
            </div>
            <div className="flex items-center gap-6 text-right">
              <div>
                <p className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/50">Total Debit</p>
                <p className="font-mono text-sm font-semibold">
                  {fmt(ledgerData.entries.reduce((s, e) => s + (e.debit || 0), 0))}
                </p>
              </div>
              <div>
                <p className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/50">Total Credit</p>
                <p className="font-mono text-sm font-semibold">
                  {fmt(ledgerData.entries.reduce((s, e) => s + (e.credit || 0), 0))}
                </p>
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
                  <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">JV #</th>
                  <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Description</th>
                  <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Debit</th>
                  <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Credit</th>
                  <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Balance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f6f3ee]">
                <tr className="bg-[#f6f3ee] text-[#1a1814]/70 text-xs font-semibold">
                  <td className="px-4 py-2" colSpan={3}>Opening Balance</td>
                  <td className="px-4 py-2 text-right font-mono" colSpan={2} />
                  <td className="px-4 py-2 text-right font-mono">{fmt(Number(ledgerData.opening_balance))}</td>
                </tr>
                {ledgerData.entries.map((entry, idx) => (
                  <tr key={idx} className="hover:bg-[#faf8f4]">
                    <td className="px-4 py-2.5 text-black/60">{entry.date}</td>
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/journal/${entry.transaction_id}`}
                        className="font-mono text-xs text-[#b8943f] hover:underline underline-offset-2"
                      >
                        {entry.jv_number}
                      </Link>
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
                ))}
                <tr className="bg-[#faf8f4] font-bold text-[#1a1814]">
                  <td className="px-4 py-2" colSpan={3}>Closing Balance</td>
                  <td className="px-4 py-2 text-right font-mono" colSpan={2} />
                  <td className="px-4 py-2 text-right font-mono">{fmt(Number(ledgerData.closing_balance))}</td>
                </tr>
              </tbody>
              <tfoot className="border-t-2 border-[#1a1814]/10">
                <tr className="bg-[#faf6ec]">
                  <td colSpan={3} className="ui-td text-xs font-bold text-[#1a1814]/55 uppercase tracking-widest">
                    {ledgerData.entries.length} transaction{ledgerData.entries.length !== 1 ? "s" : ""}
                  </td>
                  <td className="ui-td text-right font-mono font-bold">
                    {fmt(ledgerData.entries.reduce((s, e) => s + (e.debit || 0), 0))}
                  </td>
                  <td className="ui-td text-right font-mono font-bold">
                    {fmt(ledgerData.entries.reduce((s, e) => s + (e.credit || 0), 0))}
                  </td>
                  <td className={`ui-td text-right font-mono font-bold ${closing < 0 ? "text-red-600" : ""}`}>
                    {fmt(closing)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default function LedgerPage() {
  return (
    <Suspense fallback={<div className="p-6 text-center text-[#1a1814]/60">Loading…</div>}>
      <LedgerPageInner />
    </Suspense>
  )
}
