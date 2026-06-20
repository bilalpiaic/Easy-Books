"use client"
import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

interface JournalRow {
  transaction_id: number
  jv_number: string
  voucher_type: string
  date: string
  description: string
  account_name: string
  debit: number
  credit: number
  is_reversed: boolean
}

type ColKey = "voucher" | "date" | "account" | "narration" | "amount"

const ALL_COLUMNS: { key: ColKey; label: string; fixed?: boolean }[] = [
  { key: "date", label: "Date", fixed: true },
  { key: "voucher", label: "Voucher No" },
  { key: "account", label: "Account" },
  { key: "narration", label: "Narration" },
  { key: "amount", label: "Amount", fixed: true },
]

function fmtAmount(n: number): string {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function RecentTransactions() {
  const [rows, setRows] = useState<JournalRow[] | null>(null)

  const STORAGE_KEY = "eb.recentTx.cols"
  const [hidden, setHidden] = useState<Set<ColKey>>(new Set())
  const [menuOpen, setMenuOpen] = useState(false)
  const [vtypeFilter, setVtypeFilter] = useState<string>("")
  const [search, setSearch] = useState("")
  const [newestFirst, setNewestFirst] = useState(true)

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) setHidden(new Set(JSON.parse(raw) as ColKey[]))
    } catch { /* ignore malformed storage */ }
  }, [])

  function toggleCol(key: ColKey) {
    setHidden(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...next])) } catch { /* ignore */ }
      return next
    })
  }

  const visible = ALL_COLUMNS.filter(c => c.fixed || !hidden.has(c.key))

  const present = Array.from(new Set((rows ?? []).map(r => r.voucher_type))).sort()
  const q = search.trim().toLowerCase()
  const shown = (rows ?? [])
    .filter(r => !vtypeFilter || r.voucher_type === vtypeFilter)
    .filter(r => !q || r.jv_number.toLowerCase().includes(q) || r.account_name.toLowerCase().includes(q) || (r.description ?? "").toLowerCase().includes(q))
    .sort((a, b) => newestFirst ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date))

  useEffect(() => {
    apiFetch<{ items: JournalRow[] }>("/api/reports/journal?limit=100")
      .then(res => setRows(res.items ?? []))
      .catch(() => setRows([]))
  }, [])

  return (
    <div className="bg-white rounded-xl border border-[#ede9e2] shadow-sm overflow-hidden">
      <div className="px-5 py-3.5 border-b border-[#ede9e2] flex items-center justify-between gap-3">
        <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">Recent Transactions</p>
        <div className="flex items-center gap-3">
          <div className="relative">
            <button onClick={() => setMenuOpen(o => !o)}
              className="text-[11px] text-[#1a1814]/55 font-semibold hover:text-[#1a1814] border border-[#ede9e2] rounded-lg px-2 py-1">
              Columns ▾
            </button>
            {menuOpen && (
              <div className="absolute right-0 mt-1 z-10 bg-white border border-[#ede9e2] rounded-lg shadow-lg p-2 min-w-[160px]">
                {ALL_COLUMNS.filter(c => !c.fixed).map(c => (
                  <label key={c.key} className="flex items-center gap-2 px-2 py-1 text-xs text-[#1a1814]/80 cursor-pointer hover:bg-[#faf8f4] rounded">
                    <input type="checkbox" checked={!hidden.has(c.key)} onChange={() => toggleCol(c.key)} />
                    {c.label}
                  </label>
                ))}
              </div>
            )}
          </div>
          <Link href="/journal" className="text-[11px] text-[#b8943f] font-semibold hover:text-[#8a6d2e]">View all →</Link>
        </div>
      </div>
      <div className="px-5 py-2.5 border-b border-[#ede9e2] flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search voucher, account, narration…"
          className="flex-1 min-w-[160px] text-xs border border-[#ede9e2] rounded-lg px-2.5 py-1.5 bg-[#f6f3ee] outline-none focus:ring-2 focus:ring-[#b8943f]"
        />
        <select value={vtypeFilter} onChange={e => setVtypeFilter(e.target.value)}
          className="text-xs border border-[#ede9e2] rounded-lg px-2 py-1.5 bg-[#f6f3ee] outline-none">
          <option value="">All types</option>
          {present.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button onClick={() => setNewestFirst(v => !v)}
          className="text-xs border border-[#ede9e2] rounded-lg px-2.5 py-1.5 text-[#1a1814]/70 hover:bg-[#faf8f4]">
          Date {newestFirst ? "↓" : "↑"}
        </button>
      </div>
      <div className="overflow-x-auto">
        {rows === null ? (
          <div className="px-5 py-6 flex flex-col gap-2.5">
            {[...Array(5)].map((_, i) => <div key={i} className="flex gap-3"><div className="shimmer h-4 w-20 rounded" /><div className="shimmer h-4 w-24 rounded" /><div className="shimmer h-4 flex-1 rounded" /></div>)}
          </div>
        ) : shown.length === 0 ? (
          <div className="px-5 py-8 text-center text-[#1a1814]/40 text-sm">No transactions for this period.</div>
        ) : (
          <table className="w-full text-left min-w-[560px]">
            <thead>
              <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">
                {visible.map(c => (
                  <th key={c.key} className={`px-5 py-2.5 ${c.key === "amount" ? "text-right" : ""}`}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {shown.map((r, i) => (
                <tr key={`${r.transaction_id}-${i}`} className={`hover:bg-[#faf8f4] transition-colors text-sm ${r.is_reversed ? "opacity-50" : ""}`}>
                  {visible.map(c => <RowCell key={c.key} col={c.key} row={r} />)}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function RowCell({ col, row }: { col: ColKey; row: JournalRow }) {
  switch (col) {
    case "date":
      return <td className="px-5 py-3 text-[#1a1814]/55 text-xs whitespace-nowrap">{fmtDate(row.date)}</td>
    case "voucher":
      return (
        <td className="px-5 py-3">
          <Link href={`/journal?jv=${row.jv_number}`}
            className="font-mono text-[11px] text-[#b8943f] font-semibold hover:underline underline-offset-2 whitespace-nowrap">
            {row.jv_number}{row.is_reversed && <span className="ml-1 text-[#1a1814]/40">(reversed)</span>}
          </Link>
        </td>
      )
    case "account":
      return <td className="px-5 py-3 text-[#1a1814]/70 text-xs max-w-[160px] truncate">{row.account_name}</td>
    case "narration":
      return <td className="px-5 py-3 text-[#1a1814]/80 max-w-[220px] truncate">{row.description}</td>
    case "amount": {
      const isDebit = Number(row.debit) > 0
      const amt = isDebit ? row.debit : row.credit
      return (
        <td className="px-5 py-3 text-right tabular-nums whitespace-nowrap">
          {fmtAmount(amt)}
          <span className={`ml-1.5 text-[10px] font-bold ${isDebit ? "text-blue-600" : "text-green-600"}`}>{isDebit ? "Dr" : "Cr"}</span>
        </td>
      )
    }
  }
}
