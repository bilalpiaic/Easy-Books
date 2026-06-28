"use client"

import { Clock, Download, X } from "lucide-react"

interface Props {
  local:     string
  remote:    string
  onUpdate:  () => void   // "Update Now"
  onLater:   () => void   // "Remind me next login" (session dismiss)
  onSkip:    () => void   // "Skip this version" (persist dismiss per SHA)
}

export default function UpdateAvailablePopup({ local, remote, onUpdate, onLater, onSkip }: Props) {
  return (
    <div className="fixed inset-0 z-[600] flex items-end sm:items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onLater} />

      {/* Card */}
      <div className="relative bg-[var(--bg-card)] rounded-t-2xl sm:rounded-2xl shadow-2xl border border-[var(--border)] w-full max-w-sm mx-0 sm:mx-4 p-5 space-y-4">

        <button onClick={onLater} aria-label="Close"
          className="absolute top-3 right-3 p-1.5 rounded-lg hover:bg-[var(--bg-page)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
          <X className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-xl bg-[var(--primary-light)] flex items-center justify-center shrink-0">
            <Download className="w-5 h-5 text-[var(--primary)]" />
          </div>
          <div>
            <h3 className="font-semibold text-[var(--text-primary)] text-[15px] leading-tight">
              Update Available
            </h3>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              You have{" "}
              <span className="font-mono text-[var(--text-primary)]">{local}</span>
              {" · "}GitHub has{" "}
              <span className="font-mono font-bold text-[var(--primary)]">{remote}</span>
            </p>
          </div>
        </div>

        <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed">
          A new version of Easy-Books is available. The update takes <strong>1–3 minutes</strong> and
          preserves all your accounting data.
        </p>

        {/* Actions */}
        <div className="flex flex-col gap-2 pt-1">
          <button onClick={onUpdate}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[var(--primary)] text-white rounded-xl font-semibold text-sm hover:bg-[var(--primary-dark)] transition-colors">
            <Download className="w-4 h-4" />
            Update Now
          </button>
          <div className="flex gap-2">
            <button onClick={onLater}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-[var(--border)] rounded-xl text-sm text-[var(--text-muted)] hover:bg-[var(--bg-page)] transition-colors">
              <Clock className="w-3.5 h-3.5" />
              Later
            </button>
            <button onClick={onSkip}
              className="flex-1 px-3 py-2 border border-[var(--border)] rounded-xl text-sm text-[var(--text-muted)] hover:bg-[var(--bg-page)] transition-colors">
              Skip version
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
