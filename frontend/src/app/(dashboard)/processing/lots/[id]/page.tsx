"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import GreyInwardForm, { type GreyLotView } from "@/components/processing/GreyInwardForm"
import { apiFetch } from "@/lib/api"

export default function LotDetailPage() {
  const params = useParams()
  const id = Number(params.id)
  const [lot, setLot] = useState<GreyLotView | null>(null)
  const [err, setErr] = useState("")

  useEffect(() => {
    if (!id) return
    apiFetch<GreyLotView>(`/api/textile-processing/lots/${id}`)
      .then(setLot)
      .catch((ex: unknown) => {
        setLot(null)
        setErr(ex instanceof Error ? ex.message : "Failed to load")
      })
  }, [id])

  if (err) return <div className="p-4 text-sm text-red-600">{err}</div>
  if (!lot) return <div className="p-4 text-sm text-[var(--text-muted)]">Loading…</div>

  return <GreyInwardForm mode="view" initial={lot} />
}
