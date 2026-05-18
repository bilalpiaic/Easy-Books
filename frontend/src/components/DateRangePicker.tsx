"use client"

import { Calendar } from "lucide-react"

interface DateRangePickerProps {
  start: string
  end: string
  onStartChange: (v: string) => void
  onEndChange: (v: string) => void
  label?: string
}

export default function DateRangePicker({
  start,
  end,
  onStartChange,
  onEndChange,
  label = "Period",
}: DateRangePickerProps) {
  const setPreset = (days: number) => {
    const to = new Date()
    const from = new Date()
    from.setDate(to.getDate() - days)
    onStartChange(from.toISOString().split("T")[0])
    onEndChange(to.toISOString().split("T")[0])
  }

  const setCurrentMonth = () => {
    const now = new Date()
    const from = new Date(now.getFullYear(), now.getMonth(), 1)
    const to = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    onStartChange(from.toISOString().split("T")[0])
    onEndChange(to.toISOString().split("T")[0])
  }

  const setCurrentYear = () => {
    const year = new Date().getFullYear()
    onStartChange(`${year}-01-01`)
    onEndChange(`${year}-12-31`)
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Calendar className="w-4 h-4 text-black/40" />
      <span className="text-xs font-bold uppercase tracking-widest text-black/50">{label}</span>
      <input
        type="date"
        value={start}
        onChange={(e) => onStartChange(e.target.value)}
        className="px-3 py-1.5 text-sm border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
      />
      <span className="text-black/40 text-sm">to</span>
      <input
        type="date"
        value={end}
        onChange={(e) => onEndChange(e.target.value)}
        className="px-3 py-1.5 text-sm border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
      />
      <div className="flex gap-1">
        {[
          { label: "30d", action: () => setPreset(30) },
          { label: "90d", action: () => setPreset(90) },
          { label: "Month", action: setCurrentMonth },
          { label: "Year", action: setCurrentYear },
        ].map((p) => (
          <button
            key={p.label}
            onClick={p.action}
            className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider border border-[#ede9e2] rounded hover:bg-[#b8943f] hover:text-white hover:border-[#b8943f] transition-colors"
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  )
}
