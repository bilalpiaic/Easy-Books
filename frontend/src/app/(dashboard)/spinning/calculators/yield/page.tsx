"use client"

import { useMemo, useState } from "react"
import { apiFetch } from "@/lib/api"
import { WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { formatWeightTriple, type WeightTriple } from "@/lib/spinningUnits"

type YieldResult = {
  input_kg: number
  input_weight: WeightTriple
  output_kg?: number
  output_weight?: WeightTriple
  yield_pct?: number
  expected_output_kg?: number
  expected_weight?: WeightTriple
}

const inputCls = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm bg-[var(--bg-card)]"
const labelCls = "block text-xs font-medium text-[var(--text-muted)] mb-1"

export default function YieldCalculatorPage() {
  const [form, setForm] = useState({ input_kg: "", output_kg: "", expected_yield_pct: "" })
  const [result, setResult] = useState<YieldResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState("")

  const previewYield = useMemo(() => {
    const inp = parseFloat(form.input_kg) || 0
    const out = parseFloat(form.output_kg) || 0
    if (!inp || !out) return null
    return (out / inp) * 100
  }, [form.input_kg, form.output_kg])

  async function calculate(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setErr("")
    const body: Record<string, number> = {
      input_kg: parseFloat(form.input_kg) || 0,
    }
    if (form.output_kg.trim()) body.output_kg = parseFloat(form.output_kg) || 0
    if (form.expected_yield_pct.trim()) body.expected_yield_pct = parseFloat(form.expected_yield_pct) || 0
    try {
      const res = await apiFetch<YieldResult>("/api/spinning/calculators/yield", {
        method: "POST",
        body: JSON.stringify(body),
      })
      setResult(res)
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Calculation failed")
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 max-w-2xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Yield Calculator</h1>
        <p className="text-sm text-[var(--text-muted)]">Stage or lot yield — input vs output kg with expected yield</p>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}

      <form onSubmit={calculate} className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Input kg *</label>
          <input type="number" step="any" required value={form.input_kg}
            onChange={e => setForm(f => ({ ...f, input_kg: e.target.value }))} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Output kg</label>
          <input type="number" step="any" value={form.output_kg}
            onChange={e => setForm(f => ({ ...f, output_kg: e.target.value }))} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Expected yield %</label>
          <input type="number" step="any" value={form.expected_yield_pct}
            onChange={e => setForm(f => ({ ...f, expected_yield_pct: e.target.value }))} className={inputCls} />
        </div>
        <div className="flex items-end">
          <button type="submit" disabled={loading}
            className="w-full px-4 py-2 rounded-lg bg-[var(--primary)] text-white text-sm disabled:opacity-50">
            {loading ? "Calculating…" : "Calculate"}
          </button>
        </div>
        {previewYield != null && (
          <div className="sm:col-span-2 text-xs text-[var(--text-muted)]">
            Client preview yield: {previewYield.toFixed(2)}%
          </div>
        )}
      </form>

      {result && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 space-y-2 text-sm">
          <h2 className="font-medium text-[var(--text-primary)]">Results</h2>
          <div>Input: <WeightTripleDisplay triple={result.input_weight} /></div>
          {result.output_kg != null && (
            <>
              <div>Output: <WeightTripleDisplay triple={result.output_weight} /></div>
              <div className="font-medium">Yield: {result.yield_pct?.toFixed(2)}%</div>
            </>
          )}
          {result.expected_output_kg != null && (
            <div>Expected output: {formatWeightTriple(result.expected_weight)}</div>
          )}
        </div>
      )}
    </div>
  )
}
