"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { Printer, RotateCcw, FileSignature, Pencil, Link as LinkIcon, History, Send, Ban, CheckCircle2, MessageSquareWarning } from "lucide-react"
import { useBreadcrumb } from "@/context/BreadcrumbContext"
import { apiFetch, apiBase, networkErrorMessage } from "@/lib/api"
import { useFmt, useSettings } from "@/context/SettingsContext"
import AttachmentPanel, { AttachmentPreviewPane, type Attachment as AttachmentT } from "@/components/AttachmentPanel"
import DocumentActions from "@/components/DocumentActions"
import { downloadPdf } from "@/lib/downloadPdf"
import { useTranslation } from "react-i18next"
import { usePRAPortal } from "@/hooks/usePRAPortal"
import { useModules } from "@/context/ModuleContext"
import StatusBadge from "@/components/StatusBadge"
import { useMessages } from "@/context/MessageContext"
import { fmtDate } from "@/lib/utils"

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

interface InvoiceLine {
  id: number
  product_id: number | null
  description: string
  qty: number
  unit: string | null
  rate: number
  amount: number
}

interface PortalDispute {
  id: number
  body: string
  status: string
  created_at: string
}
interface Invoice {
  id: number
  number: string
  customer_id: number | null
  customer_name: string | null
  issue_date: string
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
  carrying_rate?: number | null
  status: string
  approval_status: string | null
  transaction_id: number | null
  lines: InvoiceLine[]
  // PRA e-Invoice fields
  payment_mode: number | null
  pra_status: string | null
  pra_fiscal_number: string | null
  pra_usin: string | null
  pra_submitted_at: string | null
  // ZATCA e-Invoice (#264)
  zatca_status: string | null
  zatca_uuid: string | null
  zatca_hash: string | null
  zatca_qr: string | null
  zatca_submitted_at: string | null
  // Peppol / EU VAT (#266)
  peppol_status: string | null
  peppol_document_id: string | null
  peppol_submitted_at: string | null
  allocation_audit?: {
    method: string
    transaction_price: number
    detail: unknown
    created_at?: string
  } | null
}

const PRA_STATUS_TONE: Record<string, string> = {
  not_required: "hidden",
  pending:      "bg-amber-50 text-amber-800 border-amber-300",
  submitted:    "bg-emerald-50 text-emerald-800 border-emerald-300",
  failed:       "bg-red-50 text-red-800 border-red-300",
}

const PRA_STATUS_LABEL: Record<string, string> = {
  pending:   "PRA Pending",
  submitted: "PRA Submitted",
  failed:    "PRA Failed",
}

const ZATCA_STATUS_TONE: Record<string, string> = {
  pending:   "bg-amber-50 text-amber-800 border-amber-300",
  submitted: "bg-blue-50 text-blue-800 border-blue-300",
  cleared:   "bg-emerald-50 text-emerald-800 border-emerald-300",
  reported:  "bg-emerald-50 text-emerald-800 border-emerald-300",
  rejected:  "bg-red-50 text-red-800 border-red-300",
  error:     "bg-red-50 text-red-800 border-red-300",
}

const ZATCA_STATUS_LABEL: Record<string, string> = {
  pending:   "ZATCA Pending",
  submitted: "ZATCA Submitted",
  cleared:   "ZATCA Cleared",
  reported:  "ZATCA Reported",
  rejected:  "ZATCA Rejected",
  error:     "ZATCA Error",
}

const PEPPOL_STATUS_TONE: Record<string, string> = {
  pending:   "bg-amber-50 text-amber-800 border-amber-300",
  submitted: "bg-blue-50 text-blue-800 border-blue-300",
  accepted:  "bg-emerald-50 text-emerald-800 border-emerald-300",
  rejected:  "bg-red-50 text-red-800 border-red-300",
  error:     "bg-red-50 text-red-800 border-red-300",
}

const PEPPOL_STATUS_LABEL: Record<string, string> = {
  pending:   "Peppol Pending",
  submitted: "Peppol Submitted",
  accepted:  "Peppol Accepted",
  rejected:  "Peppol Rejected",
  error:     "Peppol Error",
}

