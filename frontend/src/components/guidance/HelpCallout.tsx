"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp, Lightbulb } from "lucide-react"

interface HelpCalloutProps {
  title: string
  children: React.ReactNode
  /** Open on first render. Default true so guidance is visible by default. */
  defaultOpen?: boolean
  /** "tip" = blue, "warning" = amber, "success" = green */
  tone?: "tip" | "warning" | "success"
}

const TONE: Record<NonNullable<HelpCalloutProps["tone"]>, {
  bg: string
  border: string
  iconColor: string
  titleColor: string
  bodyColor: string
}> = {
  tip:     { bg: "bg-blue-50",  border: "border-blue-200",  iconColor: "text-blue-600",  titleColor: "text-blue-900",  bodyColor: "text-blue-800/90"  },
  warning: { bg: "bg-amber-50", border: "border-amber-300", iconColor: "text-amber-600", titleColor: "text-amber-900", bodyColor: "text-amber-800/90" },
  success: { bg: "bg-green-50", border: "border-green-300", iconColor: "text-green-600", titleColor: "text-green-900", bodyColor: "text-green-800/90" },
}

/**
 * Expandable guidance panel. Use at the top of forms and pages where the
 * user might need context on WHAT they're configuring and WHY it matters.
 */
export function HelpCallout({
  title,
  children,
  defaultOpen = true,
  tone = "tip",
}: HelpCalloutProps) {
  const [open, setOpen] = useState(defaultOpen)
  const styles = TONE[tone]

  return (
    <div className={`${styles.bg} ${styles.border} border rounded-xl px-4 py-3`}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2.5 text-left"
        aria-expanded={open}
      >
        <Lightbulb className={`w-4 h-4 flex-shrink-0 ${styles.iconColor}`} />
        <span className={`flex-1 text-sm font-semibold ${styles.titleColor}`}>{title}</span>
        {open ? (
          <ChevronUp className={`w-4 h-4 ${styles.iconColor}`} />
        ) : (
          <ChevronDown className={`w-4 h-4 ${styles.iconColor}`} />
        )}
      </button>
      {open && (
        <div className={`mt-2.5 text-xs leading-relaxed pl-6 ${styles.bodyColor}`}>
          {children}
        </div>
      )}
    </div>
  )
}
