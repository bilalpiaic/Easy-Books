"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Printer, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
import { AccountTreeRows, type TreeNode } from "@/components/AccountTree"
import { useTranslation } from "react-i18next"

interface TrialBalanceTotals {
  debit: number
  credit: number
}

interface TrialBalanceResponse {
  tree: TreeNode[]
  totals: TrialBalanceTotals
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

function flatten(nodes: TreeNode[]): TreeNode[] {
  const result: TreeNode[] = []
  for (const n of nodes) {
    result.push(n)
    if (n.children && n.children.length > 0) {
      result.push(...flatten(n.children))
    }
  }
  return result
}

export default function TrialBalancePage() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const [tree, setTree] = useState<TreeNode[]>([])
  const [totals, setTotals] = useState<TrialBalanceTotals>({ debit: 0, credit: 0 })
  const [isLoading, setIsLoading] = useState(true)
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)

  useEffect(() => {
    setIsLoading(true)
    apiFetch<TrialBalanceResponse>(`/api/reports/trial-balance?start=${start}&end=${end}`)
      .then(res => { setTree(res.tree ?? []); setTotals(res.totals ?? { debit: 0, credit: 0 }); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [start, end])

  const grandTotalDebit = totals.debit
  const grandTotalCredit = totals.credit
  const hasData = tree.length > 0

  return (
    <div className="max-w-5xl mx-auto">
      <PrintHeader title="Trial Balance" subtitle={`Period: ${start} — ${end}`} />
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Trial Balance</h1>
          <p className="text-[var(--text-primary)]/60">Debit and credit totals per account</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => window.print()} className="p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60 print:hidden" title="Print">
            <Printer className="w-5 h-5" />
          </button>
          <button
            onClick={() => downloadCSV(`trial-balance-${start}-${end}.csv`, flatten(tree).map(d => ({ Code: d.code, Name: d.name, Type: d.type, Debit: d.debit, Credit: d.credit })))}
            className="p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60 print:hidden"
            title="Export CSV"
          >
            <Download className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl print:hidden">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="overflow-x-auto table-freeze freeze-col">
        <table className="w-full text-left border-collapse min-w-[480px]">
          <thead>
            <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">{t('col.account', 'Account')}</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">{t('col.debit', 'Debit')}</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">{t('col.credit', 'Credit')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--text-primary)]/5">
            {isLoading ? (
              <tr><td colSpan={3} className="px-8 py-10 text-center text-[var(--text-primary)]/75">Generating report...</td></tr>
            ) : !hasData ? (
              <tr><td colSpan={3} className="px-8 py-10 text-center text-[var(--text-primary)]/75">No balances found for selected period.</td></tr>
            ) : (
              <AccountTreeRows
                nodes={tree}
                columns={[{ key: "debit", align: "right" }, { key: "credit", align: "right" }]}
                renderLeafLabel={(n) => (
                  <Link href={`/ledger?account=${encodeURIComponent(n.code)}&start=${start}&end=${end}`}
                        className="hover:text-[var(--primary)] hover:underline">{n.name}</Link>
                )}
              />
            )}
          </tbody>
          {!isLoading && hasData && (
            <tfoot>
              <tr className="bg-[var(--text-primary)] text-white">
                <td className="px-8 py-5 font-bold uppercase tracking-widest text-xs">Grand Total</td>
                <td className="px-8 py-5 text-right font-mono font-bold">{fmt(grandTotalDebit)}</td>
                <td className="px-8 py-5 text-right font-mono font-bold">{fmt(grandTotalCredit)}</td>
              </tr>
            </tfoot>
          )}
        </table>
        </div>
      </div>

      {!isLoading && Math.abs(grandTotalDebit - grandTotalCredit) > 0.01 && (
        <div className="mt-6 p-4 bg-red-50 border border-red-100 text-red-700 rounded-xl text-sm flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          Warning: Trial balance is not matching. Difference: {fmt(Math.abs(grandTotalDebit - grandTotalCredit))}
        </div>
      )}
    </div>
  )
}
