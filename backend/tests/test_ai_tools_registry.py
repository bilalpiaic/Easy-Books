"""services/ai_tools registry integrity + dispatch, and the invariants the
triage/specialist pipeline depends on (agent tools ⊆ registry, no agent key a
substring of another). No LLM calls — pure registry + executor checks."""
import json

from services.ai_agents import AGENTS
from services.ai_tools import (
    MAX_TOOL_RESULT_CHARS,
    TOOL_REGISTRY,
    anthropic_tools,
    execute_tool,
    openai_tools,
    tool_labels,
)


def test_registry_entries_are_complete():
    assert len(TOOL_REGISTRY) >= 7
    for name, tool in TOOL_REGISTRY.items():
        assert tool.name == name
        assert tool.description.strip()
        assert tool.label.strip()
        assert tool.input_schema.get("type") == "object"
        assert callable(tool.executor)


def test_openai_derivation_shape_and_order():
    names = list(TOOL_REGISTRY)[:3]
    derived = openai_tools(names)
    assert [d["function"]["name"] for d in derived] == names
    for d in derived:
        assert d["type"] == "function"
        t = TOOL_REGISTRY[d["function"]["name"]]
        assert d["function"]["description"] == t.description
        assert d["function"]["parameters"] == t.input_schema


def test_anthropic_derivation_shape():
    derived = anthropic_tools(["get_ar_aging"])
    assert derived == [{
        "name": "get_ar_aging",
        "description": TOOL_REGISTRY["get_ar_aging"].description,
        "input_schema": TOOL_REGISTRY["get_ar_aging"].input_schema,
    }]


def test_unknown_names_are_dropped_from_derivations():
    assert openai_tools(["not_a_tool"]) == []
    assert anthropic_tools(["not_a_tool"]) == []


def test_tool_labels_cover_every_tool():
    labels = tool_labels()
    assert set(labels) == set(TOOL_REGISTRY)
    assert all(v.strip() for v in labels.values())


def test_execute_unknown_tool_returns_error_tuple():
    text, is_error = execute_tool("nope", {}, None, None)
    assert is_error is True
    assert "Unknown tool" in json.loads(text)["error"]


def test_execute_tool_exception_becomes_error_payload():
    # session=None makes any real executor blow up — the exception must come
    # back as a recoverable error payload, never propagate.
    text, is_error = execute_tool("get_ar_aging", {}, None, None)
    assert is_error is True
    assert "error" in json.loads(text)


def test_oversized_result_is_truncated(monkeypatch):
    big = {"rows": ["x" * 100] * 500}   # far beyond MAX_TOOL_RESULT_CHARS
    # ToolDef is frozen — patch the report function the executor wraps instead.
    monkeypatch.setattr("services.ai_tools.invoice_aging", lambda s, u: big)
    text, is_error = execute_tool("get_ar_aging", {}, None, None)
    assert is_error is False
    payload = json.loads(text)
    assert payload["truncated"] is True
    assert len(payload["data"]) == MAX_TOOL_RESULT_CHARS


def test_every_agent_tool_is_registered():
    for agent in AGENTS.values():
        unknown = set(agent.tools) - set(TOOL_REGISTRY)
        assert not unknown, f"agent {agent.key!r} references unknown tools: {sorted(unknown)}"


def test_no_agent_key_is_substring_of_another():
    """_run_triage's fallback matcher does bidirectional substring matching —
    one agent key containing another would make routing ambiguous."""
    keys = list(AGENTS)
    for a in keys:
        for b in keys:
            if a != b:
                assert a not in b, f"agent key {a!r} is a substring of {b!r}"
