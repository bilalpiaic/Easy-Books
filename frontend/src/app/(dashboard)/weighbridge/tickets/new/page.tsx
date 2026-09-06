"use client"

import { FormEvent, useState } from "react"
import { useRouter } from "next/navigation"
import { apiFetch } from "@/lib/api"

const today = () => new Date().toISOString().slice(0, 10)

export default function NewWeighbridgeTicketPage() {
  const router = useRouter()
  const [err, setErr] = useState("")
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    ticket_date: today(),
    direction: "inbound",
    vehicle_no: "",
    driver_name: "",
    party_type: "other",
    party_name: "",
    commodity: "",
    lot_ref: "",
    notes: "",
    invoice_id: "",
    po_id: "",
    gate_inward_id: "",
    sp_bale_receipt_id: "",
    first_weigh_kind: "",
    first_kg: "",
  })

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErr("")
    setSaving(true)
    try {
      const body: Record<string, unknown> = {
        ticket_date: form.ticket_date,
        direction: form.direction,
        vehicle_no: form.vehicle_no.trim(),
        driver_name: form.driver_name.trim() || null,
        party_type: form.party_type,
        party_name: form.party_name.trim() || null,
        commodity: form.commodity.trim() || null,
        lot_ref: form.lot_ref.trim() || null,
        notes: form.notes.trim() || null,
      }
      if (form.invoice_id) body.invoice_id = Number(form.invoice_id)
      if (form.po_id) body.po_id = Number(form.po_id)
      if (form.gate_inward_id) body.gate_inward_id = Number(form.gate_inward_id)
      if (form.sp_bale_receipt_id) body.sp_bale_receipt_id = Number(form.sp_bale_receipt_id)
      if (form.first_weigh_kind && form.first_kg) {
        body.first_weigh_kind = form.first_weigh_kind
        body.first_kg = Number(form.first_kg)
      }
      const created = await apiFetch<{ id: number }>("/api/weighbridge/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      router.push(`/weighbridge/tickets/${created.id}`)
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Could not save ticket")
    } finally {
      setSaving(false)
    }
  }

  const input = "px-2.5 py-1.5 text-sm border border-[var(--border)] rounded-lg w-full bg-[var(--bg-card)]"

  return (
    <form onSubmit={onSubmit} className="p-4 max-w-3xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">New weighbridge ticket</h1>
        <p className="text-sm text-[var(--text-muted)]">Record the vehicle. Optional first weigh on this screen.</p>
      </div>

      {err && <div className="text-sm text-[var(--danger)] bg-red-50 border border-red-200 rounded-lg px-3 py-2">{err}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">Date</span>
          <input type="date" required className={input} value={form.ticket_date} onChange={e => set("ticket_date", e.target.value)} />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">Direction</span>
          <select className={input} value={form.direction} onChange={e => set("direction", e.target.value)}>
            <option value="inbound">Inbound</option>
            <option value="outbound">Outbound</option>
          </select>
        </label>
        <label className="text-sm space-y-1 sm:col-span-2">
          <span className="text-[var(--text-muted)]">Vehicle no</span>
          <input required className={input} value={form.vehicle_no} onChange={e => set("vehicle_no", e.target.value)} />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">Driver</span>
          <input className={input} value={form.driver_name} onChange={e => set("driver_name", e.target.value)} />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">Party type</span>
          <select className={input} value={form.party_type} onChange={e => set("party_type", e.target.value)}>
            <option value="vendor">Vendor</option>
            <option value="customer">Customer</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label className="text-sm space-y-1 sm:col-span-2">
          <span className="text-[var(--text-muted)]">Party name</span>
          <input className={input} value={form.party_name} onChange={e => set("party_name", e.target.value)} placeholder="Vendor, customer, or walk-in" />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">Commodity</span>
          <input className={input} value={form.commodity} onChange={e => set("commodity", e.target.value)} />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">Lot ref</span>
          <input className={input} value={form.lot_ref} onChange={e => set("lot_ref", e.target.value)} />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">First weigh</span>
          <select className={input} value={form.first_weigh_kind} onChange={e => set("first_weigh_kind", e.target.value)}>
            <option value="">Later on the ticket</option>
            <option value="gross">Gross now</option>
            <option value="tare">Tare now</option>
          </select>
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">First kg</span>
          <input type="number" step="0.001" min="0" className={input} value={form.first_kg} onChange={e => set("first_kg", e.target.value)} disabled={!form.first_weigh_kind} />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">Invoice id (optional)</span>
          <input type="number" className={input} value={form.invoice_id} onChange={e => set("invoice_id", e.target.value)} />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">PO id (optional)</span>
          <input type="number" className={input} value={form.po_id} onChange={e => set("po_id", e.target.value)} />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">Gate inward id (optional)</span>
          <input type="number" className={input} value={form.gate_inward_id} onChange={e => set("gate_inward_id", e.target.value)} />
        </label>
        <label className="text-sm space-y-1">
          <span className="text-[var(--text-muted)]">Bale receipt id (optional)</span>
          <input type="number" className={input} value={form.sp_bale_receipt_id} onChange={e => set("sp_bale_receipt_id", e.target.value)} />
        </label>
        <label className="text-sm space-y-1 sm:col-span-2">
          <span className="text-[var(--text-muted)]">Notes</span>
          <textarea className={input} rows={2} value={form.notes} onChange={e => set("notes", e.target.value)} />
        </label>
      </div>

      <button type="submit" disabled={saving}
        className="px-4 py-2 rounded-xl bg-[var(--primary)] text-white text-sm disabled:opacity-60">
        {saving ? "Saving…" : "Save ticket"}
      </button>
    </form>
  )
}
