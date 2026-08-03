"use client"

import PackDashboard from "@/components/localization/PackDashboard"
import type { PackInvoice } from "@/components/localization/PackDashboard"
import { apiFetch } from "@/lib/api"

async function enrichUae(invoices: PackInvoice[]): Promise<PackInvoice[]> {
  try {
    const logs = await apiFetch<Array<{
      invoice_id: number
      success: boolean
      response_uuid: string | null
    }>>("/api/uae/logs?limit=200")
    const byInv = new Map<number, { success: boolean; uuid: string | null }>()
    for (const log of logs) {
      if (!byInv.has(log.invoice_id)) {
        byInv.set(log.invoice_id, { success: log.success, uuid: log.response_uuid })
      }
    }
    return invoices.map((inv) => {
      const hit = byInv.get(inv.id)
      if (!hit) return { ...inv, pack_status: "pending", pack_ref: null }
      return {
        ...inv,
        pack_status: hit.success ? "submitted" : "failed",
        pack_ref: hit.uuid,
      }
    })
  } catch {
    return invoices.map((inv) => ({ ...inv, pack_status: inv.pack_status ?? "—" }))
  }
}

export default function UaeDashboardPage() {
  return (
    <PackDashboard
      config={{
        moduleId: "uae_vat",
        title: "UAE VAT Dashboard",
        subtitle: "FTA e-invoice compliance",
        statusColumn: "UAE",
        logsHref: "/uae/logs",
        logsLabel: "View Logs",
        successStatuses: ["submitted"],
        failStatuses: ["failed"],
        pendingStatuses: ["pending", "not_submitted", "—"],
        statusOf: (inv) => inv.pack_status,
        refOf: (inv) => inv.pack_ref,
        refColumn: "UUID",
        enrichInvoices: enrichUae,
        secondaryLinks: [{ href: "/uae/logs", label: "Submission Logs" }],
      }}
    />
  )
}
