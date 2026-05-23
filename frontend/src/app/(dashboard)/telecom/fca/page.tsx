"use client"

import { useEffect, useState } from "react"
import { Target, Plus, CheckCircle2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface KPITarget {
  id: number
  tracker_account_id: number
  target_month: string
  target_fca_count: number
  actual_fca_count: number
  incentive_earned: string
  penalty_applied: string
  status: string
}

interface FCAEvent {
  id: number
  kpi_target_id: number
  event_date: string
  sim_number: string | null
  source_channel: string
  notes: string | null
}

interface TrackerAccount { id: number; operator_name: string }

function fmt(v: string) {
  const n = parseFloat(v)
  if (!n) return "—"
  return "PKR " + n.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

interface AddKPIFormProps { trackers: TrackerAccount[]; onCreated: () => void; onCancel: () => void }
function AddKPIForm({ trackers, onCreated, onCancel }: AddKPIFormProps) {
  const thisMonth = new Date().toISOString().slice(0, 7) + "-01"
  const [form, setForm] = useState({ tracker_account_id: "", target_month: thisMonth, target_fca_count: "" })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setErr(null)
    try {
      await apiFetch("/api/telecom/kpi-targets", { method: "POST", body: JSON.stringify({
        tracker_account_id: parseInt(form.tracker_account_id),
        target_month: form.target_month,
        target_fca_count: parseInt(form.target_fca_count),
      })})
      onCreated()
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Failed") }
    finally { setSaving(false) }
  }

  return (
    <form onSubmit={submit} className="bg-white border border-[#b8943f]/20 rounded-xl p-5 space-y-3">
      <h3 className="font-semibold text-[#1a1814]">Set KPI Target</h3>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Operator</label>
          <select required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.tracker_account_id} onChange={e => setForm(f => ({...f, tracker_account_id: e.target.value}))}>
            <option value="">Select…</option>
            {trackers.map(t => <option key={t.id} value={t.id}>{t.operator_name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Month</label>
          <input type="date" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.target_month} onChange={e => setForm(f => ({...f, target_month: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">FCA Target</label>
          <input type="number" min="1" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.target_fca_count} onChange={e => setForm(f => ({...f, target_fca_count: e.target.value}))} />
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={saving}
          className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium disabled:opacity-50">
          {saving ? "Saving…" : "Set Target"}
        </button>
        <button type="button" onClick={onCancel} className="px-4 py-2 rounded-lg border text-sm">Cancel</button>
      </div>
    </form>
  )
}

interface FCAEventFormProps { targets: KPITarget[]; onCreated: () => void; onCancel: () => void }
function FCAEventForm({ targets, onCreated, onCancel }: FCAEventFormProps) {
  const openTargets = targets.filter(t => t.status === "open")
  const [form, setForm] = useState({
    kpi_target_id: openTargets[0]?.id?.toString() ?? "",
    event_date: new Date().toISOString().split("T")[0],
    sim_number: "", source_channel: "rso_retail", notes: "",
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setErr(null)
    try {
      await apiFetch("/api/telecom/fca-events", { method: "POST", body: JSON.stringify({
        kpi_target_id: parseInt(form.kpi_target_id),
        event_date: form.event_date,
        sim_number: form.sim_number || undefined,
        source_channel: form.source_channel,
        notes: form.notes || undefined,
      })})
      onCreated()
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Failed") }
    finally { setSaving(false) }
  }

  return (
    <form onSubmit={submit} className="bg-white border border-[#b8943f]/20 rounded-xl p-5 space-y-3">
      <h3 className="font-semibold text-[#1a1814]">Log FCA Event</h3>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">KPI Target</label>
          <select required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.kpi_target_id} onChange={e => setForm(f => ({...f, kpi_target_id: e.target.value}))}>
            {openTargets.map(t => <option key={t.id} value={t.id}>{t.target_month}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Event Date</label>
          <input type="date" required className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.event_date} onChange={e => setForm(f => ({...f, event_date: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">SIM Number (optional)</label>
          <input className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.sim_number} onChange={e => setForm(f => ({...f, sim_number: e.target.value}))} />
        </div>
        <div>
          <label className="text-xs text-[#1a1814]/60 block mb-1">Channel</label>
          <select className="w-full border rounded-lg px-3 py-2 text-sm"
            value={form.source_channel} onChange={e => setForm(f => ({...f, source_channel: e.target.value}))}>
            <option value="rso_retail">RSO Retail</option>
            <option value="counter">Counter</option>
            <option value="direct">Direct</option>
          </select>
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={saving}
          className="px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium disabled:opacity-50">
          {saving ? "Saving…" : "Log FCA"}
        </button>
        <button type="button" onClick={onCancel} className="px-4 py-2 rounded-lg border text-sm">Cancel</button>
      </div>
    </form>
  )
}

export default function FCAPage() {
  const [targets, setTargets]   = useState<KPITarget[]>([])
  const [events, setEvents]     = useState<FCAEvent[]>([])
  const [trackers, setTrackers] = useState<TrackerAccount[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [showKPI, setShowKPI]   = useState(false)
  const [showFCA, setShowFCA]   = useState(false)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      apiFetch<{ items: KPITarget[] }>("/api/telecom/kpi-targets"),
      apiFetch<{ items: TrackerAccount[] }>("/api/telecom/tracker-accounts"),
    ])
      .then(([k, t]) => {
        setTargets(k.items); setTrackers(t.items)
        if (k.items.length && !selected) setSelected(k.items[0].id)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false))
  }

  const loadEvents = (kpiId: number) => {
    apiFetch<{ items: FCAEvent[] }>(`/api/telecom/fca-events?kpi_target_id=${kpiId}`)
      .then(d => setEvents(d.items))
      .catch(() => {})
  }

  useEffect(() => { load() }, [])
  useEffect(() => { if (selected) loadEvents(selected) }, [selected])

  const sel = targets.find(t => t.id === selected)
  const progress = sel ? Math.min(100, Math.round((sel.actual_fca_count / Math.max(1, sel.target_fca_count)) * 100)) : 0

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Target className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">FCA & KPI Targets</h1>
            <p className="text-sm text-[#1a1814]/60">First Call Activations and monthly operator KPI targets.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowFCA(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[#b8943f]/30 text-sm">
            <Plus className="w-4 h-4" /> Log FCA
          </button>
          <button onClick={() => setShowKPI(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium">
            <Plus className="w-4 h-4" /> Set Target
          </button>
        </div>
      </header>

      <HelpCallout title="FCA and commissions" tone="tip">
        FCA events are logged here but <b>no GL entry is posted</b> — they only increment the counter.
        At month-end, use <b>Close Target</b> to post the commission (Dr 1210 / Cr 4060) or
        penalty (Dr 5090 / Cr 1210) journal entry.
      </HelpCallout>

      {showKPI && <AddKPIForm trackers={trackers} onCreated={() => { setShowKPI(false); load() }} onCancel={() => setShowKPI(false)} />}
      {showFCA && <FCAEventForm targets={targets} onCreated={() => { setShowFCA(false); if (selected) loadEvents(selected) }} onCancel={() => setShowFCA(false)} />}
      {error && <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>}

      {loading ? <p className="text-sm text-[#1a1814]/50">Loading…</p> : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* KPI list */}
          <div className="space-y-2">
            {targets.length === 0 ? (
              <p className="text-sm text-[#1a1814]/40 p-4">No targets set yet.</p>
            ) : targets.map(t => {
              const pct = Math.min(100, Math.round((t.actual_fca_count / Math.max(1, t.target_fca_count)) * 100))
              return (
                <button key={t.id} onClick={() => setSelected(t.id)}
                  className={`w-full text-left rounded-xl border p-4 transition-colors
                    ${t.id === selected ? "border-[#b8943f] bg-[#fdf9f0]" : "border-[#b8943f]/20 bg-white hover:bg-[#f6f3ee]"}`}>
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-semibold text-sm">{t.target_month}</p>
                      <p className="text-xs text-[#1a1814]/50">{t.actual_fca_count} / {t.target_fca_count} FCAs</p>
                    </div>
                    {t.status === "closed" && <CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                  </div>
                  <div className="mt-2 w-full bg-[#f6f3ee] rounded-full h-1.5">
                    <div className={`h-1.5 rounded-full ${pct >= 100 ? "bg-emerald-500" : "bg-[#b8943f]"}`}
                      style={{ width: `${pct}%` }} />
                  </div>
                  <p className="text-xs text-[#1a1814]/40 mt-1">{pct}% achieved</p>
                </button>
              )
            })}
          </div>

          {/* Detail panel */}
          <div className="md:col-span-2 space-y-4">
            {sel && (
              <>
                <div className="rounded-xl border border-[#b8943f]/20 bg-white p-5 space-y-3">
                  <div className="flex justify-between items-center">
                    <h2 className="font-semibold text-[#1a1814]">{sel.target_month}</h2>
                    {sel.status === "open" && (
                      <button onClick={() => {
                        const incentive = prompt("Incentive earned (0 if penalty):", "0")
                        const penalty   = prompt("Penalty applied (0 if incentive):", "0")
                        const date      = prompt("Transaction date (YYYY-MM-DD):", new Date().toISOString().split("T")[0])
                        if (!date) return
                        apiFetch(`/api/telecom/kpi-targets/${sel.id}/close`, { method: "POST", body: JSON.stringify({
                          txn_date: date,
                          incentive_earned: parseFloat(incentive || "0"),
                          penalty_applied: parseFloat(penalty || "0"),
                        })}).then(() => load()).catch(e => alert(e.message))
                      }}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-medium">
                        Close & Post JV
                      </button>
                    )}
                  </div>
                  <div className="w-full bg-[#f6f3ee] rounded-full h-3">
                    <div className={`h-3 rounded-full ${progress >= 100 ? "bg-emerald-500" : "bg-[#b8943f]"}`}
                      style={{ width: `${progress}%` }} />
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div><span className="text-[#1a1814]/50 text-xs block">Target</span>{sel.target_fca_count}</div>
                    <div><span className="text-[#1a1814]/50 text-xs block">Actual</span>{sel.actual_fca_count}</div>
                    <div><span className="text-[#1a1814]/50 text-xs block">Achievement</span>{progress}%</div>
                  </div>
                  {(parseFloat(sel.incentive_earned) > 0 || parseFloat(sel.penalty_applied) > 0) && (
                    <div className="flex gap-4 text-sm">
                      {parseFloat(sel.incentive_earned) > 0 && (
                        <div className="text-emerald-700">Commission: <span className="font-semibold">{fmt(sel.incentive_earned)}</span></div>
                      )}
                      {parseFloat(sel.penalty_applied) > 0 && (
                        <div className="text-red-700">Penalty: <span className="font-semibold">{fmt(sel.penalty_applied)}</span></div>
                      )}
                    </div>
                  )}
                </div>

                {/* FCA event list */}
                <div className="rounded-xl border border-[#b8943f]/20 bg-white overflow-hidden">
                  <div className="px-4 py-3 border-b border-[#b8943f]/10">
                    <h3 className="font-semibold text-sm text-[#1a1814]">FCA Events ({events.length})</h3>
                  </div>
                  {events.length === 0 ? (
                    <p className="text-sm text-[#1a1814]/40 p-5">No FCA events logged yet.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-[#1a1814]/40 uppercase tracking-wide border-b border-[#b8943f]/10">
                          <th className="px-4 py-2 text-left">Date</th>
                          <th className="px-4 py-2 text-left">SIM</th>
                          <th className="px-4 py-2 text-left">Channel</th>
                        </tr>
                      </thead>
                      <tbody>
                        {events.map(e => (
                          <tr key={e.id} className="border-b border-[#b8943f]/5 hover:bg-[#f6f3ee]">
                            <td className="px-4 py-2 font-mono text-xs">{e.event_date}</td>
                            <td className="px-4 py-2 font-mono text-xs">{e.sim_number || "—"}</td>
                            <td className="px-4 py-2">
                              <span className="px-2 py-0.5 bg-slate-50 text-slate-700 rounded text-xs">{e.source_channel}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
