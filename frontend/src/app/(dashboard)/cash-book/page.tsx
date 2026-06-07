"use client"

import { useEffect, useState } from "react"
import { Wallet, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { VOUCHER_TYPES } from "@/lib/voucherTypes"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
import LedgerEntriesTable, { LedgerPayload } from "@/components/LedgerEntriesTable"

// ─── Types ────────────────────────────────────────────────────────────────────

interface Account {
  id: number
  code: string
  name: string
  type: string
}

interface BankAccount {
  id: number
  name: string
  coa_account_id: number | null
}

interface LedgerResponse {
  total: number
  items: LedgerPayload[]
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CashBookPage() {
  const range = defaultRange()

  const [start, setStart] = useState(range.start)
  const [end, setEnd]     = useState(range.end)

  const [cashAccounts, setCashAccounts] = useState<Account[]>([])
  const [selectedCode, setSelectedCode] = useState<string>("")
  const [voucherFilter, setVoucherFilter] = useState<string>("")

  const [ledgerData, setLedgerData] = useState<LedgerPayload | null>(null)
  const [isLoading, setIsLoading]   = useState(false)
  const [loadError, setLoadError]   = useState<string | null>(null)
  const [initLoading, setInitLoading] = useState(true)

  // ── On mount: identify cash accounts ─────────────────────────────────────
  useEffect(() => {
    let cancelled = false

    Promise.all([
      apiFetch<{ total: number; items: Account[] }>("/api/accounts?limit=500"),
      apiFetch<BankAccount[]>("/api/bank-accounts"),
    ])
      .then(([acctResp, bankAccts]) => {
        if (cancelled) return

        // bank-account GL ids (those are bank, not cash)
        const bankCoaIds = new Set(
          bankAccts
            .map(b => b.coa_account_id)
            .filter((id): id is number => id !== null)
        )

        // Cash = Asset accounts that are cash (name contains "cash", e.g. Cash in
        // Hand / Petty Cash) and NOT linked to a bank account. Using the name
        // rather than a broad "10xx" code range avoids surfacing other 10xx assets
        // (e.g. Accumulated Depreciation) in the Cash Book.
        const cash = acctResp.items.filter(
          a => a.type === "Asset" && a.name.toLowerCase().includes("cash") && !bankCoaIds.has(a.id)
        )

        setCashAccounts(cash)
        if (cash.length > 0) setSelectedCode(cash[0].code)
        setInitLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError("Failed to load accounts. Please refresh.")
          setInitLoading(false)
        }
      })

    return () => { cancelled = true }
  }, [])

  // ── Fetch ledger whenever account or date range changes ───────────────────
  useEffect(() => {
    if (!selectedCode || !start || !end) { setLedgerData(null); return }

    setIsLoading(true)
    setLoadError(null)

    const params = new URLSearchParams({ account_code: selectedCode, start, end, limit: "1000" })
    apiFetch<LedgerResponse>(`/api/reports/ledger?${params}`)
      .then(resp => {
        setLedgerData(resp.items[0] ?? null)
        setIsLoading(false)
      })
      .catch(() => {
        setLoadError("Failed to load ledger data.")
        setIsLoading(false)
      })
  }, [selectedCode, start, end])

  // ─── Render ───────────────────────────────────────────────────────────────

  const selectedAccount = cashAccounts.find(a => a.code === selectedCode)

  return (
    <div>
      <PrintHeader
        title={selectedAccount ? `Cash Book — ${selectedAccount.name}` : "Cash Book"}
        subtitle={`Period: ${start} — ${end}`}
        orientation="landscape"
      />

      {/* Page title */}
      <div className="flex items-center justify-between gap-3 mb-5 print:hidden">
        <div className="flex items-center gap-3">
          <Wallet className="w-5 h-5 text-[#b8943f]" />
          <div>
            <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">Cash Book</h1>
            <p className="text-xs text-[#1a1814]/55">
              Voucher-aware ledger view of cash account transactions
            </p>
          </div>
        </div>
        <button
          onClick={() => window.print()}
          disabled={!ledgerData}
          className="p-2.5 bg-white border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 disabled:opacity-30 disabled:cursor-not-allowed"
          title={!ledgerData ? "No data to print" : "Print Cash Book"}
        >
          <Printer className="w-4 h-4" />
        </button>
      </div>

      {/* Controls */}
      <div className="bg-white border border-[#ede9e2] rounded-xl p-4 mb-5 space-y-3 print:hidden">

        {/* Cash account selector (only when multiple) */}
        {cashAccounts.length > 1 && (
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
              Cash Account
            </label>
            <select
              value={selectedCode}
              onChange={e => { setSelectedCode(e.target.value); setVoucherFilter("") }}
              className="w-full px-3 py-2.5 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-[#b8943f] bg-white"
            >
              {cashAccounts.map(a => (
                <option key={a.id} value={a.code}>
                  {a.code} — {a.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Date range */}
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />

        {/* Voucher type filter */}
        {ledgerData && ledgerData.entries.length > 0 && (
          <div className="flex items-center gap-3">
            <label className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 whitespace-nowrap">
              Voucher Type
            </label>
            <select
              value={voucherFilter}
              onChange={e => setVoucherFilter(e.target.value)}
              className="px-3 py-1.5 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-[#b8943f] bg-white"
            >
              <option value="">All vouchers</option>
              {Object.entries(VOUCHER_TYPES).map(([code, label]) => (
                <option key={code} value={code}>{code} — {label}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* ── States ────────────────────────────────────────────────────────────── */}

      {/* Initial loading */}
      {initLoading && (
        <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden animate-pulse">
          <div className="bg-[#f6f3ee] px-6 py-4 h-14" />
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-4 bg-[#f0ece4] rounded" />)}
          </div>
        </div>
      )}

      {/* Error */}
      {!initLoading && loadError && (
        <div className="bg-white border border-red-200 rounded-xl py-12 text-center">
          <p className="text-sm text-red-600">{loadError}</p>
        </div>
      )}

      {/* No cash accounts found */}
      {!initLoading && !loadError && cashAccounts.length === 0 && (
        <div className="bg-white border border-[#ede9e2] rounded-xl py-20 text-center">
          <Wallet className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]/50">No cash account found</p>
          <p className="text-xs text-[#1a1814]/35 mt-1">
            Cash accounts are Asset GL accounts with codes starting with &ldquo;10&rdquo; that are not
            linked to a bank account. Add one via Chart of Accounts.
          </p>
        </div>
      )}

      {/* Ledger loading */}
      {!initLoading && !loadError && cashAccounts.length > 0 && isLoading && (
        <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden animate-pulse">
          <div className="bg-[#f6f3ee] px-6 py-4 h-14" />
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-4 bg-[#f0ece4] rounded" />)}
          </div>
        </div>
      )}

      {/* No data for the period */}
      {!initLoading && !loadError && cashAccounts.length > 0 && !isLoading && !ledgerData && (
        <div className="bg-white border border-[#ede9e2] rounded-xl py-12 text-center">
          <p className="text-sm text-[#1a1814]/50">
            No transactions for{" "}
            <span className="font-mono text-[#b8943f]">{selectedCode}</span>{" "}
            in the selected period.
          </p>
        </div>
      )}

      {/* Ledger table */}
      {!initLoading && !isLoading && ledgerData && (
        <LedgerEntriesTable payload={ledgerData} voucherFilter={voucherFilter} />
      )}
    </div>
  )
}
