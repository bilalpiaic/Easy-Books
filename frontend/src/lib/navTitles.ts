/**
 * Canonical page-title map shared by:
 *   - (dashboard)/layout.tsx  → browser tab title (document.title)
 *   - TabContext.tsx           → in-app tab bar labels
 *
 * Trailing-slash keys (e.g. "/invoices/") match sub-paths and are used for
 * individual record pages.  Non-trailing-slash keys are exact matches.
 */
export const TITLE_MAP: Record<string, string> = {
  "/dashboard":        "Dashboard",
  "/dashboard/operations": "Operations Dashboard",
  "/entry":            "New Entry",
  "/journal":          "Journal",
  "/journal/new":      "New Voucher",
  "/recurring":        "Recurring",
  "/ledger":           "General Ledger",
  "/coa":              "Chart of Accounts",
  "/invoices":         "Invoices",
  "/invoices/":        "Invoice",
  "/invoices/new":     "New Invoice",
  "/commissions":      "Sales Commissions",
  "/promo-discounts":  "Promotional Discounts",
  "/customers":        "Customers",
  "/customers/":       "Customer",
  "/payments-received":"Payments Received",
  "/bills":            "Bills",
  "/bills/":           "Bill",
  "/bills/new":        "New Bill",
  "/vendors":          "Vendors",
  "/vendors/":         "Vendor",
  "/bill-payments":    "Bill Payments",
  "/products":         "Products",
  "/products/new":     "New Product",
  "/products/":        "Product",
  "/products/categories": "Product Categories",
  "/products/ledger":     "Product Ledger",
  "/bank-accounts":    "Bank Accounts",
  "/bank-imports":     "Bank Statement Imports",
  "/analytic-accounts":    "Analytic Accounts",
  "/analytic-accounts/":   "Analytic P&L",
  "/reports/dimensional-pl": "Dimensional P&L",
  "/exchange-rates":       "Exchange Rates",
  "/deferred-revenue":     "Deferred Revenue",
  "/contract-balances":    "Contract Balances",
  "/tax-codes":            "Tax Codes",
  "/reconciliations":  "Reconciliations",
  "/trial-balance":    "Trial Balance",
  "/pl":               "Income Statement",
  "/balance":          "Balance Sheet",
  "/consolidation":    "Consolidation",
  "/consolidation/":   "Consolidation Run",
  "/leases":           "Leases",
  "/leases/":          "Lease",
  "/cashflow":         "Cash Flow",
  "/tax":              "Tax Reports",
  "/reports/wht":      "Withholding Tax",
  "/reports/cit-worksheet": "CIT Worksheet",
  "/india-gst/gstr":   "GSTR Report",
  "/profile":          "My Profile",
  "/team":             "Team",
  "/practice":         "Practice clients",
  "/workflow":         "Workflow",
  "/guide":            "User Guide",
  "/agent":            "AI Assistant",
  "/settings":         "Settings",
  "/apps":             "Add-ons",
  "/settings/permissions": "Permissions",
  "/settings/studio": "Studio",
  "/settings/catalog": "Catalog",
  "/manufacturing":                      "Manufacturing",
  "/manufacturing/purchase-orders":      "Purchase Orders",
  "/manufacturing/purchase-orders/":     "Purchase Order",
  "/manufacturing/stock-locations":           "Stock Locations",
  "/manufacturing/stock-locations/movements": "Stock Movements",
  "/manufacturing/stock-locations/custody":   "Custody Stock",
  "/manufacturing/grn":                  "Goods Receipt",
  "/manufacturing/grn/":                 "GRN",
  "/manufacturing/boms":                 "Bills of Material",
  "/manufacturing/boms/":                "BOM",
  "/manufacturing/rate-plans":           "Rate Plans",
  "/manufacturing/production-orders":    "Production Orders",
  "/manufacturing/production-orders/":   "Production Order",
  "/manufacturing/production-orders/new": "New Production Order",
  "/manufacturing/reports":              "Manufacturing Reports",
  "/manufacturing/scrap-reasons":         "Scrap Reasons",
  "/budgets":          "Budget vs Actual",
  "/credit-notes":     "Credit Notes",
  "/credit-notes/":    "Credit Note",
  "/debit-notes":      "Debit Notes",
  "/debit-notes/":     "Debit Note",
  "/advances":         "Advances",
  "/assets":           "Fixed Assets",
  "/assets/rollforward": "Asset Rollforward",
  "/audit":            "Audit Log",
  "/bank-book":        "Bank Book",
  "/cash-book":        "Cash Book",
  "/receivable":       "Accounts Receivable",
  "/payable":          "Accounts Payable",
  "/purchases/demands":      "Purchases",
  "/purchases/comparatives": "Comparatives",
  "/banking":          "Banking",
  "/purchases":        "Purchases",
  "/aging/receivable": "AR Aging",
  "/aging/payable":    "AP Aging",
  "/period-close":     "Period Close",
  "/inventory/performance": "Inventory Performance",
  "/inventory":             "Inventory",
  "/ecommerce":             "eCommerce Stores",
  "/customer-performance":  "Customer Performance",
  "/reports/builder":       "Report Builder",
  "/telecom":                   "Telecom",
  "/telecom/tracker":           "Tracker & Load",
  "/telecom/rso":               "RSO Channel",
  "/telecom/sim":               "SIM & Activations",
  "/telecom/fca":               "FCA & Targets",
  "/telecom/mobile-money":      "Mobile Money",
  "/telecom/postpaid":          "Postpaid Billing",
  "/telecom/commissions":       "Commissions",
  "/telecom/franchise":         "Franchise Admin",
  "/telecom/devices":           "Devices (IMEI)",
  "/imports":          "CSV Bulk Import",
  "/payment-terms":    "Payment Terms",
  // Payroll / HRM
  "/hrm":                          "HRM Overview",
  "/payroll":                      "Payroll",
  "/payroll/new":                  "New Payroll Run",
  "/payroll/":                     "Payroll Run",
  "/payroll/components":           "Salary Components",
  "/employees":                    "Employees",
  "/employees/new":                "New Employee",
  "/employees/":                   "Edit Employee",
  // Attendance
  "/attendance":                   "Attendance Register",
  "/attendance/record":            "Attendance Record",
  "/attendance/bulk":              "Bulk Attendance Entry",
  "/attendance/report":            "Attendance Report",
  "/attendance/import":            "Biometric Import",
  // Localization pack dashboards
  "/pra-logs":                     "PRA Submission Logs",
  "/pra-dashboard":                "PRA Sales Dashboard",
  "/uae":                          "UAE VAT Dashboard",
  "/uae/logs":                     "UAE e-Invoice Logs",
  "/uae-logs":                     "UAE e-Invoice Logs",
  "/zatca":                        "ZATCA Dashboard",
  "/zatca/logs":                   "ZATCA Submission Logs",
  "/peppol":                       "Peppol Dashboard",
  "/peppol/logs":                  "Peppol Submission Logs",
  "/uk-mtd":                       "UK MTD Dashboard",
  "/uk-mtd/logs":                  "UK MTD Submission Logs",
  "/my-invois":                    "MyInvois Dashboard",
  "/my-invois/logs":               "MyInvois Submission Logs",
  "/india-gst":                    "India GST Dashboard",
  // Healthcare
  "/healthcare":                   "Healthcare Overview",
  "/healthcare/patients":          "Patient Registry",
  "/healthcare/patients/":         "Patient Detail",
  "/healthcare/opd":               "OPD Queue",
  "/healthcare/ipd":               "Ward / IPD",
  "/healthcare/ipd/":              "Admission Detail",
  "/healthcare/lab":               "Laboratory",
  "/healthcare/lab/tests":         "Lab Test Catalogue",
  "/healthcare/procedures":        "Procedures",
  "/healthcare/store":             "Hospital Store",
  "/healthcare/reports":           "HC Reports",
  // Weaving
  "/weaving":                      "Weaving Overview",
  "/weaving/setup":                "Weaving Setup",
  "/weaving/contracts":            "Weaving Contracts",
  "/weaving/contracts/":           "Contract Detail",
  "/weaving/contracts/new":        "New Contract",
  "/weaving/yarn-inward":          "Yarn Inward",
  "/weaving/sizing":               "Sizing",
  "/weaving/production":           "Weaving Production",
  "/weaving/dispatch":             "Weaving Dispatch",
  "/weaving/calculators/weaving":   "Weaving Calculator",
  "/weaving/calculators/sizing":   "Sizing Calculator",
  "/weaving/reports/daily":        "Daily Operations",
  "/weaving/reports/contract-control": "Contract Control Panel",
  "/weaving/reports/customer-kpi": "Customer & Contract KPI",
  "/weaving/dashboard":            "Weaving Dashboard",
  "/weighbridge":                  "Weighbridge Overview",
  "/weighbridge/tickets":          "Weighbridge Tickets",
  "/weighbridge/tickets/new":      "New Weighbridge Ticket",
  "/weighbridge/tickets/":         "Weighbridge Ticket",
  "/weighbridge/reports/register": "Weighbridge Register",
  // Yarn Spinning
  "/spinning":                     "Spinning Overview",
  "/spinning/setup":               "Spinning Setup",
  "/spinning/plans":               "Production Plans",
  "/spinning/lots":                "Spin Lots",
  "/spinning/lots/":               "Spin Lot",
  "/spinning/bale-receipts":       "Bale Receipts",
  "/spinning/stages":              "Stage Entries",
  "/spinning/cone-output":         "Cone Output",
  "/spinning/waste":               "Waste Log",
  "/spinning/dispatch":            "Yarn Dispatch",
  "/spinning/dashboard":           "Spinning Dashboard",
  "/spinning/reports/daily":       "Spinning Daily Report",
  "/spinning/reports/lot-control": "Lot Control",
  "/spinning/reports/waste":       "Waste Report",
  "/spinning/calculators/yield":   "Yield Calculator",
  // Textile Processing
  "/processing":                   "Processing Overview",
  "/processing/setup":             "Processing Setup",
  "/processing/sales-orders":      "Sales Orders",
  "/processing/sales-orders/":     "Sales Order",
  "/processing/lots":              "Grey Inward",
  "/processing/lots/new":          "New Grey Inward",
  "/processing/lots/":             "Grey Inward",
  "/processing/mending":           "Mending",
  "/processing/kachi-parchi":      "Kachi Parchi",
  "/processing/pakki-parchi":      "Pakki Parchi",
  "/processing/rejection":         "Grey Rejection Outward",
  "/processing/production-orders": "Process Production Orders",
  "/processing/stages":            "PPC Stages",
  "/processing/dispatch":          "Fresh Dispatch",
  "/processing/labor-bills":       "Labor Bills",
  "/processing/settlements":       "Grey Settlement",
  "/processing/inspections":       "Inspections",
  "/processing/reports/rejection": "Rejection Register",
  "/processing/reports/stock-ledger": "Customer Stock Ledger",
  "/processing/reports/ppc":       "PPC Reports",
}

