import Link from "next/link"
import { ArrowRight, Compass } from "lucide-react"

interface EmptyStateGuideProps {
  title: string
  /** Short paragraph explaining what this page does and why the list is empty. */
  description?: string
  /** Numbered checklist of steps the user should take. */
  steps?: string[]
  /** Primary call-to-action button (e.g. "Create your first invoice"). */
  primaryAction?: { label: string; href: string }
  /** Secondary action — usually a link to the user guide or a sample CSV. */
  secondaryAction?: { label: string; href: string }
  /** Override the default compass icon. */
  icon?: React.ElementType
}

/**
 * Use this on every list page when there are zero records. The empty state
 * is the user&apos;s introduction to the feature — make it explain WHAT they&apos;ll
 * see here and the precise next step they should take.
 */
export function EmptyStateGuide({
  title,
  description,
  steps,
  primaryAction,
  secondaryAction,
  icon: Icon = Compass,
}: EmptyStateGuideProps) {
  return (
    <div className="bg-white border border-[#ede9e2] rounded-2xl shadow-sm p-8 sm:p-10 max-w-2xl mx-auto">
      <div className="flex justify-center mb-5">
        <div className="w-14 h-14 rounded-2xl bg-[#faf6ec] border border-[#b8943f]/30 flex items-center justify-center">
          <Icon className="w-7 h-7 text-[#b8943f]" />
        </div>
      </div>
      <h2 className="text-lg sm:text-xl font-serif font-semibold text-[#1a1814] text-center">
        {title}
      </h2>
      {description && (
        <p className="mt-2.5 text-sm text-[#1a1814]/65 text-center leading-relaxed">
          {description}
        </p>
      )}
      {steps && steps.length > 0 && (
        <ol className="mt-6 space-y-2.5 max-w-md mx-auto">
          {steps.map((step, i) => (
            <li key={i} className="flex gap-3 text-sm text-[#1a1814]/80 leading-relaxed">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[#b8943f] text-white text-xs font-bold flex items-center justify-center mt-0.5">
                {i + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      )}
      {(primaryAction || secondaryAction) && (
        <div className="mt-7 flex flex-col sm:flex-row gap-3 items-center justify-center">
          {primaryAction && (
            <Link
              href={primaryAction.href}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#1a1814] text-white font-semibold rounded-xl hover:bg-[#b8943f] hover:text-[#1a1814] transition-colors text-sm"
            >
              {primaryAction.label}
              <ArrowRight className="w-4 h-4" />
            </Link>
          )}
          {secondaryAction && (
            <Link
              href={secondaryAction.href}
              className="text-sm text-[#1a1814]/55 hover:text-[#b8943f] underline underline-offset-2"
            >
              {secondaryAction.label}
            </Link>
          )}
        </div>
      )}
    </div>
  )
}
