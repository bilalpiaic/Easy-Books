'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import {
  X, RefreshCw, Download, RotateCcw, ExternalLink,
  CheckCircle, AlertCircle, Copy, Check as CopyDone,
} from 'lucide-react'
import { apiFetch } from '@/lib/api'

// ---------------------------------------------------------------------------
// Electron preload bridge types
// ---------------------------------------------------------------------------
declare global {
  interface Window {
    easybooks?: {
      isDesktop: boolean
      checkForUpdates: () => Promise<{ ok: boolean; error?: string }>
      installUpdate: () => void
      onUpdateStatus: (cb: (status: ElectronStatus) => void) => () => void
    }
  }
}

interface ElectronStatus {
  state: 'checking' | 'available' | 'none' | 'error' | 'downloading' | 'downloaded'
  version?: string
  percent?: number
  message?: string
}

// ---------------------------------------------------------------------------
// Version info stamped at build time by install-and-run scripts
// ---------------------------------------------------------------------------
const CURRENT_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? 'dev'
const CURRENT_COMMIT  = process.env.NEXT_PUBLIC_GIT_COMMIT  ?? ''
const BUILD_DATE      = process.env.NEXT_PUBLIC_BUILD_DATE  ?? ''

// "Update Now" only works when we have a real commit stamp to compare against
const CAN_AUTO_UPDATE = CURRENT_COMMIT !== '' && CURRENT_COMMIT !== 'dev'

const RELEASES_API  = 'https://api.github.com/repos/bilalpiaic/Easy-Books/releases/latest'
const RELEASES_PAGE = 'https://github.com/bilalpiaic/Easy-Books/releases'

function norm(v: string) { return v.replace(/^v/, '').trim() }
function shortCommit(c: string) { return c.length >= 7 ? c.slice(0, 7) : c || 'dev' }
function fmtBuildDate(iso: string) {
  if (!iso || iso === '2026-06-28T00:00:00Z') return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
  } catch { return '' }
}

function isDesktop() {
  return typeof window !== 'undefined' && window.easybooks?.isDesktop === true
}

// ---------------------------------------------------------------------------
// Copy-to-clipboard button
// ---------------------------------------------------------------------------
function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button onClick={copy} title="Copy"
      className="p-1 rounded hover:bg-black/10 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
      {copied
        ? <CopyDone className="w-3.5 h-3.5 text-green-600" />
        : <Copy className="w-3.5 h-3.5" />}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Copyable terminal command block
