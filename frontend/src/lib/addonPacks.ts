/** Recommended industry packs — remaps the old pre-login "tenant types" onto Add-ons. */
export type AddonPack = {
  id: string
  label: string
  tagline: string
  modules: string[]
  features: string[]
}

export const ADDON_PACKS: AddonPack[] = [
  {
    id: "trader",
    label: "Trader",
    tagline: "Buy & resell",
    modules: ["inventory"],
    features: ["Products & stock", "Product ledger", "Inventory performance"],
  },
  {
    id: "manufacturing",
    label: "Manufacturing",
    tagline: "Value-addition",
    modules: ["inventory", "production", "purchase_store", "weaving"],
    features: ["BoM & production orders", "Purchases & Store", "Weaving unit control"],
  },
  {
    id: "telecom",
    label: "Telecom Franchise",
    tagline: "Operator franchise",
    modules: ["inventory", "telecom"],
    features: ["Tracker wallet", "RSO channel", "FCA & commissions"],
  },
  {
    id: "healthcare",
    label: "Healthcare",
    tagline: "Hospital & clinic",
    modules: ["hrm", "inventory", "healthcare"],
    features: ["OPD / IPD", "Lab & pharmacy", "Payroll"],
  },
  {
    id: "pra",
    label: "PRA e-Invoice",
    tagline: "Pakistani retail",
    modules: ["pra"],
    features: ["Fiscal invoice numbers", "PRA Sales home dashboard", "Submission logs"],
  },
  {
    id: "uae_vat",
    label: "UAE VAT e-Invoice",
    tagline: "UAE localization",
    modules: ["uae_vat"],
    features: ["5% VAT tax codes", "VAT Payable/Receivable CoA", "Sandbox FTA stub"],
  },
  {
    id: "sa_zatca",
    label: "Saudi ZATCA e-Invoice",
    tagline: "KSA localization",
    modules: ["sa_zatca"],
    features: ["Phase 2 sandbox clear/report", "TLV QR payload", "Submission logs"],
  },
  {
    id: "ai",
    label: "AI Assistant",
    tagline: "Ask your books",
    modules: ["ai_assistant"],
    features: ["Chat FAB", "Agentic report answers", "Multi-provider models"],
  },
]

/** Dedicated home dashboards exposed when the matching module is installed. */
export type AddonHome = {
  module: string
  href: string
  label: string
  preferenceKey: string
}

export const ADDON_HOMES: AddonHome[] = [
  { module: "pra", href: "/pra-dashboard", label: "PRA Sales", preferenceKey: "pra" },
]

export const HOME_PREF_KEY = "eb.home_dashboard"
