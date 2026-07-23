'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Printer, ChevronLeft, CheckCircle, AlertCircle } from 'lucide-react'
import DocLink from '@/components/DocLink'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import AttachmentPanel, { AttachmentPreviewPane, type Attachment as AttachmentT } from '@/components/AttachmentPanel'
import { useTranslation } from "react-i18next"

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
  labour_cost: string
  overhead_cost: string
  output_unit_cost: string
  delivered_qty: string
  invoice_id: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  delivered_at: string | null
  billed_at: string | null
  cancelled_at: string | null
  notes: string | null
  outputs?: {
    id: number
    product_id: number
    role: string
    qty: string
    unit_cost: string
    delivered_qty: string
  }[]
  scraps?: {
    id: number
    reason_id: number
    product_id: number
    qty: string
    unit_cost: string
    total_cost: string
    gl_posted: boolean
    notes: string | null
    created_at: string
  }[]
}

interface ScrapReason { id: number; code: string; name: string; is_active: boolean }

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
  const { t } = useTranslation()

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
  const [deliverQty, setDeliverQty] = useState('')
  const [reasons, setReasons] = useState<ScrapReason[]>([])
  const [scrapReasonId, setScrapReasonId] = useState('')
  const [scrapProductId, setScrapProductId] = useState('')
  const [scrapQty, setScrapQty] = useState('')
  const [scrapNotes, setScrapNotes] = useState('')
  const [scrapBusy, setScrapBusy] = useState(false)

  const load = async () => {
    try {
      const poData = await apiFetch<Po>(`/api/production-orders/${id}`)
      setPo(poData)
      const out = parseFloat(poData.output_qty)
      const delivered = parseFloat(poData.delivered_qty || '0')
      const remaining = Math.max(0, out - delivered)
      setDeliverQty(remaining > 0 ? String(remaining) : '')

      const [bomData, customerData, productsData, reasonsData] = await Promise.all([
        apiFetch<Bom>(`/api/bom/${poData.bom_id}`),
        apiFetch<Customer>(`/api/customers/${poData.customer_id}`),
        apiFetch<{ items: Product[] }>('/api/products?limit=500'),
        apiFetch<{ items: ScrapReason[] }>('/api/scrap-reasons?active_only=true').catch(() => ({ items: [] })),
      ])
      setBom(bomData)
      setCustomer(customerData)
      setProducts(new Map(productsData.items.map(p => [p.id, p])))
      setReasons(reasonsData.items)
      if (!scrapProductId && bomData.output_product_id) {
        setScrapProductId(String(bomData.output_product_id))
      }

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

  const advance = async (action: 'start' | 'complete' | 'deliver' | 'bill' | 'cancel' | 'reverse') => {
    if (!po) return
    if (action === 'reverse') {
      const ok = window.confirm(
        'Reverse this production order? Component stock and related journal entries will be restored/reversed, and the order will be cancelled.',
      )
      if (!ok) return
    }
    setBusy(true)
    setActionError(null)
    try {
      const opts: RequestInit = { method: 'POST' }
      if (action === 'deliver') {
        const qty = parseFloat(deliverQty)
        if (!Number.isFinite(qty) || qty <= 0) {
          setActionError('Enter a delivery qty greater than 0')
          setBusy(false)
          return
        }
        opts.body = JSON.stringify({ qty })
      }
      const updated = await apiFetch<Po>(`/api/production-orders/${po.id}/${action}`, opts)
      setPo(updated)
      const out = parseFloat(updated.output_qty)
      const delivered = parseFloat(updated.delivered_qty || '0')
      const remaining = Math.max(0, out - delivered)
      setDeliverQty(remaining > 0 ? String(remaining) : '')
      if (action === 'bill' && updated.invoice_id) {
        router.push(`/invoices/${updated.invoice_id}`)
      }
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  const recordScrap = async () => {
    if (!po) return
    const qty = parseFloat(scrapQty)
    if (!scrapReasonId || !scrapProductId || !Number.isFinite(qty) || qty <= 0) {
      setActionError('Select a reason, product, and qty > 0')
      return
    }
    setScrapBusy(true)
    setActionError(null)
    try {
      const updated = await apiFetch<Po>(`/api/production-orders/${po.id}/scrap`, {
        method: 'POST',
        body: JSON.stringify({
          reason_id: Number(scrapReasonId),
          product_id: Number(scrapProductId),
          qty,
          notes: scrapNotes || null,
          post_gl: true,
        }),
      })
      setPo(updated)
      setScrapQty('')
      setScrapNotes('')
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Scrap failed')
    } finally {
      setScrapBusy(false)
    }
  }

  if (loading) return <p className="p-6 text-sm text-[var(--text-primary)]/60">Loading…</p>
  if (error || !po) return (
    <div className="p-6">
      <p className="text-sm text-red-600">{error ?? 'Order not found'}</p>
      <Link href="/manufacturing/production-orders" className="text-[var(--primary)] text-sm mt-2 inline-block">← Back to list</Link>
    </div>
  )

  const nxt        = nextAction(po.state)
  const outputProd = bom ? products.get(bom.output_product_id) : undefined
  const batches    = bom ? (parseFloat(po.output_qty) / parseFloat(bom.output_qty)) : 1
  const deliveredQty = parseFloat(po.delivered_qty || '0')
  const remainingQty = Math.max(0, parseFloat(po.output_qty) - deliveredQty)

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">

      {/* Back + print */}
      <div className="flex items-center justify-between">
        <Link href="/manufacturing/production-orders" className="flex items-center gap-1 text-sm text-[var(--text-primary)]/60 hover:text-[var(--primary)]">
          <ChevronLeft className="w-4 h-4" /> Production Orders
        </Link>
        <a
          href={`/manufacturing/production-orders/${po.id}/print`}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] rounded-xl text-xs font-bold hover:bg-[var(--bg-page)] print:hidden"
        >
          <Printer className="w-3.5 h-3.5" />{t('common.print', 'Print')}</a>
      </div>

      {/* Header card */}
      <div className="bg-white border border-[var(--border)] rounded-2xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold font-mono text-[var(--text-primary)]">{po.number}</h1>
            <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
              Customer: <DocLink type="customer" id={po.customer_id} label={customer?.name ?? `#${po.customer_id}`} />
            </p>
          </div>
          <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold ${STATE_TONE[po.state] ?? ''}`}>
            {po.state.toUpperCase()}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mt-6">
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-widest font-bold mb-0.5">Output qty</p>
            <p className="text-sm font-semibold tabular-nums">{po.output_qty}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-widest font-bold mb-0.5">Delivered</p>
            <p className="text-sm font-semibold tabular-nums">
              {deliveredQty > 0 ? `${po.delivered_qty} / ${po.output_qty}` : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-widest font-bold mb-0.5">Material cost</p>
            <p className="text-sm font-semibold tabular-nums">{fmt(Number(po.own_material_cost))}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-widest font-bold mb-0.5">Labour</p>
            <p className="text-sm font-semibold tabular-nums">
              {parseFloat(po.labour_cost || '0') > 0 ? fmt(Number(po.labour_cost)) : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-widest font-bold mb-0.5">Overhead</p>
            <p className="text-sm font-semibold tabular-nums">
              {parseFloat(po.overhead_cost || '0') > 0 ? fmt(Number(po.overhead_cost)) : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-widest font-bold mb-0.5">Unit cost</p>
            <p className="text-sm font-semibold tabular-nums">
              {parseFloat(po.output_unit_cost) > 0 ? fmt(Number(po.output_unit_cost)) : '—'}
            </p>
          </div>
        </div>
        <div className="mt-4">
          <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-widest font-bold mb-0.5">Rate plan</p>
          <p className="text-sm font-semibold">{ratePlan ? `${ratePlan.code} · ${fmt(Number(ratePlan.per_unit_rate))}/unit` : '—'}</p>
        </div>

        {po.invoice_id && (
          <div className="mt-4 flex items-center gap-2 text-sm">
            <CheckCircle className="w-4 h-4 text-violet-500" />
            Invoice: <DocLink type="invoice" id={po.invoice_id} label={`INV-${String(po.invoice_id).padStart(4,'0')}`} />
          </div>
        )}

        {po.notes && (
          <p className="mt-4 text-sm text-[var(--text-primary)]/70 italic border-t border-[var(--border)] pt-3">{po.notes}</p>
        )}
      </div>

      {(po.outputs?.length ?? 0) > 0 && (
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-[var(--border)]">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Outputs</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] text-xs uppercase tracking-wide text-[var(--text-primary)]/60">
              <tr>
                <th className="text-left px-4 py-2">Product</th>
                <th className="text-left px-4 py-2">Role</th>
                <th className="text-right px-4 py-2">Qty</th>
                <th className="text-right px-4 py-2">Unit cost</th>
                <th className="text-right px-4 py-2">Delivered</th>
              </tr>
            </thead>
            <tbody>
              {po.outputs!.map(o => {
                const p = products.get(o.product_id)
                return (
                  <tr key={o.id} className="border-t border-[var(--border)]">
                    <td className="px-4 py-2">{p?.name ?? `#${o.product_id}`}</td>
                    <td className="px-4 py-2 text-xs font-semibold">{o.role}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{o.qty}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{fmt(Number(o.unit_cost))}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{o.delivered_qty}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {(po.state === 'started' || po.state === 'completed') && (
        <div className="bg-white border border-[var(--border)] rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Record scrap</h2>
            <Link href="/manufacturing/scrap-reasons" className="text-xs text-[var(--primary)] hover:underline">
              Manage reasons
            </Link>
          </div>
          {reasons.length === 0 ? (
            <p className="text-sm text-[var(--text-primary)]/55">
              No active scrap reasons.{" "}
              <Link href="/manufacturing/scrap-reasons" className="text-[var(--primary)] hover:underline">Add one</Link>
              {" "}first.
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/60 mb-1 uppercase tracking-wide">Reason</label>
                <select value={scrapReasonId} onChange={e => setScrapReasonId(e.target.value)}
                  className="w-full border border-[var(--border)] rounded-xl px-3 py-2 text-sm">
                  <option value="">Select…</option>
                  {reasons.map(r => (
                    <option key={r.id} value={r.id}>{r.code} — {r.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/60 mb-1 uppercase tracking-wide">Product</label>
                <select value={scrapProductId} onChange={e => setScrapProductId(e.target.value)}
                  className="w-full border border-[var(--border)] rounded-xl px-3 py-2 text-sm">
                  <option value="">Select…</option>
                  {Array.from(products.values()).map(p => (
                    <option key={p.id} value={p.id}>{p.code ? `${p.code} — ` : ''}{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/60 mb-1 uppercase tracking-wide">Qty</label>
                <input type="number" min="0" step="any" value={scrapQty} onChange={e => setScrapQty(e.target.value)}
                  className="w-full border border-[var(--border)] rounded-xl px-3 py-2 text-sm tabular-nums" />
              </div>
              <button type="button" onClick={recordScrap} disabled={scrapBusy}
                className="px-4 py-2.5 border border-amber-300 text-amber-900 rounded-xl text-sm font-bold hover:bg-amber-50 disabled:opacity-50">
                {scrapBusy ? 'Recording…' : 'Record scrap'}
              </button>
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold text-[var(--text-primary)]/60 mb-1 uppercase tracking-wide">Notes</label>
            <input value={scrapNotes} onChange={e => setScrapNotes(e.target.value)}
              className="w-full border border-[var(--border)] rounded-xl px-3 py-2 text-sm" placeholder="Optional" />
          </div>
        </div>
      )}

      {(po.scraps?.length ?? 0) > 0 && (
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-[var(--border)]">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Scrap history</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] text-xs uppercase tracking-wide text-[var(--text-primary)]/60">
              <tr>
                <th className="text-left px-4 py-2">Reason</th>
                <th className="text-left px-4 py-2">Product</th>
                <th className="text-right px-4 py-2">Qty</th>
                <th className="text-right px-4 py-2">Cost</th>
                <th className="text-center px-4 py-2">GL</th>
              </tr>
            </thead>
            <tbody>
              {po.scraps!.map(s => {
                const reason = reasons.find(r => r.id === s.reason_id)
                const p = products.get(s.product_id)
                return (
                  <tr key={s.id} className="border-t border-[var(--border)]">
                    <td className="px-4 py-2 font-mono text-xs">{reason?.code ?? `#${s.reason_id}`}</td>
                    <td className="px-4 py-2">{p?.name ?? `#${s.product_id}`}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{s.qty}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{fmt(Number(s.total_cost))}</td>
                    <td className="px-4 py-2 text-center text-xs">{s.gl_posted ? 'Posted' : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Lifecycle timeline */}
      <div className="bg-white border border-[var(--border)] rounded-2xl p-6">
        <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-4">Timeline</h2>
        <div className="flex flex-wrap gap-x-6 gap-y-3">
          {STAGES.map(s => {
            const ts = po[s.key as keyof Po] as string | null
            return (
              <div key={s.key} className="flex items-start gap-2">
                {ts
                  ? <CheckCircle className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                  : <div className="w-4 h-4 rounded-full border-2 border-[var(--border)] mt-0.5 shrink-0" />
                }
                <div>
                  <p className="text-xs font-bold text-[var(--text-primary)]/60">{s.label}</p>
                  <p className="text-xs text-[var(--text-primary)]">{ts ? fmt_date(ts) : '—'}</p>
                </div>
              </div>
            )
          })}
          {po.cancelled_at && (
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-bold text-red-500">Cancelled</p>
                <p className="text-xs text-[var(--text-primary)]">{fmt_date(po.cancelled_at)}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      {(nxt || po.state === 'draft' || ['started', 'completed', 'delivered'].includes(po.state)) && (
        <div className="bg-white border border-[var(--border)] rounded-2xl p-6 space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/60">{t('col.actions', 'Actions')}</h2>
          {actionError && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              {actionError}
            </div>
          )}
          <div className="flex flex-wrap gap-3 items-end">
            {nxt === 'deliver' && (
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/60 mb-1 uppercase tracking-wide">
                  Deliver qty
                  {remainingQty > 0 && (
                    <span className="ml-1 font-normal normal-case tracking-normal">
                      (remaining {remainingQty})
                    </span>
                  )}
                </label>
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={deliverQty}
                  onChange={e => setDeliverQty(e.target.value)}
                  disabled={busy}
                  className="w-36 border border-[var(--border)] rounded-xl px-3 py-2 text-sm tabular-nums focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
            )}
            {nxt && (
              <button
                onClick={() => advance(nxt)}
                disabled={busy}
                className="px-5 py-2.5 bg-[var(--text-primary)] text-white rounded-xl text-sm font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50"
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
            {['started', 'completed', 'delivered'].includes(po.state) && (
              <button
                onClick={() => advance('reverse')}
                disabled={busy}
                className="px-5 py-2.5 border border-amber-300 text-amber-900 rounded-xl text-sm font-bold hover:bg-amber-50 transition-colors disabled:opacity-50"
              >
                Reverse Order
              </button>
            )}
          </div>
          {nxt === 'deliver' && remainingQty < parseFloat(po.output_qty) && remainingQty > 0 && (
            <p className="text-[11px] text-[var(--text-primary)]/45">
              Partial deliveries keep the order in Completed until the full output qty is shipped.
            </p>
          )}
          {['started', 'completed', 'delivered'].includes(po.state) && (
            <p className="text-[11px] text-[var(--text-primary)]/45">
              Reverse restores component stock and reverses the stage journal entries for this order, then marks it cancelled.
              Billed orders must void their invoice first.
            </p>
          )}
        </div>
      )}

      {/* BOM component table */}
      {bom && (
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-[var(--border)] flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/60">
              Bill of Materials
            </h2>
            <Link href={`/manufacturing/boms`} className="text-xs text-[var(--primary)] hover:underline">
              {outputProd ? `${outputProd.code ?? ''} ${outputProd.name}` : `BOM #${bom.id}`}
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-page)]">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Component</th>
                  <th className="px-4 py-2 text-right text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Per unit</th>
                  <th className="px-4 py-2 text-right text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Total needed</th>
                  <th className="px-4 py-2 text-center text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {bom.lines.map(ln => {
                  const prod = products.get(ln.component_product_id)
                  const total = (parseFloat(ln.qty_per_output) * batches).toFixed(3).replace(/\.?0+$/, '')
                  return (
                    <tr key={ln.id} className="hover:bg-[var(--bg-page)]/50">
                      <td className="px-4 py-2">
                        <span className="font-medium">{prod?.name ?? `Product #${ln.component_product_id}`}</span>
                        {prod?.code && <span className="ml-1.5 text-xs text-[var(--text-primary)]/50 font-mono">{prod.code}</span>}
                        {ln.is_optional && <span className="ml-1.5 text-xs text-amber-600">(optional)</span>}
                        {ln.notes && <p className="text-xs text-[var(--text-primary)]/50 mt-0.5">{ln.notes}</p>}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-[var(--text-primary)]/70">{ln.qty_per_output}</td>
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
            <p className="px-6 py-3 text-xs text-[var(--text-primary)]/50 border-t border-[var(--border)]">{bom.description}</p>
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
