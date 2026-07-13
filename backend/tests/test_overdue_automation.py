"""Core-platform leftovers: daily overdue sweep + aging reminder emails.

sweep_overdue: one cross-tenant SQL UPDATE flips past-due open/sent invoices
to 'overdue' (draft/void/paid/partial are never touched — narrower than the
per-fetch _auto_overdue, which is retained for freshness between sweeps).

send_overdue_reminders: for tenants with email_notifications=true, one email
per customer listing their overdue invoices with balance due; throttled per
tenant via the Settings KV (overdue_reminder_interval_days, default 7).
"""
from datetime import date, timedelta

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> dict:
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _invoice(client, auth, *, due, status="open", customer_id=None):
    # POST /api/invoices always creates in "draft" regardless of any status
    # field in the body; PATCH .../status is the only way to set it directly.
    body = {
        "issue_date": "2026-01-01", "due_date": due,
        "customer_name": "C",
        "lines": [{"description": "svc", "qty": 1, "rate": 100}],
    }
    if customer_id:
        body["customer_id"] = customer_id
    r = client.post("/api/invoices", headers=auth, json=body)
    assert r.status_code == 201, r.text
    inv = r.json()
    if status != "draft":
        r = client.patch(f"/api/invoices/{inv['id']}/status", headers=auth,
                         params={"status": status})
        assert r.status_code == 200, r.text
        inv = r.json()
    return inv


def _session(client):
    from sqlmodel import Session
    import db as _db
    return Session(_db.engine)


def test_sweep_marks_only_past_due_open_invoices(client: TestClient):
    from services.overdue import sweep_overdue

    auth = _signup(client, "od1@t.com")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    past_open = _invoice(client, auth, due=yesterday, status="open")
    future_open = _invoice(client, auth, due=tomorrow, status="open")
    past_draft = _invoice(client, auth, due=yesterday, status="draft")

    with _session(client) as s:
        changed = sweep_overdue(s)
    assert changed == 1

    from models import Invoice
    with _session(client) as s:
        assert s.get(Invoice, past_open["id"]).status == "overdue"
        assert s.get(Invoice, future_open["id"]).status == "open"
        assert s.get(Invoice, past_draft["id"]).status == "draft"


def test_reminders_email_per_customer_and_throttle(client: TestClient, monkeypatch):
    import services.overdue as overdue_mod
    from services.overdue import send_overdue_reminders, sweep_overdue

    sent = []
    monkeypatch.setattr(overdue_mod, "send_email",
                        lambda to, subject, html_body: sent.append((to, subject, html_body)))

    auth = _signup(client, "od2@t.com")
    client.patch("/api/settings", headers=auth, json={"email_notifications": "true"})

    cust = client.post("/api/customers", headers=auth,
                       json={"name": "Mail Co", "email": "billing@mailco.test"}).json()
    no_mail = client.post("/api/customers", headers=auth, json={"name": "Silent Co"}).json()

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _invoice(client, auth, due=yesterday, status="open", customer_id=cust["id"])
    _invoice(client, auth, due=yesterday, status="open", customer_id=cust["id"])
    _invoice(client, auth, due=yesterday, status="open", customer_id=no_mail["id"])

    with _session(client) as s:
        sweep_overdue(s)
        n = send_overdue_reminders(s)
    assert n == 1  # one email for Mail Co (2 invoices), none for Silent Co
    assert sent[0][0] == "billing@mailco.test"
    assert "overdue" in sent[0][1].lower()

    # throttle: a second run the same day sends nothing
    with _session(client) as s:
        assert send_overdue_reminders(s) == 0
    assert len(sent) == 1


def test_scheduler_runs_sweep_once_on_startup_and_cancels_cleanly(client: TestClient, monkeypatch):
    """main.py wires _overdue_scheduler_loop into the FastAPI lifespan: fires
    once immediately, then sleeps OVERDUE_SWEEP_INTERVAL_HOURS. Drive the
    lifespan directly (no test in this repo runs TestClient as a context
    manager, so this is the only path that exercises the wiring) and confirm
    the background task both runs and shuts down cleanly on exit."""
    import asyncio
    import main as main_mod

    calls = []
    monkeypatch.setattr(main_mod, "_run_overdue_sweep_once", lambda: calls.append(1))
    monkeypatch.setenv("OVERDUE_SWEEP_ENABLED", "true")
    monkeypatch.setenv("OVERDUE_SWEEP_INTERVAL_HOURS", "100")  # long enough not to tick twice
    monkeypatch.setenv("SCHEMA_BOOTSTRAP", "alembic")  # skip create_db_and_tables in this test

    async def _drive():
        async with main_mod.lifespan(main_mod.app):
            for _ in range(200):
                if calls:
                    break
                await asyncio.sleep(0.01)

    asyncio.run(_drive())
    assert calls == [1]


def test_reminders_skip_tenants_without_notifications(client: TestClient, monkeypatch):
    import services.overdue as overdue_mod
    from services.overdue import send_overdue_reminders, sweep_overdue

    sent = []
    monkeypatch.setattr(overdue_mod, "send_email",
                        lambda to, subject, html_body: sent.append(to))

    auth = _signup(client, "od3@t.com")  # email_notifications unset
    cust = client.post("/api/customers", headers=auth,
                       json={"name": "Quiet", "email": "q@t.test"}).json()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _invoice(client, auth, due=yesterday, status="open", customer_id=cust["id"])

    with _session(client) as s:
        sweep_overdue(s)
        assert send_overdue_reminders(s) == 0
    assert sent == []
