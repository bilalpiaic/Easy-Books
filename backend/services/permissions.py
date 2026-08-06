"""User Rights Module — permission resolution service.

When user_rights_enabled = "true" in Settings, every request to a protected
route is checked against UserPermission overrides + role defaults.
When the module is off, all perm_dep calls are no-ops (zero behaviour change).
"""
from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from db import get_session
from models import Settings, User, UserPermission

# ── Resource registry ─────────────────────────────────────────────────────────

PERMISSION_RESOURCES: dict[str, dict] = {
    # Dashboard (dual home — Financial / Operations)
    "dashboard.financial":    {"label": "Financial Dashboard",     "category": "Dashboard"},
    "dashboard.operations":   {"label": "Operations Dashboard",    "category": "Dashboard"},
    # Receivable
    "invoices":               {"label": "Sales Invoices",          "category": "Receivable"},
    "credit_notes":           {"label": "Credit Notes",            "category": "Receivable"},
    "payments_received":      {"label": "Payments Received",       "category": "Receivable"},
    "customers":              {"label": "Customers",               "category": "Receivable"},
    "customer_ledger":        {"label": "Customer Ledger",         "category": "Receivable"},
    "commissions":            {"label": "Sales Commissions",       "category": "Receivable"},
    # Payable
    "bills":                  {"label": "Purchase Bills",          "category": "Payable"},
    "debit_notes":            {"label": "Debit Notes",             "category": "Payable"},
    "bill_payments":          {"label": "Bill Payments",           "category": "Payable"},
    "vendors":                {"label": "Vendors",                 "category": "Payable"},
    "vendor_ledger":          {"label": "Vendor Ledger",           "category": "Payable"},
    "advances":               {"label": "Advances",                "category": "Payable"},
    # Ledger
    "journal_entry":          {"label": "Manual Journal Entry",    "category": "Ledger"},
    "recurring":              {"label": "Recurring Templates",     "category": "Ledger"},
    "accounts":               {"label": "Chart of Accounts",       "category": "Ledger"},
    "analytic_accounts":      {"label": "Analytic Accounts",       "category": "Ledger"},
    # Inventory
    "products":               {"label": "Products",                "category": "Inventory"},
    "product_categories":     {"label": "Product Categories",      "category": "Inventory"},
    # Manufacturing
    "bom":                    {"label": "Bills of Material",       "category": "Manufacturing"},
    "rate_plans":             {"label": "Rate Plans",              "category": "Manufacturing"},
    "purchase_orders":        {"label": "Purchase Orders",         "category": "Manufacturing"},
    "purchase.demand":        {"label": "Purchase Demands",        "category": "Purchasing"},
    "purchase.comparative":   {"label": "Comparative Statements",  "category": "Purchasing"},
    "purchase.gate":          {"label": "Gate Inward",             "category": "Purchasing"},
    "store.gate_outward":     {"label": "Gate Outward",            "category": "Store"},
    "store.issue":            {"label": "Store Issue",             "category": "Store"},
    # Point of Sale (#304)
    "pos.register":           {"label": "POS Registers",           "category": "POS"},
    "pos.shift":              {"label": "POS Shifts",              "category": "POS"},
    "pos.sale":               {"label": "POS Sales",               "category": "POS"},
    "grn":                    {"label": "Goods Receipt Notes",     "category": "Manufacturing"},
    "production_orders":      {"label": "Production Orders",       "category": "Manufacturing"},
    "stock_locations":        {"label": "Stock Locations",         "category": "Manufacturing"},
    "inventory.transfer":     {"label": "Stock Transfers",         "category": "Inventory"},
    "report.stock_by_warehouse": {"label": "Stock by Warehouse",   "category": "Reports"},
    # Banking
    "bank_accounts":          {"label": "Bank Accounts",           "category": "Banking"},
    "exchange_rates":         {"label": "Exchange Rates",          "category": "Banking"},
    "bank_imports":           {"label": "Bank Imports",            "category": "Banking"},
    "reconciliations":        {"label": "Reconciliations",         "category": "Banking"},
    # Reports & System
    "assets":                 {"label": "Fixed Assets",            "category": "Reports"},
    "leases":                 {"label": "Leases (IFRS 16)",         "category": "Reports"},
    "budgets":                {"label": "Budgets",                 "category": "Reports"},
    "deferred_revenue":       {"label": "Deferred Revenue",        "category": "Reports"},
    "tax_codes":              {"label": "Tax Codes",               "category": "Reports"},
    "payment_terms":          {"label": "Payment Terms",           "category": "System"},
    "period_close":           {"label": "Period Close",            "category": "System"},
    "consolidation":          {"label": "Consolidation",           "category": "Reports"},
    "approvals":              {"label": "Approvals Inbox",         "category": "System"},
    "approvals.workflows":    {"label": "Approval Workflows",      "category": "System"},
    "webhooks":               {"label": "Webhooks",                "category": "System"},
    "audit_log":              {"label": "Audit Log",               "category": "System"},
    "csv_import":             {"label": "CSV Import",              "category": "System"},
    "report_builder":         {"label": "Report Builder",          "category": "Reports"},
    "report.trial_balance":   {"label": "Trial Balance",           "category": "Reports"},
    "report.income_statement":{"label": "Income Statement",        "category": "Reports"},
    "report.balance_sheet":   {"label": "Balance Sheet",           "category": "Reports"},
    "report.cash_flow":       {"label": "Cash Flow",               "category": "Reports"},
    "report.general_ledger":  {"label": "General Ledger",          "category": "Reports"},
    "report.ar_aging":        {"label": "AR Aging",                "category": "Reports"},
    "report.ap_aging":        {"label": "AP Aging",                "category": "Reports"},
    "report.customer_performance": {"label": "Customer Performance", "category": "Reports"},
    "report.inventory_performance": {"label": "Inventory Performance", "category": "Reports"},
    "report.tax":             {"label": "Tax Reports",             "category": "Reports"},
    "report.budget_vs_actual":{"label": "Budget vs Actual",        "category": "Reports"},
    "report.product_ledger":  {"label": "Product Ledger",          "category": "Reports"},
    # Telecom
    "telecom.tracker":        {"label": "Tracker & Load",          "category": "Telecom"},
    "telecom.rso":            {"label": "RSO Channel",             "category": "Telecom"},
    "telecom.sim":            {"label": "SIM & Activations",       "category": "Telecom"},
    "telecom.fca":            {"label": "FCA & Targets",           "category": "Telecom"},
    "telecom.mobile_money":   {"label": "Mobile Money",            "category": "Telecom"},
    "telecom.postpaid":       {"label": "Postpaid Billing",        "category": "Telecom"},
    "telecom.commissions":    {"label": "Commissions",             "category": "Telecom"},
    "telecom.franchise":      {"label": "Franchise Admin",         "category": "Telecom"},
    "telecom.devices":        {"label": "Devices (IMEI)",          "category": "Telecom"},
    # Payroll
    "employees":              {"label": "Employees",              "category": "Payroll"},
    "payroll":                {"label": "Payroll Runs",           "category": "Payroll"},
    "payroll.components":     {"label": "Salary Components",      "category": "Payroll"},
    "attendance":             {"label": "Attendance Register",    "category": "Payroll"},
    "leave":                  {"label": "Leave",                   "category": "Payroll"},
    # Healthcare
    "healthcare.patients":    {"label": "Patients",              "category": "Healthcare"},
    "healthcare.opd":         {"label": "OPD / Outpatient",      "category": "Healthcare"},
    "healthcare.ipd":         {"label": "IPD / Inpatient",       "category": "Healthcare"},
    "healthcare.lab":         {"label": "Laboratory",            "category": "Healthcare"},
    "healthcare.procedures":  {"label": "Procedures & Services", "category": "Healthcare"},
    "healthcare.dialysis":    {"label": "Dialysis Unit",         "category": "Healthcare"},
    "healthcare.store":       {"label": "Hospital Store",        "category": "Healthcare"},
    "healthcare.reports":     {"label": "Healthcare Reports",    "category": "Healthcare"},
    # Weaving (#140)
    "weaving.setup":          {"label": "Weaving Setup",         "category": "Weaving"},
    "weaving.contracts":      {"label": "Weaving Contracts",     "category": "Weaving"},
    "weaving.yarn_inward":    {"label": "Yarn Inward",           "category": "Weaving"},
    "weaving.sizing":         {"label": "Sizing",                "category": "Weaving"},
    "weaving.production":     {"label": "Weaving Production",    "category": "Weaving"},
    "weaving.dispatch":       {"label": "Weaving Dispatch",      "category": "Weaving"},
    "weaving.calculators":    {"label": "Weaving Calculators",   "category": "Weaving"},
    "weaving.reports":        {"label": "Weaving Reports",       "category": "Weaving"},
    "spinning.setup":         {"label": "Spinning Setup",        "category": "Spinning"},
    "spinning.plans":         {"label": "Production Plans",      "category": "Spinning"},
    "spinning.lots":          {"label": "Spin Lots",             "category": "Spinning"},
    "spinning.bale_receipt":  {"label": "Bale Receipt",          "category": "Spinning"},
    "spinning.stages":        {"label": "Stage Entries",         "category": "Spinning"},
    "spinning.cone_output":   {"label": "Cone Output",           "category": "Spinning"},
    "spinning.waste":         {"label": "Waste Log",             "category": "Spinning"},
    "spinning.dispatch":      {"label": "Yarn Dispatch",         "category": "Spinning"},
    "spinning.calculators":   {"label": "Spinning Calculators",  "category": "Spinning"},
    "spinning.reports":       {"label": "Spinning Reports",      "category": "Spinning"},
    # Textile Processing (ballor)
    "textile.setup":          {"label": "Processing Setup",      "category": "Processing"},
    "textile.sales_orders":   {"label": "Processing Sales Orders","category": "Processing"},
    "textile.lots":           {"label": "Grey Lots / Parchis",    "category": "Processing"},
    "textile.mending":        {"label": "Mending",               "category": "Processing"},
    "textile.rejection":      {"label": "Rejection / OGP",       "category": "Processing"},
    "textile.production":     {"label": "Production Orders",     "category": "Processing"},
    "textile.stages":         {"label": "PPC Stages",            "category": "Processing"},
    "textile.dispatch":       {"label": "Fresh Dispatch",        "category": "Processing"},
    "textile.labor":          {"label": "Contractor Labor",      "category": "Processing"},
    "textile.settlement":     {"label": "Grey Settlement",       "category": "Processing"},
    "textile.inspection":     {"label": "RM Inspection",         "category": "Processing"},
    "textile.reports":        {"label": "Processing Reports",    "category": "Processing"},
}

