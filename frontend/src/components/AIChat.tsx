"use client"

import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { X, Send, Sparkles, Loader2 } from "lucide-react"
import { apiFetch } from "@/lib/api"

interface Message {
  role: "user" | "assistant"
  content: string
}

interface AIChatProps {
  open: boolean
  onClose: () => void
}

const QUICK_PROMPTS = [
  "What's my revenue this month?",
  "Which invoices are overdue?",
  "Show me my P&L summary",
  "What's my cash balance?",
]

export default function AIChat({ open, onClose }: AIChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
    } else {
      setMessages([])
      setInput("")
    }
  }, [open])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, loading])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return
    setInput("")

    const userMsg: Message = { role: "user", content: trimmed }
    const history = messages
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const data = await apiFetch<{ reply: string }>("/api/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          message: trimmed,
          history: history.map(m => ({ role: m.role, content: m.content })),
        }),
      })
      setMessages(prev => [...prev, { role: "assistant", content: data.reply }])
    } catch (err: unknown) {
      const detail =
        err instanceof Error ? err.message : "Something went wrong. Please try again."
      setMessages(prev => [
        ...prev,
        { role: "assistant", content: `Sorry, I couldn't get an answer: ${detail}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send(input)
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
        <button
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-white/20 transition-colors"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-[var(--bg-page)]">
        {messages.length === 0 && !loading && (
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
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
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

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-[var(--text-primary)]/10 rounded-2xl rounded-bl-md px-3 py-2">
              <Loader2 className="w-4 h-4 animate-spin text-[var(--primary)]" />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-[var(--text-primary)]/10 bg-white px-3 py-2 flex items-end gap-2">
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about your finances…"
          rows={1}
          className="flex-1 resize-none text-sm rounded-xl border border-[var(--text-primary)]/15 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 text-[var(--text-primary)] placeholder:text-[var(--text-primary)]/40 bg-[var(--bg-page)] max-h-24 overflow-y-auto"
          style={{ lineHeight: "1.4" }}
        />
        <button
          onClick={() => send(input)}
          disabled={!input.trim() || loading}
          className="shrink-0 p-2 rounded-xl bg-[var(--primary)] text-white hover:opacity-90 disabled:opacity-40 transition-all"
          aria-label="Send"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
