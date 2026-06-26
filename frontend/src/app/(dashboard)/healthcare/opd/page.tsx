"use client"
import { useState, useEffect, useCallback } from "react"
import { Plus, ChevronRight } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { StatusBadge } from "@/components/healthcare/primitives"
import { fmtDate } from "@/lib/utils"

type Doctor = { id: number; name: string; specialization?: string; opd_fee: number }
type Token = { id: number; token_number: number; patient_name?: string; patient_id?: number; status: string; visit_date: string }
type Patient = { id: number; mr_number: string; name: string }
type Visit = { id: number; patient_id: number; visit_type: string; diagnosis?: string; transaction_id?: number }

type Tab = "queue" | "visit"

export default function OpdPage() {
  const today = new Date().toISOString().split("T")[0]
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [selectedDoctor, setSelectedDoctor] = useState<Doctor | null>(null)
  const [tokens, setTokens] = useState<Token[]>([])
  const [tab, setTab] = useState<Tab>("queue")
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(false)

  const [tokenForm, setTokenForm] = useState({ patient_id: "", patient_name: "", visit_date: today })
  const [tokenSaving, setTokenSaving] = useState(false)

  const [visitForm, setVisitForm] = useState({
    patient_id: "", doctor_id: "", visit_date: today, visit_type: "first",
    chief_complaint: "", diagnosis: "", advice: "", follow_up_date: "",
  })
  const [visitSaving, setVisitSaving] = useState(false)
  const [visitMsg, setVisitMsg] = useState("")

  useEffect(() => {
    async function load() {
      const [docs, pts] = await Promise.all([
        apiFetch<Doctor[]>("/api/healthcare/doctors").catch(() => [] as Doctor[]),
        apiFetch<Patient[] | { items: Patient[] }>("/api/healthcare/patients?limit=200").catch(() => [] as Patient[]),
      ])
      setDoctors(docs ?? [])
      setPatients(Array.isArray(pts) ? pts : (pts as { items: Patient[] }).items ?? [])
    }
    load()
  }, [])

  const loadTokens = useCallback(async () => {
    if (!selectedDoctor) return
    setLoading(true)
    try {
      const qs = new URLSearchParams({ doctor_id: String(selectedDoctor.id), date: tokenForm.visit_date })
      const toks = await apiFetch<Token[]>(`/api/healthcare/opd/tokens?${qs}`)
      setTokens(toks ?? [])
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [selectedDoctor, tokenForm.visit_date])

  useEffect(() => { loadTokens() }, [loadTokens])

  async function issueToken(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedDoctor) return
    setTokenSaving(true)
    try {
      const body = {
        doctor_id: selectedDoctor.id,
        visit_date: tokenForm.visit_date,
        ...(tokenForm.patient_id ? { patient_id: Number(tokenForm.patient_id) } : { patient_name: tokenForm.patient_name }),
      }
      await apiFetch("/api/healthcare/opd/tokens", { method: "POST", body: JSON.stringify(body) })
      setTokenForm(f => ({ ...f, patient_id: "", patient_name: "" }))
      loadTokens()
    } catch {
      // silent
    } finally {
      setTokenSaving(false)
    }
  }

  async function callToken(id: number) {
    await apiFetch(`/api/healthcare/opd/tokens/${id}/call`, { method: "PUT" }).catch(() => null)
    loadTokens()
  }

  async function recordVisit(e: React.FormEvent) {
    e.preventDefault()
    setVisitSaving(true)
    setVisitMsg("")
    try {
      const body = { ...visitForm, patient_id: Number(visitForm.patient_id), doctor_id: Number(visitForm.doctor_id) }
      const visit = await apiFetch<{ id: number }>("/api/healthcare/opd/visits", { method: "POST", body: JSON.stringify(body) })
      const doc = doctors.find(d => d.id === Number(visitForm.doctor_id))
      if (doc && doc.opd_fee > 0) {
        const bill = await apiFetch<{ amount: string }>(`/api/healthcare/opd/visits/${visit.id}/bill`, { method: "POST" }).catch(() => null)
        setVisitMsg(bill ? `Visit recorded & billed. Amount: ${bill.amount}` : "Visit recorded (billing failed)")
      } else {
        setVisitMsg("Visit recorded successfully")
      }
      setVisitForm(f => ({ ...f, patient_id: "", chief_complaint: "", diagnosis: "", advice: "", follow_up_date: "" }))
    } catch (e: unknown) {
      setVisitMsg(e instanceof Error ? e.message : "Failed to record visit")
    } finally {
      setVisitSaving(false)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">OPD</h1>
        <p className="text-sm text-neutral-500">Outpatient department — token queue & visit entry</p>
      </div>

      {/* Doctor selector */}
      <div className="bg-white rounded-xl border border-neutral-200 p-4">
        <label className="block text-xs font-medium text-neutral-600 mb-2">Select Doctor</label>
        <div className="flex flex-wrap gap-2">
          {doctors.map(d => (
            <button
              key={d.id}
              onClick={() => setSelectedDoctor(d)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                selectedDoctor?.id === d.id
                  ? "bg-rose-500 text-white border-rose-500"
                  : "bg-white text-neutral-700 border-neutral-200 hover:border-rose-300"
              }`}
            >
              {d.name}
              {d.specialization && <span className="ml-1 text-xs opacity-70">· {d.specialization}</span>}
            </button>
          ))}
          {doctors.length === 0 && (
            <p className="text-sm text-neutral-400">No doctors configured. Add doctors first.</p>
          )}
        </div>
      </div>

      {selectedDoctor && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Left panel */}
          <div className="space-y-3">
            <div className="flex gap-2 border-b border-neutral-200 pb-2">
              {(["queue", "visit"] as Tab[]).map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className={`px-3 py-1.5 text-sm rounded-lg font-medium ${tab === t ? "bg-rose-50 text-rose-600" : "text-neutral-600 hover:bg-neutral-50"}`}>
                  {t === "queue" ? "Token Queue" : "Record Visit"}
                </button>
              ))}
            </div>

            {tab === "queue" && (
              <div className="space-y-3">
                <form onSubmit={issueToken} className="bg-white rounded-xl border border-neutral-200 p-4 space-y-3">
                  <p className="text-sm font-medium text-neutral-700">Issue Token</p>
                  <input type="date" value={tokenForm.visit_date}
                    onChange={e => setTokenForm(f => ({ ...f, visit_date: e.target.value }))}
                    className="border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1">Registered Patient</label>
                    <select value={tokenForm.patient_id}
                      onChange={e => setTokenForm(f => ({ ...f, patient_id: e.target.value, patient_name: "" }))}
                      className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                      <option value="">— Walk-in —</option>
                      {patients.map(p => <option key={p.id} value={p.id}>{p.name} ({p.mr_number})</option>)}
                    </select>
                  </div>
                  {!tokenForm.patient_id && (
                    <input value={tokenForm.patient_name}
                      onChange={e => setTokenForm(f => ({ ...f, patient_name: e.target.value }))}
                      placeholder="Walk-in name (optional)"
                      className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
                  )}
                  <button type="submit" disabled={tokenSaving}
                    className="w-full bg-rose-500 text-white py-2 rounded-lg text-sm font-medium hover:bg-rose-600 disabled:opacity-50">
                    <Plus className="w-4 h-4 inline mr-1" /> Issue Token
                  </button>
                </form>

                <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
                  <div className="px-4 py-3 border-b border-neutral-100 flex items-center justify-between">
                    <span className="text-sm font-medium">{fmtDate(tokenForm.visit_date)} Queue</span>
                    <span className="text-xs text-neutral-400">{tokens.length} tokens</span>
                  </div>
                  {loading ? (
                    <div className="p-4 text-sm text-neutral-400">Loading…</div>
                  ) : tokens.length === 0 ? (
                    <div className="p-6 text-center text-neutral-400 text-sm">No tokens for this date</div>
                  ) : (
                    <div className="divide-y divide-neutral-100">
                      {tokens.map(t => (
                        <div key={t.id} className="flex items-center justify-between px-4 py-3">
                          <div className="flex items-center gap-3">
                            <span className="w-8 h-8 bg-rose-100 text-rose-700 rounded-full flex items-center justify-center text-sm font-bold">
                              {t.token_number}
                            </span>
                            <div>
                              <div className="text-sm font-medium">{t.patient_name || <span className="text-neutral-400 italic">Walk-in</span>}</div>
                              <StatusBadge status={t.status} />
                            </div>
                          </div>
                          {t.status === "waiting" && (
                            <button onClick={() => callToken(t.id)}
                              className="text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded-lg hover:bg-blue-100">
                              Call
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {tab === "visit" && (
              <form onSubmit={recordVisit} className="bg-white rounded-xl border border-neutral-200 p-4 space-y-3">
                <p className="text-sm font-medium text-neutral-700">Record OPD Visit</p>
                {visitMsg && (
                  <div className={`text-sm p-2 rounded-lg ${visitMsg.includes("Failed") || visitMsg.includes("failed") ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"}`}>
                    {visitMsg}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1">Patient *</label>
                    <select required value={visitForm.patient_id}
                      onChange={e => setVisitForm(f => ({ ...f, patient_id: e.target.value }))}
                      className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                      <option value="">Select patient…</option>
                      {patients.map(p => <option key={p.id} value={p.id}>{p.name} ({p.mr_number})</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1">Doctor *</label>
                    <select required value={visitForm.doctor_id}
                      onChange={e => setVisitForm(f => ({ ...f, doctor_id: e.target.value }))}
                      className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                      <option value="">Select doctor…</option>
                      {doctors.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1">Visit Date</label>
                    <input type="date" required value={visitForm.visit_date}
                      onChange={e => setVisitForm(f => ({ ...f, visit_date: e.target.value }))}
                      className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1">Visit Type</label>
                    <select value={visitForm.visit_type}
                      onChange={e => setVisitForm(f => ({ ...f, visit_type: e.target.value }))}
                      className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                      <option value="first">First Visit</option>
                      <option value="follow_up">Follow-up</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Chief Complaint</label>
                  <input value={visitForm.chief_complaint}
                    onChange={e => setVisitForm(f => ({ ...f, chief_complaint: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Diagnosis</label>
                  <textarea rows={2} value={visitForm.diagnosis}
                    onChange={e => setVisitForm(f => ({ ...f, diagnosis: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm resize-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Advice / Notes</label>
                  <textarea rows={2} value={visitForm.advice}
                    onChange={e => setVisitForm(f => ({ ...f, advice: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm resize-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Follow-up Date</label>
                  <input type="date" value={visitForm.follow_up_date}
                    onChange={e => setVisitForm(f => ({ ...f, follow_up_date: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <button type="submit" disabled={visitSaving}
                  className="w-full bg-rose-500 text-white py-2 rounded-lg text-sm font-medium hover:bg-rose-600 disabled:opacity-50">
                  {visitSaving ? "Saving…" : "Record Visit & Bill"}
                </button>
              </form>
            )}
          </div>

          {/* Today's visits */}
          <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden h-fit">
            <div className="px-4 py-3 border-b border-neutral-100">
              <span className="text-sm font-medium">Today's Visits — {selectedDoctor.name}</span>
            </div>
            <RecentVisits doctorId={selectedDoctor.id} date={tokenForm.visit_date} />
          </div>
        </div>
      )}
    </div>
  )
}

function RecentVisits({ doctorId, date }: { doctorId: number; date: string }) {
  const [visits, setVisits] = useState<Visit[]>([])

  useEffect(() => {
    apiFetch<Visit[] | { items: Visit[] }>(`/api/healthcare/opd/visits?doctor_id=${doctorId}&from_date=${date}&to_date=${date}&limit=20`)
      .then(d => setVisits(Array.isArray(d) ? d : (d as { items: Visit[] }).items ?? []))
      .catch(() => setVisits([]))
  }, [doctorId, date])

  if (visits.length === 0) return <div className="p-4 text-sm text-neutral-400">No visits recorded today</div>
  return (
    <div className="divide-y divide-neutral-100">
      {visits.map(v => (
        <div key={v.id} className="flex items-center justify-between px-4 py-3">
          <div>
            <div className="text-sm text-neutral-700 capitalize">{v.visit_type.replace("_", " ")} visit</div>
            {v.diagnosis && <div className="text-xs text-neutral-400 truncate max-w-[200px]">{v.diagnosis}</div>}
          </div>
          <div className="flex items-center gap-2">
            {v.transaction_id && (
              <span className="text-xs bg-green-50 text-green-700 px-1.5 py-0.5 rounded">Billed</span>
            )}
            <ChevronRight className="w-4 h-4 text-neutral-400" />
          </div>
        </div>
      ))}
    </div>
  )
}
