"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import Sidebar from "@/components/Sidebar"
import Header from "@/components/Header"
import BottomNav from "@/components/BottomNav"
import { isAuthenticated } from "@/lib/auth"
import { SettingsProvider } from "@/context/SettingsContext"
import { PermissionProvider } from "@/context/PermissionContext"
import NavBar from "@/components/NavBar"
import { BreadcrumbProvider } from "@/context/BreadcrumbContext"

const TITLE_MAP: Record<string, string> = {
  "/dashboard":        "Dashboard",
  "/entry":            "New Entry",
  "/journal":          "Journal",
  "/recurring":        "Recurring",
  "/ledger":           "General Ledger",
  "/coa":              "Chart of Accounts",
  "/invoices":         "Invoices",
  "/commissions":      "Sales Commissions",
  "/customers":        "Customers",
  "/customers/":       "Customer",
  "/payments-received":"Payments Received",
  "/bills":            "Bills",
  "/vendors":          "Vendors",
  "/vendors/":         "Vendor",
  "/bill-payments":    "Bill Payments",
  "/products":         "Products",
  "/bank-accounts":    "Bank Accounts",
  "/bank-imports":         "Bank Statement Imports",
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
  "/manufacturing/purchase-orders/":    "Purchase Order",
  "/manufacturing/stock-locations":           "Stock Locations",
  "/manufacturing/stock-locations/movements": "Stock Movements",
  "/manufacturing/stock-locations/custody":   "Customer Goods in Custody",
  "/manufacturing/grn":                  "Goods Receipt",
  "/manufacturing/boms":                 "Bills of Material",
  "/manufacturing/boms/":               "BOM Detail",
  "/manufacturing/rate-plans":           "Rate Plans",
  "/manufacturing/production-orders":    "Production Orders",
  "/manufacturing/production-orders/new": "New Production Order",
  "/manufacturing/reports":              "Manufacturing Reports",
  "/budgets":                            "Budget vs Actual",
  "/credit-notes":     "Credit Notes",
  "/credit-notes/":    "Credit Note",
  "/debit-notes":      "Debit Notes",
  "/debit-notes/":     "Debit Note",
  "/advances":         "Advances",
  "/assets":           "Fixed Assets",
  "/audit":            "Audit Log",
  "/bank-book":        "Bank Book",
  "/cash-book":        "Cash Book",
  "/aging/receivable": "AR Aging",
  "/aging/payable":    "AP Aging",
  "/period-close":     "Period Close",
  "/products/categories": "Product Categories",
  "/products/ledger":     "Product Ledger",
  "/products/new":        "New Product",
  "/products/":           "Product",
  "/inventory/performance": "Inventory Performance",
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
}

const LS_KEY_PINNED = "eb_sidebar_pinned"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router   = useRouter()
  const pathname = usePathname()
  const [open, setOpen]     = useState(false)
  const [pinned, setPinned] = useState(false)

  // Auth gate + hydrate pinned preference from localStorage. Also auto-open
  // the drawer on first render if the screen is wide enough — so desktop
  // users see the menu by default.
  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login")
      return
    }
    const pinnedSaved = typeof window !== "undefined" && localStorage.getItem(LS_KEY_PINNED) === "1"
    const isWide      = typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches
    if (pinnedSaved) {
      setPinned(true)
      setOpen(true)
    } else if (isWide) {
      setOpen(true)
    }
  }, [router])

  // Browser tab title — map pathname prefix to human-readable page name
  useEffect(() => {
    const match = Object.entries(TITLE_MAP).find(([path]) =>
      pathname === path || pathname.startsWith(path + "/")
    )
    document.title = match ? `${match[1]} — Easy-Books` : "Easy-Books"
  }, [pathname])

  // Keyboard shortcut: press N (outside inputs) → open-new-modal event
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable) return
      if (e.key === "n" || e.key === "N") {
        e.preventDefault()
        window.dispatchEvent(new CustomEvent("kbd:new"))
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  const onOpen        = useCallback(() => setOpen(true), [])
  const onClose       = useCallback(() => setOpen(false), [])
  const onTogglePinned = useCallback(() => {
    setPinned(prev => {
      const next = !prev
      if (typeof window !== "undefined") {
        if (next) localStorage.setItem(LS_KEY_PINNED, "1")
        else localStorage.removeItem(LS_KEY_PINNED)
      }
      // Re-open after pinning so the change is visible right away
      if (next) setOpen(true)
      return next
    })
  }, [])

  return (
    <SettingsProvider>
      <PermissionProvider>
      <BreadcrumbProvider>
        <div className="flex h-screen overflow-hidden bg-[#f6f3ee]">
          <Sidebar
            open={open}
            onClose={onClose}
            pinned={pinned}
            onTogglePinned={onTogglePinned}
          />
          <div className="flex-1 flex flex-col min-w-0">
            <Header onOpenMenu={onOpen} />
            <main className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 pb-20 md:pb-6 w-full">
              {/* No max-width constraint — pages decide their own width.
                  Tables/dashboards fill the viewport; narrative content can
                  wrap itself with `max-w-prose` where readability matters. */}
              <NavBar />
              {children}
            </main>
          </div>
          <BottomNav onMore={onOpen} />
        </div>
      </BreadcrumbProvider>
      </PermissionProvider>
    </SettingsProvider>
  )
}
