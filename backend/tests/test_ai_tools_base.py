"""Base-domain AI tools (PR2 of the AI expansion) — executor smoke tests
against a real in-memory DB (no LLM), tenant scoping on the find_* lookups,
and one routed-to-sales pipeline test with a mocked litellm."""
import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import User
from services.ai_tools import TOOL_REGISTRY, execute_tool


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


def test_base_tools_smoke(client: TestClient):
    """Every new base tool executes without error against a fresh tenant
    (empty books are fine — the point is signature/wiring, not figures)."""
    auth = _signup(client, "bt1@t.com")
    r = client.post("/api/customers", headers=auth, json={"name": "Acme Traders"})
    assert r.status_code in (200, 201), r.text
    customer_id = r.json()["id"]
    r = client.post("/api/vendors", headers=auth, json={"name": "Bulk Supplies"})
    assert r.status_code in (200, 201), r.text
    vendor_id = r.json()["id"]

    session, user = _user_for(client, "bt1@t.com")
    try:
        found, err = _run(session, user, "find_account", {"query": "cash"})
        assert err is False and found, found
        account_id = found[0]["id"]

        cases = {
            "get_balance_sheet": {},
            "get_tax_summary": {},
            "get_budget_vs_actual": {"year": 2026},
            "get_net_worth_trend": {"months": 6},
            "get_customer_performance": {},
            "get_customer_statement": {"customer_id": customer_id},
            "get_customer_ledger": {"customer_id": customer_id},
            "get_vendor_statement": {"vendor_id": vendor_id},
            "get_vendor_ledger": {"vendor_id": vendor_id},
            "find_customer": {"query": "acme"},
            "find_vendor": {"query": "bulk"},
            # banking / GL / deferred / commissions / assets (gap-fill)
            "get_day_book": {},
            "find_account": {"query": "cash"},
            "get_account_ledger": {
                "account_id": account_id, "start": "2026-01-01", "end": "2026-12-31",
            },
            "get_cash_bank_subledger": {},
            "list_bank_accounts": {},
            "get_journal_report": {"start": "2026-01-01", "end": "2026-12-31"},
            "find_analytic_account": {"query": "x"},
            "list_deferred_schedules": {},
            "get_commission_ledger": {},
            "list_commission_plans": {},
            "list_fixed_assets": {},
        }
        for name, tool_input in cases.items():
            payload, is_error = _run(session, user, name, tool_input)
            assert is_error is False, f"{name}: {payload}"
    finally:
        session.close()


def test_find_lookups_are_tenant_scoped_and_capped(client: TestClient):
    auth_a = _signup(client, "bt2a@t.com", "TenantA")
    auth_b = _signup(client, "bt2b@t.com", "TenantB")
    for i in range(12):
        client.post("/api/customers", headers=auth_a, json={"name": f"Shared Name {i}"})
    client.post("/api/customers", headers=auth_b, json={"name": "Shared Name B-only"})

    session, user_b = _user_for(client, "bt2b@t.com")
    try:
        payload, is_error = _run(session, user_b, "find_customer", {"query": "shared"})
        assert is_error is False
        # Tenant B sees only its own customer, never Tenant A's 12.
        assert [c["name"] for c in payload] == ["Shared Name B-only"]
    finally:
        session.close()

    session, user_a = _user_for(client, "bt2a@t.com")
    try:
        payload, is_error = _run(session, user_a, "find_customer", {"query": "shared"})
        assert is_error is False
        assert len(payload) == 10          # capped at 10 of the 12 matches
    finally:
        session.close()


def test_statement_without_id_returns_recoverable_error(client: TestClient):
    _signup(client, "bt3@t.com")
    session, user = _user_for(client, "bt3@t.com")
    try:
        payload, is_error = _run(session, user, "get_customer_statement", {})
        assert is_error is True
        assert "find_customer" in payload["error"]
    finally:
        session.close()


# ── Routed-to-sales pipeline test (mocked litellm) ───────────────────────────

class _Delta:
    def __init__(self, content=None):
        self.content = content
        self.tool_calls = None

class _Choice:
    def __init__(self, content=None, finish_reason=None):
        self.delta = _Delta(content)
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


def test_routes_to_sales_agent_with_its_tool_subset(client: TestClient, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, "bt4@t.com")
    r = client.post("/api/modules/ai_assistant/install", headers=auth)
    assert r.status_code in (200, 201), r.text
    client.patch("/api/settings", headers=auth, json={"ai_api_key_openai": "sk-test"})
    sid = client.post("/api/ai/sessions", headers=auth, json={}).json()["id"]

    calls = []
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            return _Completion("sales")
        calls.append(kwargs)
        return _stream_from([_Chunk(content="Top customer is Acme."), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "who is my best customer this year?"}) as r:
        lines = list(r.iter_lines())

    tool_names = {t["function"]["name"] for t in calls[0]["tools"]}
    assert tool_names == {
        "get_customer_performance", "get_top_customers", "find_customer",
        "get_customer_statement", "get_customer_ledger", "get_dashboard_summary",
    }
    stage_labels = [
        json.loads(l[len("data: "):])["label"]
        for l in lines
        if l.startswith("data: ") and json.loads(l[len("data: "):]).get("type") == "stage"
    ]
    assert any("Sales & Customers Agent" in s for s in stage_labels)
