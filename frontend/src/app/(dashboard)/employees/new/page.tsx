"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

export default function NewEmployeePage() {
  const { t } = useTranslation()
  const router = useRouter()

  const [form, setForm] = useState({
    employee_code: "",
    name: "",
    department: "",
    designation: "",
    join_date: "",
    cnic: "",
    bank_account: "",
    bank_name: "",
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const update = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) { setError("Name is required"); return }
    setSaving(true)
    setError("")
    try {
      const body: Record<string, string | undefined> = { name: form.name }
      if (form.employee_code) body.employee_code = form.employee_code
      if (form.department) body.department = form.department
      if (form.designation) body.designation = form.designation
      if (form.join_date) body.join_date = form.join_date
      if (form.cnic) body.cnic = form.cnic
      if (form.bank_account) body.bank_account = form.bank_account
      if (form.bank_name) body.bank_name = form.bank_name

      const data = await apiFetch<{ id: number; employee_code: string }>("/api/employees", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      router.push(`/employees/${data.id}/edit`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create employee")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/employees" className="text-[var(--primary)] hover:underline">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">{t("New Employee")}</h1>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">
              Employee Code <span className="text-gray-400 font-normal">(auto if blank)</span>
            </label>
            <input
              type="text"
              value={form.employee_code}
              onChange={update("employee_code")}
              placeholder="EMP-0001"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">
              Full Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={update("name")}
              required
              placeholder="e.g. Ahmed Ali"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">Department</label>
            <input
              type="text"
              value={form.department}
              onChange={update("department")}
              placeholder="e.g. Finance"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">Designation</label>
            <input
              type="text"
              value={form.designation}
              onChange={update("designation")}
              placeholder="e.g. Accountant"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">Join Date</label>
            <input
              type="date"
              value={form.join_date}
              onChange={update("join_date")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">CNIC</label>
            <input
              type="text"
              value={form.cnic}
              onChange={update("cnic")}
              placeholder="XXXXX-XXXXXXX-X"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">Bank Account</label>
            <input
              type="text"
              value={form.bank_account}
              onChange={update("bank_account")}
              placeholder="Account number"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">Bank Name</label>
            <input
              type="text"
              value={form.bank_name}
              onChange={update("bank_name")}
              placeholder="e.g. HBL"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2 bg-[var(--primary)] text-white rounded-lg hover:opacity-90 text-sm font-medium disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save & Continue to Salary Structure"}
          </button>
          <Link
            href="/employees"
            className="px-6 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
