"use client"

import { useEffect, useState } from "react"
import { Printer, HelpCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtAmount } from "@/lib/utils"
import { useSettings } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import DocLink from "@/components/DocLink"

interface BalanceItem {
  code: string
  name: string
  type: string
  balance: number
}

interface BSResponse {
  current?: BalanceItem[]
  comparison?: BalanceItem[]
}

function today() { return new Date().toISOString().split("T")[0] }
function priorYear(d: string) { return `${parseInt(d.slice(0, 4)) - 1}${d.slice(4)}` }

function BalanceSection({
  title, items, cmpItems, total, cmpTotal, totalLabel, fmt, showCmp,
}: {
  title: string
  items: BalanceItem[]
  cmpItems: BalanceItem[]
  total: number
  cmpTotal: number
  totalLabel: string
  fmt: (n: number) => string
  showCmp: boolean
}) {
  function cmpBal(code: string) {
    return cmpItems.find(i => i.code === code)?.balance ?? 0
  }
  return (
    <section className="space-y-4">
      <h3 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/75 border-b border-[#1a1814]/5 pb-2">{title}</h3>
      {items.map(item => (
        <div key={item.code} className="flex justify-between text-sm">
          {item.code === "RE-CUR"
            ? <span className="text-[#1a1814] font-medium italic">{item.name}</span>
            : <DocLink type="account" id={item.code} label={item.name} className="text-[#1a1814]/60" />}
          <div className="flex gap-8">
            <span className="font-mono">{fmt(item.balance)}</span>
            {showCmp && <span className="font-mono text-[#1a1814]/35">{fmt(cmpBal(item.code))}</span>}
          </div>
        </div>
      ))}
      <div className="flex justify-between pt-4 border-t border-[#1a1814]/5 font-bold">
        <span className="text-[#1a1814]">{totalLabel}</span>
        <div className="flex gap-8">
          <span className="font-mono underline decoration-double underline-offset-4">{fmt(total)}</span>
          {showCmp && <span className="font-mono underline decoration-double underline-offset-4 text-[#1a1814]/35">{fmt(cmpTotal)}</span>}
        </div>
      </div>
    </section>
  )
}

export default function BalanceSheetPage() {
  const { settings } = useSettings()
  const [data, setData] = useState<BalanceItem[]>([])
  const [comparison, setComparison] = useState<BalanceItem[] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [asOf, setAsOf] = useState(today())
  const [compareMode, setCompareMode] = useState(false)
  const [cmpEnd, setCmpEnd] = useState(priorYear(today()))

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams({ end: asOf })
    if (compareMode) params.set("compare_end", cmpEnd)
    apiFetch<BalanceItem[] | BSResponse>(`/api/reports/balance-sheet?${params}`)
      .then(res => {
        if (compareMode && res && typeof res === "object" && "current" in res) {
          setData((res as BSResponse).current ?? [])
          setComparison((res as BSResponse).comparison ?? null)
        } else {
          setData(Array.isArray(res) ? res : [])
          setComparison(null)
        }
        setIsLoading(false)
      })
      .catch(() => setIsLoading(false))
  }, [asOf, compareMode, cmpEnd])

  const fmt = (n: number) => fmtAmount(n, settings.currency)

  const assets      = data.filter(i => i.type === "Asset")
  const liabilities = data.filter(i => i.type === "Liability")
  const equity      = data.filter(i => i.type === "Equity")
  const cmpAssets      = comparison?.filter(i => i.type === "Asset") ?? []
  const cmpLiabilities = comparison?.filter(i => i.type === "Liability") ?? []
  const cmpEquity      = comparison?.filter(i => i.type === "Equity") ?? []

  const totalAssets      = assets.reduce((s, i) => s + i.balance, 0)
  const totalLiabilities = liabilities.reduce((s, i) => s + i.balance, 0)
  const totalEquity      = equity.reduce((s, i) => s + i.balance, 0)
  const totalLE          = totalLiabilities + totalEquity
  const isBalanced       = Math.abs(totalAssets - totalLE) <= 0.01

  const cmpTotalAssets      = cmpAssets.reduce((s, i) => s + i.balance, 0)
  const cmpTotalLiabilities = cmpLiabilities.reduce((s, i) => s + i.balance, 0)
  const cmpTotalEquity      = cmpEquity.reduce((s, i) => s + i.balance, 0)

  return (
    <div className="max-w-4xl mx-auto">
      <PrintHeader title="Balance Sheet" subtitle={`As of ${asOf}`} />
      <div className="flex justify-between items-center mb-8 print:hidden">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Balance Sheet</h1>
          <p className="text-[#1a1814]/60">Financial position as of {new Date(asOf).toLocaleDateString()}</p>
        </div>
        <button onClick={() => window.print()} className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60 print:hidden" title="Print">
          <Printer className="w-5 h-5" />
        </button>
      </div>

      <div className="mb-6 p-4 bg-white border border-[#ede9e2] rounded-xl space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-bold uppercase tracking-widest text-black/50">As of</span>
          <input type="date" value={asOf} onChange={e => setAsOf(e.target.value)}
                 className="px-3 py-1.5 text-sm border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]" />
        </div>
        <label className="flex items-center gap-2 text-sm text-[#1a1814]/70 cursor-pointer">
          <input type="checkbox" checked={compareMode} onChange={e => setCompareMode(e.target.checked)} className="rounded" />
          Compare with prior period
        </label>
        {compareMode && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-[#1a1814]/50">Prior period as of:</span>
            <input type="date" value={cmpEnd} onChange={e => setCmpEnd(e.target.value)}
                   className="border border-[#ede9e2] rounded px-2 py-1 text-sm" />
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="text-center py-20 text-[#1a1814]/75">Generating report...</div>
      ) : (
        <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 p-10 space-y-12">
          {comparison && (
            <div className="flex justify-end gap-8 text-xs font-bold text-[#1a1814]/50 uppercase tracking-widest">
              <span>{asOf}</span>
              <span className="text-[#1a1814]/30">{cmpEnd}</span>
            </div>
          )}

          <BalanceSection title="Assets" items={assets} cmpItems={cmpAssets}
            total={totalAssets} cmpTotal={cmpTotalAssets} totalLabel="Total Assets"
            fmt={fmt} showCmp={!!comparison} />

          <BalanceSection title="Liabilities" items={liabilities} cmpItems={cmpLiabilities}
            total={totalLiabilities} cmpTotal={cmpTotalLiabilities} totalLabel="Total Liabilities"
            fmt={fmt} showCmp={!!comparison} />

          <BalanceSection title="Equity" items={equity} cmpItems={cmpEquity}
            total={totalEquity} cmpTotal={cmpTotalEquity} totalLabel="Total Equity"
            fmt={fmt} showCmp={!!comparison} />

          <section className="pt-8 border-t-2 border-[#1a1814] flex justify-between items-center bg-[#f6f3ee]/30 -mx-10 px-10 py-6">
            <h2 className="text-xl font-serif text-[#1a1814]">Total Liabilities &amp; Equity</h2>
            <div className="flex gap-8">
              <div className="text-2xl font-serif text-[#1a1814]">{fmt(totalLE)}</div>
              {comparison && (
                <div className="text-xl font-serif text-[#1a1814]/35">{fmt(cmpTotalLiabilities + cmpTotalEquity)}</div>
              )}
            </div>
          </section>

          {!isBalanced && (
            <div className="p-4 bg-orange-50 border border-orange-100 text-orange-700 rounded-xl text-xs flex items-center gap-3 italic">
              <HelpCircle className="w-4 h-4" />
              Balance sheet is out by {fmt(Math.abs(totalAssets - totalLE))}. Check for missing entries or run year-end closing.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
