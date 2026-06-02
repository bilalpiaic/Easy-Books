'use client'

import { useEffect, useState } from 'react'
import { X, RefreshCw, Download, RotateCcw, ExternalLink, CheckCircle, AlertCircle } from 'lucide-react'

// ---------------------------------------------------------------------------
// Type declaration for the Electron preload bridge
// ---------------------------------------------------------------------------
declare global {
  interface Window {
    easybooks?: {
      isDesktop: boolean
      checkForUpdates: () => Promise<{ ok: boolean; error?: string }>
      installUpdate: () => void
      onUpdateStatus: (cb: (status: UpdateStatus) => void) => () => void
    }
  }
}

interface UpdateStatus {
  state: 'checking' | 'available' | 'none' | 'error' | 'downloading' | 'downloaded'
  version?: string
  percent?: number
  message?: string
}

interface UpdateModalProps {
  onClose: () => void
}

const CURRENT_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? 'dev'
const RELEASES_API = 'https://api.github.com/repos/bilalpiaic/Easy-Books/releases/latest'
const RELEASES_PAGE = 'https://github.com/bilalpiaic/Easy-Books/releases/latest'

function normalise(v: string) {
  return v.replace(/^v/, '').trim()
}

function isDesktop() {
  return typeof window !== 'undefined' && window.easybooks?.isDesktop === true
}

