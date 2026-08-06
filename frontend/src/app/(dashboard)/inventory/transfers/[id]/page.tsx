"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"

interface Line {
  product_id: number
  product_name?: string
  qty: number
  unit_cost?: number
  lot_no?: string | null
}

interface Transfer {
  id: number
  number: string
  transfer_date: string
  status: string
  from_location_name?: string
  to_location_name?: string
  notes?: string | null
  lines: Line[]
}

export default function StockTransferDetailPage() {
  const params = useParams()
  const id = Number(params.id)
  const fmt = useFmt()
  const [t, setT] = useState<Transfer | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    apiFetch<Transfer>(`/api/stock-transfers/${id}`)
      .then(setT)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  useEffect(() => { load() }, [load])

  const act = async (action: "ship" | "receive" | "cancel") => {
    setBusy(true)
    setError(null)
    try {
      const body = action === "cancel" ? { reason: "Cancelled from UI" } : undefined
      await apiFetch(`/api/stock-transfers/${id}/${action}`, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed`)
    } finally {
      setBusy(false)
    }
  }

  if (!t && !error) return <p className="text-sm text-[var(--text-primary)]/50">Loading…</p>

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t?.number || "Transfer"}</h1>
          {t && (
            <p className="text-sm text-[var(--text-primary)]/55">
              {fmtDate(t.transfer_date)} · {t.from_location_name} → {t.to_location_name} ·{" "}
              <span className="capitalize">{t.status.replace("_", " ")}</span>
            </p>
          )}
        </div>
        <Link href="/inventory/transfers" className="text-sm text-[var(--primary)] hover:underline">← List</Link>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-3 py-2 text-sm">{error}</div>}

      {t && (
        <>
          <div className="flex flex-wrap gap-2 print:hidden">
            {t.status === "draft" && (
              <>
                <button type="button" disabled={busy} onClick={() => act("ship")} className="bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40">
                  Ship (in transit)
                </button>
                <button type="button" disabled={busy} onClick={() => act("cancel")} className="border px-4 py-2 rounded-lg text-sm disabled:opacity-40">
                  Cancel
                </button>
              </>
            )}
            {t.status === "in_transit" && (
              <button type="button" disabled={busy} onClick={() => act("receive")} className="bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40">
                Receive
              </button>
            )}
          </div>

          {t.notes && <p className="text-sm text-[var(--text-primary)]/70">{t.notes}</p>}

          <div className="table-freeze overflow-x-auto bg-white border border-[var(--text-primary)]/10 rounded-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-[var(--text-primary)]/60">
                  <th className="px-3 py-2">Product</th>
                  <th className="px-3 py-2 text-right">Qty</th>
                  <th className="px-3 py-2 text-right">Unit cost</th>
                </tr>
              </thead>
              <tbody>
                {t.lines.map((ln, i) => (
                  <tr key={i} className="border-b border-[var(--text-primary)]/5">
                    <td className="px-3 py-2">{ln.product_name || ln.product_id}</td>
                    <td className="px-3 py-2 text-right">{ln.qty}</td>
                    <td className="px-3 py-2 text-right">{fmt(Number(ln.unit_cost || 0))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
