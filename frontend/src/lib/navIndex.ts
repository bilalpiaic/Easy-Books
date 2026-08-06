/**
 * Static full-text search index for navigation, forms, reports, and outputs.
 * Built at module-load time — every lookup is synchronous (~0 ms).
 *
 * Layers:
 *  1. All sidebar nav items from NAV (section pages) — enriched keywords
 *  2. Quick-action / input forms ("New …" and entry screens)
 *  3. Reports, analysis, and printable / output surfaces
 */
import { NAV } from "@/lib/nav"

export interface NavResult {
  id:       string
  type:     "nav" | "action" | "report"
  label:    string
  sub:      string   // shown as secondary text
  href:     string
  keywords: string[] // extra match terms (not displayed)
}

/** Extra aliases keyed by href — merged into NAV_ITEMS keywords. */
const NAV_ALIASES: Record<string, string[]> = {
  "/dashboard":              ["home", "kpi", "overview", "main", "financial", "operations", "ops dashboard", "purpose dashboard"],
  "/entry":                  ["voucher", "jv", "payment voucher", "receipt voucher", "new entry", "manual entry"],
  "/journal":                ["journal list", "vouchers", "jv list"],
  "/recurring":              ["recurring journal", "standing entry", "auto post"],
  "/ledger":                 ["gl", "general ledger", "account history"],
  "/coa":                    ["coa", "chart of accounts", "account codes"],
  "/analytic-accounts":      ["cost center", "project", "department", "dimension", "analytic"],
  "/receivable":             ["ar hub", "accounts receivable", "sales hub"],
  "/invoices":               ["sales invoice", "billing", "ar documents"],
  "/commissions":            ["staff commission", "sales commission", "commission ledger"],
  "/promo-discounts":        ["promo", "discount rules", "promotions"],
  "/credit-notes":           ["credit note", "sales return", "cn"],
  "/customers":              ["clients", "buyers", "debtors"],
  "/payments-received":      ["receipts", "collections", "customer payment"],
  "/advances":               ["customer advance", "unearned", "deposit received"],
  "/aging/receivable":       ["ar aging", "overdue invoices", "debtors aging"],
  "/payable":                ["ap hub", "accounts payable", "purchases hub"],
  "/bills":                  ["vendor bill", "supplier invoice", "purchase invoice"],
  "/debit-notes":            ["debit note", "purchase return", "dn"],
  "/vendors":                ["suppliers", "creditors"],
  "/bill-payments":          ["payments made", "pay vendor", "supplier payment"],
  "/aging/payable":          ["ap aging", "overdue bills", "creditors aging"],
  "/purchases":              ["purchases hub", "procure", "buying"],
  "/purchases/demands":      ["purchase demand", "requisition", "indent", "pd"],
  "/purchases/comparatives": ["comparative statement", "quotation compare", "cs", "bid comparison"],
  "/purchases/gate-inward":  ["gate inward", "gi", "goods in gate", "vehicle entry"],
  "/purchases/gate-register":["gate register", "inward register"],
  "/purchases/three-way-match": ["3 way match", "po vs grn vs bill", "three way"],
  "/purchases/vendor-performance": ["vendor kpi", "supplier performance", "delivery score"],
  "/store/gate-outward":     ["gate outward", "go", "dispatch exit", "gate out"],
  "/store/gate-outward-register": ["outward register", "dispatch register"],
  "/store/dispatch-reconciliation": ["dispatch recon", "missing gate exit"],
  "/store/issues":           ["store issue", "material issue", "consumption", "si"],
  "/store/issue-register":   ["issue register", "consumption register"],
  "/store/stock-tie-out":    ["stock tie out", "inventory recon", "stock reconciliation"],
  "/inventory":              ["stock hub", "inventory hub"],
  "/products":               ["items", "sku", "stock items", "services catalog"],
  "/products/categories":    ["product category", "taxonomy", "sub category"],
  "/products/ledger":        ["stock ledger", "product movements", "inventory ledger"],
  "/inventory/performance":  ["stock report", "inventory valuation", "turnover"],
  "/manufacturing":          ["production floor", "factory", "mfg hub"],
  "/manufacturing/boms":     ["bom", "bill of materials", "recipe"],
  "/manufacturing/rate-plans": ["rate plan", "job rates", "pricing plan"],
  "/manufacturing/purchase-orders": ["po", "purchase order"],
  "/manufacturing/stock-locations": ["warehouse", "bin", "location", "store location"],
  "/manufacturing/grn":      ["grn", "goods receipt note", "receive stock"],
  "/manufacturing/production-orders": ["work order", "production order", "mo", "manufacture"],
  "/manufacturing/reports":  ["mfg reports", "wip", "production summary", "custody"],
  "/telecom":                ["franchise hub", "telecom overview"],
  "/telecom/tracker":        ["tracker", "load wallet", "float"],
  "/telecom/rso":            ["rso", "agent channel", "distributor"],
  "/telecom/sim":            ["sim stock", "activations", "airtime"],
  "/telecom/fca":            ["fca", "targets", "franchise targets"],
  "/telecom/mobile-money":   ["mobile money", "m-pesa", "float"],
  "/telecom/postpaid":       ["postpaid", "postpaid book", "billing cycle"],
  "/telecom/commissions":    ["franchise commission", "rso commission"],
  "/telecom/franchise":      ["franchise admin", "pos"],
  "/telecom/devices":        ["imei", "handset", "device stock"],
  "/banking":                ["banking hub", "cash bank"],
  "/bank-accounts":          ["bank account", "linked bank"],
  "/exchange-rates":         ["fx", "currency rate", "forex"],
  "/bank-imports":           ["bank statement import", "ofx", "csv bank"],
  "/banking/feeds":          ["bank feeds", "open banking", "plaid sync", "statement sync"],
  "/pos":                    ["pos", "point of sale", "register", "checkout", "counter sale"],
  "/pos/shifts":             ["pos shifts", "cash up", "shift close", "till variance"],
  "/ecommerce":              ["ecommerce", "shopify", "woocommerce", "daraz", "store connector", "online orders"],
  "/leave":                  ["leave", "annual leave", "sick leave", "unpaid leave", "lop"],
  "/inventory/transfers":    ["stock transfer", "warehouse transfer", "in transit", "wms"],
  "/inventory/transfer-register": ["transfer register", "warehouse transfer log"],
  "/inventory/stock-by-warehouse": ["stock by warehouse", "location stock", "warehouse qty"],
  "/cash-book":              ["cash book", "petty cash", "cash ledger"],
  "/bank-book":              ["bank book", "bank ledger"],
  "/reconciliations":        ["bank recon", "reconcile", "match statement"],
  "/trial-balance":          ["tb", "trial balance"],
  "/pl":                     ["p&l", "pnl", "profit loss", "income statement"],
  "/reports/dimensional-pl": ["dimensional", "analytic p&l", "segment p&l", "cost center p&l"],
  "/balance":                ["balance sheet", "financial position", "bs"],
  "/consolidation":          ["consolidation", "ifrs 10", "group", "subsidiary", "nci", "eliminations"],
  "/leases":                 ["leases", "ifrs 16", "right of use", "rou", "lease liability", "maturity"],
  "/cashflow":               ["cash flow", "funds flow"],
  "/tax":                    ["gst", "vat", "tax summary", "sales tax"],
  "/reports/wht":            ["wht", "withholding", "withholding tax"],
  "/reports/cit-worksheet":  ["cit", "corporate tax", "tax worksheet"],
  "/india-gst/gstr":         ["gstr", "india gst", "cgst", "sgst", "igst", "gstr-1"],
  "/tax-codes":              ["tax code", "tax rate"],
  "/budgets":                ["budget vs actual", "variance"],
  "/assets":                 ["fixed assets", "depreciation", "capex", "asset register"],
  "/assets/rollforward":     ["asset rollforward", "fixed asset movement", "nbv rollforward", "impairment"],
  "/period-close":           ["close period", "lock period", "month end"],
  "/deferred-revenue":       ["ifrs 15", "revenue recognition", "unearned"],
  "/contract-balances":      ["ifrs 15", "contract asset", "contract liability", "unbilled", "ssp"],
  "/customer-performance":   ["customer analysis", "top customers", "sales by customer"],
  "/reports/builder":        ["custom report", "ad hoc", "report builder", "query"],
  "/profile":                ["my profile", "password", "avatar"],
  "/imports":                ["csv import", "bulk upload", "spreadsheet"],
  "/payment-terms":          ["payment terms", "net 30", "due terms"],
  "/team":                   ["users", "invite", "staff accounts"],
  "/practice":               ["practice", "clients", "switch company", "multi client", "accountant"],
  "/settings/permissions":   ["permissions", "user rights", "access matrix"],
  "/audit":                  ["audit log", "activity trail", "who changed"],
  "/alerts":                 ["alerts", "inbox", "notifications", "bell"],
  "/workflow":               ["approvals", "workflow"],
  "/guide":                  ["help", "user guide", "docs", "manual"],
  "/agent":                  ["ai chat", "assistant", "ask books", "ai agent"],
  "/settings":               ["preferences", "configuration", "company settings"],
  "/apps":                   ["add-ons", "modules", "install module", "extensions"],
  "/pra-logs":               ["pra logs", "fiscal submission", "einvoice log"],
  "/zatca/logs":             ["zatca logs", "fatoora", "saudi einvoice", "ksa"],
  "/peppol/logs":            ["peppol logs", "ubl", "eu einvoice", "access point"],
  "/hrm":                    ["payroll hub", "hr overview"],
  "/payroll":                ["payroll runs", "salary run", "payslip"],
  "/employees":              ["staff", "hr master", "employee list"],
  "/attendance":             ["attendance", "time in out", "present absent"],
  "/payroll/components":     ["salary component", "allowance", "deduction"],
  "/healthcare":             ["hospital hub", "clinic"],
  "/healthcare/patients":    ["patient", "mr number", "opd patient"],
  "/healthcare/doctors":     ["doctor", "physician", "consultant"],
  "/healthcare/opd":         ["opd", "outpatient", "token"],
  "/healthcare/ipd":         ["ipd", "admission", "inpatient", "ward", "bed"],
  "/healthcare/lab":         ["lab orders", "laboratory", "pathology", "lab report", "test report", "print results"],
  "/healthcare/lab/tests":   ["lab test catalog", "test list"],
  "/healthcare/procedures":  ["procedure", "ot", "surgery catalog"],
  "/healthcare/dialysis":    ["dialysis", "hemodialysis", "hd machine", "dialysis shift", "renal"],
  "/healthcare/store":       ["pharmacy", "hc store", "dispense"],
  "/healthcare/reports":     ["hospital reports", "opd summary", "ipd census", "doctor collections"],
  "/weaving":                ["weaving hub", "loom unit"],
  "/weaving/setup":          ["loom", "shift", "operator", "fabric quality", "yarn type"],
  "/weaving/contracts":      ["weaving contract", "wc"],
  "/weaving/yarn-inward":    ["yarn inward", "yarn receipt"],
  "/weaving/sizing":         ["sizing entry", "size pickup"],
  "/weaving/production":     ["weaving production", "grey meters", "loom production"],
  "/weaving/dispatch":       ["weaving dispatch", "fabric delivery"],
  "/weaving/calculators/weaving": ["ne calculator", "yarn consumption calc", "weaving calc"],
  "/weaving/calculators/sizing":  ["sizing calculator", "pickup calc"],
  "/weaving/reports/daily":  ["daily ops", "weaving daily", "efficiency"],
  "/weaving/reports/contract-control": ["contract control", "yarn balance", "progress"],
  "/weaving/reports/customer-kpi": ["weaving kpi", "customer weaving"],
  "/weaving/dashboard":      ["weaving dashboard", "weaving kpis"],
  "/spinning":               ["spinning hub", "yarn spinning", "spin mill"],
  "/spinning/setup":         ["yarn spec", "fiber grade", "spinning machine", "waste type"],
  "/spinning/plans":         ["production plan", "spinning plan"],
  "/spinning/lots":          ["spin lot", "spinning lot"],
  "/spinning/bale-receipts": ["bale receipt", "cotton bale", "fiber receipt"],
  "/spinning/stages":        ["stage entry", "carding", "drawing", "roving", "winding"],
  "/spinning/cone-output":   ["cone output", "yarn cones"],
  "/spinning/waste":         ["waste log", "spinning waste"],
  "/spinning/dispatch":      ["yarn dispatch", "cone dispatch"],
  "/spinning/calculators/yield": ["yield calculator", "spinning yield"],
  "/spinning/reports/daily": ["spinning daily", "daily register"],
  "/spinning/reports/lot-control": ["lot control", "spin lot progress"],
  "/spinning/reports/waste": ["waste analysis", "spinning waste report"],
  "/spinning/dashboard":     ["spinning dashboard", "spinning kpis"],
  "/processing":             ["textile processing", "ballor", "printing unit", "processing hub"],
  "/processing/setup":       ["quality blend width", "process catalog", "contractor"],
  "/processing/sales-orders": ["processing sales order", "grey rate", "job order"],
  "/processing/lots":        ["grey lot", "grey inward", "grey in", "than entry", "custodial grey"],
  "/processing/mending":     ["mending", "l-kami", "safai", "safi grey", "ready meters"],
  "/processing/kachi-parchi": ["kachi parchi", "provisional slip"],
  "/processing/pakki-parchi": ["pakki parchi", "unit responsibility"],
  "/processing/rejection":   ["rejection note", "rejection ogp", "outward gate pass"],
  "/processing/production-orders": ["textile production order", "ppc order"],
  "/processing/stages":      ["ppc stage", "process wastage", "visible wastage"],
  "/processing/dispatch":    ["fresh dispatch", "process invoice"],
  "/processing/labor-bills": ["contractor labor", "labor bill"],
  "/processing/settlements": ["grey settlement", "grey credit"],
  "/processing/inspections": ["rm inspection", "gate inspection"],
  "/processing/reports/rejection": ["rejection register"],
  "/processing/reports/stock-ledger": ["customer grey stock", "custodial ledger"],
  "/processing/reports/ppc": ["ppc report", "stage register"],
}

