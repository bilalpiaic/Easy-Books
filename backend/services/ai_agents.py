"""Declarative registry of AI chat specialist agents — the routing
capability boundary for the triage ("Boss") stage.

Mirrors services/report_sources's pattern: a frozen, key-based registry that
is the actual capability boundary (an unknown/unparseable triage response
always falls back to "general", never a hard failure). Each entry is
pre-equipped with its own tool subset (drawn from ai_chat.py's TOOLS) and a
system-prompt fragment describing its domain — so the specialist stage runs
with a narrow, focused prompt instead of the current one-size-fits-all
prompt bound to all 7 tools on every turn.

v1 covers the 3 domains the existing 7 read-only tools actually support
(Receivables, Payables, Financial Reports) plus a General fallback that
reproduces today's single-agent behavior verbatim. `required_module` is
wired now (all four are None here — they only need the `ai_assistant`
module, already gated) so a future domain agent (inventory/payroll/
healthcare/telecom, once those domains have their own read-tools) is a new
registry entry, not a pipeline rewrite.
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
            "top customers."
        ),
        system_prompt_fragment=(
            "You specialize in Accounts Receivable. Use get_ar_aging and get_top_customers to "
            "answer questions about who owes the business money, overdue invoices, and customer "
            "balances. Use get_dashboard_summary only if you need a quick cross-check of the "
            "overall AR total."
        ),
        tools=("get_ar_aging", "get_top_customers", "get_dashboard_summary"),
    ),
    "payables": AgentDef(
        key="payables",
        label="Payables Agent",
        trigger_hint=(
            "What the business owes vendors: outstanding/overdue bills, AP aging."
        ),
        system_prompt_fragment=(
            "You specialize in Accounts Payable. Use get_ap_aging to answer questions about what "
            "the business owes vendors and which bills are overdue. Use get_dashboard_summary "
            "only if you need a quick cross-check of the overall AP total."
        ),
        tools=("get_ap_aging", "get_dashboard_summary"),
    ),
    "financial_reports": AgentDef(
        key="financial_reports",
        label="Financial Reports Agent",
        trigger_hint=(
            "Overall financial performance: profit & loss / income statement, trial balance, "
            "cash flow, revenue, expenses, profit, account balances."
        ),
        system_prompt_fragment=(
            "You specialize in financial statements and performance. Use get_income_statement, "
            "get_trial_balance, and get_cash_flow to answer questions about profit, revenue, "
            "expenses, account balances, and cash movement."
        ),
        tools=("get_income_statement", "get_trial_balance", "get_cash_flow", "get_dashboard_summary"),
    ),
    "general": AgentDef(
        key="general",
        label="Assistant",
        trigger_hint=(
            "Anything not clearly about receivables, payables, or financial statements — general "
            "questions, small talk, or ambiguous/multi-topic requests."
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
