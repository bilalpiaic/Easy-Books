"use client"
import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

// ── Data fetching hook ────────────────────────────────────────────────────────

export function useHealthcareList<T>(path: string, params?: Record<string, string>) {
  const [data, setData] = useState<T[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const qs = params ? "?" + new URLSearchParams(params).toString() : ""
      const json = await apiFetch<T[] | { items: T[] }>(`/api/healthcare${path}${qs}`)
      setData(Array.isArray(json) ? json : (json as { items: T[] }).items ?? [])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load")
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, JSON.stringify(params)])

  useEffect(() => { load() }, [load])
  return { data, loading, error, reload: load }
}

// ── Status badge ─────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  waiting:           "bg-yellow-100 text-yellow-800",
  called:            "bg-blue-100 text-blue-800",
  visited:           "bg-green-100 text-green-800",
  cancelled:         "bg-red-100 text-red-800",
  admitted:          "bg-blue-100 text-blue-800",
  discharged:        "bg-green-100 text-green-800",
  ordered:           "bg-yellow-100 text-yellow-800",
  sample_collected:  "bg-orange-100 text-orange-800",
  processing:        "bg-indigo-100 text-indigo-800",
  resulted:          "bg-purple-100 text-purple-800",
  delivered:         "bg-green-100 text-green-800",
  available:         "bg-emerald-100 text-emerald-800",
  occupied:          "bg-red-100 text-red-800",
  maintenance:       "bg-gray-100 text-gray-700",
  performed:         "bg-green-100 text-green-800",
  active:            "bg-emerald-100 text-emerald-800",
  inactive:          "bg-gray-100 text-gray-700",
  scheduled:         "bg-sky-100 text-sky-800",
  in_progress:       "bg-amber-100 text-amber-800",
  completed:         "bg-emerald-100 text-emerald-800",
  no_show:           "bg-rose-100 text-rose-800",
}

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-700"
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  )
}

// ── Patient badge ─────────────────────────────────────────────────────────────

export function PatientBadge({ name, mr }: { name: string; mr?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="font-medium">{name}</span>
      {mr && <span className="text-xs text-neutral-400">#{mr}</span>}
    </span>
  )
}

// ── Bed grid ─────────────────────────────────────────────────────────────────

export type Bed = {
  id: number
  bed_number: string
  status: "available" | "occupied" | "maintenance"
}

export function BedGrid({ beds, onSelect }: { beds: Bed[]; onSelect?: (bed: Bed) => void }) {
  return (
    <div className="grid grid-cols-6 gap-2">
      {beds.map(bed => {
        const color =
          bed.status === "available" ? "bg-emerald-50 border-emerald-300 hover:bg-emerald-100 cursor-pointer"
          : bed.status === "occupied" ? "bg-red-50 border-red-300"
          : "bg-gray-100 border-gray-300"
        return (
          <button
            key={bed.id}
            onClick={() => onSelect?.(bed)}
            className={`border rounded p-2 text-center text-xs font-medium ${color}`}
            disabled={bed.status !== "available"}
          >
            {bed.bed_number}
            <div className="text-[10px] text-neutral-500 mt-0.5">{bed.status}</div>
          </button>
        )
      })}
    </div>
  )
}

// ── Section card ─────────────────────────────────────────────────────────────

export function HcCard({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
      {title && (
        <div className="px-4 py-3 border-b border-neutral-100 font-medium text-sm text-neutral-700">
          {title}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  )
}
