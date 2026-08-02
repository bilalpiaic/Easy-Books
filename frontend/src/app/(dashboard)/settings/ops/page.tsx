"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, RefreshCw, RotateCcw } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Ops = {
  redis_configured: boolean
  queue: { redis: boolean; queued: number; error?: string }
  webhook: {
    window_hours: number
    total: number
    failed: number
    pending: number
    failure_rate: number
  }
  dead_letter_open: number
}

type DlqRow = {
  id: number
  task_name: string
  error: string
  status: string
  created_at: string
  retried_at: string | null
}

export default function IntegrationOpsPage() {
  const [ops, setOps] = useState<Ops | null>(null)
  const [rows, setRows] = useState<DlqRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<number | null>(null)

  const load = useCallback(() => {
    setError(null)
    Promise.all([
      apiFetch<Ops>("/api/tasks/ops"),
      apiFetch<DlqRow[]>("/api/tasks/dead-letter?status=open"),
    ])
      .then(([o, d]) => {
        setOps(o)
        setRows(d)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [])

  useEffect(() => { load() }, [load])

  const retry = async (id: number) => {
    setBusy(id)
    try {
      await apiFetch(`/api/tasks/dead-letter/${id}/retry`, { method: "POST" })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Retry failed")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <Link href="/settings" className="inline-flex items-center gap-1 text-xs text-[var(--text-primary)]/60 hover:text-[var(--text-primary)] mb-1">
          <ArrowLeft className="w-3 h-3" /> Settings
        </Link>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Integration ops</h1>
            <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
              Queue depth, webhook failure rate, and dead-lettered background jobs.
            </p>
          </div>
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-1.5 border border-[var(--border)] rounded-lg px-3 py-1.5 text-xs font-medium hover:bg-[var(--bg-page)]"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {ops && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="Queue depth" value={String(ops.queue.queued)} sub={ops.redis_configured ? "Redis" : "Inline (no Redis)"} />
          <Stat label="Webhook pending" value={String(ops.webhook.pending)} />
          <Stat
            label="Webhook fail rate (24h)"
            value={`${Math.round(ops.webhook.failure_rate * 100)}%`}
            sub={`${ops.webhook.failed}/${ops.webhook.total}`}
          />
          <Stat label="DLQ open" value={String(ops.dead_letter_open)} />
        </div>
      )}

      <section className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[var(--border)] bg-[var(--bg-page)]">
          <h2 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">
            Dead letter queue
          </h2>
        </div>
        {rows.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-[var(--text-primary)]/50">
            No failed jobs — PDF, email, and import failures will appear here.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--text-primary)]/55">
                <th className="px-4 py-2 font-semibold">Task</th>
                <th className="px-4 py-2 font-semibold">Error</th>
                <th className="px-4 py-2 font-semibold whitespace-nowrap">When</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2 font-mono text-xs">{r.task_name}</td>
                  <td className="px-4 py-2 text-xs text-[var(--text-primary)]/70 max-w-xs truncate" title={r.error}>
                    {r.error}
                  </td>
                  <td className="px-4 py-2 text-xs whitespace-nowrap">{fmtDate(r.created_at)}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      disabled={busy === r.id}
                      onClick={() => retry(r.id)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-[var(--primary)] hover:underline disabled:opacity-50"
                    >
                      <RotateCcw className="w-3 h-3" />
                      {busy === r.id ? "…" : "Retry"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <p className="text-xs text-[var(--text-primary)]/50">
        Webhook delivery logs and replay live on{" "}
        <Link href="/settings/webhooks" className="underline">Settings → Webhooks</Link>.
        Signature docs: verify <code className="font-mono">X-EasyBooks-Signature: sha256=HMAC_SHA256(secret, body)</code>.
      </p>
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white border border-[var(--border)] rounded-xl p-3">
      <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50">{label}</div>
      <div className="text-xl font-semibold mt-1 tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-[var(--text-primary)]/50 mt-0.5">{sub}</div>}
    </div>
  )
}
