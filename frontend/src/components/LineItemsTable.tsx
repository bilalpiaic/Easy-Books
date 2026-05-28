"use client"

import { Trash2, Plus } from "lucide-react"
import { useFmt } from "@/context/SettingsContext"

export interface LineItem {
  product_id?: number | null
  description: string
  qty: number
  unit?: string
  rate: number
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
}

const UNITS = ["pcs", "kg", "mtr", "hrs", "ltr", "box", "doz"]

function emptyLine(): LineItem {
  const fmt = useFmt()
  return { product_id: null, description: "", qty: 1, unit: "pcs", rate: 0, amount: 0, tax_code_id: null }
}

export default function LineItemsTable({ lines, onChange, products = [], taxCodes = [], showTax = false, readOnly = false }: Props) {
  const update = (idx: number, patch: Partial<LineItem>) => {
    const updated = lines.map((l, i) => {
      if (i !== idx) return l
      const merged = { ...l, ...patch }
      merged.amount = Math.round(merged.qty * merged.rate * 100) / 100
      return merged
    })
    onChange(updated)
  }

  const remove = (idx: number) => onChange(lines.filter((_, i) => i !== idx))
  const add = () => onChange([...lines, emptyLine()])

  const onProductSelect = (idx: number, productId: string) => {
    if (!productId) {
      update(idx, { product_id: null })
      return
    }
    const prod = products.find(p => p.id === Number(productId))
    if (!prod) return
    const amount = Math.round(lines[idx].qty * prod.default_rate * 100) / 100
    onChange(lines.map((l, i) =>
      i === idx
        ? { ...l, product_id: prod.id, description: prod.name, unit: prod.unit, rate: prod.default_rate, amount }
        : l
    ))
  }

  const subtotal = lines.reduce((s, l) => s + l.amount, 0)

  // Extra columns: product, tax — affects colspan calculations
  const hasProducts = products.length > 0
  const hasTax = showTax
  const baseCols = 4 // description, qty, unit, rate
  const extraCols = (hasProducts ? 1 : 0) + (hasTax ? 1 : 0)
  const totalDataCols = baseCols + extraCols + 1 // +1 for amount
  const actionCol = readOnly ? 0 : 1
  const totalCols = totalDataCols + actionCol

  return (
    <div className="border border-[#ede9e2] rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-[#f6f3ee]">
          <tr>
            {hasProducts && (
              <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/60">Product</th>
            )}
            <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/60">Description</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-black/60 w-20">Qty</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-black/60 w-20">Unit</th>
            <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-black/60 w-28">Rate</th>
            {hasTax && (
              <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-black/60 w-32">Tax</th>
            )}
            <th className="px-3 py-2 text-right text-[10px] font-bold uppercase tracking-widest text-black/60 w-28">Amount</th>
            {!readOnly && <th className="w-8" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-[#ede9e2]">
          {lines.map((line, idx) => (
            <tr key={idx} className="hover:bg-[#f6f3ee]/30">
              {hasProducts && (
                <td className="px-3 py-2">
                  {readOnly ? (
                    <span className="text-xs text-black/60">{products.find(p => p.id === line.product_id)?.name ?? "—"}</span>
                  ) : (
                    <select
                      value={line.product_id ?? ""}
                      onChange={e => onProductSelect(idx, e.target.value)}
                      className="w-full text-xs bg-transparent outline-none focus:ring-1 focus:ring-[#b8943f] rounded px-1 py-0.5"
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
                    className="w-full bg-transparent outline-none focus:ring-1 focus:ring-[#b8943f] rounded px-1 py-0.5 text-sm"
                  />
                )}
              </td>
              <td className="px-3 py-2">
                {readOnly ? (
                  <span className="block text-center font-mono">{line.qty}</span>
                ) : (
                  <input
                    type="number" min="0" step="0.001"
                    value={line.qty}
                    onChange={e => update(idx, { qty: parseFloat(e.target.value) || 0 })}
                    className="w-full text-center bg-transparent outline-none focus:ring-1 focus:ring-[#b8943f] rounded px-1 py-0.5 font-mono text-sm"
                  />
                )}
              </td>
              <td className="px-3 py-2">
                {readOnly ? (
                  <span className="block text-center text-xs text-black/60">{line.unit ?? "—"}</span>
                ) : (
                  <select
                    value={line.unit ?? "pcs"}
                    onChange={e => update(idx, { unit: e.target.value })}
                    className="w-full text-xs bg-transparent outline-none focus:ring-1 focus:ring-[#b8943f] rounded px-1 py-0.5"
                  >
                    {UNITS.map(u => <option key={u} value={u}>{u}</option>)}
                  </select>
                )}
              </td>
              <td className="px-3 py-2">
                {readOnly ? (
                  <span className="block text-right font-mono">{fmt(line.rate)}</span>
                ) : (
                  <input
                    type="number" min="0" step="0.01"
                    value={line.rate}
                    onChange={e => update(idx, { rate: parseFloat(e.target.value) || 0 })}
                    className="w-full text-right bg-transparent outline-none focus:ring-1 focus:ring-[#b8943f] rounded px-1 py-0.5 font-mono text-sm"
                  />
                )}
              </td>
              {hasTax && (
                <td className="px-3 py-2">
                  {readOnly ? (
                    <span className="text-xs text-black/60">
                      {taxCodes.find(t => t.id === line.tax_code_id)?.code ?? "—"}
                    </span>
                  ) : (
                    <select
                      value={line.tax_code_id ?? ""}
                      onChange={e => update(idx, { tax_code_id: e.target.value ? Number(e.target.value) : null })}
                      className="w-full text-xs bg-transparent outline-none focus:ring-1 focus:ring-[#b8943f] rounded px-1 py-0.5"
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
              <td colSpan={totalCols} className="px-4 py-4 text-center text-xs text-black/40">
                No line items. {!readOnly && "Click Add Row to begin."}
              </td>
            </tr>
          )}
        </tbody>
        <tfoot className="bg-[#f6f3ee] border-t border-[#ede9e2]">
          <tr>
            <td colSpan={totalCols - 1 - actionCol} className="px-3 py-2">
              {!readOnly && (
                <button
                  type="button"
                  onClick={add}
                  className="flex items-center gap-1 text-xs text-[#b8943f] font-bold hover:underline"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Row
                </button>
              )}
            </td>
            <td className="px-3 py-2 text-right text-xs font-bold uppercase tracking-widest text-black/60">Subtotal</td>
            <td className="px-3 py-2 text-right font-mono font-bold">{fmt(subtotal)}</td>
            {!readOnly && <td />}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