// ── 1. Sidebar pages ──────────────────────────────────────────────────────────

const NAV_ITEMS: NavResult[] = NAV.map(item => ({
  id:       `nav:${item.href}`,
  type:     "nav" as const,
  label:    item.label,
  sub:      item.section,
  href:     item.href,
  keywords: [
    item.label.toLowerCase(),
    item.section.toLowerCase(),
    ...(NAV_ALIASES[item.href] ?? []),
  ],
}))

// ── 2. Input forms & entry screens ────────────────────────────────────────────

const ACTIONS: NavResult[] = [
  {
    id: "qa:invoice-new", type: "action", label: "New Invoice",
    sub: "Create a sales invoice", href: "/invoices/new",
    keywords: ["create invoice", "add invoice", "sale", "billing", "new sale", "form"],
  },
  {
    id: "qa:credit-note", type: "action", label: "Credit Notes",
    sub: "Issue a sales credit / return", href: "/credit-notes",
    keywords: ["new credit note", "sales return", "cn form", "create credit note"],
  },
  {
    id: "qa:customer-new", type: "action", label: "New Customer",
    sub: "Add a customer", href: "/customers/new",
    keywords: ["create customer", "add customer", "client", "buyer", "form"],
  },
  {
    id: "qa:payment-received-new", type: "action", label: "New Payment Received",
    sub: "Record customer payment", href: "/payments-received/new",
    keywords: ["receive payment", "customer payment", "collection", "cash receipt", "form"],
  },
  {
    id: "qa:advances", type: "action", label: "Customer Advances",
    sub: "Record or apply advances received", href: "/advances",
    keywords: ["advance received", "customer deposit", "unearned cash"],
  },
  {
    id: "qa:promo", type: "action", label: "Promo Discounts",
    sub: "Configure invoice promo rules", href: "/promo-discounts",
    keywords: ["promo rule", "discount setup", "giveaway"],
  },
  {
    id: "qa:commissions", type: "action", label: "Staff Commissions",
    sub: "Plans and commission ledger", href: "/commissions",
    keywords: ["commission plan", "compute commission", "sales commission form"],
  },
  {
    id: "qa:bill-new", type: "action", label: "New Bill",
    sub: "Record a vendor bill", href: "/bills/new",
    keywords: ["create bill", "add bill", "purchase", "vendor invoice", "supplier", "form"],
  },
  {
    id: "qa:debit-note", type: "action", label: "Debit Notes",
    sub: "Vendor debit / purchase return", href: "/debit-notes",
    keywords: ["new debit note", "purchase return", "dn form"],
  },
  {
    id: "qa:vendor-new", type: "action", label: "New Vendor",
    sub: "Add a vendor / supplier", href: "/vendors/new",
    keywords: ["create vendor", "add vendor", "supplier", "add supplier", "form"],
  },
  {
    id: "qa:bill-payment-new", type: "action", label: "New Bill Payment",
    sub: "Pay a vendor bill", href: "/bill-payments/new",
    keywords: ["pay bill", "vendor payment", "payment made", "cash payment", "form"],
  },
  {
    id: "qa:journal-new", type: "action", label: "New Journal Entry",
    sub: "Manual debit / credit / payment / receipt", href: "/entry",
    keywords: ["journal", "jv", "voucher", "debit credit", "manual entry", "new entry", "payment voucher", "receipt voucher", "form"],
  },
  {
    id: "qa:recurring", type: "action", label: "Recurring Entries",
    sub: "Standing journal templates", href: "/recurring",
    keywords: ["recurring form", "auto journal"],
  },
  {
    id: "qa:analytic", type: "action", label: "Analytic Accounts",
    sub: "Cost centers / projects / departments", href: "/analytic-accounts",
    keywords: ["new cost center", "new project", "analytic form"],
  },
  {
    id: "qa:product-new", type: "action", label: "New Product",
    sub: "Add a product or service", href: "/products/new",
    keywords: ["create product", "add item", "inventory item", "stock item", "service", "form"],
  },
  {
    id: "qa:product-categories", type: "action", label: "Product Categories",
    sub: "Main / sub category taxonomy", href: "/products/categories",
    keywords: ["category form", "product taxonomy"],
  },
  {
    id: "qa:employee-new", type: "action", label: "New Employee",
    sub: "Add an employee record", href: "/employees/new",
    keywords: ["create employee", "add staff", "hire", "new hire", "form"],
  },
  {
    id: "qa:payroll-new", type: "action", label: "New Payroll Run",
    sub: "Process payroll for a period", href: "/payroll/new",
    keywords: ["run payroll", "pay salaries", "payroll period", "salary run", "form"],
  },
  {
    id: "qa:attendance-record", type: "action", label: "Record Attendance",
    sub: "Manual time-in / time-out", href: "/attendance/record",
    keywords: ["mark attendance", "time in", "time out", "attendance form"],
  },
  {
    id: "qa:attendance-bulk", type: "action", label: "Bulk Attendance",
    sub: "Enter a day's attendance grid", href: "/attendance/bulk",
    keywords: ["bulk attendance", "attendance grid"],
  },
  {
    id: "qa:attendance-import", type: "action", label: "Import Biometric Attendance",
    sub: "Upload device punch file", href: "/attendance/import",
    keywords: ["zkteco", "biometric import", "attendance upload"],
  },
  {
    id: "qa:salary-components", type: "action", label: "Salary Components",
    sub: "Allowances and deductions catalog", href: "/payroll/components",
    keywords: ["salary component form", "allowance", "deduction"],
  },
  {
    id: "qa:po-new", type: "action", label: "New Purchase Order",
    sub: "Create a purchase order", href: "/manufacturing/purchase-orders/new",
    keywords: ["create po", "purchase order", "order to supplier", "form"],
  },
  {
    id: "qa:grn-new", type: "action", label: "New Goods Receipt",
    sub: "Receive stock from a PO", href: "/manufacturing/grn/new",
    keywords: ["receive goods", "grn", "stock receipt", "goods in", "form"],
  },
  {
    id: "qa:bom-new", type: "action", label: "New Bill of Materials",
    sub: "Define a production recipe", href: "/manufacturing/boms/new",
    keywords: ["bom", "recipe", "manufacturing", "components", "form"],
  },
  {
    id: "qa:production-new", type: "action", label: "New Production Order",
    sub: "Start a manufacturing run", href: "/manufacturing/production-orders/new",
    keywords: ["production order", "work order", "manufacture", "produce", "form"],
  },
  {
    id: "qa:rate-plans", type: "action", label: "Rate Plans",
    sub: "Manufacturing rate / pricing plans", href: "/manufacturing/rate-plans",
    keywords: ["rate plan form", "job rate"],
  },
  {
    id: "qa:stock-locations", type: "action", label: "Stock Locations",
    sub: "Warehouses and bins", href: "/manufacturing/stock-locations",
    keywords: ["warehouse form", "location setup"],
  },
  {
    id: "qa:demand-new", type: "action", label: "New Purchase Demand",
    sub: "Quantity-only requisition", href: "/purchases/demands/new",
    keywords: ["purchase demand", "requisition", "indent", "pd form", "form"],
  },
  {
    id: "qa:gate-inward-new", type: "action", label: "New Gate Inward",
    sub: "Record gate receipt vs PO", href: "/purchases/gate-inward/new",
    keywords: ["gate inward", "gi form", "vehicle challan", "form"],
  },
  {
    id: "qa:gate-outward-new", type: "action", label: "New Gate Outward",
    sub: "Dispatch exit / scrap exit", href: "/store/gate-outward/new",
    keywords: ["gate outward", "go form", "dispatch exit", "scrap", "form"],
  },
  {
    id: "qa:store-issue-new", type: "action", label: "New Store Issue",
    sub: "Departmental material consumption", href: "/store/issues/new",
    keywords: ["store issue", "material issue", "consumption form", "si form", "form"],
  },
  {
    id: "qa:bank-accounts", type: "action", label: "Bank Accounts",
    sub: "Link bank accounts to the CoA", href: "/bank-accounts",
    keywords: ["add bank", "bank account form", "link bank"],
  },
  {
    id: "qa:bank-import-new", type: "action", label: "New Bank Import",
    sub: "Upload a bank statement", href: "/bank-imports/new",
    keywords: ["import statement", "bank csv", "ofx", "form"],
  },
  {
    id: "qa:exchange-rates", type: "action", label: "Exchange Rates",
    sub: "Maintain FX rates", href: "/exchange-rates",
    keywords: ["fx rate form", "currency rate"],
  },
  {
    id: "qa:reconciliations", type: "action", label: "Bank Reconciliation",
    sub: "Match statement to ledger", href: "/reconciliations",
    keywords: ["reconcile form", "bank match"],
  },
  {
    id: "qa:assets", type: "action", label: "Fixed Assets",
    sub: "Asset register entry", href: "/assets",
    keywords: ["add asset", "asset form", "depreciation setup"],
  },
  {
    id: "qa:budgets", type: "action", label: "Budgets",
    sub: "Budget lines and variance", href: "/budgets",
    keywords: ["budget form", "budget entry"],
  },
  {
    id: "qa:tax-codes", type: "action", label: "Tax Codes",
    sub: "GST / VAT code setup", href: "/tax-codes",
    keywords: ["tax code form", "gst rate"],
  },
  {
    id: "qa:payment-terms", type: "action", label: "Payment Terms",
    sub: "Due-date terms catalog", href: "/payment-terms",
    keywords: ["payment term form", "net days"],
  },
  {
    id: "qa:deferred", type: "action", label: "Deferred Revenue",
    sub: "Recognition schedules", href: "/deferred-revenue",
    keywords: ["deferred form", "recognition schedule"],
  },
  {
    id: "qa:contract-balances", type: "action", label: "Contract Balances",
    sub: "IFRS 15 assets & liabilities by customer", href: "/contract-balances",
    keywords: ["contract asset", "contract liability", "unbilled", "ssp"],
  },
  {
    id: "qa:wv-contract-new", type: "action", label: "New Weaving Contract",
    sub: "Create a weaving contract", href: "/weaving/contracts/new",
    keywords: ["weaving contract", "wc form", "new contract", "form"],
  },
  {
    id: "qa:wv-setup", type: "action", label: "Weaving Setup",
    sub: "Looms, shifts, operators, qualities", href: "/weaving/setup",
    keywords: ["loom setup", "shift setup", "operator", "fabric quality", "yarn type"],
  },
  {
    id: "qa:wv-yarn", type: "action", label: "Yarn Inward",
    sub: "Record yarn receipts", href: "/weaving/yarn-inward",
    keywords: ["yarn inward form", "yarn receipt"],
  },
  {
    id: "qa:wv-sizing", type: "action", label: "Sizing Entry",
    sub: "Record sizing output", href: "/weaving/sizing",
    keywords: ["sizing form", "size entry"],
  },
  {
    id: "qa:wv-production", type: "action", label: "Weaving Production",
    sub: "Record loom production", href: "/weaving/production",
    keywords: ["production form", "grey meters entry"],
  },
  {
    id: "qa:wv-dispatch", type: "action", label: "Weaving Dispatch",
    sub: "Record fabric dispatch", href: "/weaving/dispatch",
    keywords: ["dispatch form", "fabric delivery entry"],
  },
  {
    id: "qa:wv-calc-weaving", type: "action", label: "Weaving Calculator",
    sub: "Ne yarn consumption → assign to contract", href: "/weaving/calculators/weaving",
    keywords: ["ne calc", "yarn calc", "consumption calculator", "what if"],
  },
  {
    id: "qa:wv-calc-sizing", type: "action", label: "Sizing Calculator",
    sub: "Pickup / stretch / waste → assign", href: "/weaving/calculators/sizing",
    keywords: ["sizing calc", "pickup calculator"],
  },
  {
    id: "qa:sp-setup", type: "action", label: "Spinning Setup",
    sub: "Yarn specs, machines, shifts, waste types", href: "/spinning/setup",
    keywords: ["spinning setup", "yarn spec", "fiber grade", "machine"],
  },
  {
    id: "qa:sp-bale", type: "action", label: "Bale Receipt",
    sub: "Record cotton/fiber bale inward", href: "/spinning/bale-receipts",
    keywords: ["bale receipt form", "cotton bale", "fiber inward"],
  },
  {
    id: "qa:sp-stage", type: "action", label: "Stage Entry",
    sub: "Record spinning stage output", href: "/spinning/stages",
    keywords: ["stage entry form", "carding", "drawing", "roving"],
  },
  {
    id: "qa:sp-cone", type: "action", label: "Cone Output",
    sub: "Record finished cone output", href: "/spinning/cone-output",
    keywords: ["cone output form", "yarn cones"],
  },
  {
    id: "qa:sp-waste", type: "action", label: "Waste Log",
    sub: "Record stage waste", href: "/spinning/waste",
    keywords: ["waste log form", "spinning waste"],
  },
  {
    id: "qa:sp-dispatch", type: "action", label: "Yarn Dispatch",
    sub: "Dispatch cones to customer", href: "/spinning/dispatch",
    keywords: ["yarn dispatch form", "cone dispatch"],
  },
  {
    id: "qa:sp-calc-yield", type: "action", label: "Yield Calculator",
    sub: "Input/output kg yield calc", href: "/spinning/calculators/yield",
    keywords: ["yield calc", "spinning yield", "what if"],
  },
  {
    id: "qa:hc-patients", type: "action", label: "Patients",
    sub: "Patient master / MR numbers", href: "/healthcare/patients",
    keywords: ["new patient", "register patient", "mr number"],
  },
  {
    id: "qa:hc-doctors", type: "action", label: "Doctors",
    sub: "Doctor master", href: "/healthcare/doctors",
    keywords: ["new doctor", "physician form"],
  },
  {
    id: "qa:hc-opd", type: "action", label: "OPD",
    sub: "Tokens and outpatient visits", href: "/healthcare/opd",
    keywords: ["opd form", "token", "outpatient visit"],
  },
  {
    id: "qa:hc-ipd", type: "action", label: "IPD / Admissions",
    sub: "Admissions, beds, discharge", href: "/healthcare/ipd",
    keywords: ["admission form", "discharge", "ward bed"],
  },
  {
    id: "qa:hc-lab", type: "action", label: "Laboratory Orders",
    sub: "Collect samples and enter results", href: "/healthcare/lab",
    keywords: ["lab order", "sample", "result entry", "lab report", "test report", "print results"],
  },
  {
    id: "qa:hc-procedures", type: "action", label: "Procedures",
    sub: "Procedure catalog and orders", href: "/healthcare/procedures",
    keywords: ["procedure order", "ot form"],
  },
  {
    id: "qa:hc-dialysis", type: "action", label: "Dialysis Unit",
    sub: "Machines, shifts, daily schedule", href: "/healthcare/dialysis",
    keywords: ["hemodialysis", "hd session", "dialysis machine", "renal"],
  },
  {
    id: "qa:hc-store", type: "action", label: "HC Store / Pharmacy",
    sub: "Pharmacy dispense queue", href: "/healthcare/store",
    keywords: ["pharmacy", "dispense", "hc store issue"],
  },
  {
    id: "qa:imports", type: "action", label: "CSV Import",
    sub: "Bulk import from spreadsheet", href: "/imports",
    keywords: ["import form", "upload csv", "bulk data"],
  },
  {
    id: "qa:pra-dashboard", type: "action", label: "PRA Sales Dashboard",
    sub: "Retail counter + PRA status", href: "/pra-dashboard",
    keywords: ["pra home", "fiscal invoice", "einvoice counter"],
  },
  {
    id: "qa:agent", type: "action", label: "AI Assistant",
    sub: "Ask questions about your books", href: "/agent",
    keywords: ["ai chat", "ask ai", "financial assistant"],
  },
  {
    id: "qa:apps", type: "action", label: "Add-ons",
    sub: "Install industry packs and modules", href: "/apps",
    keywords: ["install module", "addons store"],
  },
  {
    id: "qa:settings", type: "action", label: "Settings",
    sub: "Company, accounting, AI keys", href: "/settings",
    keywords: ["settings form", "configure"],
  },
]

