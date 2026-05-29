"use client"

import { useEffect, useState } from "react"
import { Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtAmount } from "@/lib/utils"
import { useSettings } from "@/context/SettingsContext"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
import DocLink from "@/components/DocLink"

interface PnLItem {
  name: string
  type: string
  code?: string
  total_debit: number
  total_credit: number
}

interface PnLResponse {
  current?: PnLItem[]
  comparison?: PnLItem[]
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

function priorYearRange(start: string, end: string) {
  const priorStart = `${parseInt(start.slice(0, 4)) - 1}${start.slice(4)}`
  const priorEnd   = `${parseInt(end.slice(0, 4)) - 1}${end.slice(4)}`
  return { priorStart, priorEnd }
}

export default function PnLPage() {
  const { settings } = useSettings()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<PnLItem[]>([])
  const [comparison, setComparison] = useState<PnLItem[] | null>(null)
  const [compareMode, setCompareMode] = useState(false)
  const { priorStart, priorEnd } = priorYearRange(start, end)
  const [cmpStart, setCmpStart] = useState(priorStart)
  const [cmpEnd, setCmpEnd] = useState(priorEnd)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams({ start, end })
    if (compareMode) {
      params.set("compare_start", cmpStart)
      params.set("compare_end", cmpEnd)
    }
    apiFetch<PnLItem[] | PnLResponse>(`/api/reports/income-statement?${params}`)
      .then(res => {
        if (compareMode && res && typeof res === "object" && "current" in res) {
          setData((res as PnLResponse).current ?? [])
          setComparison((res as PnLResponse).comparison ?? null)
        } else {
          setData(Array.isArray(res) ? res : [])
          setComparison(null)
        }
        setIsLoading(false)
      })
      .catch(() => setIsLoading(false))
  }, [start, end, compareMode, cmpStart, cmpEnd])

  const revenueItems = data.filter(i => i.type === "Revenue")
  const expenseItems = data.filter(i => i.type === "Expense")
  const totalRevenue = revenueItems.reduce((sum, i) => sum + (i.total_credit - i.total_debit), 0)
  const totalExpense = expenseItems.reduce((sum, i) => sum + (i.total_debit - i.total_credit), 0)
  const netIncome = totalRevenue - totalExpense

  const cmpRevItems = comparison?.filter(i => i.type === "Revenue") ?? []
  const cmpExpItems = comparison?.filter(i => i.type === "Expense") ?? []
  const cmpTotalRevenue = cmpRevItems.reduce((sum, i) => sum + (i.total_credit - i.total_debit), 0)
  const cmpTotalExpense = cmpExpItems.reduce((sum, i) => sum + (i.total_debit - i.total_credit), 0)
  const cmpNetIncome = cmpTotalRevenue - cmpTotalExpense

  function cmpAmount(name: string, type: "Revenue" | "Expense"): number {
    const item = comparison?.find(i => i.name === name && i.type === type)
    if (!item) return 0
    return type === "Revenue"
      ? item.total_credit - item.total_debit
      : item.total_debit - item.total_credit
  }

  const fmt = (n: number) => fmtAmount(n, settings.currency)

  return (
    <div className="max-w-4xl mx-auto">
      <PrintHeader title="Income Statement" subtitle={`Period: ${start} — ${end}`} />
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Income Statement</h1>
          <p className="text-[#1a1814]/60">Revenue and expenses for the selected period</p>
        </div>
        <button onClick={() => window.print()} className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 print:hidden" title="Print">
          <Printer className="w-5 h-5" />
        </button>
      </div>

      <div className="mb-4 p-4 bg-white border border-[#ede9e2] rounded-xl space-y-3">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        <label className="flex items-center gap-2 text-sm text-[#1a1814]/70 cursor-pointer">
          <input
            type="checkbox"
            checked={compareMode}
            onChange={e => setCompareMode(e.target.checked)}
            className="rounded"
          />
          Compare with prior period
        </label>
        {compareMode && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-[#1a1814]/50">Prior period:</span>
            <input type="date" value={cmpStart} onChange={e => setCmpStart(e.target.value)}
                   className="border border-[#ede9e2] rounded px-2 py-1 text-sm" />
            <span className="text-[#1a1814]/50">to</span>
            <input type="date" value={cmpEnd} onChange={e => setCmpEnd(e.target.value)}
                   className="border border-[#ede9e2] rounded px-2 py-1 text-sm" />
          </div>
        )}
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 p-10 space-y-12">
        {comparison && (
          <div className="flex justify-end gap-8 text-xs font-bold text-[#1a1814]/50 uppercase tracking-widest">
            <span>{start.slice(0, 4)}</span>
            <span className="text-[#1a1814]/30">{cmpStart.slice(0, 4)}</span>
          </div>
        )}

        <section className="space-y-4">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 border-b border-[#1a1814]/5 pb-2">Revenue</h3>
          {isLoading ? (
            <div className="text-sm text-[#1a1814]/75 italic">Loading...</div>
          ) : revenueItems.length === 0 ? (
            <div className="text-sm text-[#1a1814]/75 italic">No revenue in selected period.</div>
          ) : (
            revenueItems.map(item => (
              <div key={item.name} className="flex justify-between text-sm">
                <DocLink type="account" id={item.name} label={item.name} className="text-[#1a1814]/60" />
                <div className="flex gap-8">
                  <span className="font-mono">{fmt(item.total_credit - item.total_debit)}</span>
                  {comparison && (
                    <span className="font-mono text-[#1a1814]/35">{fmt(cmpAmount(item.name, "Revenue"))}</span>
                  )}
                </div>
              </div>
            ))
          )}
          <div className="flex justify-between pt-4 border-t border-[#1a1814]/5 font-bold">
            <span className="text-[#1a1814]">Total Revenue</span>
            <div className="flex gap-8">
              <span className="font-mono underline decoration-double underline-offset-4">{fmt(totalRevenue)}</span>
              {comparison && (
                <span className="font-mono underline decoration-double underline-offset-4 text-[#1a1814]/35">{fmt(cmpTotalRevenue)}</span>
              )}
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 border-b border-[#1a1814]/5 pb-2">Expenses</h3>
          {isLoading ? (
            <div className="text-sm text-[#1a1814]/75 italic">Loading...</div>
          ) : expenseItems.length === 0 ? (
            <div className="text-sm text-[#1a1814]/75 italic">No expenses in selected period.</div>
          ) : (
            expenseItems.map(item => (
              <div key={item.name} className="flex justify-between text-sm">
                <DocLink type="account" id={item.name} label={item.name} className="text-[#1a1814]/60" />
                <div className="flex gap-8">
                  <span className="font-mono">({fmt(item.total_debit - item.total_credit)})</span>
                  {comparison && (
                    <span className="font-mono text-[#1a1814]/35">({fmt(cmpAmount(item.name, "Expense"))})</span>
                  )}
                </div>
              </div>
            ))
          )}
          <div className="flex justify-between pt-4 border-t border-[#1a1814]/5 font-bold text-red-600">
            <span>Total Operating Expenses</span>
            <div className="flex gap-8">
              <span className="font-mono">({fmt(totalExpense)})</span>
              {comparison && (
                <span className="font-mono text-red-300">({fmt(cmpTotalExpense)})</span>
              )}
            </div>
          </div>
        </section>

        <section className="pt-8 border-t-2 border-[#1a1814] flex justify-between items-end">
          <div>
            <h2 className="text-2xl font-serif text-[#1a1814]">Net Income</h2>
            <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75">
              {start} — {end}
            </p>
          </div>
          <div className="flex gap-8 items-end">
            <div className={`text-3xl font-serif ${netIncome >= 0 ? "text-green-600" : "text-red-600"}`}>
              {netIncome < 0 && "("}{fmt(Math.abs(netIncome))}{netIncome < 0 && ")"}
            </div>
            {comparison && (
              <div className={`text-xl font-serif ${cmpNetIncome >= 0 ? "text-green-300" : "text-red-300"}`}>
                {cmpNetIncome < 0 && "("}{fmt(Math.abs(cmpNetIncome))}{cmpNetIncome < 0 && ")"}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
