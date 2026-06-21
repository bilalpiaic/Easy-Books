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
  "/exchange-rates":       "Exchange Rates",
  "/deferred-revenue":     "Deferred Revenue",
  "/tax-codes":            "Tax Codes",
  "/reconciliations":  "Reconciliations",
  "/trial-balance":    "Trial Balance",
  "/pl":               "Income Statement",
  "/balance":          "Balance Sheet",
  "/cashflow":         "Cash Flow",
  "/tax":              "Tax Reports",
  "/profile":          "My Profile",
  "/team":             "Team",
  "/workflow":         "Workflow",
  "/guide":            "User Guide",
  "/settings":         "Settings",
  "/settings/permissions": "Permissions",
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
  "/budgets":          "Budget vs Actual",
  "/credit-notes":     "Credit Notes",
  "/credit-notes/":    "Credit Note",
  "/debit-notes":      "Debit Notes",
  "/debit-notes/":     "Debit Note",
  "/advances":         "Advances",
  "/assets":           "Fixed Assets",
  "/audit":            "Audit Log",
  "/bank-book":        "Bank Book",
  "/cash-book":        "Cash Book",
  "/receivable":       "Accounts Receivable",
  "/payable":          "Accounts Payable",
  "/banking":          "Banking",
  "/aging/receivable": "AR Aging",
  "/aging/payable":    "AP Aging",
  "/period-close":     "Period Close",
  "/inventory/performance": "Inventory Performance",
  "/inventory":             "Inventory",
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
