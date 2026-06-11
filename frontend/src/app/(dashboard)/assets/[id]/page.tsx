"use client"

import { use, useEffect, useState } from "react"
import { Building2, Printer } from "lucide-react"
import { useBreadcrumb } from "@/context/BreadcrumbContext"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import DocLink from "@/components/DocLink"

interface DepreciationEntry {
  id: number
  depreciation_date: string
  depreciation_amount: number
  transaction_id: number
}
interface AssetDetail {
  id: number
  name: string
  code: string | null
  acquisition_date: string
  acquisition_cost: number
  salvage_value: number
  useful_life_months: number
  method: string
  accumulated_depreciation: number
  book_value: number
  is_disposed: boolean
  depreciation_entries: DepreciationEntry[]
}

export default function FixedAssetRegisterPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const fmt = useFmt()
  const [asset, setAsset] = useState<AssetDetail | null>(null)
  const [loading, setLoading] = useState(true)
  useBreadcrumb(asset ? asset.name : undefined)

  useEffect(() => {
    apiFetch<AssetDetail>(`/api/assets/${id}`)
      .then(d => { setAsset(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [id])

  if (loading) return <div className="text-center py-20 text-[#1a1814]/50">Loading…</div>
  if (!asset) return <div className="text-center py-20 text-[#1a1814]/50">Asset not found.</div>

  // Build a running register: opening cost, each depreciation charge, running accumulated + book value.
  const entries = [...asset.depreciation_entries].sort((a, b) =>
    a.depreciation_date.localeCompare(b.depreciation_date))
  let runningAccum = 0
  const rows = entries.map(e => {
    runningAccum += e.depreciation_amount
    return {
      ...e,
      accumulated: runningAccum,
      book: asset.acquisition_cost - runningAccum,
    }
  })

  return (
    <div className="max-w-4xl mx-auto space-y-6">

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#1a1814] flex items-center justify-center flex-shrink-0">
            <Building2 className="w-5 h-5 text-[#ffd966]" />
          </div>
          <div>
            <h1 className="text-2xl font-serif text-[#1a1814]">{asset.name}</h1>
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mt-0.5">
              Fixed Asset Register{asset.code ? ` · ${asset.code}` : ""}
              {asset.is_disposed ? " · DISPOSED" : ""}
            </p>
          </div>
        </div>
        <button onClick={() => window.print()} className="p-3 bg-white border border-[#1a1814]/10 rounded-xl hover:bg-[#f6f3ee] text-[#1a1814]/60 print:hidden" title="Print">
          <Printer className="w-5 h-5" />
        </button>
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          ["Acquisition Cost", fmt(asset.acquisition_cost)],
          ["Accumulated Depreciation", `(${fmt(asset.accumulated_depreciation)})`],
          ["Book Value", fmt(asset.book_value)],
          ["Method / Life", `${asset.method.replace("_", " ")} · ${asset.useful_life_months}m`],
        ].map(([label, val]) => (
          <div key={label} className="bg-white border border-[#ede9e2] rounded-xl px-4 py-3">
            <p className="text-[10px] uppercase tracking-widest text-[#1a1814]/50">{label}</p>
            <p className="font-mono text-sm mt-1 text-[#1a1814]">{val}</p>
          </div>
        ))}
      </div>

      {/* Depreciation schedule */}
      <div className="bg-white rounded-2xl border border-[#1a1814]/5 overflow-hidden">
        <div className="px-5 py-3 border-b border-[#ede9e2] bg-[#f6f3ee]">
          <h2 className="text-sm font-bold text-[#1a1814]">Depreciation Schedule</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee]/50">
            <tr>
              {["Date", "JV", "Charge", "Accumulated", "Book Value"].map(h => (
                <th key={h} className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/50">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-[#1a1814]/5">
              <td className="px-4 py-2 text-[#1a1814]/70">{asset.acquisition_date}</td>
              <td className="px-4 py-2 text-[#1a1814]/40 italic">acquisition</td>
              <td className="px-4 py-2 font-mono">{fmt(asset.acquisition_cost)}</td>
              <td className="px-4 py-2 font-mono">—</td>
              <td className="px-4 py-2 font-mono">{fmt(asset.acquisition_cost)}</td>
            </tr>
            {rows.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-[#1a1814]/40 italic">No depreciation posted yet.</td></tr>
            ) : rows.map(r => (
              <tr key={r.id} className="border-t border-[#1a1814]/5 hover:bg-[#f6f3ee]/40">
                <td className="px-4 py-2 text-[#1a1814]/70">{r.depreciation_date}</td>
                <td className="px-4 py-2 font-mono text-xs">
                  <DocLink type="jv" id={r.transaction_id} label={`JV-${String(r.transaction_id).padStart(5, "0")}`} />
                </td>
                <td className="px-4 py-2 font-mono text-red-500">({fmt(r.depreciation_amount)})</td>
                <td className="px-4 py-2 font-mono text-[#1a1814]/60">({fmt(r.accumulated)})</td>
                <td className="px-4 py-2 font-mono font-bold">{fmt(r.book)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
