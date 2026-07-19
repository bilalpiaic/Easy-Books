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
            "get_dashboard_summary",
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
    "general": AgentDef(
        key="general",
        label="Assistant",
        trigger_hint=(
            "Anything that doesn't clearly match one specific domain above — general questions, "
            "small talk, or ambiguous/multi-topic requests."
        ),
        system_prompt_fragment="",
        tools=(
            "get_dashboard_summary", "get_income_statement", "get_ar_aging", "get_ap_aging",
            "get_trial_balance", "get_cash_flow", "get_top_customers",
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
