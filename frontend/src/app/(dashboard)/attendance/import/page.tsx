"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useTranslation } from "react-i18next"
import { ArrowLeft, Upload, Download, Info, CheckCircle, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

interface Employee {
  id: number
  employee_code: string
  name: string
  is_active: boolean
}

interface ParsedRow {
  employee_code: string
  date: string
  time_in: string
  time_out: string
  matched_name?: string
  matched_id?: number
}

interface ImportResult {
  matched: number
  unmatched: number
  created: number
  updated: number
}

export default function AttendanceImportPage() {
  const { t } = useTranslation()
  const fileRef = useRef<HTMLInputElement>(null)
  const [employees, setEmployees] = useState<Employee[]>([])
  const [parsed, setParsed] = useState<ParsedRow[]>([])
  const [fileName, setFileName] = useState("")
  const [result, setResult] = useState<ImportResult | null>(null)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    apiFetch<Employee[]>("/api/employees").then(setEmployees).catch(() => {})
  }, [])

  const empByCode: Record<string, Employee> = {}
  for (const emp of employees) {
    if (emp.employee_code) empByCode[emp.employee_code] = emp
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setFileName(file.name)
    setResult(null)
    setError("")
    const reader = new FileReader()
    reader.onload = ev => {
      const text = ev.target?.result as string
      const lines = text.split(/\r?\n/).filter(l => l.trim())
      // Skip header if it looks like one
      const start = /employee_code/i.test(lines[0]) ? 1 : 0
      const rows: ParsedRow[] = []
      for (const line of lines.slice(start)) {
        const parts = line.split(",").map(p => p.trim().replace(/^"|"$/g, ""))
        if (parts.length < 2) continue
        const [employee_code, date, time_in = "", time_out = ""] = parts
        if (!employee_code || !date) continue
        const emp = empByCode[employee_code]
        rows.push({
          employee_code,
          date,
          time_in,
          time_out,
          matched_name: emp?.name,
          matched_id: emp?.id,
        })
      }
      setParsed(rows)
    }
    reader.readAsText(file)
  }

  function downloadTemplate() {
    const csv = [
      "employee_code,date,time_in,time_out",
      "EMP-0001,2026-06-01,09:00,17:00",
      "EMP-0002,2026-06-01,08:30,16:30",
    ].join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "attendance_template.csv"
    a.click()
    URL.revokeObjectURL(url)
  }

  async function handleImport() {
    setImporting(true)
    setError("")
    const records = parsed
      .filter(r => r.matched_id)
      .map(r => ({
        employee_code: r.employee_code,
        date: r.date,
        time_in: r.time_in || null,
        time_out: r.time_out || null,
        raw_data: null,
      }))
    try {
      const res = await apiFetch<ImportResult>("/api/attendance/import/biometric", {
        method: "POST",
        body: JSON.stringify({ records }),
      })
      setResult(res)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Import failed")
    } finally {
      setImporting(false)
    }
  }

  const matchedCount = parsed.filter(r => r.matched_id).length
  const unmatchedCount = parsed.length - matchedCount

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3">
        <Link href="/attendance" className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[#1a1814]">
            {t("Biometric Import")}
          </h1>
          <span className="inline-block mt-0.5 text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full font-medium">
            Manual CSV mode — biometric device integration coming soon
          </span>
        </div>
      </div>

      {/* CSV Upload */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-4">
        <h2 className="font-semibold text-[#1a1814]">CSV File Upload</h2>
        <div className="text-sm text-gray-500">
          <p>Expected format: <code className="bg-gray-100 px-1 rounded">employee_code, date (YYYY-MM-DD), time_in (HH:MM), time_out (HH:MM)</code></p>
          <p className="mt-1">The header row is optional but recommended. Records are matched by employee code.</p>
        </div>

        <div className="flex gap-3 flex-wrap">
          <button
            onClick={() => fileRef.current?.click()}
            className="inline-flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50"
          >
            <Upload className="w-4 h-4 text-[#b8943f]" />
            {fileName ? fileName : "Choose CSV File"}
          </button>
          <input ref={fileRef} type="file" accept=".csv" onChange={handleFile} className="hidden" />

          <button
            onClick={downloadTemplate}
            className="inline-flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50"
          >
            <Download className="w-4 h-4" />
            Download Template
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {result && (
          <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-3 text-sm flex items-start gap-2">
            <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div>
              Matched: <strong>{result.matched}</strong> &nbsp;·&nbsp;
              Unmatched: <strong>{result.unmatched}</strong> &nbsp;·&nbsp;
              Created: <strong>{result.created}</strong> &nbsp;·&nbsp;
              Updated: <strong>{result.updated}</strong>
            </div>
          </div>
        )}

        {/* Preview table */}
        {parsed.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-[#1a1814]">
                Preview: {parsed.length} rows &nbsp;
                <span className="text-green-600">({matchedCount} matched)</span>
                {unmatchedCount > 0 && <span className="text-red-500"> · {unmatchedCount} unmatched</span>}
              </span>
              <button
                onClick={handleImport}
                disabled={importing || matchedCount === 0}
                className="inline-flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:opacity-90 text-sm font-medium disabled:opacity-50"
              >
                <Upload className="w-4 h-4" />
                {importing ? "Importing…" : `Import ${matchedCount} Records`}
              </button>
            </div>

            <div className="overflow-x-auto rounded-lg border border-gray-100">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="bg-[#f6f3ee] text-[#1a1814]">
                    <th className="text-left px-3 py-2 border-b border-gray-200">Emp Code</th>
                    <th className="text-left px-3 py-2 border-b border-gray-200">Date</th>
                    <th className="text-left px-3 py-2 border-b border-gray-200">Time In</th>
                    <th className="text-left px-3 py-2 border-b border-gray-200">Time Out</th>
                    <th className="text-left px-3 py-2 border-b border-gray-200">Matched Employee</th>
                  </tr>
                </thead>
                <tbody>
                  {parsed.map((row, i) => (
                    <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-[#faf9f7]"}>
                      <td className="px-3 py-1.5 border-b border-gray-100 font-mono">{row.employee_code}</td>
                      <td className="px-3 py-1.5 border-b border-gray-100 whitespace-nowrap">{fmtDate(row.date)}</td>
                      <td className="px-3 py-1.5 border-b border-gray-100">{row.time_in || "—"}</td>
                      <td className="px-3 py-1.5 border-b border-gray-100">{row.time_out || "—"}</td>
                      <td className={`px-3 py-1.5 border-b border-gray-100 ${row.matched_name ? "text-green-700" : "text-red-500"}`}>
                        {row.matched_name ?? "Not found"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Future integration card */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2 font-semibold text-blue-800">
          <Info className="w-5 h-5" />
          Planned Biometric Device Integration
        </div>
        <ul className="text-sm text-blue-700 space-y-1.5 ml-7">
          <li>ZKTeco / FingerTec TCP/IP pull (port 4370)</li>
          <li>CSV file export from device management software</li>
          <li>Automatic daily sync via scheduled background task</li>
          <li>Real-time WebSocket push (planned)</li>
        </ul>
        <p className="text-xs text-blue-500 ml-7">
          Until device integration is available, use the CSV upload above or enter records manually.
        </p>
      </div>
    </div>
  )
}
