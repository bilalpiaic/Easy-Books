"use client"

import { useState } from "react"
import { Trash2, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt, useCurrency } from "@/context/SettingsContext"

export interface LineItem {
  product_id?: number | null
  description: string
  qty: number
  unit?: string
  rate: number
  discount_pct?: number   // 0–100 percentage discount
  promo_rule_id?: number | null
  amount: number
  tax_code_id?: number | null
}

interface Product {
  id: number
  name: string
  code?: string | null
  unit: string
  default_rate: number
  product_type: string
  stock_qty?: number
}

export interface TaxCodeOption {
  id: number
  code: string
  name: string
  rate: number
  type: string
}

interface Props {
  lines: LineItem[]
  onChange: (lines: LineItem[]) => void
  products?: Product[]
  taxCodes?: TaxCodeOption[]
  showTax?: boolean
  readOnly?: boolean
  /** When true, show on-hand qty for stock products and flag oversells */
  showStockHint?: boolean
  /** When true, show an amber warning when qty exceeds on-hand (invoices only) */
  warnOversell?: boolean
  /** Customer or vendor id — used to fetch per-party last price hint */
  customerId?: number | null
  /** 'sale' uses invoices, 'purchase' uses bills */
  priceKind?: 'sale' | 'purchase'
}

const UNITS = ["pcs", "kg", "mtr", "hrs", "ltr", "box", "doz"]

function emptyLine(): LineItem {
  return { product_id: null, description: "", qty: 1, unit: "pcs", rate: 0, discount_pct: 0, amount: 0, tax_code_id: null }
}

function calcAmount(qty: number, rate: number, discountPct = 0) {
  return Math.round(qty * rate * (1 - discountPct / 100) * 100) / 100
}

