"use client"

import { useEffect, useState } from "react"
import { Printer, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtAmount, downloadCSV } from "@/lib/utils"
import { useSettings } from "@/context/SettingsContext"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
import DocLink from "@/components/DocLink"
import { AccountTreeRows, type TreeNode } from "@/components/AccountTree"
import { useTranslation } from "react-i18next"

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

interface PnLTreeResponse {
  revenue: TreeNode[]
  expenses: TreeNode[]
  totals: { revenue: number; expenses: number; net_profit: number }
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
  const { t } = useTranslation()

  const { settings } = useSettings()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<PnLItem[]>([])
  const [comparison, setComparison] = useState<PnLItem[] | null>(null)
  const [compareMode, setCompareMode] = useState(false)

  // Tree state for single-period mode
  const [treeRevenue, setTreeRevenue] = useState<TreeNode[]>([])
  const [treeExpenses, setTreeExpenses] = useState<TreeNode[]>([])
  const [plTotals, setPlTotals] = useState<{ revenue: number; expenses: number; net_profit: number }>({ revenue: 0, expenses: 0, net_profit: 0 })
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
    apiFetch<PnLItem[] | PnLResponse | PnLTreeResponse>(`/api/reports/income-statement?${params}`)
      .then(res => {
        if (compareMode && res && typeof res === "object" && "current" in res) {
          // Comparison mode: flat shape — unchanged
          setData((res as PnLResponse).current ?? [])
          setComparison((res as PnLResponse).comparison ?? null)
        } else if (!compareMode && res && typeof res === "object" && "revenue" in res) {
          // Single-period mode: new tree shape
          const tree = res as PnLTreeResponse
          setTreeRevenue(tree.revenue ?? [])
          setTreeExpenses(tree.expenses ?? [])
          setPlTotals(tree.totals ?? { revenue: 0, expenses: 0, net_profit: 0 })
          setData([])
          setComparison(null)
        } else {
          setData(Array.isArray(res) ? res : [])
          setComparison(null)
        }
        setIsLoading(false)
      })
      .catch(() => setIsLoading(false))
  }, [start, end, compareMode, cmpStart, cmpEnd])

  // Comparison-mode derived values (unchanged)
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

  function flattenNodes(nodes: TreeNode[]): TreeNode[] {
    const out: TreeNode[] = []
    for (const n of nodes) { out.push(n); if (n.children?.length) out.push(...flattenNodes(n.children)) }
    return out
  }

  const exportCsv = () => {
    const rows = [
      ...flattenNodes(treeRevenue).map(n => ({ Section: "Revenue", Code: n.code, Name: n.name, Amount: (n.amount as number) ?? 0 })),
      ...flattenNodes(treeExpenses).map(n => ({ Section: "Expense", Code: n.code, Name: n.name, Amount: (n.amount as number) ?? 0 })),
    ]
    downloadCSV(`income-statement-${start}-${end}.csv`, rows)
  }

  return (
    <div className="max-w-4xl mx-auto">
      <PrintHeader title="Income Statement" subtitle={`Period: ${start} — ${end}`} />
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Income Statement</h1>
          <p className="text-[var(--text-primary)]/60">Revenue and expenses for the selected period</p>
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

      <div className="mb-4 p-4 bg-white border border-[var(--border)] rounded-xl space-y-3 print:hidden">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]/70 cursor-pointer">
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
            <span className="text-[var(--text-primary)]/50">Prior period:</span>
            <input type="date" value={cmpStart} onChange={e => setCmpStart(e.target.value)}
                   className="border border-[var(--border)] rounded px-2 py-1 text-sm" />
            <span className="text-[var(--text-primary)]/50">to</span>
            <input type="date" value={cmpEnd} onChange={e => setCmpEnd(e.target.value)}
                   className="border border-[var(--border)] rounded px-2 py-1 text-sm" />
          </div>
        )}
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 p-10 space-y-12">
        {compareMode ? (
          <>
            {comparison && (
              <div className="flex justify-end gap-8 text-xs font-bold text-[var(--text-primary)]/50 uppercase tracking-widest">
                <span className="w-36 text-right">Current Period</span>
                <span className="w-36 text-right text-[var(--text-primary)]/30">Comparative Period</span>
              </div>
            )}

            <section className="space-y-4">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2">Revenue</h3>
              {isLoading ? (
                <div className="text-sm text-[var(--text-primary)]/75 italic">{t('common.loading', 'Loading...')}</div>
              ) : revenueItems.length === 0 ? (
                <div className="text-sm text-[var(--text-primary)]/75 italic">No revenue in selected period.</div>
              ) : (
                revenueItems.map(item => (
                  <div key={item.name} className="flex justify-between text-sm">
                    <DocLink type="account" id={item.name} label={item.name} className="text-[var(--text-primary)]/60" />
                    <div className="flex gap-8">
                      <span className="font-mono w-36 text-right">{fmt(item.total_credit - item.total_debit)}</span>
                      {comparison && (
                        <span className="font-mono w-36 text-right text-[var(--text-primary)]/35">{fmt(cmpAmount(item.name, "Revenue"))}</span>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div className="flex justify-between pt-4 border-t border-[var(--text-primary)]/5 font-bold">
                <span className="text-[var(--text-primary)]">Total Revenue</span>
                <div className="flex gap-8">
                  <span className="font-mono w-36 text-right underline decoration-double underline-offset-4">{fmt(totalRevenue)}</span>
                  {comparison && (
                    <span className="font-mono w-36 text-right underline decoration-double underline-offset-4 text-[var(--text-primary)]/35">{fmt(cmpTotalRevenue)}</span>
                  )}
                </div>
              </div>
            </section>

            <section className="space-y-4">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2">Expenses</h3>
              {isLoading ? (
                <div className="text-sm text-[var(--text-primary)]/75 italic">{t('common.loading', 'Loading...')}</div>
              ) : expenseItems.length === 0 ? (
                <div className="text-sm text-[var(--text-primary)]/75 italic">No expenses in selected period.</div>
              ) : (
                expenseItems.map(item => (
                  <div key={item.name} className="flex justify-between text-sm">
                    <DocLink type="account" id={item.name} label={item.name} className="text-[var(--text-primary)]/60" />
                    <div className="flex gap-8">
                      <span className="font-mono w-36 text-right">({fmt(item.total_debit - item.total_credit)})</span>
                      {comparison && (
                        <span className="font-mono w-36 text-right text-[var(--text-primary)]/35">({fmt(cmpAmount(item.name, "Expense"))})</span>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div className="flex justify-between pt-4 border-t border-[var(--text-primary)]/5 font-bold text-red-600">
                <span>Total Operating Expenses</span>
                <div className="flex gap-8">
                  <span className="font-mono w-36 text-right">({fmt(totalExpense)})</span>
                  {comparison && (
                    <span className="font-mono w-36 text-right text-red-300">({fmt(cmpTotalExpense)})</span>
                  )}
                </div>
              </div>
            </section>

            <section className="pt-8 border-t-2 border-[var(--text-primary)] flex justify-between items-end">
              <div>
                <h2 className="text-2xl font-bold text-[var(--text-primary)]">Net Income</h2>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75">
                  {start} — {end}
                </p>
              </div>
              <div className="flex gap-8 items-end">
                <div className={`text-3xl font-bold w-36 text-right ${netIncome >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {netIncome < 0 && "("}{fmt(Math.abs(netIncome))}{netIncome < 0 && ")"}
                </div>
                {comparison && (
                  <div className={`text-xl font-bold w-36 text-right ${cmpNetIncome >= 0 ? "text-green-300" : "text-red-300"}`}>
                    {cmpNetIncome < 0 && "("}{fmt(Math.abs(cmpNetIncome))}{cmpNetIncome < 0 && ")"}
                  </div>
                )}
              </div>
            </section>
          </>
        ) : (
          <>
            {/* Single-period tree view */}
            <section className="space-y-2">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2">Revenue</h3>
              {isLoading ? (
                <div className="text-sm text-[var(--text-primary)]/75 italic">{t('common.loading', 'Loading...')}</div>
              ) : treeRevenue.length === 0 ? (
                <div className="text-sm text-[var(--text-primary)]/75 italic">No revenue in selected period.</div>
              ) : (
                <div className="overflow-x-auto table-freeze">
                <table className="w-full text-left border-collapse min-w-[320px]">
                  <thead>
                    <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50">
                      <th className="py-2 pr-3 text-left font-bold">Account</th>
                      <th className="py-2 px-3 text-right font-bold">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--text-primary)]/5">
                    <AccountTreeRows
                      nodes={treeRevenue}
                      columns={[{ key: "amount", align: "right" }]}
                      renderLeafLabel={(n) =>
                        n.id != null
                          ? <DocLink type="account" id={n.code} label={n.name} className="text-[var(--text-primary)]/60" />
                          : <span className="text-[var(--text-primary)] font-medium italic">{n.name}</span>
                      }
                    />
                  </tbody>
                </table>
                </div>
              )}
              <div className="flex justify-between pt-4 border-t border-[var(--text-primary)]/5 font-bold">
                <span className="text-[var(--text-primary)]">Total Revenue</span>
                <span className="font-mono w-36 text-right underline decoration-double underline-offset-4">{fmt(plTotals.revenue)}</span>
              </div>
            </section>

            <section className="space-y-2">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2">Expenses</h3>
              {isLoading ? (
                <div className="text-sm text-[var(--text-primary)]/75 italic">{t('common.loading', 'Loading...')}</div>
              ) : treeExpenses.length === 0 ? (
                <div className="text-sm text-[var(--text-primary)]/75 italic">No expenses in selected period.</div>
              ) : (
                <div className="overflow-x-auto table-freeze">
                <table className="w-full text-left border-collapse min-w-[320px]">
                  <thead>
                    <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50">
                      <th className="py-2 pr-3 text-left font-bold">Account</th>
                      <th className="py-2 px-3 text-right font-bold">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--text-primary)]/5">
                    <AccountTreeRows
                      nodes={treeExpenses}
                      columns={[{ key: "amount", align: "right" }]}
                      renderLeafLabel={(n) =>
                        n.id != null
                          ? <DocLink type="account" id={n.code} label={n.name} className="text-[var(--text-primary)]/60" />
                          : <span className="text-[var(--text-primary)] font-medium italic">{n.name}</span>
                      }
                    />
                  </tbody>
                </table>
                </div>
              )}
              <div className="flex justify-between pt-4 border-t border-[var(--text-primary)]/5 font-bold text-red-600">
                <span>Total Operating Expenses</span>
                <span className="font-mono w-36 text-right">({fmt(plTotals.expenses)})</span>
              </div>
            </section>

            <section className="pt-8 border-t-2 border-[var(--text-primary)] flex justify-between items-end">
              <div>
                <h2 className="text-2xl font-bold text-[var(--text-primary)]">Net Income</h2>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75">
                  {start} — {end}
                </p>
              </div>
              <div className={`text-3xl font-bold w-36 text-right ${plTotals.net_profit >= 0 ? "text-green-600" : "text-red-600"}`}>
                {plTotals.net_profit < 0 && "("}{fmt(Math.abs(plTotals.net_profit))}{plTotals.net_profit < 0 && ")"}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
