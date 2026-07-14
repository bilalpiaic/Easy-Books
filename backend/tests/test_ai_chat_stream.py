"""#117 completion — SSE chat: event sequence, persistence, rate limit, pre-stream errors.

litellm.acompletion is mocked; no network calls."""
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


# ── litellm stream fakes (OpenAI chunk shape) ────────────────────────────────

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


def _events(resp_text_lines):
    out = []
    for line in resp_text_lines:
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


def test_plain_text_stream_and_persistence(client: TestClient, monkeypatch):
    auth, sid = _setup(client, "st1@t.com", monkeypatch)

    calls = []
    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _stream_from([
            _Chunk(content="Hel"),
            _Chunk(content="lo!"),
            _Chunk(finish_reason="stop"),
        ])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hi"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _events(list(r.iter_lines()))

    types = [e["type"] for e in events]
    assert types == ["token", "token", "done"]
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Hello!"
    assert calls[0]["model"] == "openai/gpt-4o-mini"   # tenant default = first configured
    assert calls[0]["api_key"] == "sk-test"

    msgs = client.get(f"/api/ai/sessions/{sid}/messages", headers=auth).json()
    assert [(m["role"], m["content"]) for m in msgs] == [("user", "hi"), ("assistant", "Hello!")]
    assert msgs[1]["model"] == "openai/gpt-4o-mini"
    # session title auto-set from first message
    assert client.get("/api/ai/sessions", headers=auth).json()[0]["title"] == "hi"


def test_tool_call_round_trip_events(client: TestClient, monkeypatch):
    auth, sid = _setup(client, "st2@t.com", monkeypatch)

    responses = [
        _stream_from([
            _Chunk(tool_calls=[_ToolCallDelta(0, id="call_1", name="get_ar_aging", arguments="")]),
            _Chunk(tool_calls=[_ToolCallDelta(0, arguments="{}")]),
            _Chunk(finish_reason="tool_calls"),
        ]),
        _stream_from([
            _Chunk(content="You are owed money."),
            _Chunk(finish_reason="stop"),
        ]),
    ]
    captured = []
    async def fake_acompletion(**kwargs):
        captured.append(kwargs["messages"])
        return responses.pop(0)
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "who owes me?"}) as r:
        events = _events(list(r.iter_lines()))

    types = [e["type"] for e in events]
    assert types == ["tool_start", "tool_end", "token", "done"]
    assert "receivable" in events[0]["label"].lower() or "owe" in events[0]["label"].lower()
    # second call carried the tool result back in OpenAI format
    second_msgs = captured[1]
    assert second_msgs[-1]["role"] == "tool"
    assert second_msgs[-1]["tool_call_id"] == "call_1"
    assert second_msgs[-2]["role"] == "assistant"
    assert second_msgs[-2]["tool_calls"][0]["function"]["name"] == "get_ar_aging"


def test_pre_stream_errors(client: TestClient, monkeypatch):
    auth, sid = _setup(client, "st3@t.com", monkeypatch)

    r = client.post("/api/ai/chat", headers=auth,
                    json={"session_id": sid, "message": "hi", "model": "openai/not-real"})
    assert r.status_code == 400

    r = client.post("/api/ai/chat", headers=auth,
                    json={"session_id": sid, "message": "hi", "model": "gemini/gemini-2.5-flash"})
    assert r.status_code == 400          # provider not configured

    r = client.post("/api/ai/chat", headers=auth,
                    json={"session_id": 999999, "message": "hi"})
    assert r.status_code == 404

    r = client.post("/api/ai/chat", headers=auth,
                    json={"session_id": sid, "message": "x" * 4001})
    assert r.status_code == 400


def test_mid_stream_error_surfaces_provider_detail(client: TestClient, monkeypatch, capsys):
    """A mid-stream provider failure (bad model, invalid key, rate limit from
    the provider itself, etc.) used to be discarded entirely -- only
    type(exc).__name__ reached the client and nothing was logged
    server-side, making every such failure undiagnosable. The provider's
    actual message must now reach both the client event and stdout."""
    auth, sid = _setup(client, "st8@t.com", monkeypatch)

    async def fake_acompletion(**kwargs):
        raise ValueError("model `openai/gpt-4o-mini` not found: no access")
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hi"}) as r:
        assert r.status_code == 200
        events = _events(list(r.iter_lines()))

    assert [e["type"] for e in events] == ["error"]
    detail = events[0]["detail"]
    assert "ValueError" in detail
    assert "not found: no access" in detail

    captured = capsys.readouterr()
    assert "[ai_chat]" in captured.out
    assert "not found: no access" in captured.out