/**
 * Resolve a pathname to a human-readable tab/page title.
 *
 * Priority:
 * 1. Exact match
 * 2. Trailing-slash prefix match (longest first) — e.g. "/invoices/" for "/invoices/123"
 *    Numeric suffix → append " #<id>"
 * 3. Non-trailing-slash prefix match (longest first)
 */
export function resolveTitle(pathname: string): string {
  // 1. Exact match
  if (TITLE_MAP[pathname]) return TITLE_MAP[pathname]

  // 2. Trailing-slash prefix (individual record routes)
  const trailingEntries = Object.entries(TITLE_MAP)
    .filter(([k]) => k.endsWith("/"))
    .sort((a, b) => b[0].length - a[0].length)

  for (const [key, title] of trailingEntries) {
    if (pathname.startsWith(key)) {
      const suffix = pathname.slice(key.length)
      const numericId = suffix.split("/")[0]
      if (/^\d+$/.test(numericId)) return `${title} #${numericId}`
      return title
    }
  }

  // 3. Non-trailing-slash prefix match
  const plainEntries = Object.entries(TITLE_MAP)
    .filter(([k]) => !k.endsWith("/"))
    .sort((a, b) => b[0].length - a[0].length)

  for (const [key, title] of plainEntries) {
    if (pathname.startsWith(key + "/")) return title
  }

  return "Page"
}
