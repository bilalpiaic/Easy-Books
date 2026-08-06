"use client"

import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt, useCurrency } from "@/context/SettingsContext"

interface Emp { id: number; name: string; employee_code: string }
interface Claim {
  id: number
  number: string
  employee_name?: string
  claim_date: string
  description?: string
  status: string
  total: number
  bill_id?: number | null
  lines: { description: string; amount: number }[]
}

export default function ExpenseClaimsPage() {
  const fmt = useFmt()
  const currency = useCurrency()
  const [emps, setEmps] = useState<Emp[]>([])
  const [claims, setClaims] = useState<Claim[]>([])
  const [error, setError] = useState<string | null>(null)
  const [empId, setEmpId] = useState<number | "">("")
  const [date, setDate] = useState("")
  const [desc, setDesc] = useState("")
  const [lineDesc, setLineDesc] = useState("Travel")
  const [amount, setAmount] = useState("")
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    Promise.all([
      apiFetch<Emp[]>("/api/employees"),
      apiFetch<Claim[]>("/api/expense-claims"),
    ]).then(([e, c]) => {
      setEmps(e)
      setClaims(c)
      if (e.length && empId === "") setEmpId(e[0].id)
    }).catch((err) => setError(err instanceof Error ? err.message : "Load failed"))
  }, [empId])

  useEffect(() => { load() }, [load])

  const create = async () => {
    if (!empId || !date || !amount) {
      setError("Fill employee, date, and amount")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await apiFetch("/api/expense-claims", {
        method: "POST",
        body: JSON.stringify({
          employee_id: empId,
          claim_date: date,
          description: desc || undefined,
          lines: [{ description: lineDesc || "Expense", amount: Number(amount) }],
        }),
      })
      setAmount("")
      setDesc("")
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed")
    } finally {
      setBusy(false)
    }
  }

  const act = async (id: number, action: "approve" | "reject" | "cancel") => {
    setBusy(true)
    setError(null)
    try {
      await apiFetch(`/api/expense-claims/${id}/${action}`, {
        method: "POST",
        body: action === "reject" ? JSON.stringify({ reason: "Rejected" }) : undefined,
      })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Expense Claims</h1>
        <p className="text-sm text-[var(--text-primary)]/55">
          Employee reimbursements — approve to create an AP bill.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 print:hidden">
        <select className="border rounded-lg px-3 py-2 text-sm" value={empId} onChange={(e) => setEmpId(Number(e.target.value))}>
          {emps.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        <input type="date" className="border rounded-lg px-3 py-2 text-sm" value={date} onChange={(e) => setDate(e.target.value)} />
        <input className="border rounded-lg px-3 py-2 text-sm" placeholder="Description" value={desc} onChange={(e) => setDesc(e.target.value)} />
        <input className="border rounded-lg px-3 py-2 text-sm w-28" placeholder="Line" value={lineDesc} onChange={(e) => setLineDesc(e.target.value)} />
        <input className="border rounded-lg px-3 py-2 text-sm w-28" placeholder="Amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <button type="button" disabled={busy} onClick={create} className="bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
          Submit claim
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="overflow-x-auto table-freeze">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-[var(--text-primary)]/60">
              <th className="py-2 pr-3">Number</th>
              <th className="py-2 pr-3">Employee</th>
              <th className="py-2 pr-3">Date</th>
              <th className="py-2 pr-3 text-right">{currency}</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c) => (
              <tr key={c.id} className="border-b border-[var(--border)]">
                <td className="py-2 pr-3 whitespace-nowrap">{c.number}</td>
                <td className="py-2 pr-3">{c.employee_name}</td>
                <td className="py-2 pr-3 whitespace-nowrap">{fmtDate(c.claim_date)}</td>
                <td className="py-2 pr-3 text-right whitespace-nowrap">{fmt(c.total)}</td>
                <td className="py-2 pr-3">{c.status}{c.bill_id ? ` · bill #${c.bill_id}` : ""}</td>
                <td className="py-2 print:hidden space-x-2">
                  {(c.status === "submitted" || c.status === "draft") && (
                    <>
                      <button type="button" className="text-xs text-[var(--primary)]" onClick={() => act(c.id, "approve")}>Approve</button>
                      <button type="button" className="text-xs text-red-600" onClick={() => act(c.id, "reject")}>Reject</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {claims.length === 0 && (
              <tr><td colSpan={6} className="py-6 text-[var(--text-primary)]/45">No claims yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