def test_ollama_call_translates_prefix_and_passes_api_base(client: TestClient, monkeypatch):
    """Ollama is stored/displayed everywhere as "ollama/<tag>" (matches the
    model dropdown and every other provider's own-name-as-prefix convention),
    but litellm needs "ollama_chat/<tag>" + an explicit api_base to actually
    reach the tenant's self-hosted server -- that translation must happen
    only at the litellm.acompletion call, not leak into what gets persisted."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, "st9@t.com")
    _install_ai(client, auth)
    client.patch("/api/settings", headers=auth, json={
        "ai_ollama_models": "llama3.1:8b",
        "ai_ollama_base_url": "http://gpu-box.local:11434",
    })
    sid = _new_session(client, auth)

    calls = []
    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _stream_from([_Chunk(content="hi"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hi", "model": "ollama/llama3.1:8b"}) as r:
        assert r.status_code == 200
        list(r.iter_lines())

    assert calls[0]["model"] == "ollama_chat/llama3.1:8b"
    assert calls[0]["api_base"] == "http://gpu-box.local:11434"
    assert calls[0]["api_key"] is None
    assert "thinking" not in calls[0]

    msgs = client.get(f"/api/ai/sessions/{sid}/messages", headers=auth).json()
    assert msgs[1]["model"] == "ollama/llama3.1:8b"   # persisted form, not ollama_chat/


def test_no_providers_returns_503(client: TestClient, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, "st4@t.com")
    _install_ai(client, auth)
    sid = _new_session(client, auth)
    r = client.post("/api/ai/chat", headers=auth, json={"session_id": sid, "message": "hi"})
    assert r.status_code == 503


def test_rate_limit_429(client: TestClient, monkeypatch):
    auth, sid = _setup(client, "st5@t.com", monkeypatch)
    client.patch("/api/settings", headers=auth, json={"ai_rate_limit_per_hour": "2"})

    async def fake_acompletion(**kwargs):
        return _stream_from([_Chunk(content="ok"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    for _ in range(2):
        with client.stream("POST", "/api/ai/chat", headers=auth,
                           json={"session_id": sid, "message": "hi"}) as r:
            assert r.status_code == 200
            list(r.iter_lines())
    r = client.post("/api/ai/chat", headers=auth, json={"session_id": sid, "message": "hi"})
    assert r.status_code == 429


def test_anthropic_default_model_and_thinking_disabled(client: TestClient, monkeypatch):
    """Anthropic default bumped to Claude Sonnet 5 (#117 deferred follow-up).
    Sonnet 5 runs adaptive thinking ON when the request omits `thinking` at
    all — a silent behavior change from 4.6 — and thinking output shares the
    same max_tokens ceiling as the reply text, so an unmodified call risks
    the 2048-token budget being consumed by reasoning instead of the answer.
    Explicitly disable thinking on anthropic calls to preserve today's
    behavior; leave non-anthropic providers (no `thinking` support) alone."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    auth = _signup(client, "st6@t.com")
    _install_ai(client, auth)
    sid = _new_session(client, auth)

    calls = []
    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _stream_from([_Chunk(content="hi"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hi"}) as r:
        assert r.status_code == 200
        list(r.iter_lines())

    assert calls[0]["model"] == "anthropic/claude-sonnet-5"
    assert calls[0]["thinking"] == {"type": "disabled"}


def test_non_anthropic_call_has_no_thinking_kwarg(client: TestClient, monkeypatch):
    """openai/gemini reject an unknown `thinking` kwarg — must not be sent."""
    auth, sid = _setup(client, "st7@t.com", monkeypatch)

    calls = []
    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _stream_from([_Chunk(content="hi"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hi"}) as r:
        assert r.status_code == 200
        list(r.iter_lines())

    assert calls[0]["model"] == "openai/gpt-4o-mini"
    assert "thinking" not in calls[0]
