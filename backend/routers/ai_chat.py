"""
Level 1 AI Financial Assistant.

Calls existing report functions directly (no HTTP re-request) so all
business rules, tenant filters, and calculations are automatically reused.
Claude acts as a natural-language orchestration layer on top of the
accounting API.

The agent loop runs up to MAX_STEPS iterations, executing tool calls and
feeding results back until Claude produces a plain-text reply.
"""
import json
import os
from datetime import date as DateType
from decimal import Decimal

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import Settings
from routers.aging import invoice_aging, bill_aging
from routers.reports import (
    get_dashboard_data,
    get_dashboard_charts,
    get_income_statement,
    get_trial_balance,
    cash_flow_statement,
)
from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/ai", tags=["ai"])

MAX_STEPS = 6
MODEL = "claude-sonnet-4-6"


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "get_dashboard_summary",
        "description": (
            "Get the current financial dashboard KPIs: total revenue, total expenses, "
            "AR outstanding, AP outstanding, overdue invoices, low stock items, cash & bank balance, "
            "and AR aging buckets. Optionally filter by date range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Start date YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "End date YYYY-MM-DD (optional)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_income_statement",
        "description": (
            "Get the Profit & Loss / Income Statement showing revenue and expense totals "
            "and net profit for a period."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD"},
            },
            "required": [],
        },
    },
    {
        "name": "get_ar_aging",
        "description": (
            "Get Accounts Receivable aging: outstanding invoice amounts grouped by age bucket "
            "(current, 1-30 days, 31-60 days, 61-90 days, 90+ days overdue), plus a list of "
            "individual outstanding invoices with customer names and amounts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_ap_aging",
        "description": (
            "Get Accounts Payable aging: outstanding bill amounts grouped by age bucket, "
            "plus individual outstanding bills with vendor names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_trial_balance",
        "description": (
            "Get the Trial Balance showing debit and credit totals for all accounts. "
            "Useful for checking if books are balanced or auditing account balances."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_cash_flow",
        "description": (
            "Get the Cash Flow Statement showing operating, investing, and financing cash flows "
            "for a period."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD"},
            },
            "required": [],
        },
    },
    {
        "name": "get_top_customers",
        "description": "Get the top 5 customers by total invoiced amount and the monthly revenue/expense trend for the last 12 months.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_safe(obj):
    """Recursively convert Decimal to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(i) for i in obj]
    return obj


def _get_company_name(session, user) -> str:
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == user.tenant_id,
            Settings.key == "company_name",
        )
    ).first()
    return row.value if row and row.value else "your company"


def _build_system_prompt(company_name: str) -> str:
    today = DateType.today().isoformat()
    return (
        f"You are the AI Financial Assistant for {company_name}, integrated into Easy-Books "
        f"accounting software. Today's date is {today}.\n\n"
        "Your role is to answer questions about the business's financial data accurately and clearly. "
        "You have access to tools that fetch live data from the accounting system — always use them "
        "when answering quantitative questions so your answers are based on real numbers, not guesses.\n\n"
        "Guidelines:\n"
        "- Be concise and direct. Lead with the key number or answer.\n"
        "- Format currency amounts clearly (e.g. PKR 1,234,567 or $ 1,234.56).\n"
        "- For overdue invoices, list the top items by amount if there are many.\n"
        "- If data spans multiple periods, mention the period in your answer.\n"
        "- You can only READ data — you cannot create invoices, post transactions, or modify anything.\n"
        "- If a question is not financial or accounting-related, politely say you can only help with "
        "financial data from this accounting system."
    )


# ── Tool execution ────────────────────────────────────────────────────────────

def _execute_tool(name: str, tool_input: dict, session, user) -> str:
    try:
        if name == "get_dashboard_summary":
            result = get_dashboard_data(
                session, user,
                start=tool_input.get("start"),
                end=tool_input.get("end"),
            )
        elif name == "get_income_statement":
            result = get_income_statement(
                session, user,
                start=tool_input.get("start"),
                end=tool_input.get("end"),
            )
        elif name == "get_ar_aging":
            result = invoice_aging(session, user)
        elif name == "get_ap_aging":
            result = bill_aging(session, user)
        elif name == "get_trial_balance":
            result = get_trial_balance(
                session, user,
                start=tool_input.get("start"),
                end=tool_input.get("end"),
            )
        elif name == "get_cash_flow":
            result = cash_flow_statement(
                session, user,
                start=tool_input.get("start", ""),
                end=tool_input.get("end", ""),
            )
        elif name == "get_top_customers":
            result = get_dashboard_charts(session, user, months=12)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
        return json.dumps(_json_safe(result))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/chat")
def ai_chat(body: ChatRequest, session: SessionDep, user: CurrentUserDep):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. Set ANTHROPIC_API_KEY in the backend environment.",
        )

    client = anthropic.Anthropic(api_key=api_key)
    company_name = _get_company_name(session, user)
    system_prompt = _build_system_prompt(company_name)

    messages: list[dict] = [
        {"role": m.role, "content": m.content}
        for m in body.history
    ]
    messages.append({"role": "user", "content": body.message})

    for _ in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return {"reply": "\n".join(text_blocks)}

        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return {"reply": "\n".join(text_blocks) or "I couldn't generate a response."}

        # Append assistant's tool-use response to the conversation
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool call and collect results
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_text = _execute_tool(block.name, block.input, session, user)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

        messages.append({"role": "user", "content": tool_results})

    return {"reply": "I wasn't able to complete the analysis. Please try a more specific question."}
