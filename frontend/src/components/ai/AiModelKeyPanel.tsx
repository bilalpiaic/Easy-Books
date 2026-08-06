"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import Link from "next/link"
import { X, KeyRound, Check, Loader2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { getCurrentUser } from "@/lib/auth"
import type { ModelsPayload } from "./ChatCore"
import { useMessages } from "@/context/MessageContext"

type AiProviderId = "anthropic" | "openai" | "gemini" | "xai"
type AiKeyStatus = Record<AiProviderId, string | null>

const CLOUD_PROVIDERS: { id: AiProviderId; label: string; settingsKey: string }[] = [
  { id: "anthropic", label: "Anthropic (Claude)", settingsKey: "ai_api_key_anthropic" },
  { id: "openai", label: "OpenAI (GPT)", settingsKey: "ai_api_key_openai" },
  { id: "gemini", label: "Google (Gemini)", settingsKey: "ai_api_key_gemini" },
  { id: "xai", label: "xAI / Cursor Grok", settingsKey: "ai_api_key_xai" },
]

interface AiModelKeyPanelProps {
  models: ModelsPayload
  selectedModel: string
  onSelectModel: (model: string) => void
  /** Called after a key is saved/cleared so the parent can refetch
   * /api/ai/models — a newly-configured provider's models won't appear in
   * the picker until that happens. */
  onModelsRefresh?: () => void
  onClose: () => void
}

/** The single in-chat entry point for both picking a model and configuring
 * the API key that powers it — opened from a button in ChatCore's header
 * bar, which previously had no path to key configuration at all when no
 * provider was set up (the model row just disappeared with no explanation). */
export default function AiModelKeyPanel({
  models, selectedModel, onSelectModel, onModelsRefresh, onClose,
}: AiModelKeyPanelProps) {
  const isAdmin = getCurrentUser()?.role === "admin" || getCurrentUser()?.role === "owner"
  const { confirm } = useMessages()
  const [keyStatus, setKeyStatus] = useState<AiKeyStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(isAdmin)
  const [newKeys, setNewKeys] = useState<Record<AiProviderId, string>>({
    anthropic: "", openai: "", gemini: "", xai: "",
  })
  const [savingProvider, setSavingProvider] = useState<AiProviderId | null>(null)
  const [error, setError] = useState("")

  const loadKeyStatus = () => {
    if (!isAdmin) return
    setStatusLoading(true)
    apiFetch<AiKeyStatus>("/api/ai/key-status")
      .then(setKeyStatus)
      .catch(() => setKeyStatus(null))
      .finally(() => setStatusLoading(false))
  }

  useEffect(() => {
    loadKeyStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSaveKey = async (provider: AiProviderId, settingsKey: string) => {
    const value = newKeys[provider].trim()
    if (!value) return
    setSavingProvider(provider)
    setError("")
    try {
      await apiFetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [settingsKey]: value }),
      })
      setNewKeys(prev => ({ ...prev, [provider]: "" }))
      loadKeyStatus()
      onModelsRefresh?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save the key.")
    } finally {
      setSavingProvider(null)
    }
  }

  const handleClearKey = async (provider: AiProviderId, settingsKey: string, label: string) => {
    const ok = await confirm({
      title: `Clear the ${label} API key?`,
      confirmLabel: "Clear key",
      danger: true,
    })
    if (!ok) return
    setError("")
    try {
      await apiFetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [settingsKey]: "" }),
      })
      loadKeyStatus()
      onModelsRefresh?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear the key.")
    }
  }

  const panel = (
    <div className="fixed inset-0 z-[950] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div
        onClick={e => e.stopPropagation()}
        className="relative w-full max-w-sm max-h-[85dvh] overflow-y-auto bg-white rounded-2xl shadow-2xl border border-[var(--text-primary)]/10"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--text-primary)]/10 sticky top-0 bg-white">
          <div className="flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-[var(--primary)]" />
            <span className="font-semibold text-sm text-[var(--text-primary)]">Model & API Key</span>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1 rounded-lg hover:bg-[var(--text-primary)]/10 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-5">
          {/* Model */}
          <div>
            <p className="text-xs font-medium text-[var(--text-primary)]/60 mb-2 uppercase tracking-wide">Model</p>
            {models.providers.length === 0 ? (
              <p className="text-xs text-[var(--text-primary)]/50">
                No AI provider is configured yet{isAdmin ? " — add a key below." : "."}
              </p>
            ) : (
              <div className="space-y-3">
                {models.providers.map(p => (
                  <div key={p.provider}>
                    <p className="text-[10px] font-semibold text-[var(--text-primary)]/40 uppercase tracking-wide mb-1">
                      {p.label}
                    </p>
                    <div className="space-y-1">
                      {p.models.map(m => {
                        const active = m === selectedModel
                        return (
                          <button
                            key={m}
                            type="button"
                            onClick={() => onSelectModel(m)}
                            className={`w-full flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-xs text-left transition-colors ${
                              active
                                ? "bg-[var(--primary)]/10 text-[var(--primary)] font-medium"
                                : "hover:bg-[var(--bg-page)] text-[var(--text-primary)]/80"
                            }`}
                          >
                            <span className="truncate">{m.split("/").slice(1).join("/")}</span>
                            {active && <Check className="w-3.5 h-3.5 shrink-0" />}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* API Key */}
          <div className="pt-4 border-t border-[var(--text-primary)]/10">
            <p className="text-xs font-medium text-[var(--text-primary)]/60 mb-2 uppercase tracking-wide">API Key</p>
            {!isAdmin ? (
              <p className="text-xs text-[var(--text-primary)]/50">
                Only admins and owners can add API keys — ask one to configure a provider in Settings → AI.
              </p>
            ) : (
              <>
                {error && (
                  <div className="mb-2 bg-red-50 border border-red-200 rounded-lg p-2 text-red-700 text-xs">
                    {error}
                  </div>
                )}
                <div className="space-y-3">
                  {CLOUD_PROVIDERS.map(p => {
                    const status = keyStatus?.[p.id] ?? null
                    return (
                      <div key={p.id} className="space-y-1">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-medium text-[var(--text-primary)]/70">{p.label}</label>
                          <span className="text-[11px] font-mono text-[var(--text-primary)]/50">
                            {statusLoading ? "…" : (status || "Not set")}
                          </span>
                        </div>
                        <div className="flex gap-1.5">
                          <input
                            type="password"
                            autoComplete="off"
                            placeholder="Paste API key…"
                            value={newKeys[p.id]}
                            onChange={e => setNewKeys(prev => ({ ...prev, [p.id]: e.target.value }))}
                            className="flex-1 min-w-0 border border-[var(--text-primary)]/15 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
                          />
                          <button
                            type="button"
                            onClick={() => handleSaveKey(p.id, p.settingsKey)}
                            disabled={!newKeys[p.id].trim() || savingProvider === p.id}
                            className="shrink-0 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-[var(--primary)] text-white disabled:opacity-40"
                          >
                            {savingProvider === p.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Save"}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleClearKey(p.id, p.settingsKey, p.label)}
                            disabled={!status}
                            className="shrink-0 px-2.5 py-1.5 rounded-lg text-xs font-medium text-red-600 border border-[var(--text-primary)]/15 hover:bg-red-50 disabled:opacity-40"
                          >
                            Clear
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
                <Link
                  href="/settings?tab=advanced"
                  className="mt-3 inline-block text-xs text-[var(--primary)] hover:underline"
                  onClick={onClose}
                >
                  More AI settings (Ollama, rate limit) →
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
