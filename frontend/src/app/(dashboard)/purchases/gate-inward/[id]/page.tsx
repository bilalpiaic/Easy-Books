"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Printer, XCircle, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import StatusBadge from "@/components/StatusBadge"

type GILine = { id: number; po_line_id: number; product_id?: number; qty_received: number }

type GateInward = {
  id: number; number: string; po_id: number; gate_date: string; time_in?: string
  vehicle_no?: string; challan_no?: string; remarks?: string
  status: string; cancel_reason?: string
  lines: GILine[]
  po_number?: string; vendor_name?: string
}

type POLine = { id: number; description: string; unit?: string }

export default function GateInwardDetailPage() {
  const { id } = useParams<{ id: string }>()
  const fmt = useFmt()

  const [gi, setGi] = useState<GateInward | null>(null)
  const [poLines, setPoLines] = useState<Record<number, POLine>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [showCancel, setShowCancel] = useState(false)
  const [cancelReason, setCancelReason] = useState("")

  const load = useCallback(async () => {
    try {
      const d = await apiFetch<GateInward>(`/api/gate-inwards/${id}`)
      setGi(d)
      const po = await apiFetch<{ lines: POLine[] }>(`/api/purchase-orders/${d.po_id}`)
      setPoLines(Object.fromEntries(po.lines.map(l => [l.id, l])))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Not found")
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  const cancel = async () => {
    if (!cancelReason.trim()) { setError("A cancellation reason is required."); return }
    setBusy(true); setError(null)
    try {
      await apiFetch(`/api/gate-inwards/${id}/cancel`, {
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
  if (!gi) return <p className="p-4 text-sm text-red-600">{error ?? "Gate inward not found"}</p>

  return (
    <div className="p-4 space-y-4 max-w-4xl">
      <PrintHeader title={gi.number} subtitle={fmtDate(gi.gate_date)} />

      <div className="flex items-center justify-between print:hidden">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-[var(--text-primary)]">{gi.number}</h1>
          <StatusBadge status={gi.status} />
        </div>
        <Link href="/purchases/gate-inward"
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft className="w-4 h-4" /> All Gate Entries
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
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Purchase Order</dt>
            <dd>
              <Link href={`/manufacturing/purchase-orders/${gi.po_id}`} className="text-[var(--primary)] print:text-inherit">
                {gi.po_number || gi.po_id}
              </Link>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Vendor</dt>
            <dd>{gi.vendor_name || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Time In</dt>
            <dd>{gi.time_in || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Status</dt>
            <dd className="capitalize">{gi.status}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Vehicle No.</dt>
            <dd>{gi.vehicle_no || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Challan No.</dt>
            <dd>{gi.challan_no || "—"}</dd>
          </div>
        </dl>
        {gi.remarks && (
          <div className="mt-3 bg-[var(--bg-page)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs text-[var(--text-muted)]">
            {gi.remarks}
          </div>
        )}
        {gi.status === "cancelled" && gi.cancel_reason && (
          <div className="mt-3 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-800">
            Cancelled: {gi.cancel_reason}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-start gap-2 print:hidden">
        <button onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--border)] text-sm hover:bg-[var(--bg-page)]">
          <Printer className="w-4 h-4" /> Print
        </button>
        {gi.status === "open" && !showCancel && (
          <button onClick={() => setShowCancel(true)} disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-red-300 text-red-700 text-sm disabled:opacity-50">
            <XCircle className="w-4 h-4" /> Cancel
          </button>
        )}
        {gi.status === "open" && showCancel && (
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
              <th className="px-3 py-2">Description</th>
              <th className="px-3 py-2">Qty Received</th>
              <th className="px-3 py-2">Unit</th>
            </tr>
          </thead>
          <tbody>
            {gi.lines.map(l => {
              const poLine = poLines[l.po_line_id]
              return (
                <tr key={l.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2">{poLine?.description || `Line #${l.po_line_id}`}</td>
                  <td className="px-3 py-2">{fmt(Number(l.qty_received))}</td>
                  <td className="px-3 py-2">{poLine?.unit || "—"}</td>
                </tr>
              )
            })}
            {gi.lines.length === 0 && (
              <tr><td colSpan={3} className="px-3 py-8 text-center text-[var(--text-muted)]">No lines</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