// ── 3. Reports, analysis & outputs ────────────────────────────────────────────

const REPORTS: NavResult[] = [
  {
    id: "rpt:trial-balance", type: "report", label: "Trial Balance",
    sub: "Accounts debit/credit summary", href: "/trial-balance",
    keywords: ["tb", "trial balance", "closing balance", "debit credit totals", "output", "analysis"],
  },
  {
    id: "rpt:pl", type: "report", label: "Income Statement",
    sub: "Profit & Loss report", href: "/pl",
    keywords: ["p&l", "profit loss", "income statement", "pnl", "revenue expenses", "output", "analysis"],
  },
  {
    id: "rpt:dimensional-pl", type: "report", label: "Dimensional P&L",
    sub: "P&L by cost center / project / location", href: "/reports/dimensional-pl",
    keywords: ["dimensional", "analytic p&l", "segment", "cost center", "project"],
  },
  {
    id: "rpt:balance-sheet", type: "report", label: "Balance Sheet",
    sub: "Assets, liabilities & equity", href: "/balance",
    keywords: ["bs", "balance sheet", "assets liabilities", "financial position", "output"],
  },
  {
    id: "rpt:consolidation", type: "report", label: "Consolidation",
    sub: "Group statements with eliminations (IFRS 10)", href: "/consolidation",
    keywords: ["consolidation", "ifrs 10", "group", "subsidiary", "nci", "eliminations", "holding"],
  },
  {
    id: "rpt:ic-recon", type: "report", label: "IC Reconciliation",
    sub: "Intercompany AR vs AP by group pair", href: "/intercompany/recon",
    keywords: ["intercompany", "ic", "reconciliation", "affiliates", "due from", "due to"],
  },
  {
    id: "rpt:cash-flow", type: "report", label: "Cash Flow Statement",
    sub: "Cash in & out by activity", href: "/cashflow",
    keywords: ["cash flow", "funds flow", "liquidity", "cash statement", "output"],
  },
  {
    id: "rpt:gl", type: "report", label: "General Ledger",
    sub: "Full account transaction history", href: "/ledger",
    keywords: ["gl", "general ledger", "ledger report", "transaction history", "output"],
  },
  {
    id: "rpt:tax", type: "report", label: "Tax Reports",
    sub: "GST / VAT summary", href: "/tax",
    keywords: ["tax", "gst", "vat", "tax report", "tax summary", "sales tax", "output"],
  },
  {
    id: "rpt:wht", type: "report", label: "Withholding Tax",
    sub: "WHT deducted on vendor payments by period", href: "/reports/wht",
    keywords: ["wht", "withholding", "withholding tax", "tax deducted", "vendor tax"],
  },
  {
    id: "rpt:cit", type: "report", label: "CIT Worksheet",
    sub: "Corporate tax addbacks and estimated tax", href: "/reports/cit-worksheet",
    keywords: ["cit", "corporate tax", "income tax", "addback", "tax worksheet"],
  },
  {
    id: "rpt:gstr", type: "report", label: "GSTR Report",
    sub: "India GST GSTR-1 B2B summary", href: "/india-gst/gstr",
    keywords: ["gstr", "india gst", "cgst", "sgst", "igst", "gstr-1", "place of supply"],
  },
  {
    id: "rpt:aging-ar", type: "report", label: "AR Aging Report",
    sub: "Outstanding customer invoices by age", href: "/aging/receivable",
    keywords: ["aging", "ar aging", "overdue", "receivable aging", "outstanding customers", "analysis"],
  },
  {
    id: "rpt:aging-ap", type: "report", label: "AP Aging Report",
    sub: "Outstanding vendor bills by age", href: "/aging/payable",
    keywords: ["ap aging", "overdue bills", "payable aging", "outstanding vendors", "analysis"],
  },
  {
    id: "rpt:budget", type: "report", label: "Budget vs Actual",
    sub: "Compare budget to actual spend", href: "/budgets",
    keywords: ["budget", "variance", "budget report", "actual vs budget", "analysis"],
  },
  {
    id: "rpt:customer-perf", type: "report", label: "Customer Performance",
    sub: "Revenue by customer", href: "/customer-performance",
    keywords: ["customer analysis", "top customers", "revenue by customer", "customer report", "analysis"],
  },
  {
    id: "rpt:product-ledger", type: "report", label: "Product Ledger",
    sub: "Stock movement history", href: "/products/ledger",
    keywords: ["stock ledger", "inventory movements", "product history", "stock history", "output"],
  },
  {
    id: "rpt:inv-perf", type: "report", label: "Inventory Performance",
    sub: "Stock levels & valuation", href: "/inventory/performance",
    keywords: ["inventory report", "stock report", "stock value", "on hand", "analysis"],
  },
  {
    id: "rpt:report-builder", type: "report", label: "Report Builder",
    sub: "Build custom reports from any table", href: "/reports/builder",
    keywords: ["custom report", "ad hoc", "report builder", "query", "dynamic report", "analysis", "output"],
  },
  {
    id: "rpt:deferred", type: "report", label: "Deferred Revenue",
    sub: "IFRS-15 recognition schedule", href: "/deferred-revenue",
    keywords: ["deferred", "revenue recognition", "ifrs", "subscription revenue", "output"],
  },
  {
    id: "rpt:contract-balances", type: "report", label: "Contract Balances",
    sub: "Contract assets & liabilities by customer", href: "/contract-balances",
    keywords: ["contract asset", "contract liability", "unbilled", "ifrs 15", "ssp", "output"],
  },
  {
    id: "rpt:assets", type: "report", label: "Fixed Assets",
    sub: "Asset register & depreciation", href: "/assets",
    keywords: ["fixed assets", "depreciation", "asset register", "capex", "output"],
  },
  {
    id: "rpt:asset-rollforward", type: "report", label: "Asset Rollforward",
    sub: "Opening / additions / disposals / dep / impairment / closing", href: "/assets/rollforward",
    keywords: ["asset rollforward", "fixed asset movement", "nbv", "impairment", "disposal", "capex", "output"],
  },
  {
    id: "rpt:leases", type: "report", label: "Leases",
    sub: "IFRS 16 RoU assets & lease liability schedule", href: "/leases",
    keywords: ["leases", "ifrs 16", "right of use", "rou", "lease liability", "maturity", "output"],
  },
  {
    id: "rpt:cashbook", type: "report", label: "Cash Book",
    sub: "All cash transactions", href: "/cash-book",
    keywords: ["cash book", "petty cash", "cash transactions", "cash ledger", "output"],
  },
  {
    id: "rpt:bankbook", type: "report", label: "Bank Book",
    sub: "All bank transactions", href: "/bank-book",
    keywords: ["bank book", "bank statement", "bank ledger", "bank transactions", "output"],
  },
  {
    id: "rpt:coa", type: "report", label: "Chart of Accounts",
    sub: "Account hierarchy", href: "/coa",
    keywords: ["coa", "chart of accounts", "accounts list", "account codes", "output"],
  },
  {
    id: "rpt:audit", type: "report", label: "Audit Log",
    sub: "System activity history", href: "/audit",
    keywords: ["audit", "activity log", "history", "who changed", "audit trail", "output"],
  },
  {
    id: "rpt:reconciliation", type: "report", label: "Bank Reconciliation",
    sub: "Match bank statement to ledger", href: "/reconciliations",
    keywords: ["reconcile", "bank reconciliation", "match transactions", "bank match", "analysis"],
  },
  {
    id: "rpt:period-close", type: "report", label: "Period Close",
    sub: "Lock an accounting period", href: "/period-close",
    keywords: ["period close", "close month", "lock period", "fiscal period", "output"],
  },
  {
    id: "rpt:journal-list", type: "report", label: "Journal Listing",
    sub: "Posted vouchers list (printable)", href: "/journal",
    keywords: ["journal report", "voucher list", "jv register", "output"],
  },
  {
    id: "rpt:gate-register", type: "report", label: "Gate Register",
    sub: "Gate inward vehicle / challan register", href: "/purchases/gate-register",
    keywords: ["gate register", "inward register", "vehicle search", "output", "analysis"],
  },
  {
    id: "rpt:three-way", type: "report", label: "3-Way Match",
    sub: "PO vs Gate Inward vs Bill variances", href: "/purchases/three-way-match",
    keywords: ["three way match", "po match", "variance", "analysis", "output"],
  },
  {
    id: "rpt:vendor-perf", type: "report", label: "Vendor Performance",
    sub: "Delivery lead time & rate trends", href: "/purchases/vendor-performance",
    keywords: ["vendor kpi", "supplier score", "analysis"],
  },
  {
    id: "rpt:outward-register", type: "report", label: "Gate Outward Register",
    sub: "Dispatch exit register", href: "/store/gate-outward-register",
    keywords: ["outward register", "dispatch list", "output"],
  },
  {
    id: "rpt:dispatch-recon", type: "report", label: "Dispatch Reconciliation",
    sub: "Posted sales missing a gate exit", href: "/store/dispatch-reconciliation",
    keywords: ["dispatch recon", "missing exit", "analysis"],
  },
  {
    id: "rpt:issue-register", type: "report", label: "Issue Register",
    sub: "Store issue / consumption register", href: "/store/issue-register",
    keywords: ["issue register", "consumption report", "output"],
  },
  {
    id: "rpt:stock-tieout", type: "report", label: "Stock Tie-Out",
    sub: "Product stock reconciliation", href: "/store/stock-tie-out",
    keywords: ["stock tie out", "inventory recon", "analysis"],
  },
  {
    id: "rpt:mfg", type: "report", label: "Manufacturing Reports",
    sub: "WIP aging, production summary, custody", href: "/manufacturing/reports",
    keywords: ["wip", "production summary", "customer custody", "mfg analysis", "analysis", "output"],
  },
  {
    id: "rpt:custody", type: "report", label: "Customer Custody Stock",
    sub: "Goods held for customers", href: "/manufacturing/stock-locations/custody",
    keywords: ["custody", "customer goods", "memo stock", "analysis"],
  },
  {
    id: "rpt:stock-movements", type: "report", label: "Stock Location Movements",
    sub: "Warehouse movement history", href: "/manufacturing/stock-locations/movements",
    keywords: ["location movements", "warehouse transfers", "output"],
  },
  {
    id: "rpt:attendance", type: "report", label: "Attendance Report",
    sub: "Monthly attendance summary", href: "/attendance/report",
    keywords: ["attendance report", "present absent", "hours worked", "analysis", "output"],
  },
  {
    id: "rpt:payroll", type: "report", label: "Payroll Runs",
    sub: "Payroll register and payslips", href: "/payroll",
    keywords: ["payroll report", "payslip", "salary register", "output"],
  },
  {
    id: "rpt:hc", type: "report", label: "Healthcare Reports",
    sub: "OPD, IPD, lab, doctor collections", href: "/healthcare/reports",
    keywords: ["hospital reports", "opd summary", "ipd census", "lab summary", "doctor collections", "analysis", "output"],
  },
  {
    id: "rpt:hc-lab-report", type: "report", label: "Lab Patient Test Report",
    sub: "View and print laboratory results", href: "/healthcare/lab",
    keywords: ["lab report", "test report", "print results", "patient lab results", "pathology report", "output"],
  },
  {
    id: "rpt:wv-daily", type: "report", label: "Weaving Daily Ops",
    sub: "Yarn, grey, efficiency by shift/loom", href: "/weaving/reports/daily",
    keywords: ["daily ops", "weaving daily", "efficiency report", "analysis", "output"],
  },
  {
    id: "rpt:wv-control", type: "report", label: "Contract Control Panel",
    sub: "Per-contract yarn & meter progress", href: "/weaving/reports/contract-control",
    keywords: ["contract control", "yarn balance", "progress panel", "analysis", "output"],
  },
  {
    id: "rpt:wv-kpi", type: "report", label: "Weaving Customer KPI",
    sub: "Meters and revenue by customer", href: "/weaving/reports/customer-kpi",
    keywords: ["weaving kpi", "customer weaving", "analysis", "output"],
  },
  {
    id: "rpt:wv-dash", type: "report", label: "Weaving Dashboard",
    sub: "Unit KPIs and monthly trend", href: "/weaving/dashboard",
    keywords: ["weaving dashboard", "weaving kpis", "analysis", "output"],
  },
  {
    id: "rpt:sp-daily", type: "report", label: "Spinning Daily Register",
    sub: "Stage entries by date", href: "/spinning/reports/daily",
    keywords: ["spinning daily", "daily register", "stage register", "analysis", "output"],
  },
  {
    id: "rpt:sp-lot-control", type: "report", label: "Lot Control Panel",
    sub: "Per-lot bale/cone/yield progress", href: "/spinning/reports/lot-control",
    keywords: ["lot control", "spin lot progress", "analysis", "output"],
  },
  {
    id: "rpt:sp-waste", type: "report", label: "Waste Analysis",
    sub: "Waste by type and stage", href: "/spinning/reports/waste",
    keywords: ["waste analysis", "spinning waste report", "analysis", "output"],
  },
  {
    id: "rpt:sp-dash", type: "report", label: "Spinning Dashboard",
    sub: "Unit KPIs and WIP by stage", href: "/spinning/dashboard",
    keywords: ["spinning dashboard", "spinning kpis", "analysis", "output"],
  },
  {
    id: "rpt:pra-dash", type: "report", label: "PRA Sales Dashboard",
    sub: "Today's invoices and PRA status", href: "/pra-dashboard",
    keywords: ["pra dashboard", "fiscal status", "einvoice summary", "analysis", "output"],
  },
  {
    id: "rpt:pra-logs", type: "report", label: "PRA Submission Logs",
    sub: "Fiscal submission attempts", href: "/pra-logs",
    keywords: ["pra logs", "submission log", "fiscal log", "output"],
  },
  {
    id: "rpt:zatca-logs", type: "report", label: "ZATCA Submission Logs",
    sub: "Saudi Fatoora clear/report attempts", href: "/zatca/logs",
    keywords: ["zatca", "fatoora", "saudi", "einvoice log", "ksa", "output"],
  },
  {
    id: "rpt:peppol-logs", type: "report", label: "Peppol Submission Logs",
    sub: "EU Access Point send attempts", href: "/peppol/logs",
    keywords: ["peppol", "ubl", "bis billing", "eu", "access point", "einvoice log", "output"],
  },
  {
    id: "sys:settings", type: "nav", label: "Settings",
    sub: "Company, accounting & preferences", href: "/settings",
    keywords: ["settings", "preferences", "configuration", "setup", "company settings"],
  },
  {
    id: "sys:settings-updates", type: "nav", label: "Check for Updates",
    sub: "System update settings", href: "/settings?tab=updates",
    keywords: ["update", "version", "upgrade", "patch", "updates tab"],
  },
  {
    id: "sys:settings-accounting", type: "nav", label: "Accounting Settings",
    sub: "Currency, fiscal year, prefixes", href: "/settings?tab=accounting",
    keywords: ["currency", "fiscal year", "invoice prefix", "accounting settings"],
  },
  {
    id: "sys:settings-ai", type: "nav", label: "AI Settings",
    sub: "Provider keys and default model", href: "/settings?tab=advanced",
    keywords: ["ai key", "anthropic", "openai", "gemini", "ollama", "ai settings"],
  },
  {
    id: "sys:team", type: "nav", label: "Team / Users",
    sub: "Manage team members and roles", href: "/team",
    keywords: ["team", "users", "roles", "staff", "members", "access"],
  },
  {
    id: "sys:practice", type: "nav", label: "Practice clients",
    sub: "Switch between companies you can access", href: "/practice",
    keywords: ["practice", "clients", "switch company", "multi client", "accountant"],
  },
  {
    id: "sys:permissions", type: "nav", label: "Permissions",
    sub: "Granular access control matrix", href: "/settings/permissions",
    keywords: ["permissions", "access control", "roles", "rights", "user rights"],
  },
  {
    id: "sys:imports", type: "nav", label: "CSV Import",
    sub: "Import data from spreadsheet", href: "/imports",
    keywords: ["import", "csv", "spreadsheet", "upload data", "bulk import"],
  },
  {
    id: "sys:addons", type: "nav", label: "Add-ons / Modules",
    sub: "Install or remove modules", href: "/apps",
    keywords: ["addons", "modules", "apps", "install module", "extensions"],
  },
  {
    id: "sys:alerts", type: "nav", label: "Alerts",
    sub: "Ops alerts inbox", href: "/alerts",
    keywords: ["alerts", "inbox", "bell", "overdue alert", "low stock alert"],
  },
  {
    id: "sys:guide", type: "nav", label: "User Guide",
    sub: "In-app help documentation", href: "/guide",
    keywords: ["help", "docs", "manual", "how to"],
  },
  {
    id: "sys:approvals", type: "nav", label: "Approvals",
    sub: "Pending approval inbox", href: "/approvals",
    keywords: ["approvals", "approve", "sod", "segregation of duties"],
  },
  {
    id: "bank:rules", type: "nav", label: "Bank Rules",
    sub: "Categorization rules for bank feeds", href: "/bank-imports/rules",
    keywords: ["bank rules", "categorization", "ofx", "statement matching"],
  },
  {
    id: "sys:approval-workflows", type: "nav", label: "Approval Workflows",
    sub: "Configure multi-step approval chains", href: "/approvals/workflows",
    keywords: ["approval workflows", "thresholds", "approver roles"],
  },
  {
    id: "sys:workflow", type: "nav", label: "Workflow",
    sub: "GL posting guide", href: "/workflow",
    keywords: ["gl workflow", "posting guide"],
  },
]

