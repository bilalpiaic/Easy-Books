/** Dual-home dashboard: Financial vs Operations (purpose / production). */

export type DashboardView = "financial" | "operations"

export type HomePreference = DashboardView | "pra" | "accounting"

/** Modules that light the Operations home tab (HRM alone is not enough). */
export const PURPOSE_MODULES = [
  "production",
  "spinning",
  "weaving",
  "weighbridge",
  "textile_processing",
  "healthcare",
  "telecom",
  "purchase_store",
] as const

/** Business models that land on Operations by default (first visit). */
export const OPS_DEFAULT_MODELS = new Set([
  "manufacturing",
  "yarn_spinning",
  "textile_processing",
  "hospital",
  "telecom_franchise",
])

export const HOME_PREF_KEY = "eb.home_dashboard"

export function hasOperationsHome(installedModules: Set<string>): boolean {
  return PURPOSE_MODULES.some(m => installedModules.has(m))
}

export function defaultViewForModel(businessModel: string | undefined): DashboardView {
  if (businessModel && OPS_DEFAULT_MODELS.has(businessModel)) return "operations"
  return "financial"
}

/** Human label for the Operations home subtitle. */
export function operationsSubtitle(
  installedModules: Set<string>,
  businessModel?: string,
): string {
  if (installedModules.has("spinning") || businessModel === "yarn_spinning") {
    return "Spinning Operations"
  }
  if (installedModules.has("textile_processing") || businessModel === "textile_processing") {
    return "Processing Operations"
  }
  if (installedModules.has("healthcare") || businessModel === "hospital") {
    return "Healthcare Operations"
  }
  if (installedModules.has("telecom") || businessModel === "telecom_franchise") {
    return "Telecom Operations"
  }
  if (installedModules.has("weaving") && installedModules.has("production")) {
    return "Manufacturing & Weaving"
  }
  if (installedModules.has("production") || businessModel === "manufacturing") {
    return "Manufacturing Operations"
  }
  if (installedModules.has("weaving")) return "Weaving Operations"
  if (installedModules.has("purchase_store")) return "Purchases & Store"
  return "Operations Overview"
}

export const DEFAULT_FINANCIAL_QUICK_ACTIONS = [
  "new_invoice", "new_bill", "new_entry", "products", "workflow", "guide",
]

export const DEFAULT_OPS_QUICK_ACTIONS = [
  "new_demand",
  "new_po",
  "new_spin_lot",
  "new_weighbridge_ticket",
  "new_grey_lot",
  "new_opd",
  "telecom_tracker",
  "new_production",
  "gate_inward",
  "attendance",
  "products",
]
