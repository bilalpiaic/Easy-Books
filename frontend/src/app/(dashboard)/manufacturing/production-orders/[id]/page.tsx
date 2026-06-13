'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Printer, ChevronLeft, CheckCircle, AlertCircle } from 'lucide-react'
import DocLink from '@/components/DocLink'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import AttachmentPanel, { AttachmentPreviewPane, type Attachment as AttachmentT } from '@/components/AttachmentPanel'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Po {
  id: number
  number: string
  state: string
  bom_id: number
  customer_id: number
  rate_plan_id: number | null
  output_qty: string
  own_material_cost: string
  output_unit_cost: string
  invoice_id: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  delivered_at: string | null
  billed_at: string | null
  cancelled_at: string | null
  notes: string | null
}

interface BomLine {
  id: number
  component_product_id: number
  qty_per_output: string
  source: 'own_stock' | 'customer_supplied'
  is_optional: boolean
  notes: string | null
}

interface Bom {
  id: number
  output_product_id: number
  output_qty: string
  description: string | null
  lines: BomLine[]
}

interface Customer { id: number; name: string }
interface RatePlan { id: number; code: string; name: string; per_unit_rate: string }
interface Product  { id: number; name: string; code: string | null }

// ── Constants ─────────────────────────────────────────────────────────────────

const STATE_TONE: Record<string, string> = {
  draft:     'bg-slate-100 text-slate-800',
  started:   'bg-amber-100 text-amber-900',
  completed: 'bg-blue-100 text-blue-900',
  delivered: 'bg-emerald-100 text-emerald-900',
  billed:    'bg-violet-100 text-violet-900',
  cancelled: 'bg-red-100 text-red-900',
}

const STAGES: { key: keyof Po & string; label: string }[] = [
  { key: 'created_at',   label: 'Created'   },
  { key: 'started_at',   label: 'Started'   },
  { key: 'completed_at', label: 'Completed' },
  { key: 'delivered_at', label: 'Delivered' },
  { key: 'billed_at',    label: 'Billed'    },
]

const ACTION_LABEL: Record<string, string> = {
  start:    'Start Production',
  complete: 'Mark Complete',
  deliver:  'Deliver to Customer',
  bill:     'Generate Invoice',
}

function nextAction(state: string): 'start' | 'complete' | 'deliver' | 'bill' | null {
  if (state === 'draft')     return 'start'
  if (state === 'started')   return 'complete'
  if (state === 'completed') return 'deliver'
  if (state === 'delivered') return 'bill'
  return null
}

