"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, Package, Archive } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

interface BomLine {
  id: number
  component_product_id: number
  qty_per_output: string
  source: string
  is_optional: boolean
  default_location_id: number | null
  notes: string | null
}

interface Bom {
  id: number
  output_product_id: number
  output_qty: string
  version: number
  is_active: boolean
  explode_on_invoice: boolean
  description: string | null
  notes: string | null
  lines: BomLine[]
}

interface Product { id: number; code: string | null; name: string; unit: string }
interface Location { id: number; name: string }

const SOURCE_LABEL: Record<string, string> = {
  own_stock:         "Own Stock",
  customer_supplied: "Customer-Supplied",
}

export default function BomDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const { id } = use(params)

  const [bom, setBom]           = useState<Bom | null>(null)
  const [products, setProducts] = useState<Map<number, Product>>(new Map())
  const [locations, setLocations] = useState<Map<number, Location>>(new Map())
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [archiving, setArchiving] = useState(false)
  const [archiveMsg, setArchiveMsg] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<Bom>(`/api/bom/${id}`),
      apiFetch<{ items: Product[] }>("/api/products?limit=500"),
      apiFetch<{ items: Location[] }>("/api/stock-locations?limit=200"),
    ])
      .then(([b, p, l]) => {
        setBom(b)
        setProducts(new Map(p.items.map(x => [x.id, x])))
        setLocations(new Map(l.items.map(x => [x.id, x])))
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [id])

  const archive = async () => {
    if (!bom || !confirm(`Archive BOM #${bom.id} (v${bom.version})? Production orders referencing it will keep their cost basis.`)) return
    setArchiving(true)
    try {
      await apiFetch(`/api/bom/${id}/deactivate`, { method: "PATCH" })
      setBom(prev => prev ? { ...prev, is_active: false } : prev)
      setArchiveMsg("BOM archived.")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Archive failed")
    } finally { setArchiving(false) }
  }

  if (loading) return <div className="p-8 text-sm text-[var(--text-primary)]/50 text-center">Loading…</div>
  if (error)   return <div className="p-8 text-sm text-red-600">{error}</div>
  if (!bom)    return null

  const outProd = products.get(bom.output_product_id)
  const ownLines  = bom.lines.filter(l => l.source === "own_stock")
  const custLines = bom.lines.filter(l => l.source === "customer_supplied")

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Link href="/manufacturing/boms" className="text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {outProd?.name ?? `Product #${bom.output_product_id}`} — BOM v{bom.version}
            </h1>
            <p className="text-sm text-[var(--text-primary)]/55 mt-0.5 flex items-center gap-2">
              {bom.is_active
                ? <span className="text-emerald-700 font-medium">{t('status.active', 'Active')}</span>
                : <span className="text-[var(--text-primary)]/40">Archived</span>}
              {bom.explode_on_invoice && (
                <span className="bg-amber-100 text-amber-800 text-xs font-medium px-1.5 py-0.5 rounded">
                  Kit — auto-consumes on invoice
                </span>
              )}
            </p>
          </div>
        </div>
        {bom.is_active && (
          <button
            onClick={archive}
            disabled={archiving}
            className="inline-flex items-center gap-2 border border-[var(--border)] px-3 py-2 rounded-lg text-sm text-[var(--text-primary)]/60 hover:bg-amber-50 hover:text-amber-700 hover:border-amber-200 transition-colors disabled:opacity-50"
          >
            <Archive className="w-4 h-4" /> Archive
          </button>
        )}
      </div>

      {archiveMsg && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 rounded-xl px-4 py-3 text-sm">{archiveMsg}</div>
      )}

      {/* Summary card */}
      <div className="bg-white border border-[var(--border)] rounded-xl p-5 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <div>
          <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">Output Product</p>
          <p className="font-medium text-[var(--text-primary)]">{outProd?.name ?? `#${bom.output_product_id}`}</p>
          {outProd?.code && <p className="font-mono text-xs text-[var(--text-primary)]/50">{outProd.code}</p>}
        </div>
        <div>
          <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">Output Qty / Batch</p>
          <p className="font-mono font-medium text-[var(--text-primary)]">{bom.output_qty} {outProd?.unit ?? ""}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">Components</p>
          <p className="font-medium text-[var(--text-primary)]">{bom.lines.length} line{bom.lines.length !== 1 ? "s" : ""}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">Version</p>
          <p className="font-medium text-[var(--text-primary)]">v{bom.version}</p>
        </div>
        {bom.description && (
          <div className="col-span-2 sm:col-span-4">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">{t('col.description', 'Description')}</p>
            <p className="text-[var(--text-primary)]">{bom.description}</p>
          </div>
        )}
        {bom.notes && (
          <div className="col-span-2 sm:col-span-4">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-0.5">{t('col.notes', 'Notes')}</p>
            <p className="text-[var(--text-primary)]/70 whitespace-pre-wrap">{bom.notes}</p>
          </div>
        )}
      </div>

      {/* Component lines */}
      {[
        { label: "Own Stock Components", lines: ownLines, tone: "emerald" as const },
        { label: "Customer-Supplied Components", lines: custLines, tone: "violet" as const },
      ].filter(g => g.lines.length > 0).map(group => (
        <section key={group.label} className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
          <div className="px-5 py-3 bg-[var(--bg-page)] border-b border-[var(--border)]">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">{group.label}</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="border-b border-[var(--border)]">
              <tr>
                <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Component</th>
                <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Qty / Batch</th>
                <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Default Location</th>
                <th className="text-center px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Optional</th>
                <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">{t('col.notes', 'Notes')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {group.lines.map(ln => {
                const comp = products.get(ln.component_product_id)
                const loc  = ln.default_location_id ? locations.get(ln.default_location_id) : null
                return (
                  <tr key={ln.id} className="hover:bg-[#faf8f4]">
                    <td className="px-4 py-2.5">
                      {comp ? (
                        <div>
                          <Link href={`/products/${comp.id}`} className="font-medium text-[var(--primary)] hover:underline">
                            {comp.name}
                          </Link>
                          {comp.code && <span className="ml-1.5 text-xs font-mono text-[var(--text-primary)]/40">{comp.code}</span>}
                        </div>
                      ) : (
                        <span className="text-[var(--text-primary)]/40">#{ln.component_product_id}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                      {ln.qty_per_output} {comp?.unit ?? ""}
                    </td>
                    <td className="px-4 py-2.5 text-[var(--text-primary)]/70">
                      {loc ? loc.name : <span className="text-[var(--text-primary)]/30">—</span>}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {ln.is_optional ? (
                        <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5">Optional</span>
                      ) : (
                        <span className="text-xs text-[var(--text-primary)]/30">Required</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-[var(--text-primary)]/60 text-xs">{ln.notes ?? ""}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>
      ))}

      {/* Quick links */}
      <div className="flex gap-3 flex-wrap">
        <Link
          href="/manufacturing/boms/new"
          className="inline-flex items-center gap-2 border border-[var(--border)] px-4 py-2 rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors"
        >
          <Package className="w-4 h-4" /> New Version
        </Link>
        {outProd && (
          <Link
            href={`/products/${outProd.id}`}
            className="inline-flex items-center gap-2 border border-[var(--border)] px-4 py-2 rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors"
          >
            View Product
          </Link>
        )}
        <Link
          href="/manufacturing/production-orders/new"
          className="inline-flex items-center gap-2 border border-[var(--border)] px-4 py-2 rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors"
        >
          New Production Order
        </Link>
      </div>
    </div>
  )
}
