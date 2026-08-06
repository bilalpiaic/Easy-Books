"use client"

import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

interface LeaveType { id: number; code: string; name: string; is_paid: boolean; annual_entitlement: number }
interface Emp { id: number; name: string; employee_code: string }
interface Req {
  id: number
  employee_name?: string
  leave_type_name?: string
  from_date: string
  to_date: string
  days: number
  status: string
  is_paid?: boolean
}

export default function LeavePage() {
  const [types, setTypes] = useState<LeaveType[]>([])
  const [emps, setEmps] = useState<Emp[]>([])
  const [reqs, setReqs] = useState<Req[]>([])
  const [error, setError] = useState<string | null>(null)
  const [empId, setEmpId] = useState<number | "">("")
  const [typeId, setTypeId] = useState<number | "">("")
  const [from, setFrom] = useState("")
  const [to, setTo] = useState("")
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    Promise.all([
      apiFetch<LeaveType[]>("/api/leave/types"),
      apiFetch<Emp[]>("/api/employees"),
      apiFetch<Req[]>("/api/leave/requests"),
    ]).then(([t, e, r]) => {
      setTypes(t)
      setEmps(e)
      setReqs(r)
      if (t.length && typeId === "") setTypeId(t[0].id)
      if (e.length && empId === "") setEmpId(e[0].id)
    }).catch((err) => setError(err instanceof Error ? err.message : "Load failed"))
  }, [empId, typeId])

  useEffect(() => { load() }, [load])

  const seed = async () => {
    setBusy(true)
    try {
      await apiFetch("/api/leave/types/seed-defaults", { method: "POST" })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed failed")
    } finally { setBusy(false) }
  }

  const create = async () => {
    if (!empId || !typeId || !from || !to) {
      setError("Fill employee, type, and dates")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await apiFetch("/api/leave/requests", {
        method: "POST",
        body: JSON.stringify({
          employee_id: empId,
          leave_type_id: typeId,
          from_date: from,
          to_date: to,
        }),
      })
      setFrom(""); setTo("")
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed")
    } finally { setBusy(false) }
  }

  const act = async (id: number, action: "approve" | "reject") => {
    setBusy(true)
    setError(null)
    try {
      await apiFetch(`/api/leave/requests/${id}/${action}`, {
        method: "POST",
        body: action === "reject" ? JSON.stringify({ reason: "Rejected" }) : undefined,
      })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed`)
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Leave</h1>
          <p className="text-sm text-[var(--text-primary)]/55">
            Types, requests, and unpaid leave that feeds payslip LOP.
          </p>
        </div>
        <button type="button" disabled={busy} onClick={seed} className="text-sm border px-3 py-2 rounded-lg">
          Seed AL/SL/UL
        </button>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-3 py-2 text-sm">{error}</div>}

      <div className="bg-white border border-[var(--text-primary)]/10 rounded-2xl p-4 space-y-3">
        <h2 className="font-semibold text-sm">New request</h2>
        <div className="grid sm:grid-cols-2 gap-2">
          <select className="border rounded-lg px-3 py-2 text-sm" value={empId === "" ? "" : String(empId)} onChange={(e) => setEmpId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Employee…</option>
            {emps.map((e) => <option key={e.id} value={e.id}>{e.employee_code} — {e.name}</option>)}
          </select>
          <select className="border rounded-lg px-3 py-2 text-sm" value={typeId === "" ? "" : String(typeId)} onChange={(e) => setTypeId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Leave type…</option>
            {types.map((t) => <option key={t.id} value={t.id}>{t.code} — {t.name}{t.is_paid ? "" : " (unpaid)"}</option>)}
          </select>
          <input type="date" className="border rounded-lg px-3 py-2 text-sm" value={from} onChange={(e) => setFrom(e.target.value)} />
          <input type="date" className="border rounded-lg px-3 py-2 text-sm" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
        <button type="button" disabled={busy} onClick={create} className="bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40">
          Submit request
        </button>
      </div>

      <div className="table-freeze overflow-x-auto bg-white border border-[var(--text-primary)]/10 rounded-xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-[var(--text-primary)]/60">
              <th className="px-3 py-2">Employee</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Dates</th>
              <th className="px-3 py-2">Days</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 print:hidden">Actions</th>
            </tr>
          </thead>
          <tbody>
            {reqs.map((r) => (
              <tr key={r.id} className="border-b border-[var(--text-primary)]/5">
                <td className="px-3 py-2">{r.employee_name}</td>
                <td className="px-3 py-2">{r.leave_type_name}{r.is_paid === false ? " · unpaid" : ""}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.from_date)} – {fmtDate(r.to_date)}</td>
                <td className="px-3 py-2">{r.days}</td>
                <td className="px-3 py-2 capitalize">{r.status}</td>
                <td className="px-3 py-2 print:hidden">
                  {r.status === "pending" && (
                    <span className="flex gap-2">
                      <button type="button" disabled={busy} className="text-[var(--primary)] text-xs font-medium" onClick={() => act(r.id, "approve")}>Approve</button>
                      <button type="button" disabled={busy} className="text-red-700 text-xs" onClick={() => act(r.id, "reject")}>Reject</button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {!reqs.length && (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--text-primary)]/45">No leave requests.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
