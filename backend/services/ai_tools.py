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

from sqlmodel import Session, select

from models import Customer, User, Vendor
from routers.aging import invoice_aging, bill_aging
from routers.reports import (
    get_dashboard_data,
    get_dashboard_charts,
    get_income_statement,
    get_trial_balance,
    cash_flow_statement,
    customer_performance,
    get_balance_sheet,
    get_budget_vs_actual,
    get_net_worth_trend,
    tax_summary,
)
from routers.subledger import (
    customer_ledger,
    customer_statement,
    vendor_ledger,
    vendor_statement,
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


def _require_id(tool_input: dict, key: str, lookup_tool: str) -> int:
    value = tool_input.get(key)
    if not value:
        raise ValueError(f"{key} is required — use {lookup_tool} first to resolve the name to an id.")
    return int(value)


def _exec_balance_sheet(session, user, tool_input):
    return get_balance_sheet(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
        date=tool_input.get("date"),
    )


def _exec_tax_summary(session, user, tool_input):
    return tax_summary(
        session, user,
        start=tool_input.get("start", ""),
        end=tool_input.get("end", ""),
    )


def _exec_budget_vs_actual(session, user, tool_input):
    year = tool_input.get("year")
    if not year:
        raise ValueError("year is required (e.g. 2026).")
    return get_budget_vs_actual(session, user, year=int(year), month=tool_input.get("month"))


def _exec_net_worth_trend(session, user, tool_input):
    months = int(tool_input.get("months") or 12)
    return get_net_worth_trend(session, user, months=max(1, min(months, 36)))


def _exec_customer_performance(session, user, tool_input):
    return customer_performance(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
        customer_id=tool_input.get("customer_id"),
    )


def _exec_customer_statement(session, user, tool_input):
    return customer_statement(
        session, user,
        customer_id=_require_id(tool_input, "customer_id", "find_customer"),
        from_date=tool_input.get("from_date"),
        to_date=tool_input.get("to_date"),
    )


def _exec_customer_ledger(session, user, tool_input):
    return customer_ledger(
        session, user,
        customer_id=_require_id(tool_input, "customer_id", "find_customer"),
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_vendor_statement(session, user, tool_input):
    return vendor_statement(
        session, user,
        vendor_id=_require_id(tool_input, "vendor_id", "find_vendor"),
        from_date=tool_input.get("from_date"),
        to_date=tool_input.get("to_date"),
    )


def _exec_vendor_ledger(session, user, tool_input):
    return vendor_ledger(
        session, user,
        vendor_id=_require_id(tool_input, "vendor_id", "find_vendor"),
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_find_customer(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(Customer).where(
            Customer.tenant_id == user.tenant_id,
            Customer.name.ilike(f"%{q}%"),
        ).limit(10)
    ).all()
    return [{"id": c.id, "name": c.name} for c in rows]


def _exec_find_vendor(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(Vendor).where(
            Vendor.tenant_id == user.tenant_id,
            Vendor.name.ilike(f"%{q}%"),
        ).limit(10)
    ).all()
    return [{"id": v.id, "name": v.name} for v in rows]


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
    ToolDef(
        name="get_balance_sheet",
        description=(
            "Get the Balance Sheet: assets, liabilities, and equity account balances "
            "(with retained earnings) as of a date, or for a period."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "date":  {"type": "string", "description": "As-of date YYYY-MM-DD (optional)"},
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": [],
        },
        label="Checking your balance sheet…",
        executor=_exec_balance_sheet,
    ),
    ToolDef(
        name="get_tax_summary",
        description=(
            "Get the tax summary: sales tax collected and purchase tax paid per tax account "
            "for a period (defaults to the current fiscal year to date)."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your tax summary…",
        executor=_exec_tax_summary,
    ),
    ToolDef(
        name="get_budget_vs_actual",
        description=(
            "Get budget vs actual variance per account for a fiscal year, optionally "
            "narrowed to a single month."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "year":  {"type": "integer", "description": "Fiscal year, e.g. 2026"},
                "month": {"type": "integer", "description": "Month 1-12 (optional)"},
            },
            "required": ["year"],
        },
        label="Checking budget vs actual…",
        executor=_exec_budget_vs_actual,
    ),
    ToolDef(
        name="get_net_worth_trend",
        description=(
            "Get the monthly assets / liabilities / net worth trend over the last N months "
            "(default 12, max 36)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "months": {"type": "integer", "description": "How many months back (default 12, max 36)"},
            },
            "required": [],
        },
        label="Checking your net worth trend…",
        executor=_exec_net_worth_trend,
    ),
    ToolDef(
        name="get_customer_performance",
        description=(
            "Get per-customer sales performance for a period: invoiced totals, receipts, "
            "outstanding balances, and invoice counts. Optionally filter to one customer."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
                "customer_id": {"type": "integer", "description": "Limit to one customer (optional; use find_customer to resolve a name)"},
            },
            "required": [],
        },
        label="Checking customer performance…",
        executor=_exec_customer_performance,
    ),
    ToolDef(
        name="get_customer_statement",
        description=(
            "Get a customer's account statement: opening balance, period invoices, payments "
            "received, and closing balance. Use find_customer first to resolve a customer "
            "name to its numeric id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer", "description": "Customer id (required)"},
                "from_date": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "to_date":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["customer_id"],
        },
        label="Fetching the customer statement…",
        executor=_exec_customer_statement,
    ),
    ToolDef(
        name="get_customer_ledger",
        description=(
            "Get a customer's chronological AR sub-ledger: every invoice and payment with a "
            "running balance. Use find_customer first to resolve a customer name to its id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer", "description": "Customer id (required)"},
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["customer_id"],
        },
        label="Fetching the customer ledger…",
        executor=_exec_customer_ledger,
    ),
    ToolDef(
        name="get_vendor_statement",
        description=(
            "Get a vendor's account statement: opening balance, period bills, payments made, "
            "and closing balance. Use find_vendor first to resolve a vendor name to its id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "vendor_id": {"type": "integer", "description": "Vendor id (required)"},
                "from_date": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "to_date":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["vendor_id"],
        },
        label="Fetching the vendor statement…",
        executor=_exec_vendor_statement,
    ),
    ToolDef(
        name="get_vendor_ledger",
        description=(
            "Get a vendor's chronological AP sub-ledger: every bill and payment with a "
            "running balance. Use find_vendor first to resolve a vendor name to its id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "vendor_id": {"type": "integer", "description": "Vendor id (required)"},
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["vendor_id"],
        },
        label="Fetching the vendor ledger…",
        executor=_exec_vendor_ledger,
    ),
    ToolDef(
        name="find_customer",
        description=(
            "Search customers by (partial) name and return up to 10 matches as {id, name}. "
            "Use this first to resolve a customer name to its numeric id before calling "
            "get_customer_statement, get_customer_ledger, or get_customer_performance."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial customer name"},
            },
            "required": ["query"],
        },
        label="Looking up the customer…",
        executor=_exec_find_customer,
    ),
    ToolDef(
        name="find_vendor",
        description=(
            "Search vendors by (partial) name and return up to 10 matches as {id, name}. "
            "Use this first to resolve a vendor name to its numeric id before calling "
            "get_vendor_statement or get_vendor_ledger."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial vendor name"},
            },
            "required": ["query"],
        },
        label="Looking up the vendor…",
        executor=_exec_find_vendor,
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
