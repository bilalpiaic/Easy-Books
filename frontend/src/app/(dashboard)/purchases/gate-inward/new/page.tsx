"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, DoorOpen, Save, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { todayLocal } from "@/lib/utils"

interface PO { id: number; number: string; vendor_name: string | null; status: string }

interface POLine { id: number; description: string; qty: number; unit?: string; product_id?: number }

interface PODetail {
  id: number; number: string; vendor_name: string | null; status: string
  lines: POLine[]
  gi_coverage: Record<string, string>
}

interface GILineForm {
  po_line_id: number
  description: string
  unit?: string
  ordered: number
  received: number
  remaining: number
  qty_received: string
}

function NewGateInwardInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const poParam = searchParams.get("po")

  const [pos, setPos] = useState<PO[]>([])
  const [poId, setPoId] = useState(poParam ?? "")
  const [lines, setLines] = useState<GILineForm[]>([])
  const [loadingPo, setLoadingPo] = useState(false)

  const [gateDate, setGateDate] = useState(todayLocal())
  const [timeIn, setTimeIn] = useState("")
  const [vehicleNo, setVehicleNo] = useState("")
  const [challanNo, setChallanNo] = useState("")
  const [remarks, setRemarks] = useState("")

  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    Promise.all([
      apiFetch<{ items: PO[] }>("/api/purchase-orders?status=approved&limit=200"),
      apiFetch<{ items: PO[] }>("/api/purchase-orders?status=received&limit=200"),
    ])
      .then(([a, r]) => setPos([...a.items, ...r.items]))
      .catch(() => setPos([]))
  }, [])

  useEffect(() => {
    if (!poId) { setLines([]); return }
    setLoadingPo(true)
    apiFetch<PODetail>(`/api/purchase-orders/${poId}`)
      .then(d => {
        setLines(d.lines.map(l => {
          const received = parseFloat(d.gi_coverage?.[String(l.id)] ?? "0")
          const remaining = Math.max(0, l.qty - received)
          return {
            po_line_id: l.id,
            description: l.description,
            unit: l.unit,
            ordered: l.qty,
            received,
            remaining,
            qty_received: String(remaining),
          }
        }))
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load purchase order"))
      .finally(() => setLoadingPo(false))
  }, [poId])

  const updateLine = (i: number, value: string) => {
    setLines(prev => prev.map((l, idx) => idx !== i ? l : { ...l, qty_received: value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    if (!poId) { setError("Purchase order is required."); return }
    const submitLines = lines
      .filter(l => (parseFloat(l.qty_received) || 0) > 0)
      .map(l => ({ po_line_id: l.po_line_id, qty_received: parseFloat(l.qty_received) }))
    if (!submitLines.length) { setError("At least one line must have a received quantity."); return }

    setSaving(true)
    try {
      const gi = await apiFetch<{ id: number }>("/api/gate-inwards", {
        method: "POST",
        body: JSON.stringify({
          po_id: Number(poId),
          gate_date: gateDate,
          time_in: timeIn || null,
          vehicle_no: vehicleNo || null,
          challan_no: challanNo || null,
          remarks: remarks || null,
          lines: submitLines,
        }),
      })
      router.push(`/purchases/gate-inward/${gi.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed")
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <DoorOpen className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">New Gate Inward</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Record goods received at the gate.</p>
          </div>
        </div>
        <Link href="/purchases/gate-inward"
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft className="w-4 h-4" /> Back to Gate Inward
        </Link>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2.5 rounded-lg flex items-start gap-2 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Header fields */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Gate Details</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Purchase Order <span className="text-red-500">*</span></label>
            <select
              required
              value={poId}
              disabled={!!poParam}
              onChange={e => setPoId(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm disabled:opacity-60"
            >
              <option value="">— Select purchase order —</option>
              {pos.map(p => (
                <option key={p.id} value={p.id}>{p.number} — {p.vendor_name || "—"}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Gate Date <span className="text-red-500">*</span></label>
            <input
              type="date"
              required
              value={gateDate}
              onChange={e => setGateDate(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Time In</label>
            <input
              type="time"
              value={timeIn}
              onChange={e => setTimeIn(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Vehicle No.</label>
            <input
              type="text"
              value={vehicleNo}
              onChange={e => setVehicleNo(e.target.value)}
              placeholder="e.g. LEA-1234"
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Challan No.</label>
            <input
              type="text"
              value={challanNo}
              onChange={e => setChallanNo(e.target.value)}
              placeholder="Vendor challan / bilty #"
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
            />
          </div>
        </div>
      </section>

      {/* Lines */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]/50">Items</h2>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
                <th className="text-left pb-2 pr-2 min-w-[220px]">Description</th>
                <th className="text-right pb-2 pr-2 w-24">Ordered</th>
                <th className="text-right pb-2 pr-2 w-28">Already Received</th>
                <th className="text-right pb-2 pr-2 w-28">Receiving Now</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {lines.map((line, idx) => (
                <tr key={line.po_line_id}>
                  <td className="py-1.5 pr-2 text-[var(--text-primary)]">{line.description}</td>
                  <td className="py-1.5 pr-2 text-right text-[var(--text-muted)]">
                    {line.ordered}{line.unit ? ` ${line.unit}` : ""}
                  </td>
                  <td className="py-1.5 pr-2 text-right text-[var(--text-muted)]">
                    {line.received}{line.unit ? ` ${line.unit}` : ""}
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      type="number"
                      min="0"
                      max={line.remaining}
                      step="any"
                      value={line.qty_received}
                      disabled={line.remaining <= 0}
                      onChange={e => updateLine(idx, e.target.value)}
                      className="w-full px-2 py-1.5 border border-[var(--border)] rounded-md text-xs text-right font-mono focus:ring-2 focus:ring-[var(--primary)] outline-none disabled:opacity-50"
                    />
                  </td>
                </tr>
              ))}
              {lines.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-[var(--text-muted)]">
                    {loadingPo ? "Loading…" : "Select a purchase order to load its lines"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Remarks */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl p-5">
        <label className="block text-sm font-semibold text-[var(--text-primary)] mb-1.5">Remarks</label>
        <textarea
          value={remarks}
          onChange={e => setRemarks(e.target.value)}
          rows={2}
          placeholder="Additional context…"
          className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm resize-none"
        />
      </section>

      {/* Actions */}
      <div className="flex gap-3 justify-end">
        <button
          type="button"
          onClick={() => router.back()}
          className="px-5 py-2.5 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg font-semibold hover:bg-[var(--bg-page)] transition-colors text-sm"
        >Cancel</button>
        <button
          type="submit"
          disabled={saving}
          className="px-5 py-2.5 bg-[var(--text-primary)] text-white rounded-lg font-semibold flex items-center gap-2 hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50 text-sm"
        >
          <Save className="w-4 h-4" />
          {saving ? "Saving…" : "Save Gate Inward"}
        </button>
      </div>
    </form>
  )
}

export default function NewGateInwardPage() {
  return (
    <Suspense fallback={null}>
      <NewGateInwardInner />
    </Suspense>
  )
}
