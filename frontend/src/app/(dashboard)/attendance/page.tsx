"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useTranslation } from "react-i18next"
import {
  ChevronLeft, ChevronRight, Plus, FileText, Upload, Printer, Users, Clock, Calendar, TrendingUp,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface AttendanceRecord {
  id: number
  employee_id: number
  employee_name: string
  date: string
  time_in: string | null
  time_out: string | null
  hours_worked: number | null
  status: string
  notes: string | null
  source: string
}

interface SummaryRow {
  employee_id: number
  name: string
  present: number
  absent: number
  half_day: number
  leave: number
  holiday: number
  off: number
  total_hours: number
}

const STATUS_CONFIG: Record<string, { label: string; short: string; bg: string; text: string }> = {
  present:  { label: "Present",  short: "P",  bg: "bg-green-100",  text: "text-green-700" },
  absent:   { label: "Absent",   short: "A",  bg: "bg-red-100",    text: "text-red-700"   },
  half_day: { label: "Half Day", short: "H",  bg: "bg-amber-100",  text: "text-amber-700" },
  leave:    { label: "Leave",    short: "L",  bg: "bg-blue-100",   text: "text-blue-700"  },
  holiday:  { label: "Holiday",  short: "Ho", bg: "bg-purple-100", text: "text-purple-700"},
  off:      { label: "Off",      short: "O",  bg: "bg-gray-100",   text: "text-gray-500"  },
}

function getDaysInMonth(year: number, month: number): number[] {
  const d = new Date(year, month, 0).getDate()
  return Array.from({ length: d }, (_, i) => i + 1)
}

function pad2(n: number): string {
  return n.toString().padStart(2, "0")
}

export default function AttendancePage() {
  const { t } = useTranslation()
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1)
  const [records, setRecords] = useState<AttendanceRecord[]>([])
  const [summary, setSummary] = useState<SummaryRow[]>([])
  const [loading, setLoading] = useState(false)
  const [popover, setPopover] = useState<{ empId: number; day: number; x: number; y: number } | null>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  const days = getDaysInMonth(year, month)
  const fromDate = `${year}-${pad2(month)}-01`
  const toDate = `${year}-${pad2(month)}-${pad2(days.length)}`

  useEffect(() => {
    setLoading(true)
    Promise.all([
      apiFetch<AttendanceRecord[]>(`/api/attendance?from_date=${fromDate}&to_date=${toDate}`),
      apiFetch<SummaryRow[]>(`/api/attendance/summary?year=${year}&month=${month}`),
    ])
      .then(([recs, sum]) => { setRecords(recs); setSummary(sum) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [year, month])

  // Build lookup: empId → day → record
  const lookup: Record<number, Record<number, AttendanceRecord>> = {}
  for (const rec of records) {
    const day = parseInt(rec.date.split("-")[2], 10)
    if (!lookup[rec.employee_id]) lookup[rec.employee_id] = {}
    lookup[rec.employee_id][day] = rec
  }

  // Unique employees (from summary + records)
  const empIds = Array.from(new Set([...summary.map(s => s.employee_id)]))
  const summaryMap: Record<number, SummaryRow> = {}
  for (const s of summary) summaryMap[s.employee_id] = s

  const totalEmployees = empIds.length
  const avgAttendance = totalEmployees > 0
    ? Math.round(summary.reduce((a, s) => a + s.present, 0) / totalEmployees / days.length * 100)
    : 0
  const totalHours = summary.reduce((a, s) => a + s.total_hours, 0)

  function prevMonth() {
    if (month === 1) { setYear(y => y - 1); setMonth(12) }
    else setMonth(m => m - 1)
  }
  function nextMonth() {
    if (month === 12) { setYear(y => y + 1); setMonth(1) }
    else setMonth(m => m + 1)
  }

  function handleCellClick(empId: number, day: number, e: React.MouseEvent) {
    const rect = (e.target as HTMLElement).getBoundingClientRect()
    setPopover(p => (p?.empId === empId && p?.day === day) ? null : { empId, day, x: rect.left, y: rect.bottom })
  }

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setPopover(null)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const popoverRecord = popover ? lookup[popover.empId]?.[popover.day] : null

  const MONTH_NAMES = ["January","February","March","April","May","June",
    "July","August","September","October","November","December"]

  return (
    <div className="space-y-4">
      <PrintHeader title="Attendance Register" orientation="landscape" />

      {/* Header toolbar */}
      <div className="print:hidden flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-xl sm:text-3xl font-bold text-[#1a1814]">
          {t("Attendance Register")}
        </h1>
        <div className="flex flex-wrap gap-2">
          <Link href="/attendance/record"
            className="inline-flex items-center gap-1 px-3 py-2 bg-[#b8943f] text-white rounded-lg hover:opacity-90 text-sm font-medium">
            <Plus className="w-4 h-4" /> Add Record
          </Link>
          <Link href="/attendance/bulk"
            className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 bg-white rounded-lg hover:bg-gray-50 text-sm text-[#1a1814]">
            <FileText className="w-4 h-4" /> Bulk Entry
          </Link>
          <Link href="/attendance/report"
            className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 bg-white rounded-lg hover:bg-gray-50 text-sm text-[#1a1814]">
            <TrendingUp className="w-4 h-4" /> Report
          </Link>
          <Link href="/attendance/import"
            className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 bg-white rounded-lg hover:bg-gray-50 text-sm text-[#1a1814]">
            <Upload className="w-4 h-4" /> Import
          </Link>
          <button onClick={() => window.print()}
            className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 bg-white rounded-lg hover:bg-gray-50 text-sm text-[#1a1814]">
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
      </div>

      {/* Month navigation */}
      <div className="print:hidden flex items-center gap-3">
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
          className="border border-gray-200 rounded-lg px-2 py-1 text-sm bg-white ml-2">
          {Array.from({ length: 5 }, (_, i) => today.getFullYear() - 2 + i).map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 print:hidden">
        {[
          { icon: Users,    label: "Total Employees",    value: totalEmployees },
          { icon: TrendingUp, label: "Avg Attendance %", value: `${avgAttendance}%` },
          { icon: Clock,    label: "Total Hours",         value: totalHours.toFixed(1) },
          { icon: Calendar, label: "Days in Period",      value: days.length },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1">
              <Icon className="w-4 h-4 text-[#b8943f]" />
              <span className="text-xs text-gray-500">{label}</span>
            </div>
            <div className="text-2xl font-bold text-[#1a1814]">{value}</div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 print:hidden">
        {Object.entries(STATUS_CONFIG).map(([, cfg]) => (
          <span key={cfg.short} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${cfg.bg} ${cfg.text}`}>
            {cfg.short} — {cfg.label}
          </span>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="text-center py-16 text-gray-400">Loading…</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-100 shadow-sm">
          <table className="min-w-[900px] w-full text-sm border-collapse">
            <thead>
              <tr className="bg-[#f6f3ee] text-[#1a1814]">
                <th className="sticky left-0 z-10 bg-[#f6f3ee] text-left px-3 py-2 font-semibold whitespace-nowrap border-b border-gray-200">
                  Employee
                </th>
                {days.map(d => (
                  <th key={d} className="px-1 py-2 font-medium text-center border-b border-gray-200 min-w-[28px]">{d}</th>
                ))}
                <th className="px-2 py-2 font-medium text-center border-b border-gray-200 whitespace-nowrap">Hrs</th>
                <th className="px-2 py-2 font-medium text-center border-b border-gray-200 whitespace-nowrap">P</th>
                <th className="px-2 py-2 font-medium text-center border-b border-gray-200 whitespace-nowrap">A</th>
              </tr>
            </thead>
            <tbody>
              {empIds.length === 0 && (
                <tr>
                  <td colSpan={days.length + 4} className="text-center py-10 text-gray-400">
                    No attendance records for this month.{" "}
                    <Link href="/attendance/record" className="text-[#b8943f] underline">Add Record</Link>
                  </td>
                </tr>
              )}
              {empIds.map((empId, idx) => {
                const sum = summaryMap[empId]
                const empName = sum?.name ?? `#${empId}`
                return (
                  <tr key={empId} className={idx % 2 === 0 ? "bg-white" : "bg-[#faf9f7]"}>
                    <td className={`sticky left-0 z-10 px-3 py-1.5 font-medium whitespace-nowrap border-b border-gray-100 ${idx % 2 === 0 ? "bg-white" : "bg-[#faf9f7]"}`}>
                      {empName}
                    </td>
                    {days.map(day => {
                      const rec = lookup[empId]?.[day]
                      const cfg = rec ? STATUS_CONFIG[rec.status] : null
                      return (
                        <td key={day} className="px-1 py-1.5 text-center border-b border-gray-100">
                          {rec && cfg ? (
                            <button
                              onClick={e => handleCellClick(empId, day, e)}
                              className={`w-6 h-6 rounded text-xs font-bold cursor-pointer ${cfg.bg} ${cfg.text} hover:opacity-80`}
                              title={`${empName} — ${fmtDate(rec.date)}: ${cfg.label}`}
                            >
                              {cfg.short}
                            </button>
                          ) : (
                            <Link
                              href={`/attendance/record?employee_id=${empId}&date=${year}-${pad2(month)}-${pad2(day)}`}
                              className="text-gray-300 hover:text-[#b8943f] text-xs"
                              title="Add record"
                            >
                              ·
                            </Link>
                          )}
                        </td>
                      )
                    })}
                    <td className="px-2 py-1.5 text-center text-xs text-gray-600 border-b border-gray-100 whitespace-nowrap">
                      {sum?.total_hours.toFixed(1) ?? "—"}
                    </td>
                    <td className="px-2 py-1.5 text-center text-xs text-green-700 font-medium border-b border-gray-100">
                      {sum?.present ?? 0}
                    </td>
                    <td className="px-2 py-1.5 text-center text-xs text-red-600 font-medium border-b border-gray-100">
                      {sum?.absent ?? 0}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Cell popover */}
      {popover && (
        <div
          ref={popoverRef}
          className="fixed z-50 bg-white rounded-xl shadow-xl border border-gray-200 p-3 min-w-[180px] text-sm"
          style={{ top: popover.y + 8, left: Math.min(popover.x, window.innerWidth - 200) }}
        >
          {popoverRecord ? (
            <div className="space-y-1">
              <div className="font-semibold text-[#1a1814]">{fmtDate(popoverRecord.date)}</div>
              <div className="text-gray-500">{STATUS_CONFIG[popoverRecord.status]?.label}</div>
              {popoverRecord.time_in && (
                <div className="text-gray-600">In: {popoverRecord.time_in}</div>
              )}
              {popoverRecord.time_out && (
                <div className="text-gray-600">Out: {popoverRecord.time_out}</div>
              )}
              {popoverRecord.hours_worked != null && (
                <div className="text-gray-600">Hours: {popoverRecord.hours_worked}</div>
              )}
              {popoverRecord.notes && (
                <div className="text-gray-400 text-xs">{popoverRecord.notes}</div>
              )}
              <Link
                href={`/attendance/record?employee_id=${popoverRecord.employee_id}&date=${popoverRecord.date}`}
                className="block mt-2 text-[#b8943f] text-xs underline"
                onClick={() => setPopover(null)}
              >
                Edit
              </Link>
            </div>
          ) : (
            <div className="text-gray-400">No record</div>
          )}
        </div>
      )}
    </div>
  )
}
