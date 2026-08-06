"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"

interface Shift {
  id: number
  register_id: number
  status: string
  opening_float: number
  closing_count?: number | null
  expected_cash?: number | null
  variance?: number | null
  opened_at: string
  closed_at?: string | null
  sale_count?: number
  expected_cash_live?: number
}

export default function PosShiftsPage() {
  const fmt = useFmt()
  const [shifts, setShifts] = useState<Shift[]>([])
  const [selected, setSelected] = useState<Shift | null>(null)
  const [count, setCount] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    apiFetch<Shift[]>("/api/pos/shifts?limit=30")
      .then(setShifts)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [])

  useEffect(() => { load() }, [load])

  const openDetail = async (id: number) => {
    setError(null)
    try {
      const s = await apiFetch<Shift>(`/api/pos/shifts/${id}`)
      setSelected(s)
      setCount(String(s.expected_cash_live ?? s.expected_cash ?? ""))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load shift")
    }
  }

  const closeShift = async () => {
    if (!selected) return
    setBusy(true)
    setError(null)
    try {
      await apiFetch(`/api/pos/shifts/${selected.id}/close`, {
        method: "POST",
        body: JSON.stringify({ closing_count: Number(count) || 0 }),
      })
      setSelected(null)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Close failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">POS Shifts</h1>
          <p className="text-sm text-[var(--text-primary)]/55">Open/close and cash variance.</p>
        </div>
        <Link href="/pos" className="text-sm font-medium text-[var(--primary)] hover:underline">
          ← Register
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-2 text-sm">{error}</div>
      )}

      <div className="bg-white border border-[var(--text-primary)]/10 rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-[var(--text-primary)]/50 border-b">
              <th className="px-4 py-3">Shift</th>
              <th className="px-4 py-3">Opened</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Variance</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {!shifts.length && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--text-primary)]/45">
                  No shifts yet.
                </td>
              </tr>
            )}
            {shifts.map((s) => (
              <tr key={s.id} className="border-b border-[var(--text-primary)]/5">
                <td className="px-4 py-3 font-medium">#{s.id}</td>
                <td className="px-4 py-3 whitespace-nowrap">{fmtDate(s.opened_at)}</td>
                <td className="px-4 py-3">{s.status}</td>
                <td className="px-4 py-3">
                  {s.variance != null ? fmt(Number(s.variance)) : "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => openDetail(s.id)}
                    className="text-[var(--primary)] font-medium hover:underline"
                  >
                    {s.status === "open" ? "Close / detail" : "Detail"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="bg-white border border-[var(--text-primary)]/10 rounded-2xl p-4 space-y-3">
          <div className="font-semibold">Shift #{selected.id}</div>
          <div className="text-sm text-[var(--text-primary)]/70 space-y-1">
            <div>Sales: {selected.sale_count ?? 0}</div>
            <div>Opening float: {fmt(Number(selected.opening_float || 0))}</div>
            <div>
              Expected cash:{" "}
              {fmt(Number(selected.expected_cash_live ?? selected.expected_cash ?? 0))}
            </div>
            {selected.status === "closed" && (
              <>
                <div>Counted: {fmt(Number(selected.closing_count || 0))}</div>
                <div>Variance: {fmt(Number(selected.variance || 0))}</div>
              </>
            )}
          </div>
          {selected.status === "open" && (
            <div className="flex flex-wrap gap-2 items-end">
              <label className="text-sm">
                <span className="text-xs text-[var(--text-primary)]/50">Closing count</span>
                <input
                  type="number"
                  className="block border rounded-lg px-3 py-2 mt-1"
                  value={count}
                  onChange={(e) => setCount(e.target.value)}
                />
              </label>
              <button
                type="button"
                disabled={busy}
                onClick={closeShift}
                className="bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40"
              >
                Close shift
              </button>
            </div>
          )}
          <button type="button" className="text-sm text-[var(--text-primary)]/50" onClick={() => setSelected(null)}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}
