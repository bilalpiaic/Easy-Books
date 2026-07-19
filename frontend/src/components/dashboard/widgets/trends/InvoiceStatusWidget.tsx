"use client"

import { Doughnut } from "react-chartjs-2"
import { useFmt } from "@/context/SettingsContext"
import { TrendShell, doughnutOpts, useTrends } from "./common"

// Status palette (reserved semantics, never reused for plain series):
// draft=slate, sent=blue, partial=cyan, paid=green, overdue=red, void=gray.
const STATUS_COLORS: Record<string, string> = {
  draft: "#94a3b8", sent: "#2563eb", posted: "#7c3aed", partial: "#0891b2",
  paid: "#16a34a", overdue: "#dc2626", void: "#64748b",
}
const STATUS_ORDER = ["draft", "sent", "posted", "partial", "paid", "overdue", "void"]

/** Invoice pipeline: outstanding amount by document status. */
export default function InvoiceStatusWidget() {
  const fmt = useFmt()
  const { data, error } = useTrends()

  const rows = [...(data?.invoice_status ?? [])].sort(
    (a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status)
  )
  const totalCount = rows.reduce((n, r) => n + r.count, 0)

  const chartData = {
    labels: rows.map(r => `${r.status} (${r.count})`),
    datasets: [{
      data: rows.map(r => Number(r.amount)),
      backgroundColor: rows.map(r => STATUS_COLORS[r.status] ?? "#a8a29e"),
      borderWidth: 2, borderColor: "#fff",
    }],
  }

  return (
    <TrendShell
      title="Invoice Pipeline" sub={`Amount by status · ${totalCount} invoice${totalCount === 1 ? "" : "s"}`}
      href="/invoices" linkLabel="Invoices"
      loading={!data} error={error} empty={rows.length === 0} emptyText="No invoices yet."
    >
      <Doughnut data={chartData} options={doughnutOpts(fmt)} />
    </TrendShell>
  )
}
