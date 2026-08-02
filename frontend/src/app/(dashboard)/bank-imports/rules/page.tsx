"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Tags, Plus, Trash2 } from "lucide-react"
import { apiFetch } from "@/lib/api"

type Account = { id: number; code: string; name: string; type: string; is_group?: boolean }
type Rule = {
  id: number
  pattern: string
  account_id: number
  is_active: boolean
  priority: number
  match_amount: number | null
  create_expense_draft: boolean
}

export default function BankRulesPage() {
  const [rules, setRules] = useState<Rule[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [error, setError] = useState<string | null>(null)
  const [pattern, setPattern] = useState("")
  const [accountId, setAccountId] = useState("")
  const [priority, setPriority] = useState("100")
  const [matchAmount, setMatchAmount] = useState("")
  const [draft, setDraft] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = () => {
    apiFetch<Rule[]>("/api/banking/rules").then(setRules).catch((e) => setError(String(e.message || e)))
    apiFetch<{ items: Account[] } | Account[]>("/api/accounts")
      .then((data) => {
        const list = Array.isArray(data) ? data : (data.items ?? [])
        setAccounts(list.filter((a) => !a.is_group))
      })
      .catch(() => setAccounts([]))
  }
  useEffect(() => { load() }, [])

  const save = async () => {
    setBusy(true); setError(null)
    try {
      await apiFetch("/api/banking/rules", {
        method: "POST",
        body: JSON.stringify({
          pattern,
          account_id: Number(accountId),
          priority: Number(priority) || 100,
          match_amount: matchAmount !== "" ? Number(matchAmount) : null,
          create_expense_draft: draft,
          is_active: true,
        }),
      })
      setPattern(""); setAccountId(""); setMatchAmount(""); setDraft(false); setPriority("100")
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed")
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: number) => {
    try {
      await apiFetch(`/api/banking/rules/${id}`, { method: "DELETE" })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed")
    }
  }

  const acctLabel = (id: number) => {
    const a = accounts.find((x) => x.id === id)
    return a ? `${a.code} · ${a.name}` : `#${id}`
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Tags className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="font-serif text-2xl">Bank Categorization Rules</h1>
            <p className="text-sm text-[var(--text-muted)]">
              Lower priority number wins first. Applied on CSV/OFX import and Plaid sync.
            </p>
          </div>
        </div>
        <Link href="/bank-imports" className="text-sm text-[var(--primary)] hover:underline">← Imports</Link>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      <section className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-bold">New rule</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="text-sm space-y-1">
            <span className="text-xs text-[var(--text-muted)]">Description contains</span>
            <input className="w-full border rounded-lg px-3 py-2" value={pattern} onChange={(e) => setPattern(e.target.value)} placeholder="e.g. STRIPE" />
          </label>
          <label className="text-sm space-y-1">
            <span className="text-xs text-[var(--text-muted)]">GL account</span>
            <select className="w-full border rounded-lg px-3 py-2 bg-white" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">Select…</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.code} · {a.name}</option>
              ))}
            </select>
          </label>
          <label className="text-sm space-y-1">
            <span className="text-xs text-[var(--text-muted)]">Priority (lower first)</span>
            <input type="number" className="w-full border rounded-lg px-3 py-2" value={priority} onChange={(e) => setPriority(e.target.value)} />
          </label>
          <label className="text-sm space-y-1">
            <span className="text-xs text-[var(--text-muted)]">Exact amount (optional)</span>
            <input type="number" className="w-full border rounded-lg px-3 py-2" value={matchAmount} onChange={(e) => setMatchAmount(e.target.value)} />
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={draft} onChange={(e) => setDraft(e.target.checked)} />
          Suggest expense draft when matched
        </label>
        <button
          type="button"
          disabled={busy || !pattern.trim() || !accountId}
          onClick={save}
          className="inline-flex items-center gap-1.5 bg-[#b8943f] px-3 py-1.5 rounded text-sm font-medium disabled:opacity-60"
        >
          <Plus className="w-4 h-4" /> Add rule
        </button>
      </section>

      <section className="space-y-2">
        {rules.map((r) => (
          <div key={r.id} className="bg-white border border-[var(--border)] rounded-xl px-4 py-3 flex justify-between gap-3">
            <div className="text-sm">
              <div className="font-medium">“{r.pattern}” → {acctLabel(r.account_id)}</div>
              <div className="text-xs text-[var(--text-muted)]">
                priority {r.priority}
                {r.match_amount != null ? ` · amount ${r.match_amount}` : ""}
                {r.create_expense_draft ? " · expense draft" : ""}
                {!r.is_active ? " · inactive" : ""}
              </div>
            </div>
            <button type="button" className="text-red-700 text-sm inline-flex items-center gap-1" onClick={() => remove(r.id)}>
              <Trash2 className="w-4 h-4" /> Delete
            </button>
          </div>
        ))}
        {!rules.length && <p className="text-sm text-[var(--text-muted)]">No rules yet.</p>}
      </section>
    </div>
  )
}