// ---------------------------------------------------------------------------
function CmdBlock({ win, unix }: { win: string; unix: string }) {
  return (
    <div className="bg-[var(--bg-page)] rounded-lg p-3 space-y-2">
      <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] mb-1">
        Run in your terminal
      </p>
      {([['Windows', win], ['macOS / Linux', unix]] as const).map(([label, cmd]) => (
        <div key={label} className="flex items-center gap-2">
          <span className="text-[10px] text-[var(--text-muted)] w-24 shrink-0">{label}</span>
          <span className="flex-1 font-mono text-[11px] bg-white border border-[var(--border)] rounded px-2 py-1 text-[var(--text-primary)] truncate">
            {cmd}
          </span>
          <CopyBtn text={cmd} />
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface UpdateModalProps { onClose: () => void }

// In-app update phase
type UpdatePhase = 'idle' | 'calling' | 'polling' | 'done' | 'error'

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function UpdateModal({ onClose }: UpdateModalProps) {
  // ── Server-side version.json probe ─────────────────────────────────────────
  const [serverInfo, setServerInfo] = useState<{ version: string; commit: string; built: string } | null>(null)
  const [serverDone, setServerDone] = useState(false)

  // ── Commit-level update check (backend) ─────────────────────────────────────
  const [commitStatus, setCommitStatus] = useState<{
    status: 'up_to_date' | 'update_available' | 'unknown'
    local: string; remote: string | null
  } | null>(null)

  // ── GitHub Releases probe ───────────────────────────────────────────────────
  const [ghVersion, setGhVersion]   = useState<string | null>(null)
  const [ghState, setGhState]       = useState<'loading' | 'ok' | 'no_release' | 'error'>('loading')

  // ── Electron updater ────────────────────────────────────────────────────────
  const [electronStatus, setElectronStatus] = useState<ElectronStatus | null>(null)
  const [confirmInstall, setConfirmInstall] = useState(false)

  // ── Re-check busy flag ──────────────────────────────────────────────────────
  const [rechecking, setRechecking] = useState(false)

  // ── In-app update state ─────────────────────────────────────────────────────
  const [updatePhase, setUpdatePhase] = useState<UpdatePhase>('idle')
  const [updateError, setUpdateError] = useState<string | null>(null)
  const [elapsed, setElapsed]         = useState(0)
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearTimeout(pollingRef.current)
      if (elapsedRef.current) clearInterval(elapsedRef.current)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Fetch helpers
  // ---------------------------------------------------------------------------
  const fetchServerVersion = useCallback(async () => {
    try {
      const res = await fetch('/version.json', { cache: 'no-store' })
      if (res.ok) setServerInfo(await res.json() as { version: string; commit: string; built: string })
    } catch { /* best effort */ }
    setServerDone(true)
  }, [])

  const fetchCommitStatus = useCallback(async () => {
    try {
      const res = await apiFetch<{
        status: 'up_to_date' | 'update_available' | 'unknown'
        local: string; remote: string | null
      }>('/api/system/update/status')
      setCommitStatus(res)
    } catch { /* ignore — backend unavailable */ }
  }, [])

  const fetchGitHub = useCallback(async () => {
    setGhState('loading')
    try {
      const res = await fetch(RELEASES_API, {
        headers: { Accept: 'application/vnd.github+json' },
        cache: 'no-store',
      })
      if (res.status === 404) { setGhState('no_release'); return }
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json() as { tag_name?: string }
      setGhVersion(norm(json.tag_name ?? ''))
      setGhState('ok')
    } catch { setGhState('error') }
  }, [])

  // ---------------------------------------------------------------------------
  // Polling — called after backend confirms git pull succeeded
  // Polls /version.json every 5 s; detects when server restarts with new build
  // ---------------------------------------------------------------------------
  const startPolling = useCallback(() => {
    const startMs = Date.now()
    const MAX_MS  = 5 * 60 * 1000   // 5-minute hard timeout

    setElapsed(0)
    elapsedRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startMs) / 1000))
    }, 1000)

    const poll = async () => {
      // Timeout guard
      if (Date.now() - startMs > MAX_MS) {
        if (elapsedRef.current) clearInterval(elapsedRef.current)
        setUpdatePhase('error')
        setUpdateError('Rebuild is taking longer than expected. Check if the server restarted correctly.')
        return
      }

      try {
        const res = await fetch('/version.json', {
          cache: 'no-store',
          signal: AbortSignal.timeout(5000),
        })
        if (res.ok) {
          const data = await res.json() as { version: string; commit: string; built: string }
          // Server is back up. If commit changed (or we had no baseline), we're done.
          const isNew = data.commit !== 'dev' && (
            !CAN_AUTO_UPDATE || data.commit !== CURRENT_COMMIT
          )
          if (isNew) {
            if (elapsedRef.current) clearInterval(elapsedRef.current)
            setUpdatePhase('done')
            // Auto-reload after 3 s so the user sees the "done" message
            setTimeout(() => window.location.reload(), 3000)
            return
          }
        }
      } catch { /* server still rebuilding — normal; keep polling */ }

      pollingRef.current = setTimeout(poll, 5000)
    }

    // First poll after 5 s (give the kill+restart script time to fire)
    pollingRef.current = setTimeout(poll, 5000)
  }, [])

  // ---------------------------------------------------------------------------
  // "Update Now" handler
  // ---------------------------------------------------------------------------
  const handleUpdateNow = async () => {
    setUpdatePhase('calling')
    setUpdateError(null)
    try {
      const res = await apiFetch<{ status: string; commit?: string; message?: string }>(
        '/api/system/update', { method: 'POST' },
      )
      if (res.status === 'up_to_date') {
        // No new code — just refresh the GitHub/version check
        setUpdatePhase('idle')
        handleRecheck()
      } else if (res.status === 'restarting') {
        setUpdatePhase('polling')
        startPolling()
      } else {
        // 'no_script' or unexpected
        setUpdatePhase('error')
        setUpdateError(res.message ?? 'Could not start update. Run the updater manually.')
      }
    } catch (e: unknown) {
      setUpdatePhase('error')
      const msg = e instanceof Error ? e.message : String(e)
      setUpdateError(msg || 'Update failed. Run the updater manually.')
    }
  }

  // ---------------------------------------------------------------------------
  // Effects
  // ---------------------------------------------------------------------------

  // Electron: wire update-status listener + auto-check on open
  useEffect(() => {
    if (!isDesktop()) return
    const unsub = window.easybooks!.onUpdateStatus(setElectronStatus)
    setElectronStatus({ state: 'checking' })
    window.easybooks!.checkForUpdates()
      .then(r => { if (!r.ok) setElectronStatus({ state: 'error', message: r.error }) })
      .catch(e => setElectronStatus({ state: 'error', message: String(e) }))
    return unsub
  }, [])

  // Script/web: probe all three sources on open
  useEffect(() => {
    if (isDesktop()) return
    fetchServerVersion()
    fetchGitHub()
    fetchCommitStatus()
  }, [fetchServerVersion, fetchGitHub, fetchCommitStatus])

  // Close on Escape
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  // ---------------------------------------------------------------------------
  // Derived state
  // ---------------------------------------------------------------------------
  const normalCurrent = norm(CURRENT_VERSION)
  const shortCur      = shortCommit(CURRENT_COMMIT)
  const builtOn       = fmtBuildDate(BUILD_DATE)

  // State A: update.sh already rebuilt the server — this page is stale
  const pageIsStale =
    serverDone &&
    serverInfo !== null &&
    serverInfo.commit !== 'dev' &&
    CURRENT_COMMIT !== '' &&
    CURRENT_COMMIT !== 'dev' &&
    serverInfo.commit !== CURRENT_COMMIT

  // State B: GitHub has a newer published release
  const ghNewer =
    !pageIsStale &&
    ghState === 'ok' &&
    ghVersion !== null &&
    ghVersion !== '' &&
    ghVersion !== normalCurrent

  // State C: newer commits on main branch (even without a tagged release)
  const commitNewer =
    !pageIsStale &&
    !ghNewer &&
    commitStatus?.status === 'update_available'

  // ---------------------------------------------------------------------------
  // Re-check handler
  // ---------------------------------------------------------------------------
  const handleRecheck = async () => {
    setRechecking(true)
    setServerDone(false); setServerInfo(null)
    setGhState('loading'); setGhVersion(null); setCommitStatus(null)
    await Promise.all([fetchServerVersion(), fetchGitHub(), fetchCommitStatus()])
    setRechecking(false)
  }

  // ---------------------------------------------------------------------------
  // Electron UI
  // ---------------------------------------------------------------------------
  function renderElectron() {
    const s = electronStatus

    if (!s) return (
      <button
        onClick={() => {
          setElectronStatus({ state: 'checking' })
          window.easybooks!.checkForUpdates()
            .then(r => { if (!r.ok) setElectronStatus({ state: 'error', message: r.error }) })
            .catch(e => setElectronStatus({ state: 'error', message: String(e) }))
        }}
        className="flex items-center gap-2 px-5 py-2.5 bg-[var(--primary)] text-white rounded-lg font-medium text-sm hover:bg-[var(--primary-dark)] transition-colors"
      >
        <RefreshCw className="w-4 h-4" /> Check for Updates
      </button>
    )

    if (s.state === 'checking') return (
      <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
        <RefreshCw className="w-4 h-4 animate-spin" /> Checking…
      </div>
    )

    if (s.state === 'available' || s.state === 'downloading') return (
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm text-[var(--text-muted)]">
          <span className="flex items-center gap-2"><Download className="w-4 h-4" /> Downloading…</span>
          {s.percent != null && (
            <span className="font-mono font-bold text-[var(--primary)]">{s.percent}%</span>
          )}
        </div>
        <div className="w-full bg-[var(--border)] rounded-full h-1.5">
          <div className="bg-[var(--primary)] h-1.5 rounded-full transition-all duration-300"
            style={{ width: `${s.percent ?? 0}%` }} />
        </div>
      </div>
    )

    if (s.state === 'downloaded') return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
          <CheckCircle className="w-4 h-4" />
          {s.version ? `v${s.version} is ready to install.` : 'Update ready.'}
        </div>
        {confirmInstall ? (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 space-y-2">
            <p className="text-sm text-amber-800 font-medium">Unsaved changes will be lost. Restart now?</p>
            <div className="flex gap-2">
              <button
                onClick={() => { try { window.easybooks!.installUpdate() } catch { /**/ } }}
                className="flex items-center gap-2 px-4 py-2 bg-[var(--text-primary)] text-white rounded-lg font-medium text-sm hover:bg-[var(--primary)] transition-colors"
              >
                <RotateCcw className="w-4 h-4" /> Yes, Restart
              </button>
              <button onClick={() => setConfirmInstall(false)}
                className="px-4 py-2 border border-black/20 rounded-lg font-medium text-sm hover:bg-black/5 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button onClick={() => setConfirmInstall(true)}
            className="flex items-center gap-2 px-5 py-2.5 bg-[var(--text-primary)] text-white rounded-lg font-medium text-sm hover:bg-[var(--primary)] transition-colors">
            <RotateCcw className="w-4 h-4" /> Restart &amp; Install
          </button>
        )}
      </div>
    )

    if (s.state === 'none') return (
      <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
        <CheckCircle className="w-4 h-4" /> You&apos;re up to date.
      </div>
    )

    return (
      <div className="space-y-3">
        <div className="flex items-start gap-2 text-sm text-red-600">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>Update check failed: {s.message ?? 'Unknown error'}</span>
        </div>
        <button
          onClick={() => {
            setElectronStatus({ state: 'checking' })
            window.easybooks!.checkForUpdates().catch(() => {})
          }}
          className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-medium hover:bg-[var(--bg-page)] transition-colors"
        >
          <RefreshCw className="w-4 h-4" /> Retry
        </button>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Script / web install UI
  // ---------------------------------------------------------------------------
  function renderWeb() {
    // ── In-app update progress ────────────────────────────────────────────────
    if (updatePhase === 'calling') return (
      <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
        <RefreshCw className="w-4 h-4 animate-spin" /> Pulling latest code…
      </div>
    )

    if (updatePhase === 'polling') return (
      <div className="space-y-3">
        <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200">
          <RefreshCw className="w-4 h-4 text-blue-600 mt-0.5 shrink-0 animate-spin" />
          <div>
            <p className="text-sm font-semibold text-blue-800">
              Rebuilding — please wait ({elapsed}s)
            </p>
            <p className="text-xs text-blue-600 mt-0.5">
              This usually takes 1–3 minutes. Keep this tab open.
            </p>
          </div>
        </div>
        <div className="w-full bg-[var(--border)] rounded-full h-1 overflow-hidden">
          <div className="h-full bg-[var(--primary)] rounded-full animate-pulse w-3/5" />
        </div>
      </div>
    )

    if (updatePhase === 'done') return (
      <div className="flex items-start gap-2 p-3 rounded-lg bg-green-50 border border-green-200">
        <CheckCircle className="w-4 h-4 text-green-700 mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-green-800">Update complete!</p>
          <p className="text-xs text-green-600 mt-0.5">Refreshing in 3 seconds…</p>
        </div>
      </div>
    )

    if (updatePhase === 'error') return (
      <div className="space-y-3">
        <div className="flex items-start gap-2 text-sm text-red-600">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{updateError ?? 'Update failed. Run the updater manually.'}</span>
        </div>
        <CmdBlock win="update.bat" unix="./update.sh" />
        <button
          onClick={() => { setUpdatePhase('idle'); setUpdateError(null) }}
          className="text-xs text-[var(--text-muted)] hover:text-[var(--primary)] transition-colors"
        >
          ← Back
        </button>
      </div>
    )

    // ── Normal states (updatePhase === 'idle') ────────────────────────────────
    if (!serverDone || ghState === 'loading') return (
      <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
        <RefreshCw className="w-4 h-4 animate-spin" /> Checking…
      </div>
    )

    // A: update.sh already ran — page is stale
    if (pageIsStale) return (
      <div className="space-y-3">
        <div className="flex items-start gap-2 p-3 rounded-lg bg-green-50 border border-green-200">
          <CheckCircle className="w-4 h-4 text-green-700 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm text-green-800 font-semibold">
              Server updated to v{serverInfo!.version}
            </p>
            <p className="text-xs text-green-700 mt-0.5">
              The updater has already run. Hard-refresh to load the new version.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.location.reload()}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg font-medium text-sm hover:bg-[var(--primary-dark)] transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Refresh Now
          </button>
          <span className="text-xs text-[var(--text-muted)]">
            or press <kbd className="font-mono bg-[var(--bg-page)] border border-[var(--border)] rounded px-1">Ctrl+Shift+R</kbd>
          </span>
        </div>
      </div>
    )

    // B: GitHub has a newer release
    if (ghNewer) return (
      <div className="space-y-3">
        <div className="flex items-start gap-2 p-3 rounded-lg bg-[var(--primary-light)] border border-[var(--primary)]/20">
          <Download className="w-4 h-4 text-[var(--primary)] mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-[var(--primary)]">v{ghVersion} is available</p>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              You&apos;re on v{normalCurrent}. Your data is preserved during the update.
            </p>
          </div>
        </div>

        {CAN_AUTO_UPDATE ? (
          <>
            {/* Primary CTA — one click triggers git pull + rebuild + restart */}
            <button
              onClick={handleUpdateNow}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[var(--primary)] text-white rounded-lg font-semibold text-sm hover:bg-[var(--primary-dark)] transition-colors"
            >
              <Download className="w-4 h-4" /> Update Now
            </button>

            {/* Fallback for power users */}
            <details className="group">
              <summary className="text-xs text-[var(--text-muted)] cursor-pointer hover:text-[var(--primary)] transition-colors list-none flex items-center gap-1">
                <span className="group-open:hidden">▸</span>
                <span className="hidden group-open:inline">▾</span>
                Or run manually
              </summary>
              <div className="mt-2">
                <CmdBlock win="update.bat" unix="./update.sh" />
              </div>
            </details>
          </>
        ) : (
          <CmdBlock win="update.bat" unix="./update.sh" />
        )}

        <a href={RELEASES_PAGE} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-[var(--primary)] hover:underline">
          <ExternalLink className="w-3.5 h-3.5" /> View release notes
        </a>
      </div>
    )

    // C: Commits available (no tagged release, but new commits on main)
    if (commitNewer) return (
      <div className="space-y-3">
        <div className="flex items-start gap-2 p-3 rounded-lg bg-[var(--primary-light)] border border-[var(--primary)]/20">
          <Download className="w-4 h-4 text-[var(--primary)] mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-[var(--primary)]">
              New commits available on main
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              You have <span className="font-mono">{commitStatus!.local}</span>.
              GitHub has <span className="font-mono">{commitStatus!.remote}</span>.
              Your data is preserved during the update.
            </p>
          </div>
        </div>

        {CAN_AUTO_UPDATE ? (
          <>
            <button
              onClick={handleUpdateNow}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[var(--primary)] text-white rounded-lg font-semibold text-sm hover:bg-[var(--primary-dark)] transition-colors"
            >
              <Download className="w-4 h-4" /> Update Now
            </button>
            <details className="group">
              <summary className="text-xs text-[var(--text-muted)] cursor-pointer hover:text-[var(--primary)] transition-colors list-none flex items-center gap-1">
                <span className="group-open:hidden">▸</span>
                <span className="hidden group-open:inline">▾</span>
                Or run manually
              </summary>
              <div className="mt-2">
                <CmdBlock win="update.bat" unix="./update.sh" />
              </div>
            </details>
          </>
        ) : (
          <CmdBlock win="update.bat" unix="./update.sh" />
        )}
      </div>
    )

    // D: No GitHub release yet
    if (ghState === 'no_release') return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
          <CheckCircle className="w-4 h-4" /> No GitHub Release published yet — you have the latest committed code.
        </div>
        <p className="text-xs text-[var(--text-muted)]">
          To pull any new commits, run the updater:
        </p>
        <CmdBlock win="update.bat" unix="./update.sh" />
      </div>
    )

    // D: GitHub fetch error
    if (ghState === 'error') return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm text-amber-600">
          <AlertCircle className="w-4 h-4 shrink-0" /> Couldn&apos;t reach GitHub — check your connection.
        </div>
        <CmdBlock win="update.bat" unix="./update.sh" />
      </div>
    )

    // E: Fully up to date
    return (
      <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
        <CheckCircle className="w-4 h-4" />
        You&apos;re up to date
        {commitStatus?.local
          ? <> — commit <span className="font-mono">{commitStatus.local}</span></>
          : ghVersion ? ` — v${normalCurrent} is the latest release` : ''
        }.
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Modal shell
  // ---------------------------------------------------------------------------
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog" aria-modal="true" aria-labelledby="update-modal-title">
      <div className="absolute inset-0 bg-[var(--text-primary)]/50 backdrop-blur-sm"
        onClick={onClose} aria-hidden="true" />

      <div className="relative bg-white rounded-2xl shadow-xl border border-[var(--border)] w-full max-w-md p-6 space-y-5">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2 id="update-modal-title" className="text-lg font-semibold text-[var(--text-primary)]">
              Check for Updates
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              {isDesktop() ? 'Desktop app — auto-updater.' : 'Script / web install'}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close"
            className="p-2 rounded-lg hover:bg-[var(--bg-page)] text-[var(--text-primary)]/50 hover:text-[var(--text-primary)] transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Version row */}
        <div className="flex flex-wrap items-start gap-x-4 gap-y-2 bg-[var(--bg-page)] rounded-xl px-4 py-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/40 mb-0.5">Version</p>
            <p className="font-mono font-bold text-[var(--text-primary)]">v{normalCurrent}</p>
          </div>
          <div className="w-px self-stretch bg-[var(--border)]" />
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/40 mb-0.5">Commit</p>
            <p className="font-mono font-bold text-[var(--text-primary)]">{shortCur}</p>
          </div>
          {builtOn && (
            <>
              <div className="w-px self-stretch bg-[var(--border)]" />
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/40 mb-0.5">Built</p>
                <p className="text-[12px] text-[var(--text-primary)]">{builtOn}</p>
              </div>
            </>
          )}
          {!isDesktop() && ghState === 'ok' && ghVersion && (
            <>
              <div className="w-px self-stretch bg-[var(--border)]" />
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/40 mb-0.5">Latest</p>
                <p className="font-mono font-bold text-[var(--primary)]">v{ghVersion}</p>
              </div>
            </>
          )}
        </div>

        {/* Body */}
        <div>{isDesktop() ? renderElectron() : renderWeb()}</div>

        {/* Footer — re-check + release history (hide during active update) */}
        {!isDesktop() && updatePhase === 'idle' && (
          <div className="flex items-center justify-between pt-1 border-t border-[var(--border-light)]">
            <button
              onClick={handleRecheck}
              disabled={rechecking || (!serverDone && ghState === 'loading')}
              className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--primary)] transition-colors disabled:opacity-40"
            >
              <RefreshCw className={`w-3 h-3 ${rechecking ? 'animate-spin' : ''}`} />
              Re-check
            </button>
            <a href={RELEASES_PAGE} target="_blank" rel="noopener noreferrer"
              className="text-xs text-[var(--text-muted)] hover:text-[var(--primary)] transition-colors">
              Release history ↗
            </a>
          </div>
        )}

      </div>
    </div>
  )
}
