/**
 * In-app visual catalog of every tenant, nav segment, workflow, report, and
 * screen. Settings → Catalog renders this list with captured snapshots.
 */
import { NAV, TOP_NAV, type NavItem } from "@/lib/nav"

export type CatalogKind = "tenant" | "segment" | "workflow" | "report" | "screen"

export type DemoTenantKey =
  | "simple"
  | "services"
  | "trader"
  | "manufacturing"
  | "telecom"
  | "pra"
  | "hospital"
  | "spinning"
  | "processing"

export const DEMO_TENANTS: Record<DemoTenantKey, {
  label: string
  email: string
  model: string
  modules: string[]
}> = {
  simple:         { label: "Simple",              email: "demo.simple@easy-books.app",         model: "simple",              modules: ["base"] },
  services:       { label: "Services",            email: "demo.services@easy-books.app",       model: "services",            modules: ["base"] },
  trader:         { label: "Trader",              email: "demo.trader@easy-books.app",         model: "trader",              modules: ["base", "inventory", "pos"] },
  manufacturing:  { label: "Manufacturing",       email: "demo.manufacturing@easy-books.app",  model: "manufacturing",       modules: ["base", "inventory", "production", "purchase_store", "weaving", "weighbridge"] },
  telecom:        { label: "Telecom Franchise",   email: "demo.telecom@easy-books.app",        model: "telecom_franchise",   modules: ["base", "inventory", "telecom"] },
  pra:            { label: "PRA e-Invoice",       email: "demo.pra@easy-books.app",            model: "pra_einvoice",        modules: ["base", "pra"] },
  hospital:       { label: "Hospital",            email: "demo.hospital@easy-books.app",       model: "hospital",            modules: ["base", "hrm", "inventory", "healthcare"] },
  spinning:       { label: "Yarn Spinning",       email: "demo.spinning@easy-books.app",       model: "yarn_spinning",       modules: ["base", "inventory", "purchase_store", "spinning", "weighbridge"] },
  processing:     { label: "Textile Processing",  email: "demo.processing@easy-books.app",     model: "textile_processing",  modules: ["base", "inventory", "purchase_store", "textile_processing"] },
}

export const CATALOG_KINDS: { id: CatalogKind | "all"; label: string }[] = [
  { id: "all",      label: "All" },
  { id: "tenant",   label: "Tenants" },
  { id: "segment",  label: "Segments" },
  { id: "workflow", label: "Workflows" },
  { id: "report",   label: "Reports" },
  { id: "screen",   label: "Screens" },
]

export interface CatalogEntry {
  id: string
  title: string
  kind: CatalogKind
  href: string
  explanation: string
  steps?: string[]
  gl?: string
  tags: string[]
  tenants: DemoTenantKey[]
  modules: string[]
  segment: string
  /** Demo tenant used when capturing the snapshot. */
  captureTenant: DemoTenantKey | "anon"
  capturePath?: string
}

export function catalogScreenshot(entry: CatalogEntry | string): string {
  if (typeof entry === "string") return `/catalog/${entry}.jpg`
  return `/catalog/${shotKey(entry)}.jpg`
}

export function shotKey(entry: CatalogEntry): string {
  const path = entry.capturePath ?? entry.href
  return `${entry.captureTenant}--${slugHref(path)}`
}