function fmt_date(iso: string | null) {
  if (!iso) return null
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ProductionOrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router  = useRouter()
  const fmt     = useFmt()

  const [po, setPo]           = useState<Po | null>(null)
  const [bom, setBom]         = useState<Bom | null>(null)
  const [products, setProducts] = useState<Map<number, Product>>(new Map())
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [ratePlan, setRatePlan] = useState<RatePlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [busy, setBusy]       = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [selectedAtt, setSelectedAtt] = useState<AttachmentT | null>(null)

  const load = async () => {
    try {
      const poData = await apiFetch<Po>(`/api/production-orders/${id}`)
      setPo(poData)

      const [bomData, customerData, productsData] = await Promise.all([
        apiFetch<Bom>(`/api/bom/${poData.bom_id}`),
        apiFetch<Customer>(`/api/customers/${poData.customer_id}`),
        apiFetch<{ items: Product[] }>('/api/products?limit=500'),
      ])
      setBom(bomData)
      setCustomer(customerData)
      setProducts(new Map(productsData.items.map(p => [p.id, p])))

      if (poData.rate_plan_id) {
        apiFetch<{ items: RatePlan[] }>('/api/rate-plans').then(d => {
          const match = d.items.find(r => r.id === poData.rate_plan_id)
          if (match) setRatePlan(match)
        }).catch(() => {})
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const advance = async (action: 'start' | 'complete' | 'deliver' | 'bill' | 'cancel') => {
    if (!po) return
    setBusy(true)
    setActionError(null)
    try {
      const updated = await apiFetch<Po>(`/api/production-orders/${po.id}/${action}`, { method: 'POST' })
      setPo(updated)
      if (action === 'bill' && updated.invoice_id) {
        router.push(`/invoices/${updated.invoice_id}`)
      }
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="p-6 text-sm text-[#1a1814]/60">Loading…</p>
  if (error || !po) return (
    <div className="p-6">
      <p className="text-sm text-red-600">{error ?? 'Order not found'}</p>
      <Link href="/manufacturing/production-orders" className="text-[#b8943f] text-sm mt-2 inline-block">← Back to list</Link>
    </div>
  )

  const nxt        = nextAction(po.state)
  const outputProd = bom ? products.get(bom.output_product_id) : undefined
  const batches    = bom ? (parseFloat(po.output_qty) / parseFloat(bom.output_qty)) : 1

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">

      {/* Back + print */}
      <div className="flex items-center justify-between">
        <Link href="/manufacturing/production-orders" className="flex items-center gap-1 text-sm text-[#1a1814]/60 hover:text-[#b8943f]">
          <ChevronLeft className="w-4 h-4" /> Production Orders
        </Link>
        <a
          href={`/manufacturing/production-orders/${po.id}/print`}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-xl text-xs font-bold hover:bg-[#f6f3ee]"
        >
          <Printer className="w-3.5 h-3.5" /> Print
        </a>
      </div>

      {/* Header card */}
      <div className="bg-white border border-[#ede9e2] rounded-2xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold font-mono text-[#1a1814]">{po.number}</h1>
            <p className="text-sm text-[#1a1814]/60 mt-0.5">
              Customer: <DocLink type="customer" id={po.customer_id} label={customer?.name ?? `#${po.customer_id}`} />
            </p>
          </div>
          <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold ${STATE_TONE[po.state] ?? ''}`}>
            {po.state.toUpperCase()}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
          <div>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest font-bold mb-0.5">Output qty</p>
            <p className="text-sm font-semibold tabular-nums">{po.output_qty}</p>
          </div>
          <div>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest font-bold mb-0.5">Material cost</p>
            <p className="text-sm font-semibold tabular-nums">{fmt(Number(po.own_material_cost))}</p>
          </div>
          <div>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest font-bold mb-0.5">Unit cost</p>
            <p className="text-sm font-semibold tabular-nums">
              {parseFloat(po.output_unit_cost) > 0 ? fmt(Number(po.output_unit_cost)) : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-widest font-bold mb-0.5">Rate plan</p>
            <p className="text-sm font-semibold">{ratePlan ? `${ratePlan.code} · ${fmt(Number(ratePlan.per_unit_rate))}/unit` : '—'}</p>
          </div>
        </div>

        {po.invoice_id && (
          <div className="mt-4 flex items-center gap-2 text-sm">
            <CheckCircle className="w-4 h-4 text-violet-500" />
            Invoice: <DocLink type="invoice" id={po.invoice_id} label={`INV-${String(po.invoice_id).padStart(4,'0')}`} />
          </div>
        )}

        {po.notes && (
          <p className="mt-4 text-sm text-[#1a1814]/70 italic border-t border-[#ede9e2] pt-3">{po.notes}</p>
        )}
      </div>

      {/* Lifecycle timeline */}
      <div className="bg-white border border-[#ede9e2] rounded-2xl p-6">
        <h2 className="text-sm font-bold uppercase tracking-widest text-[#1a1814]/60 mb-4">Timeline</h2>
        <div className="flex flex-wrap gap-x-6 gap-y-3">
          {STAGES.map(s => {
            const ts = po[s.key as keyof Po] as string | null
            return (
              <div key={s.key} className="flex items-start gap-2">
                {ts
                  ? <CheckCircle className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                  : <div className="w-4 h-4 rounded-full border-2 border-[#ede9e2] mt-0.5 shrink-0" />
                }
                <div>
                  <p className="text-xs font-bold text-[#1a1814]/60">{s.label}</p>
                  <p className="text-xs text-[#1a1814]">{ts ? fmt_date(ts) : '—'}</p>
                </div>
              </div>
            )
          })}
          {po.cancelled_at && (
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-bold text-red-500">Cancelled</p>
                <p className="text-xs text-[#1a1814]">{fmt_date(po.cancelled_at)}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      {(nxt || po.state === 'draft') && (
        <div className="bg-white border border-[#ede9e2] rounded-2xl p-6 space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[#1a1814]/60">Actions</h2>
          {actionError && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              {actionError}
            </div>
          )}
          <div className="flex flex-wrap gap-3">
            {nxt && (
              <button
                onClick={() => advance(nxt)}
                disabled={busy}
                className="px-5 py-2.5 bg-[#1a1814] text-white rounded-xl text-sm font-bold hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50"
              >
                {busy ? 'Working…' : ACTION_LABEL[nxt]}
              </button>
            )}
            {po.state === 'draft' && (
              <button
                onClick={() => advance('cancel')}
                disabled={busy}
                className="px-5 py-2.5 border border-red-200 text-red-700 rounded-xl text-sm font-bold hover:bg-red-50 transition-colors disabled:opacity-50"
              >
                Cancel Order
              </button>
            )}
          </div>
        </div>
      )}

      {/* BOM component table */}
      {bom && (
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-[#ede9e2] flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[#1a1814]/60">
              Bill of Materials
            </h2>
            <Link href={`/manufacturing/boms`} className="text-xs text-[#b8943f] hover:underline">
              {outputProd ? `${outputProd.code ?? ''} ${outputProd.name}` : `BOM #${bom.id}`}
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#f6f3ee]">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Component</th>
                  <th className="px-4 py-2 text-right text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Per unit</th>
                  <th className="px-4 py-2 text-right text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Total needed</th>
                  <th className="px-4 py-2 text-center text-xs font-bold uppercase tracking-widest text-[#1a1814]/60">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ede9e2]">
                {bom.lines.map(ln => {
                  const prod = products.get(ln.component_product_id)
                  const total = (parseFloat(ln.qty_per_output) * batches).toFixed(3).replace(/\.?0+$/, '')
                  return (
                    <tr key={ln.id} className="hover:bg-[#f6f3ee]/50">
                      <td className="px-4 py-2">
                        <span className="font-medium">{prod?.name ?? `Product #${ln.component_product_id}`}</span>
                        {prod?.code && <span className="ml-1.5 text-xs text-[#1a1814]/50 font-mono">{prod.code}</span>}
                        {ln.is_optional && <span className="ml-1.5 text-xs text-amber-600">(optional)</span>}
                        {ln.notes && <p className="text-xs text-[#1a1814]/50 mt-0.5">{ln.notes}</p>}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-[#1a1814]/70">{ln.qty_per_output}</td>
                      <td className="px-4 py-2 text-right tabular-nums font-semibold">{total}</td>
                      <td className="px-4 py-2 text-center">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                          ln.source === 'customer_supplied'
                            ? 'bg-sky-100 text-sky-800'
                            : 'bg-emerald-100 text-emerald-800'
                        }`}>
                          {ln.source === 'customer_supplied' ? 'Customer' : 'Own stock'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {bom.description && (
            <p className="px-6 py-3 text-xs text-[#1a1814]/50 border-t border-[#ede9e2]">{bom.description}</p>
          )}
        </div>
      )}

      {/* Attachments */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <AttachmentPanel parentType="production_order" parentId={po.id} embedded onSelect={setSelectedAtt} />
        {selectedAtt && <AttachmentPreviewPane att={selectedAtt} />}
      </div>
    </div>
  )
}
