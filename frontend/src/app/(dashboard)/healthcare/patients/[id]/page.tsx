"use client"
import { useState, useEffect } from "react"
import { use } from "react"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { StatusBadge } from "@/components/healthcare/primitives"
import { fmtDate } from "@/lib/utils"

type Patient = {
  id: number; mr_number: string; name: string; gender: string; dob?: string
  blood_group?: string; cnic?: string; phone?: string; address?: string
  allergies?: string; emergency_contact?: string; is_active: boolean; customer_id: number
}
type Visit = { id: number; visit_date: string; visit_type: string; doctor_id: number; diagnosis?: string }
type Admission = { id: number; admission_number: string; admission_date: string; discharge_date?: string; status: string; ward_id: number }
type LabOrder = { id: number; order_number: string; order_date: string; status: string }

type Tab = "demographics" | "opd" | "ipd" | "lab"

export default function PatientDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [patient, setPatient] = useState<Patient | null>(null)
  const [visits, setVisits] = useState<Visit[]>([])
  const [admissions, setAdmissions] = useState<Admission[]>([])
  const [labOrders, setLabOrders] = useState<LabOrder[]>([])
  const [tab, setTab] = useState<Tab>("demographics")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const [p, v, a, l] = await Promise.all([
        apiFetch<Patient>(`/api/healthcare/patients/${id}`).catch(() => null),
        apiFetch<Visit[] | { items: Visit[] }>(`/api/healthcare/opd/visits?patient_id=${id}&limit=30`).catch(() => [] as Visit[]),
        apiFetch<Admission[] | { items: Admission[] }>(`/api/healthcare/admissions?patient_id=${id}&limit=20`).catch(() => [] as Admission[]),
        apiFetch<LabOrder[] | { items: LabOrder[] }>(`/api/healthcare/lab/orders?patient_id=${id}&limit=30`).catch(() => [] as LabOrder[]),
      ])
      setPatient(p)
      setVisits(Array.isArray(v) ? v : (v as { items: Visit[] }).items ?? [])
      setAdmissions(Array.isArray(a) ? a : (a as { items: Admission[] }).items ?? [])
      setLabOrders(Array.isArray(l) ? l : (l as { items: LabOrder[] }).items ?? [])
      setLoading(false)
    }
    load()
  }, [id])

  if (loading) return <div className="p-6 text-neutral-400">Loading…</div>
  if (!patient) return <div className="p-6 text-neutral-400">Patient not found.</div>

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/healthcare/patients" className="text-neutral-400 hover:text-neutral-700">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">{patient.name}</h1>
          <p className="text-sm text-neutral-500">{patient.mr_number}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <StatusBadge status={patient.is_active ? "active" : "inactive"} />
          {patient.blood_group && (
            <span className="text-xs bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 rounded font-medium">
              {patient.blood_group}
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-neutral-200">
        {([
          ["demographics", "Demographics"],
          ["opd", `OPD History (${visits.length})`],
          ["ipd", `IPD History (${admissions.length})`],
          ["lab", `Lab Orders (${labOrders.length})`],
        ] as [Tab, string][]).map(([t, label]) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium ${tab === t ? "border-b-2 border-rose-500 text-rose-600" : "text-neutral-600 hover:text-neutral-800"}`}>
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "demographics" && (
        <div className="bg-white rounded-xl border border-neutral-200 p-5 grid grid-cols-2 gap-4">
          {[
            ["Gender", patient.gender],
            ["Date of Birth", patient.dob ? fmtDate(patient.dob) : "—"],
            ["CNIC", patient.cnic || "—"],
            ["Phone", patient.phone || "—"],
            ["Emergency Contact", patient.emergency_contact || "—"],
            ["Allergies", patient.allergies || "None recorded"],
          ].map(([label, val]) => (
            <div key={label}>
              <div className="text-xs text-neutral-500 uppercase font-medium mb-0.5">{label}</div>
              <div className="text-sm text-neutral-800">{val}</div>
            </div>
          ))}
          {patient.address && (
            <div className="col-span-2">
              <div className="text-xs text-neutral-500 uppercase font-medium mb-0.5">Address</div>
              <div className="text-sm text-neutral-800">{patient.address}</div>
            </div>
          )}
        </div>
      )}

      {tab === "opd" && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Type</th>
                <th className="text-left px-4 py-3">Diagnosis</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {visits.length === 0 ? (
                <tr><td colSpan={3} className="px-4 py-6 text-center text-neutral-400">No OPD visits</td></tr>
              ) : visits.map(v => (
                <tr key={v.id}>
                  <td className="px-4 py-3 whitespace-nowrap">{fmtDate(v.visit_date)}</td>
                  <td className="px-4 py-3 capitalize">{v.visit_type?.replace("_", " ") ?? "—"}</td>
                  <td className="px-4 py-3 text-neutral-600">{v.diagnosis || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "ipd" && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Admission No.</th>
                <th className="text-left px-4 py-3">Admitted</th>
                <th className="text-left px-4 py-3">Discharged</th>
                <th className="text-left px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {admissions.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-6 text-center text-neutral-400">No admissions</td></tr>
              ) : admissions.map(a => (
                <tr key={a.id}>
                  <td className="px-4 py-3 font-medium">
                    <Link href={`/healthcare/ipd/${a.id}`} className="text-rose-600 hover:underline">
                      {a.admission_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">{fmtDate(a.admission_date)}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{a.discharge_date ? fmtDate(a.discharge_date) : "—"}</td>
                  <td className="px-4 py-3"><StatusBadge status={a.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "lab" && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Order No.</th>
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {labOrders.length === 0 ? (
                <tr><td colSpan={3} className="px-4 py-6 text-center text-neutral-400">No lab orders</td></tr>
              ) : labOrders.map(o => (
                <tr key={o.id}>
                  <td className="px-4 py-3 font-medium">{o.order_number}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{fmtDate(o.order_date)}</td>
                  <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
