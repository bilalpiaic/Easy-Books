"use client"

import { useEffect, useRef, useState } from "react"
import { Send, Loader2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { streamChat } from "@/lib/aiStream"

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
}

const QUICK_PROMPTS = [
  "What's my revenue this month?",
  "Which invoices are overdue?",
  "Show me my P&L summary",
  "What's my cash balance?",
]

export default function ChatCore({ sessionId, models, className }: ChatCoreProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [streamingText, setStreamingText] = useState<string | null>(null)
  const [toolLabel, setToolLabel] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string>(models.default_model ?? "")

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

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    setInput("")
    setError(null)
    setMessages(prev => [...prev, { role: "user", content: trimmed }])
    streamingRef.current = ""
    setStreamingText("")
    setSending(true)

    await streamChat(
      { session_id: sessionId, message: trimmed, model: selectedModel || null },
      {
        onToken: text => {
          if (!mountedRef.current) return
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
        onDone: (_sid, messageId) => {
          if (!mountedRef.current) return
          setMessages(prev => [
            ...prev,
            { id: messageId, role: "assistant", content: streamingRef.current, model: selectedModel || null },
          ])
          streamingRef.current = ""
          setStreamingText(null)
          setToolLabel(null)
          setSending(false)
        },
        onError: detail => {
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
        },
      },
    )
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
      {/* Model picker */}
      {models.providers.length > 0 && (
        <div className="shrink-0 px-3 pt-2 pb-1 border-b border-[var(--text-primary)]/10 bg-white">
          <select
            value={selectedModel}
            onChange={e => setSelectedModel(e.target.value)}
            disabled={sending}
            className="w-full text-xs rounded-lg border border-[var(--text-primary)]/15 px-2 py-1.5 bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 disabled:opacity-50"
          >
            {models.providers.map(p => (
              <optgroup key={p.provider} label={p.label}>
                {p.models.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
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
              className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed ${
                msg.role === "user"
                  ? "bg-[var(--primary)] text-white rounded-br-md"
                  : "bg-white border border-[var(--text-primary)]/10 text-[var(--text-primary)] rounded-bl-md"
              }`}
            >
              {msg.content}
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
            <div className="max-w-[85%] px-3 py-2 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed bg-white border border-[var(--text-primary)]/10 text-[var(--text-primary)] rounded-bl-md">
              {streamingText.length > 0
                ? streamingText
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
      <div className="shrink-0 border-t border-[var(--text-primary)]/10 bg-white px-3 py-2 flex items-end gap-2">
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
