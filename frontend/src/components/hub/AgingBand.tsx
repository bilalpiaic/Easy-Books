"use client"
import { useFmt } from "@/context/SettingsContext"

export interface AgingBandProps {
  current: number
  d1_30:   number
  d31_60:  number
  d60plus: number   // 61_90 + over_90 combined
}

const SEGMENTS = [
  { key: "current" as const, label: "Current", bg: "bg-green-500",  fg: "#16a34a" },
  { key: "d1_30"   as const, label: "1–30d",   bg: "bg-amber-500",  fg: "#d97706" },
  { key: "d31_60"  as const, label: "31–60d",  bg: "bg-orange-500", fg: "#ea580c" },
  { key: "d60plus" as const, label: "60d+",    bg: "bg-red-600",    fg: "#dc2626" },
]

export default function AgingBand(props: AgingBandProps) {
  const fmt = useFmt()
  const total = props.current + props.d1_30 + props.d31_60 + props.d60plus
  if (total === 0)
    return (
      <div className="bg-white rounded-xl p-3 text-sm text-[#1a1814]/40 text-center">
        No outstanding items
      </div>
    )
  return (
    <div className="bg-white rounded-xl p-3">
      <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/40 mb-2">
        Aging Breakdown
      </div>
      <div className="flex gap-px h-2 rounded-full overflow-hidden mb-2">
        {SEGMENTS.map(s =>
          props[s.key] > 0 ? (
            <div
              key={s.key}
              className={s.bg}
              style={{ flex: props[s.key] }}
              title={`${s.label}: ${fmt(props[s.key])}`}
            />
          ) : null
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {SEGMENTS.map(s => {
          const pct = Math.round((props[s.key] / total) * 100)
          return pct > 0 ? (
            <span key={s.key} className="text-[9px]" style={{ color: s.fg }}>
              ■ {s.label} {pct}%
            </span>
          ) : null
        })}
      </div>
    </div>
  )
}
