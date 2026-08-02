"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Network, Plus, Trash2, Building2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useMessages } from "@/context/MessageContext"
import { fmtDate } from "@/lib/utils"

interface Member {
  id: number
  member_tenant_id: number
  tenant_name: string
  relationship: string
  ownership_pct: number
  label: string | null
  is_active: boolean
  ic_ar_code: string | null
  ic_ap_code: string | null
}

interface Eligible {
  tenant_id: number
  name: string
  role: string
  already_member: boolean
  is_holding: boolean
}

interface Run {
  id: number
  name: string | null
  period_start: string
  period_end: string
  status: string
  created_at: string
}

export default function ConsolidationPage() {
  const { toast, confirm } = useMessages()
  const [members, setMembers] = useState<Member[]>([])
  const [eligible, setEligible] = useState<Eligible[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const [addTenantId, setAddTenantId] = useState("")
  const [addRel, setAddRel] = useState("subsidiary")
  const [addPct, setAddPct] = useState("100")
  const [addAr, setAddAr] = useState("")
  const [addAp, setAddAp] = useState("")

  const [runStart, setRunStart] = useState("")
  const [runEnd, setRunEnd] = useState("")
  const [runName, setRunName] = useState("")

  async function load() {
    setLoading(true)
    try {
      const [m, e, r] = await Promise.all([
        apiFetch<Member[]>("/api/consolidation/members"),
        apiFetch<Eligible[]>("/api/consolidation/eligible-tenants"),
        apiFetch<Run[]>("/api/consolidation/runs"),
      ])
      setMembers(m)
      setEligible(e)
      setRuns(r)
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Failed to load consolidation", "error")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function addMember() {
    if (!addTenantId) return
    setBusy(true)
    try {
      await apiFetch("/api/consolidation/members", {
        method: "POST",
        body: JSON.stringify({
          member_tenant_id: Number(addTenantId),
          relationship: addRel,
          ownership_pct: Number(addPct) || 100,
          ic_ar_code: addAr || null,
          ic_ap_code: addAp || null,
        }),
      })
      toast("Entity added", "success")
      setAddTenantId("")
      setAddAr("")
      setAddAp("")
      await load()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Add failed", "error")
    } finally {
      setBusy(false)
    }
  }

  async function removeMember(m: Member) {
    if (!(await confirm({
      title: `Remove ${m.tenant_name}?`,
      message: "Remove this entity from the consolidation graph.",
      confirmLabel: "Remove",
      danger: true,
    }))) return
    setBusy(true)
    try {
      await apiFetch(`/api/consolidation/members/${m.id}`, { method: "DELETE" })
      toast("Removed", "success")
      await load()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Remove failed", "error")
    } finally {
      setBusy(false)
    }
  }

  async function createRun() {
    if (!runStart || !runEnd) {
      toast("Pick period start and end", "error")
      return
    }
    setBusy(true)
    try {
      const r = await apiFetch<Run>("/api/consolidation/runs", {
        method: "POST",
        body: JSON.stringify({
          period_start: runStart,
          period_end: runEnd,
          name: runName || undefined,
        }),
      })
      toast("Draft run created", "success")
      window.location.href = `/consolidation/runs/${r.id}`
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Create failed", "error")
      setBusy(false)
    }
  }

  const addable = eligible.filter((e) => !e.already_member && !e.is_holding)

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4 print:hidden">
        <div>
          <h1 className="font-serif text-2xl text-[var(--text-primary)] flex items-center gap-2">
            <Network className="w-6 h-6 text-[var(--accent)]" />
            Consolidation
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Group entity graph and consolidation worksheet (IFRS 10). Eliminations stay on the worksheet — member books are never altered.
          </p>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-[var(--text-muted)]">Loading…</p>
      ) : (
        <>
          {/* Entity graph */}
          <section className="space-y-3">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/70">
              Entity graph
            </h2>
            <div className="overflow-x-auto table-freeze">
              <table className="w-full text-sm text-left border-collapse">
                <thead>
                  <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50 border-b border-[var(--text-primary)]/10">
                    <th className="py-2 pr-3">Entity</th>
                    <th className="py-2 px-3">Relationship</th>
                    <th className="py-2 px-3 text-right">Ownership %</th>
                    <th className="py-2 px-3">IC AR</th>
                    <th className="py-2 px-3">IC AP</th>
                    <th className="py-2 pl-3 print:hidden" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--text-primary)]/5">
                  {members.map((m) => (
                    <tr key={m.id} className={!m.is_active ? "opacity-50" : undefined}>
                      <td className="py-2.5 pr-3 font-medium">
                        <span className="inline-flex items-center gap-1.5">
                          <Building2 className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                          {m.label || m.tenant_name}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 capitalize">{m.relationship}</td>
                      <td className="py-2.5 px-3 text-right font-mono">{m.ownership_pct}</td>
                      <td className="py-2.5 px-3 font-mono text-[var(--text-muted)]">{m.ic_ar_code || "—"}</td>
                      <td className="py-2.5 px-3 font-mono text-[var(--text-muted)]">{m.ic_ap_code || "—"}</td>
                      <td className="py-2.5 pl-3 print:hidden">
                        {m.relationship !== "parent" && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => removeMember(m)}
                            className="p-1 text-[var(--text-muted)] hover:text-red-600"
                            title="Remove"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-end gap-2 print:hidden pt-2">
              <label className="text-xs space-y-1">
                <span className="text-[var(--text-muted)]">Add entity</span>
                <select
                  className="block border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5 text-sm min-w-[12rem]"
                  value={addTenantId}
                  onChange={(e) => setAddTenantId(e.target.value)}
                >
                  <option value="">Select tenant…</option>
                  {addable.map((e) => (
                    <option key={e.tenant_id} value={e.tenant_id}>
                      {e.name} ({e.role})
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs space-y-1">
                <span className="text-[var(--text-muted)]">Type</span>
                <select
                  className="block border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5 text-sm"
                  value={addRel}
                  onChange={(e) => setAddRel(e.target.value)}
                >
                  <option value="subsidiary">Subsidiary</option>
                  <option value="associate">Associate</option>
                </select>
              </label>
              <label className="text-xs space-y-1">
                <span className="text-[var(--text-muted)]">Ownership %</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.01}
                  className="block border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5 text-sm w-24"
                  value={addPct}
                  onChange={(e) => setAddPct(e.target.value)}
                />
              </label>
              <label className="text-xs space-y-1">
                <span className="text-[var(--text-muted)]">IC AR code</span>
                <input
                  className="block border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5 text-sm w-24"
                  value={addAr}
                  onChange={(e) => setAddAr(e.target.value)}
                  placeholder="optional"
                />
              </label>
              <label className="text-xs space-y-1">
                <span className="text-[var(--text-muted)]">IC AP code</span>
                <input
                  className="block border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5 text-sm w-24"
                  value={addAp}
                  onChange={(e) => setAddAp(e.target.value)}
                  placeholder="optional"
                />
              </label>
              <button
                type="button"
                disabled={busy || !addTenantId}
                onClick={addMember}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-[var(--text-primary)] text-white disabled:opacity-40"
              >
                <Plus className="w-4 h-4" /> Add
              </button>
            </div>
            {addable.length === 0 && (
              <p className="text-xs text-[var(--text-muted)]">
                No other tenants available. Invite this user into a subsidiary via Team / Practice clients first.
              </p>
            )}
          </section>

          {/* New run */}
          <section className="space-y-3 print:hidden">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/70">
              New consolidation run
            </h2>
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-xs space-y-1">
                <span className="text-[var(--text-muted)]">From</span>
                <input type="date" className="block border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5 text-sm" value={runStart} onChange={(e) => setRunStart(e.target.value)} />
              </label>
              <label className="text-xs space-y-1">
                <span className="text-[var(--text-muted)]">To</span>
                <input type="date" className="block border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5 text-sm" value={runEnd} onChange={(e) => setRunEnd(e.target.value)} />
              </label>
              <label className="text-xs space-y-1">
                <span className="text-[var(--text-muted)]">Name</span>
                <input className="block border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5 text-sm min-w-[14rem]" value={runName} onChange={(e) => setRunName(e.target.value)} placeholder="Optional" />
              </label>
              <button
                type="button"
                disabled={busy}
                onClick={createRun}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-[var(--accent)] text-white disabled:opacity-40"
              >
                <Plus className="w-4 h-4" /> Create draft
              </button>
            </div>
          </section>

          {/* Runs list */}
          <section className="space-y-3">
            <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/70">
              Runs
            </h2>
            {runs.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">No consolidation runs yet.</p>
            ) : (
              <div className="overflow-x-auto table-freeze">
                <table className="w-full text-sm text-left border-collapse">
                  <thead>
                    <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50 border-b border-[var(--text-primary)]/10">
                      <th className="py-2 pr-3">Name</th>
                      <th className="py-2 px-3 whitespace-nowrap">Period</th>
                      <th className="py-2 px-3">Status</th>
                      <th className="py-2 pl-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--text-primary)]/5">
                    {runs.map((r) => (
                      <tr key={r.id}>
                        <td className="py-2.5 pr-3 font-medium">{r.name || `Run #${r.id}`}</td>
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          {fmtDate(r.period_start)} – {fmtDate(r.period_end)}
                        </td>
                        <td className="py-2.5 px-3 capitalize">{r.status}</td>
                        <td className="py-2.5 pl-3">
                          <Link href={`/consolidation/runs/${r.id}`} className="text-[var(--accent)] hover:underline text-sm">
                            Open
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
