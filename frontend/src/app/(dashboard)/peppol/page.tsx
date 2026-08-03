"use client"

import PackDashboard from "@/components/localization/PackDashboard"

export default function PeppolDashboardPage() {
  return (
    <PackDashboard
      config={{
        moduleId: "eu_peppol",
        title: "Peppol Dashboard",
        subtitle: "EU BIS Billing 3.0 / Access Point",
        statusColumn: "Peppol",
        logsHref: "/peppol/logs",
        logsLabel: "View Logs",
        successStatuses: ["accepted", "submitted"],
        failStatuses: ["rejected", "error", "failed"],
        pendingStatuses: ["pending"],
        statusOf: (inv) => inv.peppol_status,
        refOf: (inv) => inv.peppol_document_id,
        refColumn: "Doc ID",
        secondaryLinks: [{ href: "/peppol/logs", label: "Submission Logs" }],
      }}
    />
  )
}
