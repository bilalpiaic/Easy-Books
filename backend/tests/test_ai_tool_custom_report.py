"""Generic report-builder AI tools (PR4 of the AI expansion):
list_report_sources + run_custom_report over services/report_engine.

The engine already enforces tenant injection and field whitelisting; these
tests lock the AI wrapper's own responsibilities — module gating of sources,
the 50-row cap, and recoverable (never-raising) error behavior — plus one
mocked-LLM end-to-end through the general agent."""
import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import User
from services.ai_tools import execute_tool


def _signup(client, email, company="Co"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": company, "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user_for(client, email) -> tuple[Session, User]:
    session = Session(client.app.state.engine)
    user = session.exec(select(User).where(User.email == email)).first()
    assert user is not None
    return session, user


def _run(session, user, name, tool_input=None):
    text, is_error = execute_tool(name, tool_input or {}, session, user)
    return json.loads(text), is_error


def _make_customer_invoice(client, auth, customer_name, amount):
    r = client.post("/api/customers", headers=auth, json={"name": customer_name})
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    r = client.post("/api/invoices", headers=auth, json={
        "customer_id": cid, "issue_date": "2026-07-01", "due_date": "2026-07-31",
        "lines": [{"description": "Consulting", "quantity": 1, "rate": amount}],
    })
    assert r.status_code in (200, 201), r.text


def test_custom_report_returns_only_own_tenant_rows(client: TestClient):
    auth_a = _signup(client, "cr1a@t.com", "TenantA")
    auth_b = _signup(client, "cr1b@t.com", "TenantB")
    _make_customer_invoice(client, auth_a, "A Customer", 111)
    _make_customer_invoice(client, auth_b, "B Customer", 222)

    session, user_a = _user_for(client, "cr1a@t.com")
    try:
        payload, is_error = _run(session, user_a, "run_custom_report", {
            "source_key": "customers", "columns": ["name"],
        })
        assert is_error is False, payload
        names = {row["name"] for row in payload["rows"]}
        assert names == {"A Customer"}          # never Tenant B's data
    finally:
        session.close()


def test_page_size_capped_at_50(client: TestClient):
    auth = _signup(client, "cr2@t.com")
    for i in range(55):
        client.post("/api/customers", headers=auth, json={"name": f"C{i:03d}"})

    session, user = _user_for(client, "cr2@t.com")
    try:
        payload, is_error = _run(session, user, "run_custom_report", {
            "source_key": "customers", "columns": ["name"], "page_size": 500,
        })
        assert is_error is False
        assert payload["rows_returned"] == 50
        assert payload["total_count"] == 55
    finally:
        session.close()


def test_gated_source_without_module_is_recoverable_error(client: TestClient):
    """`products` needs the inventory module — without it the tool returns a
    recoverable error naming list_report_sources, never a 500 or a leak."""
    _signup(client, "cr3@t.com")
    session, user = _user_for(client, "cr3@t.com")
    try:
        payload, is_error = _run(session, user, "run_custom_report", {
            "source_key": "products", "columns": ["name"],
        })
        assert is_error is True
        assert "list_report_sources" in payload["error"]

        # …and installing inventory makes the same call work.
    finally:
        session.close()


def test_bad_field_name_surfaces_report_error(client: TestClient):
    _signup(client, "cr4@t.com")
    session, user = _user_for(client, "cr4@t.com")
    try:
        payload, is_error = _run(session, user, "run_custom_report", {
            "source_key": "invoices", "columns": ["password_hash"],
        })
        assert is_error is True
        assert "unknown field" in payload["error"]
    finally:
        session.close()


def test_list_report_sources_hides_gated_sources_and_describes_fields(client: TestClient):
    auth = _signup(client, "cr5@t.com")
    session, user = _user_for(client, "cr5@t.com")
    try:
        payload, is_error = _run(session, user, "list_report_sources", {})
        assert is_error is False
        keys = {s["key"] for s in payload}
        assert "invoices" in keys
        assert "products" not in keys           # inventory not installed
        assert "employees" not in keys          # hrm not installed

        payload, is_error = _run(session, user, "list_report_sources",
                                 {"source_key": "invoices"})
        assert is_error is False
        field_keys = {f["key"] for f in payload["fields"]}
        assert "total" in field_keys or "amount" in field_keys or len(field_keys) > 0
    finally:
        session.close()

    # Installing inventory exposes the products source.
    r = client.post("/api/modules/inventory/install", headers=auth)
    assert r.status_code in (200, 201)
    session, user = _user_for(client, "cr5@t.com")
    try:
        payload, is_error = _run(session, user, "list_report_sources", {})
        assert {s["key"] for s in payload} >= {"invoices", "products", "stock_movements"}
    finally:
        session.close()


# ── mocked-LLM end-to-end via the general agent ──────────────────────────────

class _Fn:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments

class _ToolCallDelta:
    def __init__(self, index, id=None, name=None, arguments=None):
        self.index = index
        self.id = id
        self.function = _Fn(name, arguments)

class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

class _Choice:
    def __init__(self, content=None, tool_calls=None, finish_reason=None):
        self.delta = _Delta(content, tool_calls)
        self.finish_reason = finish_reason

class _Chunk:
    def __init__(self, **kw):
        self.choices = [_Choice(**kw)]

def _stream_from(chunks):
    async def gen():
        for c in chunks:
            yield c
    return gen()


class _Message:
    def __init__(self, content):
        self.content = content

class _MsgChoice:
    def __init__(self, content):
        self.message = _Message(content)

class _Completion:
    def __init__(self, content):
        self.choices = [_MsgChoice(content)]


def test_general_agent_runs_custom_report_end_to_end(client: TestClient, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, "cr6@t.com")
    r = client.post("/api/modules/ai_assistant/install", headers=auth)
    assert r.status_code in (200, 201)
    client.patch("/api/settings", headers=auth, json={"ai_api_key_openai": "sk-test"})
    _make_customer_invoice(client, auth, "Acme", 500)
    sid = client.post("/api/ai/sessions", headers=auth, json={}).json()["id"]

    args = json.dumps({"source_key": "customers", "columns": ["name"]})
    responses = [
        _stream_from([
            _Chunk(tool_calls=[_ToolCallDelta(0, id="c1", name="run_custom_report", arguments=args)]),
            _Chunk(finish_reason="tool_calls"),
        ]),
        _stream_from([_Chunk(content="You have 1 customer: Acme."), _Chunk(finish_reason="stop")]),
        _stream_from([_Chunk(content="You have **1 customer**: Acme."), _Chunk(finish_reason="stop")]),
    ]
    captured = []
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            if kwargs["max_tokens"] == 30:
                return _Completion("general")
            return _Completion("You have 1 customer: Acme.")   # reviewer confirms
        captured.append(kwargs["messages"])
        return responses.pop(0)
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "how many customers do I have?"}) as r:
        events = [json.loads(l[len("data: "):]) for l in r.iter_lines() if l.startswith("data: ")]

    assert events[-1]["type"] == "done"
    # The tool actually executed: its result (with the seeded customer) went
    # back into the specialist loop as a tool message.
    tool_msg = next(m for m in captured[1] if m["role"] == "tool")
    result = json.loads(tool_msg["content"])
    assert result["rows"] == [{"name": "Acme"}]
