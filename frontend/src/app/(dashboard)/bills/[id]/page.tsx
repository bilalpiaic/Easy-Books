"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { RotateCcw, Receipt, Pencil, History, CheckCircle, CheckCircle2 } from "lucide-react"
import { useBreadcrumb } from "@/context/BreadcrumbContext"
import { apiFetch } from "@/lib/api"
import { useFmt, useSettings } from "@/context/SettingsContext"
import AttachmentPanel, { AttachmentPreviewPane, type Attachment as AttachmentT } from "@/components/AttachmentPanel"
import DocumentActions from "@/components/DocumentActions"
import { downloadPdf } from "@/lib/downloadPdf"
import { useTranslation } from "react-i18next"
import StatusBadge from "@/components/StatusBadge"
import { useMessages } from "@/context/MessageContext"

interface AuditEntry {
  id: number
  action: string
  entity_type: string
  entity_id: number
  detail: string | null
  timestamp: string
  user_name: string
  user_id: number
}

interface ChangeMap {
  [field: string]: { before: string | number | null; after: string | number | null }
}

interface BillLine {
  id: number
  product_id: number | null
  description: string
  qty: number
  unit: string | null
  rate: number
  amount: number
}
interface Bill {
  id: number
  number: string
  vendor_id: number | null
  vendor_name: string | null
  bill_date: string
  due_date: string
  description: string | null
  notes: string | null
  internal_memo: string | null
  subtotal: number
  gst_rate: number
  gst_amount: number
  total: number
  currency: string
  exchange_rate: number
  status: string
  approval_status: string | null
  transaction_id: number | null
  lines: BillLine[]
}


