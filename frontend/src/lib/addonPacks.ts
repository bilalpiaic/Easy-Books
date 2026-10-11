/** Recommended packs on System → Add-ons, grouped by category of use. */

export type AddonPackGroup = "industry" | "localization" | "intelligence"

export type AddonPack = {
  id: string
  label: string
  tagline: string
  group: AddonPackGroup
  modules: string[]
  features: string[]
}

/** Allowlist + sort order of MODULE_REGISTRY categories on the Add-ons page. */
export const MODULE_CATEGORY_ORDER = [
  "Core",
  "Operations",
  "HR",
  "Industry",
  "Localization",
  "Intelligence",
] as const

export type ModuleCategory = (typeof MODULE_CATEGORY_ORDER)[number]

export const MODULE_CATEGORY_META: Record<
  Exclude<ModuleCategory, "Core">,
  { label: string; hint: string }
> = {
  Operations: {
    label: "Operations",
    hint: "Horizontal capabilities used across industries — stock, manufacturing, purchases, POS, eCommerce, weighbridge",
  },
  HR: {
    label: "HR & Payroll",
    hint: "Employees, attendance, leave, expense claims, and pay runs",
  },
  Industry: {
    label: "Business nature",
    hint: "Full industry verticals — mill, hospital, telecom franchise, textile processing",
  },
  Localization: {
    label: "Country & statutory",
    hint: "Tax and e-invoice packs by jurisdiction (Pakistan FBR, UAE, KSA, India, EU Peppol, UK MTD, Malaysia MyInvois)",
  },
  Intelligence: {
    label: "Intelligence",
    hint: "Ask your books in plain language",
  },
}

export const ADDON_PACK_GROUPS: {
  id: AddonPackGroup
  label: string
  hint: string
}[] = [
  {
    id: "industry",
    label: "Business nature",
    hint: "Industry verticals — trader, mill, hospital, telecom, textile processing",
  },
  {
    id: "localization",
    label: "Country & statutory",
    hint: "Tax and e-invoice packs by jurisdiction — install beside any business nature",
  },
  {
    id: "intelligence",
    label: "Intelligence",
    hint: "Ask your books in plain language",
  },
]

export const ADDON_PACKS: AddonPack[] = [
  {
    id: "trader",
    label: "Trader",
    tagline: "Buy & resell",
    group: "industry",
    modules: ["inventory", "pos"],
    features: ["Products & stock", "Point of Sale register", "Inventory performance", "Weighbridge tickets available in Optional / Marketplace"],
  },
  {
    id: "manufacturing",
    label: "Manufacturing",
    tagline: "Value-addition",
    group: "industry",
    modules: ["inventory", "production", "purchase_store", "weaving", "weighbridge"],
    features: ["BoM & production orders", "Purchases & Store", "Weaving unit control", "Weighbridge tickets"],
  },
  {
    id: "yarn_spinning",
    label: "Yarn Spinning",
    tagline: "Spinning mill",
    group: "industry",
    modules: ["inventory", "purchase_store", "spinning", "weighbridge"],
    features: ["Bale receipt & lots", "Multi-stage tracking", "Cone output & GL costing", "Weighbridge tickets"],
  },
  {
    id: "textile_processing",
    label: "Textile Processing",
    tagline: "Printing / ballor unit",
    group: "industry",
    modules: ["inventory", "purchase_store", "textile_processing"],
    features: ["Grey lots & mending", "PPC stages & wastage", "Process billing & grey credit"],
  },
  {
    id: "healthcare",
    label: "Healthcare",
    tagline: "Hospital & clinic",
    group: "industry",
    modules: ["hrm", "inventory", "healthcare"],
    features: ["OPD / IPD", "Lab, pharmacy & dialysis", "Payroll"],
  },
  {
    id: "telecom",
    label: "Telecom Franchise",
    tagline: "Operator franchise",
    group: "industry",
    modules: ["inventory", "telecom"],
    features: ["Tracker wallet", "RSO channel", "FCA & commissions"],
  },
  {
    id: "pra",
    label: "FBR Digital Invoicing",
    tagline: "Pakistan",
    group: "localization",
    modules: ["inventory", "pos", "pra"],
    features: ["FBR invoice number + QR", "POS counter sales", "FBR DI / PRA Sales home"],
  },
  {
    id: "uae_vat",
    label: "UAE VAT e-Invoice",
    tagline: "United Arab Emirates",
    group: "localization",
    modules: ["uae_vat"],
    features: ["5% VAT tax codes", "UAE Sales dashboard", "Sandbox FTA logs"],
  },
  {
    id: "sa_zatca",
    label: "Saudi ZATCA e-Invoice",
    tagline: "Saudi Arabia",
    group: "localization",
    modules: ["sa_zatca"],
    features: ["Phase 2 sandbox clear/report", "ZATCA Sales dashboard", "TLV QR + logs"],
  },
  {
    id: "in_gst",
    label: "India GST",
    tagline: "India",
    group: "localization",
    modules: ["in_gst"],
    features: ["CGST/SGST/IGST split", "GST Sales dashboard", "GSTR-1 summary export"],
  },
  {
    id: "eu_peppol",
    label: "Peppol / EU VAT e-Invoice",
    tagline: "European Union",
    group: "localization",
    modules: ["eu_peppol"],
    features: ["BIS Billing 3.0 UBL", "Peppol Sales dashboard", "Access Point logs"],
  },
  {
    id: "uk_mtd",
    label: "UK MTD VAT",
    tagline: "United Kingdom",
    group: "localization",
    modules: ["uk_mtd"],
    features: ["VAT return boxes 1–9", "HMRC sandbox submit", "Obligation logs"],
  },
  {
    id: "my_invois",
    label: "Malaysia MyInvois",
    tagline: "Malaysia",
    group: "localization",
    modules: ["my_invois"],
    features: ["LHDN sandbox submit", "UUID tracking", "Submission logs"],
  },
  {
    id: "ai",
    label: "AI Assistant",
    tagline: "Ask your books",
    group: "intelligence",
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

export { HOME_PREF_KEY } from "@/lib/dashboardHome"
