"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, CheckCircle, XCircle, Lock, Pencil, FileText, Scale, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate, todayLocal } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"

type DemandLine = { id: number; product_id?: number; description: string; qty: number; unit?: string }

type Demand = {
  id: number; number: string; demand_date: string; required_by?: string
  analytic_account_id?: number; purpose?: string; notes?: string; status: string
  created_by_id: number; approved_by_id?: number
  lines: DemandLine[]
}

type Quotation = {
  id: number; number: string; vendor_id: number; quote_date: string
  valid_until?: string; total: number
}

export default function DemandDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const fmt = useFmt()

  const [demand, setDemand] = useState<Demand | null>(null)
  const [quotes, setQuotes] = useState<Quotation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const d = await apiFetch<Demand>(`/api/purchase-demands/${id}`)
      setDemand(d)
      const q = await apiFetch<Quotation[]>(`/api/quotations?demand_id=${id}`)
      setQuotes(q)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Not found")
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  const runAction = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed")
    } finally {
      setBusy(false)
    }
  }

  const approve = () => runAction(async () => {
    await apiFetch(`/api/purchase-demands/${id}/approve`, { method: "PATCH" })
    await load()
  })

  const cancel = () => runAction(async () => {
    await apiFetch(`/api/purchase-demands/${id}/cancel`, { method: "PATCH" })
    await load()
  })

  const close = () => runAction(async () => {
    await apiFetch(`/api/purchase-demands/${id}/close`, { method: "PATCH" })
    await load()
  })

  const createComparative = () => runAction(async () => {
    const cs = await apiFetch<{ id: number }>(`/api/comparatives`, {
      method: "POST",
      body: JSON.stringify({ demand_id: Number(id), cs_date: todayLocal() }),
    })
    router.push(`/purchases/comparatives/${cs.id}`)
  })

  if (loading) return <p className="p-4 text-sm text-[var(--text-muted)]">Loading…</p>
  if (!demand) return <p className="p-4 text-sm text-red-600">{error ?? "Demand not found"}</p>

  return (
    <div className="p-4 space-y-4 max-w-4xl">
      <PrintHeader title={demand.number} subtitle={fmtDate(demand.demand_date)} />

      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-lg font-bold text-[var(--text-primary)]">{demand.number}</h1>
        <Link href="/purchases/demands"
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft className="w-4 h-4" /> All Demands
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm flex items-start gap-2 print:hidden">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {/* Header fields */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Date</dt>
            <dd>{fmtDate(demand.demand_date)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Required By</dt>
            <dd>{demand.required_by ? fmtDate(demand.required_by) : "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Purpose</dt>
            <dd>{demand.purpose || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Status</dt>
            <dd className="capitalize">{demand.status}</dd>
          </div>
        </dl>
        {demand.notes && (
          <div className="mt-3 bg-[var(--bg-page)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs text-[var(--text-muted)]">
            {demand.notes}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 print:hidden">
        {demand.status === "draft" && (
          <>
            <Link href={`/purchases/demands/${id}/edit`}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--border)] text-sm hover:bg-[var(--bg-page)]">
              <Pencil className="w-4 h-4" /> Edit
            </Link>
            <button onClick={approve} disabled={busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-blue-600 text-white text-sm disabled:opacity-50">
              <CheckCircle className="w-4 h-4" /> Approve
            </button>
            <button onClick={cancel} disabled={busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-red-300 text-red-700 text-sm disabled:opacity-50">
              <XCircle className="w-4 h-4" /> Cancel
            </button>
          </>
        )}

        {demand.status === "approved" && (
          <>
            <Link href={`/purchases/demands/${id}/quotations/new`}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
              <FileText className="w-4 h-4" /> New Quotation
            </Link>
            {quotes.length >= 1 && (
              <button onClick={createComparative} disabled={busy}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-600 text-white text-sm disabled:opacity-50">
                <Scale className="w-4 h-4" /> Create Comparative
              </button>
            )}
            <button onClick={close} disabled={busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--border)] text-sm hover:bg-[var(--bg-page)] disabled:opacity-50">
              <Lock className="w-4 h-4" /> Close
            </button>
            <button onClick={cancel} disabled={busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-red-300 text-red-700 text-sm disabled:opacity-50">
              <XCircle className="w-4 h-4" /> Cancel
            </button>
          </>
        )}
      </div>

      {/* Lines */}
      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Description</th>
              <th className="px-3 py-2">Qty</th>
              <th className="px-3 py-2">Unit</th>
            </tr>
          </thead>
          <tbody>
            {demand.lines.map(l => (
              <tr key={l.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2">{l.description}</td>
                <td className="px-3 py-2">{l.qty}</td>
                <td className="px-3 py-2">{l.unit || "—"}</td>
              </tr>
            ))}
            {demand.lines.length === 0 && (
              <tr><td colSpan={3} className="px-3 py-8 text-center text-[var(--text-muted)]">No lines</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Quotations received */}
      <div className="space-y-2 print:hidden">
        <h2 className="text-sm font-bold text-[var(--text-primary)]">Quotations Received</h2>
        <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-muted)]">
                <th className="px-3 py-2">VQ #</th>
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Valid Until</th>
                <th className="px-3 py-2">Total</th>
              </tr>
            </thead>
            <tbody>
              {quotes.map(q => (
                <tr key={q.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2 whitespace-nowrap">{q.number}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{fmtDate(q.quote_date)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{q.valid_until ? fmtDate(q.valid_until) : "—"}</td>
                  <td className="px-3 py-2">{fmt(Number(q.total))}</td>
                </tr>
              ))}
              {quotes.length === 0 && (
                <tr><td colSpan={4} className="px-3 py-8 text-center text-[var(--text-muted)]">No quotations yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