// ── Full combined index (dedupe by href — later layers win for type/label) ────

function mergeIndex(layers: NavResult[][]): NavResult[] {
  const byHref = new Map<string, NavResult>()
  for (const layer of layers) {
    for (const item of layer) {
      const prev = byHref.get(item.href)
      if (!prev) {
        byHref.set(item.href, item)
        continue
      }
      const prefer = item.type !== "nav" || prev.type === "nav"
      byHref.set(item.href, {
        ...(prefer ? item : prev),
        keywords: Array.from(new Set([...prev.keywords, ...item.keywords])),
        label: prefer ? item.label : prev.label,
        sub: prefer ? item.sub : prev.sub,
        type: prefer ? item.type : prev.type,
        id: prefer ? item.id : prev.id,
      })
    }
  }
  return Array.from(byHref.values())
}

const ALL: NavResult[] = mergeIndex([NAV_ITEMS, ACTIONS, REPORTS])

// ── Search function ───────────────────────────────────────────────────────────

export type NavIndexType = NavResult["type"]

/** Browse the index by layer (used when the user types `form:` / `rpt:` alone). */
export function listNavByType(type: NavIndexType, limit = 40): NavResult[] {
  return ALL
    .filter(r => r.type === type)
    .sort((a, b) => a.label.localeCompare(b.label))
    .slice(0, limit)
}

