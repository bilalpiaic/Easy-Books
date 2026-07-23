"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

type Req = {
  id: number
  document_type: string
  document_id: number
  status: string
  notes?: string
}

export default function ApprovalsPage() {
  const [items, setItems] = useState<Req[]>([])
  const [notes, setNotes] = useState<Record<number, string>>({})

  const load = () =>
    apiFetch<Req[]>("/api/approvals")
      .then(setItems)
      .catch(() => setItems([]))
  useEffect(() => { load() }, [])

  const act = async (id: number, action: "approve" | "reject") => {
    await apiFetch(`/api/approvals/${id}/${action}`, {
      method: "POST",
      body: JSON.stringify({ notes: notes[id] || (action === "reject" ? "Rejected" : null) }),
    })
    load()
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-4">
      <h1 className="font-serif text-2xl">Approvals</h1>
      {items.map((r) => (
        <div key={r.id} className="border border-[var(--border)] rounded-xl p-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="font-medium capitalize">{r.document_type} #{r.document_id}</div>
            <div className="text-xs text-[var(--text-muted)]">Request #{r.id} · {r.status}</div>
            <input
              className="mt-2 border rounded px-2 py-1 text-sm w-full max-w-xs"
              placeholder="Notes"
              value={notes[r.id] || ""}
              onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
            />
          </div>
          <div className="flex gap-2">
            <button type="button" className="bg-[#b8943f] px-3 py-1.5 rounded text-sm" onClick={() => act(r.id, "approve")}>Approve</button>
            <button type="button" className="border px-3 py-1.5 rounded text-sm" onClick={() => act(r.id, "reject")}>Reject</button>
          </div>
        </div>
      ))}
      {!items.length && <p className="text-sm text-[var(--text-muted)]">No pending approvals.</p>}
    </div>
  )
}
