"use client"

import PackDashboard from "@/components/localization/PackDashboard"

export default function ZatcaDashboardPage() {
  return (
    <PackDashboard
      config={{
        moduleId: "sa_zatca",
        title: "ZATCA Dashboard",
        subtitle: "Saudi Fatoora e-invoice",
        statusColumn: "ZATCA",
        logsHref: "/zatca/logs",
        logsLabel: "View Logs",
        successStatuses: ["cleared", "reported", "submitted"],
        failStatuses: ["rejected", "error", "failed"],
        pendingStatuses: ["pending"],
        statusOf: (inv) => inv.zatca_status,
        refOf: (inv) => inv.zatca_uuid,
        refColumn: "UUID",
        secondaryLinks: [{ href: "/zatca/logs", label: "Submission Logs" }],
      }}
    />
  )
}
