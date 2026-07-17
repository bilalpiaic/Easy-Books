"use client"

import { useEffect, useRef, useState } from "react"
import { Send, Loader2, KeyRound, ChevronDown } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { streamChat } from "@/lib/aiStream"
import ChatMarkdown from "./ChatMarkdown"
import AiModelKeyPanel from "./AiModelKeyPanel"

interface Message {
  id?: number
  role: "user" | "assistant"
  content: string
  model?: string | null
}

interface ModelInfo {
  provider: string
  label: string
  models: string[]
}

export interface ModelsPayload {
  providers: ModelInfo[]
  default_model: string | null
}

interface ChatCoreProps {
  sessionId: number
  models: ModelsPayload
  className?: string
  /** Fired once, after the session's first message completes — the backend
   * auto-titles the session from that message, so callers with a visible
   * session list (the /agent sidebar) should refetch it here. */
  onFirstMessageSent?: () => void
  /** Called after a key is saved/cleared in the Model & API Key panel so the
   * caller can refetch /api/ai/models and pass an updated `models` prop back
   * down — a newly-configured provider otherwise never appears in the picker. */
  onModelsRefresh?: () => void
}

const QUICK_PROMPTS = [
  "What's my revenue this month?",
  "Which invoices are overdue?",
  "Show me my P&L summary",
  "What's my cash balance?",
]