# Role defaults: owner/admin/accountant → edit, viewer → view
_ROLE_DEFAULT: dict[str, str] = {
    "owner":       "edit",
    "admin":       "edit",
    "accountant":  "edit",
    "viewer":      "view",
}


def _rights_enabled(tenant_id: int, session: Session) -> bool:
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id,
            Settings.key == "user_rights_enabled",
        )
    ).first()
    return (row.value if row else "false") == "true"


def get_effective_permission(user: User, resource_key: str, session: Session) -> str:
    """Returns 'none' | 'view' | 'edit'. Falls back to role default when no override row.

    Overrides are tenant-scoped (#299) so a practice user can have different
    rights on each client company.
    """
    override = session.exec(
        select(UserPermission).where(
            UserPermission.tenant_id == user.tenant_id,
            UserPermission.user_id == user.id,
            UserPermission.resource_key == resource_key,
        )
    ).first()
    if override:
        return override.access_level
    return _ROLE_DEFAULT.get(user.role, "view")


def perm_dep(resource_key: str, level: str = "view"):
    """FastAPI Depends factory.

    Usage:
      router = APIRouter(dependencies=[perm_dep("invoices")])         # view gate
      @router.post("", dependencies=[perm_dep("invoices", "edit")])   # write gate

    When the module is off (default), resolves immediately without DB lookup.
    When on, enforces the specified level or raises 403.
    """
    from routers.common import get_current_user  # lazy import avoids circular

    async def _dep(
        user: User = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> None:
        if not _rights_enabled(user.tenant_id, session):
            return
        effective = get_effective_permission(user, resource_key, session)
        label = PERMISSION_RESOURCES.get(resource_key, {}).get("label", resource_key)
        if level == "view" and effective == "none":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have access to '{label}'.",
            )
        if level == "edit" and effective in ("none", "view"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"'{label}' is view-only for your account.",
            )

    return Depends(_dep)


def apply_own_filter(query, model_class, user: User, session: Session):
    """Restrict a SQLModel select() to rows created by `user` when My Data Only is on.

    Admins and owners bypass the filter. Non-posted models (no created_by_id) are
    returned unmodified.
    """
    if user.role in ("admin", "owner"):
        return query
    if not user.my_data_only:
        return query
    if not _rights_enabled(user.tenant_id, session):
        return query
    if not hasattr(model_class, "created_by_id"):
        return query
    return query.where(model_class.created_by_id == user.id)
