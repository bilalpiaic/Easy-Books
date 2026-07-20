"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, CheckCircle, Send, Printer, XCircle, BookOpen, Edit2, Save, X } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt, useCurrency } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"
import { useMessages } from "@/context/MessageContext"

interface LineDetail {
  id: number
  component_id: number
  component_name: string
  component_type: string
  amount: number
}

interface RunLine {
  id: number
  employee_id: number
  employee_name: string
  employee_code: string
  gross_earnings: number
  total_deductions: number
  net_pay: number
  details: LineDetail[]
}

interface RunDetail {
  id: number
  period_start: string
  period_end: string
  pay_date: string
  status: string
  notes: string | null
  jv_number: string | null
  transaction_id: number | null
  created_at: string | null
  lines: RunLine[]
  total_gross: number
  total_deductions: number
  total_net: number
}

const STATUS_COLOR: Record<string, string> = {
  draft:    "text-gray-500",
  approved: "text-blue-600",
  posted:   "text-emerald-600",
  void:     "text-red-400",
}

export default function PayrollRunPage() {
  const { confirm } = useMessages()
  const { t } = useTranslation()
  const params = useParams()
  const runId = params.id as string
  const fmt = useFmt()
  const currency = useCurrency()

  const [run, setRun] = useState<RunDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [actionLoading, setActionLoading] = useState("")
  const [editMode, setEditMode] = useState(false)
  const [editLines, setEditLines] = useState<RunLine[]>([])
  const [expandedEmployees, setExpandedEmployees] = useState<Set<number>>(new Set())

  const loadRun = () => {
    setLoading(true)
    apiFetch<RunDetail>(`/api/payroll/runs/${runId}`)
      .then(data => {
        setRun(data)
        setEditLines(data.lines)
      })
      .catch(() => setError("Failed to load run"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadRun() }, [runId])

  const doAction = async (action: string) => {
    setActionLoading(action)
    setError("")
    try {
      await apiFetch(`/api/payroll/runs/${runId}/${action}`, { method: "POST" })
      loadRun()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action}`)
    } finally {
      setActionLoading("")
    }
  }

  const saveEdits = async () => {
    setActionLoading("save")
    setError("")
    try {
      await apiFetch(`/api/payroll/runs/${runId}/lines`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lines: editLines.map(l => ({
            employee_id: l.employee_id,
            gross_earnings: l.gross_earnings,
            total_deductions: l.total_deductions,
            net_pay: l.net_pay,
          }))
        }),
      })
      setEditMode(false)
      loadRun()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setActionLoading("")
    }
  }

  const toggleExpand = (empId: number) => {
    setExpandedEmployees(prev => {
      const next = new Set(prev)
      if (next.has(empId)) next.delete(empId)
      else next.add(empId)
      return next
    })
  }

  if (loading) return <div className="p-8 text-gray-400">Loading...</div>
  if (!run) return <div className="p-8 text-red-500">{error || "Run not found"}</div>

  const lines = editMode ? editLines : run.lines

  return (
    <div className="space-y-6">
      <PrintHeader title={`Payroll — ${run.jv_number ?? "#" + run.id}`} orientation="landscape" />

      <div className="print:hidden flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Link href="/payroll" className="text-[var(--primary)] hover:underline mt-1">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">
              {run.jv_number ? `Payroll ${run.jv_number}` : `Payroll Run #${run.id}`}
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Period: {fmtDate(run.period_start)} – {fmtDate(run.period_end)} &nbsp;·&nbsp;
              Pay Date: {fmtDate(run.pay_date)} &nbsp;·&nbsp;
              <span className={`capitalize font-medium ${STATUS_COLOR[run.status] ?? ""}`}>{run.status}</span>
            </p>
            {run.notes && <p className="text-sm text-gray-400 mt-0.5">{run.notes}</p>}
          </div>
        </div>

        {/* Action buttons by status */}
        <div className="flex flex-wrap gap-2">
          {run.status === "draft" && !editMode && (
            <>
              <button
                onClick={() => { setEditMode(true); setEditLines(run.lines) }}
                className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
              >
                <Edit2 className="w-4 h-4" /> Edit Lines
              </button>
              <button
                onClick={() => doAction("approve")}
                disabled={!!actionLoading}
                className="inline-flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                <CheckCircle className="w-4 h-4" />
                {actionLoading === "approve" ? "Approving..." : "Approve"}
              </button>
            </>
          )}
          {run.status === "draft" && editMode && (
            <>
              <button
                onClick={saveEdits}
                disabled={!!actionLoading}
                className="inline-flex items-center gap-1 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm hover:opacity-90 disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {actionLoading === "save" ? "Saving..." : "Save Changes"}
              </button>
              <button
                onClick={() => { setEditMode(false); setEditLines(run.lines) }}
                className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
              >
                <X className="w-4 h-4" /> Cancel
              </button>
            </>
          )}
          {run.status === "approved" && (
            <button
              onClick={() => doAction("post")}
              disabled={!!actionLoading}
              className="inline-flex items-center gap-1 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-700 disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
              {actionLoading === "post" ? "Posting..." : "Post to GL"}
            </button>
          )}
          {run.status === "posted" && (
            <>
              {run.transaction_id && (
                <Link
                  href={`/journal/${run.transaction_id}`}
                  className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
                >
                  <BookOpen className="w-4 h-4" /> View Journal Entry
                </Link>
              )}
              <button
                onClick={() => window.print()}
                className="inline-flex items-center gap-1 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
              >
                <Printer className="w-4 h-4" /> Print
              </button>
              <button
                onClick={async () => {
                  const ok = await confirm({
                    title: "Void this payroll run?",
                    message: "This will create a reversing journal entry.",
                    confirmLabel: "Void",
                    danger: true,
                  })
                  if (ok) doAction("void")
                }}
                disabled={!!actionLoading}
                className="inline-flex items-center gap-1 px-3 py-2 border border-red-200 text-red-600 rounded-lg text-sm hover:bg-red-50 disabled:opacity-50"
              >
                <XCircle className="w-4 h-4" />
                {actionLoading === "void" ? "Voiding..." : "Void"}
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm print:hidden">{error}</div>
      )}

      {/* Lines table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] border-b border-gray-100">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]">Employee</th>
                <th className="text-right px-4 py-3 font-semibold text-[var(--text-primary)]">Gross Earnings ({currency})</th>
                <th className="text-right px-4 py-3 font-semibold text-[var(--text-primary)]">Deductions ({currency})</th>
                <th className="text-right px-4 py-3 font-semibold text-[var(--text-primary)]">Net Pay ({currency})</th>
                <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)] print:hidden">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {lines.map((line, idx) => (
                <>
                  <tr
                    key={line.employee_id}
                    className="hover:bg-[var(--bg-page)]/50 cursor-pointer"
                    onClick={() => !editMode && toggleExpand(line.employee_id)}
                  >
                    <td className="px-4 py-3">
                      <span className="font-medium text-[var(--text-primary)]">{line.employee_name}</span>
                      <span className="text-xs text-gray-400 ml-2">{line.employee_code}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {editMode ? (
                        <input
                          type="number" min={0} step="0.01"
                          value={editLines[idx].gross_earnings}
                          onChange={e => {
                            const v = parseFloat(e.target.value) || 0
                            setEditLines(prev => prev.map((l, i) => i === idx
                              ? { ...l, gross_earnings: v, net_pay: v - l.total_deductions }
                              : l
                            ))
                          }}
                          onClick={e => e.stopPropagation()}
                          className="border border-gray-200 rounded px-2 py-1 text-sm text-right w-28 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
                        />
                      ) : fmt(line.gross_earnings)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {editMode ? (
                        <input
                          type="number" min={0} step="0.01"
                          value={editLines[idx].total_deductions}
                          onChange={e => {
                            const v = parseFloat(e.target.value) || 0
                            setEditLines(prev => prev.map((l, i) => i === idx
                              ? { ...l, total_deductions: v, net_pay: l.gross_earnings - v }
                              : l
                            ))
                          }}
                          onClick={e => e.stopPropagation()}
                          className="border border-gray-200 rounded px-2 py-1 text-sm text-right w-28 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
                        />
                      ) : fmt(line.total_deductions)}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold">
                      {editMode ? fmt(editLines[idx].net_pay) : fmt(line.net_pay)}
                    </td>
                    <td className="px-4 py-3 print:hidden">
                      <Link
                        href={`/payroll/${runId}/payslip/${line.employee_id}`}
                        className="text-[var(--primary)] hover:underline text-xs font-medium"
                        onClick={e => e.stopPropagation()}
                      >
                        Payslip
                      </Link>
                    </td>
                  </tr>
                  {expandedEmployees.has(line.employee_id) && !editMode && (
                    <tr key={`detail-${line.employee_id}`} className="bg-gray-50/50">
                      <td colSpan={5} className="px-8 py-3">
                        <div className="grid grid-cols-2 gap-4 text-xs">
                          <div>
                            <p className="font-medium text-gray-600 mb-1">Earnings</p>
                            {line.details.filter(d => d.component_type === "earnings").map(d => (
                              <div key={d.id} className="flex justify-between py-0.5">
                                <span className="text-gray-500">{d.component_name}</span>
                                <span className="font-medium">{fmt(d.amount)}</span>
                              </div>
                            ))}
                            {line.details.filter(d => d.component_type === "earnings").length === 0 && (
                              <span className="text-gray-300">None</span>
                            )}
                          </div>
                          <div>
                            <p className="font-medium text-gray-600 mb-1">Deductions</p>
                            {line.details.filter(d => d.component_type !== "earnings").map(d => (
                              <div key={d.id} className="flex justify-between py-0.5">
                                <span className="text-gray-500">{d.component_name}</span>
                                <span className="font-medium">{fmt(d.amount)}</span>
                              </div>
                            ))}
                            {line.details.filter(d => d.component_type !== "earnings").length === 0 && (
                              <span className="text-gray-300">None</span>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
            <tfoot className="border-t-2 border-gray-200 bg-[var(--bg-page)]">
              <tr>
                <td className="px-4 py-3 font-bold text-[var(--text-primary)]">Total</td>
                <td className="px-4 py-3 text-right font-bold">
                  {editMode
                    ? fmt(editLines.reduce((s, l) => s + l.gross_earnings, 0))
                    : fmt(run.total_gross)}
                </td>
                <td className="px-4 py-3 text-right font-bold">
                  {editMode
                    ? fmt(editLines.reduce((s, l) => s + l.total_deductions, 0))
                    : fmt(run.total_deductions)}
                </td>
                <td className="px-4 py-3 text-right font-bold text-emerald-600">
                  {editMode
                    ? fmt(editLines.reduce((s, l) => s + l.net_pay, 0))
                    : fmt(run.total_net)}
                </td>
                <td className="px-4 py-3 print:hidden"></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  )
}
