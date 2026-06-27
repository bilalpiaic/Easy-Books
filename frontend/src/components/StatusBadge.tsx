"use client"

import { cn } from "@/lib/utils"

const BADGE: Record<string, { bg: string; fg: string }> = {
  paid:       { bg: "var(--badge-green-bg)",  fg: "var(--success)" },
  posted:     { bg: "var(--badge-green-bg)",  fg: "var(--success)" },
  active:     { bg: "var(--badge-green-bg)",  fg: "var(--success)" },
  delivered:  { bg: "var(--badge-green-bg)",  fg: "var(--success)" },
  completed:  { bg: "var(--badge-green-bg)",  fg: "var(--success)" },
  sent:       { bg: "var(--badge-yellow-bg)", fg: "#D97706" },
  due:        { bg: "var(--badge-yellow-bg)", fg: "#D97706" },
  partial:    { bg: "var(--badge-yellow-bg)", fg: "#D97706" },
  pending:    { bg: "var(--badge-yellow-bg)", fg: "#D97706" },
  received:   { bg: "var(--badge-yellow-bg)", fg: "#D97706" },
  overdue:    { bg: "var(--badge-red-bg)",    fg: "var(--danger)" },
  void:       { bg: "var(--badge-red-bg)",    fg: "var(--danger)" },
  reversed:   { bg: "var(--badge-gray-bg)",   fg: "var(--text-muted)" },
  rejected:   { bg: "var(--badge-red-bg)",    fg: "var(--danger)" },
  draft:      { bg: "var(--badge-gray-bg)",   fg: "var(--text-muted)" },
  inactive:   { bg: "var(--badge-gray-bg)",   fg: "var(--text-muted)" },
  cancelled:  { bg: "var(--badge-gray-bg)",   fg: "var(--text-muted)" },
  processing: { bg: "var(--badge-blue-bg)",   fg: "var(--text-link)" },
  parsed:     { bg: "var(--badge-yellow-bg)", fg: "#D97706" },
  matched:    { bg: "var(--badge-green-bg)",  fg: "var(--success)" },
  reconciled: { bg: "var(--badge-blue-bg)",   fg: "var(--text-link)" },
  info:       { bg: "var(--badge-blue-bg)",   fg: "var(--text-link)" },
  approved:   { bg: "var(--badge-purple-bg)", fg: "#7C3AED" },
  applied:    { bg: "var(--badge-green-bg)",  fg: "var(--success)" },
  open:       { bg: "var(--badge-blue-bg)",   fg: "var(--text-link)" },
}

const FALLBACK = { bg: "var(--badge-gray-bg)", fg: "var(--text-muted)" }

export default function StatusBadge({
  status,
  className,
}: {
  status: string
  className?: string
}) {
  const { bg, fg } = BADGE[status?.toLowerCase()] ?? FALLBACK
  return (
    <span
      className={cn(
        "px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wide",
        className
      )}
      style={{ backgroundColor: bg, color: fg }}
    >
      {status}
    </span>
  )
}