export function searchNav(
  q: string,
  limit = 12,
  opts?: { type?: NavIndexType },
): NavResult[] {
  const lower = q.toLowerCase().trim()
  if (!lower) {
    return opts?.type ? listNavByType(opts.type, limit) : []
  }
  const scored: Array<{ r: NavResult; score: number }> = []
  // Avoid mid-word hits on short tokens ("form" ⊂ "performance")
  const softIncludes = (hay: string) =>
    lower.length >= 5
      ? hay.includes(lower)
      : new RegExp(`(?:^|[^a-z0-9])${lower.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:$|[^a-z0-9])`).test(hay)

  for (const r of ALL) {
    if (opts?.type && r.type !== opts.type) continue

    const labelLower = r.label.toLowerCase()
    const subLower   = r.sub.toLowerCase()
    const hrefLower  = r.href.toLowerCase()

    let score = -1
    if (labelLower === lower) score = 5
    else if (labelLower.startsWith(lower)) score = 4
    else if (softIncludes(labelLower)) score = 3
    else if (r.keywords.some(k => k === lower || k.startsWith(lower))) score = 2
    else if (softIncludes(subLower) || (lower.length >= 5 && hrefLower.includes(lower.replace(/\s+/g, "-")))) score = 1
    else if (r.keywords.some(k => softIncludes(k))) score = 0

    if (score >= 0) scored.push({ r, score })
  }

  return scored
    .sort((a, b) => b.score - a.score || a.r.label.localeCompare(b.r.label))
    .slice(0, limit)
    .map(x => x.r)
}

/** Full index size — useful for tests / diagnostics. */
export function searchIndexSize(): number {
  return ALL.length
}

// ── Prefix map for typed search (e.g. "inv:" → only invoices group) ──────────

export const SEARCH_PREFIXES: Record<string, string> = {
  inv:       "invoices",
  invoice:   "invoices",
  bill:      "bills",
  bills:     "bills",
  cust:      "customers",
  customer:  "customers",
  vend:      "vendors",
  vendor:    "vendors",
  acc:       "accounts",
  account:   "accounts",
  prod:      "products",
  product:   "products",
  emp:       "employees",
  employee:  "employees",
  tx:        "transactions",
  jv:        "transactions",
  pay:       "payments_received",
  payment:   "payments_received",
  cn:        "credit_notes",
  dn:        "debit_notes",
  amt:       "__amount__",
  amount:    "__amount__",
  nav:       "__nav__",
  page:      "__nav__",
  tab:       "__tabs__",
  report:    "__reports__",
  rpt:       "__reports__",
  analysis:  "__reports__",
  output:    "__reports__",
  action:    "__actions__",
  new:       "__actions__",
  form:      "__actions__",
  input:     "__actions__",
}

export { type NavResult as SearchNavResult }
