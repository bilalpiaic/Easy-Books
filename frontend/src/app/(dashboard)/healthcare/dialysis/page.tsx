"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import {
  ArrowLeft, Droplets, Play, CheckCircle2, XCircle, Wrench, Plus,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate, todayLocal } from "@/lib/utils"
import { StatusBadge } from "@/components/healthcare/primitives"

type Machine = {
  id: number
  code: string
  name: string
  status: string
  is_active: boolean
}

type Shift = {
  id: number
  code: string
  name: string
  start_time: string
  end_time: string
  sort_order: number
  is_active: boolean
}

type SessionInfo = {
  id: number
  session_number: string
  patient_id: number
  patient_name?: string | null
  patient_mr?: string | null
  doctor_name?: string | null
  machine_id: number
  shift_id: number
  session_date: string
  status: string
  fee: number | string
}

type Slot = {
  machine_id: number
  machine_code: string
  machine_status: string
  shift_id: number
  shift_code: string
  shift_name: string
  start_time: string
  end_time: string
  session: SessionInfo | null
}

type Schedule = {
  date: string
  unit: { id: number; name: string; open_time: string; close_time: string; shift_hours: number } | null
  machines: Machine[]
  shifts: Shift[]
  slots: Slot[]
  capacity: number
  usable_capacity: number
  booked: number
  available: number
  active_machines?: number
  usable_machines?: number
  active_shifts?: number
}

type Patient = { id: number; mr_number: string; name: string }
type Doctor = { id: number; name: string; specialization?: string | null }

const SESSION_COLORS: Record<string, string> = {
  scheduled: "bg-sky-50 border-sky-200 text-sky-900",
  in_progress: "bg-amber-50 border-amber-300 text-amber-900",
  completed: "bg-emerald-50 border-emerald-200 text-emerald-900",
  cancelled: "bg-neutral-100 border-neutral-200 text-neutral-500",
  no_show: "bg-rose-50 border-rose-200 text-rose-800",
}

