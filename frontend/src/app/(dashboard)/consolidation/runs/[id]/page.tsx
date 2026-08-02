"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowLeft, Printer, Sparkles, Lock, Ban } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { useMessages } from "@/context/MessageContext"
import PrintHeader from "@/components/PrintHeader"
import { AccountTreeRows, type TreeNode } from "@/components/AccountTree"
import { fmtDate } from "@/lib/utils"

interface Run {
  id: number
  name: string | null
  period_start: string
  period_end: string
  status: string
  notes: string | null
  package?: Statements | null
}

interface Elim {
  id: number
  kind: string
  description: string
  account_code: string
  account_name: string
  account_type: string
  debit: number
  credit: number
}

interface Statements {
  balance_sheet: {
    assets: TreeNode[]
    liabilities: TreeNode[]
    equity: TreeNode[]
    totals: { assets: number; liabilities: number; equity: number }
  }
  income_statement: {
    revenue: TreeNode[]
    expenses: TreeNode[]
    totals: { revenue: number; expenses: number; net_profit: number }
  }
  eliminations?: Elim[]
  members?: { name: string; relationship: string; ownership_pct: number; net_assets: number }[]
  worksheet?: { code: string; name: string; type: string; debit: number; credit: number; balance: number }[]
}

function TreeSection({
  title, nodes, total, totalLabel, field, fmt,
}: {
  title: string
  nodes: TreeNode[]
  total: number
  totalLabel: string
  field: "balance" | "amount"
  fmt: (n: number) => string
}) {
  return (
    <section className="space-y-2">
      <h3 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/75 border-b border-[var(--text-primary)]/5 pb-2">{title}</h3>
      <div className="overflow-x-auto table-freeze">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50">
              <th className="py-2 pr-3 text-left font-bold">Account</th>
              <th className="py-2 px-3 text-right font-bold">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--text-primary)]/5">
            <AccountTreeRows
              nodes={nodes}
              columns={[{ key: field, align: "right" }]}
            />
          </tbody>
        </table>
      </div>
      <div className="flex justify-between pt-4 border-t border-[var(--text-primary)]/5 font-bold">
        <span>{totalLabel}</span>
        <span className="font-mono w-36 text-right underline decoration-double underline-offset-4">{fmt(total)}</span>
      </div>
    </section>
  )
}

