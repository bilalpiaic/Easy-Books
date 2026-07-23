"""Tests for ARQ task queue + health (#115 / #116) — Redis-free sync path."""
from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_enqueue_email_runs_inline_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    from services import queue as q
    q._pool = None
    q._REDIS_URL = ""

    called = {}

    def fake_send(to, subject, html_body):
        called["to"] = to
        called["subject"] = subject

    monkeypatch.setattr("services.email.send_email", fake_send)
    result = await q.enqueue("send_email_task", "a@b.co", "Hi", "<p>x</p>")
    assert result["status"] == "complete"
    assert called["to"] == "a@b.co"


@pytest.mark.asyncio
async def test_enqueue_unknown_task_fails(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    from services import queue as q
    q._pool = None
    q._REDIS_URL = ""
    result = await q.enqueue("no_such_task")
    assert result["status"] == "failed"


def test_health_endpoint(client, admin_headers):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok"
    assert body["storage"] == "ok"
    assert body["redis"] == "skipped"
    assert "version" in body


def test_task_status_sync_id(client, admin_headers):
    r = client.get("/api/tasks/sync-send_email_task", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "complete"


def test_storage_local_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    from importlib import reload
    import local_config
    import services.storage as storage
    reload(local_config)
    reload(storage)
    url = storage.upload_file("t1/hello.txt", b"hello", "text/plain")
    assert url.startswith("/uploads/")
    assert storage.download_file("t1/hello.txt") == b"hello"
    assert storage.get_file_url("t1/hello.txt").startswith("/uploads/")


@pytest.mark.asyncio
async def test_pdf_task_writes_local(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.delenv("REDIS_URL", raising=False)
    from importlib import reload
    import local_config
    import services.storage as storage
    reload(local_config)
    reload(storage)

    # Stub WeasyPrint-heavy render
    monkeypatch.setattr(
        "services.pdf.render_invoice_pdf",
        lambda *a, **k: b"%PDF-fake",
    )
    from services import queue as q
    q._pool = None
    q._REDIS_URL = ""
    data = json.dumps({"invoice": {"number": "INV-1"}, "lines": []})
    result = await q.enqueue(
        "generate_pdf_task", "invoice", data, "t1/pdfs/INV-1.pdf", "Acme", ""
    )
    assert result["status"] == "complete"
    assert result["result"]["ok"] is True
    assert storage.download_file("t1/pdfs/INV-1.pdf") == b"%PDF-fake"