export default function DialysisPage() {
  const [day, setDay] = useState(todayLocal())
  const [schedule, setSchedule] = useState<Schedule | null>(null)
  const [machines, setMachines] = useState<Machine[]>([])
  const [shifts, setShifts] = useState<Shift[]>([])
  const [patients, setPatients] = useState<Patient[]>([])
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState("")
  const [tab, setTab] = useState<"schedule" | "setup">("schedule")
  const [busy, setBusy] = useState(false)

  // Book modal
  const [bookSlot, setBookSlot] = useState<Slot | null>(null)
  const [bookPatientId, setBookPatientId] = useState("")
  const [bookDoctorId, setBookDoctorId] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    setMsg("")
    try {
      const [sched, mach, sh, pts, docs] = await Promise.all([
        apiFetch<Schedule>(`/api/healthcare/dialysis/schedule?date=${day}`),
        apiFetch<Machine[]>("/api/healthcare/dialysis/machines").catch(() => [] as Machine[]),
        apiFetch<Shift[]>("/api/healthcare/dialysis/shifts").catch(() => [] as Shift[]),
        apiFetch<Patient[] | { items: Patient[] }>("/api/healthcare/patients?limit=200").catch(() => [] as Patient[]),
        apiFetch<Doctor[]>("/api/healthcare/doctors").catch(() => [] as Doctor[]),
      ])
      setSchedule(sched)
      setMachines(mach ?? [])
      setShifts(sh ?? [])
      setPatients(Array.isArray(pts) ? pts : (pts as { items: Patient[] }).items ?? [])
      setDoctors(docs ?? [])
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Failed to load dialysis unit")
      setSchedule(null)
    } finally {
      setLoading(false)
    }
  }, [day])

  useEffect(() => { load() }, [load])

  const grid = useMemo(() => {
    if (!schedule) return { byMachine: new Map<number, Map<number, Slot>>() }
    const byMachine = new Map<number, Map<number, Slot>>()
    for (const slot of schedule.slots) {
      if (!byMachine.has(slot.machine_id)) byMachine.set(slot.machine_id, new Map())
      byMachine.get(slot.machine_id)!.set(slot.shift_id, slot)
    }
    return { byMachine }
  }, [schedule])

  async function ensureUnit() {
    setBusy(true)
    setMsg("")
    try {
      await apiFetch("/api/healthcare/dialysis/unit", {
        method: "POST",
        body: JSON.stringify({
          name: "Dialysis Treatment Unit",
          open_time: "08:00",
          close_time: "20:00",
          shift_hours: 4,
        }),
      })
      // Seed default 3 shifts + prompt user to add machines
      const unit = await apiFetch<{ id: number }>("/api/healthcare/dialysis/unit")
      const defaults = [
        { code: "A", name: "Morning", start_time: "08:00", end_time: "12:00", sort_order: 1 },
        { code: "B", name: "Afternoon", start_time: "12:00", end_time: "16:00", sort_order: 2 },
        { code: "C", name: "Evening", start_time: "16:00", end_time: "20:00", sort_order: 3 },
      ]
      for (const sh of defaults) {
        await apiFetch("/api/healthcare/dialysis/shifts", {
          method: "POST",
          body: JSON.stringify({ ...sh, unit_id: unit.id }),
        }).catch(() => null)
      }
      for (let i = 1; i <= 17; i++) {
        await apiFetch("/api/healthcare/dialysis/machines", {
          method: "POST",
          body: JSON.stringify({
            code: `DM-${String(i).padStart(2, "0")}`,
            name: `Dialysis Machine ${String(i).padStart(2, "0")}`,
            status: i >= 16 ? "maintenance" : "available",
            unit_id: unit.id,
          }),
        }).catch(() => null)
      }
      setMsg("Dialysis unit created with 17 machines and 3 shifts")
      await load()
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Failed to create unit")
    } finally {
      setBusy(false)
    }
  }

  async function bookSession(e: React.FormEvent) {
    e.preventDefault()
    if (!bookSlot || !bookPatientId) return
    setBusy(true)
    setMsg("")
    try {
      await apiFetch("/api/healthcare/dialysis/sessions", {
        method: "POST",
        body: JSON.stringify({
          patient_id: Number(bookPatientId),
          machine_id: bookSlot.machine_id,
          shift_id: bookSlot.shift_id,
          session_date: day,
          doctor_id: bookDoctorId ? Number(bookDoctorId) : undefined,
        }),
      })
      setBookSlot(null)
      setBookPatientId("")
      setBookDoctorId("")
      setMsg("Session booked")
      await load()
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "Booking failed")
    } finally {
      setBusy(false)
    }
  }

  async function act(sessionId: number, action: "start" | "complete" | "cancel") {
    setBusy(true)
    setMsg("")
    try {
      await apiFetch(`/api/healthcare/dialysis/sessions/${sessionId}/${action}`, { method: "PUT" })
      setMsg(`Session ${action === "cancel" ? "cancelled" : action + "ed"}`)
      await load()
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "Action failed")
    } finally {
      setBusy(false)
    }
  }

  async function setMachineStatus(id: number, status: string) {
    setBusy(true)
    try {
      await apiFetch(`/api/healthcare/dialysis/machines/${id}`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      })
      await load()
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "Update failed")
    } finally {
      setBusy(false)
    }
  }

  if (loading && !schedule) {
    return <div className="p-6 text-neutral-400">Loading dialysis unit…</div>
  }

  const unit = schedule?.unit
  const activeShifts = schedule?.shifts?.length ? schedule.shifts : shifts.filter(s => s.is_active)
  const activeMachines = schedule?.machines?.length ? schedule.machines : machines.filter(m => m.is_active)

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            href="/healthcare"
            className="inline-flex items-center gap-1.5 text-sm text-neutral-600 hover:text-rose-600 mb-1"
          >
            <ArrowLeft className="w-4 h-4" /> Healthcare
          </Link>
          <h1 className="text-2xl font-semibold text-neutral-900 flex items-center gap-2">
            <Droplets className="w-6 h-6 text-sky-600" />
            Dialysis Treatment Unit
          </h1>
          <p className="text-sm text-neutral-500 mt-0.5">
            {unit
              ? `${unit.name} · ${unit.open_time}–${unit.close_time} · ${unit.shift_hours}h shifts`
              : "No unit configured yet"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-neutral-200 overflow-hidden text-sm">
            <button
              onClick={() => setTab("schedule")}
              className={`px-3 py-1.5 ${tab === "schedule" ? "bg-rose-500 text-white" : "bg-white text-neutral-700"}`}
            >
              Schedule
            </button>
            <button
              onClick={() => setTab("setup")}
              className={`px-3 py-1.5 ${tab === "setup" ? "bg-rose-500 text-white" : "bg-white text-neutral-700"}`}
            >
              Setup
            </button>
          </div>
        </div>
      </div>

      {msg && (
        <div className={`text-sm p-3 rounded-lg ${
          msg.toLowerCase().includes("fail") || msg.toLowerCase().includes("full") || msg.toLowerCase().includes("already")
            ? "bg-amber-50 text-amber-800"
            : "bg-green-50 text-green-700"
        }`}>
          {msg}
        </div>
      )}

      {!unit && (
        <div className="bg-white border border-dashed border-neutral-300 rounded-xl p-8 text-center space-y-3">
          <p className="text-neutral-600 text-sm">
            Create the Dialysis Treatment Unit with 17 machines and 3×4-hour shifts (08:00–20:00, capacity 51/day).
          </p>
          <button
            onClick={ensureUnit}
            disabled={busy}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-500 text-white rounded-lg text-sm hover:bg-rose-600 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" /> Create Dialysis Unit
          </button>
        </div>
      )}

      {unit && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[
              { label: "Machines", value: schedule?.active_machines ?? activeMachines.length, sub: `${schedule?.usable_machines ?? "—"} usable` },
              { label: "Shifts", value: schedule?.active_shifts ?? activeShifts.length, sub: "4 hours each" },
              { label: "Capacity", value: schedule?.capacity ?? 0, sub: "slots / day" },
              { label: "Booked", value: schedule?.booked ?? 0, sub: fmtDate(day) },
              { label: "Available", value: schedule?.available ?? 0, sub: "open slots" },
            ].map(k => (
              <div key={k.label} className="bg-white rounded-xl border border-neutral-200 p-3">
                <div className="text-xs text-neutral-500 uppercase font-medium">{k.label}</div>
                <div className="text-2xl font-bold text-neutral-900 mt-0.5">{k.value}</div>
                <div className="text-[11px] text-neutral-400">{k.sub}</div>
              </div>
            ))}
          </div>

          {tab === "schedule" && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <label className="text-sm text-neutral-600">
                  Date{" "}
                  <input
                    type="date"
                    value={day}
                    onChange={e => setDay(e.target.value)}
                    className="ml-1 border border-neutral-200 rounded-lg px-2 py-1.5 text-sm"
                  />
                </label>
                <span className="text-xs text-neutral-400">
                  Click an empty cell to book · {schedule?.booked}/{schedule?.usable_capacity} usable
                </span>
              </div>

              <div className="bg-white rounded-xl border border-neutral-200 overflow-x-auto">
                <table className="w-full text-sm min-w-[720px]">
                  <thead>
                    <tr className="bg-neutral-50 border-b border-neutral-200 text-xs uppercase text-neutral-500">
                      <th className="text-left px-3 py-2.5 sticky left-0 bg-neutral-50">Machine</th>
                      {activeShifts.map(sh => (
                        <th key={sh.id} className="text-left px-3 py-2.5">
                          {sh.name}
                          <div className="font-normal normal-case text-neutral-400">
                            {sh.start_time}–{sh.end_time}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {activeMachines.map(m => (
                      <tr key={m.id}>
                        <td className="px-3 py-2 sticky left-0 bg-white whitespace-nowrap">
                          <div className="font-medium text-neutral-900">{m.code}</div>
                          <div className="text-[10px] text-neutral-400 capitalize flex items-center gap-1">
                            {m.status === "maintenance" && <Wrench className="w-3 h-3" />}
                            {m.status}
                          </div>
                        </td>
                        {activeShifts.map(sh => {
                          const slot = grid.byMachine.get(m.id)?.get(sh.id)
                          const sess = slot?.session
                          const offline = m.status === "maintenance"
                          if (sess) {
                            return (
                              <td key={sh.id} className="px-2 py-1.5 align-top">
                                <div className={`rounded-lg border p-2 space-y-1 ${SESSION_COLORS[sess.status] || SESSION_COLORS.scheduled}`}>
                                  <div className="font-medium text-xs leading-tight">
                                    {sess.patient_name || `Patient #${sess.patient_id}`}
                                  </div>
                                  <div className="text-[10px] opacity-80">
                                    {sess.patient_mr} · {sess.session_number}
                                  </div>
                                  <StatusBadge status={sess.status} />
                                  <div className="flex flex-wrap gap-1 pt-1">
                                    {sess.status === "scheduled" && (
                                      <>
                                        <button
                                          disabled={busy}
                                          onClick={() => act(sess.id, "start")}
                                          className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-white/80 border border-current/20"
                                        >
                                          <Play className="w-3 h-3" /> Start
                                        </button>
                                        <button
                                          disabled={busy}
                                          onClick={() => act(sess.id, "cancel")}
                                          className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-white/80 border border-current/20"
                                        >
                                          <XCircle className="w-3 h-3" /> Cancel
                                        </button>
                                      </>
                                    )}
                                    {(sess.status === "scheduled" || sess.status === "in_progress") && (
                                      <button
                                        disabled={busy}
                                        onClick={() => act(sess.id, "complete")}
                                        className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-white/80 border border-current/20"
                                      >
                                        <CheckCircle2 className="w-3 h-3" /> Complete
                                      </button>
                                    )}
                                    {sess.status === "in_progress" && (
                                      <button
                                        disabled={busy}
                                        onClick={() => act(sess.id, "cancel")}
                                        className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-white/80 border border-current/20"
                                      >
                                        <XCircle className="w-3 h-3" /> Cancel
                                      </button>
                                    )}
                                  </div>
                                </div>
                              </td>
                            )
                          }
                          return (
                            <td key={sh.id} className="px-2 py-1.5">
                              <button
                                disabled={offline || busy}
                                onClick={() => {
                                  if (slot) setBookSlot(slot)
                                }}
                                title={offline ? "Machine under maintenance" : "Book session"}
                                className={`w-full min-h-[72px] rounded-lg border border-dashed text-xs ${
                                  offline
                                    ? "border-neutral-200 bg-neutral-50 text-neutral-400 cursor-not-allowed"
                                    : "border-sky-200 text-sky-600 hover:bg-sky-50"
                                }`}
                              >
                                {offline ? "Offline" : "Book"}
                              </button>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === "setup" && (
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
                <div className="px-4 py-2.5 bg-neutral-50 border-b text-xs font-semibold uppercase text-neutral-600">
                  Machines ({machines.length})
                </div>
                <table className="w-full text-sm">
                  <thead className="text-xs text-neutral-500 uppercase border-b">
                    <tr>
                      <th className="text-left px-4 py-2">Code</th>
                      <th className="text-left px-4 py-2">Name</th>
                      <th className="text-left px-4 py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {machines.map(m => (
                      <tr key={m.id}>
                        <td className="px-4 py-2 font-medium">{m.code}</td>
                        <td className="px-4 py-2 text-neutral-600">{m.name}</td>
                        <td className="px-4 py-2">
                          <select
                            value={m.status}
                            disabled={busy}
                            onChange={e => setMachineStatus(m.id, e.target.value)}
                            className="border border-neutral-200 rounded-lg px-2 py-1 text-xs"
                          >
                            <option value="available">available</option>
                            <option value="in_use">in_use</option>
                            <option value="maintenance">maintenance</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
                <div className="px-4 py-2.5 bg-neutral-50 border-b text-xs font-semibold uppercase text-neutral-600">
                  Shifts ({shifts.length}) — 08:00 to 20:00
                </div>
                <table className="w-full text-sm">
                  <thead className="text-xs text-neutral-500 uppercase border-b">
                    <tr>
                      <th className="text-left px-4 py-2">Code</th>
                      <th className="text-left px-4 py-2">Name</th>
                      <th className="text-left px-4 py-2">Window</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {shifts.map(sh => (
                      <tr key={sh.id}>
                        <td className="px-4 py-2 font-medium">{sh.code}</td>
                        <td className="px-4 py-2">{sh.name}</td>
                        <td className="px-4 py-2 text-neutral-600 whitespace-nowrap">
                          {sh.start_time}–{sh.end_time}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-neutral-500 p-4 border-t">
                  Daily capacity = active machines × active shifts
                  ({schedule?.active_machines ?? 0} × {schedule?.active_shifts ?? 0} = {schedule?.capacity ?? 0}).
                  Maintenance machines reduce usable capacity to {schedule?.usable_capacity ?? 0}.
                </p>
              </div>
            </div>
          )}
        </>
      )}

      {/* Book modal */}
      {bookSlot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form
            onSubmit={bookSession}
            className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-4"
          >
            <h2 className="text-lg font-semibold">Book dialysis session</h2>
            <p className="text-sm text-neutral-500">
              {bookSlot.machine_code} · {bookSlot.shift_name} ({bookSlot.start_time}–{bookSlot.end_time}) · {fmtDate(day)}
            </p>
            <label className="block text-sm">
              Patient
              <select
                required
                value={bookPatientId}
                onChange={e => setBookPatientId(e.target.value)}
                className="mt-1 w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm"
              >
                <option value="">Select patient…</option>
                {patients.map(p => (
                  <option key={p.id} value={p.id}>{p.mr_number} — {p.name}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              Doctor (optional)
              <select
                value={bookDoctorId}
                onChange={e => setBookDoctorId(e.target.value)}
                className="mt-1 w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm"
              >
                <option value="">—</option>
                {doctors.map(d => (
                  <option key={d.id} value={d.id}>
                    {d.name}{d.specialization ? ` (${d.specialization})` : ""}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setBookSlot(null)}
                className="px-3 py-2 text-sm border border-neutral-200 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy}
                className="px-3 py-2 text-sm bg-rose-500 text-white rounded-lg hover:bg-rose-600 disabled:opacity-50"
              >
                {busy ? "Booking…" : "Book"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
