"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { Printer, Package } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"

interface GrnLine {
  id: number
  product_id: number
  qty: number
  lot_no: string | null
  declared_value: number
  notes: string | null
}

interface Grn {
  id: number
  number: string
  customer_id: number
  received_date: string
  location_id: number
  declared_value: number
  notes: string | null
  transaction_id: number | null
  created_at: string
  lines: GrnLine[]
}

interface Customer { id: number; name: string }
interface Product  { id: number; code: string; name: string }
interface StockLocation { id: number; code: string; name: string }

export default function GrnDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const fmt     = useFmt()

  const [grn, setGrn]           = useState<Grn | null>(null)
  const [customerMap, setCustomerMap] = useState<Record<number, string>>({})
  const [productMap, setProductMap]   = useState<Record<number, { code: string; name: string }>>({})
  const [locationMap, setLocationMap] = useState<Record<number, string>>({})
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<Grn>(`/api/grn/${id}`),
      apiFetch<{ items: Customer[] }>("/api/customers?limit=500"),
      apiFetch<{ items: Product[] }>("/api/products?limit=500"),
      apiFetch<{ items: StockLocation[] }>("/api/stock-locations"),
    ])
      .then(([g, cs, ps, ls]) => {
        setGrn(g)
        const cm: Record<number, string> = {}
        cs.items.forEach(c => { cm[c.id] = c.name })
        setCustomerMap(cm)
        const pm: Record<number, { code: string; name: string }> = {}
        ps.items.forEach(p => { pm[p.id] = { code: p.code, name: p.name } })
        setProductMap(pm)
        const lm: Record<number, string> = {}
        ls.items.forEach(l => { lm[l.id] = `${l.code} — ${l.name}` })
        setLocationMap(lm)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="text-sm text-[#1a1814]/50 py-8 text-center">Loading…</div>
  if (error || !grn) return <div className="text-sm text-red-700 py-8 text-center">{error ?? "GRN not found"}</div>

  const totalDeclared = grn.lines.reduce((s, l) => s + Number(l.declared_value), 0)

  return (
    <div className="max-w-3xl space-y-6">
      {/* Breadcrumb + actions */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link href="/manufacturing/grn" className="text-sm text-[#b8943f] hover:underline">
            ← Goods Receipt
          </Link>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814] mt-1">
            {grn.number}
          </h1>
        </div>
        <Link
          href={`/manufacturing/grn/${grn.id}/print`}
          className="inline-flex items-center gap-2 border border-[#ede9e2] rounded-lg px-3 py-2 text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors"
        >
          <Printer className="w-4 h-4" /> Print
        </Link>
      </div>

      {/* Header card */}
      <div className="bg-white border border-[#ede9e2] rounded-xl p-5">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-4 text-sm">
          <Field label="Customer">
            {customerMap[grn.customer_id] ?? `Customer #${grn.customer_id}`}
          </Field>
          <Field label="Received Date">{grn.received_date}</Field>
          <Field label="Location">
            {locationMap[grn.location_id] ?? `Location #${grn.location_id}`}
          </Field>
          <Field label="Total Declared Value">
            <span className={totalDeclared > 0 ? "font-semibold text-[#1a1814]" : "text-[#1a1814]/40"}>
              {totalDeclared > 0 ? fmt(totalDeclared) : "—"}
            </span>
          </Field>
          {grn.transaction_id && (
            <Field label="Memo JE">
              <Link href={`/journal?transaction_id=${grn.transaction_id}`} className="text-[#b8943f] hover:underline text-xs">
                View journal entry →
              </Link>
            </Field>
          )}
          {grn.notes && (
            <Field label="Notes" className="col-span-2 sm:col-span-3">
              {grn.notes}
            </Field>
          )}
        </div>
      </div>

      {/* Lines table */}
      <div className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-[#ede9e2] flex items-center gap-2">
          <Package className="w-4 h-4 text-[#b8943f]" />
          <h2 className="text-sm font-semibold text-[#1a1814]">Material Lines</h2>
          <span className="text-xs text-[#1a1814]/50">({grn.lines.length})</span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#ede9e2] bg-[#faf8f4]">
              <th className="text-left px-5 py-2.5 font-semibold text-[#1a1814]/70">Product</th>
              <th className="text-right px-4 py-2.5 font-semibold text-[#1a1814]/70">Qty</th>
              <th className="text-left px-4 py-2.5 font-semibold text-[#1a1814]/70">Lot No.</th>
              <th className="text-right px-4 py-2.5 font-semibold text-[#1a1814]/70">Declared Value</th>
              <th className="text-left px-4 py-2.5 font-semibold text-[#1a1814]/70">Notes</th>
            </tr>
          </thead>
          <tbody>
            {grn.lines.map(line => {
              const prod = productMap[line.product_id]
              return (
                <tr key={line.id} className="border-b border-[#ede9e2] last:border-0">
                  <td className="px-5 py-2.5">
                    {prod ? (
                      <>
                        <span className="font-mono text-xs text-[#1a1814]/50 mr-1.5">{prod.code}</span>
                        {prod.name}
                      </>
                    ) : `Product #${line.product_id}`}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{Number(line.qty).toFixed(2)}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-[#1a1814]/70">{line.lot_no || "—"}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">
                    {Number(line.declared_value) > 0 ? fmt(Number(line.declared_value)) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-[#1a1814]/60 text-xs">{line.notes || "—"}</td>
                </tr>
              )
            })}
          </tbody>
          {totalDeclared > 0 && (
            <tfoot>
              <tr className="border-t border-[#ede9e2] bg-[#faf8f4]">
                <td className="px-5 py-2.5 text-xs text-[#1a1814]/60" colSpan={3}>Total declared value</td>
                <td className="px-4 py-2.5 text-right text-sm font-bold tabular-nums text-[#1a1814]">
                  {fmt(totalDeclared)}
                </td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}

function Field({
  label, children, className = "",
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      <dt className="text-xs font-semibold uppercase tracking-wide text-[#1a1814]/50 mb-0.5">{label}</dt>
      <dd className="text-sm text-[#1a1814]/80">{children}</dd>
    </div>
  )
}
