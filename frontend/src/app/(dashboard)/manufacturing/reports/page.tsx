"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { BarChart2, Printer, AlertTriangle, PackageCheck, Users, Download } from "lucide-react"
import PrintHeader from "@/components/PrintHeader"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import { useTranslation } from "react-i18next"

/* ── Types ── */

interface WipBucket { count: number; total_wip_cost: string }
interface WipAging {
  summary: Record<string, WipBucket>
  buckets: Record<string, Array<{
    id: number; number: string; customer_id: number
    output_qty: string; own_material_cost: string
    started_at: string; age_days: number
  }>>
}

interface ProdSummary {
  [state: string]: { count: number; output_qty: string; cost: string }
}

interface CustodyRow {
  customer_id: number; customer_name: string
  product_id: number; product: { code: string; name: string; unit: string }
  qty_on_hand: string; declared_value_open: string
}

/* ── Helpers ── */

const AGING_BUCKETS = ["0-7d", "8-14d", "15-30d", "30d+"]
const AGING_TONE: Record<string, string> = {
  "0-7d":  "bg-emerald-50 border-emerald-200 text-emerald-800",
  "8-14d": "bg-amber-50 border-amber-200 text-amber-800",
  "15-30d":"bg-orange-50 border-orange-200 text-orange-800",
  "30d+":  "bg-red-50 border-red-200 text-red-800",
}

const STATE_ORDER = ["draft","started","completed","delivered","billed","cancelled"]
const STATE_TONE: Record<string, string> = {
  draft:     "bg-slate-100 text-slate-700",
  started:   "bg-amber-100 text-amber-900",
  completed: "bg-blue-100 text-blue-900",
  delivered: "bg-emerald-100 text-emerald-900",
  billed:    "bg-violet-100 text-violet-900",
  cancelled: "bg-red-100 text-red-800",
}

function fmt0(v: string) {
  const n = Number(v); return isNaN(n) ? v : n.toFixed(0)
}

/* ── Page ── */

type Tab = "wip-aging" | "production-summary" | "customer-custody"