export default function ConsolidationRunPage() {
  const params = useParams()
  const runId = Number(params.id)
  const fmt = useFmt()
  const { toast, confirm } = useMessages()
  const [run, setRun] = useState<Run | null>(null)
  const [elims, setElims] = useState<Elim[]>([])
  const [stmts, setStmts] = useState<Statements | null>(null)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<"worksheet" | "bs" | "pl">("worksheet")

  async function load() {
    const [r, e, s] = await Promise.all([
      apiFetch<Run>(`/api/consolidation/runs/${runId}`),
      apiFetch<Elim[]>(`/api/consolidation/runs/${runId}/eliminations`),
      apiFetch<Statements>(`/api/consolidation/runs/${runId}/statements`),
    ])
    setRun(r)
    setElims(e)
    setStmts(s)
  }

  useEffect(() => {
    if (!runId) return
    load().catch((err: unknown) => {
      toast(err instanceof Error ? err.message : "Failed to load run", "error")
    })
  }, [runId])

  async function propose() {
    setBusy(true)
    try {
      const lines = await apiFetch<Elim[]>(`/api/consolidation/runs/${runId}/propose`, { method: "POST" })
      setElims(lines)
      const s = await apiFetch<Statements>(`/api/consolidation/runs/${runId}/statements`)
      setStmts(s)
      toast(`Proposed ${lines.length} elimination lines`, "success")
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Propose failed", "error")
    } finally {
      setBusy(false)
    }
  }

  async function post() {
    if (!(await confirm({
      title: "Post consolidation package?",
      message: "The package becomes immutable. Member GLs are not changed.",
      confirmLabel: "Post",
    }))) return
    setBusy(true)
    try {
      const r = await apiFetch<Run>(`/api/consolidation/runs/${runId}/post`, { method: "POST" })
      setRun(r)
      if (r.package) setStmts(r.package)
      toast("Package posted", "success")
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Post failed", "error")
    } finally {
      setBusy(false)
    }
  }

  async function voidRun() {
    if (!(await confirm({
      title: "Void this posted package?",
      message: "The package will be marked void and can no longer be used as the locked snapshot.",
      confirmLabel: "Void",
      danger: true,
    }))) return
    setBusy(true)
    try {
      const r = await apiFetch<Run>(`/api/consolidation/runs/${runId}/void`, { method: "POST" })
      setRun(r)
      toast("Package voided", "success")
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Void failed", "error")
    } finally {
      setBusy(false)
    }
  }

  if (!run || !stmts) {
    return <p className="text-sm text-[var(--text-muted)]">Loading…</p>
  }

  const elimDebit = elims.reduce((s, e) => s + e.debit, 0)
  const elimCredit = elims.reduce((s, e) => s + e.credit, 0)

  return (
    <div className="space-y-6">
      <PrintHeader
        title={run.name || `Consolidation #${run.id}`}
        subtitle={`${fmtDate(run.period_start)} – ${fmtDate(run.period_end)} · ${run.status}`}
      />

      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <Link href="/consolidation" className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="font-serif text-xl text-[var(--text-primary)]">{run.name || `Run #${run.id}`}</h1>
            <p className="text-sm text-[var(--text-muted)]">
              {fmtDate(run.period_start)} – {fmtDate(run.period_end)} · <span className="capitalize">{run.status}</span>
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {run.status === "draft" && (
            <>
              <button type="button" disabled={busy} onClick={propose} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[var(--text-primary)]/20 disabled:opacity-40">
                <Sparkles className="w-4 h-4" /> Propose eliminations
              </button>
              <button type="button" disabled={busy} onClick={post} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--text-primary)] text-white disabled:opacity-40">
                <Lock className="w-4 h-4" /> Post package
              </button>
            </>
          )}
          {run.status === "posted" && (
            <button type="button" disabled={busy} onClick={voidRun} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-red-300 text-red-700 disabled:opacity-40">
              <Ban className="w-4 h-4" /> Void
            </button>
          )}
          <button type="button" onClick={() => window.print()} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[var(--text-primary)]/20">
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
      </div>

      <div className="flex gap-1 print:hidden border-b border-[var(--text-primary)]/10">
        {(["worksheet", "bs", "pl"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium ${tab === t ? "border-b-2 border-[var(--accent)] text-[var(--text-primary)]" : "text-[var(--text-muted)]"}`}
          >
            {t === "worksheet" ? "Worksheet" : t === "bs" ? "Balance Sheet" : "Income Statement"}
          </button>
        ))}
      </div>

      {tab === "worksheet" && (
        <div className="space-y-6">
          {stmts.members && stmts.members.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50 border-b">
                    <th className="py-2 text-left">Member</th>
                    <th className="py-2 text-left">Type</th>
                    <th className="py-2 text-right">Own %</th>
                    <th className="py-2 text-right">Net assets</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--text-primary)]/5">
                  {stmts.members.map((m, i) => (
                    <tr key={i}>
                      <td className="py-2">{m.name}</td>
                      <td className="py-2 capitalize">{m.relationship}</td>
                      <td className="py-2 text-right font-mono">{m.ownership_pct}</td>
                      <td className="py-2 text-right font-mono">{fmt(m.net_assets)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <section>
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/70 mb-2">
              Eliminations
              <span className="ml-2 font-mono font-normal normal-case text-[var(--text-muted)]">
                Dr {fmt(elimDebit)} / Cr {fmt(elimCredit)}
                {Math.abs(elimDebit - elimCredit) > 0.005 && (
                  <span className="text-red-600 ml-2">out of balance</span>
                )}
              </span>
            </h2>
            {elims.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">No eliminations yet — click Propose or add manual lines.</p>
            ) : (
              <div className="overflow-x-auto table-freeze">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50 border-b">
                      <th className="py-2 text-left">Kind</th>
                      <th className="py-2 text-left">Description</th>
                      <th className="py-2 text-left">Account</th>
                      <th className="py-2 text-right">Debit</th>
                      <th className="py-2 text-right">Credit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--text-primary)]/5">
                    {elims.map((e) => (
                      <tr key={e.id}>
                        <td className="py-2 whitespace-nowrap text-[var(--text-muted)]">{e.kind}</td>
                        <td className="py-2">{e.description}</td>
                        <td className="py-2 font-mono whitespace-nowrap">{e.account_code} {e.account_name}</td>
                        <td className="py-2 text-right font-mono">{e.debit ? fmt(e.debit) : ""}</td>
                        <td className="py-2 text-right font-mono">{e.credit ? fmt(e.credit) : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}

      {tab === "bs" && (
        <div className="space-y-8">
          <TreeSection title="Assets" nodes={stmts.balance_sheet.assets} total={stmts.balance_sheet.totals.assets} totalLabel="Total assets" field="balance" fmt={fmt} />
          <TreeSection title="Liabilities" nodes={stmts.balance_sheet.liabilities} total={stmts.balance_sheet.totals.liabilities} totalLabel="Total liabilities" field="balance" fmt={fmt} />
          <TreeSection title="Equity" nodes={stmts.balance_sheet.equity} total={stmts.balance_sheet.totals.equity} totalLabel="Total equity" field="balance" fmt={fmt} />
        </div>
      )}

      {tab === "pl" && (
        <div className="space-y-8">
          <TreeSection title="Revenue" nodes={stmts.income_statement.revenue} total={stmts.income_statement.totals.revenue} totalLabel="Total revenue" field="amount" fmt={fmt} />
          <TreeSection title="Expenses" nodes={stmts.income_statement.expenses} total={stmts.income_statement.totals.expenses} totalLabel="Total expenses" field="amount" fmt={fmt} />
          <div className="flex justify-between pt-2 font-bold text-lg">
            <span>Net profit</span>
            <span className="font-mono">{fmt(stmts.income_statement.totals.net_profit)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
