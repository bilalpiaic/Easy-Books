"""Declarative registry of AI chat specialist agents — the routing
capability boundary for the triage ("Boss") stage.

Mirrors services/report_sources's pattern: a frozen, key-based registry that
is the actual capability boundary (an unknown/unparseable triage response
always falls back to "general", never a hard failure). Each entry is
pre-equipped with its own tool subset (drawn from ai_chat.py's TOOLS) and a
system-prompt fragment describing its domain — so the specialist stage runs
with a narrow, focused prompt instead of the current one-size-fits-all
prompt bound to all 7 tools on every turn.

Base agents (required_module=None) cover Receivables, Payables, Financial
Reports, Sales & Customers, Banking, Deferred Revenue, Staff Commissions,
Fixed Assets, Leases, Consolidation/IC, plus a General fallback.
`required_module` gates module-specific agents (inventory, hrm, healthcare,
telecom, purchasing/store, manufacturing, weaving, spinning, textile_proc,
pra + localization packs) to tenants with that module installed — adding a
domain agent is a new registry entry (tools from TOOL_REGISTRY), not a
pipeline change.

Invariants (enforced by tests + the import-time assert below): every name in
an AgentDef.tools must exist in TOOL_REGISTRY, and no agent key may be a
substring of another (triage's fallback matcher is substring-based).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDef:
    key: str
    label: str                      # shown in the chat's stage-progress label
    trigger_hint: str                # one-line description fed to the triage prompt
    system_prompt_fragment: str      # appended to the base system prompt
    tools: tuple[str, ...]           # subset of ai_tools.TOOL_REGISTRY names this agent may call
    required_module: str | None = None  # None = always offered once ai_assistant is installed


AGENTS: dict[str, AgentDef] = {
    "receivables": AgentDef(
        key="receivables",
        label="Receivables Agent",
        trigger_hint=(
            "Who owes the business money: outstanding/overdue customer invoices, AR aging, "
            "a specific customer's statement or ledger balance."
        ),
        system_prompt_fragment=(
            "You specialize in Accounts Receivable. Use get_ar_aging and get_top_customers to "
            "answer questions about who owes the business money, overdue invoices, and customer "
            "balances. For a specific customer's account, resolve their id with find_customer, "
            "then use get_customer_statement or get_customer_ledger. Use get_dashboard_summary "
            "only if you need a quick cross-check of the overall AR total."
        ),
        tools=(
            "get_ar_aging", "get_top_customers", "get_dashboard_summary",
            "find_customer", "get_customer_statement", "get_customer_ledger",
        ),
    ),
    "payables": AgentDef(
        key="payables",
        label="Payables Agent",
        trigger_hint=(
            "What the business owes vendors: outstanding/overdue bills, AP aging, a specific "
            "vendor's statement or ledger balance."
        ),
        system_prompt_fragment=(
            "You specialize in Accounts Payable. Use get_ap_aging to answer questions about what "
            "the business owes vendors and which bills are overdue. For a specific vendor's "
            "account, resolve their id with find_vendor, then use get_vendor_statement or "
            "get_vendor_ledger. Use get_dashboard_summary only if you need a quick cross-check "
            "of the overall AP total."
        ),
        tools=(
            "get_ap_aging", "get_dashboard_summary",
            "find_vendor", "get_vendor_statement", "get_vendor_ledger",
        ),
    ),
    "financial_reports": AgentDef(
        key="financial_reports",
        label="Financial Reports Agent",
        trigger_hint=(
            "Overall financial statements and position: profit & loss / income statement, "
            "balance sheet, trial balance, cash flow, tax summary, budget vs actual, net worth, "
            "revenue, expenses, profit, account balances, analytic/cost-center P&L, journal report."
        ),
        system_prompt_fragment=(
            "You specialize in financial statements and performance. Use get_income_statement, "
            "get_balance_sheet, get_trial_balance, and get_cash_flow for statements; "
            "get_tax_summary for tax collected/paid; get_budget_vs_actual for budget variance; "
            "get_net_worth_trend for the assets/liabilities/net-worth trajectory; "
            "get_account_ledger / get_day_book / get_journal_report for GL detail; "
            "find_analytic_account + get_analytic_pl for cost-center P&L."
        ),
        tools=(
            "get_income_statement", "get_balance_sheet", "get_trial_balance", "get_cash_flow",
            "get_tax_summary", "get_budget_vs_actual", "get_net_worth_trend",
            "get_dashboard_summary", "list_report_sources", "run_custom_report",
            "get_account_ledger", "get_day_book", "get_journal_report",
            "get_analytic_pl", "find_analytic_account", "find_account",
        ),
    ),
    "sales": AgentDef(
        key="sales",
        label="Sales & Customers Agent",
        trigger_hint=(
            "Sales analysis and customer performance: revenue per customer, best/top customers, "
            "sales trends, how much a customer bought — NOT who owes money (that is receivables)."
        ),
        system_prompt_fragment=(
            "You specialize in sales and customer analysis. Use get_customer_performance for "
            "per-customer invoiced/received/outstanding figures, get_top_customers for rankings "
            "and revenue trend, and find_customer to resolve a customer name to an id when "
            "drilling into one customer (get_customer_statement / get_customer_ledger)."
        ),
        tools=(
            "get_customer_performance", "get_top_customers", "find_customer",
            "get_customer_statement", "get_customer_ledger", "get_dashboard_summary",
            "create_draft_invoice",
        ),
    ),
    "banking": AgentDef(
        key="banking",
        label="Banking & Cash Agent",
        trigger_hint=(
            "Cash and bank: day book, cash book / bank book / account ledger for cash or bank "
            "accounts, cash/bank sub-ledger, linked bank account balances."
        ),
        system_prompt_fragment=(
            "You specialize in cash and banking. Use get_day_book for one day's voucher activity, "
            "list_bank_accounts for linked bank balances, get_cash_bank_subledger for the cash/"
            "bank control reconciliation, and find_account + get_account_ledger for a specific "
            "cash or bank GL account's movements."
        ),
        tools=(
            "get_day_book", "get_account_ledger", "get_cash_bank_subledger",
            "list_bank_accounts", "find_account", "get_dashboard_summary",
        ),
    ),
    "deferred_rev": AgentDef(
        key="deferred_rev",
        label="Deferred Revenue Agent",
        trigger_hint=(
            "Deferred revenue / IFRS-15 recognition schedules: unearned revenue, recognition "
            "status, remaining deferred balances."
        ),
        system_prompt_fragment=(
            "You specialize in deferred revenue. Use list_deferred_schedules to inspect active "
            "and completed recognition schedules. Do not attempt to run recognition — that is "
            "a write action outside your tools."
        ),
        tools=("list_deferred_schedules",),
    ),
    "staff_commissions": AgentDef(
        key="staff_commissions",
        label="Staff Commissions Agent",
        trigger_hint=(
            "Staff sales commissions (internal sales team, not franchise channel commissions): "
            "commission plans, ledger periods, amounts payable to sales staff."
        ),
        system_prompt_fragment=(
            "You specialize in staff sales commissions (base feature — not franchise channel). "
            "Use list_commission_plans for rate/target plans and get_commission_ledger for "
            "period commission amounts. Franchise-channel commissions belong to the franchise "
            "operations specialist."
        ),
        tools=("get_commission_ledger", "list_commission_plans"),
    ),
    "fixed_assets": AgentDef(
        key="fixed_assets",
        label="Fixed Assets Agent",
        trigger_hint=(
            "Fixed assets register: asset cost, accumulated depreciation, net book value, "
            "acquisition dates, asset rollforward — not inventory stock."
        ),
        system_prompt_fragment=(
            "You specialize in the fixed-asset register. Use list_fixed_assets for active "
            "(non-disposed) assets with cost and book value, and get_asset_rollforward for "
            "period movements. Do not attempt depreciation or disposal — those are write "
            "actions outside your tools."
        ),
        tools=("list_fixed_assets", "get_asset_rollforward"),
    ),
    "leases": AgentDef(
        key="leases",
        label="Leases Agent",
        trigger_hint=(
            "IFRS 16 leases: lease contracts, right-of-use assets, lease liability, "
            "maturity analysis — not ordinary rental invoices."
        ),
        system_prompt_fragment=(
            "You specialize in IFRS 16 leases. Use list_leases for the contract register and "
            "get_lease_maturity for liability maturity. If leases are disabled for the tenant, "
            "say so clearly. Do not create or terminate leases."
        ),
        tools=("list_leases", "get_lease_maturity"),
    ),
    "consol": AgentDef(
        key="consol",
        label="Consolidation Agent",
        trigger_hint=(
            "Group consolidation and intercompany: consolidation runs, consolidated "
            "statements, eliminations, IC counterparties, IC AR/AP recon (IFRS 10)."
        ),
        system_prompt_fragment=(
            "You specialize in IFRS 10 consolidation worksheets and intercompany recon. "
            "Use list_consol_runs, then get_consol_statements / get_consol_elims for a run. "
            "Use get_ic_counterparties and get_ic_recon for affiliate AR/AP matching. "
            "Eliminations never post to member GLs — explain that if asked."
        ),
        tools=(
            "list_consol_runs", "get_consol_statements", "get_consol_elims",
            "get_ic_counterparties", "get_ic_recon",
        ),
    ),
    "inventory": AgentDef(
        key="inventory",
        label="Inventory Agent",
        trigger_hint=(
            "Stock and products: on-hand quantities, stock valuation, product movement/ledger, "
            "inventory turnover, low stock, product performance."
        ),
        system_prompt_fragment=(
            "You specialize in inventory and products. Use get_product_valuation for the "
            "closing-stock valuation tree, get_inventory_performance / get_product_performance "
            "for movement and turnover, and find_product + get_product_ledger to trace one "
            "product's movements."
        ),
        tools=(
            "get_product_valuation", "get_inventory_performance", "get_product_performance",
            "find_product", "get_product_ledger", "get_dashboard_summary",
        ),
        required_module="inventory",
    ),
    "payroll": AgentDef(
        key="payroll",
        label="Payroll & HR Agent",
        trigger_hint=(
            "Employees, payroll, salaries, and attendance: headcount, payroll runs, salary "
            "totals, who was present/absent."
        ),
        system_prompt_fragment=(
            "You specialize in HR and payroll. Use get_hrm_summary for headcount and payroll "
            "KPIs, get_attendance_summary for a month's per-employee attendance, and "
            "find_employee to resolve an employee name to their record."
        ),
        tools=("get_hrm_summary", "get_attendance_summary", "find_employee"),
        required_module="hrm",
    ),
    "healthcare": AgentDef(
        key="healthcare",
        label="Healthcare Agent",
        trigger_hint=(
            "Hospital operations: patients, OPD visits, admissions/IPD, beds, lab orders, "
            "doctor collections, hospital revenue."
        ),
        system_prompt_fragment=(
            "You specialize in hospital operations. Use get_healthcare_dashboard for today's "
            "KPIs, get_opd_summary / get_doctor_collections / get_lab_summary / get_ipd_census "
            "for period reports, get_hc_revenue_by_type for the revenue split, and "
            "find_patient + get_patient_statement for one patient's account."
        ),
        tools=(
            "get_healthcare_dashboard", "get_opd_summary", "get_doctor_collections",
            "get_lab_summary", "get_ipd_census", "get_hc_revenue_by_type",
            "find_patient", "get_patient_statement",
        ),
        required_module="healthcare",
    ),
    "telecom": AgentDef(
        key="telecom",
        label="Telecom Agent",
        trigger_hint=(
            "Telecom franchise: load/tracker balances, SIM stock and activations, RSO agents, "
            "commissions, mobile-money float, FCA targets, postpaid book, tracker statement."
        ),
        system_prompt_fragment=(
            "You specialize in the telecom franchise business. Use get_telecom_dashboard for "
            "headline KPIs, get_commission_aging for commission receivables, "
            "get_float_statement for mobile-money reconciliation, get_sim_utilisation and "
            "get_stock_issuance for SIM/load movement, get_revenue_by_stream for the revenue "
            "split, get_fca_target_progress for targets, get_postpaid_book / "
            "get_tracker_statement for postpaid and wallet detail, and find_rso + "
            "get_rso_ledger for a specific agent's position."
        ),
        tools=(
            "get_telecom_dashboard", "get_commission_aging", "get_float_statement",
            "get_sim_utilisation", "get_revenue_by_stream", "get_fca_target_progress",
            "get_stock_issuance", "find_rso", "get_rso_ledger",
            "get_postpaid_book", "get_tracker_statement",
        ),
        required_module="telecom",
    ),
    "purchasing": AgentDef(
        key="purchasing",
        label="Purchasing Agent",
        trigger_hint=(
            "Purchasing chain: gate inward receipts, goods received vs ordered vs billed "
            "(3-way match), vendor delivery performance — NOT store issues or gate outward "
            "(those are store_ops)."
        ),
        system_prompt_fragment=(
            "You specialize in the purchase chain. Use get_gate_register for gate inward "
            "receipts, get_three_way_match for PO vs received vs billed variances, and "
            "get_purchase_vendor_performance (with find_vendor) for vendor delivery metrics. "
            "Store issues, gate outward, and dispatch reconciliation belong to the Store Agent."
        ),
        tools=(
            "get_gate_register", "get_three_way_match", "get_purchase_vendor_performance",
            "find_vendor",
        ),
        required_module="purchase_store",
    ),
    "store_ops": AgentDef(
        key="store_ops",
        label="Store Agent",
        trigger_hint=(
            "Store operations: gate outward / dispatch exit, store issues (departmental "
            "consumption), dispatch reconciliation, stock tie-out — NOT purchase gate inward "
            "or 3-way match (those are purchasing)."
        ),
        system_prompt_fragment=(
            "You specialize in store operations. Use get_gate_outward_register for dispatch "
            "exits, get_dispatch_reconciliation for un-exited dispatches, get_issue_register "
            "for departmental consumption, and get_stock_tie_out for stock reconciliation."
        ),
        tools=(
            "get_gate_outward_register", "get_dispatch_reconciliation",
            "get_issue_register", "get_stock_tie_out",
        ),
        required_module="purchase_store",
    ),
    "manufacturing": AgentDef(
        key="manufacturing",
        label="Manufacturing Agent",
        trigger_hint=(
            "Production: production orders, work in progress (WIP), production output and "
            "billing, customer custody stock."
        ),
        system_prompt_fragment=(
            "You specialize in manufacturing. Use get_manufacturing_dashboard for pipeline "
            "KPIs, get_wip_aging for open orders by age, get_production_summary for period "
            "output and billed revenue, get_customer_custody for goods held for customers, "
            "and get_scrap_by_reason for scrap analysis."
        ),
        tools=(
            "get_manufacturing_dashboard", "get_wip_aging", "get_production_summary",
            "get_customer_custody", "get_scrap_by_reason",
        ),
        required_module="production",
    ),
    "weaving": AgentDef(
        key="weaving",
        label="Weaving Ops Agent",
        trigger_hint=(
            "Weaving unit: yarn inward/sizing/production/dispatch, contract control, daily "
            "ops, customer weaving KPIs, efficiency (Kg/Lbs/Bags)."
        ),
        system_prompt_fragment=(
            "You specialize in weaving unit control. Use get_weaving_dashboard for headline "
            "KPIs, get_weaving_daily for period activity and efficiency breakdowns, "
            "get_weaving_customer_kpi for per-customer rollups, and find_wv_contract + "
            "get_contract_control for one contract's yarn/meter progress."
        ),
        tools=(
            "get_weaving_dashboard", "get_weaving_daily", "get_contract_control",
            "get_weaving_customer_kpi", "find_wv_contract",
        ),
        required_module="weaving",
    ),
    "spinning": AgentDef(
        key="spinning",
        label="Spinning Ops Agent",
        trigger_hint=(
            "Yarn spinning mill: bale receipt, spin lots, stage entries, cone output, "
            "waste analysis, cost per kg, yarn dispatch, WIP/yield KPIs (Kg/Lbs/Bags)."
        ),
        system_prompt_fragment=(
            "You specialize in yarn spinning mill operations. Use get_spinning_dashboard for "
            "headline KPIs, get_spinning_daily for the daily register, get_lot_control for one "
            "lot's progress, get_spinning_waste / get_spinning_cost_per_kg / get_spinning_dispatch "
            "for waste, costing, and dispatch."
        ),
        tools=(
            "get_spinning_dashboard", "get_spinning_daily", "get_lot_control",
            "get_spinning_waste", "get_spinning_cost_per_kg", "get_spinning_dispatch",
        ),
        required_module="spinning",
    ),
    "textile_proc": AgentDef(
        key="textile_proc",
        label="Textile Processing Agent",
        trigger_hint=(
            "Textile processing / ballor / jobber unit: grey lots, mending, kachi/pakki parchi, "
            "PPC stages, rejection register, customer stock ledger, fresh dispatch, settlements."
        ),
        system_prompt_fragment=(
            "You specialize in textile processing (customer-owned grey fabric). Use "
            "get_tp_lot_register for lots, find_tp_lot before lot-scoped questions, "
            "get_tp_rejection_register / get_tp_stock_ledger / get_tp_ppc_stage for reports. "
            "Customer goods are custody (1210/2150), not inventory valuation."
        ),
        tools=(
            "get_tp_lot_register", "get_tp_rejection_register", "get_tp_stock_ledger",
            "get_tp_ppc_stage", "find_tp_lot",
        ),
        required_module="textile_processing",
    ),
    "pra_status": AgentDef(
        key="pra_status",
        label="PRA Compliance Agent",
        trigger_hint=(
            "PRA e-invoice compliance (Punjab Revenue Authority): submission status, fiscal "
            "numbers, submission logs, today's submitted/pending/failed counts."
        ),
        system_prompt_fragment=(
            "You specialize in PRA e-invoice compliance. Use get_pra_today_summary for "
            "status buckets in a date window, get_pra_logs for recent submission attempts, "
            "and get_invoice_pra_status for one invoice's fiscal number / status. Do not "
            "attempt to submit or retry — those are write actions outside your tools."
        ),
        tools=("get_pra_logs", "get_invoice_pra_status", "get_pra_today_summary"),
        required_module="pra",
    ),
    "zatca_status": AgentDef(
        key="zatca_status",
        label="ZATCA Compliance Agent",
        trigger_hint=(
            "Saudi ZATCA e-invoice compliance: submission logs, invoice ZATCA status, UUID/QR."
        ),
        system_prompt_fragment=(
            "You specialize in ZATCA e-invoice compliance. Use get_zatca_logs and "
            "get_invoice_zatca_status. Do not submit or clear invoices."
        ),
        tools=("get_zatca_logs", "get_invoice_zatca_status"),
        required_module="sa_zatca",
    ),
    "peppol_status": AgentDef(
        key="peppol_status",
        label="Peppol Compliance Agent",
        trigger_hint=(
            "Peppol / EU e-invoice compliance: submission logs, invoice Peppol status."
        ),
        system_prompt_fragment=(
            "You specialize in Peppol e-invoice compliance. Use get_peppol_logs and "
            "get_invoice_peppol_status. Do not submit invoices."
        ),
        tools=("get_peppol_logs", "get_invoice_peppol_status"),
        required_module="eu_peppol",
    ),
    "uae_einvoice": AgentDef(
        key="uae_einvoice",
        label="UAE e-Invoice Agent",
        trigger_hint=(
            "UAE VAT e-invoice compliance: submission logs and per-invoice UAE status."
        ),
        system_prompt_fragment=(
            "You specialize in UAE e-invoice compliance. Use get_uae_logs and "
            "get_invoice_uae_status. Do not submit invoices."
        ),
        tools=("get_uae_logs", "get_invoice_uae_status"),
        required_module="uae_vat",
    ),
    "india_gst": AgentDef(
        key="india_gst",
        label="India GST Agent",
        trigger_hint=(
            "India GST returns: GSTR-1 and GSTR-3B summaries for a date window."
        ),
        system_prompt_fragment=(
            "You specialize in India GST reporting. Use get_gstr1 and get_gstr3b with "
            "explicit start/end dates. Do not file returns."
        ),
        tools=("get_gstr1", "get_gstr3b"),
        required_module="in_gst",
    ),
    "general": AgentDef(
        key="general",
        label="Assistant",
        trigger_hint=(
            "Anything that doesn't clearly match one specific domain above — general questions, "
            "small talk, operations overview, or ambiguous/multi-topic requests."
        ),
        system_prompt_fragment=(
            "For questions no dedicated report tool answers, you can query raw records with "
            "run_custom_report — call list_report_sources first to see valid sources and fields. "
            "Use get_operations_summary for a cross-module ops KPI bag when the question is broad."
        ),
        tools=(
            "get_dashboard_summary", "get_income_statement", "get_ar_aging", "get_ap_aging",
            "get_trial_balance", "get_cash_flow", "get_top_customers",
            "list_report_sources", "run_custom_report",
            "list_agent_suggestions", "get_operations_summary",
        ),
    ),
    "data_entry": AgentDef(
        key="data_entry",
        label="Data Entry",
        trigger_hint="Assisted data entry, correcting customer details, OCR / receipt capture requests.",
        system_prompt_fragment=(
            "You help with careful write operations. Prefer find_customer before update_customer_email. "
            "Never invent IDs. Confirm destructive or financial writes with the user first."
        ),
        tools=(
            "find_customer", "update_customer_email", "create_draft_invoice",
            "list_agent_suggestions", "get_dashboard_summary",
        ),
    ),
}

FALLBACK_AGENT_KEY = "general"


def available_agents(installed_modules: set[str]) -> dict[str, AgentDef]:
    """Registry entries usable by this tenant right now — filters out any
    agent whose required_module isn't installed."""
    return {
        key: agent
        for key, agent in AGENTS.items()
        if agent.required_module is None or agent.required_module in installed_modules
    }


# A tool name that isn't in TOOL_REGISTRY would be silently dropped when the
# specialist's tool subset is built — fail loudly at import instead.
from services.ai_tools import TOOL_REGISTRY as _TOOL_REGISTRY  # noqa: E402

for _agent in AGENTS.values():
    _unknown = set(_agent.tools) - _TOOL_REGISTRY.keys()
    assert not _unknown, f"agent {_agent.key!r} references unknown tools: {sorted(_unknown)}"
