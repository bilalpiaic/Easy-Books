"use client"

import { useEffect, useState } from "react"
import { Printer, HelpCircle, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtAmount, downloadCSV, fmtDate } from "@/lib/utils"
import { useSettings } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import DocLink from "@/components/DocLink"
import { AccountTreeRows, type TreeNode } from "@/components/AccountTree"
import { useTranslation } from "react-i18next"

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

interface BSTreeResponse {
  assets: TreeNode[]
  liabilities: TreeNode[]
  equity: TreeNode[]
  totals: { assets: number; liabilities: number; equity: number }
}

function today() { return new Date().toISOString().split("T")[0] }
function priorYear(d: string) { return `${parseInt(d.slice(0, 4)) - 1}${d.slice(4)}` }

/** Single-period tree section rendered with AccountTreeRows */
function TreeSection({
  title, nodes, total, totalLabel, fmt,
}: {
  title: string
  nodes: TreeNode[]
  total: number
  totalLabel: string
  fmt: (n: number) => string
}) {
  return (
    <section className="space-y-2">
      <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2">{title}</h3>
      <div className="overflow-x-auto table-freeze">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50">
            <th className="py-2 pr-3 text-left font-bold">Account</th>
            <th className="py-2 px-3 text-right font-bold">Balance</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--text-primary)]/5">
          <AccountTreeRows
            nodes={nodes}
            columns={[{ key: "balance", align: "right" }]}
            renderLeafLabel={(n) =>
              n.id != null
                ? <DocLink type="account" id={n.code} label={n.name} className="text-[var(--text-primary)]/60" />
                : <span className="text-[var(--text-primary)] font-medium italic">{n.name}</span>
            }
          />
        </tbody>
      </table>
      </div>
      <div className="flex justify-between pt-4 border-t border-[var(--text-primary)]/5 font-bold">
        <span className="text-[var(--text-primary)]">{totalLabel}</span>
        <span className="font-mono w-36 text-right underline decoration-double underline-offset-4">{fmt(total)}</span>
      </div>
    </section>
  )
}

/** Comparison-mode section (flat BalanceItem list) — unchanged */
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
      <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2">{title}</h3>
      {items.map(item => (
        <div key={item.code} className="flex justify-between text-sm">
          {item.code === "RE-CUR"
            ? <span className="text-[var(--text-primary)] font-medium italic">{item.name}</span>
            : <DocLink type="account" id={item.code} label={item.name} className="text-[var(--text-primary)]/60" />}
          <div className="flex gap-8">
            <span className="font-mono w-36 text-right">{fmt(item.balance)}</span>
            {showCmp && <span className="font-mono w-36 text-right text-[var(--text-primary)]/35">{fmt(cmpBal(item.code))}</span>}
          </div>
        </div>
      ))}
      <div className="flex justify-between pt-4 border-t border-[var(--text-primary)]/5 font-bold">
        <span className="text-[var(--text-primary)]">{totalLabel}</span>
        <div className="flex gap-8">
          <span className="font-mono w-36 text-right underline decoration-double underline-offset-4">{fmt(total)}</span>
          {showCmp && <span className="font-mono w-36 text-right underline decoration-double underline-offset-4 text-[var(--text-primary)]/35">{fmt(cmpTotal)}</span>}
        </div>
      </div>
    </section>
  )
}