export default function BillDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { confirm, toast } = useMessages()
  const { t } = useTranslation()

  const fmt = useFmt()
  const { settings } = useSettings()
  const baseCurrency = settings.currency || "USD"
  const { id } = use(params)
  const [bill, setBill]   = useState<Bill | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy]   = useState(false)
  const [selectedAtt, setSelectedAtt] = useState<AttachmentT | null>(null)
  const [history, setHistory] = useState<AuditEntry[]>([])
  const [hasApprovalWorkflow, setHasApprovalWorkflow] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  useBreadcrumb(bill ? bill.number : undefined)

  const load = () =>
    apiFetch<Bill>(`/api/bills/${id}`)
      .then(setBill)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))

  const loadHistory = () =>
    apiFetch<{ items: AuditEntry[] }>(`/api/audit-log?entity_type=bill&entity_id=${id}&limit=50`)
      .then(data => setHistory(data.items.filter(r => r.action === "UPDATE")))
      .catch(() => {/* non-critical; silently ignore */})

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); loadHistory() }, [id])

  useEffect(() => {
    apiFetch<{ is_active?: boolean }[]>(`/api/approvals/workflows?document_type=bill`)
      .then((rows) => setHasApprovalWorkflow(rows.some((w) => w.is_active !== false)))
      .catch(() => setHasApprovalWorkflow(false))
  }, [])

  const submitForApproval = async () => {
    if (!bill) return
    setBusy(true); setError(null)
    try {
      const res = await apiFetch<{
        ok: boolean; submitted: boolean; message?: string; approval_status?: string
      }>(`/api/bills/${bill.id}/submit-for-approval`, { method: "POST" })
      if (!res.submitted) {
        toast(res.message || "No approval workflow configured", "info")
      } else {
        toast("Submitted for approval", "success")
        setBill((prev) => prev ? { ...prev, approval_status: res.approval_status || "pending" } : prev)
      }
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed")
    } finally {
      setBusy(false)
    }
  }

  const markReceived = async () => {
    const ok = await confirm({
      title: `Mark bill ${bill?.number} as Received?`,
      confirmLabel: "Mark received",
    })
    if (!ok) return
    setBusy(true); setError(null)
    try {
      await apiFetch(`/api/bills/${id}/status?status=received`, { method: "PATCH" })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to mark as received")
    } finally {
      setBusy(false)
    }
  }

  const reverse = async () => {
    if (!bill?.transaction_id) {
      setError("This bill has no posted transaction to reverse.")
      return
    }
    const ok = await confirm({
      title: `Reverse bill ${bill.number}?`,
      message: "A new equal-and-opposite JV will be posted today.",
      confirmLabel: "Reverse",
      danger: true,
    })
    if (!ok) return
    setBusy(true); setError(null)
    try {
      await apiFetch(`/api/transactions/${bill.transaction_id}/reverse`, { method: "POST" })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reverse failed")
    } finally {
      setBusy(false)
    }
  }

  if (error && !bill) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!bill)          return <p className="p-4 text-[var(--text-primary)]/60 text-sm">Loading bill…</p>

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div className="flex items-center gap-2">
          {(bill.status === "draft" || bill.status === "received" || bill.status === "overdue") && (
            <Link
              href={`/bills/${bill.id}/edit`}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--primary)]/50 text-[var(--primary)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)]"
            >
              <Pencil className="w-4 h-4" /> Edit
            </Link>
          )}
          {(bill.status === "paid" || bill.status === "partial") && (
            <span
              title="Unallocate payments to edit."
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--border)] text-[var(--text-primary)]/30 rounded-lg text-sm font-bold cursor-not-allowed"
            >
              <Pencil className="w-4 h-4" /> Edit
            </span>
          )}
          {bill.status === "draft" && (
            <button
              onClick={markReceived}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--primary)]/50 text-[var(--primary)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              <CheckCircle className="w-4 h-4" /> Mark as Received
            </button>
          )}
          {hasApprovalWorkflow && !["pending", "approved"].includes(bill.approval_status || "")
            && !["void", "voided", "reversed", "paid"].includes(bill.status) && (
            <button
              onClick={submitForApproval}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--primary)]/50 text-[var(--primary)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" /> Submit for approval
            </button>
          )}
          <DocumentActions
            onPrint={() => { window.location.href = `/bills/${bill.id}/print` }}
            onSavePdf={async () => {
              setPdfBusy(true)
              try {
                await downloadPdf(`/api/bills/${bill.id}/pdf`, `${bill.number}.pdf`)
              } catch (e) {
                toast((e as Error).message || "PDF generation failed", "error")
              } finally {
                setPdfBusy(false)
              }
            }}
            pdfBusy={pdfBusy}
          />
          {bill.transaction_id && bill.status !== "reversed" && (
            <button onClick={reverse} disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-red-50 hover:text-red-700 disabled:opacity-50">
              <RotateCcw className="w-4 h-4" /> {busy ? "Reversing…" : "Reverse"}
            </button>
          )}
        </div>
      </div>

      <header className="bg-white border border-[var(--border)] rounded-xl p-5 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <Receipt className="w-7 h-7 text-[var(--primary)] shrink-0 mt-1" />
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Bill {bill.number}</h1>
            <p className="text-sm text-[var(--text-primary)]/60">
              Dated {bill.bill_date} · Due {bill.due_date}
              {bill.currency && bill.currency !== baseCurrency && (
                <> · {bill.currency} @ {bill.exchange_rate} · {baseCurrency} {fmt(Number(bill.total) * Number(bill.exchange_rate || 1))}</>
              )}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <StatusBadge status={bill.status} />
          {bill.approval_status && (
            <span className="inline-block border rounded-full px-2 py-0.5 text-[10px] font-semibold border-[var(--border)] text-[var(--text-primary)]/70">
              Approval: {bill.approval_status}
            </span>
          )}
        </div>
      </header>

      {error && <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2 rounded text-sm">{error}</div>}

      <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="bg-white border border-[var(--border)] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.vendor', 'Vendor')}</div>
          {bill.vendor_id ? (
            <Link href={`/vendors/${bill.vendor_id}/ledger`} className="font-semibold text-[var(--text-primary)] hover:text-[var(--primary)] hover:underline">
              {bill.vendor_name ?? `#${bill.vendor_id}`}
            </Link>
          ) : (
            <span className="font-semibold">{bill.vendor_name ?? "—"}</span>
          )}
        </div>
        <div className="bg-white border border-[var(--border)] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Posted Voucher</div>
          {bill.transaction_id ? (
            <Link href={`/journal/${bill.transaction_id}`} className="font-mono text-sm text-[var(--primary)] hover:underline">View JV →</Link>
          ) : (
            <span className="text-sm text-[var(--text-primary)]/55">No voucher yet (draft)</span>
          )}
        </div>
      </section>

      <section className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)]">
            <tr>
              <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">{t('col.description', 'Description')}</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-24">Qty</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-28">Rate</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-32">{t('col.amount', 'Amount')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {bill.lines.map(ln => (
              <tr key={ln.id}>
                <td className="px-4 py-2">
                  {ln.product_id ? (
                    <Link href={`/products/${ln.product_id}/stock-card`} className="hover:text-[var(--primary)] hover:underline">{ln.description}</Link>
                  ) : ln.description}
                </td>
                <td className="px-4 py-2 text-right font-mono">{ln.qty} {ln.unit ?? ""}</td>
                <td className="px-4 py-2 text-right font-mono">{fmt(ln.rate)}</td>
                <td className="px-4 py-2 text-right font-mono">{fmt(ln.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </section>

      {(bill.notes || bill.internal_memo) && (
        <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {bill.notes && (
            <div className="bg-white border border-[var(--border)] rounded-xl p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.notes', 'Notes')}</div>
              <p className="text-sm text-[var(--text-primary)]/80 whitespace-pre-wrap">{bill.notes}</p>
            </div>
          )}
          {bill.internal_memo && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-amber-700/70 mb-1">Internal Memo</div>
              <p className="text-sm text-amber-900/80 whitespace-pre-wrap">{bill.internal_memo}</p>
            </div>
          )}
        </section>
      )}

      <section className="flex justify-end">
        <div className="bg-white border border-[var(--border)] rounded-xl p-4 w-full sm:w-80 text-sm space-y-1">
          <Row label="Subtotal" value={fmt(bill.subtotal)} />
          {bill.gst_rate > 0 && <Row label={`GST (${bill.gst_rate}%)`} value={fmt(bill.gst_amount)} />}
          <div className="border-t border-[var(--text-primary)] pt-1.5 mt-1.5">
            <Row label="Total" value={fmt(bill.total)} bold />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4 print:hidden">
        <AttachmentPanel parentType="bill" parentId={bill.id} embedded onSelect={setSelectedAtt} />
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden min-h-[60vh]">
          <AttachmentPreviewPane att={selectedAtt} />
        </div>
      </section>

      {/* Change History */}
      {history.length > 0 && (
        <section className="bg-white border border-[var(--border)] rounded-xl overflow-hidden print:hidden">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-[var(--bg-page)] border-b border-[var(--border)]">
            <History className="w-4 h-4 text-[var(--primary)]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Change History</span>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {history.map(entry => {
              let changes: ChangeMap = {}
              try {
                const detail = JSON.parse(entry.detail ?? "{}")
                changes = (detail.changes ?? {}) as ChangeMap
              } catch {
                // ignore malformed detail
              }
              const changedFields = Object.entries(changes)
              return (
                <div key={entry.id} className="px-4 py-3 text-sm">
                  <p className="text-[var(--text-primary)]/65 text-xs mb-1">
                    Edited by <span className="font-semibold text-[var(--text-primary)]">{entry.user_name}</span>
                    {" "}on {new Date(entry.timestamp).toLocaleString()}
                  </p>
                  {changedFields.length > 0 ? (
                    <table className="ui-table text-xs mt-1">
                      <thead>
                        <tr>
                          <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/40 w-32">Field</th>
                          <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/40">Before</th>
                          <th className="ui-th text-left text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/40">After</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]/60">
                        {changedFields.map(([field, val]) => (
                          <tr key={field}>
                            <td className="ui-td font-medium text-[var(--text-primary)]/70 capitalize">{field.replace(/_/g, " ")}</td>
                            <td className="ui-td font-mono text-red-700/80">{String(val.before ?? "—")}</td>
                            <td className="ui-td font-mono text-emerald-700">{String(val.after ?? "—")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="text-xs text-[var(--text-primary)]/40 italic">No header fields changed.</p>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}

function Row({ label, value, bold = false }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className={bold ? "font-bold" : "text-[var(--text-primary)]/65"}>{label}</span>
      <span className={`font-mono ${bold ? "font-bold text-base" : ""}`}>{value}</span>
    </div>
  )
}
