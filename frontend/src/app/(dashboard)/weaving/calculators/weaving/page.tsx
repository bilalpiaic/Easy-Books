"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { apiFetch } from "@/lib/api"
import { calculateWeaving } from "@/lib/weavingYarnCalc"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { formatWeightTriple } from "@/lib/weavingUnits"

type ContractOpt = { id: number; number: string; planned_total_yarn_kg?: number | null }

const inputCls = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm bg-[var(--bg-card)]"
const labelCls = "block text-xs font-medium text-[var(--text-muted)] mb-1"

export default function WeavingCalculatorPage() {
  const router = useRouter()
  const search = useSearchParams()
  const [contracts, setContracts] = useState<ContractOpt[]>([])
  const [contractId, setContractId] = useState(search.get("contract") ?? "")
  const [form, setForm] = useState({
    epi: "60", ppi: "50", width_in: "60", length_yd: "1000",
    warp_ne: "40", weft_ne: "30",
    warp_crimp_pct: "10", weft_crimp_pct: "5",
    visible_waste_pct: "3", invisible_waste_pct: "1",
  })
  const [assigning, setAssigning] = useState(false)
  const [err, setErr] = useState("")
  const [overrideOpen, setOverrideOpen] = useState(false)
  const [overrideReason, setOverrideReason] = useState("")
  const [pendingWarnings, setPendingWarnings] = useState<string[]>([])

  useEffect(() => {
    apiFetch<ContractOpt[]>("/api/weaving/contracts").then(rows => {
      setContracts(Array.isArray(rows) ? rows : [])
    }).catch(() => setContracts([]))
  }, [])

  const num = (k: keyof typeof form) => parseFloat(form[k]) || 0

  const result = useMemo(() => calculateWeaving({
    epi: num("epi"), ppi: num("ppi"), width_in: num("width_in"), length_yd: num("length_yd"),
    warp_ne: num("warp_ne"), weft_ne: num("weft_ne"),
    warp_crimp_pct: num("warp_crimp_pct"), weft_crimp_pct: num("weft_crimp_pct"),
    visible_waste_pct: num("visible_waste_pct"), invisible_waste_pct: num("invisible_waste_pct"),
  }), [form]) // eslint-disable-line react-hooks/exhaustive-deps

  function set(k: keyof typeof form, v: string) {
    setForm(f => ({ ...f, [k]: v }))
  }

  async function doAssign(reason?: string) {
    if (!contractId) {
      setErr("Select a contract")
      return
    }
    setAssigning(true)
    setErr("")
    const body = {
      contract_id: Number(contractId),
      epi: num("epi"), ppi: num("ppi"), width_in: num("width_in"), length_yd: num("length_yd"),
      warp_ne: num("warp_ne"), weft_ne: num("weft_ne"),
      warp_crimp_pct: num("warp_crimp_pct"), weft_crimp_pct: num("weft_crimp_pct"),
      visible_waste_pct: num("visible_waste_pct"), invisible_waste_pct: num("invisible_waste_pct"),
      ...(reason ? { override_reason: reason } : {}),
    }
    try {
      await apiFetch("/api/weaving/calculators/weaving/assign", {
        method: "POST",
        body: JSON.stringify(body),
      })
      setOverrideOpen(false)
      setOverrideReason("")
      router.push(`/weaving/contracts/${contractId}`)
    } catch (ex: unknown) {
      const msg = ex instanceof Error ? ex.message : "Assign failed"
      if (msg.toLowerCase().includes("override") || msg.toLowerCase().includes("mismatch")) {
        setPendingWarnings(msg.split(" — ").filter(Boolean))
        setOverrideOpen(true)
      } else {
        setErr(msg)
      }
    } finally {
      setAssigning(false)
    }
  }

  const fields: { key: keyof typeof form; label: string }[] = [
    { key: "epi", label: "EPI" },
    { key: "ppi", label: "PPI" },
    { key: "width_in", label: "Width (inches)" },
    { key: "length_yd", label: "Length (yards)" },
    { key: "warp_ne", label: "Warp count (Ne)" },
    { key: "weft_ne", label: "Weft count (Ne)" },
    { key: "warp_crimp_pct", label: "Warp crimp %" },
    { key: "weft_crimp_pct", label: "Weft crimp %" },
    { key: "visible_waste_pct", label: "Visible waste %" },
    { key: "invisible_waste_pct", label: "Invisible waste %" },
  ]

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">Weaving Calculator</h1>
          <p className="text-sm text-[var(--text-muted)]">Ne yarn consumption → planned warp/weft on a contract</p>
        </div>
        <Link href="/weaving/calculators/sizing" className="text-sm text-[var(--primary)]">Sizing calculator →</Link>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {fields.map(f => (
          <div key={f.key}>
            <label className={labelCls}>{f.label}</label>
            <input type="number" step="any" value={form[f.key]} onChange={e => set(f.key, e.target.value)} className={inputCls} />
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 space-y-2 text-sm">
        <h2 className="font-medium text-[var(--text-primary)]">Results</h2>
        <div>Warp: <WeightTripleDisplay triple={result.warp} /></div>
        <div>Weft: <WeightTripleDisplay triple={result.weft} /></div>
        <div className="font-medium">Total: {formatWeightTriple(result.total)}</div>
        <div className="text-[var(--text-muted)] text-xs">
          Net before waste: {formatWeightTriple(result.net_before_waste)} · waste factor {result.waste_factor.toFixed(3)}
        </div>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 space-y-3">
        <div>
          <label className={labelCls}>Assign to contract</label>
          <select value={contractId} onChange={e => setContractId(e.target.value)} className={inputCls}>
            <option value="">Select…</option>
            {contracts.map(c => (
              <option key={c.id} value={c.id}>{c.number}</option>
            ))}
          </select>
        </div>
        <button
          type="button"
          disabled={assigning || !contractId}
          onClick={() => doAssign()}
          className="px-4 py-2 rounded-lg bg-[var(--primary)] text-white text-sm disabled:opacity-50"
        >
          {assigning ? "Assigning…" : "Assign to Contract"}
        </button>
      </div>

      {overrideOpen && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] shadow-xl w-full max-w-md p-5 space-y-3">
            <h2 className="text-lg font-semibold">Calculation mismatches contract</h2>
            <ul className="text-sm text-[var(--text-muted)] list-disc pl-5 space-y-1">
              {pendingWarnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
            <div>
              <label className={labelCls}>Override reason *</label>
              <textarea
                value={overrideReason}
                onChange={e => setOverrideReason(e.target.value)}
                className={inputCls}
                rows={2}
                placeholder="Why proceed despite the mismatch?"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setOverrideOpen(false)} className="px-3 py-2 text-sm rounded-lg border border-[var(--border)]">Cancel</button>
              <button
                type="button"
                disabled={!overrideReason.trim() || assigning}
                onClick={() => doAssign(overrideReason.trim())}
                className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50"
              >
                Assign anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