export default function LineItemsTable({ lines, onChange, products = [], taxCodes = [], showTax = false, readOnly = false, showStockHint = false, warnOversell = false, customerId = null, priceKind = 'sale' }: Props) {
  const fmt      = useFmt()
  const currency = useCurrency()
  const [hints, setHints] = useState<Record<number, { rate: number; date: string; scope: string; party_name: string | null } | null>>({})
  const update = (idx: number, patch: Partial<LineItem>) => {
    const updated = lines.map((l, i) => {
      if (i !== idx) return l
      const merged = { ...l, ...patch }
      merged.amount = calcAmount(merged.qty, merged.rate, merged.discount_pct ?? 0)
      return merged
    })
    onChange(updated)
  }

  const remove = (idx: number) => {
    onChange(lines.filter((_, i) => i !== idx))
    setHints(h => {
      const next: typeof h = {}
      Object.entries(h).forEach(([k, v]) => {
        const ki = Number(k)
        if (ki < idx) next[ki] = v
        else if (ki > idx) next[ki - 1] = v
        // ki === idx dropped
      })
      return next
    })
  }
  const add = () => onChange([...lines, emptyLine()])

  const onProductSelect = (idx: number, productId: string) => {
    if (!productId) {
      update(idx, { product_id: null })
      setHints(h => ({ ...h, [idx]: null }))
      return
    }
    const prod = products.find(p => p.id === Number(productId))
    if (!prod) return
    const amount = calcAmount(lines[idx].qty, prod.default_rate, lines[idx].discount_pct ?? 0)
    onChange(lines.map((l, i) =>
      i === idx
        ? { ...l, product_id: prod.id, description: prod.name, unit: prod.unit, rate: prod.default_rate, amount }
        : l
    ))
    // Fetch last-price hint for this product + party
    const qs = new URLSearchParams({ kind: priceKind })
    if (customerId) qs.set('customer_id', String(customerId))
    apiFetch<{ rate: number | null; date: string | null; scope: string | null; party_name: string | null }>(
      `/api/products/${prod.id}/last-price?${qs}`
    ).then(r => setHints(h => ({ ...h, [idx]: r.rate != null ? { rate: r.rate, date: r.date!, scope: r.scope!, party_name: r.party_name ?? null } : null })))
     .catch(() => {})
  }

  const subtotal = lines.reduce((s, l) => s + l.amount, 0)

  // Extra columns: product, tax — affects colspan calculations
  const hasProducts = products.length > 0
  const hasTax = showTax
  const baseCols = 5 // description, qty, unit, rate, discount
  const extraCols = (hasProducts ? 1 : 0) + (hasTax ? 1 : 0)
  const totalDataCols = baseCols + extraCols + 1 // +1 for amount
  const actionCol = readOnly ? 0 : 1
  const totalCols = totalDataCols + actionCol

  return (
    <div className="border border-[var(--border)] rounded-xl overflow-x-auto">
      <table className="w-full text-sm min-w-[920px]">
        <thead className="bg-[var(--bg-page)]">
          <tr>
            {hasProducts && (
              <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] min-w-[160px] w-[18%]">Product</th>
            )}
            <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] min-w-[200px] w-[28%]">Description</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] w-28">Qty</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] w-20">Unit</th>
            <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] w-32">Rate ({currency})</th>
            <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] w-20">Disc %</th>
            {hasTax && (
              <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] w-40">Tax</th>
            )}
            <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] w-36">Amount ({currency})</th>
            {!readOnly && <th className="w-8" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {lines.map((line, idx) => (
            <tr key={idx} className="hover:bg-[var(--bg-page)]/30">
              {hasProducts && (
                <td className="px-3 py-2">
                  {readOnly ? (
                    <span className="text-xs text-[var(--text-muted)]">{products.find(p => p.id === line.product_id)?.name ?? "—"}</span>
                  ) : (
                    <select
                      value={line.product_id ?? ""}
                      onChange={e => onProductSelect(idx, e.target.value)}
                      className="w-full text-xs bg-transparent outline-none focus:ring-1 focus:ring-[var(--primary)] rounded px-1 py-0.5"
                    >
                      <option value="">— none —</option>
                      {products.map(p => (
                        <option key={p.id} value={p.id}>{p.code ? `${p.code} — ` : ""}{p.name}</option>
                      ))}
                    </select>
                  )}
                </td>
              )}
              <td className="px-3 py-2">
                {readOnly ? (
                  <span>{line.description}</span>
                ) : (
                  <input
                    value={line.description}
                    onChange={e => update(idx, { description: e.target.value })}
                    placeholder="Description"
                    className="w-full bg-transparent outline-none focus:ring-1 focus:ring-[var(--primary)] rounded px-1 py-0.5 text-sm"
                  />
                )}
              </td>
              <td className="px-3 py-2">
                {readOnly ? (
                  <span className="block text-center font-mono">{line.qty}</span>
                ) : (
                  <div>
                    <input
                      type="number" min="0" step="0.001"
                      value={line.qty}
                      onChange={e => update(idx, { qty: parseFloat(e.target.value) || 0 })}
                      className="w-full text-center bg-transparent outline-none focus:ring-1 focus:ring-[var(--primary)] rounded px-1 py-0.5 font-mono text-sm"
                    />
                    {showStockHint && (() => {
                      const prod = line.product_id ? products.find(p => p.id === line.product_id) : null
                      if (!prod || prod.product_type !== "stock") return null
                      const onHand = prod.stock_qty ?? 0
                      const oversell = warnOversell && line.qty > onHand
                      return (
                        <div className="text-[10px] mt-0.5 text-center">
                          <span className={`whitespace-nowrap ${oversell ? "text-amber-600 font-semibold" : "text-[var(--text-muted)]"}`}>
                            On hand: {onHand}
                          </span>
                          {oversell && (
                            <span className="block text-amber-600 font-semibold whitespace-nowrap">↑ exceeds stock</span>
                          )}
                        </div>
                      )
                    })()}
                  </div>
                )}
              </td>
              <td className="px-3 py-2">
                {readOnly || line.product_id ? (
                  <span className="block text-center text-xs text-[var(--text-muted)]">{line.unit ?? "—"}</span>
                ) : (
                  <select
                    value={line.unit ?? "pcs"}
                    onChange={e => update(idx, { unit: e.target.value })}
                    className="w-full text-xs bg-transparent outline-none focus:ring-1 focus:ring-[var(--primary)] rounded px-1 py-0.5"
                  >
                    {UNITS.map(u => <option key={u} value={u}>{u}</option>)}
                  </select>
                )}
              </td>
              <td className="px-3 py-2">
                {readOnly ? (
                  <span className="block text-right font-mono">{fmt(line.rate)}</span>
                ) : (
                  <>
                    <input
                      type="number" min="0" step="0.01"
                      value={line.rate}
                      onChange={e => update(idx, { rate: parseFloat(e.target.value) || 0 })}
                      className="w-full text-right bg-transparent outline-none focus:ring-1 focus:ring-[var(--primary)] rounded px-1 py-0.5 font-mono text-sm"
                    />
                    {hints[idx] && hints[idx]!.rate !== line.rate && (
                      <button type="button"
                        onClick={() => update(idx, { rate: hints[idx]!.rate, amount: Math.round(line.qty * hints[idx]!.rate * 100) / 100 })}
                        className="block mt-1 text-[10px] text-[var(--primary)] hover:underline"
                        title={`Last ${priceKind === 'purchase' ? 'bought' : 'sold'} (${hints[idx]!.scope})`}
                      >
                        Last: {fmt(hints[idx]!.rate)}{hints[idx]!.party_name ? ` — ${hints[idx]!.party_name}` : ""} · {hints[idx]!.date} — Use
                      </button>
                    )}
                  </>
                )}
              </td>
              <td className="px-3 py-2">
                {readOnly ? (
                  <span className="block text-right font-mono text-xs">
                    {(line.discount_pct ?? 0) > 0 ? `${line.discount_pct}%` : "—"}
                  </span>
                ) : (
                  <input
                    type="number" min="0" max="100" step="0.01"
                    value={line.discount_pct ?? 0}
                    onChange={e => update(idx, { discount_pct: parseFloat(e.target.value) || 0 })}
                    className={`w-full text-right bg-transparent outline-none focus:ring-1 focus:ring-[var(--primary)] rounded px-1 py-0.5 font-mono text-sm ${(line.discount_pct ?? 0) > 0 ? "text-emerald-600 font-semibold" : ""}`}
                  />
                )}
              </td>
              {hasTax && (
                <td className="px-3 py-2">
                  {readOnly ? (
                    <span className="text-xs text-[var(--text-muted)]">
                      {taxCodes.find(t => t.id === line.tax_code_id)?.code ?? "—"}
                    </span>
                  ) : (
                    <select
                      value={line.tax_code_id ?? ""}
                      onChange={e => update(idx, { tax_code_id: e.target.value ? Number(e.target.value) : null })}
                      className="w-full text-xs bg-transparent outline-none focus:ring-1 focus:ring-[var(--primary)] rounded px-1 py-0.5"
                    >
                      <option value="">— none —</option>
                      {taxCodes.map(t => (
                        <option key={t.id} value={t.id}>{t.code} ({t.rate}%)</option>
                      ))}
                    </select>
                  )}
                </td>
              )}
              <td className="px-3 py-2 text-right font-mono text-sm font-semibold">{fmt(line.amount)}</td>
              {!readOnly && (
                <td className="px-2 py-2">
                  <button onClick={() => remove(idx)} className="text-red-400 hover:text-red-600">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </td>
              )}
            </tr>
          ))}
          {lines.length === 0 && (
            <tr>
              <td colSpan={totalCols} className="px-4 py-4 text-center text-xs text-[var(--text-muted)]">
                No line items. {!readOnly && "Click Add Row to begin."}
              </td>
            </tr>
          )}
        </tbody>
        <tfoot className="bg-[var(--bg-page)] border-t border-[var(--border)]">
          <tr>
            <td colSpan={totalCols - 1 - actionCol} className="px-3 py-2">
              {!readOnly && (
                <button
                  type="button"
                  onClick={add}
                  className="flex items-center gap-1 text-xs text-[var(--primary)] font-bold hover:underline"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Row
                </button>
              )}
            </td>
            <td className="px-3 py-2 text-right text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">Subtotal</td>
            <td className="px-3 py-2 text-right font-mono font-bold">{fmt(subtotal)}</td>
            {!readOnly && <td />}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
