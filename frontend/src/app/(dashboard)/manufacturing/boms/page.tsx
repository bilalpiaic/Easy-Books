"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Layers, Printer, Plus, Archive, Download } from "lucide-react"
import PrintHeader from "@/components/PrintHeader"
import { apiFetch } from "@/lib/api"
import { downloadCSV } from "@/lib/utils"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { EmptyStateGuide } from "@/components/guidance/EmptyStateGuide"
import { useTranslation } from "react-i18next"
import { useMessages } from "@/context/MessageContext"

interface BomLine {
  id: number; component_product_id: number; qty_per_output: string
  source: string; is_optional: boolean; default_location_id: number | null
}
interface Bom {
  id: number; output_product_id: number; output_qty: string; version: number
  is_active: boolean; explode_on_invoice: boolean; description: string | null; lines: BomLine[]
}
interface Product { id: number; code: string; name: string }

export default function BomsListPage() {
  const { confirm } = useMessages()
  const { t } = useTranslation()

  const [boms, setBoms]         = useState<Bom[]>([])
  const [products, setProducts] = useState<Map<number, Product>>(new Map())
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [busyId, setBusyId]     = useState<number | null>(null)

  const load = () =>
    Promise.all([
      apiFetch<{ items: Bom[] }>("/api/bom"),
      apiFetch<{ items: Product[] }>("/api/products?limit=500"),
    ])
      .then(([b, p]) => {
        setBoms(b.items)
        setProducts(new Map(p.items.map(x => [x.id, x])))
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const deactivate = async (bom: Bom) => {
    const ok = await confirm({
      title: `Archive BOM #${bom.id} (v${bom.version})?`,
      message: "Production orders referencing it will keep their cost basis.",
      confirmLabel: "Archive",
      danger: true,
    })
    if (!ok) return
    setBusyId(bom.id)
    try {
      await apiFetch(`/api/bom/${bom.id}/deactivate`, { method: "PATCH" })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Archive failed")
    } finally { setBusyId(null) }
  }

  if (loading) return <p className="text-sm text-[var(--text-primary)]/60">Loading…</p>

  return (
    <div className="space-y-5">
      <PrintHeader title="Bills of Material" orientation="landscape" />
      <header className="flex items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <Layers className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Bills of Material</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Recipes that turn raw materials into finished goods.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/manufacturing/boms/new"
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors">
            <Plus className="w-4 h-4" /> New BOM
          </Link>
          <button
            onClick={() => downloadCSV('boms.csv', boms.map(b => ({ "Product": products.get(b.output_product_id)?.name ?? String(b.output_product_id), "Output Qty": b.output_qty, Version: b.version, Active: b.is_active ? "Yes" : "No", "Auto-explode": b.explode_on_invoice ? "Yes" : "No", Components: b.lines.length })))}
            disabled={boms.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
            title="Export CSV"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
            title="Print"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
        </div>
      </header>

      <HelpCallout title="What a BoM does for you" tone="tip">
        A BoM specifies <b>which components</b> (and how much of each) are needed to produce one
        unit of an output product. Each line is tagged as either <b>own_stock</b> (from your raw
        material inventory, costs hit WIP) or <b>customer_supplied</b> (from a customer godown,
        memo-only — never your asset).
        <p className="mt-2 opacity-80">
          BoMs are versioned. Edit by posting a new version — historical production orders
          stay reconstructable.
        </p>
      </HelpCallout>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {boms.length === 0 ? (
        <EmptyStateGuide
          title="No bills of material yet"
          description="Create your first recipe to start producing."
          steps={[
            "Make sure the output product and all component products exist (Products page).",
            "Click 'New BOM' to define output product, batch qty, and component lines.",
            "Tag each line as 'own_stock' or 'customer_supplied' depending on who owns the material.",
          ]}
          primaryAction={{ label: "New BOM", href: "/manufacturing/boms/new" }}
          secondaryAction={{ label: "How to model BoMs →", href: "/guide" }}
        />
      ) : (
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] text-[var(--text-primary)]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">Output product</th>
                <th className="text-left px-4 py-2">{t('col.description', 'Description')}</th>
                <th className="text-right px-4 py-2">Output qty</th>
                <th className="text-center px-4 py-2">Lines</th>
                <th className="text-center px-4 py-2">Ver.</th>
                <th className="text-center px-4 py-2">{t('col.status', 'Status')}</th>
                <th className="px-4 py-2 print:hidden" />
              </tr>
            </thead>
            <tbody>
              {boms.map(b => {
                const prod = products.get(b.output_product_id)
                return (
                  <tr key={b.id} className="border-t border-[var(--border)] hover:bg-[#faf8f4]">
                    <td className="px-4 py-2.5">
                      {prod ? (
                        <div>
                          <span className="font-medium">{prod.name}</span>
                          <span className="text-[var(--text-primary)]/50 text-xs ml-1.5 font-mono">{prod.code}</span>
                        </div>
                      ) : (
                        <span className="text-[var(--text-primary)]/50">#{b.output_product_id}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-[var(--text-primary)]/60 text-xs">{b.description ?? "—"}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{b.output_qty}</td>
                    <td className="px-4 py-2.5 text-center">{b.lines.length}</td>
                    <td className="px-4 py-2.5 text-center text-xs text-[var(--text-primary)]/60">v{b.version}</td>
                    <td className="px-4 py-2.5 text-center">
                      <div className="flex flex-col items-center gap-0.5">
                        {b.is_active
                          ? <span className="text-emerald-700 font-semibold text-xs">{t('status.active', 'Active')}</span>
                          : <span className="text-[var(--text-primary)]/40 text-xs">Archived</span>}
                        {b.explode_on_invoice && (
                          <span className="text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 text-[10px] font-medium">Kit</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-right print:hidden">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          href={`/manufacturing/boms/${b.id}`}
                          className="text-[var(--primary)] text-xs font-medium hover:underline"
                        >
                          View
                        </Link>
                        {b.is_active && (
                          <button
                            onClick={() => deactivate(b)}
                            disabled={busyId === b.id}
                            title="Archive BOM"
                            className="p-1.5 rounded border border-[var(--border)] hover:bg-amber-50 text-[var(--text-primary)]/40 hover:text-amber-600 disabled:opacity-50 transition-colors"
                          >
                            <Archive className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
