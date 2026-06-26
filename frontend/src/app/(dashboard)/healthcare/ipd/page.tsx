"use client"
import { useState, useEffect, useCallback } from "react"
import { BedDouble } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { BedGrid, Bed, StatusBadge, HcCard } from "@/components/healthcare/primitives"
import { fmtDate } from "@/lib/utils"

type Ward = { id: number; name: string; ward_type: string; daily_charge: number; available_beds: number; occupied_beds: number }
type Admission = { id: number; admission_number: string; patient_id: number; ward_id: number; admission_date: string; status: string; diagnosis?: string; deposit_amount: number }
type Patient = { id: number; mr_number: string; name: string }
type Doctor = { id: number; name: string }

export default function IpdPage() {
  const today = new Date().toISOString().split("T")[0]
  const [wards, setWards] = useState<Ward[]>([])
  const [admissions, setAdmissions] = useState<Admission[]>([])
  const [selectedWard, setSelectedWard] = useState<Ward | null>(null)
  const [beds, setBeds] = useState<Bed[]>([])
  const [patients, setPatients] = useState<Patient[]>([])
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [showAdmit, setShowAdmit] = useState(false)
  const [selectedBed, setSelectedBed] = useState<Bed | null>(null)
  const [admitForm, setAdmitForm] = useState({
    patient_id: "", doctor_id: "", ward_id: "", bed_id: "",
    admission_date: today, diagnosis: "", admission_type: "planned", deposit_amount: "0",
  })
  const [admitting, setAdmitting] = useState(false)
  const [admitErr, setAdmitErr] = useState("")

  useEffect(() => {
    async function load() {
      const [w, a, p, d] = await Promise.all([
        apiFetch<Ward[]>("/api/healthcare/wards").catch(() => [] as Ward[]),
        apiFetch<Admission[] | { items: Admission[] }>("/api/healthcare/admissions?status=admitted&limit=50").catch(() => ({ items: [] as Admission[] })),
        apiFetch<Patient[] | { items: Patient[] }>("/api/healthcare/patients?limit=200").catch(() => ({ items: [] as Patient[] })),
        apiFetch<Doctor[]>("/api/healthcare/doctors").catch(() => [] as Doctor[]),
      ])
      setWards(w || [])
      setAdmissions(Array.isArray(a) ? a : (a as { items: Admission[] }).items ?? [])
      setPatients(Array.isArray(p) ? p : (p as { items: Patient[] }).items ?? [])
      setDoctors(d || [])
    }
    load()
  }, [])

  const loadBeds = useCallback(async (ward: Ward) => {
    const beds = await apiFetch<Bed[]>(`/api/healthcare/wards/${ward.id}/beds`).catch(() => [] as Bed[])
    setBeds(beds)
  }, [])

  useEffect(() => {
    if (selectedWard) loadBeds(selectedWard)
  }, [selectedWard, loadBeds])

  function selectBed(bed: Bed) {
    setSelectedBed(bed)
    setAdmitForm(f => ({
      ...f,
      ward_id: String(selectedWard?.id ?? ""),
      bed_id: String(bed.id),
    }))
    setShowAdmit(true)
  }

  async function admit(e: React.FormEvent) {
    e.preventDefault()
    setAdmitting(true)
    setAdmitErr("")
    try {
      const body = {
        patient_id: Number(admitForm.patient_id),
        doctor_id: Number(admitForm.doctor_id),
        ward_id: Number(admitForm.ward_id),
        bed_id: Number(admitForm.bed_id),
        admission_date: admitForm.admission_date,
        diagnosis: admitForm.diagnosis,
        admission_type: admitForm.admission_type,
        deposit_amount: parseFloat(admitForm.deposit_amount) || 0,
      }
      await apiFetch("/api/healthcare/admissions", { method: "POST", body: JSON.stringify(body) })
      setShowAdmit(false)
      setSelectedBed(null)
      const [w, a] = await Promise.all([
        apiFetch<Ward[]>("/api/healthcare/wards").catch(() => [] as Ward[]),
        apiFetch<Admission[] | { items: Admission[] }>("/api/healthcare/admissions?status=admitted&limit=50").catch(() => ({ items: [] as Admission[] })),
      ])
      setWards(w || [])
      setAdmissions(Array.isArray(a) ? a : (a as { items: Admission[] }).items ?? [])
      if (selectedWard) loadBeds(selectedWard)
    } catch (e: unknown) {
      setAdmitErr(e instanceof Error ? e.message : "Admission failed")
    } finally {
      setAdmitting(false)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">IPD / Inpatient</h1>
        <p className="text-sm text-neutral-500">Ward management & patient admissions</p>
      </div>

      {/* Ward selector */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {wards.map(w => (
          <button
            key={w.id}
            onClick={() => setSelectedWard(w)}
            className={`rounded-xl border p-4 text-left transition-colors ${
              selectedWard?.id === w.id ? "border-rose-400 bg-rose-50" : "border-neutral-200 bg-white hover:border-rose-300"
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <BedDouble className="w-4 h-4 text-rose-400" />
              <span className="font-medium text-sm">{w.name}</span>
            </div>
            <div className="text-xs text-neutral-500 capitalize">{w.ward_type}</div>
            <div className="mt-2 text-xs">
              <span className="text-emerald-600 font-medium">{w.available_beds}</span>
              <span className="text-neutral-400"> available / </span>
              <span className="text-red-600 font-medium">{w.occupied_beds}</span>
              <span className="text-neutral-400"> occupied</span>
            </div>
          </button>
        ))}
        {wards.length === 0 && (
          <div className="col-span-4 text-sm text-neutral-400">No wards configured. Add wards to get started.</div>
        )}
      </div>

      {/* Bed grid for selected ward */}
      {selectedWard && (
        <HcCard title={`${selectedWard.name} — Bed Layout (click available bed to admit)`}>
          <BedGrid beds={beds} onSelect={selectBed} />
        </HcCard>
      )}

      {/* Active admissions table */}
      <HcCard title="Currently Admitted Patients">
        <table className="w-full text-sm">
          <thead className="text-xs text-neutral-500 uppercase border-b border-neutral-100">
            <tr>
              <th className="text-left pb-2">Admission No.</th>
              <th className="text-left pb-2">Admitted</th>
              <th className="text-left pb-2">Status</th>
              <th className="text-left pb-2">Deposit</th>
              <th className="text-left pb-2">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {admissions.length === 0 ? (
              <tr><td colSpan={5} className="py-6 text-center text-neutral-400">No active admissions</td></tr>
            ) : admissions.map(a => (
              <tr key={a.id}>
                <td className="py-2.5 font-medium text-neutral-800">{a.admission_number}</td>
                <td className="py-2.5 text-neutral-600">{fmtDate(a.admission_date)}</td>
                <td className="py-2.5"><StatusBadge status={a.status} /></td>
                <td className="py-2.5 text-neutral-600">{parseFloat(String(a.deposit_amount)).toLocaleString()}</td>
                <td className="py-2.5">
                  <a href={`/healthcare/ipd/${a.id}`} className="text-xs text-rose-600 hover:underline">
                    View Details
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </HcCard>

      {/* Admit patient modal */}
      {showAdmit && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-semibold mb-1">Admit Patient</h2>
            {selectedBed && (
              <p className="text-sm text-neutral-500 mb-4">
                Bed <strong>{selectedBed.bed_number}</strong> in {selectedWard?.name}
              </p>
            )}
            {admitErr && <div className="mb-3 text-red-600 text-sm">{admitErr}</div>}
            <form onSubmit={admit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Patient *</label>
                  <select required value={admitForm.patient_id}
                    onChange={e => setAdmitForm(f => ({ ...f, patient_id: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                    <option value="">Select patient…</option>
                    {patients.map(p => <option key={p.id} value={p.id}>{p.name} ({p.mr_number})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Doctor *</label>
                  <select required value={admitForm.doctor_id}
                    onChange={e => setAdmitForm(f => ({ ...f, doctor_id: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                    <option value="">Select doctor…</option>
                    {doctors.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Admission Date</label>
                  <input type="date" value={admitForm.admission_date}
                    onChange={e => setAdmitForm(f => ({ ...f, admission_date: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Admission Type</label>
                  <select value={admitForm.admission_type}
                    onChange={e => setAdmitForm(f => ({ ...f, admission_type: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                    <option value="planned">Planned</option>
                    <option value="emergency">Emergency</option>
                    <option value="referred">Referred</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Deposit Amount</label>
                  <input type="number" min="0" step="0.01" value={admitForm.deposit_amount}
                    onChange={e => setAdmitForm(f => ({ ...f, deposit_amount: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Diagnosis</label>
                  <input value={admitForm.diagnosis}
                    onChange={e => setAdmitForm(f => ({ ...f, diagnosis: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => { setShowAdmit(false); setSelectedBed(null) }}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-lg hover:bg-neutral-50">
                  Cancel
                </button>
                <button type="submit" disabled={admitting}
                  className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg hover:bg-rose-600 disabled:opacity-50">
                  {admitting ? "Admitting…" : "Admit Patient"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
