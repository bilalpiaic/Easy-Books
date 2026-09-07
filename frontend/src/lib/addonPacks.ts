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
    modules: ["inventory", "pos"],
    features: ["Products & stock", "Point of Sale register", "Inventory performance", "Weighbridge tickets available in Optional / Marketplace"],
  },
  {
    id: "manufacturing",
    label: "Manufacturing",
    tagline: "Value-addition",
    modules: ["inventory", "production", "purchase_store", "weaving", "weighbridge"],
    features: ["BoM & production orders", "Purchases & Store", "Weaving unit control", "Weighbridge tickets"],
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
    modules: ["inventory", "pos", "pra"],
    features: ["Fiscal invoice numbers", "POS counter sales", "PRA Sales home dashboard"],
  },
  {
    id: "uae_vat",
    label: "UAE VAT e-Invoice",
    tagline: "UAE localization",
    modules: ["uae_vat"],
    features: ["5% VAT tax codes", "UAE Sales dashboard", "Sandbox FTA logs"],
  },
  {
    id: "sa_zatca",
    label: "Saudi ZATCA e-Invoice",
    tagline: "KSA localization",
    modules: ["sa_zatca"],
    features: ["Phase 2 sandbox clear/report", "ZATCA Sales dashboard", "TLV QR + logs"],
  },
  {
    id: "in_gst",
    label: "India GST",
    tagline: "India localization",
    modules: ["in_gst"],
    features: ["CGST/SGST/IGST split", "GST Sales dashboard", "GSTR-1 summary export"],
  },
  {
    id: "eu_peppol",
    label: "Peppol / EU VAT e-Invoice",
    tagline: "EU localization",
    modules: ["eu_peppol"],
    features: ["BIS Billing 3.0 UBL", "Peppol Sales dashboard", "Access Point logs"],
  },
  {
    id: "yarn_spinning",
    label: "Yarn Spinning",
    tagline: "Spinning mill",
    modules: ["inventory", "purchase_store", "spinning", "weighbridge"],
    features: ["Bale receipt & lots", "Multi-stage tracking", "Cone output & GL costing", "Weighbridge tickets"],
  },
  {
    id: "textile_processing",
    label: "Textile Processing",
    tagline: "Printing / ballor unit",
    modules: ["inventory", "purchase_store", "textile_processing"],
    features: ["Grey lots & mending", "PPC stages & wastage", "Process billing & grey credit"],
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

export { HOME_PREF_KEY } from "@/lib/dashboardHome"
