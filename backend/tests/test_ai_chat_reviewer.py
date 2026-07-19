"""Reviewer stage — silent verify-and-correct between specialist and drafting.

litellm.acompletion is mocked; no network calls. The pipeline's four LLM
calls are distinguished by (stream, max_tokens): triage (False, 30),
reviewer (False, 1500), specialist (True, 2048), drafting (True, 4096).
"""
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


def _events(resp_text_lines):
    out = []
    for line in resp_text_lines:
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


def _tool_turn_responses():
    """Specialist rounds: one tool call, then a raw finding with a wrong figure."""
    return [
        _stream_from([
            _Chunk(tool_calls=[_ToolCallDelta(0, id="call_1", name="get_ar_aging", arguments="")]),
            _Chunk(tool_calls=[_ToolCallDelta(0, arguments="{}")]),
            _Chunk(finish_reason="tool_calls"),
        ]),
        _stream_from([
            _Chunk(content="Customers owe you PKR 99,999."),
            _Chunk(finish_reason="stop"),
        ]),
        _stream_from([
            _Chunk(content="Final drafted reply."),
            _Chunk(finish_reason="stop"),
        ]),
    ]


def test_reviewer_called_and_its_output_reaches_drafting(client: TestClient, monkeypatch):
    """On a tool-using turn the reviewer must run (cheap tier, non-streaming,
    max_tokens=1500, temperature=0) with the specialist's analysis + raw tool
    results, and its corrected text — not the specialist's raw text — must be
    what the drafting stage receives."""
    auth, sid = _setup(client, "rv1@t.com", monkeypatch)

    responses = _tool_turn_responses()
    reviewer_kwargs = {}
    drafting_kwargs = {}
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            if kwargs["max_tokens"] == 30:
                return _Completion("receivables")
            reviewer_kwargs.update(kwargs)
            return _Completion("Customers owe you PKR 12,345.")
        if kwargs["max_tokens"] == 4096:
            drafting_kwargs.update(kwargs)
        return responses.pop(0)
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "who owes me?"}) as r:
        events = _events(list(r.iter_lines()))

    # Reviewer ran on the cheap tier with the right signature.
    assert reviewer_kwargs["max_tokens"] == 1500
    assert reviewer_kwargs["temperature"] == 0
    assert reviewer_kwargs["model"] == "openai/gpt-4o-mini"
    reviewer_payload = json.loads(reviewer_kwargs["messages"][-1]["content"])
    assert reviewer_payload["question"] == "who owes me?"
    assert reviewer_payload["specialist_analysis"] == "Customers owe you PKR 99,999."
    assert reviewer_payload["supporting_data"][0]["name"] == "get_ar_aging"

    # Drafting received the REVIEWED text, not the specialist's raw text.
    drafting_payload = json.loads(drafting_kwargs["messages"][-1]["content"])
    assert drafting_payload["specialist_analysis"] == "Customers owe you PKR 12,345."

    # The "Reviewing figures…" stage fired between tool_end and drafting.
    labels = [e.get("label", "") for e in events if e["type"] == "stage"]
    assert "Reviewing figures…" in labels
    assert events[-1]["type"] == "done"
    assert events[-1]["reply"] == "Final drafted reply."


def test_no_tool_turn_skips_reviewer(client: TestClient, monkeypatch):
    """A turn with no tool calls has nothing to verify — the reviewer must
    not run and the event sequence must stay exactly as before."""
    auth, sid = _setup(client, "rv2@t.com", monkeypatch)

    non_streaming_calls = []
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            non_streaming_calls.append(kwargs["max_tokens"])
            return _Completion("general")
        return _stream_from([_Chunk(content="hi!"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hello"}) as r:
        events = _events(list(r.iter_lines()))

    assert non_streaming_calls == [30]      # triage only, no reviewer
    types = [e["type"] for e in events]
    assert types == ["stage", "stage", "stage", "token", "done"]
    labels = [e.get("label", "") for e in events if e["type"] == "stage"]
    assert "Reviewing figures…" not in labels


def test_reviewer_failure_falls_back_to_specialist_text(client: TestClient, monkeypatch):
    """A reviewer exception must never abort the stream — drafting receives
    the raw specialist text and the turn completes normally."""
    auth, sid = _setup(client, "rv3@t.com", monkeypatch)

    responses = _tool_turn_responses()
    drafting_kwargs = {}
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            if kwargs["max_tokens"] == 30:
                return _Completion("receivables")
            raise RuntimeError("reviewer provider timed out")
        if kwargs["max_tokens"] == 4096:
            drafting_kwargs.update(kwargs)
        return responses.pop(0)
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "who owes me?"}) as r:
        events = _events(list(r.iter_lines()))

    assert events[-1]["type"] == "done"
    drafting_payload = json.loads(drafting_kwargs["messages"][-1]["content"])
    assert drafting_payload["specialist_analysis"] == "Customers owe you PKR 99,999."


def test_reviewer_empty_output_falls_back_to_specialist_text(client: TestClient, monkeypatch):
    """An empty reviewer response is treated like a failure — the specialist
    text passes through unchanged."""
    auth, sid = _setup(client, "rv4@t.com", monkeypatch)

    responses = _tool_turn_responses()
    drafting_kwargs = {}
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            if kwargs["max_tokens"] == 30:
                return _Completion("receivables")
            return _Completion("")
        if kwargs["max_tokens"] == 4096:
            drafting_kwargs.update(kwargs)
        return responses.pop(0)
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "who owes me?"}) as r:
        events = _events(list(r.iter_lines()))

    assert events[-1]["type"] == "done"
    drafting_payload = json.loads(drafting_kwargs["messages"][-1]["content"])
    assert drafting_payload["specialist_analysis"] == "Customers owe you PKR 99,999."
