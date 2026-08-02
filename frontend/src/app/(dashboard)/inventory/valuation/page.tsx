"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { fmtDateJs } from "@/lib/utils"

type PreviewRow = {
  product_id: number
  product_name: string
  qty: number
  unit_cost: number
  nrv_unit: number
  write_down: number
}

type Landed = { id: number; number: string; amount: number; status: string; goods_source_doc: string | null }
type NrV = { id: number; number: string; status: string; run_date: string }

export default function InventoryValuationPage() {
  const fmt = useFmt()
  const [preview, setPreview] = useState<PreviewRow[]>([])
  const [landed, setLanded] = useState<Landed[]>([])
  const [runs, setRuns] = useState<NrV[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [sourceDoc, setSourceDoc] = useState("")
  const [lcAmount, setLcAmount] = useState("100")
  const [busy, setBusy] = useState(false)

  const load = () => {
    apiFetch<PreviewRow[]>("/api/inventory/nrv/preview").then(setPreview).catch(() => setPreview([]))
    apiFetch<Landed[]>("/api/inventory/landed-costs").then(setLanded).catch(() => setLanded([]))
    apiFetch<NrV[]>("/api/inventory/nrv/runs").then(setRuns).catch(() => setRuns([]))
  }
  useEffect(load, [])

  const postNrv = async () => {
    setBusy(true); setErr(null); setMsg(null)
    try {
      const r = await apiFetch<NrV>("/api/inventory/nrv/runs", {
        method: "POST",
        body: JSON.stringify({ use_allowance: true }),
      })
      setMsg(`Posted ${r.number}`)
      load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : "NRV failed")
    } finally {
      setBusy(false)
    }
  }

  const postLanded = async () => {
    if (!sourceDoc.trim()) return
    setBusy(true); setErr(null); setMsg(null)
    try {
      const r = await apiFetch<Landed>("/api/inventory/landed-costs", {
        method: "POST",
        body: JSON.stringify({
          cost_date: new Date().toISOString().slice(0, 10),
          amount: Number(lcAmount),
          goods_source_doc: sourceDoc.trim(),
          allocation_method: "value",
          post: true,
        }),
      })
      setMsg(`Posted landed cost ${r.number}`)
      setSourceDoc("")
      load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Landed cost failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold">Inventory valuation</h1>
        <p className="text-sm text-[var(--text-muted)] mt-0.5">
          Landed cost allocation and IAS 2 NRV write-downs · {fmtDateJs(new Date())}
        </p>
      </div>

      {err && <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{err}</div>}
      {msg && <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-xl px-4 py-3 text-sm">{msg}</div>}

      <section className="bg-white border border-[var(--border)] rounded-xl p-4 space-y-3">
        <h2 className="text-sm font-semibold">Post landed cost</h2>
        <p className="text-xs text-[var(--text-muted)]">
          Enter the goods bill number (source_doc on inventory layers) and the freight/duty amount to allocate.
        </p>
        <div className="flex flex-wrap gap-2 items-end">
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-[var(--text-muted)] mb-1">Goods bill #</label>
            <input className="border rounded-lg px-3 py-1.5 text-sm" value={sourceDoc} onChange={e => setSourceDoc(e.target.value)} placeholder="BILL-0001" />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-[var(--text-muted)] mb-1">Amount</label>
            <input className="border rounded-lg px-3 py-1.5 text-sm w-28" value={lcAmount} onChange={e => setLcAmount(e.target.value)} />
          </div>
          <button type="button" disabled={busy || !sourceDoc} onClick={postLanded}
            className="bg-[var(--primary)] text-white px-3 py-1.5 rounded-lg text-sm disabled:opacity-40">
            Allocate &amp; post
          </button>
        </div>
        {landed.length > 0 && (
          <ul className="text-xs space-y-1 pt-2 border-t border-[var(--border)]">
            {landed.slice(0, 8).map(l => (
              <li key={l.id} className="flex justify-between">
                <span>{l.number} → {l.goods_source_doc || "—"}</span>
                <span>{fmt(l.amount)} · {l.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border)] bg-[var(--bg-page)]">
          <h2 className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">NRV preview</h2>
          <button type="button" disabled={busy || preview.length === 0} onClick={postNrv}
            className="text-xs bg-[var(--primary)] text-white px-3 py-1 rounded-lg disabled:opacity-40">
            Post write-down
          </button>
        </div>
        {preview.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
            No write-downs — set NRV on stock products below cost to see candidates.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--text-muted)]">
                <th className="px-4 py-2">Product</th>
                <th className="px-4 py-2 text-right">Qty</th>
                <th className="px-4 py-2 text-right">Cost</th>
                <th className="px-4 py-2 text-right">NRV</th>
                <th className="px-4 py-2 text-right">Write-down</th>
              </tr>
            </thead>
            <tbody>
              {preview.map(r => (
                <tr key={r.product_id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2">{r.product_name}</td>
                  <td className="px-4 py-2 text-right font-mono">{r.qty}</td>
                  <td className="px-4 py-2 text-right font-mono">{fmt(r.unit_cost)}</td>
                  <td className="px-4 py-2 text-right font-mono">{fmt(r.nrv_unit)}</td>
                  <td className="px-4 py-2 text-right font-mono font-semibold text-red-700">{fmt(r.write_down)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {runs.length > 0 && (
          <div className="px-4 py-3 border-t border-[var(--border)] text-xs text-[var(--text-muted)]">
            Recent runs: {runs.slice(0, 5).map(r => `${r.number} (${r.status})`).join(" · ")}
          </div>
        )}
      </section>
    </div>
  )
}
