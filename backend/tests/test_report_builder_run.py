"""run_report end-to-end via the engine, against seeded invoices."""
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlmodel import Session
from main import app
from services.report_engine import run_report, ReportConfig, FilterClause, Aggregate


def _auth(client):
    client.post("/api/auth/signup", json={"email": "run@rb.test", "password": "password123",
                                          "full_name": "U", "company_name": "RB Co"})
    r = client.post("/api/auth/login", data={"username": "run@rb.test", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_two_invoices(client, auth):
    c = client.post("/api/customers", headers=auth, json={"name": "Acme"}).json()
    for amt, cur in ((1000, "USD"), (2000, "USD")):
        client.post("/api/invoices", headers=auth, json={
            "customer_id": c["id"], "issue_date": "2026-05-02", "due_date": "2026-06-30",
            "gst_rate": 0, "currency": cur, "lines": [{"description": "S", "qty": 1, "rate": amt}]})


def test_run_filters_and_sums(client: TestClient):
    auth = _auth(client)
    _seed_two_invoices(client, auth)
    with Session(app.state.engine) as s:
        from models import User
        from sqlmodel import select as sel
        user = s.exec(sel(User)).first()
        cfg = ReportConfig(columns=["number", "total"],
                           filters=[FilterClause(field="total", op="gte", value="1500")],
                           aggregates=[Aggregate(field="total", fn="sum")])
        res = run_report(s, tenant_id=user.tenant_id, source_key="invoices",
                         config=cfg, page=0, page_size=100)
    assert res.total_count == 1                       # only the 2000 invoice
    assert res.footers["total"] == "2000.00"
    assert res.rows[0]["total"] == "2000.00"


def test_journal_lines_multi_field_same_join_no_duplicate(client: TestClient):
    """Two fields off the same related table (account_code + account_name, and
    date + jv_number off transaction) must not emit duplicate JOINs."""
    auth = _auth(client)
    _seed_two_invoices(client, auth)   # posting invoices writes journal entries
    with Session(app.state.engine) as s:
        from models import User
        from sqlmodel import select as sel
        user = s.exec(sel(User)).first()
        cfg = ReportConfig(columns=["date", "jv_number", "account_code", "account_name", "debit", "credit"])
        res = run_report(s, tenant_id=user.tenant_id, source_key="journal_lines",
                         config=cfg, page=0, page_size=100)
    assert res.total_count > 0                          # invoice postings produced JE lines
    assert {"account_code", "account_name", "jv_number"} <= set(res.rows[0].keys())
