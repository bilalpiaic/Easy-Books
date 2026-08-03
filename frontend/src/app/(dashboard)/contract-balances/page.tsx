"use client"

import { useCallback, useEffect, useState } from "react"
import { Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV, fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface BalanceRow {
  customer_id: number
  name: string
  contract_liability: number
  contract_asset: number
}

interface BalancesResp {
  customers: BalanceRow[]
  totals: { contract_liability: number; contract_asset: number }
}

interface Customer { id: number; name: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function ContractBalancesPage() {
  const fmt = useFmt()
  const [data, setData] = useState<BalancesResp | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [customers, setCustomers] = useState<Customer[]>([])
  const [certify, setCertify] = useState({
    customer_id: "",
    amount: "",
    certify_date: today(),
    description: "",
  })
  const [certifying, setCertifying] = useState(false)
  const [certifyMsg, setCertifyMsg] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    apiFetch<BalancesResp>("/api/reports/contract-balances")
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    apiFetch<{ total: number; items: Customer[] }>("/api/customers?limit=200")
      .then(d => setCustomers(d.items ?? []))
      .catch(() => {})
  }, [])

  const submitCertify = async () => {
    if (!certify.customer_id || !certify.amount || !certify.description.trim()) {
      setCertifyMsg("Customer, amount, and description are required.")
      return
    }
    setCertifying(true)
    setCertifyMsg(null)
    try {
      await apiFetch("/api/contract-assets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: Number(certify.customer_id),
          amount: parseFloat(certify.amount),
          certify_date: certify.certify_date,
          description: certify.description.trim(),
        }),
      })
      setCertifyMsg("Contract asset certified.")
      setCertify(c => ({ ...c, amount: "", description: "" }))
      load()
    } catch (e) {
      setCertifyMsg(e instanceof Error ? e.message : "Certify failed")
    } finally {
      setCertifying(false)
    }
  }

  const rows = data?.customers ?? []

  return (
    <div className="space-y-6">
      <PrintHeader title="Contract Balances" orientation="landscape" />
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Contract Balances</h1>
          <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
            IFRS 15 — contract assets (unbilled) and liabilities (unearned deferred) by customer.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] rounded-lg text-xs font-bold hover:bg-[var(--bg-page)]"
          >
            <Printer className="w-3.5 h-3.5" /> Print
          </button>
          <button
            onClick={() => downloadCSV("contract-balances.csv", rows.map(r => ({
              Customer: r.name,
              "Contract Liability": r.contract_liability,
              "Contract Asset": r.contract_asset,
            })))}
            disabled={rows.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] rounded-lg text-xs font-bold hover:bg-[var(--bg-page)] disabled:opacity-40"
          >
            <Download className="w-3.5 h-3.5" /> CSV
          </button>
        </div>
      </div>

      {/* Certify unbilled */}
      <section className="bg-white border border-[var(--border)] rounded-xl p-4 print:hidden space-y-3">
        <h2 className="text-sm font-bold text-[var(--text-primary)]">Certify unbilled (contract asset)</h2>
        <p className="text-xs text-[var(--text-primary)]/55">
          Posts Dr Contract Asset (1140) / Cr Revenue when a performance obligation is satisfied before billing.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <select
            value={certify.customer_id}
            onChange={e => setCertify(c => ({ ...c, customer_id: e.target.value }))}
            className="ui-field bg-[var(--bg-page)] rounded-xl text-sm"
          >
            <option value="">Customer…</option>
            {customers.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <input
            type="number" min="0" step="0.01" placeholder="Amount"
            value={certify.amount}
            onChange={e => setCertify(c => ({ ...c, amount: e.target.value }))}
            className="ui-field bg-[var(--bg-page)] rounded-xl text-sm"
          />
          <input
            type="date"
            value={certify.certify_date}
            onChange={e => setCertify(c => ({ ...c, certify_date: e.target.value }))}
            className="ui-field bg-[var(--bg-page)] rounded-xl text-sm"
          />
          <input
            placeholder="Description"
            value={certify.description}
            onChange={e => setCertify(c => ({ ...c, description: e.target.value }))}
            className="ui-field bg-[var(--bg-page)] rounded-xl text-sm"
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={submitCertify}
            disabled={certifying}
            className="px-4 py-2 bg-[var(--primary)] text-white rounded-xl text-sm font-bold disabled:opacity-50"
          >
            {certifying ? "Saving…" : "Certify"}
          </button>
          {certifyMsg && <p className="text-xs text-[var(--text-primary)]/70">{certifyMsg}</p>}
        </div>
      </section>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {loading && <p className="text-sm text-[var(--text-primary)]/55">Loading…</p>}

      {!loading && data && (
        <div className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
          <div className="table-freeze overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-page)]">
                <tr>
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Customer</th>
                  <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Contract Liability</th>
                  <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Contract Asset</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-[var(--text-primary)]/50">
                      No open contract balances.
                    </td>
                  </tr>
                )}
                {rows.map(r => (
                  <tr key={r.customer_id}>
                    <td className="px-4 py-2 whitespace-nowrap">{r.name}</td>
                    <td className="px-4 py-2 text-right font-mono">{fmt(r.contract_liability)}</td>
                    <td className="px-4 py-2 text-right font-mono">{fmt(r.contract_asset)}</td>
                  </tr>
                ))}
              </tbody>
              {rows.length > 0 && (
                <tfoot>
                  <tr className="bg-[var(--bg-page)] font-bold">
                    <td className="px-4 py-2">Totals</td>
                    <td className="px-4 py-2 text-right font-mono">{fmt(data.totals.contract_liability)}</td>
                    <td className="px-4 py-2 text-right font-mono">{fmt(data.totals.contract_asset)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
          <p className="px-4 py-2 text-[10px] text-[var(--text-primary)]/45 print:hidden">
            As of {fmtDate(today())} · Liability = remaining deferred schedules · Asset = open unbilled certifications
          </p>
        </div>
      )}
    </div>
  )
}
