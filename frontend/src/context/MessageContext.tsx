"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
} from "react"
import { createPortal } from "react-dom"
import {
  AlertTriangle,
  CheckCircle,
  Info,
  X,
  XCircle,
} from "lucide-react"
import { cn } from "@/lib/utils"

export type ToastTone = "success" | "error" | "info"

export interface ConfirmOptions {
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  /** Red confirm button for destructive actions */
  danger?: boolean
}

export interface PromptOptions {
  title: string
  message?: string
  defaultValue?: string
  confirmLabel?: string
  cancelLabel?: string
  placeholder?: string
}

interface ToastItem {
  id: number
  message: string
  tone: ToastTone
}

interface MessageApi {
  /** In-app confirm dialog. Resolves true if the user confirms. */
  confirm: (opts: ConfirmOptions) => Promise<boolean>
  /** In-app text prompt. Resolves the entered string, or null if cancelled. */
  prompt: (opts: PromptOptions) => Promise<string | null>
  /** Transient bottom toast (replaces browser alert). */
  toast: (message: string, tone?: ToastTone) => void
}

const MessageContext = createContext<MessageApi>({
  confirm: async () => false,
  prompt: async () => null,
  toast: () => {},
})

let toastSeq = 0

function ToastIcon({ tone }: { tone: ToastTone }) {
  if (tone === "success") return <CheckCircle className="w-4 h-4 text-green-600" />
  if (tone === "error") return <XCircle className="w-4 h-4 text-red-600" />
  return <Info className="w-4 h-4 text-blue-600" />
}

