"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Cpu, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import KpiCard from "@/components/dashboard/KpiCard"
import StatusBadge from "@/components/StatusBadge"

type EventType = {
  key: string
  label: string
  module: string
  auto_apply: boolean
  gl: boolean
}

type Device = {
  id: number
  code: string
  name: string
  protocol: string
  event_type: string
  binding: Record<string, unknown>
  auto_apply: boolean | null
  is_active: boolean
  last_seen_at: string | null
  last_error: string | null
}

type EventRow = {
  id: number
  machine_code: string
  event_type: string
  status: string
  received_at: string | null
  result_number: string | null
  result_doc_type: string | null
  error_message: string | null
  replayed?: boolean
}

type Summary = {
  devices: number
  pending: number
  applied_today: number
  event_types: EventType[]
}

type EventsPage = { total: number; items: EventRow[] }

const PROTOCOLS = ["http_gateway", "modbus_tcp", "opcua", "mqtt", "s7"] as const

const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm bg-[var(--bg-card)]"

export default function ShopFloorPage() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [devices, setDevices] = useState<Device[]>([])
  const [events, setEvents] = useState<EventRow[]>([])
  const [eventTypes, setEventTypes] = useState<EventType[]>([])
  const [err, setErr] = useState("")
  const [showDevice, setShowDevice] = useState(false)
  const [showReading, setShowReading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deviceForm, setDeviceForm] = useState({
    code: "", name: "", protocol: "http_gateway", event_type: "weaving.production",
    binding: '{"contract_id": null}', auto_apply: "",
  })
  const [readingForm, setReadingForm] = useState({
    machine_code: "", event_type: "weaving.production",
    idempotency_key: "", readings: '{\n  "grey_meters": 100\n}',
  })

  const load = useCallback(() => {
    apiFetch<Summary>("/api/plc/summary").then(setSummary).catch(() => setSummary(null))
    apiFetch<Device[]>("/api/plc/devices").then(d => setDevices(Array.isArray(d) ? d : [])).catch(() => setDevices([]))
    apiFetch<EventsPage>("/api/plc/events?limit=50").then(d => setEvents(d.items || [])).catch(() => setEvents([]))
    apiFetch<EventType[]>("/api/plc/event-types").then(d => setEventTypes(Array.isArray(d) ? d : [])).catch(() => setEventTypes([]))
  }, [])

  useEffect(() => { load() }, [load])

  async function saveDevice(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      let binding: Record<string, unknown> = {}
      if (deviceForm.binding.trim()) binding = JSON.parse(deviceForm.binding)
      await apiFetch("/api/plc/devices", {
        method: "POST",
        body: JSON.stringify({
          code: deviceForm.code,
          name: deviceForm.name || deviceForm.code,
          protocol: deviceForm.protocol,
          event_type: deviceForm.event_type,
          binding,
          auto_apply: deviceForm.auto_apply === "" ? null : deviceForm.auto_apply === "true",
        }),
      })
      setShowDevice(false)
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Could not save device")
    } finally {
      setSaving(false)
    }
  }

  async function postReading(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      const readings = JSON.parse(readingForm.readings)
      await apiFetch("/api/plc/ingest", {
        method: "POST",
        body: JSON.stringify({
          idempotency_key: readingForm.idempotency_key || `${readingForm.machine_code}-${Date.now()}`,
          machine_code: readingForm.machine_code,
          event_type: readingForm.event_type,
          readings,
        }),
      })
      setShowReading(false)
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Ingest failed")
    } finally {
      setSaving(false)
    }
  }

  async function act(id: number, action: "apply" | "reject") {
    setErr("")
    try {
      await apiFetch(`/api/plc/events/${id}/${action}`, {
        method: "POST",
        body: action === "reject" ? JSON.stringify({ reason: "Rejected from PLC Feed" }) : undefined,
      })
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Action failed")
    }
  }

  return (
    <div className="p-4 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">PLC Feed</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Auto-record mill production from machinery. A shop-floor gateway reads the PLC and POSTs JSON —
          Easy-Books never opens Modbus or OPC-UA itself. Map machine codes here, then point the gateway at{" "}
          <code className="text-xs">POST /api/plc/ingest</code> with an{" "}
          <Link href="/settings" className="text-[var(--primary)]">API key</Link>.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <KpiCard title="Machines mapped" value={summary ? String(summary.devices) : null} tone="blue" icon={Cpu} />
        <KpiCard title="Waiting to apply" value={summary ? String(summary.pending) : null} tone="amber" />
        <KpiCard title="Applied today" value={summary ? String(summary.applied_today) : null} tone="green" />
      </div>

      {err && <p className="text-sm text-red-600 print:hidden">{err}</p>}

      <div className="flex gap-2 print:hidden">
        <button onClick={() => { setShowDevice(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> Map machine
        </button>
        <button onClick={() => { setShowReading(true); setErr("") }}
          className="px-3 py-2 rounded-xl border border-[var(--border)] text-sm">
          Simulate reading
        </button>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] overflow-hidden">
        <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Machines</div>
        <div className="table-freeze">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-muted)]">
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Event</th>
                <th className="px-3 py-2">Protocol</th>
                <th className="px-3 py-2">Auto-apply</th>
                <th className="px-3 py-2">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {devices.map(d => (
                <tr key={d.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2 whitespace-nowrap font-medium">{d.code}</td>
                  <td className="px-3 py-2">{d.name}</td>
                  <td className="px-3 py-2">{d.event_type}</td>
                  <td className="px-3 py-2">{d.protocol}</td>
                  <td className="px-3 py-2">{d.auto_apply === null ? "default" : d.auto_apply ? "yes" : "queue"}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-[var(--text-muted)]">
                    {d.last_seen_at ? fmtDate(d.last_seen_at) : "—"}
                    {d.last_error && <span className="block text-red-600 text-xs">{d.last_error}</span>}
                  </td>
                </tr>
              ))}
              {devices.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">No machines mapped yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] overflow-hidden">
        <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Readings</div>
        <div className="table-freeze">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-muted)]">
                <th className="px-3 py-2">When</th>
                <th className="px-3 py-2">Machine</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Document</th>
                <th className="px-3 py-2 print:hidden"></th>
              </tr>
            </thead>
            <tbody>
              {events.map(e => (
                <tr key={e.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2 whitespace-nowrap">{e.received_at ? fmtDate(e.received_at) : "—"}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{e.machine_code}</td>
                  <td className="px-3 py-2">{e.event_type}</td>
                  <td className="px-3 py-2"><StatusBadge status={e.status} /></td>
                  <td className="px-3 py-2">
                    {e.result_number || e.error_message || "—"}
                  </td>
                  <td className="px-3 py-2 print:hidden">
                    {(e.status === "received" || e.status === "error") && (
                      <div className="flex gap-2">
                        <button onClick={() => act(e.id, "apply")} className="text-xs text-[var(--primary)]">Apply</button>
                        <button onClick={() => act(e.id, "reject")} className="text-xs text-[var(--text-muted)]">Reject</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">No readings yet — simulate one or point a gateway here</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-xs text-[var(--text-muted)] space-y-1">
        <p>
          Weaving production and weighbridge weighs auto-write mill documents (no GL).
          Spinning stages wait for Apply because they post inventory/WIP. See the mill PLC note in the user guide.
        </p>
      </div>

      {showDevice && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={saveDevice} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">Map a machine</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-[var(--text-muted)]">Machine code *</label>
                <input required value={deviceForm.code} onChange={e => setDeviceForm(f => ({ ...f, code: e.target.value }))} className={input} placeholder="L-01" />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Name</label>
                <input value={deviceForm.name} onChange={e => setDeviceForm(f => ({ ...f, name: e.target.value }))} className={input} placeholder="Airjet 1" />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Event type</label>
                <select value={deviceForm.event_type} onChange={e => setDeviceForm(f => ({ ...f, event_type: e.target.value }))} className={input}>
                  {(eventTypes.length ? eventTypes : [{ key: "weaving.production", label: "Loom production" }]).map(t => (
                    <option key={t.key} value={t.key}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">PLC protocol (gateway-side)</label>
                <select value={deviceForm.protocol} onChange={e => setDeviceForm(f => ({ ...f, protocol: e.target.value }))} className={input}>
                  {PROTOCOLS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Binding JSON (contract_id, spin_lot_id, …)</label>
                <textarea rows={4} value={deviceForm.binding} onChange={e => setDeviceForm(f => ({ ...f, binding: e.target.value }))} className={input + " font-mono text-xs"} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowDevice(false)} className="px-3 py-2 text-sm rounded-lg border border-[var(--border)]">Cancel</button>
              <button type="submit" disabled={saving} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50">{saving ? "Saving…" : "Save"}</button>
            </div>
          </form>
        </div>
      )}

      {showReading && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={postReading} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">Simulate a PLC reading</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-[var(--text-muted)]">Machine code *</label>
                <input required value={readingForm.machine_code} onChange={e => setReadingForm(f => ({ ...f, machine_code: e.target.value }))} className={input} placeholder="L-01" />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Event type</label>
                <select value={readingForm.event_type} onChange={e => setReadingForm(f => ({ ...f, event_type: e.target.value }))} className={input}>
                  {(eventTypes.length ? eventTypes : [{ key: "weaving.production", label: "Loom production" }]).map(t => (
                    <option key={t.key} value={t.key}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Readings JSON</label>
                <textarea rows={6} value={readingForm.readings} onChange={e => setReadingForm(f => ({ ...f, readings: e.target.value }))} className={input + " font-mono text-xs"} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowReading(false)} className="px-3 py-2 text-sm rounded-lg border border-[var(--border)]">Cancel</button>
              <button type="submit" disabled={saving} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50">{saving ? "Sending…" : "Ingest"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
