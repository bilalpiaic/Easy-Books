"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Printer, XCircle, CheckCircle, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { getCurrentUser } from "@/lib/auth"
import PrintHeader from "@/components/PrintHeader"
import StatusBadge from "@/components/StatusBadge"

type GOLine = { id: number; product_id: number; qty: number; unit_cost: number; unit_value: number }

type GateOutward = {
  id: number; number: string; source_doc_type: string; source_doc_id?: number
  gate_date: string; time_out?: string
  vehicle_no?: string; challan_no?: string; remarks?: string
  status: string; created_by_id: number; approved_by_id?: number
  cancel_reason?: string
  lines: GOLine[]
  reference?: string
}

type Product = { id: number; name: string; unit?: string }

const TYPE_LABEL: Record<string, string> = {
  invoice: "Invoice",
  debit_note: "Debit Note",
  scrap: "Scrap",
}

export default function GateOutwardDetailPage() {
  const { id } = useParams<{ id: string }>()
  const fmt = useFmt()

  const [go, setGo] = useState<GateOutward | null>(null)
  const [products, setProducts] = useState<Record<number, Product>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [currentUserId, setCurrentUserId] = useState<number | null>(null)
  const [isAdmin, setIsAdmin] = useState(false)

  const [showCancel, setShowCancel] = useState(false)
  const [cancelReason, setCancelReason] = useState("")

  const load = useCallback(async () => {
    try {
      const d = await apiFetch<GateOutward>(`/api/gate-outwards/${id}`)
      setGo(d)
      if (d.lines.length) {
        const prodIds = Array.from(new Set(d.lines.map(l => l.product_id)))
        const entries = await Promise.all(
          prodIds.map(pid => apiFetch<Product>(`/api/products/${pid}`).catch(() => null))
        )
        setProducts(Object.fromEntries(
          entries.filter((p): p is Product => !!p).map(p => [p.id, p])
        ))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Not found")
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const user = getCurrentUser()
    if (user) setIsAdmin(user.role === "admin" || user.role === "owner")
    apiFetch<{ id: number; role?: string }>("/api/auth/me")
      .then(d => {
        setCurrentUserId(d.id)
        if (d.role) setIsAdmin(d.role === "admin" || d.role === "owner")
      })
      .catch(() => {})
  }, [])

  const approve = async () => {
    setBusy(true); setError(null)
    try {
      await apiFetch(`/api/gate-outwards/${id}/approve`, { method: "PATCH" })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed")
    } finally {
      setBusy(false)
    }
  }

  const cancel = async () => {
    if (!cancelReason.trim()) { setError("A cancellation reason is required."); return }
    setBusy(true); setError(null)
    try {
      await apiFetch(`/api/gate-outwards/${id}/cancel`, {
        method: "PATCH",
        body: JSON.stringify({ reason: cancelReason.trim() }),
      })
      setShowCancel(false)
      setCancelReason("")
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cancel failed")
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="p-4 text-sm text-[var(--text-muted)]">Loading…</p>
  if (!go) return <p className="p-4 text-sm text-red-600">{error ?? "Gate outward not found"}</p>

  const canApprove = go.source_doc_type === "scrap" && go.status === "draft"
  const isSelfApproval = currentUserId != null && go.created_by_id === currentUserId
  const canCancel = go.status !== "cancelled" && !(go.source_doc_type === "scrap" && go.status === "approved")

  return (
    <div className="p-4 space-y-4 max-w-4xl">
      <PrintHeader title={go.number} subtitle={fmtDate(go.gate_date)} />

      <div className="flex items-center justify-between print:hidden">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-[var(--text-primary)]">{go.number}</h1>
          <StatusBadge status={go.status} />
        </div>
        <Link href="/store/gate-outward"
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft className="w-4 h-4" /> All Gate Outward
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
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Type</dt>
            <dd>{TYPE_LABEL[go.source_doc_type] || go.source_doc_type}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Reference</dt>
            <dd>{go.reference || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Time Out</dt>
            <dd>{go.time_out || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Status</dt>
            <dd className="capitalize">{go.status}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Vehicle No.</dt>
            <dd>{go.vehicle_no || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Challan No.</dt>
            <dd>{go.challan_no || "—"}</dd>
          </div>
        </dl>
        {go.remarks && (
          <div className="mt-3 bg-[var(--bg-page)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs text-[var(--text-muted)]">
            {go.remarks}
          </div>
        )}
        {go.status === "cancelled" && go.cancel_reason && (
          <div className="mt-3 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-800">
            Cancelled: {go.cancel_reason}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-start gap-2 print:hidden">
        <button onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--border)] text-sm hover:bg-[var(--bg-page)]">
          <Printer className="w-4 h-4" /> Print
        </button>
        {canApprove && isAdmin && (
          <button
            onClick={approve}
            disabled={busy || isSelfApproval}
            title={isSelfApproval ? "You cannot approve your own entry" : undefined}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-blue-600 text-white text-sm disabled:opacity-50"
          >
            <CheckCircle className="w-4 h-4" /> Approve
          </button>
        )}
        {canCancel && !showCancel && (
          <button onClick={() => setShowCancel(true)} disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-red-300 text-red-700 text-sm disabled:opacity-50">
            <XCircle className="w-4 h-4" /> Cancel
          </button>
        )}
        {canCancel && showCancel && (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2">
            <input
              type="text"
              value={cancelReason}
              onChange={e => setCancelReason(e.target.value)}
              placeholder="Reason for cancellation…"
              className="px-2 py-1.5 border border-[var(--border)] rounded-md text-sm min-w-[220px] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
            />
            <button onClick={cancel} disabled={busy}
              className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-sm disabled:opacity-50">
              Confirm Cancel
            </button>
            <button onClick={() => { setShowCancel(false); setCancelReason("") }} disabled={busy}
              className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-sm hover:bg-[var(--bg-page)]">
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Lines */}
      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Product</th>
              <th className="px-3 py-2">Qty</th>
              <th className="px-3 py-2">Unit</th>
              {go.source_doc_type === "scrap" && (
                <>
                  <th className="px-3 py-2">Unit Cost</th>
                  <th className="px-3 py-2">Unit Value</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {go.lines.map(l => {
              const product = products[l.product_id]
              return (
                <tr key={l.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2">{product?.name || `Product #${l.product_id}`}</td>
                  <td className="px-3 py-2">{fmt(Number(l.qty))}</td>
                  <td className="px-3 py-2">{product?.unit || "—"}</td>
                  {go.source_doc_type === "scrap" && (
                    <>
                      <td className="px-3 py-2">{fmt(Number(l.unit_cost))}</td>
                      <td className="px-3 py-2">{fmt(Number(l.unit_value))}</td>
                    </>
                  )}
                </tr>
              )
            })}
            {go.lines.length === 0 && (
              <tr><td colSpan={go.source_doc_type === "scrap" ? 5 : 3} className="px-3 py-8 text-center text-[var(--text-muted)]">No lines</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