function ConfirmModal({
  opts,
  onResolve,
}: {
  opts: ConfirmOptions
  onResolve: (ok: boolean) => void
}) {
  const titleId = useId()
  const confirmRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    confirmRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onResolve(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onResolve])

  return createPortal(
    <div
      className="fixed inset-0 z-[960] flex items-center justify-center p-4 print:hidden"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={() => onResolve(false)}
      />
      <div className="relative w-full max-w-md bg-[var(--bg-card)] rounded-2xl shadow-2xl border border-[var(--border)] p-5">
        <div className="flex items-start gap-3">
          {opts.danger ? (
            <div className="w-9 h-9 rounded-full bg-red-100 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-4 h-4 text-red-600" />
            </div>
          ) : (
            <div className="w-9 h-9 rounded-full bg-[var(--primary)]/10 flex items-center justify-center shrink-0">
              <Info className="w-4 h-4 text-[var(--primary)]" />
            </div>
          )}
          <div className="min-w-0 flex-1 pt-0.5">
            <h2 id={titleId} className="text-base font-semibold text-[var(--text-primary)]">
              {opts.title}
            </h2>
            {opts.message && (
              <p className="mt-1.5 text-sm text-[var(--text-muted)] whitespace-pre-line leading-relaxed">
                {opts.message}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => onResolve(false)}
            className="p-1 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--border)]/40 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => onResolve(false)}
            className="px-3.5 py-2 rounded-lg text-sm font-medium border border-[var(--border)] text-[var(--text-primary)] hover:bg-[var(--border)]/30 transition-colors"
          >
            {opts.cancelLabel ?? "Cancel"}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={() => onResolve(true)}
            className={cn(
              "px-3.5 py-2 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90",
              opts.danger ? "bg-red-600" : "bg-[var(--primary)]",
            )}
          >
            {opts.confirmLabel ?? "Confirm"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function PromptModal({
  opts,
  onResolve,
}: {
  opts: PromptOptions
  onResolve: (value: string | null) => void
}) {
  const titleId = useId()
  const [value, setValue] = useState(opts.defaultValue ?? "")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onResolve(null)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onResolve])

  const submit = () => {
    const v = value.trim()
    onResolve(v ? v : null)
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[960] flex items-center justify-center p-4 print:hidden"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={() => onResolve(null)}
      />
      <div className="relative w-full max-w-md bg-[var(--bg-card)] rounded-2xl shadow-2xl border border-[var(--border)] p-5">
        <h2 id={titleId} className="text-base font-semibold text-[var(--text-primary)]">
          {opts.title}
        </h2>
        {opts.message && (
          <p className="mt-1.5 text-sm text-[var(--text-muted)]">{opts.message}</p>
        )}
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); submit() } }}
          placeholder={opts.placeholder}
          className="mt-4 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/40"
        />
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => onResolve(null)}
            className="px-3.5 py-2 rounded-lg text-sm font-medium border border-[var(--border)] text-[var(--text-primary)] hover:bg-[var(--border)]/30 transition-colors"
          >
            {opts.cancelLabel ?? "Cancel"}
          </button>
          <button
            type="button"
            onClick={submit}
            className="px-3.5 py-2 rounded-lg text-sm font-medium text-white bg-[var(--primary)] hover:opacity-90 transition-opacity"
          >
            {opts.confirmLabel ?? "OK"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function ToastStack({
  items,
  onDismiss,
}: {
  items: ToastItem[]
  onDismiss: (id: number) => void
}) {
  if (items.length === 0) return null
  return createPortal(
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[800] flex flex-col-reverse gap-2 w-[min(100%-2rem,28rem)] print:hidden pointer-events-none">
      {items.map(t => (
        <div
          key={t.id}
          role="status"
          className="pointer-events-auto flex items-start gap-3 bg-[var(--bg-card)] border border-[var(--border)] shadow-2xl rounded-2xl px-4 py-3"
        >
          <div className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
            t.tone === "success" && "bg-green-100",
            t.tone === "error" && "bg-red-100",
            t.tone === "info" && "bg-blue-100",
          )}>
            <ToastIcon tone={t.tone} />
          </div>
          <p className="flex-1 text-[13px] font-medium text-[var(--text-primary)] pt-1.5 whitespace-pre-line leading-snug">
            {t.message}
          </p>
          <button
            type="button"
            onClick={() => onDismiss(t.id)}
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] text-lg leading-none transition-colors pt-1"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      ))}
    </div>,
    document.body,
  )
}

export function MessageProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<{
    opts: ConfirmOptions
    resolve: (ok: boolean) => void
  } | null>(null)
  const [promptPending, setPromptPending] = useState<{
    opts: PromptOptions
    resolve: (value: string | null) => void
  } | null>(null)
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const confirm = useCallback((opts: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setPending(prev => {
        prev?.resolve(false)
        return { opts, resolve }
      })
    })
  }, [])

  const prompt = useCallback((opts: PromptOptions) => {
    return new Promise<string | null>((resolve) => {
      setPromptPending(prev => {
        prev?.resolve(null)
        return { opts, resolve }
      })
    })
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts(list => list.filter(t => t.id !== id))
  }, [])

  const toast = useCallback((message: string, tone: ToastTone = "info") => {
    const id = ++toastSeq
    setToasts(list => [...list, { id, message, tone }])
    window.setTimeout(() => {
      setToasts(list => list.filter(t => t.id !== id))
    }, 5_000)
  }, [])

  const resolveConfirm = useCallback((ok: boolean) => {
    setPending(cur => {
      cur?.resolve(ok)
      return null
    })
  }, [])

  const resolvePrompt = useCallback((value: string | null) => {
    setPromptPending(cur => {
      cur?.resolve(value)
      return null
    })
  }, [])

  return (
    <MessageContext.Provider value={{ confirm, prompt, toast }}>
      {children}
      {pending && (
        <ConfirmModal opts={pending.opts} onResolve={resolveConfirm} />
      )}
      {promptPending && (
        <PromptModal opts={promptPending.opts} onResolve={resolvePrompt} />
      )}
      <ToastStack items={toasts} onDismiss={dismissToast} />
    </MessageContext.Provider>
  )
}

export function useMessages() {
  return useContext(MessageContext)
}
