"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useTranslation } from "react-i18next"
import { ArrowLeft, Save, ChevronLeft, ChevronRight } from "lucide-react"
import { apiFetch } from "@/lib/api"

interface Employee {
  id: number
  employee_code: string
  name: string
  is_active: boolean
}

interface AttendanceRecord {
  employee_id: number
  date: string
  status: string
}

const STATUS_OPTIONS = [
  { value: "",         label: "·"        },
  { value: "present",  label: "P – Present"  },
  { value: "absent",   label: "A – Absent"   },
  { value: "half_day", label: "H – Half Day" },
  { value: "leave",    label: "L – Leave"    },
  { value: "holiday",  label: "Ho – Holiday" },
  { value: "off",      label: "O – Off"      },
]

const STATUS_CELL: Record<string, { short: string; bg: string; text: string }> = {
  present:  { short: "P",  bg: "bg-green-50",  text: "text-green-700"  },
  absent:   { short: "A",  bg: "bg-red-50",    text: "text-red-700"    },
  half_day: { short: "H",  bg: "bg-amber-50",  text: "text-amber-700"  },
  leave:    { short: "L",  bg: "bg-blue-50",   text: "text-blue-700"   },
  holiday:  { short: "Ho", bg: "bg-purple-50", text: "text-purple-700" },
  off:      { short: "O",  bg: "bg-gray-50",   text: "text-gray-500"   },
}

function getDaysInMonth(year: number, month: number): number[] {
  const d = new Date(year, month, 0).getDate()
  return Array.from({ length: d }, (_, i) => i + 1)
}

function pad2(n: number): string {
  return n.toString().padStart(2, "0")
}

const MONTH_NAMES = ["January","February","March","April","May","June",
  "July","August","September","October","November","December"]

export default function BulkAttendancePage() {
  const { t } = useTranslation()
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1)
  const [employees, setEmployees] = useState<Employee[]>([])
  const [grid, setGrid] = useState<Record<number, Record<number, string>>>({})
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState("")
  const [loading, setLoading] = useState(false)

  const days = getDaysInMonth(year, month)
  const fromDate = `${year}-${pad2(month)}-01`
  const toDate = `${year}-${pad2(month)}-${pad2(days.length)}`

  useEffect(() => {
    apiFetch<Employee[]>("/api/employees")
      .then(data => setEmployees(data.filter(e => e.is_active)))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!employees.length) return
    setLoading(true)
    apiFetch<AttendanceRecord[]>(`/api/attendance?from_date=${fromDate}&to_date=${toDate}`)
      .then(recs => {
        const g: Record<number, Record<number, string>> = {}
        for (const emp of employees) g[emp.id] = {}
        for (const rec of recs) {
          const day = parseInt(rec.date.split("-")[2], 10)
          if (!g[rec.employee_id]) g[rec.employee_id] = {}
          g[rec.employee_id][day] = rec.status
        }
        setGrid(g)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [year, month, employees.length])

  function prevMonth() {
    if (month === 1) { setYear(y => y - 1); setMonth(12) }
    else setMonth(m => m - 1)
  }
  function nextMonth() {
    if (month === 12) { setYear(y => y + 1); setMonth(1) }
    else setMonth(m => m + 1)
  }

  function setCell(empId: number, day: number, value: string) {
    setGrid(g => ({
      ...g,
      [empId]: { ...(g[empId] ?? {}), [day]: value },
    }))
  }

  async function handleSave() {
    setSaving(true)
    const records: Array<{ employee_id: number; date: string; status: string }> = []
    for (const emp of employees) {
      for (const day of days) {
        const st = grid[emp.id]?.[day]
        if (st) {
          records.push({
            employee_id: emp.id,
            date: `${year}-${pad2(month)}-${pad2(day)}`,
            status: st,
          })
        }
      }
    }
    try {
      const res = await apiFetch<{ created: number; updated: number; errors: string[] }>(
        "/api/attendance/bulk",
        { method: "POST", body: JSON.stringify({ records }) }
      )
      setToast(`Created ${res.created}, Updated ${res.updated} records.${res.errors.length ? ` Errors: ${res.errors.length}` : ""}`)
      setTimeout(() => setToast(""), 5000)
    } catch {
      setToast("Failed to save")
      setTimeout(() => setToast(""), 4000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/attendance" className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold text-[#1a1814]">
          {t("Bulk Attendance Entry")}
        </h1>
      </div>

      {toast && (
        <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm">{toast}</div>
      )}

      {/* Month nav */}
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={prevMonth} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-lg font-semibold text-[#1a1814] min-w-[160px] text-center">
          {MONTH_NAMES[month - 1]} {year}
        </span>
        <button onClick={nextMonth} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50">
          <ChevronRight className="w-4 h-4" />
        </button>
        <select value={year} onChange={e => setYear(+e.target.value)}
          className="border border-gray-200 rounded-lg px-2 py-1 text-sm bg-white">
          {Array.from({ length: 5 }, (_, i) => today.getFullYear() - 2 + i).map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
        <button
          onClick={handleSave}
          disabled={saving}
          className="ml-auto inline-flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:opacity-90 text-sm font-medium disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {saving ? "Saving…" : "Save All"}
        </button>
      </div>

      <p className="text-xs text-gray-400">
        Select status for each day. Blank cells (·) are skipped. Time in/out can be added via the single record form.
      </p>

      {loading ? (
        <div className="text-center py-16 text-gray-400">Loading…</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-100 shadow-sm">
          <table className="min-w-[900px] w-full text-xs border-collapse">
            <thead>
              <tr className="bg-[#f6f3ee]">
                <th className="sticky left-0 z-10 bg-[#f6f3ee] text-left px-3 py-2 font-semibold text-[#1a1814] border-b border-gray-200 whitespace-nowrap">
                  Employee
                </th>
                {days.map(d => (
                  <th key={d} className="px-1 py-2 font-medium text-center border-b border-gray-200 min-w-[32px] text-[#1a1814]">{d}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {employees.length === 0 && (
                <tr>
                  <td colSpan={days.length + 1} className="text-center py-10 text-gray-400">
                    No active employees found.
                  </td>
                </tr>
              )}
              {employees.map((emp, idx) => (
                <tr key={emp.id} className={idx % 2 === 0 ? "bg-white" : "bg-[#faf9f7]"}>
                  <td className={`sticky left-0 z-10 px-3 py-1 font-medium whitespace-nowrap border-b border-gray-100 ${idx % 2 === 0 ? "bg-white" : "bg-[#faf9f7]"}`}>
                    {emp.name}
                  </td>
                  {days.map(day => {
                    const val = grid[emp.id]?.[day] ?? ""
                    const cfg = val ? STATUS_CELL[val] : null
                    return (
                      <td key={day} className={`border-b border-gray-100 text-center p-0.5 ${cfg ? `${cfg.bg}` : ""}`}>
                        <select
                          value={val}
                          onChange={e => setCell(emp.id, day, e.target.value)}
                          className={`w-full h-7 text-xs text-center border-0 bg-transparent focus:outline-none cursor-pointer appearance-none ${cfg ? cfg.text : "text-gray-300"}`}
                          title={`${emp.name} — ${year}-${pad2(month)}-${pad2(day)}`}
                        >
                          {STATUS_OPTIONS.map(o => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </select>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
