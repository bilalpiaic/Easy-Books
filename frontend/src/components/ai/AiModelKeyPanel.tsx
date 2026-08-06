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
type PanelTab = "models" | "keys"

const CLOUD_PROVIDERS: { id: AiProviderId; label: string; short: string; settingsKey: string }[] = [
  { id: "anthropic", label: "Anthropic (Claude)", short: "Claude", settingsKey: "ai_api_key_anthropic" },
  { id: "openai", label: "OpenAI (GPT)", short: "OpenAI", settingsKey: "ai_api_key_openai" },
  { id: "gemini", label: "Google (Gemini)", short: "Gemini", settingsKey: "ai_api_key_gemini" },
  { id: "xai", label: "xAI / Cursor Grok", short: "Grok", settingsKey: "ai_api_key_xai" },
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
  /** Which top-level tab to open. Defaults to API Keys when no provider
   * is configured yet so the key-insertion UI is immediately visible. */
  initialTab?: PanelTab
}

/** The single in-chat entry point for both picking a model and configuring
 * the API key that powers it — opened from a button in ChatCore's header
 * bar, which previously had no path to key configuration at all when no
 * provider was set up (the model row just disappeared with no explanation). */
export default function AiModelKeyPanel({
  models, selectedModel, onSelectModel, onModelsRefresh, onClose, initialTab,
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
  const [tab, setTab] = useState<PanelTab>(
    initialTab ?? (models.providers.length === 0 ? "keys" : "models"),
  )
  const [keyProvider, setKeyProvider] = useState<AiProviderId>("xai")

  const loadKeyStatus = () => {
    if (!isAdmin) return
    setStatusLoading(true)
    apiFetch<AiKeyStatus>("/api/ai/key-status")
      .then((status) => {
        setKeyStatus(status)
        // Prefer a provider that still needs a key when opening the keys tab
        const unset = CLOUD_PROVIDERS.find((p) => !status?.[p.id])
        if (unset) setKeyProvider(unset.id)
        else if (status?.xai) setKeyProvider("xai")
      })
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

  const activeProvider = CLOUD_PROVIDERS.find((p) => p.id === keyProvider) ?? CLOUD_PROVIDERS[0]
  const activeStatus = keyStatus?.[activeProvider.id] ?? null

  const panel = (
    <div className="fixed inset-0 z-[950] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div
        onClick={e => e.stopPropagation()}
        className="relative w-full max-w-sm max-h-[85dvh] flex flex-col bg-white rounded-2xl shadow-2xl border border-[var(--text-primary)]/10 overflow-hidden"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--text-primary)]/10 shrink-0">
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

        {/* Top tabs — Models vs API Keys (keeps xAI key insertion discoverable) */}
        <div className="shrink-0 px-4 pt-3">
          <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-[var(--bg-page)] border border-[var(--text-primary)]/10">
            <button
              type="button"
              onClick={() => setTab("models")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                tab === "models"
                  ? "bg-white text-[var(--text-primary)] shadow-sm"
                  : "text-[var(--text-primary)]/60 hover:text-[var(--text-primary)]"
              }`}
            >
              Models
            </button>
            <button
              type="button"
              onClick={() => setTab("keys")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                tab === "keys"
                  ? "bg-white text-[var(--text-primary)] shadow-sm"
                  : "text-[var(--text-primary)]/60 hover:text-[var(--text-primary)]"
              }`}
            >
              API Keys
            </button>
          </div>
        </div>

        <div className="p-4 overflow-y-auto flex-1 min-h-0">
          {tab === "models" ? (
            <div>
              {models.providers.length === 0 ? (
                <div className="space-y-3">
                  <p className="text-xs text-[var(--text-primary)]/50">
                    No AI provider is configured yet{isAdmin ? "." : "."}
                  </p>
                  {isAdmin && (
                    <button
                      type="button"
                      onClick={() => setTab("keys")}
                      className="w-full rounded-lg px-3 py-2 text-xs font-medium bg-[var(--primary)] text-white"
                    >
                      Add an API key (incl. xAI / Cursor Grok)
                    </button>
                  )}
                </div>
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
          ) : (
            <div>
              {!isAdmin ? (
                <p className="text-xs text-[var(--text-primary)]/50">
                  Only admins and owners can add API keys — ask one to configure a provider in Settings → AI.
                </p>
              ) : (
                <div className="space-y-4">
                  <p className="text-xs text-[var(--text-primary)]/50">
                    Choose a provider tab, paste its API key, then Save.
                  </p>

                  {/* Provider insertion tabs — Claude / OpenAI / Gemini / Grok */}
                  <div className="flex flex-wrap gap-1.5">
                    {CLOUD_PROVIDERS.map((p) => {
                      const active = p.id === keyProvider
                      const set = Boolean(keyStatus?.[p.id])
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => setKeyProvider(p.id)}
                          className={`rounded-full px-2.5 py-1 text-[11px] font-medium border transition-colors ${
                            active
                              ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                              : "bg-white text-[var(--text-primary)]/70 border-[var(--text-primary)]/15 hover:border-[var(--primary)]/40"
                          }`}
                        >
                          {p.short}
                          {set ? " · ✓" : ""}
                        </button>
                      )
                    })}
                  </div>

                  {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-2 text-red-700 text-xs">
                      {error}
                    </div>
                  )}

                  <div className="space-y-2 rounded-xl border border-[var(--text-primary)]/10 p-3 bg-[var(--bg-page)]/60">
                    <div className="flex items-center justify-between gap-2">
                      <label className="text-sm font-medium text-[var(--text-primary)]">
                        {activeProvider.label}
                      </label>
                      <span className="text-[11px] font-mono text-[var(--text-primary)]/50">
                        {statusLoading ? "…" : (activeStatus || "Not set")}
                      </span>
                    </div>
                    <input
                      type="password"
                      autoComplete="off"
                      placeholder={`Paste ${activeProvider.short} API key…`}
                      value={newKeys[activeProvider.id]}
                      onChange={e => setNewKeys(prev => ({ ...prev, [activeProvider.id]: e.target.value }))}
                      className="w-full border border-[var(--text-primary)]/15 rounded-lg px-2.5 py-2 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
                    />
                    <div className="flex gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleSaveKey(activeProvider.id, activeProvider.settingsKey)}
                        disabled={!newKeys[activeProvider.id].trim() || savingProvider === activeProvider.id}
                        className="flex-1 px-2.5 py-2 rounded-lg text-xs font-medium bg-[var(--primary)] text-white disabled:opacity-40 inline-flex items-center justify-center gap-1"
                      >
                        {savingProvider === activeProvider.id
                          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          : "Save key"}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleClearKey(activeProvider.id, activeProvider.settingsKey, activeProvider.label)}
                        disabled={!activeStatus}
                        className="px-2.5 py-2 rounded-lg text-xs font-medium text-red-600 border border-[var(--text-primary)]/15 hover:bg-red-50 disabled:opacity-40"
                      >
                        Clear
                      </button>
                    </div>
                    {activeProvider.id === "xai" && (
                      <p className="text-[11px] text-[var(--text-primary)]/50">
                        Get a key from{" "}
                        <a
                          href="https://console.x.ai/"
                          target="_blank"
                          rel="noreferrer"
                          className="text-[var(--primary)] hover:underline"
                        >
                          console.x.ai
                        </a>
                        . Enables Cursor Grok models (grok-4.5, etc.).
                      </p>
                    )}
                  </div>

                  <Link
                    href="/settings?tab=advanced"
                    className="inline-block text-xs text-[var(--primary)] hover:underline"
                    onClick={onClose}
                  >
                    More AI settings (Ollama, rate limit) →
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
