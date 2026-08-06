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
    "px-2.5 py-1.5 text-sm border border-[var(--border)] rounded-lg focus:outline-none " +
    "focus:ring-2 focus:ring-[var(--primary)] disabled:opacity-60 disabled:cursor-not-allowed " +
    "min-w-0 max-w-full"
  const hint =
    selected === "all" ? "All dates"
    : start && end ? `${fmtDate(start)} – ${fmtDate(end)}`
    : ""
  const showCustomDates = selected === "custom"

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 w-full">
      <div className="flex items-center gap-1.5 shrink-0">
        <Calendar className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">{label}</span>
      </div>
      <select
        value={selected}
        onChange={(e) => pick(e.target.value as PresetId)}
        className={inputCls + " flex-1 min-w-[8rem] sm:flex-none sm:min-w-[10rem]"}
        aria-label={label}
      >
        {presets.map((p) => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
      </select>
      {/* Custom From/To — hide on sm when a preset is selected (hint shows range) */}
      <div
        className={
          showCustomDates
            ? "flex flex-wrap items-center gap-1.5 w-full sm:w-auto"
            : "hidden sm:flex items-center gap-1.5"
        }
      >
        <input
          type="date" value={start} disabled={!showCustomDates}
          onChange={(e) => onStartChange(e.target.value)}
          className={inputCls + " flex-1 min-w-0 sm:flex-none"}
          aria-label="From date"
        />
        <span className="text-[var(--text-muted)] text-xs shrink-0">to</span>
        <input
          type="date" value={end} disabled={!showCustomDates}
          onChange={(e) => onEndChange(e.target.value)}
          className={inputCls + " flex-1 min-w-0 sm:flex-none"}
          aria-label="To date"
        />
      </div>
      {hint && (
        <span className="text-[11px] text-[var(--text-muted)] tabular-nums sm:ml-0 w-full sm:w-auto">
          {hint}
        </span>
      )}
    </div>
  )
}
