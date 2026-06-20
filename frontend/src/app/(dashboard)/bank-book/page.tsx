"use client"

import { useEffect, useState } from "react"
import { Landmark, Printer, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { VOUCHER_TYPES } from "@/lib/voucherTypes"
import { downloadCSV } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
import LedgerEntriesTable, { LedgerPayload } from "@/components/LedgerEntriesTable"

// ─── Types ────────────────────────────────────────────────────────────────────

interface BankAccount {
  id: number
  name: string
  bank_name: string | null
  account_number: string | null
  coa_account_id: number | null
  balance?: number
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

export default function BankBookPage() {
  const range = defaultRange()

  const [start, setStart] = useState(range.start)
  const [end, setEnd]     = useState(range.end)

  const [banks, setBanks]             = useState<BankAccount[]>([])
  const [selectedId, setSelectedId]   = useState<number | null>(null)
  const [voucherFilter, setVoucherFilter] = useState<string>("")

  const [ledgerData, setLedgerData]   = useState<LedgerPayload | null>(null)
  const [isLoading, setIsLoading]     = useState(false)
  const [loadError, setLoadError]     = useState<string | null>(null)
  const [initLoading, setInitLoading] = useState(true)

  // ── On mount: load bank accounts, default to first ───────────────────────
  useEffect(() => {
    let cancelled = false
    apiFetch<BankAccount[]>("/api/bank-accounts")
      .then(data => {
        if (cancelled) return
        setBanks(data)
        if (data.length > 0) setSelectedId(data[0].id)
        setInitLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError("Failed to load bank accounts. Please refresh.")
          setInitLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  // ── Fetch ledger whenever bank or date range changes ─────────────────────
  useEffect(() => {
    if (selectedId === null || !start || !end) { setLedgerData(null); return }

    const bank = banks.find(b => b.id === selectedId)
    if (!bank) { setLedgerData(null); return }

    if (!bank.coa_account_id) {
      // bank exists but has no linked GL account — show friendly message
      setLedgerData(null)
      return
    }

    setIsLoading(true)
    setLoadError(null)

    const params = new URLSearchParams({
      account_id: String(bank.coa_account_id),
      start,
      end,
      limit: "1000",
    })

    apiFetch<LedgerResponse>(`/api/reports/ledger?${params}`)
      .then(resp => {
        setLedgerData(resp.items[0] ?? null)
        setIsLoading(false)
      })
      .catch(() => {
        setLoadError("Failed to load ledger data.")
        setIsLoading(false)
      })
  }, [selectedId, start, end, banks])

  // ─── Render ───────────────────────────────────────────────────────────────

  const selectedBank = banks.find(b => b.id === selectedId)
  const hasCoa = selectedBank?.coa_account_id != null

  const pageTitle = selectedBank
    ? `Bank Book — ${selectedBank.name}${selectedBank.bank_name ? ` (${selectedBank.bank_name})` : ""}`
    : "Bank Book"

  return (
    <div>
      <PrintHeader
        title={pageTitle}
        subtitle={`Period: ${start} — ${end}`}
      />

      {/* Page title */}
      <div className="flex items-center justify-between gap-3 mb-5 print:hidden">
        <div className="flex items-center gap-3">
          <Landmark className="w-5 h-5 text-[#b8943f]" />
          <div>
            <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">Bank Book</h1>
            <p className="text-xs text-[#1a1814]/55">
              Voucher-aware ledger view of bank account transactions
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (!ledgerData) return
              downloadCSV(`bank-book-${ledgerData.name}.csv`, ledgerData.entries.map(e => ({
                Date: e.date, "JV#": e.jv_number, Type: e.voucher_type ?? "", Description: e.description,
                Debit: e.debit, Credit: e.credit, Balance: e.balance,
              })))
            }}
            disabled={!ledgerData}
            className="p-2.5 bg-white border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 disabled:opacity-30 disabled:cursor-not-allowed"
            title="Export CSV"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={() => window.print()}
            disabled={!ledgerData}
            className="p-2.5 bg-white border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 disabled:opacity-30 disabled:cursor-not-allowed"
            title={!ledgerData ? "No data to print" : "Print Bank Book"}
          >
            <Printer className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white border border-[#ede9e2] rounded-xl p-4 mb-5 space-y-3 print:hidden">

        {/* Bank account selector */}
        {banks.length > 0 && (
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
              Bank Account
            </label>
            <select
              value={selectedId ?? ""}
              onChange={e => { setSelectedId(Number(e.target.value)); setVoucherFilter("") }}
              className="w-full px-3 py-2.5 border border-[#ede9e2] rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-[#b8943f] bg-white"
            >
              {banks.map(b => (
                <option key={b.id} value={b.id}>
                  {b.name}
                  {b.bank_name ? ` — ${b.bank_name}` : ""}
                  {b.account_number ? ` (${b.account_number})` : ""}
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

      {/* No bank accounts */}
      {!initLoading && !loadError && banks.length === 0 && (
        <div className="bg-white border border-[#ede9e2] rounded-xl py-20 text-center">
          <Landmark className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]/50">No bank accounts found</p>
          <p className="text-xs text-[#1a1814]/35 mt-1">
            Add a bank account via{" "}
            <a href="/bank-accounts" className="text-[#b8943f] hover:underline">
              Banking → Bank Accounts
            </a>
            .
          </p>
        </div>
      )}

      {/* Bank has no linked GL account */}
      {!initLoading && !loadError && selectedBank && !hasCoa && (
        <div className="bg-white border border-amber-200 rounded-xl py-12 text-center">
          <Landmark className="w-10 h-10 text-amber-400/60 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]/60">
            <span className="font-semibold">{selectedBank.name}</span> has no linked GL account.
          </p>
          <p className="text-xs text-[#1a1814]/40 mt-1">
            Edit this bank account and assign a Chart of Accounts entry to see its ledger.
          </p>
        </div>
      )}

      {/* Ledger loading */}
      {!initLoading && !loadError && hasCoa && isLoading && (
        <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden animate-pulse">
          <div className="bg-[#f6f3ee] px-6 py-4 h-14" />
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-4 bg-[#f0ece4] rounded" />)}
          </div>
        </div>
      )}

      {/* No data for the period */}
      {!initLoading && !loadError && hasCoa && !isLoading && !ledgerData && (
        <div className="bg-white border border-[#ede9e2] rounded-xl py-12 text-center">
          <p className="text-sm text-[#1a1814]/50">
            No transactions for{" "}
            <span className="font-semibold text-[#1a1814]/70">{selectedBank?.name}</span>{" "}
            in the selected period.
          </p>
        </div>
      )}

      {/* Ledger table */}
      {!initLoading && !isLoading && hasCoa && ledgerData && (
        <LedgerEntriesTable payload={ledgerData} voucherFilter={voucherFilter} />
      )}
    </div>
  )
}
