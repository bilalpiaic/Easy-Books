"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { X, Sparkles, Loader2, Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import ChatCore, { type ModelsPayload } from "@/components/ai/ChatCore"

interface AIChatProps {
  open: boolean
  onClose: () => void
}

interface SessionSummary {
  id: number
  title: string
  updated_at: string
}

export default function AIChat({ open, onClose }: AIChatProps) {
  const [models, setModels] = useState<ModelsPayload | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [initLoading, setInitLoading] = useState(false)
  const [initError, setInitError] = useState<string | null>(null)

  // First time the panel opens: load available models and resume (or create) a session.
  useEffect(() => {
    if (!open || models !== null) return
    let cancelled = false
    setInitLoading(true)
    setInitError(null)
    Promise.all([
      apiFetch<ModelsPayload>("/api/ai/models"),
      apiFetch<SessionSummary[]>("/api/ai/sessions"),
    ])
      .then(async ([modelsData, sessions]) => {
        if (cancelled) return
        setModels(modelsData)
        if (sessions.length > 0) {
          setSessionId(sessions[0].id)
        } else {
          const created = await apiFetch<SessionSummary>("/api/ai/sessions", { method: "POST" })
          if (cancelled) return
          setSessionId(created.id)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setInitError(err instanceof Error ? err.message : "Failed to start the AI assistant.")
      })
      .finally(() => {
        if (cancelled) return
        setInitLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, models])

  const newChat = async () => {
    try {
      const created = await apiFetch<SessionSummary>("/api/ai/sessions", { method: "POST" })
      setSessionId(created.id)
    } catch {
      // Session creation failed silently — user can retry via the button.
    }
  }

  if (!open) return null

  const panel = (
    <div className="fixed bottom-20 right-4 md:bottom-6 md:right-6 z-[900] w-[calc(100vw-2rem)] max-w-sm flex flex-col bg-white rounded-3xl shadow-2xl border border-[var(--text-primary)]/10 overflow-hidden"
      style={{ height: "min(520px, calc(100vh - 7rem))" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-[var(--primary)] text-white shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4" />
          <span className="font-semibold text-sm">AI Assistant</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={newChat}
            disabled={initLoading || sessionId === null}
            className="p-1 rounded-lg hover:bg-white/20 transition-colors disabled:opacity-40"
            aria-label="New chat"
            title="New chat"
          >
            <Plus className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-white/20 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {initLoading && (
        <div className="flex-1 flex items-center justify-center bg-[var(--bg-page)]">
          <Loader2 className="w-5 h-5 animate-spin text-[var(--primary)]" />
        </div>
      )}

      {!initLoading && initError && (
        <div className="flex-1 flex items-center justify-center bg-[var(--bg-page)] p-4">
          <p className="text-xs text-center text-red-600">{initError}</p>
        </div>
      )}

      {!initLoading && !initError && models && sessionId !== null && (
        <ChatCore key={sessionId} sessionId={sessionId} models={models} className="min-h-0" />
      )}
    </div>
  )

  return createPortal(panel, document.body)
}
