"use client"

import { useState } from "react"
import Link from "next/link"
import { useTranslation } from "react-i18next"
import { ArrowLeft, Printer, Download, Search } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface Employee {
  id: number
  name: string
  employee_code: string
}

interface AttendanceRecord {
  id: number
  employee_id: number
  employee_name: string
  date: string
  status: string
  time_in: string | null
  time_out: string | null
  hours_worked: number | null
  source: string
  notes: string | null
}

const STATUS_LABELS: Record<string, string> = {
  present:  "Present",
  absent:   "Absent",
  half_day: "Half Day",
  leave:    "Leave",
  holiday:  "Holiday",
  off:      "Off",
}

const STATUS_COLORS: Record<string, string> = {
  present:  "text-green-700",
  absent:   "text-red-600",
  half_day: "text-amber-600",
  leave:    "text-blue-600",
  holiday:  "text-purple-600",
  off:      "text-gray-400",
}

export default function AttendanceReportPage() {
  const { t } = useTranslation()
  const today = new Date().toISOString().split("T")[0]
  const firstOfMonth = today.slice(0, 7) + "-01"

  const [employeeId, setEmployeeId] = useState("")
  const [employees, setEmployees] = useState<Employee[]>([])
  const [fromDate, setFromDate] = useState(firstOfMonth)
  const [toDate, setToDate] = useState(today)
  const [records, setRecords] = useState<AttendanceRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [hasRun, setHasRun] = useState(false)

  // Load employees for dropdown
  useState(() => {
    apiFetch<Employee[]>("/api/employees").then(setEmployees).catch(() => {})
  })

  function handleRun() {
    setLoading(true)
    const params = new URLSearchParams({ from_date: fromDate, to_date: toDate })
    if (employeeId) params.set("employee_id", employeeId)
    apiFetch<AttendanceRecord[]>(`/api/attendance?${params}`)
      .then(data => { setRecords(data); setHasRun(true) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  // Group by employee when "All"
  const grouped: Record<number, AttendanceRecord[]> = {}
  for (const rec of records) {
    if (!grouped[rec.employee_id]) grouped[rec.employee_id] = []
    grouped[rec.employee_id].push(rec)
  }

  const totalPresent = records.filter(r => r.status === "present").length
  const totalAbsent = records.filter(r => r.status === "absent").length
  const totalHours = records.reduce((a, r) => a + (r.hours_worked ?? 0), 0)
  const attendancePct = records.length > 0 ? Math.round(totalPresent / records.length * 100) : 0

  function exportCsv() {
    const header = "Date,Employee,Status,Time In,Time Out,Hours,Source,Notes"
    const rows = records.map(r =>
      [
        r.date,
        r.employee_name,
        STATUS_LABELS[r.status] ?? r.status,
        r.time_in ?? "",
        r.time_out ?? "",
        r.hours_worked ?? "",
        r.source,
        r.notes ?? "",
      ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(",")
    )
    const csv = [header, ...rows].join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `attendance_${fromDate}_to_${toDate}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      <PrintHeader title="Attendance Report" orientation="landscape" />

      <div className="print:hidden flex items-center gap-3">
        <Link href="/attendance" className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">
          {t("Attendance Report")}
        </h1>
      </div>

      {/* Filters */}
      <div className="print:hidden flex flex-wrap gap-3 items-end bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Employee</label>
          <select
            value={employeeId}
            onChange={e => setEmployeeId(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white min-w-[180px] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
          >
            <option value="">All Employees</option>
            {employees.map(emp => (
              <option key={emp.id} value={emp.id}>{emp.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">From Date</label>
          <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">To Date</label>
          <input type="date" value={toDate} onChange={e => setToDate(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30" />
        </div>
        <button
          onClick={handleRun}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg hover:opacity-90 text-sm font-medium disabled:opacity-50"
        >
          <Search className="w-4 h-4" />
          {loading ? "Loading…" : "Run Report"}
        </button>
        {hasRun && (
          <>
            <button onClick={() => window.print()}
              className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
              <Printer className="w-4 h-4" /> Print
            </button>
            <button onClick={exportCsv}
              className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
              <Download className="w-4 h-4" /> Export CSV
            </button>
          </>
        )}
      </div>

      {/* Summary footer */}
      {hasRun && (
        <div className="print:hidden grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          {[
            { label: "Total Records", value: records.length },
            { label: "Total Hours", value: totalHours.toFixed(1) },
            { label: "Attendance %", value: `${attendancePct}%` },
            { label: "Absent", value: totalAbsent },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-100 p-3 shadow-sm">
              <div className="text-xs text-gray-500">{label}</div>
              <div className="text-lg font-bold text-[var(--text-primary)]">{value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Table */}
      {hasRun && (
        <div className="overflow-x-auto table-freeze rounded-xl border border-gray-100 shadow-sm">
          {!employeeId ? (
            // Grouped by employee
            Object.entries(grouped).map(([eid, recs]) => {
              const empTotalHours = recs.reduce((a, r) => a + (r.hours_worked ?? 0), 0)
              const empPresent = recs.filter(r => r.status === "present").length
              return (
                <div key={eid} className="mb-6">
                  <div className="bg-[var(--bg-page)] px-4 py-2 font-semibold text-sm text-[var(--text-primary)] flex justify-between">
                    <span>{recs[0]?.employee_name}</span>
                    <span className="text-gray-500">{empPresent} present · {empTotalHours.toFixed(1)} hrs</span>
                  </div>
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-gray-50 text-gray-500 text-xs">
                        <th className="text-left px-4 py-2 border-b border-gray-100 whitespace-nowrap">Date</th>
                        <th className="text-left px-4 py-2 border-b border-gray-100">Status</th>
                        <th className="text-left px-4 py-2 border-b border-gray-100 whitespace-nowrap">Time In</th>
                        <th className="text-left px-4 py-2 border-b border-gray-100 whitespace-nowrap">Time Out</th>
                        <th className="text-right px-4 py-2 border-b border-gray-100">Hours</th>
                        <th className="text-left px-4 py-2 border-b border-gray-100">Source</th>
                        <th className="text-left px-4 py-2 border-b border-gray-100">Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recs.map((rec, i) => (
                        <tr key={rec.id} className={i % 2 === 0 ? "bg-white" : "bg-[#faf9f7]"}>
                          <td className="px-4 py-1.5 border-b border-gray-100 whitespace-nowrap">{fmtDate(rec.date)}</td>
                          <td className={`px-4 py-1.5 border-b border-gray-100 font-medium ${STATUS_COLORS[rec.status] ?? ""}`}>
                            {STATUS_LABELS[rec.status] ?? rec.status}
                          </td>
                          <td className="px-4 py-1.5 border-b border-gray-100 whitespace-nowrap">{rec.time_in ?? "—"}</td>
                          <td className="px-4 py-1.5 border-b border-gray-100 whitespace-nowrap">{rec.time_out ?? "—"}</td>
                          <td className="px-4 py-1.5 border-b border-gray-100 text-right">{rec.hours_worked ?? "—"}</td>
                          <td className="px-4 py-1.5 border-b border-gray-100 text-xs text-gray-500">{rec.source}</td>
                          <td className="px-4 py-1.5 border-b border-gray-100 text-xs text-gray-400">{rec.notes ?? ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            })
          ) : (
            // Single employee flat table
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-[var(--bg-page)] text-[var(--text-primary)]">
                  <th className="text-left px-4 py-2 border-b border-gray-200 whitespace-nowrap">Date</th>
                  <th className="text-left px-4 py-2 border-b border-gray-200">Employee</th>
                  <th className="text-left px-4 py-2 border-b border-gray-200">Status</th>
                  <th className="text-left px-4 py-2 border-b border-gray-200 whitespace-nowrap">Time In</th>
                  <th className="text-left px-4 py-2 border-b border-gray-200 whitespace-nowrap">Time Out</th>
                  <th className="text-right px-4 py-2 border-b border-gray-200">Hours</th>
                  <th className="text-left px-4 py-2 border-b border-gray-200">Source</th>
                  <th className="text-left px-4 py-2 border-b border-gray-200">Notes</th>
                </tr>
              </thead>
              <tbody>
                {records.length === 0 && (
                  <tr><td colSpan={8} className="text-center py-10 text-gray-400">No records found.</td></tr>
                )}
                {records.map((rec, i) => (
                  <tr key={rec.id} className={i % 2 === 0 ? "bg-white" : "bg-[#faf9f7]"}>
                    <td className="px-4 py-1.5 border-b border-gray-100 whitespace-nowrap">{fmtDate(rec.date)}</td>
                    <td className="px-4 py-1.5 border-b border-gray-100">{rec.employee_name}</td>
                    <td className={`px-4 py-1.5 border-b border-gray-100 font-medium ${STATUS_COLORS[rec.status] ?? ""}`}>
                      {STATUS_LABELS[rec.status] ?? rec.status}
                    </td>
                    <td className="px-4 py-1.5 border-b border-gray-100 whitespace-nowrap">{rec.time_in ?? "—"}</td>
                    <td className="px-4 py-1.5 border-b border-gray-100 whitespace-nowrap">{rec.time_out ?? "—"}</td>
                    <td className="px-4 py-1.5 border-b border-gray-100 text-right">{rec.hours_worked ?? "—"}</td>
                    <td className="px-4 py-1.5 border-b border-gray-100 text-xs text-gray-500">{rec.source}</td>
                    <td className="px-4 py-1.5 border-b border-gray-100 text-xs text-gray-400">{rec.notes ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {!hasRun && (
        <div className="text-center py-16 text-gray-400 bg-white rounded-xl border border-gray-100">
          Select filters and click <strong>Run Report</strong>
        </div>
      )}
    </div>
  )
}
