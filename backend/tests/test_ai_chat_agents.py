"""Triage -> specialist agent routing (agentic pipeline, part 4/6).

litellm.acompletion is mocked; no network calls. Complements
test_ai_chat_stream.py (which locks the pre-existing single-loop SSE
contract) with tests specific to the new routing layer: correct tool
subset per routed agent, cheap-tier model selection for the triage call,
graceful fallback on an unparseable/failed triage response, and the
persisted AiChatMessage.agent column."""
import json

from fastapi.testclient import TestClient


def _signup(client, email):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co", "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_ai(client, auth):
    r = client.post("/api/modules/ai_assistant/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def _new_session(client, auth) -> int:
    return client.post("/api/ai/sessions", headers=auth, json={}).json()["id"]


def _setup(client, email, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, email)
    _install_ai(client, auth)
    client.patch("/api/settings", headers=auth, json={"ai_api_key_openai": "sk-test"})
    return auth, _new_session(client, auth)


# ── litellm fakes (OpenAI chunk + plain completion shapes) ───────────────────

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


class _TriageMessage:
    def __init__(self, content):
        self.content = content

class _TriageChoice:
    def __init__(self, content):
        self.message = _TriageMessage(content)

class _TriageCompletion:
    def __init__(self, content):
        self.choices = [_TriageChoice(content)]


def _events(resp_text_lines):
    out = []
    for line in resp_text_lines:
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


def test_routes_to_specialist_with_narrowed_tool_subset(client: TestClient, monkeypatch):
    """A payables-shaped query, once routed, must only offer the payables
    agent's tool subset to the specialist call -- not all 7 tools."""
    auth, sid = _setup(client, "ag1@t.com", monkeypatch)

    calls = []
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            assert kwargs["max_tokens"] == 20
            assert kwargs["temperature"] == 0
            return _TriageCompletion("payables")
        calls.append(kwargs)
        return _stream_from([_Chunk(content="You owe 3 vendors."), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "what do I owe vendors?"}) as r:
        events = _events(list(r.iter_lines()))

    tool_names = {t["function"]["name"] for t in calls[0]["tools"]}
    assert tool_names == {"get_ap_aging", "get_dashboard_summary"}

    stage_labels = [e["label"] for e in events if e["type"] == "stage"]
    assert stage_labels[0] == "Routing your question…"
    assert "Payables Agent" in stage_labels[1]

    msgs = client.get(f"/api/ai/sessions/{sid}/messages", headers=auth).json()
    # agent isn't exposed on the /messages payload yet (PR3 landed the column
    # only) -- verify persistence directly instead.
    from sqlmodel import Session, select
    from models import AiChatMessage
    engine = client.app.state.engine
    with Session(engine) as s:
        row = s.exec(
            select(AiChatMessage).where(AiChatMessage.session_id == sid, AiChatMessage.role == "assistant")
        ).first()
        assert row.agent == "payables"
    assert msgs[-1]["content"] == "You owe 3 vendors."


def test_triage_cheap_tier_differs_from_specialist_model(client: TestClient, monkeypatch):
    """Triage must use the provider's cheap tier even when the user selected
    a pricier model for the actual conversation."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    auth = _signup(client, "ag2@t.com")
    _install_ai(client, auth)
    sid = _new_session(client, auth)

    seen_models = []
    async def fake_acompletion(**kwargs):
        seen_models.append((kwargs.get("stream"), kwargs["model"]))
        if kwargs.get("stream") is False:
            return _TriageCompletion("general")
        return _stream_from([_Chunk(content="hi"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hi", "model": "anthropic/claude-sonnet-5"}) as r:
        list(r.iter_lines())

    triage_calls = [m for streamed, m in seen_models if streamed is False]
    specialist_calls = [m for streamed, m in seen_models if streamed is True]
    assert triage_calls == ["anthropic/claude-haiku-4-5"]
    assert specialist_calls == ["anthropic/claude-sonnet-5"]


def test_unparseable_triage_response_falls_back_to_general(client: TestClient, monkeypatch):
    """A malformed/nonsense triage response must never abort the request --
    it silently routes to the general (today's-behavior, all-7-tools) agent."""
    auth, sid = _setup(client, "ag3@t.com", monkeypatch)

    calls = []
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            return _TriageCompletion("this is not a real agent key at all!!")
        calls.append(kwargs)
        return _stream_from([_Chunk(content="ok"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hello"}) as r:
        assert r.status_code == 200
        events = _events(list(r.iter_lines()))

    assert events[-1]["type"] == "done"
    tool_names = {t["function"]["name"] for t in calls[0]["tools"]}
    assert tool_names == {
        "get_dashboard_summary", "get_income_statement", "get_ar_aging",
        "get_ap_aging", "get_trial_balance", "get_cash_flow", "get_top_customers",
    }


def test_triage_call_raising_falls_back_to_general(client: TestClient, monkeypatch):
    """A network/provider failure during triage itself (not just a bad
    response) must also fall back silently, not abort the request."""
    auth, sid = _setup(client, "ag4@t.com", monkeypatch)

    calls = []
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            raise RuntimeError("triage provider timed out")
        calls.append(kwargs)
        return _stream_from([_Chunk(content="ok"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hello"}) as r:
        assert r.status_code == 200
        events = _events(list(r.iter_lines()))

    assert events[-1]["type"] == "done"
    assert len(calls) == 1   # specialist call still happened, on the general agent
