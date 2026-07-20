"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Check, Loader2, MessagesSquare, Pencil, Plus, Sparkles, Trash2, X } from "lucide-react"
import { apiFetch, apiBase } from "@/lib/api"
import { getAuthHeader } from "@/lib/auth"
import ChatCore, { type ModelsPayload } from "@/components/ai/ChatCore"
import { useMessages } from "@/context/MessageContext"

interface SessionSummary {
  id: number
  title: string
  updated_at: string
}

/** Height reserved for TopNav + TabBar + page padding above the two-column layout. */
const PAGE_HEIGHT = "h-[calc(100dvh-190px)] min-h-[480px]"

export default function AgentPage() {
  const { confirm } = useMessages()
  const [models, setModels] = useState<ModelsPayload | null>(null)
  const [moduleBlocked, setModuleBlocked] = useState(false)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [initError, setInitError] = useState<string | null>(null)

  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState("")
  const [renameError, setRenameError] = useState<string | null>(null)
  const [renameSaving, setRenameSaving] = useState(false)

  const [creating, setCreating] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  // Below md the session rail and the chat thread are two swappable panes
  // (the fixed 260px rail would leave almost nothing for the thread on a
  // phone); md+ always shows both side by side and ignores this state.
  const [mobileRailOpen, setMobileRailOpen] = useState(false)

  // Initial load: models (raw fetch so we can inspect the 403 status directly —
  // apiFetch collapses non-ok responses to an Error with no status code attached),
  // then the session list, resuming the newest session or creating one.
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setInitError(null)
    ;(async () => {
      try {
        const res = await fetch(`${apiBase}/api/ai/models`, { headers: { ...getAuthHeader() } })
        if (res.status === 403) {
          if (!cancelled) setModuleBlocked(true)
          return
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          const detail = (data as { detail?: unknown }).detail
          throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`)
        }
        const modelsData = (await res.json()) as ModelsPayload
        if (cancelled) return
        setModels(modelsData)

        const sessionRows = await apiFetch<SessionSummary[]>("/api/ai/sessions")
        if (cancelled) return
        if (sessionRows.length > 0) {
          setSessions(sessionRows)
          setSelectedId(sessionRows[0].id)
        } else {
          const created = await apiFetch<SessionSummary>("/api/ai/sessions", { method: "POST" })
          if (cancelled) return
          setSessions([created])
          setSelectedId(created.id)
        }
      } catch (err) {
        if (!cancelled) setInitError(err instanceof Error ? err.message : "Failed to load the AI assistant.")
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const refreshSessions = useCallback(async () => {
    try {
      const rows = await apiFetch<SessionSummary[]>("/api/ai/sessions")
      setSessions(rows)
    } catch {
      // Non-critical — the sidebar just keeps its current (stale) title/order.
    }
  }, [])

  // Re-fetches just the model list — used after a key is saved/cleared in
  // the Model & API Key panel so a newly-configured provider's models show
  // up without needing to reload the page.
  const loadModels = useCallback(async () => {
    try {
      setModels(await apiFetch<ModelsPayload>("/api/ai/models"))
    } catch {
      // Silent — the panel's own save/clear call already surfaces its own error.
    }
  }, [])

  const newChat = useCallback(async () => {
    if (creating) return
    setCreating(true)
    try {
      const created = await apiFetch<SessionSummary>("/api/ai/sessions", { method: "POST" })
      setSessions(prev => [created, ...prev])
      setSelectedId(created.id)
    } catch {
      // Session creation failed silently — user can retry via the button.
    } finally {
      setCreating(false)
    }
  }, [creating])

  const startRename = (s: SessionSummary) => {
    setRenamingId(s.id)
    setRenameValue(s.title)
    setRenameError(null)
  }

  const cancelRename = () => {
    setRenamingId(null)
    setRenameValue("")
    setRenameError(null)
  }

  const saveRename = async (id: number) => {
    if (renameSaving) return
    setRenameSaving(true)
    setRenameError(null)
    try {
      const updated = await apiFetch<{ id: number; title: string }>(`/api/ai/sessions/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: renameValue }),
      })
      setSessions(prev => prev.map(s => (s.id === id ? { ...s, title: updated.title } : s)))
      setRenamingId(null)
      setRenameValue("")
    } catch (err) {
      // Surface the backend's 400-on-empty-title (and any other) error inline —
      // never swallow it, so the user knows why the rename didn't take.
      setRenameError(err instanceof Error ? err.message : "Rename failed.")
    } finally {
      setRenameSaving(false)
    }
  }

  const removeSession = async (id: number) => {
    const ok = await confirm({
      title: "Delete this chat?",
      message: "This cannot be undone.",
      confirmLabel: "Delete",
      danger: true,
    })
    if (!ok) return
    setDeletingId(id)
    try {
      await apiFetch(`/api/ai/sessions/${id}`, { method: "DELETE" })
      const remaining = sessions.filter(s => s.id !== id)
      setSessions(remaining)
      if (selectedId === id) {
        if (remaining.length > 0) {
          setSelectedId(remaining[0].id)
        } else {
          const created = await apiFetch<SessionSummary>("/api/ai/sessions", { method: "POST" })
          setSessions([created])
          setSelectedId(created.id)
        }
      }
    } catch {
      // Delete failed silently — row stays in the list, user can retry.
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) {
    return (
      <div className={`flex items-center justify-center ${PAGE_HEIGHT}`}>
        <Loader2 className="w-6 h-6 animate-spin text-[var(--primary)]" />
      </div>
    )
  }

  if (moduleBlocked) {
    return (
      <div className={`flex flex-col items-center justify-center gap-3 px-4 text-center ${PAGE_HEIGHT}`}>
        <Sparkles className="w-10 h-10 text-[var(--primary)]/40" />
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">AI Assistant not installed</h2>
        <p className="max-w-sm text-sm text-[var(--text-primary)]/60">
          Install the AI Assistant from System → Apps to start chatting with your financial data.
        </p>
        <Link
          href="/apps"
          className="mt-2 rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white transition-all hover:opacity-90"
        >
          Go to Apps
        </Link>
      </div>
    )
  }

  if (initError) {
    return (
      <div className={`flex items-center justify-center px-4 ${PAGE_HEIGHT}`}>
        <p className="text-center text-sm text-red-600">{initError}</p>
      </div>
    )
  }

  if (!models || selectedId === null) return null

  const currentTitle = sessions.find(s => s.id === selectedId)?.title ?? "New chat"

  return (
    <div className={`flex gap-3 ${PAGE_HEIGHT}`}>
      {/* Session rail — always visible md+; below md it swaps with the chat
          thread (opened from the thread's mobile header). */}
      <div
        className={`print:hidden ${mobileRailOpen ? "flex" : "hidden"} w-full shrink-0 flex-col overflow-hidden rounded-2xl border border-[var(--text-primary)]/10 bg-white md:flex md:w-[260px]`}
      >
        <div className="shrink-0 border-b border-[var(--text-primary)]/10 p-2">
          <button
            onClick={() => {
              setMobileRailOpen(false)
              newChat()
            }}
            disabled={creating}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--primary)] px-3 py-2 text-sm font-medium text-white transition-all hover:opacity-90 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            New chat
          </button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto p-2">
          {sessions.map(s => {
            const isSelected = s.id === selectedId
            const isRenaming = renamingId === s.id
            return (
              <div
                key={s.id}
                onClick={() => {
                  if (isRenaming) return
                  setSelectedId(s.id)
                  setMobileRailOpen(false)
                }}
                className={`group rounded-xl px-2 py-2 text-sm transition-all ${
                  isRenaming ? "" : "cursor-pointer"
                } ${
                  isSelected
                    ? "bg-[var(--primary)]/10 text-[var(--text-primary)]"
                    : "text-[var(--text-primary)]/70 hover:bg-[var(--bg-page)]"
                }`}
              >
                {isRenaming ? (
                  <div onClick={e => e.stopPropagation()} className="space-y-1">
                    <div className="flex items-center gap-1">
                      <input
                        autoFocus
                        value={renameValue}
                        onChange={e => setRenameValue(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === "Enter") saveRename(s.id)
                          if (e.key === "Escape") cancelRename()
                        }}
                        className="min-w-0 flex-1 rounded-lg border border-[var(--text-primary)]/20 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
                      />
                      <button
                        onClick={() => saveRename(s.id)}
                        disabled={renameSaving}
                        aria-label="Save name"
                        title="Save"
                        className="shrink-0 rounded-lg p-1 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={cancelRename}
                        aria-label="Cancel rename"
                        title="Cancel"
                        className="shrink-0 rounded-lg p-1 hover:bg-[var(--text-primary)]/10"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    {renameError && <p className="px-1 text-[10px] text-red-600">{renameError}</p>}
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    <span className="flex-1 truncate">{s.title}</span>
                    <button
                      onClick={e => {
                        e.stopPropagation()
                        startRename(s)
                      }}
                      aria-label="Rename chat"
                      title="Rename"
                      className="shrink-0 rounded-lg p-1 transition-opacity hover:bg-[var(--text-primary)]/10 md:opacity-0 md:group-hover:opacity-100"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={e => {
                        e.stopPropagation()
                        removeSession(s.id)
                      }}
                      disabled={deletingId === s.id}
                      aria-label="Delete chat"
                      title="Delete"
                      className="shrink-0 rounded-lg p-1 transition-opacity hover:bg-red-50 hover:text-red-600 disabled:opacity-50 md:opacity-0 md:group-hover:opacity-100"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Chat thread — hidden below md while the session rail is open */}
      <div
        className={`${mobileRailOpen ? "hidden" : "flex"} min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-[var(--text-primary)]/10 bg-white md:flex`}
      >
        {/* Mobile-only header: opens the session rail (md+ shows it side by side) */}
        <div className="flex shrink-0 items-center gap-2 border-b border-[var(--text-primary)]/10 px-2 py-1.5 md:hidden">
          <button
            onClick={() => setMobileRailOpen(true)}
            aria-label="Show chats"
            className="flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-[var(--primary)] hover:bg-[var(--primary)]/10 transition-colors"
          >
            <MessagesSquare className="h-4 w-4" />
            Chats
          </button>
          <span className="min-w-0 flex-1 truncate text-xs text-[var(--text-primary)]/60">{currentTitle}</span>
        </div>
        <ChatCore
          key={selectedId}
          sessionId={selectedId}
          models={models}
          className="min-h-0"
          onFirstMessageSent={refreshSessions}
          onModelsRefresh={loadModels}
        />
      </div>
    </div>
  )
}
