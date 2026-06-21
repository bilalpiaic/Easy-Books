"use client"

import { useEffect, useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useTranslation } from "react-i18next"
import { ArrowLeft, Save, Clock } from "lucide-react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"

interface Employee {
  id: number
  employee_code: string
  name: string
  is_active: boolean
}

interface AttendanceRecord {
  id: number
  employee_id: number
  date: string
  time_in: string | null
  time_out: string | null
  hours_worked: number | null
  status: string
  notes: string | null
}

const STATUS_OPTIONS = [
  { value: "present",  label: "Present"  },
  { value: "absent",   label: "Absent"   },
  { value: "half_day", label: "Half Day" },
  { value: "leave",    label: "Leave"    },
  { value: "holiday",  label: "Holiday"  },
  { value: "off",      label: "Off"      },
]

function computeHours(timeIn: string, timeOut: string): number | null {
  try {
    const [ih, im] = timeIn.split(":").map(Number)
    const [oh, om] = timeOut.split(":").map(Number)
    const mins = (oh * 60 + om) - (ih * 60 + im)
    return Math.round(Math.max(0, mins) / 60 * 100) / 100
  } catch {
    return null
  }
}

function AttendanceRecordForm() {
  const { t } = useTranslation()
  const router = useRouter()
  const params = useSearchParams()

  const initEmpId = params.get("employee_id") ? parseInt(params.get("employee_id")!) : null
  const initDate = params.get("date") ?? ""

  const [employees, setEmployees] = useState<Employee[]>([])
  const [employeeId, setEmployeeId] = useState<string>(initEmpId?.toString() ?? "")
  const [date, setDate] = useState(initDate)
  const [status, setStatus] = useState("present")
  const [timeIn, setTimeIn] = useState("")
  const [timeOut, setTimeOut] = useState("")
  const [notes, setNotes] = useState("")
  const [existingId, setExistingId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const showTimes = status === "present" || status === "half_day"
  const hoursPreview = showTimes && timeIn && timeOut ? computeHours(timeIn, timeOut) : null

  useEffect(() => {
    apiFetch<Employee[]>("/api/employees")
      .then(data => setEmployees(data.filter(e => e.is_active)))
      .catch(() => {})
  }, [])

  // Load existing record if both employee_id and date are provided
  useEffect(() => {
    if (!employeeId || !date) return
    setLoading(true)
    apiFetch<AttendanceRecord[]>(`/api/attendance?employee_id=${employeeId}&from_date=${date}&to_date=${date}`)
      .then(data => {
        if (data.length > 0) {
          const rec = data[0]
          setExistingId(rec.id)
          setStatus(rec.status)
          setTimeIn(rec.time_in ?? "")
          setTimeOut(rec.time_out ?? "")
          setNotes(rec.notes ?? "")
        } else {
          setExistingId(null)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [employeeId, date])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!employeeId || !date) { setError("Employee and date are required"); return }
    setSaving(true)
    setError("")
    const payload = {
      employee_id: parseInt(employeeId),
      date,
      status,
      time_in: showTimes && timeIn ? timeIn : null,
      time_out: showTimes && timeOut ? timeOut : null,
      notes: notes || null,
    }
    try {
      if (existingId) {
        await apiFetch(`/api/attendance/${existingId}`, { method: "PUT", body: JSON.stringify({
          status,
          time_in: showTimes && timeIn ? timeIn : null,
          time_out: showTimes && timeOut ? timeOut : null,
          notes: notes || null,
        }) })
      } else {
        await apiFetch("/api/attendance", { method: "POST", body: JSON.stringify(payload) })
      }
      router.push("/attendance")
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save"
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/attendance" className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold text-[#1a1814]">
          {existingId ? t("Edit Attendance") : t("Add Attendance Record")}
        </h1>
      </div>

      {loading && <p className="text-sm text-gray-400">Checking existing record…</p>}

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-4">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm">{error}</div>
        )}

        {existingId && (
          <div className="bg-amber-50 border border-amber-200 text-amber-700 rounded-lg px-4 py-2 text-sm">
            Existing record found — editing.
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-[#1a1814] mb-1">Employee *</label>
          <select
            value={employeeId}
            onChange={e => { setEmployeeId(e.target.value); setExistingId(null) }}
            required
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
          >
            <option value="">Select employee…</option>
            {employees.map(emp => (
              <option key={emp.id} value={emp.id}>{emp.name} ({emp.employee_code})</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-[#1a1814] mb-1">Date *</label>
          <input
            type="date"
            value={date}
            onChange={e => { setDate(e.target.value); setExistingId(null) }}
            required
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[#1a1814] mb-1">Status</label>
          <select
            value={status}
            onChange={e => setStatus(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
          >
            {STATUS_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {showTimes && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[#1a1814] mb-1">Time In (HH:MM)</label>
              <input
                type="time"
                value={timeIn}
                onChange={e => setTimeIn(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#1a1814] mb-1">Time Out (HH:MM)</label>
              <input
                type="time"
                value={timeOut}
                onChange={e => setTimeOut(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
              />
            </div>
          </div>
        )}

        {showTimes && hoursPreview !== null && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Clock className="w-4 h-4 text-[#b8943f]" />
            Hours worked: <strong className="text-[#1a1814]">{hoursPreview}</strong>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-[#1a1814] mb-1">Notes</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={2}
            placeholder="Optional notes…"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30 resize-none"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:opacity-90 text-sm font-medium disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? "Saving…" : "Save Record"}
          </button>
          <Link href="/attendance"
            className="px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}

export default function AttendanceRecordPage() {
  return (
    <Suspense fallback={<div className="text-center py-16 text-gray-400">Loading…</div>}>
      <AttendanceRecordForm />
    </Suspense>
  )
}
