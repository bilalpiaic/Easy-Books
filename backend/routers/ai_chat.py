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
import time
from collections import defaultdict, deque
from datetime import date as DateType, datetime
from decimal import Decimal

import litellm
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select

from models import AiChatMessage, AiChatSession, Settings, Tenant
from routers.aging import invoice_aging, bill_aging
from routers.modules import _get_enabled
from routers.reports import (
    get_dashboard_data,
    get_dashboard_charts,
    get_income_statement,
    get_trial_balance,
    cash_flow_statement,
)
from services.ai_providers import (
    DEFAULT_MODEL,
    PROVIDERS,
    configured_providers,
    mask_key,
    resolve_api_key,
    validate_model,
)
from .common import AdminUserDep, CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/ai", tags=["ai"])

MAX_STEPS = 6
MAX_HISTORY = 20          # history turns kept per request (cost guard)
MAX_MESSAGE_CHARS = 4000  # per-message length cap (cost guard)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: int
    message: str
    model: str | None = None


# ── Session CRUD helpers ──────────────────────────────────────────────────────

def _require_ai_module(session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "ai_assistant" not in _get_enabled(tenant):
        raise HTTPException(
            status_code=403,
            detail="The AI Financial Assistant module is not installed. Install it from System → Apps.",
        )


def _get_session_or_404(session, user, session_id: int) -> AiChatSession:
    row = session.exec(
        select(AiChatSession).where(
            AiChatSession.id == session_id,
            AiChatSession.tenant_id == user.tenant_id,
            AiChatSession.user_id == user.id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Chat session not found")
    return row


class SessionPatch(BaseModel):
    title: str


@router.get("/sessions")
def list_sessions(session: SessionDep, user: CurrentUserDep):
    _require_ai_module(session, user)
    rows = session.exec(
        select(AiChatSession).where(
            AiChatSession.tenant_id == user.tenant_id,
            AiChatSession.user_id == user.id,
        ).order_by(AiChatSession.updated_at.desc())
    ).all()
    return [{"id": r.id, "title": r.title, "updated_at": r.updated_at} for r in rows]


@router.post("/sessions", status_code=201)
def create_session(session: SessionDep, user: CurrentUserDep):
    _require_ai_module(session, user)
    row = AiChatSession(tenant_id=user.tenant_id, user_id=user.id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"id": row.id, "title": row.title, "updated_at": row.updated_at}


@router.patch("/sessions/{session_id}")
def rename_session(session: SessionDep, user: CurrentUserDep, session_id: int, body: SessionPatch):
    _require_ai_module(session, user)
    row = _get_session_or_404(session, user, session_id)
    title = body.title.strip()[:120]
    if not title:
        raise HTTPException(400, "Title cannot be empty")
    row.title = title
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    return {"id": row.id, "title": row.title}


@router.delete("/sessions/{session_id}")
def delete_session(session: SessionDep, user: CurrentUserDep, session_id: int):
    _require_ai_module(session, user)
    row = _get_session_or_404(session, user, session_id)
    # Explicitly delete child messages before deleting session (SQLite doesn't enforce ON DELETE CASCADE)
    for m in session.exec(
        select(AiChatMessage).where(AiChatMessage.session_id == row.id)
    ).all():
        session.delete(m)
    session.delete(row)
    session.commit()
    return {"success": True}


@router.get("/sessions/{session_id}/messages")
def session_messages(session: SessionDep, user: CurrentUserDep, session_id: int):
    _require_ai_module(session, user)
    _get_session_or_404(session, user, session_id)
    rows = session.exec(
        select(AiChatMessage).where(AiChatMessage.session_id == session_id)
        .order_by(AiChatMessage.id)
    ).all()
    return [
        {"id": m.id, "role": m.role, "content": m.content, "model": m.model}
        for m in rows
    ]


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
        "description": "Get the top 10 customers by total invoiced amount and the monthly revenue/expense trend for the last 12 months.",
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

def _execute_tool(name: str, tool_input: dict, session, user) -> tuple[str, bool]:
    """Run one tool call; returns (json_text, is_error)."""
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
            return json.dumps({"error": f"Unknown tool: {name}"}), True
        return json.dumps(_json_safe(result)), False
    except Exception as exc:
        return json.dumps({"error": str(exc)}), True


# ── Tool conversion (Anthropic → OpenAI function format) + rate limiting ──────

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS
]

TOOL_LABELS = {
    "get_dashboard_summary": "Checking your dashboard…",
    "get_income_statement": "Checking your P&L…",
    "get_ar_aging": "Checking who owes you (receivables)…",
    "get_ap_aging": "Checking what you owe (payables)…",
    "get_trial_balance": "Checking your trial balance…",
    "get_cash_flow": "Checking your cash flow…",
    "get_top_customers": "Checking your top customers…",
}

# Sliding-hour rate limiter. Per-process by design (single-process deploy);
# resets on restart — acceptable, documented in the spec.
_RATE: dict[tuple[int, int], deque] = defaultdict(deque)
DEFAULT_RATE_LIMIT = 20


def _check_rate_limit(session, user) -> None:
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == user.tenant_id,
            Settings.key == "ai_rate_limit_per_hour",
        )
    ).first()
    try:
        limit = int(row.value) if row and row.value else DEFAULT_RATE_LIMIT
    except ValueError:
        limit = DEFAULT_RATE_LIMIT
    bucket = _RATE[(user.tenant_id, user.id)]
    now = time.monotonic()
    while bucket and now - bucket[0] > 3600:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"AI request limit reached ({limit}/hour). Try again in a few minutes.",
        )
    bucket.append(now)


