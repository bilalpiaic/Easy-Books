"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, Plus, Send, Trash2, Webhook, RotateCcw } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

interface Endpoint {
  id: number
  url: string
  events: string[]
  description: string | null
  is_active: boolean
  secret_masked: string
  created_at: string
}

interface DeliveryLog {
  id: number
  event_type: string
  status: string
  attempts: number
  response_code: number | null
  last_error: string | null
  created_at: string
}

const STATUS_TONE: Record<string, string> = {
  delivered: "bg-emerald-100 text-emerald-800",
  pending: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
}

function StatusPill({ status }: { status: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_TONE[status] ?? "bg-gray-100 text-gray-700"}`}>
      {status}
    </span>
  )
}

export default function WebhooksSettingsPage() {
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [eventTypes, setEventTypes] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // add form
  const [showForm, setShowForm] = useState(false)
  const [url, setUrl] = useState("")
  const [description, setDescription] = useState("")
  const [events, setEvents] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const [newSecret, setNewSecret] = useState<string | null>(null)

  // per-endpoint UI state
  const [testResult, setTestResult] = useState<Record<number, string>>({})
  const [openLogs, setOpenLogs] = useState<number | null>(null)
  const [logs, setLogs] = useState<DeliveryLog[]>([])

  const load = () =>
    apiFetch<Endpoint[]>("/api/webhooks")
      .then(setEndpoints)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))

  useEffect(() => {
    Promise.all([
      apiFetch<Endpoint[]>("/api/webhooks"),
      apiFetch<string[]>("/api/webhooks/event-types"),
    ])
      .then(([eps, types]) => { setEndpoints(eps); setEventTypes(types) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])

  const toggleEvent = (ev: string) => {
    setEvents(prev => {
      const next = new Set(prev)
      if (next.has(ev)) next.delete(ev); else next.add(ev)
      return next
    })
  }

  const createEndpoint = async () => {
    if (!url || events.size === 0) return
    setSaving(true)
    setError(null)
    try {
      const created = await apiFetch<Endpoint & { secret: string }>("/api/webhooks", {
        method: "POST",
        body: JSON.stringify({ url, description: description || null, events: [...events] }),
      })
      setNewSecret(created.secret)
      setShowForm(false)
      setUrl(""); setDescription(""); setEvents(new Set())
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create endpoint")
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (ep: Endpoint) => {
    await apiFetch(`/api/webhooks/${ep.id}`, {
      method: "PUT",
      body: JSON.stringify({ is_active: !ep.is_active }),
    })
    await load()
  }

  const remove = async (ep: Endpoint) => {
    if (!confirm(`Delete webhook endpoint ${ep.url}? Its delivery history is removed too.`)) return
    await apiFetch(`/api/webhooks/${ep.id}`, { method: "DELETE" })
    if (openLogs === ep.id) setOpenLogs(null)
    await load()
  }

  const sendTest = async (ep: Endpoint) => {
    setTestResult(prev => ({ ...prev, [ep.id]: "…" }))
    try {
      const r = await apiFetch<{ ok: boolean; response_code: number | null; error: string | null }>(
        `/api/webhooks/${ep.id}/test`, { method: "POST" })
      setTestResult(prev => ({
        ...prev,
        [ep.id]: r.ok ? `✓ HTTP ${r.response_code}` : (r.response_code ? `✗ HTTP ${r.response_code}` : `✗ ${r.error ?? "unreachable"}`),
      }))
    } catch {
      setTestResult(prev => ({ ...prev, [ep.id]: "✗ request failed" }))
    }
  }

  const viewLogs = async (ep: Endpoint) => {
    if (openLogs === ep.id) { setOpenLogs(null); return }
    const rows = await apiFetch<DeliveryLog[]>(`/api/webhooks/${ep.id}/logs`)
    setLogs(rows)
    setOpenLogs(ep.id)
  }

  const replay = async (ep: Endpoint, logId: number) => {
    try {
      await apiFetch(`/api/webhooks/${ep.id}/logs/${logId}/replay`, { method: "POST" })
      const rows = await apiFetch<DeliveryLog[]>(`/api/webhooks/${ep.id}/logs`)
      setLogs(rows)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Replay failed")
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/settings" className="inline-flex items-center gap-1 text-xs text-[var(--text-primary)]/60 hover:text-[var(--text-primary)] mb-1">
            <ArrowLeft className="w-3 h-3" /> Settings
          </Link>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Webhooks</h1>
          <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
            Send signed HTTP notifications to external systems when things happen in your books.
          </p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Endpoint
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {newSecret && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 text-sm">
          <p className="font-semibold text-amber-900">Signing secret — shown only once, copy it now:</p>
          <code className="block mt-1 font-mono text-xs break-all select-all">{newSecret}</code>
          <p className="text-xs text-amber-800 mt-1">
            Verify each delivery: <code>X-EasyBooks-Signature: sha256=HMAC_SHA256(secret, raw_body)</code>
          </p>
          <button onClick={() => setNewSecret(null)} className="text-xs underline mt-1">Dismiss</button>
        </div>
      )}

      {showForm && (
        <div className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1">Payload URL</label>
              <input
                value={url} onChange={e => setUrl(e.target.value)}
                placeholder="https://example.com/hooks/easy-books"
                className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1">Description (optional)</label>
              <input
                value={description} onChange={e => setDescription(e.target.value)}
                placeholder="Zapier — new invoice to Slack"
                className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-2">Events</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {eventTypes.map(ev => (
                <label key={ev} className="flex items-center gap-2 text-sm text-[var(--text-primary)]/85">
                  <input type="checkbox" checked={events.has(ev)} onChange={() => toggleEvent(ev)} />
                  <code className="text-xs">{ev}</code>
                </label>
              ))}
            </div>
          </div>
          <button
            onClick={createEndpoint}
            disabled={saving || !url || events.size === 0}
            className="bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-40"
          >
            {saving ? "Creating…" : "Create Endpoint"}
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-[var(--text-primary)]/50 py-8 text-center">Loading…</div>
      ) : endpoints.length === 0 ? (
        <div className="bg-white border border-[var(--border)] rounded-xl px-6 py-12 text-center">
          <Webhook className="w-10 h-10 text-[var(--primary)]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[var(--text-primary)]">No webhook endpoints yet</p>
          <p className="text-xs text-[var(--text-primary)]/55 mt-1">
            Add one to push invoice, payment, and stock events to Zapier, Make, Slack, or your own systems.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {endpoints.map(ep => (
            <div key={ep.id} className="bg-white border border-[var(--border)] rounded-xl p-4">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-sm text-[var(--text-primary)] break-all">{ep.url}</span>
                    <StatusPill status={ep.is_active ? "active" : "inactive"} />
                  </div>
                  {ep.description && (
                    <p className="text-xs text-[var(--text-primary)]/60 mt-0.5">{ep.description}</p>
                  )}
                  <div className="flex gap-1 mt-1.5 flex-wrap">
                    {ep.events.map(ev => (
                      <span key={ev} className="bg-[var(--bg-page)] border border-[var(--border)] rounded px-1.5 py-0.5 text-[11px] font-mono">{ev}</span>
                    ))}
                  </div>
                  <p className="text-[11px] text-[var(--text-primary)]/45 mt-1.5">
                    Secret {ep.secret_masked} · added {fmtDate(ep.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {testResult[ep.id] && (
                    <span className={`text-xs font-medium ${testResult[ep.id].startsWith("✓") ? "text-emerald-700" : "text-red-700"}`}>
                      {testResult[ep.id]}
                    </span>
                  )}
                  <button onClick={() => sendTest(ep)} title="Send a test ping"
                    className="inline-flex items-center gap-1 border border-[var(--border)] rounded-lg px-2.5 py-1.5 text-xs font-medium hover:bg-[var(--bg-page)]">
                    <Send className="w-3.5 h-3.5" /> Test
                  </button>
                  <button onClick={() => viewLogs(ep)}
                    className="border border-[var(--border)] rounded-lg px-2.5 py-1.5 text-xs font-medium hover:bg-[var(--bg-page)]">
                    {openLogs === ep.id ? "Hide Logs" : "Logs"}
                  </button>
                  <button onClick={() => toggleActive(ep)}
                    className="border border-[var(--border)] rounded-lg px-2.5 py-1.5 text-xs font-medium hover:bg-[var(--bg-page)]">
                    {ep.is_active ? "Disable" : "Enable"}
                  </button>
                  <button onClick={() => remove(ep)} title="Delete endpoint"
                    className="border border-red-200 text-red-700 rounded-lg px-2.5 py-1.5 text-xs font-medium hover:bg-red-50">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {openLogs === ep.id && (
                <div className="mt-3 border-t border-[var(--border)] pt-3 overflow-x-auto">
                  {logs.length === 0 ? (
                    <p className="text-xs text-[var(--text-primary)]/50">No deliveries yet — trigger a subscribed event or use Test.</p>
                  ) : (
                    <table className="w-full text-xs min-w-[560px]">
                      <thead>
                        <tr className="text-left text-[var(--text-primary)]/60">
                          <th className="py-1.5 pr-3 font-semibold">Event</th>
                          <th className="py-1.5 pr-3 font-semibold">Status</th>
                          <th className="py-1.5 pr-3 font-semibold text-right">Attempts</th>
                          <th className="py-1.5 pr-3 font-semibold text-right">Response</th>
                          <th className="py-1.5 pr-3 font-semibold">Error</th>
                          <th className="py-1.5 pr-3 font-semibold whitespace-nowrap">Created</th>
                          <th className="py-1.5 font-semibold" />
                        </tr>
                      </thead>
                      <tbody>
                        {logs.map(l => (
                          <tr key={l.id} className="border-t border-[var(--border)]/60">
                            <td className="py-1.5 pr-3 font-mono">{l.event_type}</td>
                            <td className="py-1.5 pr-3"><StatusPill status={l.status} /></td>
                            <td className="py-1.5 pr-3 text-right tabular-nums">{l.attempts}</td>
                            <td className="py-1.5 pr-3 text-right tabular-nums">{l.response_code ?? "—"}</td>
                            <td className="py-1.5 pr-3 text-[var(--text-primary)]/60 max-w-[220px] truncate" title={l.last_error ?? undefined}>{l.last_error ?? "—"}</td>
                            <td className="py-1.5 pr-3 whitespace-nowrap">{fmtDate(l.created_at)}</td>
                            <td className="py-1.5 text-right">
                              <button
                                type="button"
                                title="Replay as new attempt"
                                onClick={() => replay(ep, l.id)}
                                className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--primary)] hover:underline"
                              >
                                <RotateCcw className="w-3 h-3" /> Replay
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
