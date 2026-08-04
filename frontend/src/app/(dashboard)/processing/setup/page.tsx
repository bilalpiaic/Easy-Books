"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

type Quality = { id: number; code: string; name: string; blend?: string; width?: string; unit: string; is_active: boolean }
type Process = { id: number; seq: number; code: string; name: string; is_billing: boolean; default_sale_rate: number; is_active: boolean }
type Contractor = { id: number; code: string; name: string; vendor_id: number; is_active: boolean }
type Vendor = { id: number; name: string }

export default function ProcessingSetupPage() {
  const [tab, setTab] = useState<"qualities" | "processes" | "contractors">("qualities")
  const [qualities, setQualities] = useState<Quality[]>([])
  const [processes, setProcesses] = useState<Process[]>([])
  const [contractors, setContractors] = useState<Contractor[]>([])
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [err, setErr] = useState("")
  const [qForm, setQForm] = useState({ code: "", name: "", blend: "", width: "", unit: "MTR" })
  const [cForm, setCForm] = useState({ code: "", name: "", vendor_id: "" })

  function load() {
    apiFetch<Quality[]>("/api/textile-processing/qualities").then(d => setQualities(Array.isArray(d) ? d : [])).catch(() => setQualities([]))
    apiFetch<Process[]>("/api/textile-processing/processes").then(d => setProcesses(Array.isArray(d) ? d : [])).catch(() => setProcesses([]))
    apiFetch<Contractor[]>("/api/textile-processing/contractors").then(d => setContractors(Array.isArray(d) ? d : [])).catch(() => setContractors([]))
    apiFetch<Vendor[]>("/api/vendors").then(d => setVendors(Array.isArray(d) ? d : [])).catch(() => setVendors([]))
  }

  useEffect(() => { load() }, [])

  async function addQuality(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    try {
      await apiFetch("/api/textile-processing/qualities", { method: "POST", body: JSON.stringify(qForm) })
      setQForm({ code: "", name: "", blend: "", width: "", unit: "MTR" })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  async function addContractor(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    try {
      await apiFetch("/api/textile-processing/contractors", {
        method: "POST",
        body: JSON.stringify({ ...cForm, vendor_id: Number(cForm.vendor_id) }),
      })
      setCForm({ code: "", name: "", vendor_id: "" })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const tabs = [
    ["qualities", "Qualities"],
    ["processes", "Processes"],
    ["contractors", "Contractors"],
  ] as const

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <h1 className="text-xl font-semibold">Processing Setup</h1>
      <div className="flex gap-2 print:hidden">
        {tabs.map(([k, label]) => (
          <button key={k} type="button" onClick={() => setTab(k)}
            className={`px-3 py-1.5 text-sm rounded-lg border ${tab === k ? "border-[var(--primary)] bg-[var(--primary)]/10" : "border-[var(--border)]"}`}>
            {label}
          </button>
        ))}
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}

      {tab === "qualities" && (
        <div className="space-y-4">
          <form onSubmit={addQuality} className="grid grid-cols-2 md:grid-cols-5 gap-2 print:hidden">
            <input className={input} placeholder="Code" value={qForm.code} onChange={e => setQForm({ ...qForm, code: e.target.value })} required />
            <input className={input} placeholder="Name" value={qForm.name} onChange={e => setQForm({ ...qForm, name: e.target.value })} required />
            <input className={input} placeholder="Blend" value={qForm.blend} onChange={e => setQForm({ ...qForm, blend: e.target.value })} />
            <input className={input} placeholder="Width" value={qForm.width} onChange={e => setQForm({ ...qForm, width: e.target.value })} />
            <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Add quality</button>
          </form>
          <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
            <table className="w-full text-sm">
              <thead><tr className="text-left border-b border-[var(--border)]">
                <th className="p-2">Code</th><th className="p-2">Name</th><th className="p-2">Blend</th><th className="p-2">Width</th><th className="p-2">Unit</th>
              </tr></thead>
              <tbody>
                {qualities.map(q => (
                  <tr key={q.id} className="border-b border-[var(--border)]/60">
                    <td className="p-2 whitespace-nowrap">{q.code}</td>
                    <td className="p-2">{q.name}</td>
                    <td className="p-2">{q.blend || "—"}</td>
                    <td className="p-2">{q.width || "—"}</td>
                    <td className="p-2">{q.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "processes" && (
        <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
          <table className="w-full text-sm">
            <thead><tr className="text-left border-b border-[var(--border)]">
              <th className="p-2">Seq</th><th className="p-2">Code</th><th className="p-2">Name</th>
              <th className="p-2">Billing</th><th className="p-2 text-right">Default rate</th>
            </tr></thead>
            <tbody>
              {processes.map(p => (
                <tr key={p.id} className="border-b border-[var(--border)]/60">
                  <td className="p-2">{p.seq}</td>
                  <td className="p-2 whitespace-nowrap">{p.code}</td>
                  <td className="p-2">{p.name}</td>
                  <td className="p-2">{p.is_billing ? "Yes" : "No"}</td>
                  <td className="p-2 text-right">{p.default_sale_rate.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "contractors" && (
        <div className="space-y-4">
          <form onSubmit={addContractor} className="grid grid-cols-2 md:grid-cols-4 gap-2 print:hidden">
            <input className={input} placeholder="Code" value={cForm.code} onChange={e => setCForm({ ...cForm, code: e.target.value })} required />
            <input className={input} placeholder="Name" value={cForm.name} onChange={e => setCForm({ ...cForm, name: e.target.value })} required />
            <select className={input} value={cForm.vendor_id} onChange={e => setCForm({ ...cForm, vendor_id: e.target.value })} required>
              <option value="">Vendor…</option>
              {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
            <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Add contractor</button>
          </form>
          <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
            <table className="w-full text-sm">
              <thead><tr className="text-left border-b border-[var(--border)]">
                <th className="p-2">Code</th><th className="p-2">Name</th><th className="p-2">Vendor ID</th>
              </tr></thead>
              <tbody>
                {contractors.map(c => (
                  <tr key={c.id} className="border-b border-[var(--border)]/60">
                    <td className="p-2">{c.code}</td>
                    <td className="p-2">{c.name}</td>
                    <td className="p-2">{c.vendor_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
