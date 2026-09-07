"use client"

import PackDashboard from "@/components/localization/PackDashboard"

export default function MyInvoisDashboardPage() {
  return (
    <PackDashboard
      config={{
        moduleId: "my_invois",
        title: "MyInvois Dashboard",
        subtitle: "LHDN Malaysia e-invoice",
        statusColumn: "MyInvois",
        logsHref: "/my-invois/logs",
        logsLabel: "View Logs",
        successStatuses: ["accepted", "submitted"],
        failStatuses: ["rejected", "error", "failed"],
        pendingStatuses: ["pending"],
        statusOf: (inv) => inv.my_invois_status,
        refOf: (inv) => inv.my_invois_uuid,
        refColumn: "UUID",
        secondaryLinks: [{ href: "/my-invois/logs", label: "Submission Logs" }],
      }}
    />
  )
}
