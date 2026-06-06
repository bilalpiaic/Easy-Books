"use client"

import React, { useEffect, useState, useCallback, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { ChevronRight, ChevronDown, BookOpen, Printer, Download, Layers, List } from "lucide-react"
import { downloadCSV } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { VOUCHER_TYPES, voucherTypeBadgeClass } from "@/lib/voucherTypes"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"

// ─── Types ────────────────────────────────────────────────────────────────────

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
  voucher_type: string
  description: string
  debit: number
  credit: number
  balance: number
}

interface LedgerAccount {
  id?: number
  code: string
  name: string
  type: string
  entries: LedgerEntry[]
  running_balance: number
  opening_balance: number | string
  closing_balance: number | string
}

/** Shape returned by GET /api/reports/ledger/subledger */
interface SubledgerItem {
  id: number
  name: string
  link: string
  opening: number
  debit: number
  credit: number
  closing: number
}

interface SubledgerResult {
  control: { id: number | null; code: string; name: string }
  items: SubledgerItem[]
  control_balance: number
  sub_total: number
  reconciles: boolean
}

/** Which control param a GL account maps to */
type ControlType = "ar" | "ap"

// ─── Helpers ─────────────────────────────────────────────────────────────────

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

/**
 * Identify the control type for an account, if any.
 * AR  → code "1100" or name "Accounts Receivable"
 * AP  → code "2000" or name "Accounts Payable"
 * Bank accounts (code starts with "10") are listed individually in the flat ledger
 * and do not need expansion — they return null.
 */
function getControlType(account: LedgerAccount | Account): ControlType | null {
  const code = account.code ?? ""
  const name = (account.name ?? "").toLowerCase()
  if (code === "1100" || name === "accounts receivable") return "ar"
  if (code === "2000" || name === "accounts payable") return "ap"
  return null
}

// ─── Sub-Ledger expand row ────────────────────────────────────────────────────

interface ExpandedRowProps {
  control: ControlType
  start: string
  end: string
  fmt: (n: number) => string
  /** Cache set callback so parent can store result */
  onLoaded: (ctrl: ControlType, result: SubledgerResult) => void
  cached: SubledgerResult | null
}

function SubledgerRows({ control, start, end, fmt, onLoaded, cached }: ExpandedRowProps) {
  const [data, setData] = useState<SubledgerResult | null>(cached)
  const [loading, setLoading] = useState(!cached)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (cached) { setData(cached); setLoading(false); return }
    setLoading(true)
    const params = new URLSearchParams({ control, start, end })
    apiFetch<SubledgerResult>(`/api/reports/ledger/subledger?${params}`)
      .then(res => { setData(res); onLoaded(control, res); setLoading(false) })
      .catch(() => { setError("Failed to load sub-ledger"); setLoading(false) })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [control, start, end])

  if (loading) {
    return (
      <tr>
        <td colSpan={6} className="ui-td pl-10 text-xs text-[#1a1814]/40 italic">Loading…</td>
      </tr>
    )
  }
  if (error || !data) {
    return (
      <tr>
        <td colSpan={6} className="ui-td pl-10 text-xs text-red-500">{error ?? "No data"}</td>
      </tr>
    )
  }
  if (data.items.length === 0) {
    return (
      <tr>
        <td colSpan={6} className="ui-td pl-10 text-xs text-[#1a1814]/40 italic">No sub-entities found in this period.</td>
      </tr>
    )
  }

  return (
    <>
      {/* Sub-entity header */}
      <tr className="bg-[#faf6ec]">
        <th className="ui-th" />
        <th className="ui-th pl-10 text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Name</th>
        <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Opening</th>
        <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Debit</th>
        <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Credit</th>
        <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Closing</th>
      </tr>
      {data.items.map(item => (
        <tr key={item.id} className="bg-[#fdfcfa] hover:bg-[#faf8f4]">
          <td className="ui-td" />
          <td className="ui-td pl-10">
            <Link
              href={item.link}
              className="text-sm text-[#b8943f] hover:underline underline-offset-2"
            >
              {item.name}
            </Link>
          </td>
          <td className="ui-td text-right font-mono text-sm text-[#1a1814]/70">{fmt(item.opening)}</td>
          <td className="ui-td text-right font-mono text-sm">{item.debit > 0 ? fmt(item.debit) : <span className="text-black/20">—</span>}</td>
          <td className="ui-td text-right font-mono text-sm">{item.credit > 0 ? fmt(item.credit) : <span className="text-black/20">—</span>}</td>
          <td className={`ui-td text-right font-mono text-sm font-semibold ${item.closing < 0 ? "text-red-600" : ""}`}>
            {fmt(item.closing)}
          </td>
        </tr>
      ))}
      {/* Sub-total row */}
      <tr className="bg-[#f6f3ee] font-semibold text-[#1a1814]">
        <td className="ui-td" />
        <td className="ui-td pl-10 text-xs text-[#1a1814]/55 uppercase tracking-widest">
          {data.items.length} sub-{control === "ar" ? "customer" : "vendor"}{data.items.length !== 1 ? "s" : ""}
        </td>
        <td className="ui-td text-right font-mono text-sm" />
        <td className="ui-td text-right font-mono text-sm" />
        <td className="ui-td text-right font-mono text-sm" />
        <td className="ui-td text-right font-mono text-sm">{fmt(data.sub_total)}</td>
      </tr>
    </>
  )
}

