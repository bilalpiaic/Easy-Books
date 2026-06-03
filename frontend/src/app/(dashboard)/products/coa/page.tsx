"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { TableProperties, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface CoaItem {
  id: number
  code: string | null
  name: string
  qty: number
  avg_rate: number
  value: number
}

interface CoaSub {
  name: string
  qty: number
  value: number
  items: CoaItem[]
}

interface CoaGroup {
  name: string
  qty: number
  value: number
  subs: CoaSub[]
}

interface CoaData {
  groups: CoaGroup[]
  grand: { qty: number; value: number }
}

export default function ProductCoaPage() {
  const fmt = useFmt()
  const [data, setData] = useState<CoaData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setIsLoading(true)
    apiFetch<CoaData>("/api/reports/product-coa")
      .then(d => { setData(d); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [])

  const exportCsv = () => {
    if (!data) return
    const rows: Record<string, unknown>[] = []
    for (const g of data.groups)
      for (const s of g.subs)
        for (const it of s.items)
          rows.push({
            Main: g.name, Sub: s.name, Code: it.code ?? "", Item: it.name,
            Qty: it.qty, "Avg Rate": it.avg_rate, Value: it.value,
          })
    downloadCSV("product-coa.csv", rows)
  }

  return (
    <div className="max-w-5xl mx-auto">
      <PrintHeader title="Product Chart of Accounts" subtitle="Closing stock valuation by category" />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Product COA</h1>
          <p className="text-[#1a1814]/60">Main → Sub → Item with closing qty, avg rate &amp; value</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => window.print()}
            className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60"
            title="Print"
          >
            <Printer className="w-5 h-5" />
          </button>
          <button
            onClick={exportCsv}
            className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] transition-colors text-[#1a1814]/60"
            title="Export CSV"
          >
            <Download className="w-5 h-5" />
          </button>
          <TableProperties className="w-7 h-7 text-[#b8943f] hidden md:block self-center" />
        </div>
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[640px]">
            <thead>
              <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
                <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Category / Product</th>
                <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Qty</th>
                <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Avg Rate</th>
                <th className="px-6 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Value</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1a1814]/5">
              {isLoading ? (
                <tr><td colSpan={4} className="px-6 py-10 text-center text-[#1a1814]/60">Loading…</td></tr>
              ) : !data || data.groups.length === 0 ? (
                <tr><td colSpan={4} className="px-6 py-10 text-center text-[#1a1814]/60">No products found.</td></tr>
              ) : (
                data.groups.map(g => (
                  <FragmentGroup key={g.name} group={g} fmt={fmt} />
                ))
              )}
            </tbody>
            {!isLoading && data && data.groups.length > 0 && (
              <tfoot>
                <tr className="bg-[#1a1814] text-white">
                  <td className="px-6 py-5 font-bold uppercase tracking-widest text-xs">Grand Total</td>
                  <td className="px-6 py-5 text-right font-mono font-bold">{Number(data.grand.qty).toLocaleString()}</td>
                  <td />
                  <td className="px-6 py-5 text-right font-mono font-bold">{fmt(data.grand.value)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </div>
  )
}

function FragmentGroup({ group, fmt }: { group: CoaGroup; fmt: (n: number) => string }) {
  return (
    <>
      {/* Main category row */}
      <tr className="bg-[#f6f3ee]/60">
        <td className="px-6 py-3 font-semibold text-[#1a1814]">{group.name}</td>
        <td className="px-6 py-3 text-right font-mono text-sm text-[#1a1814]">{Number(group.qty).toLocaleString()}</td>
        <td />
        <td className="px-6 py-3 text-right font-mono text-sm font-semibold text-[#1a1814]">{fmt(group.value)}</td>
      </tr>
      {group.subs.map(sub => (
        <FragmentSub key={`${group.name}-${sub.name}`} sub={sub} fmt={fmt} />
      ))}
    </>
  )
}

function FragmentSub({ sub, fmt }: { sub: CoaSub; fmt: (n: number) => string }) {
  return (
    <>
      {/* Sub category row */}
      <tr>
        <td className="px-6 py-2 pl-10 font-medium text-sm text-[#1a1814]/80">{sub.name}</td>
        <td className="px-6 py-2 text-right font-mono text-xs text-[#1a1814]/70">{Number(sub.qty).toLocaleString()}</td>
        <td />
        <td className="px-6 py-2 text-right font-mono text-xs text-[#1a1814]/70">{fmt(sub.value)}</td>
      </tr>
      {sub.items.map(it => (
        <tr key={it.id} className="hover:bg-[#f6f3ee]/30 transition-colors">
          <td className="px-6 py-2 pl-16 text-sm">
            <Link
              href={`/products/ledger?product=${it.id}`}
              className="text-[#1a1814]/90 hover:text-[#b8943f] hover:underline"
              title="View product ledger"
            >
              {it.name}
            </Link>
            {it.code && <span className="ml-2 font-mono text-xs text-[#b8943f]">{it.code}</span>}
          </td>
          <td className="px-6 py-2 text-right font-mono text-sm text-[#1a1814]">{Number(it.qty).toLocaleString()}</td>
          <td className="px-6 py-2 text-right font-mono text-sm text-[#1a1814]/70">{fmt(it.avg_rate)}</td>
          <td className="px-6 py-2 text-right font-mono text-sm text-[#1a1814]">{fmt(it.value)}</td>
        </tr>
      ))}
    </>
  )
}
