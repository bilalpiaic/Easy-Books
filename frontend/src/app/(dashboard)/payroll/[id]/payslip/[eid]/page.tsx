"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt, useCurrency } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface PayslipData {
  run: {
    id: number
    period_start: string
    period_end: string
    pay_date: string
    jv_number: string | null
    status: string
  }
  employee: {
    id: number
    employee_code: string
    name: string
    department: string | null
    designation: string | null
    bank_account: string | null
    bank_name: string | null
  }
  earnings: { name: string; code: string; amount: number }[]
  deductions: { name: string; code: string; amount: number }[]
  leave?: { leave_type: string; code: string; is_paid: boolean; from_date: string; to_date: string; days: number }[]
  unpaid_leave_days?: number
  gross_earnings: number
  total_deductions: number
  net_pay: number
}

export default function PayslipPage() {
  const { t } = useTranslation()
  const params = useParams()
  const runId = params.id as string
  const eid = params.eid as string
  const fmt = useFmt()
  const currency = useCurrency()

  const [data, setData] = useState<PayslipData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    apiFetch<PayslipData>(`/api/payroll/runs/${runId}/payslip/${eid}`)
      .then(setData)
      .catch(() => setError("Failed to load payslip"))
      .finally(() => setLoading(false))
  }, [runId, eid])

  if (loading) return <div className="p-8 text-[var(--text-primary)]/60">Loading…</div>
  if (!data)   return <div className="p-8 text-red-500">{error || "Payslip not found"}</div>

  return (
    <div className="max-w-2xl space-y-4">
      <PrintHeader
        title="Pay Slip"
        subtitle={`Period: ${fmtDate(data.run.period_start)} – ${fmtDate(data.run.period_end)}`}
      />

      {/* ── Screen-only toolbar ───────────────────────────────────── */}
      <div className="print:hidden flex items-center justify-between">
        <Link
          href={`/payroll/${runId}`}
          className="inline-flex items-center gap-2 text-[var(--primary)] hover:underline text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          {t("common.back", "Back to Payroll Run")}
        </Link>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm hover:bg-[var(--bg-page)]"
        >
          <Printer className="w-4 h-4" /> {t("common.print", "Print")}
        </button>
      </div>

      {/* ── Screen card view ─────────────────────────────────────── */}
      <div className="print:hidden bg-white rounded-xl border border-[var(--border)] shadow-sm p-6 space-y-6">
        <div className="border-b border-[var(--border)] pb-4">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">{data.employee.name}</h2>
          <p className="text-xs text-[var(--text-primary)]/55">
            {data.employee.employee_code}
            {data.employee.designation ? ` · ${data.employee.designation}` : ""}
            {data.employee.department  ? ` — ${data.employee.department}`  : ""}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="space-y-1.5">
            <ScreenRow label="Pay Date"    value={fmtDate(data.run.pay_date)} />
            {data.employee.bank_name    && <ScreenRow label="Bank"    value={data.employee.bank_name} />}
            {data.employee.bank_account && <ScreenRow label="Account" value={data.employee.bank_account} />}
          </div>
          <div className="space-y-1.5">
            <ScreenRow label="Gross Earnings"   value={`${currency} ${fmt(data.gross_earnings)}`} />
            <ScreenRow label="Total Deductions"  value={`${currency} ${fmt(data.total_deductions)}`} />
            <ScreenRow label="Net Pay"           value={`${currency} ${fmt(data.net_pay)}`} bold />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 text-sm">
          <div>
            <h4 className="font-semibold text-[var(--text-primary)] border-b border-[var(--border)] pb-2 mb-2">
              Earnings
            </h4>
            {data.earnings.length === 0
              ? <p className="text-[var(--text-primary)]/45 text-xs italic">No earnings recorded</p>
              : data.earnings.map((e, i) => <ScreenRow key={i} label={e.name} value={fmt(e.amount)} />)
            }
          </div>
          <div>
            <h4 className="font-semibold text-[var(--text-primary)] border-b border-[var(--border)] pb-2 mb-2">
              Deductions
            </h4>
            {data.deductions.length === 0
              ? <p className="text-[var(--text-primary)]/45 text-xs italic">No deductions recorded</p>
              : data.deductions.map((d, i) => <ScreenRow key={i} label={d.name} value={fmt(d.amount)} />)
            }
          </div>
        </div>
      </div>

      {/* ── Print-only document — pure dot-matrix article ─────────── */}
      <article className="hidden print:block text-[var(--text-primary)]">

        {/* Employee / period info strip */}
        <div className="gb-meta-strip">
          <div>
            <div className="gb-box-label">Employee</div>
            <div className="gb-box-value">{data.employee.name}</div>
            <div className="gb-box-sub">
              {data.employee.employee_code}
              {data.employee.designation ? ` · ${data.employee.designation}` : ""}
              {data.employee.department  ? ` — ${data.employee.department}`  : ""}
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="gb-box-label">Pay Period</div>
            <div className="gb-box-sub">
              {fmtDate(data.run.period_start)} — {fmtDate(data.run.period_end)}
            </div>
            <div className="gb-box-label" style={{ marginTop: "4pt" }}>Pay Date</div>
            <div className="gb-box-sub">{fmtDate(data.run.pay_date)}</div>
            {data.run.jv_number && (
              <>
                <div className="gb-box-label" style={{ marginTop: "4pt" }}>Voucher</div>
                <div className="gb-box-sub">{data.run.jv_number}</div>
              </>
            )}
          </div>
        </div>

        {/* Earnings + Deductions side by side */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16pt", marginBottom: "8pt" }}>

          <div>
            <h2>Earnings ({currency})</h2>
            <table>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>Component</th>
                  <th style={{ textAlign: "right" }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {data.earnings.length === 0
                  ? <tr><td colSpan={2} style={{ fontStyle: "italic" }}>No earnings</td></tr>
                  : data.earnings.map((e, i) => (
                    <tr key={i}>
                      <td>{e.name}</td>
                      <td style={{ textAlign: "right" }}>{fmt(e.amount)}</td>
                    </tr>
                  ))
                }
              </tbody>
              <tfoot>
                <tr>
                  <td>Gross Earnings</td>
                  <td style={{ textAlign: "right" }}>{fmt(data.gross_earnings)}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          <div>
            <h2>Deductions ({currency})</h2>
            <table>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>Component</th>
                  <th style={{ textAlign: "right" }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {data.deductions.length === 0
                  ? <tr><td colSpan={2} style={{ fontStyle: "italic" }}>No deductions</td></tr>
                  : data.deductions.map((d, i) => (
                    <tr key={i}>
                      <td>{d.name}</td>
                      <td style={{ textAlign: "right" }}>{fmt(d.amount)}</td>
                    </tr>
                  ))
                }
              </tbody>
              <tfoot>
                <tr>
                  <td>Total Deductions</td>
                  <td style={{ textAlign: "right" }}>{fmt(data.total_deductions)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        {/* Net Pay — double-ruled box */}
        <div className="gb-amount-box">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong style={{ textTransform: "uppercase", letterSpacing: "0.1em", fontSize: "9.5pt" }}>
              Net Pay
            </strong>
            <strong style={{ fontSize: "11pt" }}>
              {currency} {fmt(data.net_pay)}
            </strong>
          </div>
        </div>

        {/* Bank details strip */}
        {data.employee.bank_account && (
          <div className="gb-from-strip">
            <span className="gb-box-label">Pay to Account</span>
            <span>
              {data.employee.bank_account}
              {data.employee.bank_name ? ` · ${data.employee.bank_name}` : ""}
            </span>
          </div>
        )}

        {/* Signature bar */}
        <div className="gb-sig">
          <div className="gb-sig-item"><div className="gb-sig-line">Employee Signature</div></div>
          <div className="gb-sig-item"><div className="gb-sig-line">Prepared By</div></div>
          <div className="gb-sig-item"><div className="gb-sig-line">Authorized By</div></div>
        </div>

      </article>
    </div>
  )
}

function ScreenRow({ label, value, bold = false }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-[var(--text-primary)]/65">{label}</span>
      <span className={`font-mono ${bold ? "font-bold" : ""}`}>{value}</span>
    </div>
  )
}
