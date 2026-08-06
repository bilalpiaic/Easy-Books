"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { RefreshCw, Plus, AlertTriangle, CheckCircle2, Clock } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface FeedConnection {
  id: number
  provider: string
  institution_name: string
  bank_account_id: number | null
  last_sync: string | null
  last_error: string | null
  sync_status: "never" | "ok" | "error" | "consent_expired" | string
  consent_expires_at: string | null
  is_active: boolean
}

interface BankAccount {
  id: number
  name: string
  bank_name: string | null
}

function StatusPill({ status }: { status: string }) {
  if (status === "ok") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
        <CheckCircle2 className="w-3 h-3" /> OK
      </span>
    )
  }
  if (status === "consent_expired") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-800 bg-amber-50 px-2 py-0.5 rounded">
        <AlertTriangle className="w-3 h-3" /> Consent expired
      </span>
    )
  }
  if (status === "error") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700 bg-red-50 px-2 py-0.5 rounded">
        <AlertTriangle className="w-3 h-3" /> Error
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-[var(--text-primary)]/60 bg-[var(--bg-page)] px-2 py-0.5 rounded">
      <Clock className="w-3 h-3" /> Never synced
    </span>
  )
}

export default function BankFeedsPage() {
  const [connections, setConnections] = useState<FeedConnection[]>([])
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [accountId, setAccountId] = useState<number | "">("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [connecting, setConnecting] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      apiFetch<FeedConnection[]>("/api/banking/feeds/connections"),
      apiFetch<BankAccount[]>("/api/bank-accounts"),
    ])
      .then(([conns, accts]) => {
        setConnections(conns)
        setAccounts(accts)
        setAccountId((prev) => (prev === "" && accts.length ? accts[0].id : prev))
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const accountName = (id: number | null) => {
    if (!id) return "—"
    const a = accounts.find((x) => x.id === id)
    return a ? a.name : `#${id}`
  }

  const connectMock = async () => {
    if (accountId === "") return
    setConnecting(true)
    setError(null)
    try {
      await apiFetch("/api/banking/feeds/mock/connect", {
        method: "POST",
        body: JSON.stringify({ bank_account_id: accountId }),
      })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connect failed")
    } finally {
      setConnecting(false)
    }
  }

  const syncNow = async (id: number) => {
    setBusyId(id)
    setError(null)
    try {
      await apiFetch(`/api/banking/feeds/${id}/sync`, { method: "POST" })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed")
      load()
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6">
      <PrintHeader title="Bank Feeds" subtitle="Open Banking / statement sync status" />
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Bank Feeds</h1>
          <p className="text-sm text-[var(--text-primary)]/60 mt-0.5 max-w-xl">
            Multi-account sync status for connected feeds. EU/UK Open Banking is pull-only —
            use Sync now or the scheduled pull. Consent expiry is shown separately from sync errors.
          </p>
        </div>
        <Link
          href="/bank-imports"
          className="text-sm font-medium text-[var(--primary)] hover:underline"
        >
          Statement imports →
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm print:hidden">
          {error}
        </div>
      )}

      <div className="bg-white border border-[var(--text-primary)]/10 rounded-2xl p-4 print:hidden">
        <div className="text-sm font-semibold text-[var(--text-primary)] mb-2">
          Connect mock Open Banking feed
        </div>
        <p className="text-xs text-[var(--text-primary)]/55 mb-3">
          Demo adapter (no real bank). Imports sample remittance-style transactions for matching.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={accountId === "" ? "" : String(accountId)}
            onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : "")}
            className="border border-[var(--border)] rounded-lg px-3 py-2 text-sm bg-white"
          >
            {accounts.length === 0 && <option value="">No bank accounts</option>}
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          <button
            type="button"
            disabled={connecting || accountId === ""}
            onClick={connectMock}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-40"
          >
            <Plus className="w-4 h-4" />
            {connecting ? "Connecting…" : "Connect mock feed"}
          </button>
        </div>
      </div>

      <div className="table-freeze overflow-x-auto rounded-2xl border border-[var(--text-primary)]/10 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-[var(--text-primary)]/50 border-b border-[var(--text-primary)]/10">
              <th className="px-4 py-3 font-semibold">Institution</th>
              <th className="px-4 py-3 font-semibold">Provider</th>
              <th className="px-4 py-3 font-semibold">Account</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold whitespace-nowrap">Last success</th>
              <th className="px-4 py-3 font-semibold print:hidden"> </th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[var(--text-primary)]/50">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && connections.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[var(--text-primary)]/50">
                  No feed connections yet.
                </td>
              </tr>
            )}
            {connections.map((c) => (
              <tr key={c.id} className="border-b border-[var(--text-primary)]/5 align-top">
                <td className="px-4 py-3 font-medium text-[var(--text-primary)]">
                  {c.institution_name || "Bank"}
                  {c.last_error && (
                    <div className="text-xs text-red-600 mt-1 max-w-xs">{c.last_error}</div>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">{c.provider}</td>
                <td className="px-4 py-3">{accountName(c.bank_account_id)}</td>
                <td className="px-4 py-3"><StatusPill status={c.sync_status} /></td>
                <td className="px-4 py-3 whitespace-nowrap">
                  {c.last_sync ? fmtDate(c.last_sync) : "—"}
                </td>
                <td className="px-4 py-3 print:hidden">
                  <button
                    type="button"
                    disabled={busyId === c.id || c.sync_status === "consent_expired"}
                    onClick={() => syncNow(c.id)}
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--primary)] hover:underline disabled:opacity-40"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${busyId === c.id ? "animate-spin" : ""}`} />
                    Sync now
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