export default function UpdateModal({ onClose }: UpdateModalProps) {
  const [latestVersion, setLatestVersion] = useState<string | null>(null)
  const [fetchError, setFetchError] = useState(false)
  const [fetching, setFetching] = useState(true)

  // Electron updater state machine
  const [updaterStatus, setUpdaterStatus] = useState<UpdateStatus | null>(null)

  // Fetch the latest GitHub release version on mount
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(RELEASES_API, { headers: { Accept: 'application/vnd.github+json' } })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json() as { tag_name?: string }
        if (!cancelled) setLatestVersion(normalise(json.tag_name ?? ''))
      } catch {
        if (!cancelled) setFetchError(true)
      } finally {
        if (!cancelled) setFetching(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  // Register the Electron update-status listener when in desktop mode
  useEffect(() => {
    if (!isDesktop()) return
    const unsubscribe = window.easybooks!.onUpdateStatus((status) => {
      setUpdaterStatus(status)
    })
    return unsubscribe
  }, [])

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const normalCurrent = normalise(CURRENT_VERSION)
  const normalLatest = latestVersion ? normalise(latestVersion) : null
  const updateAvailable =
    !fetchError &&
    normalLatest !== null &&
    normalLatest !== '' &&
    normalLatest !== normalCurrent

  // ---------------------------------------------------------------------------
  // Helpers for Electron updater UI
  // ---------------------------------------------------------------------------
  const handleCheckForUpdates = async () => {
    setUpdaterStatus({ state: 'checking' })
    try {
      const result = await window.easybooks!.checkForUpdates()
      if (!result.ok) {
        setUpdaterStatus({ state: 'error', message: result.error ?? 'Unknown error' })
      }
      // Success: status will arrive via onUpdateStatus events
    } catch (e) {
      setUpdaterStatus({ state: 'error', message: String(e) })
    }
  }

  const handleInstall = () => {
    try { window.easybooks!.installUpdate() } catch { /* best effort */ }
  }

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------
  function renderElectronActions() {
    const s = updaterStatus

    if (!s) {
      // Not yet triggered — show the button
      return (
        <button
          onClick={handleCheckForUpdates}
          className="flex items-center gap-2 px-5 py-2.5 bg-[#b8943f] text-white rounded-lg font-medium text-sm hover:bg-[#a07c35] transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Download &amp; Install
        </button>
      )
    }

    if (s.state === 'checking') {
      return (
        <div className="flex items-center gap-2 text-sm text-black/60">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Checking for updates…
        </div>
      )
    }

    if (s.state === 'available') {
      return (
        <div className="flex items-center gap-2 text-sm text-[#b8943f]">
          <Download className="w-4 h-4" />
          {s.version ? `Downloading v${s.version}…` : 'Downloading update…'}
        </div>
      )
    }

    if (s.state === 'downloading') {
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm text-black/70">
            <span className="flex items-center gap-2">
              <Download className="w-4 h-4" />
              Downloading…
            </span>
            <span className="font-mono font-bold text-[#b8943f]">{s.percent ?? 0}%</span>
          </div>
          <div className="w-full bg-[#ede9e2] rounded-full h-2">
            <div
              className="bg-[#b8943f] h-2 rounded-full transition-all duration-300"
              style={{ width: `${s.percent ?? 0}%` }}
            />
          </div>
        </div>
      )
    }

    if (s.state === 'downloaded') {
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
            <CheckCircle className="w-4 h-4" />
            {s.version ? `v${s.version} is ready.` : 'Update ready.'}
          </div>
          <button
            onClick={handleInstall}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#1a1814] text-white rounded-lg font-medium text-sm hover:bg-[#b8943f] transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Restart &amp; Install
          </button>
        </div>
      )
    }

    if (s.state === 'none') {
      return (
        <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
          <CheckCircle className="w-4 h-4" />
          You&apos;re up to date.
        </div>
      )
    }

    if (s.state === 'error') {
      return (
        <div className="space-y-3">
          <div className="flex items-start gap-2 text-sm text-red-600">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>Update check failed: {s.message ?? 'Unknown error'}</span>
          </div>
          <button
            onClick={handleCheckForUpdates}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-medium hover:bg-[#f6f3ee] transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      )
    }

    return null
  }

  function renderWebContent() {
    if (fetching) {
      return (
        <div className="flex items-center gap-2 text-sm text-black/50">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Checking GitHub for latest release…
        </div>
      )
    }

    if (fetchError) {
      return (
        <div className="flex items-center gap-2 text-sm text-amber-600">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          Couldn&apos;t check for updates — check your connection.
        </div>
      )
    }

    if (updateAvailable) {
      return (
        <div className="space-y-3">
          <p className="text-sm text-[#1a1814]">
            A new version (<span className="font-bold text-[#b8943f]">v{normalLatest}</span>) is available.
            Close the app and run the updater script — your data is preserved.
          </p>
          <div className="bg-[#f6f3ee] rounded-lg p-4 space-y-2">
            <p className="text-xs font-bold uppercase tracking-widest text-[#1a1814]/50 mb-2">Run in your terminal</p>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono bg-white border border-[#ede9e2] rounded px-2 py-1 text-[#1a1814]">
                Windows: update.bat
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono bg-white border border-[#ede9e2] rounded px-2 py-1 text-[#1a1814]">
                macOS / Linux: ./update.sh
              </span>
            </div>
          </div>
          <a
            href={RELEASES_PAGE}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm text-[#b8943f] hover:underline font-medium"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            View release notes on GitHub
          </a>
        </div>
      )
    }

    // Up to date
    return (
      <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
        <CheckCircle className="w-4 h-4" />
        You&apos;re up to date.
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Modal render
  // ---------------------------------------------------------------------------
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="update-modal-title"
    >
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-[#1a1814]/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Card */}
      <div className="relative bg-white rounded-2xl shadow-xl border border-[#ede9e2] w-full max-w-md p-6 space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2 id="update-modal-title" className="text-lg font-semibold text-[#1a1814]">
              Check for Updates
            </h2>
            <p className="text-xs text-black/50 mt-0.5">
              {isDesktop() ? 'Desktop app — updates install automatically.' : 'Web / script install'}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-2 rounded-lg hover:bg-[#f6f3ee] text-[#1a1814]/50 hover:text-[#1a1814] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Version row */}
        <div className="flex items-center gap-4 bg-[#f6f3ee] rounded-xl px-4 py-3 text-sm">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-0.5">Current</p>
            <p className="font-mono font-bold text-[#1a1814]">v{normalCurrent}</p>
          </div>
          <div className="w-px h-8 bg-[#ede9e2]" />
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-0.5">Latest</p>
            <p className="font-mono font-bold text-[#b8943f]">
              {fetching ? '…' : fetchError ? '?' : `v${normalLatest}`}
            </p>
          </div>
          {!fetching && !fetchError && updateAvailable && (
            <span className="ml-auto px-2.5 py-1 bg-[#b8943f]/10 text-[#b8943f] rounded-full text-[11px] font-bold uppercase tracking-wide">
              Update available
            </span>
          )}
        </div>

        {/* Body — desktop or web branch */}
        <div>
          {isDesktop() ? renderElectronActions() : renderWebContent()}
        </div>
      </div>
    </div>
  )
}