export default function BalanceSheetPage() {
  const { t } = useTranslation()

  const { settings } = useSettings()

  // Flat state for comparison mode (unchanged)
  const [data, setData] = useState<BalanceItem[]>([])
  const [comparison, setComparison] = useState<BalanceItem[] | null>(null)

  // Tree state for single-period mode
  const [treeAssets, setTreeAssets] = useState<TreeNode[]>([])
  const [treeLiabilities, setTreeLiabilities] = useState<TreeNode[]>([])
  const [treeEquity, setTreeEquity] = useState<TreeNode[]>([])
  const [bsTotals, setBsTotals] = useState<{ assets: number; liabilities: number; equity: number }>({ assets: 0, liabilities: 0, equity: 0 })

  const [isLoading, setIsLoading] = useState(true)
  const [asOf, setAsOf] = useState(today())
  const [compareMode, setCompareMode] = useState(false)
  const [cmpEnd, setCmpEnd] = useState(priorYear(today()))

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams({ end: asOf })
    if (compareMode) params.set("compare_end", cmpEnd)
    apiFetch<BalanceItem[] | BSResponse | BSTreeResponse>(`/api/reports/balance-sheet?${params}`)
      .then(res => {
        if (compareMode && res && typeof res === "object" && "current" in res) {
          // Comparison mode: flat shape — unchanged
          setData((res as BSResponse).current ?? [])
          setComparison((res as BSResponse).comparison ?? null)
        } else if (!compareMode && res && typeof res === "object" && "assets" in res) {
          // Single-period mode: new tree shape
          const tree = res as BSTreeResponse
          setTreeAssets(tree.assets ?? [])
          setTreeLiabilities(tree.liabilities ?? [])
          setTreeEquity(tree.equity ?? [])
          setBsTotals(tree.totals ?? { assets: 0, liabilities: 0, equity: 0 })
          setData([])
          setComparison(null)
        } else {
          setData(Array.isArray(res) ? res : [])
          setComparison(null)
        }
        setIsLoading(false)
      })
      .catch(() => setIsLoading(false))
  }, [asOf, compareMode, cmpEnd])

  const fmt = (n: number) => fmtAmount(n, settings.currency)

  function flattenNodes(nodes: TreeNode[]): TreeNode[] {
    const out: TreeNode[] = []
    for (const n of nodes) { out.push(n); if (n.children?.length) out.push(...flattenNodes(n.children)) }
    return out
  }

  const exportCsv = () => {
    const rows = [
      ...flattenNodes(treeAssets).map(n => ({ Section: "Assets", Code: n.code, Name: n.name, Balance: (n.balance as number) ?? 0 })),
      ...flattenNodes(treeLiabilities).map(n => ({ Section: "Liabilities", Code: n.code, Name: n.name, Balance: (n.balance as number) ?? 0 })),
      ...flattenNodes(treeEquity).map(n => ({ Section: "Equity", Code: n.code, Name: n.name, Balance: (n.balance as number) ?? 0 })),
    ]
    downloadCSV(`balance-sheet-${asOf}.csv`, rows)
  }

  // Comparison-mode derived values (unchanged)
  const cmpAssets      = comparison?.filter(i => i.type === "Asset") ?? []
  const cmpLiabilities = comparison?.filter(i => i.type === "Liability") ?? []
  const cmpEquity      = comparison?.filter(i => i.type === "Equity") ?? []

  const flatAssets      = data.filter(i => i.type === "Asset")
  const flatLiabilities = data.filter(i => i.type === "Liability")
  const flatEquity      = data.filter(i => i.type === "Equity")

  const cmpTotalAssets      = cmpAssets.reduce((s, i) => s + i.balance, 0)
  const cmpTotalLiabilities = cmpLiabilities.reduce((s, i) => s + i.balance, 0)
  const cmpTotalEquity      = cmpEquity.reduce((s, i) => s + i.balance, 0)

  const flatTotalAssets      = flatAssets.reduce((s, i) => s + i.balance, 0)
  const flatTotalLiabilities = flatLiabilities.reduce((s, i) => s + i.balance, 0)
  const flatTotalEquity      = flatEquity.reduce((s, i) => s + i.balance, 0)

  // Totals: tree values in single-period mode, flat values in compare mode
  const totalAssets      = compareMode ? flatTotalAssets      : bsTotals.assets
  const totalLiabilities = compareMode ? flatTotalLiabilities : bsTotals.liabilities
  const totalEquity      = compareMode ? flatTotalEquity      : bsTotals.equity
  const totalLE          = totalLiabilities + totalEquity
  const isBalanced       = Math.abs(totalAssets - totalLE) <= 0.01

  return (
    <div className="max-w-4xl mx-auto">
      <PrintHeader title="Balance Sheet" subtitle={`As of ${fmtDate(asOf)}`} />
      <div className="flex justify-between items-center mb-8 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Balance Sheet</h1>
          <p className="text-[var(--text-primary)]/60">Financial position as of {fmtDate(asOf)}</p>
        </div>
        <div className="flex items-center gap-2">
          {!compareMode && (
            <button onClick={exportCsv} disabled={isLoading} className="p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60 disabled:opacity-40" title="Export CSV">
              <Download className="w-5 h-5" />
            </button>
          )}
          <button onClick={() => window.print()} className="p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60" title="Print">
            <Printer className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl space-y-3 print:hidden">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">As of</span>
          <input type="date" value={asOf} onChange={e => setAsOf(e.target.value)}
                 className="px-3 py-1.5 text-sm border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)]" />
        </div>
        <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]/70 cursor-pointer">
          <input type="checkbox" checked={compareMode} onChange={e => setCompareMode(e.target.checked)} className="rounded" />
          Compare with prior period
        </label>
        {compareMode && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-[var(--text-primary)]/50">Prior period as of:</span>
            <input type="date" value={cmpEnd} onChange={e => setCmpEnd(e.target.value)}
                   className="border border-[var(--border)] rounded px-2 py-1 text-sm" />
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="text-center py-20 text-[var(--text-primary)]/75">Generating report...</div>
      ) : (
        <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 p-10 space-y-12">
          {compareMode ? (
            <>
              {comparison && (
                <div className="flex justify-end gap-8 text-xs font-bold text-[var(--text-primary)]/50 uppercase tracking-widest">
                  <span className="w-36 text-right">Current Period</span>
                  <span className="w-36 text-right text-[var(--text-primary)]/30">Comparative Period</span>
                </div>
              )}

              <BalanceSection title="Assets" items={flatAssets} cmpItems={cmpAssets}
                total={flatTotalAssets} cmpTotal={cmpTotalAssets} totalLabel="Total Assets"
                fmt={fmt} showCmp={!!comparison} />

              <BalanceSection title="Liabilities" items={flatLiabilities} cmpItems={cmpLiabilities}
                total={flatTotalLiabilities} cmpTotal={cmpTotalLiabilities} totalLabel="Total Liabilities"
                fmt={fmt} showCmp={!!comparison} />

              <BalanceSection title="Equity" items={flatEquity} cmpItems={cmpEquity}
                total={flatTotalEquity} cmpTotal={cmpTotalEquity} totalLabel="Total Equity"
                fmt={fmt} showCmp={!!comparison} />
            </>
          ) : (
            <>
              <TreeSection title="Assets" nodes={treeAssets}
                total={bsTotals.assets} totalLabel="Total Assets" fmt={fmt} />

              <TreeSection title="Liabilities" nodes={treeLiabilities}
                total={bsTotals.liabilities} totalLabel="Total Liabilities" fmt={fmt} />

              <TreeSection title="Equity" nodes={treeEquity}
                total={bsTotals.equity} totalLabel="Total Equity" fmt={fmt} />
            </>
          )}

          <section className="pt-8 border-t-2 border-[var(--text-primary)] flex justify-between items-center bg-[var(--bg-page)]/30 -mx-10 px-10 py-6">
            <h2 className="text-xl font-bold text-[var(--text-primary)]">Total Liabilities &amp; Equity</h2>
            <div className="flex gap-8">
              <div className="text-2xl font-bold w-36 text-right text-[var(--text-primary)]">{fmt(totalLE)}</div>
              {compareMode && comparison && (
                <div className="text-xl font-bold w-36 text-right text-[var(--text-primary)]/35">{fmt(cmpTotalLiabilities + cmpTotalEquity)}</div>
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