// ─── All-accounts Sub-Ledger table ─────────────────────────────────────────

interface AllAccountsTableProps {
  allLedger: LedgerAccount[]
  start: string
  end: string
  fmt: (n: number) => string
  subledgerCache: Partial<Record<ControlType, SubledgerResult>>
  onSubledgerLoaded: (ctrl: ControlType, result: SubledgerResult) => void
}

function AllAccountsTable({ allLedger, start, end, fmt, subledgerCache, onSubledgerLoaded }: AllAccountsTableProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggle = (key: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      return next
    })
  }

  return (
    <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Code</th>
              <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Account</th>
              <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Opening</th>
              <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Debit</th>
              <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Credit</th>
              <th className="ui-th text-right text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Closing</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#f6f3ee]">
            {allLedger.map(acc => {
              const ctrl = getControlType(acc)
              const isExpanded = ctrl ? expanded.has(ctrl) : false
              const closing = Number(acc.closing_balance ?? acc.running_balance ?? 0)
              const totalDebit = acc.entries.reduce((s, e) => s + (e.debit || 0), 0)
              const totalCredit = acc.entries.reduce((s, e) => s + (e.credit || 0), 0)
              const badge = ctrl && subledgerCache[ctrl]
                ? subledgerCache[ctrl]!.reconciles
                  ? <span className="ml-2 px-1.5 py-0.5 text-[9px] font-bold rounded bg-green-100 text-green-700">✓ reconciles</span>
                  : <span className="ml-2 px-1.5 py-0.5 text-[9px] font-bold rounded bg-amber-100 text-amber-700">⚠ off by {fmt(Math.abs(subledgerCache[ctrl]!.sub_total - subledgerCache[ctrl]!.control_balance))}</span>
                : null

              return (
                <React.Fragment key={acc.code}>
                  <tr
                    className={`hover:bg-[#faf8f4] ${ctrl ? "cursor-pointer" : ""}`}
                    onClick={ctrl ? () => toggle(ctrl) : undefined}
                  >
                    <td className="ui-td">
                      <span className="font-mono text-xs text-[#b8943f]">{acc.code}</span>
                    </td>
                    <td className="ui-td">
                      <div className="flex items-center gap-1.5">
                        {ctrl && (
                          isExpanded
                            ? <ChevronDown className="w-3.5 h-3.5 text-[#b8943f] shrink-0" />
                            : <ChevronRight className="w-3.5 h-3.5 text-[#1a1814]/40 shrink-0" />
                        )}
                        <span className="text-sm text-[#1a1814]">{acc.name}</span>
                        <span className="text-[10px] text-[#1a1814]/40 border border-[#ede9e2] rounded px-1.5 py-0.5 ml-1">{acc.type}</span>
                        {badge}
                      </div>
                    </td>
                    <td className="ui-td text-right font-mono text-sm text-[#1a1814]/70">
                      {fmt(Number(acc.opening_balance ?? 0))}
                    </td>
                    <td className="ui-td text-right font-mono text-sm">
                      {totalDebit > 0 ? fmt(totalDebit) : <span className="text-black/20">—</span>}
                    </td>
                    <td className="ui-td text-right font-mono text-sm">
                      {totalCredit > 0 ? fmt(totalCredit) : <span className="text-black/20">—</span>}
                    </td>
                    <td className={`ui-td text-right font-mono text-sm font-semibold ${closing < 0 ? "text-red-600" : ""}`}>
                      {fmt(closing)}
                    </td>
                  </tr>
                  {ctrl && isExpanded && (
                    <SubledgerRows
                      key={`${ctrl}-${start}-${end}`}
                      control={ctrl}
                      start={start}
                      end={end}
                      fmt={fmt}
                      cached={subledgerCache[ctrl] ?? null}
                      onLoaded={onSubledgerLoaded}
                    />
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Main page inner ──────────────────────────────────────────────────────────

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

  // Sub-Ledger view state
  const [view, setView] = useState<"consolidated" | "subledger">("consolidated")
  const [allLedger, setAllLedger] = useState<LedgerAccount[]>([])
  const [allLedgerLoading, setAllLedgerLoading] = useState(false)
  const [subledgerCache, setSubledgerCache] = useState<Partial<Record<ControlType, SubledgerResult>>>({})

  // Initialise account from ?account=CODE or ?account_id=ID query param
  useEffect(() => {
    const code = searchParams.get("account")
    const aid = searchParams.get("account_id")
    apiFetch<{ total: number; items: Account[] }>("/api/accounts?limit=500")
      .then(d => {
        setAccounts(d.items)
        if (code) {
          const match = d.items.find(a => a.code === code) ?? d.items.find(a => a.name === code)
          if (match) setSelectedAccount(match)
        } else if (aid) {
          const match = d.items.find(a => a.id === Number(aid))
          if (match) setSelectedAccount(match)
        }
      })
      .catch(() => {})
  }, [searchParams])

  // Fetch ledger for the selected account (Consolidated / single-account view)
  useEffect(() => {
    if (!selectedAccount) { setLedgerData(null); return }
    setIsLoading(true)
    const params = new URLSearchParams({ start, end, account_id: String(selectedAccount.id), limit: "1000" })
    apiFetch<{ total: number; items: LedgerAccount[] }>(`/api/reports/ledger?${params}`)
      .then(data => { setLedgerData(data.items[0] ?? null); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [selectedAccount, start, end])

  // Fetch ALL accounts for Sub-Ledger view
  useEffect(() => {
    if (view !== "subledger") return
    setAllLedgerLoading(true)
    const params = new URLSearchParams({ start, end, limit: "500" })
    apiFetch<{ total: number; items: LedgerAccount[] }>(`/api/reports/ledger?${params}`)
      .then(data => { setAllLedger(data.items); setAllLedgerLoading(false) })
      .catch(() => setAllLedgerLoading(false))
  }, [view, start, end])

  // Clear cache when date range changes
  useEffect(() => {
    setSubledgerCache({})
  }, [start, end])

  const handleSubledgerLoaded = useCallback((ctrl: ControlType, result: SubledgerResult) => {
    setSubledgerCache(prev => ({ ...prev, [ctrl]: result }))
  }, [])

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

      {/* Page title + toggle + actions */}
      <div className="flex items-center justify-between gap-3 mb-5 print:hidden">
        <div className="flex items-center gap-3">
          <BookOpen className="w-5 h-5 text-[#b8943f]" />
          <div>
            <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">General Ledger</h1>
            <p className="text-xs text-[#1a1814]/55">
              {view === "consolidated"
                ? "Select an account to view its transaction history with running balance"
                : "All accounts — expand AR / AP rows to see per-entity breakdowns"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Consolidated / Sub-Ledger toggle */}
          <div className="flex rounded-lg border border-[#ede9e2] overflow-hidden">
            <button
              onClick={() => setView("consolidated")}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-bold transition-colors ${view === "consolidated" ? "bg-[#1a1814] text-white" : "bg-white text-black/60 hover:bg-[#f6f3ee]"}`}
              title="Single account view"
            >
              <List className="w-4 h-4" /> Consolidated
            </button>
            <button
              onClick={() => setView("subledger")}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-bold transition-colors ${view === "subledger" ? "bg-[#1a1814] text-white" : "bg-white text-black/60 hover:bg-[#f6f3ee]"}`}
              title="Sub-ledger view with expandable control accounts"
            >
              <Layers className="w-4 h-4" /> Sub-Ledger
            </button>
          </div>

          {view === "consolidated" && selectedAccount && ledgerData && (
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
            disabled={view === "consolidated" && (!selectedAccount || !ledgerData)}
            className="p-2.5 bg-white border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 disabled:opacity-30 disabled:cursor-not-allowed"
            title={view === "consolidated" && (!selectedAccount || !ledgerData) ? "Select an account first" : "Print ledger"}
          >
            <Printer className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Controls — shown in both modes (date range always useful; account picker only in consolidated) */}
      <div className="bg-white border border-[#ede9e2] rounded-xl p-4 mb-5 space-y-3 print:hidden">
        {/* Account LOV — consolidated only */}
        {view === "consolidated" && (
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
        )}

        {/* Date range */}
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
      </div>

      {/* Close dropdown on outside click */}
      {showDropdown && (
        <div className="fixed inset-0 z-20" onClick={() => setShowDropdown(false)} />
      )}

      {/* ── Consolidated view ──────────────────────────────────────────── */}
      {view === "consolidated" && (
        <>
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
        </>
      )}

      {/* ── Sub-Ledger view ────────────────────────────────────────────── */}
      {view === "subledger" && (
        <>
          {allLedgerLoading && (
            <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden animate-pulse">
              <div className="bg-[#f6f3ee] px-6 py-4 h-14" />
              <div className="p-6 space-y-3">
                {[1, 2, 3, 4, 5, 6, 7, 8].map(i => <div key={i} className="h-4 bg-[#f0ece4] rounded" />)}
              </div>
            </div>
          )}

          {!allLedgerLoading && allLedger.length === 0 && (
            <div className="bg-white border border-[#ede9e2] rounded-xl py-20 text-center">
              <BookOpen className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-[#1a1814]/50">No activity in the selected period</p>
              <p className="text-xs text-[#1a1814]/35 mt-1">Try widening the date range</p>
            </div>
          )}

          {!allLedgerLoading && allLedger.length > 0 && (
            <>
              <p className="text-xs text-[#1a1814]/50 mb-3 print:hidden">
                Accounts with activity in the period. Click on <span className="font-semibold text-[#b8943f]">AR / AP</span> rows to expand per-entity breakdowns.
              </p>
              <AllAccountsTable
                allLedger={allLedger}
                start={start}
                end={end}
                fmt={fmt}
                subledgerCache={subledgerCache}
                onSubledgerLoaded={handleSubledgerLoaded}
              />
            </>
          )}
        </>
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
