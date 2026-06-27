"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

interface RunSummary {
  id: number
  total_lines: number
  total_net_pay: number
}

export default function NewPayrollRunPage() {
  const { t } = useTranslation()
  const router = useRouter()

  const today = new Date().toISOString().slice(0, 10)
  const firstOfMonth = today.slice(0, 8) + "01"

  const [form, setForm] = useState({
    period_start: firstOfMonth,
    period_end: today,
    pay_date: today,
    notes: "",
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const update = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.period_start || !form.period_end || !form.pay_date) {
      setError("Period dates and pay date are required")
      return
    }
    setSaving(true)
    setError("")
    try {
      const data = await apiFetch<RunSummary>("/api/payroll/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      })
      router.push(`/payroll/${data.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create payroll run")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/payroll" className="text-[var(--primary)] hover:underline">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">{t("New Payroll Run")}</h1>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">
            Period Start <span className="text-red-500">*</span>
          </label>
          <input
            type="date" required value={form.period_start}
            onChange={update("period_start")}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">
            Period End <span className="text-red-500">*</span>
          </label>
          <input
            type="date" required value={form.period_end}
            onChange={update("period_end")}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">
            Pay Date <span className="text-red-500">*</span>
          </label>
          <input
            type="date" required value={form.pay_date}
            onChange={update("pay_date")}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-[var(--text-primary)] mb-1">Notes</label>
          <textarea
            value={form.notes}
            onChange={update("notes")}
            rows={2}
            placeholder="Optional notes for this payroll run..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 resize-none"
          />
        </div>
        <p className="text-xs text-gray-400">
          Payroll lines will be auto-computed from each employee&apos;s current salary structure.
        </p>
        <div className="flex gap-3 pt-2">
          <button
            type="submit" disabled={saving}
            className="px-6 py-2 bg-[var(--primary)] text-white rounded-lg hover:opacity-90 text-sm font-medium disabled:opacity-50"
          >
            {saving ? "Computing..." : "Create Run & Compute Lines"}
          </button>
          <Link
            href="/payroll"
            className="px-6 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
