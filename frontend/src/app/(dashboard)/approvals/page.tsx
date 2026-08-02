"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { CheckCheck, GitBranch } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"

type StepHint = {
  step_order: number
  approver_role?: string | null
  approver_user_id?: number | null
  min_amount?: number | null
}

type Req = {
  id: number
  document_type: string
  document_id: number
  status: string
  amount?: number
  current_step?: number
  notes?: string
  step?: StepHint
}

function docHref(r: Req): string {
  if (r.document_type === "invoice") return `/invoices/${r.document_id}`
  if (r.document_type === "bill") return `/bills/${r.document_id}`
  return "/approvals"
}

export default function ApprovalsPage() {
  const fmt = useFmt()
  const [items, setItems] = useState<Req[]>([])
  const [notes, setNotes] = useState<Record<number, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = () =>
    apiFetch<Req[]>("/api/approvals")
      .then(setItems)
      .catch(() => setItems([]))
  useEffect(() => { load() }, [])

  const act = async (id: number, action: "approve" | "reject") => {
    setError(null)
    setBusyId(id)
    try {
      await apiFetch(`/api/approvals/${id}/${action}`, {
        method: "POST",
        body: JSON.stringify({
          notes: notes[id] || (action === "reject" ? "Rejected" : null),
        }),
      })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <CheckCheck className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="font-serif text-2xl text-[var(--text-primary)]">Approvals</h1>
            <p className="text-sm text-[var(--text-muted)]">Documents waiting for your decision.</p>
          </div>
        </div>
        <Link
          href="/approvals/workflows"
          className="print:hidden inline-flex items-center gap-1.5 text-sm text-[var(--primary)] hover:underline"
        >
          <GitBranch className="w-4 h-4" /> Workflows
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {items.map((r) => (
        <div
          key={r.id}
          className="border border-[var(--border)] rounded-xl p-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between bg-white"
        >
          <div className="min-w-0">
            <Link href={docHref(r)} className="font-medium capitalize text-[var(--text-primary)] hover:underline">
              {r.document_type} #{r.document_id}
            </Link>
            <div className="text-xs text-[var(--text-muted)] mt-0.5">
              Request #{r.id}
              {r.amount != null && <> · {fmt(r.amount)}</>}
              {r.step && (
                <>
                  {" · "}
                  {r.step.approver_role
                    ? `Role: ${r.step.approver_role}`
                    : r.step.approver_user_id
                      ? `User #${r.step.approver_user_id}`
                      : `Step ${r.current_step ?? 0}`}
                </>
              )}
            </div>
            <input
              className="mt-2 border border-[var(--border)] rounded px-2 py-1 text-sm w-full max-w-xs print:hidden"
              placeholder="Notes"
              value={notes[r.id] || ""}
              onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
            />
          </div>
          <div className="flex gap-2 print:hidden">
            <button
              type="button"
              disabled={busyId === r.id}
              className="bg-[#b8943f] px-3 py-1.5 rounded text-sm font-medium disabled:opacity-60"
              onClick={() => act(r.id, "approve")}
            >
              Approve
            </button>
            <button
              type="button"
              disabled={busyId === r.id}
              className="border border-[var(--border)] px-3 py-1.5 rounded text-sm disabled:opacity-60"
              onClick={() => act(r.id, "reject")}
            >
              Reject
            </button>
          </div>
        </div>
      ))}
      {!items.length && (
        <p className="text-sm text-[var(--text-muted)]">No pending approvals for you.</p>
      )}
    </div>
  )
}
