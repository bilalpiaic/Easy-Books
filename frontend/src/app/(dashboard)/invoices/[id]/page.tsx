"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { Printer, RotateCcw, FileSignature, Pencil, ChevronRight, Download, Link as LinkIcon, History } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { getAuthHeader } from "@/lib/auth"
import { useFmt } from "@/context/SettingsContext"
import AttachmentPanel, { AttachmentPreviewPane, type Attachment as AttachmentT } from "@/components/AttachmentPanel"

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
  status: string
  transaction_id: number | null
  lines: InvoiceLine[]
}

const STATUS_TONE: Record<string, string> = {
  draft:    "bg-slate-100 text-slate-800 border-slate-300",
  posted:   "bg-blue-100 text-blue-900 border-blue-300",
  partial:  "bg-amber-100 text-amber-900 border-amber-300",
  paid:     "bg-emerald-100 text-emerald-900 border-emerald-300",
  overdue:  "bg-red-100 text-red-900 border-red-300",
  reversed: "bg-gray-100 text-gray-600 border-gray-300",
}

export default function InvoiceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const fmt = useFmt()
  const { id } = use(params)
  const [inv, setInv]       = useState<Invoice | null>(null)
  const [error, setError]   = useState<string | null>(null)
  const [busy, setBusy]     = useState(false)
  const [selectedAtt, setSelectedAtt] = useState<AttachmentT | null>(null)
  const [history, setHistory] = useState<AuditEntry[]>([])

  const load = () =>
    apiFetch<Invoice>(`/api/invoices/${id}`)
      .then(setInv)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))

  const loadHistory = () =>
    apiFetch<{ items: AuditEntry[] }>(`/api/audit-log?entity_type=invoice&entity_id=${id}&limit=50`)
      .then(data => setHistory(data.items.filter(r => r.action === "UPDATE")))
      .catch(() => {/* non-critical; silently ignore */})

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); loadHistory() }, [id])

  const reverse = async () => {
    if (!inv?.transaction_id) {
      setError("This invoice has no posted transaction to reverse.")
      return
    }
    if (!window.confirm(`Reverse invoice ${inv.number}? A new equal-and-opposite JV will be posted today.`)) return
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
  if (!inv)           return <p className="p-4 text-[#1a1814]/60 text-sm">Loading invoice…</p>

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-black/40">
        <Link href="/invoices" className="hover:text-black/70 transition-colors">Invoices</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-black/60">{inv.number}</span>
      </nav>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div className="flex items-center gap-2">
          {(inv.status === "draft" || inv.status === "sent" || inv.status === "posted" || inv.status === "overdue") && (
            <Link
              href={`/invoices?edit=${inv.id}`}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#b8943f]/50 text-[#b8943f] rounded-lg text-sm font-bold hover:bg-[#faf6ec]"
            >
              <Pencil className="w-4 h-4" /> Edit
            </Link>
          )}
          {(inv.status === "paid" || inv.status === "partial") && (
            <span
              title="Unallocate payments to edit."
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] text-[#1a1814]/30 rounded-lg text-sm font-bold cursor-not-allowed"
            >
              <Pencil className="w-4 h-4" /> Edit
            </span>
          )}
          <Link
            href={`/invoices/${inv.id}/print`}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee]"
          >
            <Printer className="w-4 h-4" /> Print
          </Link>
          <button
            onClick={async () => {
              const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
              const res = await fetch(`${apiUrl}/api/invoices/${inv.id}/pdf`, {
                headers: getAuthHeader() as HeadersInit,
              })
              if (!res.ok) return alert("PDF generation failed")
              const blob = await res.blob()
              const url = URL.createObjectURL(blob)
              const a = document.createElement("a")
              a.href = url
              a.download = `${inv.number}.pdf`
              a.click()
              URL.revokeObjectURL(url)
            }}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee]"
          >
            <Download className="w-4 h-4" /> PDF
          </button>
          {inv.status !== "paid" && (
            <button
              onClick={async () => {
                try {
                  const res = await apiFetch<{ payment_link_url: string }>(
                    `/api/invoices/${inv.id}/payment-link`, { method: "POST" }
                  )
                  window.open(res.payment_link_url, "_blank")
                } catch (e) {
                  alert((e as Error).message)
                }
              }}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#b8943f]/50 text-[#b8943f] rounded-lg text-sm font-bold hover:bg-[#faf6ec]"
            >
              <LinkIcon className="w-4 h-4" /> Payment Link
            </button>
          )}
          {inv.transaction_id && inv.status !== "reversed" && (
            <button
              onClick={reverse}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
            >
              <RotateCcw className="w-4 h-4" /> {busy ? "Reversing…" : "Reverse"}
            </button>
          )}
        </div>
      </div>

      {/* Header */}
      <header className="bg-white border border-[#ede9e2] rounded-xl p-5 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <FileSignature className="w-7 h-7 text-[#b8943f] shrink-0 mt-1" />
          <div className="min-w-0">
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Invoice {inv.number}</h1>
            <p className="text-sm text-[#1a1814]/60">
              Issued {inv.issue_date} · Due {inv.due_date}
              {inv.currency !== "USD" && <> · {inv.currency} @ {inv.exchange_rate}</>}
            </p>
          </div>
        </div>
        <span className={`inline-block border rounded-full px-3 py-1 text-xs font-semibold uppercase ${STATUS_TONE[inv.status] ?? STATUS_TONE.posted}`}>
          {inv.status}
        </span>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2 rounded text-sm">{error}</div>
      )}

      {/* Parties + linked txn */}
      <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="bg-white border border-[#ede9e2] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Bill To</div>
          {inv.customer_id ? (
            <Link href={`/customers/${inv.customer_id}/ledger`} className="font-semibold text-[#1a1814] hover:text-[#b8943f] hover:underline">
              {inv.customer_name ?? `#${inv.customer_id}`}
            </Link>
          ) : (
            <span className="font-semibold">{inv.customer_name ?? "—"}</span>
          )}
        </div>
        <div className="bg-white border border-[#ede9e2] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Posted Voucher</div>
          {inv.transaction_id ? (
            <Link href={`/journal/${inv.transaction_id}`} className="font-mono text-sm text-[#b8943f] hover:underline">
              View JV →
            </Link>
          ) : (
            <span className="text-sm text-[#1a1814]/55">No voucher yet (draft)</span>
          )}
        </div>
      </section>

      {/* Lines */}
      <section className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#faf6ec]">
            <tr>
              <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Description</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-24">Qty</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Rate</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {inv.lines.map(ln => (
              <tr key={ln.id}>
                <td className="px-4 py-2">
                  {ln.product_id ? (
                    <Link href={`/products/${ln.product_id}/stock-card`} className="hover:text-[#b8943f] hover:underline">
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
      </section>

      {/* Notes */}
      {(inv.notes || inv.internal_memo) && (
        <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {inv.notes && (
            <div className="bg-white border border-[#ede9e2] rounded-xl p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Notes</div>
              <p className="text-sm text-[#1a1814]/80 whitespace-pre-wrap">{inv.notes}</p>
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
        <div className="bg-white border border-[#ede9e2] rounded-xl p-4 w-full sm:w-80 text-sm space-y-1">
          <Row label="Subtotal" value={fmt(inv.subtotal)} />
          {inv.gst_rate > 0 && <Row label={`GST (${inv.gst_rate}%)`} value={fmt(inv.gst_amount)} />}
          <div className="border-t border-[#1a1814] pt-1.5 mt-1.5">
            <Row label="Total" value={fmt(inv.total)} bold />
          </div>
        </div>
      </section>

      {/* Attachments */}
      <section className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4 print:hidden">
        <AttachmentPanel parentType="invoice" parentId={inv.id} embedded onSelect={setSelectedAtt} />
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-hidden min-h-[60vh]">
          <AttachmentPreviewPane att={selectedAtt} />
        </div>
      </section>

      {/* Change History */}
      {history.length > 0 && (
        <section className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden print:hidden">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-[#faf6ec] border-b border-[#ede9e2]">
            <History className="w-4 h-4 text-[#b8943f]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Change History</span>
          </div>
          <div className="divide-y divide-[#ede9e2]">
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
                  <p className="text-[#1a1814]/65 text-xs mb-1">
                    Edited by <span className="font-semibold text-[#1a1814]">{entry.user_name}</span>
                    {" "}on {new Date(entry.timestamp).toLocaleString()}
                  </p>
                  {changedFields.length > 0 ? (
                    <table className="w-full text-xs mt-1">
                      <thead>
                        <tr>
                          <th className="text-left py-1 pr-3 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 w-32">Field</th>
                          <th className="text-left py-1 pr-3 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">Before</th>
                          <th className="text-left py-1 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">After</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#ede9e2]/60">
                        {changedFields.map(([field, val]) => (
                          <tr key={field}>
                            <td className="py-1 pr-3 font-medium text-[#1a1814]/70 capitalize">{field.replace(/_/g, " ")}</td>
                            <td className="py-1 pr-3 font-mono text-red-700/80">{String(val.before ?? "—")}</td>
                            <td className="py-1 font-mono text-emerald-700">{String(val.after ?? "—")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="text-xs text-[#1a1814]/40 italic">No header fields changed.</p>
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
      <span className={bold ? "font-bold" : "text-[#1a1814]/65"}>{label}</span>
      <span className={`font-mono ${bold ? "font-bold text-base" : ""}`}>{value}</span>
    </div>
  )
}
