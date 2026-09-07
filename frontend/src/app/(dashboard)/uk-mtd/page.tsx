"use client"

import { useEffect, useState } from "react"
import PackDashboard from "@/components/localization/PackDashboard"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"

type VatBoxes = {
  vatDueSales: number
  vatDueAcquisitions: number
  totalVatDue: number
  vatReclaimedCurrPeriod: number
  netVatDue: number
  totalValueSalesExVAT: number
  totalValuePurchasesExVAT: number
  totalValueGoodsSuppliedExVAT: number
  totalAcquisitionsExVAT: number
  invoice_count?: number
  bill_count?: number
}

type VatReturn = {
  period_key: string
  start: string
  end: string
  boxes: VatBoxes
}

const BOX_ROWS: { key: keyof VatBoxes; label: string }[] = [
  { key: "vatDueSales", label: "Box 1 · VAT due on sales" },
  { key: "vatDueAcquisitions", label: "Box 2 · VAT due on acquisitions" },
  { key: "totalVatDue", label: "Box 3 · Total VAT due" },
  { key: "vatReclaimedCurrPeriod", label: "Box 4 · VAT reclaimed on purchases" },
  { key: "netVatDue", label: "Box 5 · Net VAT to pay / reclaim" },
  { key: "totalValueSalesExVAT", label: "Box 6 · Total sales excluding VAT" },
  { key: "totalValuePurchasesExVAT", label: "Box 7 · Total purchases excluding VAT" },
  { key: "totalValueGoodsSuppliedExVAT", label: "Box 8 · Total supplies to EU" },
  { key: "totalAcquisitionsExVAT", label: "Box 9 · Total acquisitions from EU" },
]

export default function UkMtdDashboardPage() {
  const fmt = useFmt()
  const [vat, setVat] = useState<VatReturn | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const load = () => {
    apiFetch<VatReturn>("/api/uk-mtd/vat-return")
      .then(setVat)
      .catch(() => {})
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-6">
      <section className="bg-white rounded-xl border border-[var(--border)] p-5 space-y-4">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h2 className="text-lg font-bold">VAT return boxes</h2>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              HMRC MTD boxes 1–9 for {vat?.period_key ?? "the current quarter"}
              {vat ? ` (${vat.start} → ${vat.end})` : ""}. Filing export only — this does not rewrite posted GL.
            </p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true)
              setMsg(null)
              try {
                const r = await apiFetch<{
                  success: boolean
                  error_message?: string
                  period_key?: string
                }>(`/api/uk-mtd/vat-return/submit${vat?.period_key ? `?period_key=${encodeURIComponent(vat.period_key)}` : ""}`, {
                  method: "POST",
                })
                setMsg(r.success
                  ? `Sandbox accepted ${r.period_key ?? "the return"}.`
                  : (r.error_message || "Submit failed"))
                load()
              } catch (e: unknown) {
                setMsg(String((e as Error).message ?? e))
              } finally {
                setBusy(false)
              }
            }}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--text-primary)] text-white hover:bg-[var(--text-primary)]/80 disabled:opacity-50"
          >
            {busy ? "Submitting…" : "Submit sandbox return"}
          </button>
        </div>
        {msg && (
          <p className="text-sm text-[var(--text-muted)]">{msg}</p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <tbody>
              {BOX_ROWS.map(row => (
                <tr key={row.key} className="border-t border-[var(--border-light)]">
                  <td className="py-2 pr-4 text-[var(--text-muted)]">{row.label}</td>
                  <td className="py-2 text-right font-mono">
                    {vat ? fmt(Number(vat.boxes[row.key] ?? 0)) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <PackDashboard
        config={{
          moduleId: "uk_mtd",
          title: "UK MTD Dashboard",
          subtitle: "HMRC Making Tax Digital VAT",
          statusColumn: "MTD",
          logsHref: "/uk-mtd/logs",
          logsLabel: "View Logs",
          successStatuses: ["accepted", "submitted"],
          failStatuses: ["rejected", "error", "failed"],
          pendingStatuses: ["pending"],
          statusOf: (inv) => inv.uk_mtd_status,
          refOf: (inv) => inv.uk_mtd_correlation_id,
          refColumn: "Correlation",
          secondaryLinks: [{ href: "/uk-mtd/logs", label: "Submission Logs" }],
        }}
      />
    </div>
  )
}
