"use client"

import { FormEvent, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import PrintHeader from "@/components/PrintHeader"
import StatusBadge from "@/components/StatusBadge"
import { fmtDate } from "@/lib/utils"
import { formatWeightTriple, type WeightTriple } from "@/lib/weavingUnits"

type Ticket = {
  id: number
  number: string
  ticket_date: string
  direction: string
  vehicle_no: string
  driver_name?: string | null
  party_type: string
  party_name?: string | null
  commodity?: string | null
  lot_ref?: string | null
  gross: WeightTriple
  tare: WeightTriple
  net: WeightTriple
  first_weigh_kind?: string | null
  first_weigh_at?: string | null
  second_weigh_at?: string | null
  status: string
  notes?: string | null
  invoice_id?: number | null
  po_id?: number | null
  gate_inward_id?: number | null
  sp_bale_receipt_id?: number | null
  cancel_reason?: string | null
}

export default function WeighbridgeTicketDetailPage() {
  const params = useParams<{ id: string }>()
  const [row, setRow] = useState<Ticket | null>(null)
  const [err, setErr] = useState("")
  const [kg, setKg] = useState("")
  const [kind, setKind] = useState("gross")
  const [reason, setReason] = useState("")
  const [invoiceId, setInvoiceId] = useState("")
  const [msg, setMsg] = useState("")

  function load() {
    apiFetch<Ticket>(`/api/weighbridge/tickets/${params.id}`)
      .then(t => {
        setRow(t)
        setInvoiceId(t.invoice_id ? String(t.invoice_id) : "")
        if (t.status === "draft") setKind("gross")
        else if (t.first_weigh_kind === "gross") setKind("tare")
        else if (t.first_weigh_kind === "tare") setKind("gross")
      })
      .catch(() => setErr("Ticket not found"))
  }

  useEffect(() => { load() }, [params.id])

  async function weigh(e: FormEvent) {
    e.preventDefault()
    setErr(""); setMsg("")
    try {
      const next = await apiFetch<Ticket>(`/api/weighbridge/tickets/${params.id}/weigh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, kg: Number(kg) }),
      })
      setRow(next)
      setKg("")
      setMsg(next.status === "completed" ? "Second weigh complete." : "First weigh recorded — vehicle on site.")
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Weigh failed")
    }
  }

  async function cancel(e: FormEvent) {
    e.preventDefault()
    setErr(""); setMsg("")
    try {
      const next = await apiFetch<Ticket>(`/api/weighbridge/tickets/${params.id}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      })
      setRow(next)
      setMsg("Ticket cancelled.")
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Cancel failed")
    }
  }

  async function copyGate() {
    setErr(""); setMsg("")
    try {
      const body: Record<string, unknown> = {}
      if (invoiceId) body.invoice_id = Number(invoiceId)
      const res = await apiFetch<{ gate_pass_no: string; invoice_number: string }>(
        `/api/weighbridge/tickets/${params.id}/copy-gate-pass`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
      )
      setMsg(`Copied ${res.gate_pass_no} onto invoice ${res.invoice_number}.`)
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Copy failed")
    }
  }

  if (!row && !err) return <div className="p-4 text-sm text-[var(--text-muted)]">Loading…</div>
  if (!row) return <div className="p-4 text-sm text-[var(--danger)]">{err}</div>

  const canWeigh = row.status === "draft" || row.status === "weighed_in"
  const canCancel = row.status === "draft" || row.status === "weighed_in"
  const canCopy = row.status === "completed" && row.direction === "inbound"

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-4">
      <PrintHeader title={`Weighbridge slip ${row.number}`} subtitle={fmtDate(row.ticket_date)} />

      <div className="flex items-start justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">{row.number}</h1>
          <p className="text-sm text-[var(--text-muted)]">{fmtDate(row.ticket_date)} · {row.vehicle_no}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={row.status} />
          <button onClick={() => window.print()} className="px-3 py-1.5 text-sm border border-[var(--border)] rounded-lg">Print slip</button>
        </div>
      </div>

      {err && <div className="print:hidden text-sm text-[var(--danger)]">{err}</div>}
      {msg && <div className="print:hidden text-sm text-[var(--success)]">{msg}</div>}

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 space-y-3 text-sm">
        <div className="grid grid-cols-2 gap-2">
          <div><span className="text-[var(--text-muted)]">Direction</span><div className="capitalize">{row.direction}</div></div>
          <div><span className="text-[var(--text-muted)]">Vehicle</span><div>{row.vehicle_no}</div></div>
          <div><span className="text-[var(--text-muted)]">Driver</span><div>{row.driver_name || "—"}</div></div>
          <div><span className="text-[var(--text-muted)]">Party</span><div>{row.party_name || row.party_type}</div></div>
          <div><span className="text-[var(--text-muted)]">Commodity</span><div>{row.commodity || "—"}</div></div>
          <div><span className="text-[var(--text-muted)]">Lot ref</span><div>{row.lot_ref || "—"}</div></div>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="py-1"> </th>
              <th className="py-1 text-right">Kg</th>
              <th className="py-1 text-right">Lbs</th>
              <th className="py-1 text-right">Bags</th>
            </tr>
          </thead>
          <tbody>
            {(["gross", "tare", "net"] as const).map(k => (
              <tr key={k} className="border-t border-[var(--border)]">
                <td className="py-1 capitalize">{k}</td>
                <td className="py-1 text-right">{row[k].kg.toLocaleString(undefined, { maximumFractionDigits: 3 })}</td>
                <td className="py-1 text-right">{row[k].lbs.toLocaleString(undefined, { maximumFractionDigits: 3 })}</td>
                <td className="py-1 text-right">{row[k].bags.toLocaleString(undefined, { maximumFractionDigits: 3 })}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-[var(--text-muted)]">Lbs = Kg × 2.2046226218 · Bags = Lbs / 100</p>
        {row.notes && <p>{row.notes}</p>}
        {row.cancel_reason && <p className="text-[var(--danger)]">Cancelled: {row.cancel_reason}</p>}
      </div>

      {canWeigh && (
        <form onSubmit={weigh} className="print:hidden rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 space-y-2">
          <h2 className="text-sm font-semibold">{row.status === "draft" ? "First weigh" : "Second weigh"}</h2>
          <div className="flex flex-wrap gap-2">
            <select className="px-2.5 py-1.5 text-sm border border-[var(--border)] rounded-lg"
              value={kind} onChange={e => setKind(e.target.value)}
              disabled={row.status === "weighed_in"}>
              <option value="gross">Gross</option>
              <option value="tare">Tare</option>
            </select>
            <input type="number" step="0.001" min="0.001" required value={kg} onChange={e => setKg(e.target.value)}
              placeholder="Kg" className="px-2.5 py-1.5 text-sm border border-[var(--border)] rounded-lg w-32" />
            <button type="submit" className="px-3 py-1.5 rounded-lg bg-[var(--primary)] text-white text-sm">Record weigh</button>
          </div>
        </form>
      )}

      {canCancel && (
        <form onSubmit={cancel} className="print:hidden rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 space-y-2">
          <h2 className="text-sm font-semibold">Cancel</h2>
          <div className="flex flex-wrap gap-2">
            <input required value={reason} onChange={e => setReason(e.target.value)} placeholder="Reason"
              className="px-2.5 py-1.5 text-sm border border-[var(--border)] rounded-lg flex-1 min-w-[12rem]" />
            <button type="submit" className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-sm">Cancel ticket</button>
          </div>
        </form>
      )}

      {canCopy && (
        <div className="print:hidden rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 space-y-2">
          <h2 className="text-sm font-semibold">Copy Gate pass onto invoice</h2>
          <p className="text-xs text-[var(--text-muted)]">Writes {row.number} to invoice custom field x.gate_pass_no. No GL change.</p>
          <div className="flex flex-wrap gap-2">
            <input type="number" value={invoiceId} onChange={e => setInvoiceId(e.target.value)} placeholder="Invoice id"
              className="px-2.5 py-1.5 text-sm border border-[var(--border)] rounded-lg w-40" />
            <button type="button" onClick={copyGate} className="px-3 py-1.5 rounded-lg bg-[var(--primary)] text-white text-sm">Copy Gate pass</button>
          </div>
        </div>
      )}

      <p className="print:hidden text-sm">
        <Link href="/weighbridge/tickets" className="text-[var(--primary)]">Back to tickets</Link>
        {" · "}
        <span className="text-[var(--text-muted)]">{formatWeightTriple(row.net)}</span>
      </p>
    </div>
  )
}
