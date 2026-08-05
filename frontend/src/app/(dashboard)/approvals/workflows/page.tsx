"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { GitBranch, Plus, Trash2 } from "lucide-react"
import { apiFetch } from "@/lib/api"

type Step = {
  id?: number
  step_order: number
  approver_role?: string | null
  approver_user_id?: number | null
  min_amount?: number | null
  timeout_hours?: number | null
}

type Workflow = {
  id: number
  document_type: string
  name: string
  is_active: boolean
  steps: Step[]
}

type StepDraft = {
  step_order: number
  mode: "role" | "user"
  approver_role: string
  approver_user_id: string
  min_amount: string
}

type DocTypeOption = {
  key: string
  label: string
  module?: string
}

const ROLES = ["owner", "admin", "accountant"] as const

function emptyStep(order: number): StepDraft {
  return {
    step_order: order,
    mode: "role",
    approver_role: "owner",
    approver_user_id: "",
    min_amount: "",
  }
}

export default function ApprovalWorkflowsPage() {
  const [items, setItems] = useState<Workflow[]>([])
  const [docTypes, setDocTypes] = useState<DocTypeOption[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState("Invoice approval")
  const [documentType, setDocumentType] = useState<string>("invoice")
  const [steps, setSteps] = useState<StepDraft[]>([emptyStep(0)])

  const load = () =>
    apiFetch<Workflow[]>("/api/approvals/workflows")
      .then(setItems)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))

  useEffect(() => {
    load()
    apiFetch<DocTypeOption[]>("/api/approvals/document-types")
      .then((rows) => {
        setDocTypes(rows)
        setDocumentType((current) =>
          rows.some((r) => r.key === current) ? current : (rows[0]?.key ?? current),
        )
      })
      .catch(() => {
        setDocTypes([
          { key: "invoice", label: "Sales Invoice" },
          { key: "bill", label: "Purchase Bill" },
          { key: "purchase_order", label: "Purchase Order" },
          { key: "journal", label: "Journal Entry" },
        ])
      })
  }, [])

  const save = async () => {
    setError(null)
    setBusy(true)
    try {
      const payload = {
        document_type: documentType,
        name,
        is_active: true,
        steps: steps.map((s, i) => ({
          step_order: i,
          approver_role: s.mode === "role" ? s.approver_role : null,
          approver_user_id: s.mode === "user" && s.approver_user_id
            ? Number(s.approver_user_id)
            : null,
          min_amount: s.min_amount !== "" ? Number(s.min_amount) : null,
        })),
      }
      await apiFetch("/api/approvals/workflows", {
        method: "POST",
        body: JSON.stringify(payload),
      })
      setName("Invoice approval")
      setSteps([emptyStep(0)])
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create")
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: number) => {
    setError(null)
    try {
      await apiFetch(`/api/approvals/workflows/${id}`, { method: "DELETE" })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete")
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <GitBranch className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="font-serif text-2xl text-[var(--text-primary)]">Approval Workflows</h1>
            <p className="text-sm text-[var(--text-muted)]">
              Multi-step chains by document type and amount threshold.
            </p>
          </div>
        </div>
        <Link href="/approvals" className="text-sm text-[var(--primary)] hover:underline">
          ← Inbox
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-bold text-[var(--text-primary)]">New workflow</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="text-sm space-y-1">
            <span className="text-xs text-[var(--text-muted)]">Name</span>
            <input
              className="w-full border border-[var(--border)] rounded-lg px-3 py-2"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label className="text-sm space-y-1">
            <span className="text-xs text-[var(--text-muted)]">Document type</span>
            <select
              className="w-full border border-[var(--border)] rounded-lg px-3 py-2 bg-white"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
            >
              {docTypes.map((t) => (
                <option key={t.key} value={t.key}>{t.label}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="space-y-3">
          {steps.map((s, idx) => (
            <div key={idx} className="border border-[var(--border)] rounded-lg p-3 grid grid-cols-1 sm:grid-cols-4 gap-2 items-end">
              <label className="text-sm space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Assign by</span>
                <select
                  className="w-full border border-[var(--border)] rounded px-2 py-1.5 bg-white"
                  value={s.mode}
                  onChange={(e) => {
                    const next = [...steps]
                    next[idx] = { ...s, mode: e.target.value as "role" | "user" }
                    setSteps(next)
                  }}
                >
                  <option value="role">Role</option>
                  <option value="user">User ID</option>
                </select>
              </label>
              {s.mode === "role" ? (
                <label className="text-sm space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">Role</span>
                  <select
                    className="w-full border border-[var(--border)] rounded px-2 py-1.5 bg-white"
                    value={s.approver_role}
                    onChange={(e) => {
                      const next = [...steps]
                      next[idx] = { ...s, approver_role: e.target.value }
                      setSteps(next)
                    }}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <label className="text-sm space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">User ID</span>
                  <input
                    className="w-full border border-[var(--border)] rounded px-2 py-1.5"
                    value={s.approver_user_id}
                    onChange={(e) => {
                      const next = [...steps]
                      next[idx] = { ...s, approver_user_id: e.target.value }
                      setSteps(next)
                    }}
                  />
                </label>
              )}
              <label className="text-sm space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Min amount (blank = always)</span>
                <input
                  type="number"
                  className="w-full border border-[var(--border)] rounded px-2 py-1.5"
                  value={s.min_amount}
                  onChange={(e) => {
                    const next = [...steps]
                    next[idx] = { ...s, min_amount: e.target.value }
                    setSteps(next)
                  }}
                />
              </label>
              <button
                type="button"
                className="text-sm text-red-700 inline-flex items-center gap-1 justify-self-start sm:justify-self-end"
                onClick={() => setSteps(steps.filter((_, i) => i !== idx).map((x, i) => ({ ...x, step_order: i })))}
                disabled={steps.length <= 1}
              >
                <Trash2 className="w-4 h-4" /> Remove
              </button>
            </div>
          ))}
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 border border-[var(--border)] px-3 py-1.5 rounded text-sm"
            onClick={() => setSteps([...steps, emptyStep(steps.length)])}
          >
            <Plus className="w-4 h-4" /> Add step
          </button>
          <button
            type="button"
            disabled={busy || !name.trim()}
            className="bg-[#b8943f] px-3 py-1.5 rounded text-sm font-medium disabled:opacity-60"
            onClick={save}
          >
            Create workflow
          </button>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-bold text-[var(--text-primary)]">Existing</h2>
        {items.map((wf) => (
          <div key={wf.id} className="bg-white border border-[var(--border)] rounded-xl p-4 flex justify-between gap-3">
            <div>
              <div className="font-medium">{wf.name}</div>
              <div className="text-xs text-[var(--text-muted)]">
                {docTypes.find((d) => d.key === wf.document_type)?.label
                  ?? wf.document_type}
                {" · "}
                {wf.is_active ? "active" : "inactive"}
                {" · "}
                {wf.steps.length} step(s)
              </div>
              <ul className="mt-2 text-xs text-[var(--text-muted)] space-y-0.5">
                {wf.steps.map((st, i) => (
                  <li key={st.id ?? i}>
                    #{i + 1}:{" "}
                    {st.approver_role
                      ? `role ${st.approver_role}`
                      : `user ${st.approver_user_id}`}
                    {st.min_amount != null ? ` · min ${st.min_amount}` : ""}
                  </li>
                ))}
              </ul>
            </div>
            <button
              type="button"
              className="text-sm text-red-700 self-start"
              onClick={() => remove(wf.id)}
            >
              Delete
            </button>
          </div>
        ))}
        {!items.length && (
          <p className="text-sm text-[var(--text-muted)]">No workflows yet.</p>
        )}
      </section>
    </div>
  )
}