export function slugHref(href: string): string {
  return href.replace(/^\//, "").replace(/[/?=&]/g, "-").replace(/-+/g, "-").replace(/-$/, "") || "home"
}

function tenantForModule(mod?: string): DemoTenantKey {
  switch (mod) {
    case "healthcare":
    case "hrm":                 return "hospital"
    case "telecom":             return "telecom"
    case "pra":                 return "pra"
    case "spinning":            return "spinning"
    case "weaving":
    case "weighbridge":
    case "production":
    case "purchase_store":
    case "sa_zatca":            return "manufacturing"
    case "textile_processing":  return "processing"
    case "inventory":
    case "pos":
    case "ecommerce":
    case "in_gst":              return "trader"
    case "eu_peppol":
    case "uae_vat":             return "services"
    case "ai_assistant":        return "services"
    default:                    return "services"
  }
}

function tenantsForModules(mods: string[]): DemoTenantKey[] {
  const keys = new Set<DemoTenantKey>()
  if (mods.length === 0 || mods.includes("base")) {
    (Object.keys(DEMO_TENANTS) as DemoTenantKey[]).forEach(k => keys.add(k))
  }
  for (const [key, t] of Object.entries(DEMO_TENANTS) as [DemoTenantKey, typeof DEMO_TENANTS[DemoTenantKey]][]) {
    if (mods.some(m => m !== "base" && t.modules.includes(m))) keys.add(key)
  }
  if (keys.size === 0) return Object.keys(DEMO_TENANTS) as DemoTenantKey[]
  return [...keys]
}

function navModules(item: NavItem): string[] {
  if (item.forModule) return [item.forModule]
  if (item.forAnyModule?.length) return [...item.forAnyModule]
  return ["base"]
}

function isReportNav(item: NavItem): boolean {
  const h = item.href.toLowerCase()
  const l = item.label.toLowerCase()
  if (item.section === "Reports") return true
  if (h.includes("/reports") || h.includes("register") || h.includes("aging")) return true
  if (l.includes("report") || l.includes("register") || l.includes("recon") || l.includes("kpi") || l.includes("performance") || l.includes("tie-out") || l.includes("3-way") || l.includes("match") || l.includes("dashboard") && item.section !== "Overview") return true
  return false
}

// ── Tenants ──────────────────────────────────────────────────────────────────

const TENANT_ENTRIES: CatalogEntry[] = [
  {
    id: "tenant-simple", kind: "tenant", title: "Simple company", href: "/dashboard",
    captureTenant: "simple", segment: "Overview", modules: ["base"], tenants: ["simple"],
    tags: ["tenant", "ledger", "sales", "banking"],
    explanation: "Solo and micro-businesses. Base accounting only: invoices, bills, journal, bank, and the core financial statements. No inventory or industry packs — the cleanest place to learn the double-entry loop.",
    steps: ["Sign in as demo.simple@easy-books.app (password demo1234).", "Confirm company name and currency in Settings → Company.", "Raise a sales invoice, collect a receipt, then open Trial Balance."],
  },
  {
    id: "tenant-services", kind: "tenant", title: "Services firm", href: "/dashboard",
    captureTenant: "services", segment: "Overview", modules: ["base"], tenants: ["services"],
    tags: ["tenant", "ifrs", "sales", "ledger"],
    explanation: "Consulting and agencies. Same base books plus deferred-revenue origination (IFRS 15): mark a product deferred and the invoice credits Unearned Revenue 2300 instead of 4100, with a recognition schedule you post over the contract life. Peppol EU e-invoice is seeded on this demo.",
    steps: ["Open Products and find a deferred item.", "Invoice it — GL credits 2300 Deferred Revenue, not sales.", "Run Deferred Revenue and recognise a month."],
    gl: "Dr 1100 AR / Cr 2300 Deferred Revenue on issue; later Dr 2300 / Cr 4100 as revenue is earned.",
  },
  {
    id: "tenant-trader", kind: "tenant", title: "Trader (buy & resell)", href: "/dashboard",
    captureTenant: "trader", segment: "Overview", modules: ["base", "inventory", "pos"], tenants: ["trader"],
    tags: ["tenant", "inventory", "pos", "purchases", "tax"],
    explanation: "Wholesale/retail trading. Inventory + POS are pre-installed: product catalog, stock ledger, valuation, and a counter register. India GST (GSTR) is seeded so tax reports have live CGST/SGST/IGST figures.",
    steps: ["Create or open a stock product.", "Buy via a bill (Dr Inventory / Cr AP).", "Sell on an invoice or the POS register (COGS + stock relief)."],
    gl: "Purchase Dr 1200 Inventory / Cr 2000 AP. Sale Dr 1100 AR / Cr 4100 Sales and Dr 5010 COGS / Cr 1200 Inventory.",
  },
  {
    id: "tenant-manufacturing", kind: "tenant", title: "Manufacturing mill", href: "/dashboard/operations",
    captureTenant: "manufacturing", segment: "Overview", modules: ["base", "inventory", "production", "purchase_store", "weaving", "weighbridge"],
    tenants: ["manufacturing"], tags: ["tenant", "manufacturing", "weaving", "weighbridge", "purchases", "inventory"],
    explanation: "Value-add mill. Production floor (BoM, rate plans, work orders), the full purchase/store chain (demand → comparative → PO → gate inward/outward → store issue), weaving unit-control, and Marketplace Weighbridge. ZATCA is seeded for KSA e-invoicing.",
    steps: ["Start on the Operations home — mill KPIs live here.", "Walk Purchases: an approved demand, a comparative, then a PO.", "Open Weaving and Weighbridge from the top nav."],
  },
  {
    id: "tenant-telecom", kind: "tenant", title: "Telecom franchise", href: "/telecom",
    captureTenant: "telecom", segment: "Telecom", modules: ["base", "inventory", "telecom"], tenants: ["telecom"],
    tags: ["tenant", "telecom", "inventory", "sales"],
    explanation: "Mobile-operator franchise books. Tracker deposit and load float, RSO channel, SIM activations, FCA targets, mobile money, postpaid, commissions, and IMEI devices sit on a 56-account franchise CoA (1210 Tracker Deposit, 1211 Load Float, and the commission/royalty pair).",
    steps: ["Open Telecom Overview for float and activation KPIs.", "Load the tracker wallet, then issue to an RSO.", "Post a commission run from Telecom → Commissions."],
    gl: "Load purchase Dr 1211 Load Float / Cr 2000 AP. Retail sale Dr 1100 AR / Cr load-revenue; tracker movements stay on 1210.",
  },
  {
    id: "tenant-pra", kind: "tenant", title: "PRA e-Invoice retailer", href: "/pra-dashboard",
    captureTenant: "pra", segment: "PRA", modules: ["base", "pra"], tenants: ["pra"],
    tags: ["tenant", "compliance", "tax", "sales"],
    explanation: "Pakistani retail with Punjab Revenue Authority sandbox e-invoicing. Every posted invoice can be submitted; PRA Logs keep the success/retry trail. Currency is PKR and the PRA home is the default operations landing.",
    steps: ["Post a sales invoice.", "Open PRA Dashboard to see submission status.", "Drill into PRA Logs for the sandbox payload trail."],
  },
  {
    id: "tenant-hospital", kind: "tenant", title: "Hospital / healthcare", href: "/healthcare",
    captureTenant: "hospital", segment: "Healthcare", modules: ["base", "hrm", "inventory", "healthcare"], tenants: ["hospital"],
    tags: ["tenant", "healthcare", "payroll", "inventory", "sales"],
    explanation: "Hospital pack: patients (auto-linked customers), doctors, OPD tokens/visits, IPD admissions with deposit + discharge invoice, lab orders, procedures, pharmacy dispense, plus HRM payroll and attendance. OPD visits bill Dr 1100 / Cr 4100 immediately; IPD charges accumulate until discharge.",
    steps: ["Register or open a patient — a Customer is created automatically.", "Issue an OPD token, record the visit (invoice posts).", "Admit to a ward, add charges, discharge to a consolidated invoice."],
    gl: "OPD: Dr 1100 AR / Cr 4100–4121 service revenue. Discharge consolidates IPD charges + settles the admission deposit.",
  },
  {
    id: "tenant-spinning", kind: "tenant", title: "Yarn spinning mill", href: "/spinning",
    captureTenant: "spinning", segment: "Spinning", modules: ["base", "inventory", "purchase_store", "spinning", "weighbridge"],
    tenants: ["spinning"], tags: ["tenant", "spinning", "weighbridge", "purchases", "gl", "manufacturing"],
    explanation: "Cotton-to-yarn mill with full GL from day one. Bale receipt → multi-stage lots (blowroom/card/draw/ring) → cone output → waste log → yarn dispatch. CoA extras 1200–1204 (RM/WIP/FG) and 5901–5904 waste. Weighbridge is pre-granted.",
    steps: ["Receive bales (Dr 1200 Raw Cotton).", "Open a spin lot and post stage entries (WIP 1201–1203).", "Record cone output (Dr 1204 FG) and dispatch."],
    gl: "All spinning writes go through spinning_posting → posting.py. Waste hits 5901–5904; COGS 5010 on dispatch.",
  },
  {
    id: "tenant-processing", kind: "tenant", title: "Textile processing unit", href: "/processing",
    captureTenant: "processing", segment: "Processing", modules: ["base", "inventory", "purchase_store", "textile_processing"],
    tenants: ["processing"], tags: ["tenant", "processing", "inventory", "purchases"],
    explanation: "Grey-in / process / packed-out mill. Sales orders, grey inward lots, mending, kachi/pakki parchi, rejection outward, PPC stages, fresh dispatch, labor bills, grey settlement, and inspections. Customer-owned grey is custody stock until processed.",
    steps: ["Create a sales order, then grey-in a lot against it.", "Move the lot through PPC stages.", "Issue pakki parchi and dispatch; settle leftover grey."],
  },
]

// ── Segments ─────────────────────────────────────────────────────────────────

const SEGMENT_COPY: Record<string, { title: string; explanation: string; tags: string[]; href: string; captureTenant: DemoTenantKey }> = {
  dashboard:     { title: "Dashboard",     href: "/dashboard",         captureTenant: "services",      tags: ["ledger", "workflow"], explanation: "Dual-home landing. Financial shows AR/AP/cash KPIs and the widget grid; Operations (when an industry pack is installed) shows mill/hospital/franchise activity. Layout is per-user JSON (v4) with Financial and Operations slices." },
  accounting:    { title: "Accounting",    href: "/entry",             captureTenant: "services",      tags: ["ledger", "gl", "workflow"], explanation: "Manual vouchers (JV / payment / receipt), journal list, recurring entries, general ledger, chart of accounts, analytic dimensions, period close, deferred revenue, assets, and leases. This is the bookkeeping spine every tenant shares." },
  reports:       { title: "Reports",       href: "/trial-balance",     captureTenant: "services",      tags: ["reports", "ifrs", "tax"], explanation: "Statutory pack: hierarchical trial balance, P&L, dimensional P&L, balance sheet (with RE-CUR), consolidation, intercompany recon, cash flow, tax/WHT/CIT, budgets, assets, leases, period close, and the ad-hoc Report Builder." },
  banking:       { title: "Banking",       href: "/banking",           captureTenant: "services",      tags: ["banking", "ledger"], explanation: "Bank accounts, cash book, bank book, statement imports, feeds, matching rules, exchange rates, and reconciliations. Imports never post — you match lines to existing receipts/payments, then close the recon." },
  sales:         { title: "Sales",         href: "/receivable",        captureTenant: "services",      tags: ["sales", "ledger"], explanation: "AR hub: invoices, credit notes, customers, receipts, advances, commissions, promo discounts, and AR aging. Every invoice posts Dr AR / Cr revenue (or deferred revenue) in one balanced voucher." },
  purchases:     { title: "Purchases",     href: "/purchases",         captureTenant: "manufacturing", tags: ["purchases", "inventory"], explanation: "AP plus the purchase-store chain when that module is on: demands (qty only), vendor quotations, comparative statement, PO, gate inward, 3-way match, and vendor performance. Bare POs are blocked while require_purchase_chain is on." },
  store:         { title: "Store",         href: "/store/gate-outward", captureTenant: "manufacturing", tags: ["inventory", "purchases", "gl"], explanation: "Dispatch and consumption. Gate outward is the exit memo (scrap posts GL on approve). Store issues debit a picked expense account and credit inventory immediately — no draft gate." },
  weighbridge:   { title: "Weighbridge",   href: "/weighbridge",       captureTenant: "manufacturing", tags: ["weighbridge", "manufacturing"], explanation: "Mill scale tickets (first/second weigh, tare/gross/net kg). v1 is memo/ops — no GL. Completed inbound tickets can copy the gate-pass number onto a linked invoice’s Studio field." },
  spinning:      { title: "Spinning",      href: "/spinning",          captureTenant: "spinning",      tags: ["spinning", "gl", "manufacturing"], explanation: "Yarn mill workspace: setup masters, production plans, lots, bale receipts, stage entries, cone output, waste, dispatch, yield calculator, and lot/waste registers. Every quantity move posts GL." },
  weaving:       { title: "Weaving",       href: "/weaving",           captureTenant: "manufacturing", tags: ["weaving", "manufacturing"], explanation: "Unit-control weaving (memo, no GL in v1): fabric qualities, looms, yarn types, contracts with embedded rates, yarn inward, sizing, production, dispatch, and daily/contract KPI reports. Weights in kg with lb/bag derived." },
  processing:    { title: "Processing",    href: "/processing",        captureTenant: "processing",    tags: ["processing", "inventory"], explanation: "Textile processing floor: grey inward through PPC stages to packed dispatch, plus labor bills and grey settlement against customer-owned stock." },
  pos:           { title: "POS",           href: "/pos",               captureTenant: "trader",        tags: ["pos", "sales", "inventory"], explanation: "Counter register and cashier shifts. Sales post the same AR/revenue/COGS as an invoice, with shift open/close and till variance." },
  ecommerce:     { title: "eCommerce",     href: "/ecommerce",         captureTenant: "trader",        tags: ["ecommerce", "sales"], explanation: "Store connectors (Shopify / Woo / Daraz-style). Pulled orders land as drafts you post into the same invoice pipeline — they never bypass GL." },
  manufacturing: { title: "Manufacturing", href: "/manufacturing",     captureTenant: "manufacturing", tags: ["manufacturing", "inventory", "gl"], explanation: "Production floor: BoMs, rate plans, work orders, scrap reasons, stock locations, and manufacturing reports (WIP, custody). Purchase orders/GRN dual-home here unless purchase_store is installed." },
  inventory:     { title: "Inventory",     href: "/inventory",         captureTenant: "trader",        tags: ["inventory", "gl"], explanation: "Products (list + category tree), product ledger with location, valuation, performance, warehouse transfers, pick/pack, and stock-by-warehouse. Negative stock can be blocked in Settings." },
  payroll:       { title: "Payroll",       href: "/hrm",               captureTenant: "hospital",      tags: ["payroll", "gl"], explanation: "Employees, salary structures, component catalog, attendance/leave, expense claims, and payroll runs (draft → approve → post GL → void). Posting is Dr Salary Expense / Cr Salaries Payable." },
  healthcare:    { title: "Healthcare",    href: "/healthcare",        captureTenant: "hospital",      tags: ["healthcare", "sales"], explanation: "Patients, doctors, OPD, IPD/wards, laboratory, procedures, dialysis, hospital store, and seven healthcare reports. Patients are customers; visits and discharges create real AR invoices." },
  telecom:       { title: "Telecom",       href: "/telecom",           captureTenant: "telecom",       tags: ["telecom", "inventory"], explanation: "Franchise operating loop: tracker/load, RSO, SIM, FCA, mobile money, postpaid, commissions, franchise admin, IMEI devices." },
  pra:           { title: "PRA e-Invoice", href: "/pra-dashboard",     captureTenant: "pra",           tags: ["compliance", "tax"], explanation: "Punjab Revenue Authority sandbox dashboard and submission logs. Posted invoices can be sent; failures retry without rewriting the GL." },
  uae:           { title: "UAE VAT",       href: "/uae",               captureTenant: "services",      tags: ["compliance", "tax", "localization"], explanation: "UAE VAT e-invoice dashboard and logs. Install the uae_vat pack from Add-ons to light this segment." },
  zatca:         { title: "ZATCA",         href: "/zatca",             captureTenant: "manufacturing", tags: ["compliance", "tax", "localization"], explanation: "Saudi Fatoora (ZATCA) clear/report dashboard and logs. Seeded on the manufacturing demo." },
  peppol:        { title: "Peppol",        href: "/peppol",            captureTenant: "services",      tags: ["compliance", "tax", "localization"], explanation: "EU Peppol Access Point send dashboard and logs. Seeded on the services demo." },
  india_gst:     { title: "India GST",     href: "/india-gst",         captureTenant: "trader",        tags: ["compliance", "tax", "localization"], explanation: "GSTR home and GSTR-1 style report (CGST/SGST/IGST). Seeded on the trader demo." },
  system:        { title: "System",        href: "/settings",          captureTenant: "services",      tags: ["settings", "approvals", "ai"], explanation: "Settings (including this Catalog), Studio custom fields, team, permissions, approvals, audit, CSV import, payment terms, tax codes, workflow/user guides, Add-ons, and the AI assistant." },
}

const SEGMENT_ENTRIES: CatalogEntry[] = TOP_NAV.map(sec => {
  const copy = SEGMENT_COPY[sec.key]
  return {
    id: `segment-${sec.key}`,
    title: copy?.title ?? sec.label,
    kind: "segment" as const,
    href: copy?.href ?? "/dashboard",
    explanation: copy?.explanation ?? `${sec.label} navigation segment.`,
    tags: copy?.tags ?? ["workflow"],
    tenants: tenantsForModules(sec.forModule ? [sec.forModule] : ["base"]),
    modules: sec.forModule ? [sec.forModule] : ["base"],
    segment: sec.label,
    captureTenant: copy?.captureTenant ?? "services",
    capturePath: copy?.href,
  }
})

// ── Workflows ────────────────────────────────────────────────────────────────

const WORKFLOW_ENTRIES: CatalogEntry[] = [
  {
    id: "wf-sales-cycle", kind: "workflow", title: "Sales cycle", href: "/invoices",
    captureTenant: "services", segment: "Sales", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["sales", "workflow", "gl", "ledger"],
    explanation: "The AR loop every tenant shares. A customer invoice posts receivables and revenue in one balanced voucher. Receipts allocate to open invoices; credit notes reverse the sale without deleting history. Aging and customer statements read the same sub-ledger.",
    steps: ["Create the customer (NTN/address print on the invoice).", "New Invoice — lines, tax, due date from payment terms.", "Post: Dr 1100 AR / Cr 4100 (or 2300 if deferred).", "Collect via Payments Received; leftover sits on advances if overpaid.", "Issue a credit note for returns; it allocates against the original invoice."],
    gl: "Invoice Dr 1100 / Cr 4100 (+ tax). Receipt Dr 1010 Bank / Cr 1100. Credit note Dr 4100 / Cr 1100.",
  },
  {
    id: "wf-purchase-cycle", kind: "workflow", title: "AP bill cycle", href: "/bills",
    captureTenant: "services", segment: "Purchases", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["purchases", "workflow", "gl", "ledger"],
    explanation: "Vendor bills are the AP mirror of invoices. Stock products debit inventory; expenses debit the picked P&L account. Bill payments allocate FIFO-style to open bills. Debit notes handle purchase returns.",
    steps: ["Create the vendor.", "New Bill — expense or stock lines.", "Post: Dr expense/inventory / Cr 2000 AP.", "Pay via Bill Payments (Dr 2000 / Cr bank).", "Debit note for returns."],
    gl: "Bill Dr 5xxx or 12xx / Cr 2000. Payment Dr 2000 / Cr 1010.",
  },
  {
    id: "wf-purchase-store", kind: "workflow", title: "Demand → PO → gate inward", href: "/purchases/demands",
    captureTenant: "manufacturing", segment: "Purchases", modules: ["purchase_store"], tenants: ["manufacturing", "spinning", "processing"],
    tags: ["purchases", "workflow", "inventory"],
    explanation: "Controlled buying. A quantity-only purchase demand cannot be self-approved. Vendors quote rates against demand lines; one comparative statement per demand picks a winner (lowest total, or a written justification). Convert creates the PO. Gate inward books the vehicle/challan against remaining PO qty; convert-to-bill can require full GI coverage.",
    steps: ["Raise a Purchase Demand (qty, no rates) and send it for approval — a different user must approve.", "Enter vendor quotations against each demand line.", "Build the comparative, select a vendor, justify if not lowest, approve.", "Convert to PO (demand_id + comparative_id stamped).", "Gate inward the lorry; qty cannot exceed PO remaining.", "Convert PO to a vendor bill when GI coverage is complete."],
    gl: "Demand/quote/GI are memo until the bill posts. Bill Dr Inventory / Cr AP. GI never writes the GL.",
  },
  {
    id: "wf-store-issue", kind: "workflow", title: "Store issue & gate outward", href: "/store/issues",
    captureTenant: "manufacturing", segment: "Store", modules: ["purchase_store"], tenants: ["manufacturing", "spinning", "processing"],
    tags: ["inventory", "workflow", "gl"],
    explanation: "Consumption and dispatch. A store issue posts immediately (Dr user-picked Expense with analytic tag / Cr Inventory) and relieves stock. Gate outward is the exit memo for invoices/debit notes; scrap is draft→approve and posts GL only on approval via consume_stock.",
    steps: ["Store Issue: pick department, expense account, lines — save posts GL + stock.", "Invoice or debit note for sales/returns.", "Gate outward against that source (create = approved for invoice/DN).", "Scrap: draft GO → approve (GL + stock)."],
    gl: "Issue Dr 5xxx Expense / Cr 1200 Inventory. Scrap GO uses consume_stock(source_doc_type=gate_outward).",
  },
  {
    id: "wf-journal", kind: "workflow", title: "Journal, payment & receipt vouchers", href: "/journal/new",
    captureTenant: "services", segment: "Accounting", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["ledger", "workflow", "gl", "banking"],
    explanation: "Three-mode voucher form. Journal (JV) is a free Dr/Cr grid. Payment (CP cash / BP bank) pre-filters the instrument to cash/bank and shows a payee. Receipt (CR/BR) is the mirror. Prefixes auto-number; print templates differ (PV / RV / JV). Debits must equal credits or the API rejects the post.",
    steps: ["Open New Entry and pick Journal, Payment, or Receipt.", "Add lines — exactly one of debit or credit per line, both sides totalling equal.", "Save; the voucher appears on Journal and in the GL of every account touched."],
    gl: "Invariant: Σ debit = Σ credit. One JournalEntry row stores separate debit and credit floats; exactly one is > 0.",
  },
  {
    id: "wf-banking", kind: "workflow", title: "Bank import → match → recon", href: "/bank-imports",
    captureTenant: "services", segment: "Banking", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["banking", "workflow", "ledger"],
    explanation: "Statement lines are facts from the bank, not books. Import CSV/OFX, optionally apply Bank Rules, match each line to an existing receipt/payment/journal, then close the reconciliation. Unmatched lines stay on the open recon — they never auto-post a GL entry.",
    steps: ["Create or pick the GL bank account.", "Import a statement (Bank Imports) or pull a feed.", "Match lines; rules can auto-suggest.", "Open Reconciliations and close when the difference is zero."],
  },
  {
    id: "wf-payroll", kind: "workflow", title: "Payroll run", href: "/payroll",
    captureTenant: "hospital", segment: "Payroll", modules: ["hrm"], tenants: ["hospital"],
    tags: ["payroll", "workflow", "gl"],
    explanation: "Employees carry a salary structure of catalog components. A payroll run drafts lines from those structures (attendance can drive LOP), then approve → post GL → payslips. Voiding reverses the voucher. Biometric attendance cannot be deleted.",
    steps: ["Add salary components, then an employee with a structure.", "Record attendance for the month.", "New Payroll Run — review lines, approve, post.", "Print payslips; void only if you need to reverse the GL."],
    gl: "Dr Salary Expense / Cr Salaries Payable (PR-YYYY-seq). Payment of net pay is a later CP/BP voucher.",
  },
  {
    id: "wf-healthcare-opd", kind: "workflow", title: "OPD visit → invoice", href: "/healthcare/opd",
    captureTenant: "hospital", segment: "Healthcare", modules: ["healthcare"], tenants: ["hospital"],
    tags: ["healthcare", "workflow", "sales", "gl"],
    explanation: "Walk-in clinic loop. Patient (MR-YYYYNNNN) is auto-linked to a Customer. An OPD token queues the visit; recording the visit bills immediately (Dr 1100 / Cr 4100). Prescriptions and lab orders hang off the visit.",
    steps: ["Register the patient.", "Issue an OPD token.", "Record the visit — invoice posts.", "Optionally prescribe or send a lab order."],
    gl: "Dr 1100 AR / Cr 4100 (consultation). No draft — recording the visit is the post.",
  },
  {
    id: "wf-healthcare-ipd", kind: "workflow", title: "IPD admission → discharge", href: "/healthcare/ipd",
    captureTenant: "hospital", segment: "Healthcare", modules: ["healthcare"], tenants: ["hospital"],
    tags: ["healthcare", "workflow", "sales", "gl"],
    explanation: "Inpatient loop. Admission (ADM-YYYYNNNN) takes a deposit and occupies a bed. Charges accumulate with no per-line GL. Discharge builds one invoice for all charges and settles the deposit against it.",
    steps: ["Admit the patient to a ward/bed (status → occupied).", "Post charges during the stay (memo until discharge).", "Discharge — consolidated invoice + deposit settlement.", "Bed returns to available."],
    gl: "Deposit is a liability until discharge. Discharge Dr AR / Cr 4100–4121 and applies the deposit.",
  },
  {
    id: "wf-healthcare-lab", kind: "workflow", title: "Lab order → collect → result", href: "/healthcare/lab",
    captureTenant: "hospital", segment: "Healthcare", modules: ["healthcare"], tenants: ["hospital"],
    tags: ["healthcare", "workflow"],
    explanation: "Lab orders (LO-YYYYNNNN) pick tests from the catalogue. Collect the sample, enter results (unit/range default from the catalogue), then deliver. Pharmacy dispense is a separate store queue.",
    steps: ["Create a lab order on the patient/visit.", "Collect (sample collection row).", "Enter results per test.", "Deliver; bill follows the visit/admission rules."],
  },
  {
    id: "wf-manufacturing", kind: "workflow", title: "BoM → work order → stock", href: "/manufacturing/production-orders",
    captureTenant: "manufacturing", segment: "Manufacturing", modules: ["production"], tenants: ["manufacturing"],
    tags: ["manufacturing", "workflow", "inventory", "gl"],
    explanation: "Build-to-stock/order. A BoM lists components and a finished item. A production order consumes components (and optional scrap reason) and receipts the finished good into a stock location. Rate plans price the job.",
    steps: ["Define stock locations (MAIN / GODOWN / WIP are seeded).", "Build the BoM.", "Raise a production order, issue components, complete output.", "Review Mfg Reports for WIP and custody."],
    gl: "Issue Dr WIP / Cr RM. Complete Dr FG / Cr WIP. Scrap follows the scrap-reason account.",
  },
  {
    id: "wf-weaving", kind: "workflow", title: "Weaving contract → dispatch", href: "/weaving/contracts",
    captureTenant: "manufacturing", segment: "Weaving", modules: ["weaving"], tenants: ["manufacturing"],
    tags: ["weaving", "workflow", "manufacturing"],
    explanation: "Memo/ops weaving (no GL in v1). A contract embeds quality, construction, and rates. Yarn inward (kg, with lb/bag derived) feeds sizing, then loom production by shift/operator, then dispatch against the contract. Daily ops and contract-control reports keep the mill honest.",
    steps: ["Setup: qualities, looms, yarn types, shifts, operators.", "Open a contract with rate/costing.", "Yarn inward → sizing → production → dispatch.", "Read Daily Ops and Contract Control."],
  },
  {
    id: "wf-spinning", kind: "workflow", title: "Bale → lot → cone → dispatch", href: "/spinning/lots",
    captureTenant: "spinning", segment: "Spinning", modules: ["spinning"], tenants: ["spinning"],
    tags: ["spinning", "workflow", "gl", "manufacturing"],
    explanation: "Full-GL spinning. Bales debit raw cotton. A spin lot is planned against a recipe; stage entries move kg through WIP accounts; cone output lands finished yarn; waste logs hit 5901–5904; dispatch relieves FG and books COGS. Yield calculator is the what-if twin of the lot.",
    steps: ["Receive bales.", "Create a production plan and spin lot.", "Post stage entries, cone output, and waste.", "Dispatch yarn; check Daily Register and Lot Control."],
    gl: "1200 RM → 1201–1203 WIP → 1204 FG. Waste 5901–5904. Dispatch Dr 5010 COGS / Cr 1204.",
  },
  {
    id: "wf-processing", kind: "workflow", title: "Grey inward → packed dispatch", href: "/processing/lots",
    captureTenant: "processing", segment: "Processing", modules: ["textile_processing"], tenants: ["processing"],
    tags: ["processing", "workflow", "inventory"],
    explanation: "Customer grey is taken in against a sales order, mended, ticketed (kachi then pakki parchi), processed through PPC stages, inspected, and dispatched. Rejections go outwards; leftover grey is settled. Labor bills capture contractor cost.",
    steps: ["Sales order → grey inward lot.", "Mending and kachi parchi.", "PPC stages; pakki parchi when packed.", "Fresh dispatch; settle leftover; bill labor."],
  },
  {
    id: "wf-weighbridge", kind: "workflow", title: "Weighbridge ticket", href: "/weighbridge/tickets/new",
    captureTenant: "manufacturing", segment: "Weighbridge", modules: ["weighbridge"], tenants: ["manufacturing", "spinning"],
    tags: ["weighbridge", "workflow", "manufacturing"],
    explanation: "Two-weigh mill ticket: first weigh (gross or tare), second weigh, net kg with lb/bag derived. Inbound completed tickets can stamp x.gate_pass_no on a linked invoice. No GL — the books move when you bill or receive against the vehicle.",
    steps: ["New ticket — vehicle, product, first weigh.", "Second weigh when the lorry returns.", "Complete; optionally copy gate pass onto the invoice.", "Review the Ticket Register."],
  },
  {
    id: "wf-telecom", kind: "workflow", title: "Tracker load → RSO → activation", href: "/telecom/tracker",
    captureTenant: "telecom", segment: "Telecom", modules: ["telecom"], tenants: ["telecom"],
    tags: ["telecom", "workflow", "inventory"],
    explanation: "Franchise float loop. Buy load onto the tracker, issue to RSOs, activate SIMs, and settle commissions/FCA. Mobile money and postpaid are parallel books on the same CoA. Devices (IMEI) are inventory.",
    steps: ["Load the tracker wallet.", "Issue to an RSO.", "Activate SIMs against that float.", "Run commissions and review FCA vs target."],
  },
  {
    id: "wf-pos", kind: "workflow", title: "POS shift & register", href: "/pos",
    captureTenant: "trader", segment: "POS", modules: ["pos"], tenants: ["trader"],
    tags: ["pos", "workflow", "sales", "inventory"],
    explanation: "Open a shift, ring up counter sales (same GL as invoices plus COGS), then close the shift and explain till variance. Receipts still allocate to the walk-in/counter customer.",
    steps: ["Open a shift (opening float).", "Sell on the register.", "Close the shift; record actual cash.", "Variance sits on the shift, not a silent GL plug."],
  },
  {
    id: "wf-deferred", kind: "workflow", title: "Deferred revenue (IFRS 15)", href: "/deferred-revenue",
    captureTenant: "services", segment: "Accounting", modules: ["base"], tenants: ["services"],
    tags: ["ifrs", "workflow", "sales", "gl"],
    explanation: "Products marked is_deferred with recognition_months credit 2300 on invoice and originate a DeferredRevenueSchedule. Edit of an unrecognised invoice rebuilds the plan; recognised months block the edit. Recognise from the Deferred Revenue screen; contract assets (1140) cover the unbilled remainder.",
    steps: ["Mark the product deferred + months.", "Invoice it (Cr 2300, schedule created).", "Recognise a period (Dr 2300 / Cr 4100).", "Review Contract Balances for asset/liability."],
    gl: "Issue Dr 1100 / Cr 2300. Recognise Dr 2300 / Cr 4100. Contract asset 1140 when performance leads billing.",
  },
  {
    id: "wf-assets", kind: "workflow", title: "Fixed assets & leases", href: "/assets",
    captureTenant: "services", segment: "Reports", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["assets", "leases", "ifrs", "workflow", "gl"],
    explanation: "Asset register with components (parent_id), depreciation, impairment, disposal, and rollforward. IFRS 16 leases (when leases_enabled) compute RoU + liability schedules and post through posting.py. Settings can hide the lease UI.",
    steps: ["Add an asset (cost, life, account).", "Run depreciation for the period.", "Impair or dispose; read the rollforward.", "Optional: new lease contract → schedule → post."],
  },
  {
    id: "wf-period-close", kind: "workflow", title: "Period close", href: "/period-close",
    captureTenant: "services", segment: "Reports", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["ledger", "workflow", "gl"],
    explanation: "Accounting periods can be locked. posting.py refuses any voucher dated in a locked period — the guard that keeps last year frozen. The only locked demo period is FY(year−3), outside the seed window, so re-seeds never trip the guard.",
    steps: ["Review Trial Balance / P&L for the month.", "Lock the period on Period Close.", "A dated-in-period invoice or JV now returns 400."],
  },
  {
    id: "wf-approvals", kind: "workflow", title: "Approval workflows", href: "/approvals/workflows",
    captureTenant: "manufacturing", segment: "System", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["approvals", "workflow", "settings"],
    explanation: "Configurable multi-step chains (role + threshold) per document type. Inbox lives at /approvals. Purchase demands and comparatives also have hardcoded self-approval blocks on top of this engine.",
    steps: ["Admin: define a workflow and steps.", "A document enters the inbox when it matches the type/threshold.", "Approvers act in order; rejection stops the chain."],
  },
  {
    id: "wf-reports", kind: "workflow", title: "Month-end report pack", href: "/trial-balance",
    captureTenant: "services", segment: "Reports", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["reports", "workflow", "ifrs", "ledger"],
    explanation: "Read the books in order: Trial Balance (tree with opening/period/closing) → Income Statement → Balance Sheet (RE-CUR synthetic equity) → Cash Flow. Comparison mode (compare_start/end) flattens to current vs prior. PrintHeader landscape is used on wide tables; dates always fmtDate (dd-mm-yy).",
    steps: ["Set the date range (presets follow fiscal_year_start and week_start_day).", "Trial Balance — drill a leaf into the GL.", "P&L then Balance Sheet; confirm net profit rolls to equity.", "Cash Flow and Tax Reports to finish the pack."],
  },
  {
    id: "wf-localization", kind: "workflow", title: "E-invoice localization packs", href: "/apps",
    captureTenant: "pra", segment: "System", modules: ["pra"], tenants: ["pra", "manufacturing", "trader", "services"],
    tags: ["compliance", "workflow", "tax", "localization"],
    explanation: "PRA (Punjab), ZATCA (KSA Fatoora), Peppol (EU), UAE VAT, and India GST are installable packs. They add a dashboard + submission log; they never rewrite posted GL. Install from Add-ons; credentials live under Settings.",
    steps: ["Add-ons → install the pack for your jurisdiction.", "Complete credentials (see User Guide for Peppol AP).", "Post an invoice, submit, watch the log.", "Failures retry; the voucher stays posted."],
  },
]

// ── Extra screens (login, settings tabs, new forms) ───────────────────────────

const EXTRA_SCREENS: CatalogEntry[] = [
  {
    id: "screen-login", kind: "screen", title: "Login", href: "/login",
    captureTenant: "anon", segment: "System", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["settings", "workflow"],
    explanation: "Email + password into a tenant. Demo companies all use password demo1234. Forgot-password always returns a generic confirmation; demo accounts never receive mail. Try demo is hidden when ALLOW_DEMO_LOGIN=false.",
    steps: ["Enter the tenant owner email.", "Password demo1234 on every seeded demo.", "Land on Financial or Operations home based on the model."],
  },
  {
    id: "screen-settings-company", kind: "screen", title: "Settings · Company", href: "/settings?tab=company",
    captureTenant: "services", capturePath: "/settings?tab=company", segment: "System", modules: ["base"],
    tenants: tenantsForModules(["base"]), tags: ["settings"],
    explanation: "Legal name, tagline, logo, address, phone, website. These print on invoices (IAS 1.49) and the header. Logo drag-and-drop uploads to /api/settings/logo.",
  },
  {
    id: "screen-settings-accounting", kind: "screen", title: "Settings · Accounting", href: "/settings?tab=accounting",
    captureTenant: "services", capturePath: "/settings?tab=accounting", segment: "System", modules: ["base"],
    tenants: tenantsForModules(["base"]), tags: ["settings", "ledger", "tax"],
    explanation: "Base currency, fiscal year start, statement date, invoice/bill prefixes, tax id, payment terms, and accounting periods (lock/unlock). week_start_day drives report presets.",
  },
  {
    id: "screen-settings-preferences", kind: "screen", title: "Settings · Preferences", href: "/settings?tab=preferences",
    captureTenant: "services", capturePath: "/settings?tab=preferences", segment: "System", modules: ["base"],
    tenants: tenantsForModules(["base"]), tags: ["settings"],
    explanation: "Theme, density, language, home dashboard (financial vs operations), negative-stock block, purchase-chain gates, leases_enabled, and notification cadence.",
  },
  {
    id: "screen-settings-advanced", kind: "screen", title: "Settings · Advanced", href: "/settings?tab=advanced",
    captureTenant: "services", capturePath: "/settings?tab=advanced", segment: "System", modules: ["base"],
    tenants: tenantsForModules(["base"]), tags: ["settings", "ai", "compliance"],
    explanation: "AI provider keys (write-only), Ollama URL/tags, rate limit, webhooks, billing, WhatsApp, appearance, demo-data seed/purge, and 2FA. Admin/owner only for secrets.",
  },
  {
    id: "screen-invoice-new", kind: "screen", title: "New invoice", href: "/invoices/new",
    captureTenant: "services", segment: "Sales", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["sales", "workflow", "gl"],
    explanation: "Full-page invoice form: customer, dates, tax, promo discounts, analytic dimensions, deferred lines, and Studio custom fields. Posting is blocked until Dr = Cr including tax.",
  },
  {
    id: "screen-bill-new", kind: "screen", title: "New bill", href: "/bills/new",
    captureTenant: "trader", segment: "Purchases", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["purchases", "workflow", "gl"],
    explanation: "Vendor bill form. Stock lines debit inventory; expense lines debit the picked P&L account. WHT fields appear when the vendor is flagged.",
  },
  {
    id: "screen-demand-new", kind: "screen", title: "New purchase demand", href: "/purchases/demands/new",
    captureTenant: "manufacturing", segment: "Purchases", modules: ["purchase_store"],
    tenants: ["manufacturing", "spinning", "processing"], tags: ["purchases", "workflow"],
    explanation: "Quantity-only requisition (PD-YYYY-seq). No rates. Creator cannot approve their own demand.",
  },
  {
    id: "screen-ops-home", kind: "screen", title: "Operations home", href: "/dashboard/operations",
    captureTenant: "manufacturing", segment: "Dashboard", modules: ["production"],
    tenants: ["manufacturing", "spinning", "processing", "hospital", "telecom", "trader"],
    tags: ["workflow", "manufacturing", "healthcare", "telecom"],
    explanation: "Purpose-built home for mill/hospital/franchise operators. Widgets and quick actions are the operations slice of the v4 layout. Staff need dashboard.operations.",
  },
  {
    id: "screen-catalog-self", kind: "screen", title: "Workflow catalog", href: "/settings/catalog",
    captureTenant: "services", segment: "System", modules: ["base"], tenants: tenantsForModules(["base"]),
    tags: ["settings", "workflow"],
    explanation: "This page. Filter by tenant, segment, tag, or kind; open a snapshot and jump to the live screen. Recapture snapshots with CAPTURE_CATALOG=1 against the demo tenants.",
  },
]

// ── Copy overlays for NAV-derived screens / reports ──────────────────────────

const SCREEN_COPY: Record<string, { explanation: string; tags: string[]; gl?: string }> = {
  "/dashboard": { tags: ["ledger"], explanation: "Financial home: KPI tiles, widget grid, setup checklist, and quick actions. Layout persists per user under Settings-backed JSON (schema v4)." },
  "/dashboard/operations": { tags: ["manufacturing", "healthcare", "telecom"], explanation: "Operations home for installed purpose modules. Defaults on for mill/hospital/franchise models." },
  "/entry": { tags: ["ledger", "gl"], explanation: "New voucher landing — same 3-mode form as Journal → New (JV / payment / receipt)." },
  "/journal": { tags: ["ledger", "gl"], explanation: "Posted voucher list. Filter by date, type prefix (JV/CP/BP/CR/BR), and amount. Open a row for the print template." },
  "/recurring": { tags: ["ledger", "gl"], explanation: "Standing journals that generate the next voucher on schedule. Pause or skip a cycle without deleting the template." },
  "/ledger": { tags: ["ledger", "reports", "gl"], explanation: "General ledger with opening and closing when a date range is set. Opening = net before start; closing follows account-type sign." },
  "/coa": { tags: ["ledger", "gl"], explanation: "Hierarchical chart of accounts. Posting is allowed only to active leaves. Groups (is_group) roll up on statements." },
  "/analytic-accounts": { tags: ["ledger", "reports"], explanation: "Up to three analytic dimensions (#260). Mark a dimension required and journal lines must carry it. Dimensional P&L slices on these." },
  "/receivable": { tags: ["sales", "reports"], explanation: "AR hub: aging bands plus top overdue customers and shortcuts into invoices, receipts, and statements." },
  "/invoices": { tags: ["sales", "gl"], explanation: "Sales invoice register. Status draft/posted/paid/overdue. Overdue sweep runs on the server (disable with OVERDUE_SWEEP_ENABLED=false)." },
  "/commissions": { tags: ["sales", "gl"], explanation: "Commission plans per user, compute for a period, approve, then post Dr Commission Expense / Cr Commissions Payable." },
  "/promo-discounts": { tags: ["sales"], explanation: "Promo rules (product, min-qty, %). Invoice form “Apply Promos” writes discount_pct and promo_rule_id; amount = qty × rate × (1 − pct/100)." },
  "/credit-notes": { tags: ["sales", "gl"], explanation: "Sales returns. Allocates against the original invoice and reverses revenue/tax/stock as needed." },
  "/customers": { tags: ["sales"], explanation: "Customer master + statement (opening, period invoices with outstanding, receipts, closing)." },
  "/payments-received": { tags: ["sales", "banking", "gl"], explanation: "AR receipts. Allocate to invoices; excess can sit as customer advances." },
  "/pos": { tags: ["pos", "sales"], explanation: "Point-of-sale register. Requires the pos module (trader demo)." },
  "/pos/shifts": { tags: ["pos", "banking"], explanation: "Cashier shifts: opening float, sales, closing count, till variance." },
  "/ecommerce": { tags: ["ecommerce", "sales"], explanation: "Connected web stores. Orders import as draft invoices you post into the GL." },
  "/advances": { tags: ["sales", "gl"], explanation: "Customer advances (unearned). Applied when the invoice is posted or via allocation." },
  "/aging/receivable": { tags: ["sales", "reports"], explanation: "AR aging buckets. Landscape print. Customer names drill into statements." },
  "/payable": { tags: ["purchases", "reports"], explanation: "AP hub: aging bands and top overdue vendors." },
  "/bills": { tags: ["purchases", "gl"], explanation: "Vendor bill register. Stock vs expense lines; WHT when the vendor is flagged." },
  "/debit-notes": { tags: ["purchases", "gl"], explanation: "Purchase returns. Reverses AP and stock/expense from the original bill." },
  "/vendors": { tags: ["purchases"], explanation: "Vendor master + AP statement (bills, payments, closing)." },
  "/bill-payments": { tags: ["purchases", "banking", "gl"], explanation: "Payments made. Allocate to open bills; WHT amount is stored on the payment." },
  "/aging/payable": { tags: ["purchases", "reports"], explanation: "AP aging. Landscape print. Vendor names drill into statements." },
  "/purchases/demands": { tags: ["purchases"], explanation: "Purchase demands (PD-YYYY-seq). Quantity-only; self-approval is blocked." },
  "/purchases/comparatives": { tags: ["purchases"], explanation: "One comparative per demand. Lowest wins unless a justification is recorded. Convert-to-PO stamps demand and comparative FKs." },
  "/purchases/gate-inward": { tags: ["purchases", "inventory"], explanation: "Memo gate entry vs remaining PO qty. Price-free PO views so a gate-only user never sees rates." },
  "/purchases/gate-register": { tags: ["purchases", "reports"], explanation: "Searchable inward register (vehicle/challan) with {total, items} pagination." },
  "/purchases/three-way-match": { tags: ["purchases", "reports"], explanation: "PO vs Σ GI vs Bill, positional line match, variance flags. Paginated." },
  "/purchases/vendor-performance": { tags: ["purchases", "reports"], explanation: "Lead time, quotation-rate trend, short-receipt proxy for rejection. Not paginated." },
  "/manufacturing/purchase-orders": { tags: ["purchases", "manufacturing"], explanation: "Purchase orders. With purchase_store, a bare PO is rejected unless it carries an approved comparative." },
  "/manufacturing/grn": { tags: ["purchases", "inventory", "gl"], explanation: "Goods receipt note — stock in against a PO when you are not using gate inward." },
  "/store/gate-outward": { tags: ["inventory", "gl"], explanation: "Dispatch exit. Invoice/DN sources approve on create; scrap is draft→approve with GL." },
  "/store/gate-outward-register": { tags: ["inventory", "reports"], explanation: "Outward register, paginated, vehicle/challan search." },
  "/store/dispatch-reconciliation": { tags: ["inventory", "reports", "sales"], explanation: "Posted invoices and debit notes missing a gate exit. SQL UNION so search spans both doc types." },
  "/store/issues": { tags: ["inventory", "gl"], explanation: "Departmental consumption. Posts Dr Expense / Cr Inventory on create; debit account must be Expense-type." },
  "/store/issue-register": { tags: ["inventory", "reports"], explanation: "Issue register, paginated (demo manufacturing seeds 60 rows so page 2 exists)." },
  "/store/stock-tie-out": { tags: ["inventory", "reports"], explanation: "Product-level stock tie-out. Variance columns null when an end date truncates the window (live stock cannot recon a partial period)." },
  "/inventory": { tags: ["inventory"], explanation: "Inventory hub: on-hand value and low-stock band." },
  "/products": { tags: ["inventory"], explanation: "Product catalog. List/Tree toggle — Tree is Main→Sub→Item closing-stock valuation via /api/reports/product-coa." },
  "/products/categories": { tags: ["inventory"], explanation: "Two-level taxonomy. Delete is blocked while children or products exist." },
  "/products/ledger": { tags: ["inventory", "reports"], explanation: "Per-product movements with resolved store location. ?product= pre-selects from performance reports." },
  "/inventory/performance": { tags: ["inventory", "reports"], explanation: "Turns, value, and movement. Product names link into the product ledger." },
  "/inventory/valuation": { tags: ["inventory", "reports"], explanation: "Closing stock valuation by product." },
  "/inventory/transfers": { tags: ["inventory"], explanation: "Warehouse transfers. In-transit then receipt at the destination." },
  "/inventory/pick-lists": { tags: ["inventory", "sales"], explanation: "Pick / pack lists against sales demand." },
  "/inventory/transfer-register": { tags: ["inventory", "reports"], explanation: "Transfer register — every warehouse move in one list." },
  "/inventory/stock-by-warehouse": { tags: ["inventory", "reports"], explanation: "On-hand by location. consume_stock itself is not location-scoped; this view is the warehouse overlay." },
  "/manufacturing/stock-locations": { tags: ["inventory", "manufacturing"], explanation: "Stock locations (MAIN, GODOWN, WIP seeded on manufacturing)." },
  "/manufacturing": { tags: ["manufacturing"], explanation: "Production floor hub — open orders, WIP, shortcuts into BoMs and work orders." },
  "/manufacturing/boms": { tags: ["manufacturing"], explanation: "Bills of material. Components + finished item; used by production orders." },
  "/manufacturing/rate-plans": { tags: ["manufacturing"], explanation: "Job rate plans for pricing production." },
  "/manufacturing/production-orders": { tags: ["manufacturing", "gl"], explanation: "Work orders: issue components, complete output, optional scrap." },
  "/manufacturing/scrap-reasons": { tags: ["manufacturing"], explanation: "Scrap reason catalog so write-offs hit a consistent P&L account." },
  "/manufacturing/reports": { tags: ["manufacturing", "reports"], explanation: "WIP, output, custody stock — manufacturing’s report pack." },
  "/telecom": { tags: ["telecom"], explanation: "Franchise hub: float, activations, FCA, commissions at a glance." },
  "/telecom/tracker": { tags: ["telecom"], explanation: "Tracker deposit and load wallet. This is the franchise float sub-ledger." },
  "/telecom/rso": { tags: ["telecom"], explanation: "Retail sales officer channel — issue load, collect, commission base." },
  "/telecom/sim": { tags: ["telecom", "inventory"], explanation: "SIM stock and activations." },
  "/telecom/fca": { tags: ["telecom"], explanation: "Franchise contracted amounts and targets vs actual." },
  "/telecom/mobile-money": { tags: ["telecom", "banking"], explanation: "Mobile-money float (M-Pesa-style) on the franchise CoA." },
  "/telecom/postpaid": { tags: ["telecom", "sales"], explanation: "Postpaid book and billing cycle." },
  "/telecom/commissions": { tags: ["telecom", "gl"], explanation: "Franchise/RSO commission runs." },
  "/telecom/franchise": { tags: ["telecom"], explanation: "Franchise admin: POS and contract terms." },
  "/telecom/devices": { tags: ["telecom", "inventory"], explanation: "IMEI / handset inventory." },
  "/banking": { tags: ["banking"], explanation: "Banking hub: live GL balances for cash and bank accounts." },
  "/bank-accounts": { tags: ["banking"], explanation: "Bank account master linked to a cash/bank GL leaf." },
  "/exchange-rates": { tags: ["banking", "ledger"], explanation: "FX catalog. Inverse fallback: if only USD→EUR exists, EUR→USD is 1/rate. Documents store the rate they used." },
  "/bank-imports": { tags: ["banking"], explanation: "CSV/OFX statement import. Lines are matched, never auto-posted." },
  "/banking/feeds": { tags: ["banking"], explanation: "Bank feeds (open-banking style). Same matching pipeline as imports." },
  "/bank-imports/rules": { tags: ["banking"], explanation: "Matching rules: description contains → suggest this GL/party." },
  "/cash-book": { tags: ["banking", "reports"], explanation: "Cash book — receipts and payments on cash accounts." },
  "/bank-book": { tags: ["banking", "reports"], explanation: "Bank book — same idea on bank GL leaves." },
  "/reconciliations": { tags: ["banking"], explanation: "Open/closed bank recs. Close only when statement vs book difference is zero." },
  "/trial-balance": { tags: ["reports", "ledger"], explanation: "Hierarchical TB {tree, totals}. Comparison mode is flat current vs prior. Leaves drill to the GL." },
  "/pl": { tags: ["reports", "ifrs"], explanation: "Income statement tree (revenue/expenses) plus net_profit. Print uses a real thead + freeze panes in single-period mode." },
  "/reports/dimensional-pl": { tags: ["reports", "ledger"], explanation: "P&L sliced by analytic dimension (cost centre / project)." },
  "/balance": { tags: ["reports", "ifrs"], explanation: "Balance sheet trees (assets, liabilities, equity) with RE-CUR synthetic retained earnings." },
  "/consolidation": { tags: ["reports", "ifrs"], explanation: "IFRS 10 group worksheet on the holding tenant. Eliminations never post to member GLs." },
  "/intercompany/recon": { tags: ["reports", "ifrs"], explanation: "Intercompany recon: invoices/bills flagged is_intercompany against Due from/to Affiliates (1180/2180)." },
  "/cashflow": { tags: ["reports"], explanation: "Cash flow statement from GL movements on cash/bank." },
  "/tax": { tags: ["reports", "tax"], explanation: "Tax summary from tax codes on invoices and bills." },
  "/reports/wht": { tags: ["reports", "tax"], explanation: "Withholding tax — vendor WHT flags and BillPayment.wht_amount." },
  "/reports/cit-worksheet": { tags: ["reports", "tax"], explanation: "Corporate income tax worksheet with CitAdjustment rows." },
  "/india-gst/gstr": { tags: ["reports", "tax", "localization"], explanation: "GSTR-style outward/inward tax (CGST/SGST/IGST)." },
  "/india-gst": { tags: ["tax", "localization"], explanation: "India GST pack home." },
  "/tax-return": { tags: ["reports", "tax"], explanation: "Tax return assembly from posted tax codes." },
  "/tax-codes": { tags: ["tax", "settings"], explanation: "Tax code catalog (rate, inclusive/exclusive). Historical docs keep the rate they were issued with." },
  "/budgets": { tags: ["reports"], explanation: "Budget vs actual by account, both tabs freeze-paned." },
  "/assets": { tags: ["assets", "reports", "gl"], explanation: "Fixed-asset register: cost, accum dep, NBV, components, impairment, disposal." },
  "/assets/rollforward": { tags: ["assets", "reports"], explanation: "Opening → additions → dep → impair → disposal → closing NBV." },
  "/leases": { tags: ["leases", "ifrs", "gl"], explanation: "IFRS 16 RoU and lease liability. Hidden when leases_enabled is false." },
  "/period-close": { tags: ["ledger", "settings"], explanation: "Lock accounting periods. posting.py refuses locked dates." },
  "/deferred-revenue": { tags: ["ifrs", "sales", "gl"], explanation: "Recognition schedule per deferred invoice. Recognise a month or reverse an unposted plan." },
  "/contract-balances": { tags: ["ifrs", "sales", "reports"], explanation: "IFRS 15 contract asset (1140) vs liability — performance vs billing." },
  "/customer-performance": { tags: ["sales", "reports"], explanation: "Top customers, margins, outstanding. Names link to statements." },
  "/reports/builder": { tags: ["reports"], explanation: "Whitelisted ad-hoc reports (9 sources). Unknown field keys → 400. Export CSV/XLSX is formula-injection-safe." },
  "/profile": { tags: ["settings"], explanation: "Own profile, password, avatar, TOTP." },
  "/imports": { tags: ["settings"], explanation: "CSV bulk import with a column guide per entity." },
  "/payment-terms": { tags: ["settings", "sales"], explanation: "Net-X terms used to compute invoice due dates." },
  "/team": { tags: ["settings"], explanation: "Invite users (owner/admin/accountant/clerk). Admin-only." },
  "/practice": { tags: ["settings"], explanation: "Practice-firm client switcher — jump across tenants you are a member of." },
  "/settings/permissions": { tags: ["settings"], explanation: "76-resource rights matrix plus my_data_only. A resource only enforces where perm_dep is on the route." },
  "/audit": { tags: ["settings"], explanation: "Who changed what. Seeded demo data has mixed owner/accountant/clerk attribution." },
  "/approvals": { tags: ["approvals"], explanation: "Approval inbox — documents waiting on you." },
  "/approvals/workflows": { tags: ["approvals", "settings"], explanation: "Define chains: document type, threshold, role sequence." },
  "/workflow": { tags: ["workflow", "gl"], explanation: "GL posting flowcharts (sales, purchases, FX, manufacturing, telecom, spinning…). Companion to this catalog." },
  "/guide": { tags: ["settings"], explanation: "Prose user guide, filtered to the tenant’s business model. This catalog is the visual twin." },
  "/agent": { tags: ["ai"], explanation: "AI Financial Assistant (module ai_assistant). Four-stage pipeline: triage → specialist tools → reviewer → drafting." },
  "/settings/studio": { tags: ["settings"], explanation: "Custom fields, form layout, print templates. Weighbridge overlay adds x.gate_pass_no on invoices." },
  "/settings": { tags: ["settings"], explanation: "Company, accounting, preferences, advanced, API keys, updates — and the Catalog tab." },
  "/settings/catalog": { tags: ["settings", "workflow"], explanation: "Visual catalog of every tenant, segment, workflow, report, and screen with captured snapshots and GL notes. Filter by tag or demo company." },
  "/apps": { tags: ["settings"], explanation: "Add-ons store (Default / Recommended / Optional / Marketplace). CATEGORY_ORDER is an allowlist — missing categories never show a card." },
  "/pra-dashboard": { tags: ["compliance", "tax"], explanation: "PRA sales dashboard — sandbox submissions and KPIs." },
  "/pra-logs": { tags: ["compliance", "reports"], explanation: "PRA submission log (success + failed-then-retried rows in the demo)." },
  "/uae": { tags: ["compliance", "tax"], explanation: "UAE VAT e-invoice dashboard." },
  "/uae/logs": { tags: ["compliance", "reports"], explanation: "UAE e-invoice submission logs." },
  "/zatca": { tags: ["compliance", "tax"], explanation: "ZATCA / Fatoora dashboard (seeded on manufacturing)." },
  "/zatca/logs": { tags: ["compliance", "reports"], explanation: "ZATCA clear/report attempt log." },
  "/peppol": { tags: ["compliance", "tax"], explanation: "Peppol AP dashboard (seeded on services)." },
  "/peppol/logs": { tags: ["compliance", "reports"], explanation: "Peppol send log." },
  "/hrm": { tags: ["payroll"], explanation: "HRM hub: headcount, last run, attendance shortcuts." },
  "/payroll": { tags: ["payroll", "gl"], explanation: "Payroll run list with KPI cards. Draft → approve → post → void." },
  "/employees": { tags: ["payroll"], explanation: "Employee master (search, active/all). Edit includes the salary-structure tab." },
  "/attendance": { tags: ["payroll"], explanation: "Monthly attendance grid. Biometric import matches employee_code; those rows cannot be deleted." },
  "/leave": { tags: ["payroll"], explanation: "Leave requests (annual/sick/unpaid) that feed LOP on the next payroll." },
  "/expense-claims": { tags: ["payroll", "gl"], explanation: "Employee expense claims — reimburse via a payment voucher after approval." },
  "/payroll/components": { tags: ["payroll"], explanation: "Salary component catalog (earning/deduction) used by structures and runs." },
  "/healthcare": { tags: ["healthcare"], explanation: "Hospital hub: OPD/IPD/lab KPIs and shortcuts." },
  "/healthcare/patients": { tags: ["healthcare", "sales"], explanation: "Patient registry (MR-YYYYNNNN) with auto-linked Customer." },
  "/healthcare/doctors": { tags: ["healthcare"], explanation: "Doctor master used by OPD tokens and collections reports." },
  "/healthcare/opd": { tags: ["healthcare", "sales", "gl"], explanation: "OPD tokens and visits. Recording a visit posts Dr 1100 / Cr 4100." },
  "/healthcare/ipd": { tags: ["healthcare", "sales"], explanation: "Wards, beds (available/occupied/maintenance), admissions, charges, discharge." },
  "/healthcare/lab": { tags: ["healthcare"], explanation: "Lab order queue: collect, result, deliver." },
  "/healthcare/lab/tests": { tags: ["healthcare"], explanation: "Lab test catalogue (unit + normal range copied onto results)." },
  "/healthcare/procedures": { tags: ["healthcare"], explanation: "Procedure catalogue and orders (OT/surgery)." },
  "/healthcare/dialysis": { tags: ["healthcare"], explanation: "Dialysis session board." },
  "/healthcare/store": { tags: ["healthcare", "inventory"], explanation: "Hospital store issues and pharmacy dispense queue." },
  "/healthcare/reports": { tags: ["healthcare", "reports"], explanation: "Seven HC reports: dashboard, OPD, doctor collections, lab, IPD census, revenue-by-type (4100–4121), patient statement." },
  "/weaving": { tags: ["weaving"], explanation: "Weaving hub (memo/ops)." },
  "/weaving/setup": { tags: ["weaving"], explanation: "Qualities, looms, yarn types, shifts, operators." },
  "/weaving/contracts": { tags: ["weaving"], explanation: "Contracts with embedded rate/costing." },
  "/weaving/yarn-inward": { tags: ["weaving"], explanation: "Yarn inward in kg; lb/bag derived via weaving_calc." },
  "/weaving/sizing": { tags: ["weaving"], explanation: "Sizing programme against contract yarn." },
  "/weaving/production": { tags: ["weaving"], explanation: "Loom production by shift/operator." },
  "/weaving/dispatch": { tags: ["weaving"], explanation: "Finished-fabric dispatch against the contract." },
  "/weaving/calculators/weaving": { tags: ["weaving"], explanation: "Weaving calculator (construction, rpm, efficiency → pick/production)." },
  "/weaving/calculators/sizing": { tags: ["weaving"], explanation: "Sizing calculator (recipe, pickup, beam)." },
  "/weaving/reports/daily": { tags: ["weaving", "reports"], explanation: "Daily weaving operations register." },
  "/weaving/reports/contract-control": { tags: ["weaving", "reports"], explanation: "Contract control — inward vs production vs dispatch." },
  "/weaving/reports/customer-kpi": { tags: ["weaving", "reports"], explanation: "Customer KPI for weaving jobs." },
  "/weaving/dashboard": { tags: ["weaving", "reports"], explanation: "Weaving dashboard tiles." },
  "/weighbridge": { tags: ["weighbridge"], explanation: "Weighbridge hub — open tickets and today’s net kg." },
  "/weighbridge/tickets/new": { tags: ["weighbridge"], explanation: "New ticket: vehicle, product, first weigh." },
  "/weighbridge/tickets": { tags: ["weighbridge"], explanation: "Ticket list (open/completed)." },
  "/weighbridge/reports/register": { tags: ["weighbridge", "reports"], explanation: "Weighbridge ticket register." },
  "/spinning": { tags: ["spinning"], explanation: "Spinning hub with lot and yield KPIs." },
  "/spinning/setup": { tags: ["spinning"], explanation: "Yarn specs, fiber grades, machines, shifts, operators, waste types, recipes." },
  "/spinning/plans": { tags: ["spinning"], explanation: "Production plans that feed spin lots." },
  "/spinning/lots": { tags: ["spinning", "gl"], explanation: "Spin lots — the control record for a batch through the mill." },
  "/spinning/bale-receipts": { tags: ["spinning", "gl"], explanation: "Raw cotton bale receipts (Dr 1200)." },
  "/spinning/stages": { tags: ["spinning", "gl"], explanation: "Stage entries moving kg through WIP 1201–1203." },
  "/spinning/cone-output": { tags: ["spinning", "gl"], explanation: "Finished yarn cones (Dr 1204 FG)." },
  "/spinning/waste": { tags: ["spinning", "gl"], explanation: "Waste log → 5901–5904." },
  "/spinning/dispatch": { tags: ["spinning", "gl"], explanation: "Yarn dispatch (COGS 5010 / FG 1204)." },
  "/spinning/calculators/yield": { tags: ["spinning"], explanation: "Yield calculator — what-if vs posted lots." },
  "/spinning/reports/daily": { tags: ["spinning", "reports"], explanation: "Daily spinning register." },
  "/spinning/reports/lot-control": { tags: ["spinning", "reports"], explanation: "Lot control — RM in vs FG out vs waste." },
  "/spinning/reports/waste": { tags: ["spinning", "reports"], explanation: "Waste analysis by type/stage." },
  "/spinning/dashboard": { tags: ["spinning", "reports"], explanation: "Spinning dashboard tiles." },
  "/processing": { tags: ["processing"], explanation: "Processing hub — grey in, WIP, packed out." },
  "/processing/setup": { tags: ["processing"], explanation: "Qualities, blends, widths, process catalog, contractors." },
  "/processing/sales-orders": { tags: ["processing", "sales"], explanation: "Processing sales orders that grey lots attach to." },
  "/processing/lots": { tags: ["processing"], explanation: "Grey inward lots (customer-owned custody)." },
  "/processing/mending": { tags: ["processing"], explanation: "Mending before process." },
  "/processing/kachi-parchi": { tags: ["processing"], explanation: "Kachi parchi (rough ticket) against a lot." },
  "/processing/pakki-parchi": { tags: ["processing"], explanation: "Pakki parchi (packed ticket) before dispatch." },
  "/processing/rejection": { tags: ["processing"], explanation: "Grey rejection outward." },
  "/processing/production-orders": { tags: ["processing"], explanation: "Processing production orders." },
  "/processing/stages": { tags: ["processing"], explanation: "PPC stage board." },
  "/processing/dispatch": { tags: ["processing"], explanation: "Fresh (packed) dispatch." },
  "/processing/labor-bills": { tags: ["processing", "purchases"], explanation: "Contractor labor bills against processed lots." },
  "/processing/settlements": { tags: ["processing"], explanation: "Grey settlement — leftover customer stock." },
  "/processing/inspections": { tags: ["processing"], explanation: "Inspection records before pack/dispatch." },
  "/processing/reports/rejection": { tags: ["processing", "reports"], explanation: "Rejection register." },
  "/processing/reports/stock-ledger": { tags: ["processing", "reports"], explanation: "Customer grey stock ledger." },
  "/processing/reports/ppc": { tags: ["processing", "reports"], explanation: "PPC stage reports." },
}

function uniqueNav(): NavItem[] {
  const seen = new Set<string>()
  const out: NavItem[] = []
  for (const item of NAV) {
    if (seen.has(item.href)) continue
    seen.add(item.href)
    out.push(item)
  }
  return out
}

const EXTRA_HREFS = new Set(EXTRA_SCREENS.map(e => e.href))

const NAV_ENTRIES: CatalogEntry[] = uniqueNav().filter(item => !EXTRA_HREFS.has(item.href)).map(item => {
  const mods = navModules(item)
  const copy = SCREEN_COPY[item.href]
  const report = isReportNav(item)
  return {
    id: `${report ? "report" : "screen"}-${slugHref(item.href)}`,
    title: item.label,
    kind: (report ? "report" : "screen") as CatalogKind,
    href: item.href,
    explanation: (() => {
      const raw = copy?.explanation ?? `${item.label} in the ${item.section} section. Open the live screen from this catalog card after you install the required module.`
      return raw.length > 40 ? raw : `${raw} Open the live screen from this catalog card.`
    })(),
    tags: copy?.tags ?? [item.section.toLowerCase()],
    gl: copy?.gl,
    tenants: tenantsForModules(mods),
    modules: mods,
    segment: item.section,
    captureTenant: tenantForModule(item.forModule ?? item.forAnyModule?.[0]),
  }
})

export const CATALOG: CatalogEntry[] = [
  ...TENANT_ENTRIES,
  ...SEGMENT_ENTRIES,
  ...WORKFLOW_ENTRIES,
  ...EXTRA_SCREENS,
  ...NAV_ENTRIES,
]

export const CATALOG_BY_ID: Record<string, CatalogEntry> = Object.fromEntries(
  CATALOG.map(e => [e.id, e]),
)

export function allCatalogTags(): { tag: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const e of CATALOG) {
    for (const t of e.tags) counts.set(t, (counts.get(t) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
}

export function filterCatalog(opts: {
  kind?: CatalogKind | "all"
  tag?: string | null
  tenant?: DemoTenantKey | "all"
  q?: string
}): CatalogEntry[] {
  const q = (opts.q ?? "").trim().toLowerCase()
  return CATALOG.filter(e => {
    if (opts.kind && opts.kind !== "all" && e.kind !== opts.kind) return false
    if (opts.tag && !e.tags.includes(opts.tag)) return false
    if (opts.tenant && opts.tenant !== "all" && !e.tenants.includes(opts.tenant)) return false
    if (!q) return true
    const blob = `${e.title} ${e.explanation} ${e.tags.join(" ")} ${e.segment} ${e.href}`.toLowerCase()
    return blob.includes(q)
  })
}

/** Unique capture jobs for the Playwright snapshot pass. */
export function catalogCaptureJobs(): {
  id: string
  path: string
  tenant: DemoTenantKey | "anon"
}[] {
  const seen = new Set<string>()
  const jobs: { id: string; path: string; tenant: DemoTenantKey | "anon" }[] = []
  for (const e of CATALOG) {
    const path = e.capturePath ?? e.href
    const key = `${e.captureTenant}::${path}`
    if (seen.has(key)) continue
    seen.add(key)
    jobs.push({ id: shotKey(e), path, tenant: e.captureTenant })
  }
  return jobs
}
