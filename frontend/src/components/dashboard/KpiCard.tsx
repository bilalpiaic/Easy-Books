"use client"
import React from "react"
import Link from "next/link"

export type KpiTone = "green" | "red" | "amber" | "emerald" | "blue" | "neutral"

const TONES: Record<KpiTone, { box: string; text: string }> = {
  green:   { box: "bg-green-50 border-green-200",     text: "text-green-800" },
  red:     { box: "bg-red-50 border-red-200",         text: "text-red-800" },
  amber:   { box: "bg-amber-50 border-amber-200",     text: "text-amber-800" },
  emerald: { box: "bg-emerald-50 border-emerald-200", text: "text-emerald-800" },
  blue:    { box: "bg-blue-50 border-blue-200",       text: "text-blue-800" },
  neutral: {
    box: "bg-[var(--bg-card)] border-[var(--border)] hover:border-[var(--primary)]/40 hover:shadow-sm",
    text: "text-[var(--text-primary)]",
  },
}

export interface KpiBadge { count: number; label: string; className: string }

export interface KpiCardProps {
  title: string
  value: string | null          // null → loading shimmer
  icon?: React.ElementType      // lucide icon; layout switches on its presence
  tone?: KpiTone                // colored tile variants; neutral = plain card
  href?: string                 // renders as a Link when set
  sub?: string
  badge?: KpiBadge
  iconClass?: string            // overrides the tone-derived icon color
  valueClass?: string           // alert coloring on the value (e.g. text-red-600)
}

/**
 * Unified dashboard KPI card (#128).
 * With icon:  icon top-left, title bottom-left, value bottom-right.
 * Without:    title top-left, value bottom-right.
 */
export default function KpiCard({
  title, value, icon: Icon, tone = "neutral", href, sub, badge, iconClass, valueClass,
}: KpiCardProps) {
  const tn = TONES[tone]
  const titleEl = (
    <p className={`text-[11px] font-semibold uppercase tracking-[0.10em] ${tn.text} opacity-70 truncate`}>
      {title}
    </p>
  )
  const body = (
    <>
      <div className="flex items-start justify-between gap-1.5 min-w-0">
        {Icon ? <Icon className={`w-4 h-4 flex-shrink-0 ${iconClass ?? `${tn.text} opacity-40`}`} /> : titleEl}
        {badge && (
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 ${badge.className}`}>
            {badge.count} {badge.label}
          </span>
        )}
      </div>
      <div className="flex items-end justify-between gap-2 min-w-0">
        <div className="min-w-0">
          {Icon && titleEl}
          {sub && <p className={`text-[9px] ${tn.text} opacity-55 font-medium truncate`}>{sub}</p>}
        </div>
        {value === null
          ? <div className="shimmer h-5 w-16 rounded" />
          : (
            <p className={`text-sm sm:text-base font-bold ${tn.text} leading-none text-right tabular-nums truncate ${valueClass ?? ""}`}>
              {value}
            </p>
          )}
      </div>
    </>
  )
  const cls = `${tn.box} border rounded-xl p-3 card-lift transition-all flex h-full flex-col justify-between gap-2 min-w-0`
  return href
    ? <Link href={href} className={cls}>{body}</Link>
    : <div className={cls}>{body}</div>
}
