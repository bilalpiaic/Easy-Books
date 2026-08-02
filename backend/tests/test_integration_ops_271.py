"""#271 Integration ops: webhook replay, DLQ, quota gates."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import Tenant, WebhookDelivery
from services.queue import enqueue


def _auth(client: TestClient, email: str, company: str = "OpsCo"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": company,
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_webhook_replay_creates_new_attempt_row(client: TestClient):
    auth = _auth(client, "replay@ops.test", "ReplayCo")
    ep = client.post(
        "/api/webhooks",
        headers=auth,
        json={"url": "https://hooks.example/eb", "events": ["customer.created"]},
    ).json()
    client.post("/api/customers", headers=auth, json={"name": "Hook Co"})

    session = Session(client.app.state.engine)
    src = session.exec(select(WebhookDelivery)).first()
    assert src is not None
    src_id = src.id
    session.close()

    r = client.post(
        f"/api/webhooks/{ep['id']}/logs/{src_id}/replay",
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_id"] == src_id
    assert body["status"] == "pending"
    assert body["attempts"] == 0
    assert body["id"] != src_id

    logs = client.get(f"/api/webhooks/{ep['id']}/logs", headers=auth).json()
    assert len(logs) >= 2
    ids = {row["id"] for row in logs}
    assert src_id in ids and body["id"] in ids


def test_document_quota_blocks_invoice_create(client: TestClient):
    auth = _auth(client, "quota@ops.test", "QuotaCo")
    # Force free plan with tiny doc limit
    session = Session(client.app.state.engine)
    tenant = session.exec(select(Tenant)).first()
    assert tenant is not None
    tenant.max_documents = 0
    tenant.plan = "free"
    session.add(tenant)
    session.commit()
    session.close()

    cust = client.post(
        "/api/customers", headers=auth, json={"name": "Buyer"},
    ).json()
    r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-08-01",
            "due_date": "2026-08-31",
            "gst_rate": 0,
            "lines": [{"description": "X", "qty": 1, "rate": 10}],
        },
    )
    assert r.status_code == 402, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "document_quota_exceeded"
    assert "message" in detail


def test_ai_quota_gate(client: TestClient, monkeypatch):
    """Plan/settings AI hourly cap returns structured 429 (#271)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _auth(client, "aiq@ops.test", "AiQuotaCo")
    r = client.post("/api/modules/ai_assistant/install", headers=auth)
    assert r.status_code in (200, 201), r.text
    client.patch("/api/settings", headers=auth, json={
        "ai_api_key_openai": "sk-test",
        "ai_rate_limit_per_hour": "1",
    })
    sid = client.post("/api/ai/sessions", headers=auth, json={}).json()["id"]

    class _Delta:
        def __init__(self, content=None, tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls

    class _Choice:
        def __init__(self, content=None, finish_reason=None, message_content=None):
            self.delta = _Delta(content)
            self.finish_reason = finish_reason
            self.message = type("M", (), {"content": message_content or "general", "tool_calls": None})()

    class _Chunk:
        def __init__(self, content=None, finish_reason=None):
            self.choices = [_Choice(content=content, finish_reason=finish_reason)]

    async def fake_acompletion(**kwargs):
        if kwargs.get("stream"):
            async def gen():
                yield _Chunk(content="ok")
                yield _Chunk(finish_reason="stop")
            return gen()
        return type("Resp", (), {"choices": [_Choice(message_content="general")]})()

    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream(
        "POST", "/api/ai/chat", headers=auth,
        json={"session_id": sid, "message": "hi"},
    ) as r1:
        assert r1.status_code == 200, r1.text
        list(r1.iter_lines())

    r2 = client.post(
        "/api/ai/chat", headers=auth,
        json={"session_id": sid, "message": "again"},
    )
    assert r2.status_code == 429, r2.text
    detail = r2.json()["detail"]
    assert detail["error"] == "ai_quota_exceeded"
    assert detail["limit"] == 1


@pytest.mark.asyncio
async def test_dead_letter_list_and_retry(client: TestClient, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    from services import queue as q
    q._pool = None
    q._REDIS_URL = ""

    auth = _auth(client, "dlq@ops.test", "DlqCo")
    # Force a failed inline enqueue
    result = await enqueue("no_such_task_xyz", tenant_id=1)
    assert result["status"] == "failed"

    rows = client.get("/api/tasks/dead-letter?status=open", headers=auth).json()
    assert any(r["task_name"] == "no_such_task_xyz" for r in rows)

    ops = client.get("/api/tasks/ops", headers=auth).json()
    assert "webhook" in ops and "dead_letter_open" in ops
    assert ops["dead_letter_open"] >= 1

    target = next(r for r in rows if r["task_name"] == "no_such_task_xyz")
    # Retry will fail again (unknown task) but should mark retried
    r = client.post(f"/api/tasks/dead-letter/{target['id']}/retry", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["enqueue"]["status"] == "failed"

    open_rows = client.get("/api/tasks/dead-letter?status=open", headers=auth).json()
    assert all(r["id"] != target["id"] for r in open_rows)
