"use client"

import { createPortal } from "react-dom"
import { useEffect, useRef, useState } from "react"
import { CheckCircle, AlertCircle, Zap } from "lucide-react"
import { apiFetch } from "@/lib/api"

const CURRENT_COMMIT = process.env.NEXT_PUBLIC_GIT_COMMIT ?? ""

interface ChangelogEntry { sha: string; message: string; date: string }

const STEP_LABELS = ["Pull", "Compile", "Bundle", "Start"]
const PHASE_MSGS = [
  "Pulling latest code from GitHub…",
  "Compiling updated modules…",
  "Building optimised frontend bundle…",
  "Restarting services — almost done…",
  "Waiting for server to come back online…",
]

interface Props { onClose: () => void }

export default function UpdateProgressScreen({ onClose }: Props) {
  const [mounted,    setMounted]    = useState(false)
  const [phase,      setPhase]      = useState(0)
  const [elapsed,    setElapsed]    = useState(0)
  const [done,       setDone]       = useState(false)
  const [error,      setError]      = useState<string | null>(null)
  const [changelog,  setChangelog]  = useState<ChangelogEntry[]>([])
  const [newCommit,  setNewCommit]  = useState<string | null>(null)
  const [reloading,  setReloading]  = useState(false)

  const pollRef  = useRef<ReturnType<typeof setTimeout> | null>(null)
  const elRef    = useRef<ReturnType<typeof setInterval> | null>(null)
  const phaseRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    setMounted(true)
    doUpdate()
    phaseRef.current = setInterval(() => setPhase(p => Math.min(p + 1, PHASE_MSGS.length - 1)), 22_000)
    elRef.current    = setInterval(() => setElapsed(e => e + 1), 1_000)
    return () => {
      if (pollRef.current)  clearTimeout(pollRef.current)
      if (elRef.current)    clearInterval(elRef.current)
      if (phaseRef.current) clearInterval(phaseRef.current)
    }
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  async function doUpdate() {
    try {
      const res = await apiFetch<{ status: string; message?: string }>(
        "/api/system/update", { method: "POST" },
      )
      if (res.status === "up_to_date") {
        stopTimers(); setDone(true); setNewCommit(null)
        setTimeout(() => window.location.reload(), 2_000)
      } else if (res.status === "restarting") {
        setPhase(2)
        pollRestart(Date.now())
      } else {
        stopTimers(); setError(res.message ?? "Could not start update. Run update.bat / update.sh manually.")
      }
    } catch (e) {
      stopTimers(); setError(e instanceof Error ? e.message : "Update failed.")
    }
  }

  function pollRestart(startMs: number) {
    if (Date.now() - startMs > 6 * 60_000) {
      stopTimers()
      setError("Rebuild is taking longer than expected. Check if the server restarted correctly.")
      return
    }
    pollRef.current = setTimeout(async () => {
      try {
        const res = await fetch("/version.json", {
          cache: "no-store",
          signal: AbortSignal.timeout(5_000),
        })
        if (res.ok) {
          const data = await res.json() as { commit?: string }
          const changed = data.commit && data.commit !== "dev" && data.commit !== CURRENT_COMMIT
          if (changed) {
            stopTimers()
            const short = (data.commit ?? "").slice(0, 7)
            setNewCommit(short)
            setDone(true)
            localStorage.setItem("eb.just-updated", JSON.stringify({
              from: CURRENT_COMMIT.slice(0, 7),
              to:   short,
              at:   new Date().toISOString(),
            }))
            // Fetch changelog (best-effort)
            apiFetch<{ commits: ChangelogEntry[] }>(
              `/api/system/update/changelog?since=${CURRENT_COMMIT}&limit=8`,
            ).then(r => setChangelog(r.commits)).catch(() => {})
            setReloading(true)
            setTimeout(() => window.location.reload(), 4_500)
            return
          }
        }
      } catch { /* still rebuilding */ }
      pollRestart(startMs)
    }, 5_000)
  }

  function stopTimers() {
    if (elRef.current)    clearInterval(elRef.current)
    if (phaseRef.current) clearInterval(phaseRef.current)
  }

  if (!mounted) return null

  const progressPct = Math.min(Math.round((elapsed / 120) * 100), 90)
  const activeStep  = Math.floor(phase * (STEP_LABELS.length / PHASE_MSGS.length))

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-[var(--bg-page)]">

      {/* ── Done ─────────────────────────────────────────────────────────── */}
      {done && (
        <div className="text-center space-y-6 max-w-sm px-6 animate-in fade-in duration-500">
          {/* Big success ring */}
          <div className="mx-auto w-24 h-24 rounded-full bg-green-100 flex items-center justify-center ring-4 ring-green-200">
            <CheckCircle className="w-12 h-12 text-green-600" />
          </div>

          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">
              {newCommit ? "Update Complete!" : "Already up to date"}
            </h2>
            {newCommit && (
              <p className="text-sm text-[var(--text-muted)] mt-1">
                Now running commit{" "}
                <span className="font-mono font-bold text-[var(--primary)]">{newCommit}</span>
              </p>
            )}
          </div>

          {/* Changelog */}
          {changelog.length > 0 && (
            <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] p-4 text-left space-y-2 max-h-48 overflow-y-auto">
              <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                What&apos;s New
              </p>
              {changelog.map(c => (
                <div key={c.sha} className="flex items-start gap-2">
                  <span className="font-mono text-[10px] text-[var(--text-muted)] mt-0.5 shrink-0">{c.sha}</span>
                  <span className="text-[12px] text-[var(--text-primary)] leading-snug">{c.message}</span>
                </div>
              ))}
            </div>
          )}

          <p className="text-xs text-[var(--text-muted)] animate-pulse">
            {reloading ? "Reloading page…" : "Done"}
          </p>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────────────────── */}
      {!done && error && (
        <div className="text-center space-y-4 max-w-sm px-6">
          <div className="mx-auto w-16 h-16 rounded-full bg-red-100 flex items-center justify-center">
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
          <h2 className="text-xl font-bold text-[var(--text-primary)]">Update Failed</h2>
          <p className="text-sm text-[var(--text-muted)]">{error}</p>
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] p-3 text-left space-y-1">
            <p className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider mb-2">Run manually:</p>
            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="text-[var(--text-muted)] w-20">Windows</span>
              <code className="text-[var(--text-primary)]">update.bat</code>
            </div>
            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="text-[var(--text-muted)] w-20">macOS/Linux</span>
              <code className="text-[var(--text-primary)]">./update.sh</code>
            </div>
          </div>
          <button onClick={onClose}
            className="px-5 py-2 border border-[var(--border)] rounded-xl text-sm hover:bg-[var(--bg-card)] transition-colors">
            Close
          </button>
        </div>
      )}

      {/* ── Loading ───────────────────────────────────────────────────────── */}
      {!done && !error && (
        <div className="text-center space-y-8 max-w-xs px-6">

          {/* Animated ring */}
          <div className="relative w-28 h-28 mx-auto">
            <svg className="w-28 h-28 -rotate-90" viewBox="0 0 112 112">
              <circle cx="56" cy="56" r="48" fill="none" stroke="var(--border)" strokeWidth="6" />
              <circle cx="56" cy="56" r="48" fill="none" stroke="var(--primary)" strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray="75 226"
                className="animate-spin origin-center"
                style={{ animationDuration: "1.4s" }} />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <Zap className="w-9 h-9 text-[var(--primary)]" />
            </div>
          </div>

          <div className="space-y-1.5">
            <h2 className="text-xl font-bold text-[var(--text-primary)]">Updating Easy-Books</h2>
            <p className="text-sm text-[var(--text-muted)] min-h-[18px] transition-all duration-700">
              {PHASE_MSGS[phase]}
            </p>
          </div>

          {/* Step indicators */}
          <div className="flex items-center justify-center gap-3">
            {STEP_LABELS.map((label, i) => {
              const past   = activeStep > i
              const active = activeStep === i
              return (
                <div key={label} className="flex flex-col items-center gap-1">
                  <div className={`w-9 h-9 rounded-full border-2 flex items-center justify-center text-xs font-bold transition-all duration-500 ${
                    past   ? "bg-[var(--primary)] border-[var(--primary)] text-white" :
                    active ? "border-[var(--primary)] text-[var(--primary)]" :
                             "border-[var(--border)] text-[var(--text-muted)] opacity-40"
                  }`}>
                    {past ? "✓" : i + 1}
                  </div>
                  <span className={`text-[9px] font-medium transition-colors ${active || past ? "text-[var(--text-primary)]" : "text-[var(--text-muted)] opacity-40"}`}>
                    {label}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Progress bar */}
          <div className="space-y-1.5">
            <div className="w-full bg-[var(--border)] rounded-full h-1.5 overflow-hidden">
              <div className="h-full bg-[var(--primary)] rounded-full transition-all duration-1000 ease-linear"
                style={{ width: `${progressPct}%` }} />
            </div>
            <p className="text-[10px] text-[var(--text-muted)] text-center">
              {elapsed < 60 ? `${elapsed}s` : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`} elapsed
              {" · "}Keep this tab open
            </p>
          </div>
        </div>
      )}
    </div>,
    document.body,
  )
}