export default function InvoiceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { confirm, toast } = useMessages()
  const { t } = useTranslation()

  const fmt = useFmt()
  const { settings } = useSettings()
  const baseCurrency = settings.currency || "USD"
  const { isPortal } = usePRAPortal()
  const { id } = use(params)
  const [inv, setInv]       = useState<Invoice | null>(null)
  const [error, setError]   = useState<string | null>(null)
  const [busy, setBusy]     = useState(false)
  const [praRetrying, setPraRetrying] = useState(false)
  const [uaeSubmitting, setUaeSubmitting] = useState(false)
  const [uaeUuid, setUaeUuid] = useState<string | null>(null)
  const [uaeMsg, setUaeMsg] = useState<string | null>(null)
  const [zatcaSubmitting, setZatcaSubmitting] = useState(false)
  const [peppolSubmitting, setPeppolSubmitting] = useState(false)
  const [peppolExporting, setPeppolExporting] = useState(false)
  const { installedModules } = useModules()
  const uaeInstalled = installedModules.has("uae_vat")
  const zatcaInstalled = installedModules.has("sa_zatca")
  const peppolInstalled = installedModules.has("eu_peppol")
  const [selectedAtt, setSelectedAtt] = useState<AttachmentT | null>(null)
  const [history, setHistory] = useState<AuditEntry[]>([])
  const [disputes, setDisputes] = useState<PortalDispute[]>([])
  const [hasApprovalWorkflow, setHasApprovalWorkflow] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  useBreadcrumb(inv ? inv.number : undefined)

  const load = () =>
    apiFetch<Invoice>(`/api/invoices/${id}`)
      .then(setInv)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))

  const loadHistory = () =>
    apiFetch<{ items: AuditEntry[] }>(`/api/audit-log?entity_type=invoice&entity_id=${id}&limit=50`)
      .then(data => setHistory(data.items.filter(r => r.action === "UPDATE")))
      .catch(() => {/* non-critical; silently ignore */})

  const loadDisputes = () =>
    apiFetch<PortalDispute[]>(`/api/invoices/${id}/disputes`)
      .then(setDisputes)
      .catch(() => setDisputes([]))

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); loadHistory(); loadDisputes() }, [id])

  useEffect(() => {
    apiFetch<{ is_active?: boolean }[]>(`/api/approvals/workflows?document_type=invoice`)
      .then((rows) => setHasApprovalWorkflow(rows.some((w) => w.is_active !== false)))
      .catch(() => setHasApprovalWorkflow(false))
  }, [])

  const submitForApproval = async () => {
    if (!inv) return
    setBusy(true); setError(null)
    try {
      const res = await apiFetch<{
        ok: boolean; submitted: boolean; message?: string; approval_status?: string
      }>(`/api/invoices/${inv.id}/submit-for-approval`, { method: "POST" })
      if (!res.submitted) {
        toast(res.message || "No approval workflow configured", "info")
      } else {
        toast("Submitted for approval", "success")
        setInv((prev) => prev ? { ...prev, approval_status: res.approval_status || "pending" } : prev)
      }
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed")
    } finally {
      setBusy(false)
    }
  }

  const voidInvoice = async () => {
    const ok = await confirm({
      title: `Void invoice ${inv?.number}?`,
      message: "This cannot be undone and removes it from reports.",
      confirmLabel: "Void",
      danger: true,
    })
    if (!ok) return
    setBusy(true); setError(null)
    try {
      await apiFetch(`/api/invoices/${id}/status?status=void`, { method: "PATCH" })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to void invoice")
    } finally {
      setBusy(false)
    }
  }

  const markSent = async () => {
    const ok = await confirm({
      title: `Mark invoice ${inv?.number} as Sent?`,
      message: "This may send an email notification to the customer.",
      confirmLabel: "Mark sent",
    })
    if (!ok) return
    setBusy(true); setError(null)
    try {
      await apiFetch(`/api/invoices/${id}/status?status=sent`, { method: "PATCH" })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to mark as sent")
    } finally {
      setBusy(false)
    }
  }

  const reverse = async () => {
    if (!inv?.transaction_id) {
      setError("This invoice has no posted transaction to reverse.")
      return
    }
    const ok = await confirm({
      title: `Reverse invoice ${inv.number}?`,
      message: "A new equal-and-opposite JV will be posted today.",
      confirmLabel: "Reverse",
      danger: true,
    })
    if (!ok) return
    setBusy(true)
    setError(null)
    try {
      await apiFetch(`/api/transactions/${inv.transaction_id}/reverse`, { method: "POST" })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reverse failed")
    } finally {
      setBusy(false)
    }
  }

  if (error && !inv) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!inv)           return <p className="p-4 text-[var(--text-primary)]/60 text-sm">Loading invoice…</p>

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div className="flex items-center gap-2">
          {(inv.status === "draft" || inv.status === "sent" || inv.status === "posted" || inv.status === "overdue") && (
            <Link
              href={`/invoices/${inv.id}/edit`}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--primary)]/50 text-[var(--primary)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)]"
            >
              <Pencil className="w-4 h-4" /> Edit
            </Link>
          )}
          {(inv.status === "paid" || inv.status === "partial") && (
            <span
              title="Unallocate payments to edit."
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--border)] text-[var(--text-primary)]/30 rounded-lg text-sm font-bold cursor-not-allowed"
            >
              <Pencil className="w-4 h-4" /> Edit
            </span>
          )}
          {inv.status === "draft" && (
            <button
              onClick={markSent}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--primary)]/50 text-[var(--primary)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              <Send className="w-4 h-4" /> Mark as Sent
            </button>
          )}
          <DocumentActions
            onPrint={() => { window.location.href = `/invoices/${inv.id}/print` }}
            onSavePdf={async () => {
              setPdfBusy(true)
              try {
                await downloadPdf(`/api/invoices/${inv.id}/pdf`, `${inv.number}.pdf`)
              } catch (e) {
                toast((e as Error).message || "PDF generation failed", "error")
              } finally {
                setPdfBusy(false)
              }
            }}
            pdfBusy={pdfBusy}
          />
          {isPortal && inv.pra_fiscal_number && (
            <Link
              href={`/invoices/${inv.id}/receipt`}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] text-[var(--text-primary)]/70"
            >
              <Printer className="w-4 h-4" /> Print Receipt
            </Link>
          )}
          {inv.status !== "paid" && (
            <button
              onClick={async () => {
                try {
                  const res = await apiFetch<{ payment_link_url: string }>(
                    `/api/invoices/${inv.id}/payment-link`, { method: "POST" }
                  )
                  window.open(res.payment_link_url, "_blank")
                } catch (e) {
                  toast((e as Error).message, "error")
                }
              }}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--primary)]/50 text-[var(--primary)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)]"
            >
              <LinkIcon className="w-4 h-4" /> Payment Link
            </button>
          )}
          {hasApprovalWorkflow && !["pending", "approved"].includes(inv.approval_status || "")
            && !["void", "voided", "reversed", "paid"].includes(inv.status) && (
            <button
              onClick={submitForApproval}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--primary)]/50 text-[var(--primary)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" /> Submit for approval
            </button>
          )}
          {(inv.status === "draft" || inv.status === "sent") && (
            <button
              onClick={voidInvoice}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-red-50 hover:text-red-700 hover:border-red-200 disabled:opacity-50"
            >
              <Ban className="w-4 h-4" />{t('status.void', 'Void')}</button>
          )}
          {inv.transaction_id && inv.status !== "reversed" && (
            <button
              onClick={reverse}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
            >
              <RotateCcw className="w-4 h-4" /> {busy ? "Reversing…" : "Reverse"}
            </button>
          )}
        </div>
      </div>

      {/* Header */}
      <header className="bg-white border border-[var(--border)] rounded-xl p-5 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <FileSignature className="w-7 h-7 text-[var(--primary)] shrink-0 mt-1" />
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Invoice {inv.number}</h1>
            <p className="text-sm text-[var(--text-primary)]/60">
              Issued {inv.issue_date} · Due {inv.due_date}
              {inv.currency && inv.currency !== baseCurrency && (
                <> · {inv.currency} @ {Number(inv.carrying_rate ?? inv.exchange_rate)} · {baseCurrency} {fmt(Number(inv.total) * Number(inv.carrying_rate ?? inv.exchange_rate || 1))}</>
              )}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <StatusBadge status={inv.status} />
          {inv.approval_status && (
            <span className="inline-block border rounded-full px-2 py-0.5 text-[10px] font-semibold border-[var(--border)] text-[var(--text-primary)]/70">
              Approval: {inv.approval_status}
            </span>
          )}
          {inv.pra_status && inv.pra_status !== "not_required" && (
            <div className="flex items-center gap-1.5">
              <span className={`inline-block border rounded-full px-2 py-0.5 text-[10px] font-semibold ${PRA_STATUS_TONE[inv.pra_status] ?? ""}`}>
                {PRA_STATUS_LABEL[inv.pra_status] ?? inv.pra_status}
              </span>
              {inv.pra_status === "failed" && (
                <button
                  onClick={async () => {
                    setPraRetrying(true)
                    try {
                      const r = await apiFetch<{ success: boolean; pra_fiscal_number?: string; pra_status?: string }>(
                        `/api/pra/invoices/${inv.id}/submit`, { method: "POST" }
                      )
                      setInv(prev => prev ? { ...prev, pra_status: r.pra_status ?? prev.pra_status, pra_fiscal_number: r.pra_fiscal_number ?? prev.pra_fiscal_number } : prev)
                    } catch { /* silent — status badge already shows failed */ }
                    finally { setPraRetrying(false) }
                  }}
                  disabled={praRetrying}
                  className="text-[10px] text-red-700 hover:underline disabled:opacity-50"
                >
                  {praRetrying ? "Retrying…" : "Retry"}
                </button>
              )}
            </div>
          )}
          {inv.pra_fiscal_number && (
            <div className="text-[10px] text-[var(--text-primary)]/50 font-mono">FIN: {inv.pra_fiscal_number}</div>
          )}
          {uaeInstalled && (
            <div className="flex flex-col gap-1">
              <button
                type="button"
                onClick={async () => {
                  setUaeSubmitting(true)
                  setUaeMsg(null)
                  try {
                    const r = await apiFetch<{ success: boolean; uuid?: string; error_message?: string }>(
                      `/api/uae/invoices/${inv.id}/submit`,
                      { method: "POST" },
                    )
                    if (r.success && r.uuid) {
                      setUaeUuid(r.uuid)
                      setUaeMsg(null)
                    } else {
                      setUaeMsg(r.error_message || "Submit failed")
                    }
                  } catch (e: unknown) {
                    setUaeMsg(String((e as Error).message ?? e))
                  } finally {
                    setUaeSubmitting(false)
                  }
                }}
                disabled={uaeSubmitting}
                className="text-[10px] font-semibold text-[var(--text-link)] hover:underline disabled:opacity-50 text-left"
              >
                {uaeSubmitting ? "Submitting…" : uaeUuid ? "Re-submit to FTA" : "Submit to FTA (UAE)"}
              </button>
              {uaeUuid && (
                <div className="text-[10px] text-[var(--text-primary)]/50 font-mono">FTA: {uaeUuid}</div>
              )}
              {uaeMsg && <div className="text-[10px] text-red-600">{uaeMsg}</div>}
            </div>
          )}
          {zatcaInstalled && (
            <div className="flex flex-col items-end gap-1">
              {inv.zatca_status && (
                <span className={`inline-block border rounded-full px-2 py-0.5 text-[10px] font-semibold ${ZATCA_STATUS_TONE[inv.zatca_status] ?? ""}`}>
                  {ZATCA_STATUS_LABEL[inv.zatca_status] ?? inv.zatca_status}
                </span>
              )}
              <button
                type="button"
                onClick={async () => {
                  setZatcaSubmitting(true)
                  setError(null)
                  try {
                    const r = await apiFetch<{
                      success: boolean
                      zatca_status?: string
                      zatca_uuid?: string
                      zatca_hash?: string
                      zatca_qr?: string
                      error_message?: string
                    }>(`/api/zatca/invoices/${inv.id}/submit`, { method: "POST" })
                    setInv(prev => prev ? {
                      ...prev,
                      zatca_status: r.zatca_status ?? prev.zatca_status,
                      zatca_uuid: r.zatca_uuid ?? prev.zatca_uuid,
                      zatca_hash: r.zatca_hash ?? prev.zatca_hash,
                      zatca_qr: r.zatca_qr ?? prev.zatca_qr,
                    } : prev)
                    if (!r.success && r.error_message) {
                      setError(r.error_message)
                    }
                  } catch (e: unknown) {
                    setError(String((e as Error).message ?? e))
                  } finally {
                    setZatcaSubmitting(false)
                  }
                }}
                disabled={zatcaSubmitting}
                className="text-[10px] font-semibold text-[var(--text-link)] hover:underline disabled:opacity-50 text-left"
              >
                {zatcaSubmitting
                  ? "Submitting…"
                  : inv.zatca_status && ["cleared", "reported"].includes(inv.zatca_status)
                    ? "Re-submit to ZATCA"
                    : "Submit to ZATCA"}
              </button>
              {inv.zatca_uuid && (
                <div className="text-[10px] text-[var(--text-primary)]/50 font-mono">UUID: {inv.zatca_uuid}</div>
              )}
            </div>
          )}
          {peppolInstalled && (
            <div className="flex flex-col items-end gap-1">
              {inv.peppol_status && (
                <span className={`inline-block border rounded-full px-2 py-0.5 text-[10px] font-semibold ${PEPPOL_STATUS_TONE[inv.peppol_status] ?? ""}`}>
                  {PEPPOL_STATUS_LABEL[inv.peppol_status] ?? inv.peppol_status}
                </span>
              )}
              <button
                type="button"
                onClick={async () => {
                  setPeppolSubmitting(true)
                  setError(null)
                  try {
                    const r = await apiFetch<{
                      success: boolean
                      peppol_status?: string
                      peppol_document_id?: string
                      error_message?: string
                    }>(`/api/peppol/invoices/${inv.id}/submit`, { method: "POST" })
                    setInv(prev => prev ? {
                      ...prev,
                      peppol_status: r.peppol_status ?? prev.peppol_status,
                      peppol_document_id: r.peppol_document_id ?? prev.peppol_document_id,
                    } : prev)
                    if (!r.success && r.error_message) {
                      setError(r.error_message)
                    }
                  } catch (e: unknown) {
                    setError(String((e as Error).message ?? e))
                  } finally {
                    setPeppolSubmitting(false)
                  }
                }}
                disabled={peppolSubmitting}
                className="text-[10px] font-semibold text-[var(--text-link)] hover:underline disabled:opacity-50 text-left"
              >
                {peppolSubmitting
                  ? "Submitting…"
                  : inv.peppol_status === "accepted"
                    ? "Re-submit to Peppol"
                    : "Submit to Peppol"}
              </button>
              <button
                type="button"
                onClick={async () => {
                  setPeppolExporting(true)
                  setError(null)
                  try {
                    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
                    const url = `${apiBase}/api/peppol/invoices/${inv.id}/export`
                    const res = await fetch(url, {
                      headers: token ? { Authorization: `Bearer ${token}` } : {},
                    })
                    if (!res.ok) {
                      let detail = "UBL export failed"
                      try {
                        const body = await res.json()
                        if (body?.detail) detail = String(body.detail)
                      } catch { /* ignore */ }
                      throw new Error(detail)
                    }
                    const blob = await res.blob()
                    const a = document.createElement("a")
                    a.href = URL.createObjectURL(blob)
                    a.download = `${inv.number}-peppol.xml`
                    document.body.appendChild(a)
                    a.click()
                    a.remove()
                    URL.revokeObjectURL(a.href)
                  } catch (e: unknown) {
                    setError(networkErrorMessage(e, String((e as Error).message ?? e)))
                  } finally {
                    setPeppolExporting(false)
                  }
                }}
                disabled={peppolExporting}
                className="text-[10px] font-semibold text-[var(--text-link)] hover:underline disabled:opacity-50 text-left"
              >
                {peppolExporting ? "Exporting…" : "Export UBL XML"}
              </button>
              {inv.peppol_document_id && (
                <div className="text-[10px] text-[var(--text-primary)]/50 font-mono">Doc: {inv.peppol_document_id}</div>
              )}
            </div>
          )}
        </div>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2 rounded text-sm">{error}</div>
      )}

      {/* Parties + linked txn */}
      <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="bg-white border border-[var(--border)] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Bill To</div>
          {inv.customer_id ? (
            <Link href={`/customers/${inv.customer_id}/ledger`} className="font-semibold text-[var(--text-primary)] hover:text-[var(--primary)] hover:underline">
              {inv.customer_name ?? `#${inv.customer_id}`}
            </Link>
          ) : (
            <span className="font-semibold">{inv.customer_name ?? "—"}</span>
          )}
        </div>
        <div className="bg-white border border-[var(--border)] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Posted Voucher</div>
          {inv.transaction_id ? (
            <Link href={`/journal/${inv.transaction_id}`} className="font-mono text-sm text-[var(--primary)] hover:underline">
              View JV →
            </Link>
          ) : (
            <span className="text-sm text-[var(--text-primary)]/55">No voucher yet (draft)</span>
          )}
        </div>
      </section>

      {/* Lines */}
      <section className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
        {inv.allocation_audit?.method === "relative_ssp" && (
          <div className="px-4 py-2 bg-[var(--bg-page)] border-b border-[var(--border)] text-xs text-[var(--text-primary)]/70">
            Allocated by SSP (IFRS 15 relative standalone selling price) — transaction price {fmt(inv.allocation_audit.transaction_price)}
          </div>
        )}
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
            {inv.lines.map(ln => (
              <tr key={ln.id}>
                <td className="px-4 py-2">
                  {ln.product_id ? (
                    <Link href={`/products/${ln.product_id}/stock-card`} className="hover:text-[var(--primary)] hover:underline">
                      {ln.description}
                    </Link>
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

      {/* Notes */}
      {(inv.notes || inv.internal_memo) && (
        <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {inv.notes && (
            <div className="bg-white border border-[var(--border)] rounded-xl p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.notes', 'Notes')}</div>
              <p className="text-sm text-[var(--text-primary)]/80 whitespace-pre-wrap">{inv.notes}</p>
            </div>
          )}
          {inv.internal_memo && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-amber-700/70 mb-1">Internal Memo</div>
              <p className="text-sm text-amber-900/80 whitespace-pre-wrap">{inv.internal_memo}</p>
            </div>
          )}
        </section>
      )}

      {/* Totals */}
      <section className="flex justify-end">
        <div className="bg-white border border-[var(--border)] rounded-xl p-4 w-full sm:w-80 text-sm space-y-1">
          <Row label="Subtotal" value={fmt(inv.subtotal)} />
          {inv.gst_rate > 0 && <Row label={`GST (${inv.gst_rate}%)`} value={fmt(inv.gst_amount)} />}
          <div className="border-t border-[var(--text-primary)] pt-1.5 mt-1.5">
            <Row label={`Total (${inv.currency || baseCurrency})`} value={fmt(inv.total)} bold />
            {inv.currency && inv.currency !== baseCurrency && (
              <div className="flex justify-between text-xs text-[var(--text-muted)] mt-1">
                <span>≈ {baseCurrency}</span>
                <span className="font-mono">{fmt(Number(inv.total) * Number(inv.carrying_rate ?? inv.exchange_rate || 1))}</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Portal disputes */}
      {disputes.length > 0 && (
        <section className="bg-white border border-amber-200 rounded-xl overflow-hidden print:hidden">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 border-b border-amber-200">
            <MessageSquareWarning className="w-4 h-4 text-amber-700" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-amber-800/70">
              Portal disputes ({disputes.length})
            </span>
          </div>
          <div className="divide-y divide-amber-100">
            {disputes.map(d => (
              <div key={d.id} className="px-4 py-3 text-sm">
                <div className="flex items-center gap-2 text-xs text-[var(--text-primary)]/55 mb-1">
                  <span className="uppercase tracking-wide font-semibold text-amber-800">{d.status}</span>
                  <span>·</span>
                  <span>{fmtDate(d.created_at)}</span>
                </div>
                <p className="whitespace-pre-wrap text-[var(--text-primary)]/85">{d.body}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Attachments */}
      <section className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4 print:hidden">
        <AttachmentPanel parentType="invoice" parentId={inv.id} embedded onSelect={setSelectedAtt} />
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