# ── Endpoint ──────────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/chat")
async def ai_chat(body: ChatRequest, session: SessionDep, user: CurrentUserDep):
    # ── Pre-stream validation: plain HTTP errors ────────────────────────
    _require_ai_module(session, user)
    chat_session = _get_session_or_404(session, user, body.session_id)

    if len(body.message) > MAX_MESSAGE_CHARS:
        raise HTTPException(400, f"Message too long (max {MAX_MESSAGE_CHARS} characters).")

    providers = configured_providers(session, user.tenant_id)
    if not providers:
        raise HTTPException(
            503,
            "AI assistant is not configured. Add a provider API key in Settings → AI "
            "(or set ANTHROPIC_API_KEY in the backend environment).",
        )
    model = body.model or providers[0]["default"] or DEFAULT_MODEL
    try:
        litellm_model, api_key, api_base = validate_model(session, user.tenant_id, model)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    _check_rate_limit(session, user)

    # Server-side history (last MAX_HISTORY turns), then persist the new user msg.
    history_rows = session.exec(
        select(AiChatMessage).where(AiChatMessage.session_id == chat_session.id)
        .order_by(AiChatMessage.id.desc()).limit(MAX_HISTORY)
    ).all()
    messages: list[dict] = [{"role": "system", "content": _build_system_prompt(_get_company_name(session, user))}]
    messages += [
        {"role": m.role, "content": m.content[:MAX_MESSAGE_CHARS]}
        for m in reversed(history_rows)
    ]
    messages.append({"role": "user", "content": body.message})

    user_msg = AiChatMessage(session_id=chat_session.id, role="user", content=body.message)
    session.add(user_msg)
    if chat_session.title == "New chat":
        chat_session.title = body.message.strip()[:60]
    chat_session.updated_at = datetime.utcnow()
    session.add(chat_session)
    session.commit()

    async def stream():
        assistant_text_parts: list[str] = []
        try:
            for _ in range(MAX_STEPS):
                # Claude Sonnet 5 runs adaptive thinking ON when `thinking` is
                # omitted entirely (a silent change from claude-sonnet-4-6,
                # which ran thinking-off by default) — and thinking output
                # shares this call's fixed max_tokens budget with the reply
                # text, so an unmodified call risks truncating the answer.
                # Disable it explicitly to keep today's plain-text behavior;
                # other providers don't accept the kwarg at all.
                extra: dict = {}
                if litellm_model.startswith("anthropic/"):
                    extra["thinking"] = {"type": "disabled"}
                # litellm needs the "ollama_chat/" prefix (not "ollama/") for
                # OpenAI-style chat + tool-calling + streaming, and api_base
                # to reach the tenant's own server instead of localhost.
                # litellm_model stays "ollama/<tag>" everywhere else (display,
                # persisted AiChatMessage.model) -- only this call is translated.
                call_model = litellm_model
                if litellm_model.startswith("ollama/"):
                    call_model = "ollama_chat/" + litellm_model[len("ollama/"):]
                    extra["api_base"] = api_base
                response = await litellm.acompletion(
                    model=call_model,
                    api_key=api_key,
                    max_tokens=2048,
                    messages=messages,
                    tools=OPENAI_TOOLS,
                    stream=True,
                    **extra,
                )
                # Accumulate this round's text + tool calls from the chunk stream.
                round_text_parts: list[str] = []
                tool_calls: dict[int, dict] = {}
                finish_reason = None
                async for chunk in response:
                    choice = chunk.choices[0]
                    delta = choice.delta
                    if getattr(delta, "content", None):
                        round_text_parts.append(delta.content)
                        yield _sse({"type": "token", "text": delta.content})
                    for tc in getattr(delta, "tool_calls", None) or []:
                        slot = tool_calls.setdefault(
                            tc.index, {"id": None, "name": None, "arguments": ""}
                        )
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function.name:
                            slot["name"] = tc.function.name
                        if tc.function.arguments:
                            slot["arguments"] += tc.function.arguments
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
                assistant_text_parts += round_text_parts

                if finish_reason != "tool_calls" or not tool_calls:
                    break  # done — plain answer (or provider stopped)

                # Echo the assistant tool-call turn, execute, append results.
                ordered = [tool_calls[i] for i in sorted(tool_calls)]
                messages.append({
                    "role": "assistant",
                    "content": "".join(round_text_parts) or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {"name": c["name"], "arguments": c["arguments"] or "{}"},
                        }
                        for c in ordered
                    ],
                })
                for c in ordered:
                    yield _sse({
                        "type": "tool_start",
                        "label": TOOL_LABELS.get(c["name"], f"Running {c['name']}…"),
                    })
                    try:
                        tool_input = json.loads(c["arguments"] or "{}")
                    except json.JSONDecodeError:
                        tool_input = {}
                    result_text, _is_error = _execute_tool(c["name"], tool_input, session, user)
                    yield _sse({"type": "tool_end"})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "content": result_text,
                    })

            reply = "".join(assistant_text_parts) or \
                "I wasn't able to complete the analysis. Please try a more specific question."
            assistant_msg = AiChatMessage(
                session_id=chat_session.id, role="assistant",
                content=reply, model=litellm_model,
            )
            chat_session.updated_at = datetime.utcnow()
            session.add(assistant_msg)
            session.add(chat_session)
            session.commit()
            # "reply" is the authoritative final text (falls back to a fixed
            # string when the model only ever emitted tool_calls and no
            # content deltas at all -- see above). Without it here, the
            # frontend has no way to learn that text: it only knows what it
            # accumulated from "token" events, which is empty in exactly
            # that case, so the assistant bubble it commits on "done" would
            # render blank even though a real (persisted) message exists.
            yield _sse({
                "type": "done",
                "session_id": chat_session.id,
                "message_id": assistant_msg.id,
                "reply": reply,
            })
        except Exception as exc:  # mid-stream: headers already sent → error event
            # The provider's actual error text (invalid model, bad key, rate
            # limit, etc.) was previously discarded entirely -- only the
            # exception class name reached the client, and nothing was
            # logged server-side, making every mid-stream failure
            # undiagnosable. litellm exceptions carry the provider's message
            # in str(exc); truncated here since some are verbose.
            print(f"[ai_chat] {type(exc).__name__} for model={litellm_model}: {exc}", flush=True)
            detail = str(exc).strip()
            if len(detail) > 300:
                detail = detail[:300] + "..."
            yield _sse({
                "type": "error",
                "detail": f"The AI service failed mid-response: {type(exc).__name__}: {detail}",
            })

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/models")
def list_models(session: SessionDep, user: CurrentUserDep):
    _require_ai_module(session, user)
    providers = configured_providers(session, user.tenant_id)
    default = providers[0]["default"] if providers else None
    return {"providers": providers, "default_model": default}


@router.get("/key-status")
def key_status(session: SessionDep, user: AdminUserDep):
    # Ollama has no secret key to mask (self-hosted, gated by tagged models
    # instead) -- ai_ollama_base_url/ai_ollama_models aren't secrets, so the
    # frontend reads its configuration state straight off GET /api/settings.
    return {
        provider: mask_key(resolve_api_key(session, user.tenant_id, provider))
        for provider, cfg in PROVIDERS.items()
        if cfg["settings_key"]
    }
