import { Info } from "lucide-react"

interface FieldHintProps {
  children: React.ReactNode
}

/**
 * Subtle inline hint placed below a form field. Use to explain WHAT the
 * field does and HOW it affects accounting — not to repeat the placeholder.
 */
export function FieldHint({ children }: FieldHintProps) {
  return (
    <p className="mt-1.5 flex gap-1.5 text-[11px] leading-relaxed text-[var(--text-primary)]/55">
      <Info className="w-3 h-3 flex-shrink-0 mt-0.5 text-[var(--text-primary)]/40" />
      <span>{children}</span>
    </p>
  )
}
