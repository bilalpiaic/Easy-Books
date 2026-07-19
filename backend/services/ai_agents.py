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
Reports, and Sales & Customers, plus a General fallback bound to the original
7 tools. `required_module` gates module-specific agents to tenants with that
module installed — adding a domain agent is a new registry entry (tools come
from services/ai_tools.TOOL_REGISTRY), not a pipeline change.

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
            "revenue, expenses, profit, account balances."
        ),
        system_prompt_fragment=(
            "You specialize in financial statements and performance. Use get_income_statement, "
            "get_balance_sheet, get_trial_balance, and get_cash_flow for statements; "
            "get_tax_summary for tax collected/paid; get_budget_vs_actual for budget variance; "
            "get_net_worth_trend for the assets/liabilities/net-worth trajectory."
        ),
        tools=(
            "get_income_statement", "get_balance_sheet", "get_trial_balance", "get_cash_flow",
            "get_tax_summary", "get_budget_vs_actual", "get_net_worth_trend",
            "get_dashboard_summary", "list_report_sources", "run_custom_report",
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
            "commissions, mobile-money float, FCA targets."
        ),
        system_prompt_fragment=(
            "You specialize in the telecom franchise business. Use get_telecom_dashboard for "
            "headline KPIs, get_commission_aging for commission receivables, "
            "get_float_statement for mobile-money reconciliation, get_sim_utilisation and "
            "get_stock_issuance for SIM/load movement, get_revenue_by_stream for the revenue "
            "split, get_fca_target_progress for targets, and find_rso + get_rso_ledger for a "
            "specific agent's position."
        ),
        tools=(
            "get_telecom_dashboard", "get_commission_aging", "get_float_statement",
            "get_sim_utilisation", "get_revenue_by_stream", "get_fca_target_progress",
            "get_stock_issuance", "find_rso", "get_rso_ledger",
        ),
        required_module="telecom",
    ),
    "purchasing": AgentDef(
        key="purchasing",
        label="Purchasing & Store Agent",
        trigger_hint=(
            "Purchasing chain and store: gate inward/outward, goods received vs ordered vs "
            "billed (3-way match), store issues, dispatch reconciliation, vendor delivery "
            "performance."
        ),
        system_prompt_fragment=(
            "You specialize in the purchase and store chain. Use get_gate_register / "
            "get_gate_outward_register for gate movement, get_three_way_match for PO vs "
            "received vs billed variances, get_dispatch_reconciliation for un-exited "
            "dispatches, get_issue_register for departmental consumption, get_stock_tie_out "
            "for stock reconciliation, and get_purchase_vendor_performance (with find_vendor) "
            "for vendor delivery metrics."
        ),
        tools=(
            "get_gate_register", "get_three_way_match", "get_purchase_vendor_performance",
            "get_gate_outward_register", "get_dispatch_reconciliation", "get_issue_register",
            "get_stock_tie_out", "find_vendor",
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
            "output and billed revenue, and get_customer_custody for goods held for customers."
        ),
        tools=(
            "get_manufacturing_dashboard", "get_wip_aging", "get_production_summary",
            "get_customer_custody",
        ),
        required_module="production",
    ),
    "general": AgentDef(
        key="general",
        label="Assistant",
        trigger_hint=(
            "Anything that doesn't clearly match one specific domain above — general questions, "
            "small talk, or ambiguous/multi-topic requests."
        ),
        system_prompt_fragment=(
            "For questions no dedicated report tool answers, you can query raw records with "
            "run_custom_report — call list_report_sources first to see valid sources and fields."
        ),
        tools=(
            "get_dashboard_summary", "get_income_statement", "get_ar_aging", "get_ap_aging",
            "get_trial_balance", "get_cash_flow", "get_top_customers",
            "list_report_sources", "run_custom_report",
        ),
    ),
}

FALLBACK_AGENT_KEY = "general"


def available_agents(installed_modules: set[str]) -> dict[str, AgentDef]:
    """Registry entries usable by this tenant right now — filters out any
    agent whose required_module isn't installed. All v1 agents have
    required_module=None (always available), so this is a no-op filter today;
    it exists so a future module-gated agent doesn't need triage-prompt
    changes anywhere else."""
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
