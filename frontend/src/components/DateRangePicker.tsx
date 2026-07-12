"use client"

import { useMemo, useState } from "react"
import { Calendar } from "lucide-react"
import { useSettings } from "@/context/SettingsContext"
import { fmtDate } from "@/lib/utils"
import {
  PRESETS, PresetId, resolvePreset, matchPreset,
  fiscalStartMonthFromSetting, weekStartFromSetting,
} from "@/lib/datePresets"

interface DateRangePickerProps {
  start: string
  end: string
  onStartChange: (v: string) => void
  onEndChange: (v: string) => void
  label?: string
  hideAll?: boolean
}

export default function DateRangePicker({
  start, end, onStartChange, onEndChange, label = "Period", hideAll = false,
}: DateRangePickerProps) {
  const { settings } = useSettings()
  const opts = useMemo(() => ({
    fiscalStartMonth: fiscalStartMonthFromSetting(settings.fiscal_year_start),
    weekStartDay: weekStartFromSetting(settings.week_start_day),
  }), [settings.fiscal_year_start, settings.week_start_day])

  // Dropdown state derives from the incoming dates so deep links and
  // externally-changed ranges show the right preset. A manual "Custom"
  // choice is sticky until the user picks a preset again.
  const [manualCustom, setManualCustom] = useState(false)
  const matched = useMemo(() => matchPreset(start, end, opts), [start, end, opts])
  const selected: PresetId = manualCustom ? "custom" : (matched ?? "custom")

  const presets = hideAll ? PRESETS.filter((p) => p.id !== "all") : PRESETS

  const pick = (id: PresetId) => {
    if (id === "custom") { setManualCustom(true); return }
    setManualCustom(false)
    const r = resolvePreset(id, opts)
    if (r) { onStartChange(r.start); onEndChange(r.end) }
  }

  const inputCls =
    "px-3 py-1.5 text-sm border border-[var(--border)] rounded-lg focus:outline-none " +
    "focus:ring-2 focus:ring-[var(--primary)] disabled:opacity-60 disabled:cursor-not-allowed"
  const hint =
    selected === "all" ? "All dates"
    : start && end ? `${fmtDate(start)} – ${fmtDate(end)}`
    : ""

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Calendar className="w-4 h-4 text-[var(--text-muted)]" />
      <span className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">{label}</span>
      <select
        value={selected}
        onChange={(e) => pick(e.target.value as PresetId)}
        className={inputCls}
      >
        {presets.map((p) => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
      </select>
      <input
        type="date" value={start} disabled={selected !== "custom"}
        onChange={(e) => onStartChange(e.target.value)} className={inputCls}
      />
      <span className="text-[var(--text-muted)] text-sm">to</span>
      <input
        type="date" value={end} disabled={selected !== "custom"}
        onChange={(e) => onEndChange(e.target.value)} className={inputCls}
      />
      {hint && <span className="text-xs text-[var(--text-muted)]">{hint}</span>}
    </div>
  )
}