export default function ChatCore({ sessionId, models, className, onFirstMessageSent, onModelsRefresh }: ChatCoreProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [streamingText, setStreamingText] = useState<string | null>(null)
  const [toolLabel, setToolLabel] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string>(models.default_model ?? "")
  const [showModelKeyPanel, setShowModelKeyPanel] = useState(false)

  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const streamingRef = useRef("")
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  useEffect(() => {
    setSelectedModel(models.default_model ?? "")
  }, [models.default_model])

  // Load message history whenever the active session changes.
  useEffect(() => {
    let cancelled = false
    setLoadingHistory(true)
    setError(null)
    setStreamingText(null)
    setToolLabel(null)
    streamingRef.current = ""
    apiFetch<Message[]>(`/api/ai/sessions/${sessionId}/messages`)
      .then(rows => {
        if (cancelled || !mountedRef.current) return
        setMessages(rows)
      })
      .catch((err: unknown) => {
        if (cancelled || !mountedRef.current) return
        setError(err instanceof Error ? err.message : "Failed to load chat history.")
      })
      .finally(() => {
        if (cancelled || !mountedRef.current) return
        setLoadingHistory(false)
      })
    return () => {
      cancelled = true
    }
  }, [sessionId])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamingText, toolLabel, loadingHistory])

  // Auto-grow the composer up to max-h-24 (the Tailwind class caps the pixel
  // height we set here and overflow-y-auto takes over beyond it) — rows={1}
  // alone never grows past one line.
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${el.scrollHeight}px`
  }, [input])

  const handleStreamError = (detail: string) => {
    if (!mountedRef.current) return
    // Commit whatever text streamed in before the failure, if any, so it isn't lost.
    if (streamingRef.current) {
      setMessages(prev => [
        ...prev,
        { role: "assistant", content: streamingRef.current, model: selectedModel || null },
      ])
    }
    streamingRef.current = ""
    setStreamingText(null)
    setToolLabel(null)
    setError(detail)
    setSending(false)
  }

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    const isFirstMessage = messages.length === 0
    setInput("")
    setError(null)
    setMessages(prev => [...prev, { role: "user", content: trimmed }])
    streamingRef.current = ""
    setStreamingText("")
    setSending(true)

    try {
      await streamChat(
        { session_id: sessionId, message: trimmed, model: selectedModel || null },
        {
          onToken: text => {
            if (!mountedRef.current) return
            // The first real token is the implicit end of any pipeline-stage
            // or tool-progress label (e.g. "Drafting your report…") — no
            // separate stage-end frame needed.
            setToolLabel(null)
            streamingRef.current += text
            setStreamingText(streamingRef.current)
          },
          onToolStart: label => {
            if (!mountedRef.current) return
            setToolLabel(label)
          },
          onToolEnd: () => {
            if (!mountedRef.current) return
            setToolLabel(null)
          },
          onStage: label => {
            if (!mountedRef.current) return
            setToolLabel(label)
          },
          onDone: (_sid, messageId, reply) => {
            if (!mountedRef.current) return
            // Trust the backend's authoritative "reply" over the locally
            // accumulated token buffer: they normally match, but when the
            // model only ever emits tool_calls with no content deltas, the
            // backend substitutes a fallback message that was never
            // streamed as tokens -- using streamingRef.current there would
            // commit a blank bubble even though a real reply was persisted.
            setMessages(prev => [
              ...prev,
              { id: messageId, role: "assistant", content: reply || streamingRef.current, model: selectedModel || null },
            ])
            streamingRef.current = ""
            setStreamingText(null)
            setToolLabel(null)
            setSending(false)
            // The backend auto-titles the session from this message once it
            // was still "New chat" — let a listing parent (e.g. /agent's
            // sidebar) know so the displayed title doesn't stay stale.
            if (isFirstMessage) onFirstMessageSent?.()
          },
          onError: handleStreamError,
        },
      )
    } catch {
      // Belt-and-braces: streamChat should never reject after its own terminal-event
      // guarantee, but the UI must never be able to lock up if it somehow does.
      handleStreamError("The AI response ended unexpectedly. Please try again.")
    }
  }

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const isEmpty = messages.length === 0 && streamingText === null

  return (
    <div className={`flex flex-col min-h-0 flex-1 ${className ?? ""}`}>
      {/* Model & API Key — always visible, regardless of configuration state,
          so there is always a discoverable path to set up a provider instead
          of the picker silently disappearing when none is configured yet. */}
      <div className="print:hidden shrink-0 px-3 pt-2 pb-1 border-b border-[var(--text-primary)]/10 bg-white">
        <button
          type="button"
          onClick={() => setShowModelKeyPanel(true)}
          className="w-full flex items-center justify-between gap-2 text-xs rounded-lg border border-[var(--text-primary)]/15 px-2.5 py-1.5 bg-[var(--bg-page)] text-[var(--text-primary)] hover:border-[var(--primary)]/40 transition-colors"
        >
          <span className="flex items-center gap-1.5 min-w-0">
            <KeyRound className="w-3.5 h-3.5 shrink-0 text-[var(--primary)]" />
            <span className="truncate">
              {selectedModel || (models.providers.length === 0 ? "No AI model configured" : "Choose a model")}
            </span>
          </span>
          <ChevronDown className="w-3.5 h-3.5 shrink-0 opacity-50" />
        </button>
      </div>

      {showModelKeyPanel && (
        <AiModelKeyPanel
          models={models}
          selectedModel={selectedModel}
          onSelectModel={setSelectedModel}
          onModelsRefresh={onModelsRefresh}
          onClose={() => setShowModelKeyPanel(false)}
        />
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-[var(--bg-page)]">
        {loadingHistory && (
          <div className="flex justify-center py-4">
            <Loader2 className="w-4 h-4 animate-spin text-[var(--primary)]" />
          </div>
        )}

        {!loadingHistory && isEmpty && (
          <div className="space-y-3">
            <p className="text-xs text-center text-[var(--text-primary)]/50 py-2">
              Ask me anything about your finances
            </p>
            <div className="grid grid-cols-1 gap-2">
              {QUICK_PROMPTS.map(p => (
                <button
                  key={p}
                  onClick={() => send(p)}
                  className="text-left text-xs px-3 py-2 rounded-xl bg-white border border-[var(--text-primary)]/10 hover:border-[var(--primary)]/40 hover:bg-[var(--primary)]/5 transition-all text-[var(--text-primary)]/70"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={msg.id ?? i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-[var(--primary)] text-white rounded-br-md whitespace-pre-wrap"
                  : "bg-white border border-[var(--text-primary)]/10 text-[var(--text-primary)] rounded-bl-md"
              }`}
            >
              {msg.role === "assistant" ? <ChatMarkdown content={msg.content} /> : msg.content}
            </div>
          </div>
        ))}

        {toolLabel && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 bg-white border border-[var(--text-primary)]/10 rounded-2xl rounded-bl-md px-3 py-2 text-xs text-[var(--text-primary)]/60">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--primary)]" />
              {toolLabel}
            </div>
          </div>
        )}

        {streamingText !== null && !toolLabel && (
          <div className="flex justify-start">
            <div className="max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed bg-white border border-[var(--text-primary)]/10 text-[var(--text-primary)] rounded-bl-md">
              {streamingText.length > 0
                ? <ChatMarkdown content={streamingText} />
                : <Loader2 className="w-4 h-4 animate-spin text-[var(--primary)]" />}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="shrink-0 mx-3 mb-2 px-3 py-2 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700">
          {error}
        </div>
      )}

      {/* Input */}
      <div className="print:hidden shrink-0 border-t border-[var(--text-primary)]/10 bg-white px-3 py-2 flex items-end gap-2">
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about your finances…"
          rows={1}
          disabled={sending}
          className="flex-1 resize-none text-sm rounded-xl border border-[var(--text-primary)]/15 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 text-[var(--text-primary)] placeholder:text-[var(--text-primary)]/40 bg-[var(--bg-page)] max-h-24 overflow-y-auto disabled:opacity-60"
          style={{ lineHeight: "1.4" }}
        />
        <button
          onClick={() => send(input)}
          disabled={!input.trim() || sending}
          className="shrink-0 p-2 rounded-xl bg-[var(--primary)] text-white hover:opacity-90 disabled:opacity-40 transition-all"
          aria-label="Send"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
