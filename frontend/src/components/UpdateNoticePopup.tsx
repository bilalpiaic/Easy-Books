"use client"

import { Sparkles, X } from "lucide-react"

export type UpdateNoticeItem = {
  id: number
  title: string
  body?: string | null
  created_at?: string | null
}

interface Props {
  items: UpdateNoticeItem[]
  onDismiss: () => void
}

/** Easy-language what's-new popup for every logged-in user. */
export default function UpdateNoticePopup({ items, onDismiss }: Props) {
  if (!items.length) return null
  const primary = items[0]
  const extras = items.slice(1, 4)

  return (
    <div className="fixed inset-0 z-[610] flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onDismiss} />

      <div
        role="dialog"
        aria-labelledby="update-notice-title"
        className="relative bg-[var(--bg-card)] rounded-t-2xl sm:rounded-2xl shadow-2xl border border-[var(--border)] w-full max-w-md mx-0 sm:mx-4 p-5 space-y-4"
      >
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Close"
          className="absolute top-3 right-3 p-1.5 rounded-lg hover:bg-[var(--bg-page)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-xl bg-[var(--primary-light)] flex items-center justify-center shrink-0">
            <Sparkles className="w-5 h-5 text-[var(--primary)]" />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-[var(--text-muted)] font-medium">
              What&apos;s new
            </p>
            <h3
              id="update-notice-title"
              className="font-semibold text-[var(--text-primary)] text-[15px] leading-snug mt-0.5"
            >
              {primary.title}
            </h3>
          </div>
        </div>

        {primary.body && (
          <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed">
            {primary.body}
          </p>
        )}

        {extras.length > 0 && (
          <ul className="space-y-2 border-t border-[var(--border)] pt-3">
            {extras.map((it) => (
              <li key={it.id} className="text-[12.5px] text-[var(--text-primary)]">
                <span className="font-medium">{it.title}</span>
                {it.body && (
                  <span className="block text-[11px] text-[var(--text-muted)] mt-0.5 line-clamp-2">
                    {it.body}
                  </span>
                )}
              </li>
            ))}
            {items.length > 4 && (
              <li className="text-[11px] text-[var(--text-muted)]">
                +{items.length - 4} more in your notifications
              </li>
            )}
          </ul>
        )}

        <p className="text-[11px] text-[var(--text-muted)]">
          You can also find these under the bell icon in the top bar.
        </p>

        <button
          type="button"
          onClick={onDismiss}
          className="w-full px-4 py-2.5 bg-[var(--primary)] text-white rounded-xl font-semibold text-sm hover:bg-[var(--primary-dark)] transition-colors"
        >
          Got it
        </button>
      </div>
    </div>
  )
}
