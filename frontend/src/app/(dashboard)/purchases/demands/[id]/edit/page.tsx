"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { AlertTriangle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { DemandForm, DemandFormValues, emptyDemandLine } from "../../new/page"

type DemandLineApi = {
  id: number
  product_id?: number | null
  description: string
  qty: number
  unit?: string | null
}

type DemandApi = {
  id: number
  number: string
  demand_date: string
  required_by?: string | null
  analytic_account_id?: number | null
  purpose?: string | null
  notes?: string | null
  status: string
  lines: DemandLineApi[]
}

export default function EditDemandPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()

  const [demand, setDemand] = useState<DemandApi | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<DemandApi>(`/api/purchase-demands/${id}`)
      .then(setDemand)
      .catch(e => setError(e instanceof Error ? e.message : "Not found"))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <p className="p-4 text-sm text-[var(--text-muted)]">Loading…</p>
  if (!demand) return <p className="p-4 text-sm text-red-600">{error ?? "Demand not found"}</p>

  if (demand.status !== "draft") {
    return (
      <div className="p-4 max-w-4xl space-y-4">
        <div className="bg-amber-50 border border-amber-200 text-amber-900 rounded-xl px-4 py-3 text-sm flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            {demand.number} is <strong>{demand.status}</strong> and can no longer be edited. Only demands in <strong>draft</strong> status may be changed.
          </span>
        </div>
        <button
          onClick={() => router.push(`/purchases/demands/${id}`)}
          className="px-4 py-2 rounded-lg border border-[var(--border)] text-sm hover:bg-[var(--bg-page)]"
        >
          Back to Demand
        </button>
      </div>
    )
  }

  const initial: DemandFormValues = {
    demand_date: demand.demand_date,
    required_by: demand.required_by || "",
    analytic_account_id: demand.analytic_account_id ? String(demand.analytic_account_id) : "",
    purpose: demand.purpose || "",
    notes: demand.notes || "",
    lines: demand.lines.length
      ? demand.lines.map(l => ({
          product_id: l.product_id ? String(l.product_id) : "",
          description: l.description,
          qty: String(l.qty),
          unit: l.unit || "",
        }))
      : [emptyDemandLine()],
  }

  return (
    <DemandForm
      title={`Edit ${demand.number}`}
      subtitle="Quantities only — no pricing on this form."
      initial={initial}
      submitLabel="Update Demand"
      onSubmit={async payload => {
        await apiFetch(`/api/purchase-demands/${id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        })
        router.push(`/purchases/demands/${id}`)
      }}
    />
  )
}