export default function ManufacturingReportsPage() {
  const { t } = useTranslation()

  const fmt = useFmt()

  const [tab, setTab] = useState<Tab>("wip-aging")

  const [wip,     setWip]     = useState<WipAging | null>(null)
  const [summary, setSummary] = useState<ProdSummary | null>(null)
  const [custody, setCustody] = useState<CustodyRow[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)

  useEffect(() => {
    setLoading(true); setError(null)
    const promises: Promise<void>[] = []

    if (!wip)
      promises.push(
        apiFetch<WipAging>("/api/manufacturing/wip-aging")
          .then(setWip)
          .catch(e => { throw e })
      )
    if (!summary)
      promises.push(
        apiFetch<ProdSummary>("/api/manufacturing/production-summary")
          .then(setSummary)
          .catch(e => { throw e })
      )
    if (!custody)
      promises.push(
        apiFetch<CustodyRow[]>("/api/manufacturing/customer-custody")
          .then(setCustody)
          .catch(e => { throw e })
      )

    Promise.all(promises)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const totalWip = wip
    ? AGING_BUCKETS.reduce((s, k) => s + Number(wip.summary[k]?.total_wip_cost ?? 0), 0)
    : 0

  return (
    <div className="space-y-5">
      <PrintHeader title="Manufacturing Reports" orientation="landscape" />

      <header className="flex items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <BarChart2 className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Manufacturing Reports</h1>
            <p className="text-sm text-[#1a1814]/60">WIP aging, production summary, and customer custody.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (tab === "wip-aging" && wip) {
                const rows = AGING_BUCKETS.flatMap(b => (wip.buckets[b] ?? []).map(o => ({ Bucket: b, "Order #": o.number, "Age Days": o.age_days, "Output Qty": o.output_qty, "Material Cost": o.own_material_cost })))
                downloadCSV('mfg-wip-aging.csv', rows)
              } else if (tab === "production-summary" && summary) {
                downloadCSV('mfg-production-summary.csv', STATE_ORDER.filter(s => summary[s]).map(s => ({ State: s, Count: summary[s].count, "Output Qty": summary[s].output_qty, Cost: summary[s].cost })))
              } else if (tab === "customer-custody" && custody) {
                downloadCSV('mfg-customer-custody.csv', custody.map(r => ({ Customer: r.customer_name, "Product Code": r.product.code, Product: r.product.name, Unit: r.product.unit, "Qty On Hand": r.qty_on_hand, "Declared Value": r.declared_value_open })))
              }
            }}
            disabled={!wip && !summary && !custody}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm hover:bg-[#f6f3ee] transition-colors">
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
        </div>
      </header>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-[#ede9e2] print:hidden">
        {(["wip-aging","production-summary","customer-custody"] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-[#b8943f] text-[#b8943f]"
                : "border-transparent text-[#1a1814]/60 hover:text-[#1a1814]"
            }`}>
            {t === "wip-aging" && "WIP Aging"}
            {t === "production-summary" && "Production Summary"}
            {t === "customer-custody" && "Customer Custody"}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-[#1a1814]/60">Loading…</p>}
      {error   && <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {/* ── WIP Aging ── */}
      {tab === "wip-aging" && wip && (
        <div className="space-y-4">
          {/* Age bucket summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {AGING_BUCKETS.map(bucket => {
              const s = wip.summary[bucket] ?? { count: 0, total_wip_cost: "0" }
              return (
                <div key={bucket} className={`border rounded-xl px-4 py-3 ${AGING_TONE[bucket]}`}>
                  <div className="text-xs font-semibold opacity-75 flex items-center gap-1">
                    {bucket === "30d+" && <AlertTriangle className="w-3 h-3" />}
                    {bucket}
                  </div>
                  <div className="text-xl font-serif font-bold mt-0.5">{s.count} PO{s.count !== 1 ? "s" : ""}</div>
                  <div className="text-xs mt-0.5 opacity-70">WIP: {fmt(Number(s.total_wip_cost))}</div>
                </div>
              )
            })}
          </div>

          {/* Total WIP */}
          <div className="bg-[#faf8f4] border border-[#ede9e2] rounded-xl px-4 py-3 flex items-center justify-between">
            <span className="text-sm font-medium text-[#1a1814]/70">Total open WIP cost</span>
            <span className="text-lg font-serif font-bold text-[#1a1814]">{fmt(totalWip)}</span>
          </div>

          {/* Per-bucket detail tables */}
          {AGING_BUCKETS.map(bucket => {
            const items = wip.buckets[bucket] ?? []
            if (!items.length) return null
            return (
              <div key={bucket} className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
                <div className={`px-4 py-2.5 border-b border-[#ede9e2] text-xs font-semibold ${AGING_TONE[bucket]} bg-opacity-50`}>
                  {bucket} — {items.length} order{items.length !== 1 ? "s" : ""}
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-[#faf8f4] text-[#1a1814]/60 text-xs">
                    <tr>
                      <th className="text-left px-4 py-2">PO #</th>
                      <th className="text-left px-4 py-2">{t('col.customer', 'Customer')}</th>
                      <th className="text-right px-4 py-2">Output Qty</th>
                      <th className="text-right px-4 py-2">WIP Cost</th>
                      <th className="text-right px-4 py-2">Age (days)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map(po => (
                      <tr key={po.id} className="border-t border-[#ede9e2] hover:bg-[#faf8f4]">
                        <td className="px-4 py-2 font-mono text-xs">
                          <Link href="/manufacturing/production-orders" className="text-[#b8943f] hover:underline">
                            {po.number}
                          </Link>
                        </td>
                        <td className="px-4 py-2 text-sm">#{po.customer_id}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{fmt0(po.output_qty)}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{fmt(Number(po.own_material_cost))}</td>
                        <td className={`px-4 py-2 text-right tabular-nums font-semibold ${po.age_days > 30 ? "text-red-700" : po.age_days > 14 ? "text-orange-700" : ""}`}>
                          {po.age_days}d
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          })}

          {Object.values(wip.buckets).every(b => b.length === 0) && (
            <div className="bg-white border border-[#ede9e2] rounded-xl px-6 py-10 text-center">
              <PackageCheck className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
              <p className="text-sm font-medium text-[#1a1814]">No open WIP orders</p>
              <p className="text-xs text-[#1a1814]/55 mt-1">All started orders have been completed.</p>
            </div>
          )}
        </div>
      )}

      {/* ── Production Summary ── */}
      {tab === "production-summary" && summary && (
        <div className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#faf6ec] text-[#1a1814]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-3">State</th>
                <th className="text-right px-4 py-3">PO Count</th>
                <th className="text-right px-4 py-3">Output Qty</th>
                <th className="text-right px-4 py-3">Material Cost</th>
              </tr>
            </thead>
            <tbody>
              {STATE_ORDER.filter(s => summary[s]).map(state => {
                const row = summary[state]
                return (
                  <tr key={state} className="border-t border-[#ede9e2] hover:bg-[#faf8f4]">
                    <td className="px-4 py-2.5">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold ${STATE_TONE[state] ?? ""}`}>
                        {state}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-semibold">{row.count}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{fmt0(row.output_qty)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{fmt(Number(row.cost))}</td>
                  </tr>
                )
              })}
              {/* Totals */}
              {Object.keys(summary).length > 0 && (() => {
                const totalCount = STATE_ORDER.reduce((s, k) => s + (summary[k]?.count ?? 0), 0)
                const totalQty   = STATE_ORDER.reduce((s, k) => s + Number(summary[k]?.output_qty ?? 0), 0)
                const totalCost  = STATE_ORDER.reduce((s, k) => s + Number(summary[k]?.cost ?? 0), 0)
                return (
                  <tr className="border-t-2 border-[#b8943f]/40 bg-[#faf6ec] font-semibold">
                    <td className="px-4 py-2.5 text-xs uppercase tracking-wide text-[#1a1814]/70">{t('col.total', 'Total')}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{totalCount}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{totalQty.toFixed(0)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{fmt(totalCost)}</td>
                  </tr>
                )
              })()}
            </tbody>
          </table>
          {Object.keys(summary).length === 0 && (
            <div className="px-6 py-10 text-center text-sm text-[#1a1814]/50">No production orders yet.</div>
          )}
        </div>
      )}

      {/* ── Customer Custody ── */}
      {tab === "customer-custody" && custody && (
        <div className="space-y-4">
          <div className="bg-[#faf8f4] border border-[#ede9e2] rounded-xl px-4 py-3 text-xs text-[#1a1814]/70">
            <span className="font-semibold text-[#1a1814]/90">What this shows: </span>
            Customer-supplied goods currently held in your custody (custodial inventory layers with qty &gt; 0).
            These are <em>off-balance-sheet</em> — they belong to your customers, not you.
          </div>

          {custody.length === 0 ? (
            <div className="bg-white border border-[#ede9e2] rounded-xl px-6 py-10 text-center">
              <Users className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-2" />
              <p className="text-sm font-medium text-[#1a1814]">No customer goods on hand</p>
              <p className="text-xs text-[#1a1814]/55 mt-1">
                Customer-supplied material is recorded via{" "}
                <Link href="/manufacturing/grn" className="text-[#b8943f] hover:underline">Goods Receipts</Link>.
              </p>
            </div>
          ) : (
            <div className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-[#faf6ec] text-[#1a1814]/70 text-xs uppercase tracking-wide">
                  <tr>
                    <th className="text-left px-4 py-3">{t('col.customer', 'Customer')}</th>
                    <th className="text-left px-4 py-3">{t('col.product', 'Product')}</th>
                    <th className="text-right px-4 py-3">Qty on Hand</th>
                    <th className="text-right px-4 py-3">{t('col.unit', 'Unit')}</th>
                    <th className="text-right px-4 py-3">Declared Value (open GRNs)</th>
                  </tr>
                </thead>
                <tbody>
                  {custody.map((row, i) => (
                    <tr key={i} className="border-t border-[#ede9e2] hover:bg-[#faf8f4]">
                      <td className="px-4 py-2.5 font-medium">
                        <Link href={`/customers/${row.customer_id}/ledger`} className="text-[#b8943f] hover:underline">
                          {row.customer_name || `#${row.customer_id}`}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="font-mono text-xs text-[#1a1814]/70 mr-1">{row.product.code}</span>
                        {row.product.name}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums font-semibold">
                        {Number(row.qty_on_hand).toFixed(2)}
                      </td>
                      <td className="px-4 py-2.5 text-right text-[#1a1814]/60 text-xs">{row.product.unit}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">
                        {Number(row.declared_value_open) > 0 ? fmt(Number(row.declared_value_open)) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
                {/* Per-customer subtotals */}
                {(() => {
                  const byCustomer = custody.reduce<Record<string, { name: string; qty: number; value: number }>>((acc, r) => {
                    const k = String(r.customer_id)
                    if (!acc[k]) acc[k] = { name: r.customer_name, qty: 0, value: 0 }
                    acc[k].qty   += Number(r.qty_on_hand)
                    acc[k].value += Number(r.declared_value_open)
                    return acc
                  }, {})
                  const entries = Object.entries(byCustomer)
                  if (entries.length <= 1) return null
                  return (
                    <tfoot className="border-t-2 border-[#b8943f]/40 bg-[#faf6ec] text-xs font-semibold">
                      {entries.map(([cid, c]) => (
                        <tr key={cid} className="border-t border-[#ede9e2]">
                          <td className="px-4 py-2 text-[#1a1814]/70" colSpan={2}>
                            {c.name} — subtotal
                          </td>
                          <td className="px-4 py-2 text-right tabular-nums">{c.qty.toFixed(2)}</td>
                          <td />
                          <td className="px-4 py-2 text-right tabular-nums">
                            {c.value > 0 ? fmt(c.value) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tfoot>
                  )
                })()}
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
