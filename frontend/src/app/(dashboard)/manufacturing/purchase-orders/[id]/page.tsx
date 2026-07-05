"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { ShoppingCart, CheckCircle, FileText, AlertCircle, ArrowLeft, Printer, DoorOpen } from "lucide-react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { useTranslation } from "react-i18next"
import StatusBadge from "@/components/StatusBadge"

interface POLine {
  id: number
  description: string
  qty: string
  unit: string | null
  rate: string
  amount: string
}

interface PurchaseOrder {
  id: number
  number: string
  vendor_id: number | null
  vendor_name: string | null
  order_date: string
  expected_date: string | null
  description: string | null
  notes: string | null
  subtotal: string
  total: string
  status: string
  bill_id: number | null
  lines: POLine[]
  gi_coverage?: Record<string, string>
  gate_required?: boolean
}

export default function PurchaseOrderDetailPage() {
  const { t } = useTranslation()

  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const fmt = useFmt()

  const [po, setPo] = useState<PurchaseOrder | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Convert-to-bill modal state
  const [showConvert, setShowConvert] = useState(false)
  const [billDate, setBillDate] = useState(new Date().toISOString().split("T")[0])
  const [dueDate, setDueDate] = useState("")
  const [convertError, setConvertError] = useState("")

  useEffect(() => {
    apiFetch<PurchaseOrder>(`/api/purchase-orders/${id}`)
      .then(setPo)
      .catch(e => setError(e instanceof Error ? e.message : "Not found"))
      .finally(() => setLoading(false))
  }, [id])

  const approve = async () => {
    setBusy(true); setError(null)
    try {
      await apiFetch(`/api/purchase-orders/${id}/approve`, { method: "PATCH" })
      const updated = await apiFetch<PurchaseOrder>(`/api/purchase-orders/${id}`)
      setPo(updated)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed")
    } finally {
      setBusy(false)
    }
  }

  const convertToBill = async () => {
    if (!dueDate) { setConvertError("Due date is required"); return }
    setBusy(true); setConvertError("")
    try {
      const res = await apiFetch<{ bill: { id: number } }>(`/api/purchase-orders/${id}/convert-to-bill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bill_date: billDate, due_date: dueDate }),
      })
      router.push(`/bills/${res.bill.id}`)
    } catch (e) {
      setConvertError(e instanceof Error ? e.message : "Convert failed")
      setBusy(false)
    }
  }

  if (loading) return <p className="text-sm text-[var(--text-primary)]/60">Loading…</p>
  if (!po) return <p className="text-sm text-red-600">{error ?? "Purchase order not found"}</p>

  const gateRequired = !!po.gate_required
  const coverageFor = (lineId: number) => Number(po.gi_coverage?.[String(lineId)] ?? 0)
  const fullyCovered = !gateRequired || po.lines.every(l => coverageFor(l.id) >= Number(l.qty))

  return (
    <div className="space-y-5 max-w-4xl">
      {/* Header */}
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <ShoppingCart className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">{po.number}</h1>
              <StatusBadge status={po.status} />
            </div>
            <p className="text-sm text-[var(--text-primary)]/60">{po.vendor_name ?? "No vendor"} · {po.order_date}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href={`/manufacturing/purchase-orders/${id}/print`}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] rounded-xl text-xs font-bold hover:bg-[var(--bg-page)] print:hidden"
          >
            <Printer className="w-3.5 h-3.5" />{t('common.print', 'Print')}</Link>
          <Link
            href="/manufacturing/purchase-orders"
            className="flex items-center gap-1.5 text-sm text-[var(--text-primary)]/60 hover:text-[var(--text-primary)] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            All POs
          </Link>
        </div>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {/* Actions */}
      {po.status === "draft" && (
        <div className="flex gap-3">
          <button
            onClick={approve}
            disabled={busy}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            <CheckCircle className="w-4 h-4" />
            {busy ? "Approving…" : "Approve PO"}
          </button>
        </div>
      )}

      {po.status === "approved" && (
        <div className="flex gap-3">
          {gateRequired && (
            <Link
              href={`/purchases/gate-inward/new?po=${po.id}`}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
            >
              <DoorOpen className="w-4 h-4 text-[var(--primary)]" />
              Record Gate Inward
            </Link>
          )}
          <button
            onClick={() => setShowConvert(true)}
            disabled={busy || !fullyCovered}
            title={!fullyCovered ? "Record gate inward entries covering every line first" : undefined}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-bold hover:bg-emerald-700 transition-colors disabled:opacity-50"
          >
            <FileText className="w-4 h-4" />
            Convert to Bill
          </button>
        </div>
      )}

      {po.status === "billed" && po.bill_id && (
        <div className="flex gap-3">
          <Link
            href={`/bills/${po.bill_id}`}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-[var(--border)] rounded-lg text-sm font-semibold hover:bg-[var(--bg-page)] transition-colors"
          >
            <FileText className="w-4 h-4 text-[var(--primary)]" />
            View Bill
          </Link>
        </div>
      )}

      {/* Details card */}
      <div className="bg-white border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Order Details</h2>
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div><dt className="text-[var(--text-primary)]/55 text-xs font-semibold uppercase tracking-wide mb-0.5">{t('col.vendor', 'Vendor')}</dt><dd>{po.vendor_name ?? "—"}</dd></div>
          <div><dt className="text-[var(--text-primary)]/55 text-xs font-semibold uppercase tracking-wide mb-0.5">Order Date</dt><dd>{po.order_date}</dd></div>
          <div><dt className="text-[var(--text-primary)]/55 text-xs font-semibold uppercase tracking-wide mb-0.5">Expected</dt><dd>{po.expected_date ?? "—"}</dd></div>
          <div><dt className="text-[var(--text-primary)]/55 text-xs font-semibold uppercase tracking-wide mb-0.5">{t('col.total', 'Total')}</dt><dd className="font-mono font-bold">{fmt(Number(po.total))}</dd></div>
        </dl>
        {po.description && <p className="text-sm text-[var(--text-primary)]/75">{po.description}</p>}
        {po.notes && (
          <div className="bg-[#faf8f4] border border-[var(--border)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)]/70">{po.notes}</div>
        )}
      </div>

      {/* Line items */}
      <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border)]">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Items</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)] text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
            <tr>
              <th className="text-left px-4 py-2">{t('col.description', 'Description')}</th>
              <th className="text-right px-4 py-2 w-20">Qty</th>
              <th className="text-left px-4 py-2 w-20">{t('col.unit', 'Unit')}</th>
              <th className="text-right px-4 py-2 w-28">Rate</th>
              <th className="text-right px-4 py-2 w-28">{t('col.amount', 'Amount')}</th>
              {gateRequired && <th className="text-right px-4 py-2 w-32">Gate Coverage</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {po.lines.map(line => {
              const received = coverageFor(line.id)
              const covered = received >= Number(line.qty)
              return (
                <tr key={line.id}>
                  <td className="px-4 py-2">{line.description}</td>
                  <td className="px-4 py-2 text-right font-mono">{line.qty}</td>
                  <td className="px-4 py-2 text-[var(--text-primary)]/60">{line.unit ?? "—"}</td>
                  <td className="px-4 py-2 text-right font-mono">{fmt(Number(line.rate))}</td>
                  <td className="px-4 py-2 text-right font-mono font-semibold">{fmt(Number(line.amount))}</td>
                  {gateRequired && (
                    <td className={`px-4 py-2 text-right font-mono text-xs font-semibold ${covered ? "text-emerald-700" : "text-amber-700"}`}>
                      {fmt(received)}/{line.qty}
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
          <tfoot className="border-t-2 border-[var(--border)] bg-[#faf8f4]">
            <tr>
              <td colSpan={4} className="px-4 py-2 text-right text-xs font-bold uppercase tracking-wide text-[var(--text-primary)]/55">{t('col.total', 'Total')}</td>
              <td className="px-4 py-2 text-right font-mono font-bold text-[var(--text-primary)]">{fmt(Number(po.total))}</td>
              {gateRequired && <td />}
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Convert-to-Bill modal */}
      {showConvert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl border border-[var(--border)] w-full max-w-sm p-6 space-y-4 shadow-xl">
            <h2 className="text-lg font-bold text-[var(--text-primary)]">Convert to Bill</h2>
            <p className="text-sm text-[var(--text-primary)]/60">Creates a vendor bill from this PO and posts the accounting entry.</p>

            {convertError && (
              <div className="bg-red-50 border border-red-200 text-red-800 text-sm px-3 py-2 rounded-lg">{convertError}</div>
            )}

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Bill Date <span className="text-red-500">*</span></label>
                <input
                  type="date"
                  value={billDate}
                  onChange={e => setBillDate(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">{t('col.dueDate', 'Due Date')}<span className="text-red-500">*</span></label>
                <input
                  type="date"
                  value={dueDate}
                  onChange={e => setDueDate(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
                />
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => { setShowConvert(false); setConvertError("") }}
                className="flex-1 px-4 py-2.5 bg-white border border-[var(--border)] rounded-lg font-semibold text-sm hover:bg-[var(--bg-page)] transition-colors"
              >{t('common.cancel', 'Cancel')}</button>
              <button
                onClick={convertToBill}
                disabled={busy}
                className="flex-1 px-4 py-2.5 bg-[var(--text-primary)] text-white rounded-lg font-semibold text-sm hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50"
              >
                {busy ? "Creating…" : "Create Bill"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
