"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { X, Sparkles, Loader2, Plus, Minus, Maximize2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import ChatCore, { type ModelsPayload } from "@/components/ai/ChatCore"
import { useDraggablePanel } from "@/hooks/useDraggablePanel"

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

  const { panelRef, pos, minimized, dragging, startDrag, toggleMinimized } =
    useDraggablePanel("eb.aichat")

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

  // Re-fetches just the model list — used after a key is saved/cleared in
  // the Model & API Key panel so a newly-configured provider's models show
  // up without needing to close and reopen the chat.
  const loadModels = async () => {
    try {
      setModels(await apiFetch<ModelsPayload>("/api/ai/models"))
    } catch {
      // Silent — the panel's own save/clear call already surfaces its own error.
    }
  }

  if (!open) return null

  const panel = (
    <div
      ref={panelRef}
      className={`fixed z-[900] w-[calc(100vw-2rem)] max-w-sm flex flex-col bg-white rounded-3xl shadow-2xl border border-[var(--text-primary)]/10 overflow-hidden ${
        pos ? "" : "bottom-20 right-4 md:bottom-6 md:right-6"
      } ${dragging ? "select-none" : ""}`}
      style={{
        ...(pos ? { left: pos.x, top: pos.y } : {}),
        height: minimized ? "auto" : "min(520px, calc(100vh - 7rem))",
      }}
    >
      {/* Header — also the drag handle */}
      <div
        onPointerDown={startDrag}
        className={`flex items-center justify-between px-4 py-3 bg-[var(--primary)] text-white shrink-0 ${dragging ? "cursor-grabbing" : "cursor-grab"}`}
      >
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
            onClick={toggleMinimized}
            className="p-1 rounded-lg hover:bg-white/20 transition-colors"
            aria-label={minimized ? "Restore" : "Minimize"}
            title={minimized ? "Restore" : "Minimize"}
          >
            {minimized ? <Maximize2 className="w-4 h-4" /> : <Minus className="w-4 h-4" />}
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

      {/* Body — kept mounted (not unmounted) while minimized so an in-flight
          stream or scroll position isn't lost; just visually collapsed. */}
      <div className={minimized ? "hidden" : "flex-1 flex flex-col min-h-0"}>
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
          <ChatCore
            key={sessionId}
            sessionId={sessionId}
            models={models}
            className="min-h-0"
            onModelsRefresh={loadModels}
          />
        )}
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
