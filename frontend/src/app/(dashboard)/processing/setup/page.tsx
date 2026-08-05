"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

type Quality = {
  id: number; code: string; name: string; blend?: string; width?: string; unit: string
  fiber?: string; warp_count?: string; weft_count?: string; epi?: string; ppi?: string
  width_inch?: string; is_active: boolean
}
type Process = {
  id: number; seq: number; code: string; name: string; is_billing: boolean
  default_sale_rate: number; is_active: boolean
}
type Contractor = {
  id: number; code: string; name: string; vendor_id: number
  default_process_id?: number | null; phone?: string; is_active: boolean
}
type Vendor = { id: number; name: string }

const emptyQ = {
  fiber: "CTN", warp_count: "60", weft_count: "60", epi: "40", ppi: "52",
  width_inch: "45", name: "", blend: "", unit: "MTR", code: "",
}
const emptyP = { seq: "170", code: "", name: "", is_billing: true, default_sale_rate: "0" }
const emptyC = { code: "", name: "", vendor_id: "", default_process_id: "", phone: "" }

function previewCode(f: typeof emptyQ) {
  const fiber = f.fiber.trim().toUpperCase()
  const w = f.width_inch.trim().replace(/["']/g, "")
  if (!fiber || !f.warp_count || !f.weft_count || !f.epi || !f.ppi || !w) return ""
  return `${fiber} ${f.warp_count}X${f.weft_count} ${f.epi}X${f.ppi} ${w}"`
}

export default function ProcessingSetupPage() {
  const [tab, setTab] = useState<"qualities" | "processes" | "contractors">("qualities")
  const [qualities, setQualities] = useState<Quality[]>([])
  const [processes, setProcesses] = useState<Process[]>([])
  const [contractors, setContractors] = useState<Contractor[]>([])
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [err, setErr] = useState("")
  const [qForm, setQForm] = useState(emptyQ)
  const [pForm, setPForm] = useState(emptyP)
  const [cForm, setCForm] = useState(emptyC)
  const [editProc, setEditProc] = useState<Process | null>(null)
  const [editContr, setEditContr] = useState<Contractor | null>(null)

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
      const code = previewCode(qForm) || qForm.code.trim()
      await apiFetch("/api/textile-processing/qualities", {
        method: "POST",
        body: JSON.stringify({
          ...qForm,
          code: code || undefined,
          name: qForm.name || code,
          fiber: qForm.fiber || undefined,
        }),
      })
      setQForm(emptyQ)
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  async function deactivateQuality(id: number) {
    setErr("")
    try {
      await apiFetch(`/api/textile-processing/qualities/${id}`, { method: "DELETE" })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  async function saveProcess(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    const payload = {
      seq: parseInt(editProc ? String(editProc.seq) : pForm.seq, 10) || 0,
      code: (editProc?.code ?? pForm.code).trim(),
      name: (editProc?.name ?? pForm.name).trim(),
      is_billing: editProc ? editProc.is_billing : pForm.is_billing,
      default_sale_rate: editProc
        ? editProc.default_sale_rate
        : parseFloat(pForm.default_sale_rate) || 0,
      is_active: editProc ? editProc.is_active : true,
    }
    try {
      if (editProc) {
        await apiFetch(`/api/textile-processing/processes/${editProc.id}`, {
          method: "PUT", body: JSON.stringify(payload),
        })
        setEditProc(null)
      } else {
        await apiFetch("/api/textile-processing/processes", {
          method: "POST", body: JSON.stringify(payload),
        })
        setPForm(emptyP)
      }
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  async function deleteProcess(id: number) {
    if (!confirm("Delete / deactivate this process?")) return
    setErr("")
    try {
      await apiFetch(`/api/textile-processing/processes/${id}`, { method: "DELETE" })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  async function saveContractor(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    const src = editContr
      ? {
          code: editContr.code,
          name: editContr.name,
          vendor_id: editContr.vendor_id,
          default_process_id: editContr.default_process_id || null,
          phone: editContr.phone || null,
          is_active: editContr.is_active,
        }
      : {
          code: cForm.code,
          name: cForm.name,
          vendor_id: Number(cForm.vendor_id),
          default_process_id: cForm.default_process_id ? Number(cForm.default_process_id) : null,
          phone: cForm.phone || null,
          is_active: true,
        }
    try {
      if (editContr) {
        await apiFetch(`/api/textile-processing/contractors/${editContr.id}`, {
          method: "PUT", body: JSON.stringify(src),
        })
        setEditContr(null)
      } else {
        await apiFetch("/api/textile-processing/contractors", {
          method: "POST", body: JSON.stringify(src),
        })
        setCForm(emptyC)
      }
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const tabs = [
    ["qualities", "Grey Qualities"],
    ["processes", "Processes"],
    ["contractors", "Contractors"],
  ] as const
  const procMap = Object.fromEntries(processes.map(p => [p.id, p.name]))

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
          <form onSubmit={addQuality} className="space-y-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
            <p className="text-xs font-medium text-[var(--text-muted)]">
              CODE STRUCTURE → <span className="font-mono text-[var(--text-primary)]">{previewCode(qForm) || "CTN 60X60 40X52 45\""}</span>
            </p>
            <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
              <input className={input} placeholder="Fiber (CTN)" value={qForm.fiber} onChange={e => setQForm({ ...qForm, fiber: e.target.value })} />
              <input className={input} placeholder="Warp" value={qForm.warp_count} onChange={e => setQForm({ ...qForm, warp_count: e.target.value })} />
              <input className={input} placeholder="Weft" value={qForm.weft_count} onChange={e => setQForm({ ...qForm, weft_count: e.target.value })} />
              <input className={input} placeholder="EPI" value={qForm.epi} onChange={e => setQForm({ ...qForm, epi: e.target.value })} />
              <input className={input} placeholder="PPI" value={qForm.ppi} onChange={e => setQForm({ ...qForm, ppi: e.target.value })} />
              <input className={input} placeholder='Width "' value={qForm.width_inch} onChange={e => setQForm({ ...qForm, width_inch: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <input className={input} placeholder="Display name (optional)" value={qForm.name} onChange={e => setQForm({ ...qForm, name: e.target.value })} />
              <input className={input} placeholder="Blend" value={qForm.blend} onChange={e => setQForm({ ...qForm, blend: e.target.value })} />
              <input className={input} placeholder="Free-text code override" value={qForm.code} onChange={e => setQForm({ ...qForm, code: e.target.value })} />
              <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Add quality</button>
            </div>
          </form>
          <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
            <table className="w-full text-sm">
              <thead><tr className="text-left border-b border-[var(--border)]">
                <th className="p-2">Code</th><th className="p-2">Name</th><th className="p-2">Structure</th>
                <th className="p-2">Unit</th><th className="p-2 print:hidden"> </th>
              </tr></thead>
              <tbody>
                {qualities.filter(q => q.is_active).map(q => (
                  <tr key={q.id} className="border-b border-[var(--border)]/60">
                    <td className="p-2 whitespace-nowrap font-mono text-xs">{q.code}</td>
                    <td className="p-2">{q.name}</td>
                    <td className="p-2 text-xs text-[var(--text-muted)]">
                      {[q.fiber, q.warp_count && q.weft_count ? `${q.warp_count}X${q.weft_count}` : null,
                        q.epi && q.ppi ? `${q.epi}X${q.ppi}` : null,
                        q.width_inch ? `${q.width_inch}"` : q.width].filter(Boolean).join(" · ") || "—"}
                    </td>
                    <td className="p-2">{q.unit}</td>
                    <td className="p-2 print:hidden">
                      <button type="button" onClick={() => deactivateQuality(q.id)} className="text-xs text-red-600">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "processes" && (
        <div className="space-y-4">
          <form onSubmit={saveProcess} className="grid grid-cols-2 md:grid-cols-6 gap-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
            {editProc ? (
              <>
                <input className={input} type="number" value={editProc.seq} onChange={e => setEditProc({ ...editProc, seq: Number(e.target.value) })} />
                <input className={input} value={editProc.code} onChange={e => setEditProc({ ...editProc, code: e.target.value })} />
                <input className={input} value={editProc.name} onChange={e => setEditProc({ ...editProc, name: e.target.value })} />
                <label className="flex items-center gap-2 text-sm px-2">
                  <input type="checkbox" checked={editProc.is_billing} onChange={e => setEditProc({ ...editProc, is_billing: e.target.checked })} /> Billing
                </label>
                <input className={input} type="number" step="0.01" value={editProc.default_sale_rate}
                  onChange={e => setEditProc({ ...editProc, default_sale_rate: parseFloat(e.target.value) || 0 })} />
                <div className="flex gap-2">
                  <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2 flex-1">Update</button>
                  <button type="button" onClick={() => setEditProc(null)} className="rounded-lg border text-sm px-3 py-2">Cancel</button>
                </div>
              </>
            ) : (
              <>
                <input className={input} type="number" placeholder="Seq" value={pForm.seq} onChange={e => setPForm({ ...pForm, seq: e.target.value })} required />
                <input className={input} placeholder="Code" value={pForm.code} onChange={e => setPForm({ ...pForm, code: e.target.value })} required />
                <input className={input} placeholder="Name" value={pForm.name} onChange={e => setPForm({ ...pForm, name: e.target.value })} required />
                <label className="flex items-center gap-2 text-sm px-2">
                  <input type="checkbox" checked={pForm.is_billing} onChange={e => setPForm({ ...pForm, is_billing: e.target.checked })} /> Billing
                </label>
                <input className={input} type="number" step="0.01" placeholder="Rate" value={pForm.default_sale_rate}
                  onChange={e => setPForm({ ...pForm, default_sale_rate: e.target.value })} />
                <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Add process</button>
              </>
            )}
          </form>
          <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
            <table className="w-full text-sm">
              <thead><tr className="text-left border-b border-[var(--border)]">
                <th className="p-2">Seq</th><th className="p-2">Code</th><th className="p-2">Name</th>
                <th className="p-2">Billing</th><th className="p-2 text-right">Default rate</th>
                <th className="p-2 print:hidden">Actions</th>
              </tr></thead>
              <tbody>
                {processes.filter(p => p.is_active).map(p => (
                  <tr key={p.id} className="border-b border-[var(--border)]/60">
                    <td className="p-2">{p.seq}</td>
                    <td className="p-2 whitespace-nowrap">{p.code}</td>
                    <td className="p-2">{p.name}</td>
                    <td className="p-2">{p.is_billing ? "Yes" : "No"}</td>
                    <td className="p-2 text-right">{Number(p.default_sale_rate).toFixed(2)}</td>
                    <td className="p-2 print:hidden space-x-2 whitespace-nowrap">
                      <button type="button" className="text-xs text-[var(--primary)]" onClick={() => setEditProc(p)}>Update</button>
                      <button type="button" className="text-xs text-red-600" onClick={() => deleteProcess(p.id)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "contractors" && (
        <div className="space-y-4">
          <form onSubmit={saveContractor} className="grid grid-cols-2 md:grid-cols-5 gap-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
            {editContr ? (
              <>
                <input className={input} value={editContr.code} onChange={e => setEditContr({ ...editContr, code: e.target.value })} />
                <input className={input} value={editContr.name} onChange={e => setEditContr({ ...editContr, name: e.target.value })} />
                <select className={input} value={editContr.vendor_id}
                  onChange={e => setEditContr({ ...editContr, vendor_id: Number(e.target.value) })}>
                  {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
                <select className={input} value={editContr.default_process_id ?? ""}
                  onChange={e => setEditContr({ ...editContr, default_process_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">Process tag…</option>
                  {processes.filter(p => p.is_active).map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
                <div className="flex gap-2">
                  <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2 flex-1">Update</button>
                  <button type="button" onClick={() => setEditContr(null)} className="rounded-lg border text-sm px-3 py-2">Cancel</button>
                </div>
              </>
            ) : (
              <>
                <input className={input} placeholder="Code" value={cForm.code} onChange={e => setCForm({ ...cForm, code: e.target.value })} required />
                <input className={input} placeholder="Name" value={cForm.name} onChange={e => setCForm({ ...cForm, name: e.target.value })} required />
                <select className={input} value={cForm.vendor_id} onChange={e => setCForm({ ...cForm, vendor_id: e.target.value })} required>
                  <option value="">Vendor…</option>
                  {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
                <select className={input} value={cForm.default_process_id} onChange={e => setCForm({ ...cForm, default_process_id: e.target.value })}>
                  <option value="">Process tag…</option>
                  {processes.filter(p => p.is_active).map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
                <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Add contractor</button>
              </>
            )}
          </form>
          <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
            <table className="w-full text-sm">
              <thead><tr className="text-left border-b border-[var(--border)]">
                <th className="p-2">Code</th><th className="p-2">Name</th>
                <th className="p-2">Process tag</th><th className="p-2 print:hidden">Actions</th>
              </tr></thead>
              <tbody>
                {contractors.filter(c => c.is_active).map(c => (
                  <tr key={c.id} className="border-b border-[var(--border)]/60">
                    <td className="p-2">{c.code}</td>
                    <td className="p-2">{c.name}</td>
                    <td className="p-2">{c.default_process_id ? (procMap[c.default_process_id] || c.default_process_id) : "—"}</td>
                    <td className="p-2 print:hidden">
                      <button type="button" className="text-xs text-[var(--primary)]" onClick={() => setEditContr(c)}>Update</button>
                    </td>
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
