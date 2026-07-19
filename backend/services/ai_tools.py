"""Declarative registry of the AI chat's read-only tools.

Mirrors services/report_sources's pattern: a frozen, key-based registry that
is the single source of truth for every tool the AI assistant can call.
`routers/ai_chat.py` derives its provider-facing tool schemas
(anthropic_tools / openai_tools), progress labels (tool_labels), and dispatch
(execute_tool) from here — adding a tool is one TOOL_REGISTRY entry, not a
4-place hand-edit across ai_chat.py.

Each executor wraps an existing report function directly (no HTTP
re-request) so business rules, tenant filters, and calculations are reused,
never re-implemented. `required_module` gates module-specific tools the same
way AgentDef.required_module gates agents (None = base, always available).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Iterable

from sqlmodel import Session

from models import User
from routers.aging import invoice_aging, bill_aging
from routers.reports import (
    get_dashboard_data,
    get_dashboard_charts,
    get_income_statement,
    get_trial_balance,
    cash_flow_statement,
)

# Oversized tool results are truncated before they re-enter the LLM loop —
# unpaginated reports (per-product/per-customer lists) can otherwise blow the
# reviewer/drafting stages' input budget. This constant is the tuning knob.
MAX_TOOL_RESULT_CHARS = 15_000

_DATE_RANGE_SCHEMA = {
    "type": "object",
    "properties": {
        "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
        "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
    },
    "required": [],
}

_EMPTY_SCHEMA = {"type": "object", "properties": {}, "required": []}


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict               # JSON Schema (Anthropic tool shape)
    label: str                       # user-facing progress label ("Checking your P&L…")
    executor: Callable[[Session, User, dict], Any]
    required_module: str | None = None  # None = base, always available


def _json_safe(obj):
    """Recursively convert Decimal to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(i) for i in obj]
    return obj


# ── Executors ─────────────────────────────────────────────────────────────────

def _exec_dashboard_summary(session, user, tool_input):
    return get_dashboard_data(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_income_statement(session, user, tool_input):
    return get_income_statement(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_ar_aging(session, user, tool_input):
    return invoice_aging(session, user)


def _exec_ap_aging(session, user, tool_input):
    return bill_aging(session, user)


def _exec_trial_balance(session, user, tool_input):
    return get_trial_balance(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_cash_flow(session, user, tool_input):
    return cash_flow_statement(
        session, user,
        start=tool_input.get("start", ""),
        end=tool_input.get("end", ""),
    )


def _exec_top_customers(session, user, tool_input):
    return get_dashboard_charts(session, user, months=12)


# ── Registry ──────────────────────────────────────────────────────────────────

_TOOLS: tuple[ToolDef, ...] = (
    ToolDef(
        name="get_dashboard_summary",
        description=(
            "Get the current financial dashboard KPIs: total revenue, total expenses, "
            "AR outstanding, AP outstanding, overdue invoices, low stock items, cash & bank balance, "
            "and AR aging buckets. Optionally filter by date range."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your dashboard…",
        executor=_exec_dashboard_summary,
    ),
    ToolDef(
        name="get_income_statement",
        description=(
            "Get the Profit & Loss / Income Statement showing revenue and expense totals "
            "and net profit for a period."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your P&L…",
        executor=_exec_income_statement,
    ),
    ToolDef(
        name="get_ar_aging",
        description=(
            "Get Accounts Receivable aging: outstanding invoice amounts grouped by age bucket "
            "(current, 1-30 days, 31-60 days, 61-90 days, 90+ days overdue), plus a list of "
            "individual outstanding invoices with customer names and amounts."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking who owes you (receivables)…",
        executor=_exec_ar_aging,
    ),
    ToolDef(
        name="get_ap_aging",
        description=(
            "Get Accounts Payable aging: outstanding bill amounts grouped by age bucket, "
            "plus individual outstanding bills with vendor names."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking what you owe (payables)…",
        executor=_exec_ap_aging,
    ),
    ToolDef(
        name="get_trial_balance",
        description=(
            "Get the Trial Balance showing debit and credit totals for all accounts. "
            "Useful for checking if books are balanced or auditing account balances."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your trial balance…",
        executor=_exec_trial_balance,
    ),
    ToolDef(
        name="get_cash_flow",
        description=(
            "Get the Cash Flow Statement showing operating, investing, and financing cash flows "
            "for a period."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your cash flow…",
        executor=_exec_cash_flow,
    ),
    ToolDef(
        name="get_top_customers",
        description=(
            "Get the top 10 customers by total invoiced amount and the monthly revenue/expense "
            "trend for the last 12 months."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking your top customers…",
        executor=_exec_top_customers,
    ),
)

TOOL_REGISTRY: dict[str, ToolDef] = {t.name: t for t in _TOOLS}


# ── Derivations + dispatch ────────────────────────────────────────────────────

def anthropic_tools(names: Iterable[str]) -> list[dict]:
    """Anthropic-shaped tool defs for the named registry entries."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in (TOOL_REGISTRY[n] for n in names if n in TOOL_REGISTRY)
    ]


def openai_tools(names: Iterable[str]) -> list[dict]:
    """OpenAI function-calling-shaped tool defs (what litellm is passed)."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in (TOOL_REGISTRY[n] for n in names if n in TOOL_REGISTRY)
    ]


def tool_labels() -> dict[str, str]:
    return {t.name: t.label for t in TOOL_REGISTRY.values()}


def execute_tool(name: str, tool_input: dict, session: Session, user: User) -> tuple[str, bool]:
    """Run one tool call; returns (json_text, is_error). Unknown names and
    executor exceptions become error payloads the model can recover from,
    never HTTP failures mid-stream."""
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        return json.dumps({"error": f"Unknown tool: {name}"}), True
    try:
        result = tool.executor(session, user, tool_input)
    except Exception as exc:
        return json.dumps({"error": str(exc)}), True
    text = json.dumps(_json_safe(result))
    if len(text) > MAX_TOOL_RESULT_CHARS:
        text = json.dumps({
            "truncated": True,
            "note": (
                "Result was too large and has been truncated; totals may be "
                "incomplete. Narrow the query (date range or filters) for full data."
            ),
            "data": text[:MAX_TOOL_RESULT_CHARS],
        })
    return text, False
