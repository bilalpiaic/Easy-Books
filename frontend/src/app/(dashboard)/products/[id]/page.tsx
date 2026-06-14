"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft, Pencil, Package, BarChart2, BookOpen,
  FileText, TrendingDown, TrendingUp, AlertTriangle,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"

interface Product {
  id: number
  code: string | null
  name: string
  unit: string
  product_type: string
  default_rate: number
  stock_qty: number
  avg_cost: number
  reorder_level: number
  is_active: boolean
  is_deferred: boolean
  recognition_months: number
  hs_code: string | null
  category_id: number | null
}

interface Bom {
  id: number
  version: number
  is_active: boolean
  explode_on_invoice: boolean
  output_qty: string
  description: string | null
  lines: { id: number }[]
}

export default function ProductHubPage() {
  const params = useParams()
  const id = params.id as string
  const fmt = useFmt()

  const [product, setProduct] = useState<Product | null>(null)
  const [boms, setBoms]       = useState<Bom[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<Product>(`/api/products/${id}`),
      apiFetch<{ total: number; items: Bom[] }>(`/api/bom?output_product_id=${id}&limit=10`),
    ])
      .then(([p, b]) => { setProduct(p); setBoms(b.items) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="p-8 text-sm text-[#1a1814]/50 text-center">Loading…</div>
  if (error)   return <div className="p-8 text-sm text-red-600">{error}</div>
  if (!product) return null

  const isStock    = product.product_type === "stock"
  const stockValue = product.stock_qty * product.avg_cost
  const lowStock   = isStock && product.stock_qty <= product.reorder_level && product.stock_qty > 0
  const outOfStock = isStock && product.stock_qty <= 0
  const activeBom  = boms.find(b => b.is_active)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Link href="/products" className="text-[#1a1814]/40 hover:text-[#b8943f] transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">{product.name}</h1>
            <p className="text-sm text-[#1a1814]/55 mt-0.5 flex items-center gap-2">
              <span className="capitalize">{product.product_type}</span>
              {product.code && <span className="font-mono text-xs bg-[#f0ede6] px-1.5 py-0.5 rounded">{product.code}</span>}
              {product.hs_code && <span className="text-xs text-[#1a1814]/40">HS: {product.hs_code}</span>}
            </p>
          </div>
          {!product.is_active && (
            <span className="inline-block bg-slate-100 text-slate-500 text-xs font-medium px-2.5 py-0.5 rounded-full border border-slate-200">
              Inactive
            </span>
          )}
        </div>
        <Link
          href={`/products/${id}/edit`}
          className="inline-flex items-center gap-2 border border-[#ede9e2] px-3 py-2 rounded-lg text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors"
        >
          <Pencil className="w-4 h-4" /> Edit
        </Link>
      </div>

      {/* Stock status cards (stock products only) */}
      {isStock && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className={`bg-white border rounded-xl p-4 text-center ${outOfStock ? "border-red-200 bg-red-50/30" : lowStock ? "border-amber-200 bg-amber-50/30" : "border-[#ede9e2]"}`}>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-1">On Hand</p>
            <p className={`text-xl font-bold tabular-nums ${outOfStock ? "text-red-600" : lowStock ? "text-amber-700" : "text-[#1a1814]"}`}>
              {Number(product.stock_qty).toFixed(3)} {product.unit}
            </p>
            {outOfStock && <p className="text-xs text-red-500 mt-0.5">Out of stock</p>}
            {lowStock   && <p className="text-xs text-amber-600 mt-0.5">Below reorder level</p>}
          </div>
          <div className="bg-white border border-[#ede9e2] rounded-xl p-4 text-center">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-1">Avg Cost</p>
            <p className="text-xl font-bold tabular-nums text-[#1a1814]">{fmt(product.avg_cost)}</p>
          </div>
          <div className="bg-white border border-[#ede9e2] rounded-xl p-4 text-center">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-1">Stock Value</p>
            <p className="text-xl font-bold tabular-nums text-[#1a1814]">{fmt(stockValue)}</p>
          </div>
          <div className="bg-white border border-[#ede9e2] rounded-xl p-4 text-center">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-1">Sale Price</p>
            <p className="text-xl font-bold tabular-nums text-[#1a1814]">{fmt(product.default_rate)}</p>
          </div>
        </div>
      )}

      {/* Service product summary */}
      {!isStock && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white border border-[#ede9e2] rounded-xl p-4 text-center">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-1">Default Rate</p>
            <p className="text-xl font-bold tabular-nums text-[#1a1814]">{fmt(product.default_rate)}</p>
          </div>
          {product.is_deferred && (
            <div className="bg-white border border-[#ede9e2] rounded-xl p-4 text-center">
              <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-1">Recognition</p>
              <p className="text-xl font-bold text-[#1a1814]">{product.recognition_months} months</p>
            </div>
          )}
        </div>
      )}

      {/* Low-stock alert */}
      {outOfStock && (
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          Stock is at zero. Create a Bill or GRN to restock.
        </div>
      )}
      {lowStock && (
        <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          Stock is below the reorder level of {Number(product.reorder_level).toFixed(3)} {product.unit}.
        </div>
      )}

      {/* Active BOM banner */}
      {activeBom && (
        <div className="flex items-center gap-3 bg-violet-50 border border-violet-200 rounded-xl px-4 py-3 text-sm text-violet-800">
          <Package className="w-4 h-4 shrink-0" />
          <span>
            Active BOM v{activeBom.version} · {activeBom.lines.length} component{activeBom.lines.length !== 1 ? "s" : ""}
            {activeBom.explode_on_invoice && <span className="ml-2 bg-amber-100 text-amber-800 text-xs font-medium px-1.5 py-0.5 rounded">Kit — auto-consumes on invoice</span>}
          </span>
          <Link href="/manufacturing/boms" className="ml-auto text-xs text-violet-600 hover:underline">View BOMs</Link>
        </div>
      )}

      {/* Quick links */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {isStock && (
          <Link
            href={`/products/${id}/stock-card`}
            className="bg-white border border-[#ede9e2] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[#b8943f] hover:bg-[#faf8f4] transition-colors group"
          >
            <BarChart2 className="w-5 h-5 text-[#b8943f]/70 group-hover:text-[#b8943f]" />
            <span className="text-sm font-medium text-[#1a1814]">Stock Card</span>
          </Link>
        )}
        <Link
          href={`/products/ledger?product=${id}`}
          className="bg-white border border-[#ede9e2] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[#b8943f] hover:bg-[#faf8f4] transition-colors group"
        >
          <BookOpen className="w-5 h-5 text-[#b8943f]/70 group-hover:text-[#b8943f]" />
          <span className="text-sm font-medium text-[#1a1814]">Ledger</span>
        </Link>
        <Link
          href={`/invoices/new`}
          className="bg-white border border-[#ede9e2] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[#b8943f] hover:bg-[#faf8f4] transition-colors group"
        >
          <TrendingUp className="w-5 h-5 text-[#b8943f]/70 group-hover:text-[#b8943f]" />
          <span className="text-sm font-medium text-[#1a1814]">New Invoice</span>
        </Link>
        {isStock && (
          <Link
            href={`/bills/new`}
            className="bg-white border border-[#ede9e2] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[#b8943f] hover:bg-[#faf8f4] transition-colors group"
          >
            <TrendingDown className="w-5 h-5 text-[#b8943f]/70 group-hover:text-[#b8943f]" />
            <span className="text-sm font-medium text-[#1a1814]">New Bill</span>
          </Link>
        )}
        {boms.length > 0 && (
          <Link
            href="/manufacturing/boms"
            className="bg-white border border-[#ede9e2] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[#b8943f] hover:bg-[#faf8f4] transition-colors group"
          >
            <FileText className="w-5 h-5 text-[#b8943f]/70 group-hover:text-[#b8943f]" />
            <span className="text-sm font-medium text-[#1a1814]">BOMs ({boms.length})</span>
          </Link>
        )}
      </div>

      {/* Product details card */}
      <div className="bg-white border border-[#ede9e2] rounded-xl p-5 grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-4 text-sm">
        <div>
          <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-0.5">Type</p>
          <p className="capitalize font-medium text-[#1a1814]">{product.product_type}</p>
        </div>
        <div>
          <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-0.5">Unit</p>
          <p className="font-medium text-[#1a1814]">{product.unit}</p>
        </div>
        {product.code && (
          <div>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-0.5">SKU / Code</p>
            <p className="font-mono text-[#1a1814]">{product.code}</p>
          </div>
        )}
        {product.hs_code && (
          <div>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-0.5">HS Code (FBR)</p>
            <p className="font-mono text-[#1a1814]">{product.hs_code}</p>
          </div>
        )}
        {isStock && (
          <div>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-0.5">Reorder Level</p>
            <p className="tabular-nums text-[#1a1814]">{Number(product.reorder_level).toFixed(3)} {product.unit}</p>
          </div>
        )}
        {product.is_deferred && (
          <div>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-0.5">Revenue Recognition</p>
            <p className="text-[#1a1814]">Deferred · {product.recognition_months} months</p>
          </div>
        )}
      </div>
    </div>
  )
}
