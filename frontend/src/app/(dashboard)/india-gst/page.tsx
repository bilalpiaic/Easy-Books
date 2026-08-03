"use client"

import PackDashboard from "@/components/localization/PackDashboard"

export default function IndiaGstDashboardPage() {
  return (
    <PackDashboard
      config={{
        moduleId: "in_gst",
        title: "India GST Dashboard",
        subtitle: "CGST / SGST / IGST sales overview",
        statusColumn: "Status",
        logsHref: "/india-gst/gstr",
        logsLabel: "GSTR Report",
        // India pack is filing-oriented; treat posted/sent invoices as OK for the day
        successStatuses: ["posted", "sent", "paid", "partial"],
        failStatuses: ["void", "cancelled"],
        pendingStatuses: ["draft"],
        statusOf: (inv) => inv.status ?? "draft",
        showFailBanner: false,
        secondaryLinks: [
          { href: "/india-gst/gstr", label: "GSTR-1 / 3B" },
          { href: "/tax-codes", label: "Tax Codes" },
        ],
      }}
    />
  )
}
