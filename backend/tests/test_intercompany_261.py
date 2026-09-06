"""#261 Intercompany invoices/bills + IC reconciliation."""
from __future__ import annotations

from datetime import date, timedelta

import jwt
from fastapi.testclient import TestClient

from auth import ALGORITHM, SECRET_KEY


def _doc_dates():
    """Keep due dates in the future so list _auto_overdue does not flip draft mirrors."""
    issue = date.today().isoformat()
    due = (date.today() + timedelta(days=30)).isoformat()
    return issue, due


def _signup(client: TestClient, email: str, company: str) -> dict:
    r = client.post("/api/auth/signup", json={
        "email": email,
        "password": "pw12345678",
        "full_name": email.split("@")[0].title(),
        "company_name": company,
        "business_model": "simple",
    })
    assert r.status_code == 200, r.text
    return r.json()


def _login(client: TestClient, email: str) -> str:
    client.cookies.clear()
    r = client.post("/api/auth/login", data={"username": email, "password": "pw12345678"})
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return r.json()["access_token"]


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _attach(client, owner_tok: str, email: str, role: str = "accountant"):
    r = client.post(
        "/api/users/invites",
        headers=_hdr(owner_tok),
        json={"email": email, "role": role},
    )
    assert r.status_code in (200, 201), r.text
    assert r.json().get("attached") is True


def _setup_group(client: TestClient):
    """Parent HoldCo + SubCo; HoldCo owner is member of both (same as #255)."""
    _signup(client, "hold@ic261.test", "HoldCo IC")
    _signup(client, "sub@ic261.test", "SubCo IC")
    hold_tok = _login(client, "hold@ic261.test")
    sub_tok = _login(client, "sub@ic261.test")
    sub_tid = jwt.decode(sub_tok, SECRET_KEY, algorithms=[ALGORITHM])["tenant_id"]
    hold_tid = jwt.decode(hold_tok, SECRET_KEY, algorithms=[ALGORITHM])["tenant_id"]

    _attach(client, sub_tok, "hold@ic261.test", "accountant")
    hold_tok = _login(client, "hold@ic261.test")

    r = client.get("/api/consolidation/members", headers=_hdr(hold_tok))
    assert r.status_code == 200, r.text

    r = client.post("/api/consolidation/members", headers=_hdr(hold_tok), json={
        "member_tenant_id": sub_tid,
        "relationship": "subsidiary",
        "ownership_pct": 100,
        "ic_ar_code": "1180",
        "ic_ap_code": "2180",
    })
    assert r.status_code == 201, r.text

    return hold_tok, sub_tok, hold_tid, sub_tid


def test_ic_invoice_creates_mirror_draft_bill(client: TestClient):
    hold_tok, sub_tok, hold_tid, sub_tid = _setup_group(client)

    cps = client.get("/api/intercompany/counterparties", headers=_hdr(hold_tok))
    assert cps.status_code == 200, cps.text
    assert any(c["tenant_id"] == sub_tid for c in cps.json())

    # IC invoice Hold → Sub (posts GL on Hold; mirrors draft bill on Sub)
    issue, due = _doc_dates()
    r = client.post("/api/invoices", headers=_hdr(hold_tok), json={
        "customer_name": "SubCo IC",
        "issue_date": issue,
        "due_date": due,
        "gst_rate": 0,
        "is_intercompany": True,
        "ic_counterparty_tenant_id": sub_tid,
        "lines": [{"description": "IC management fee", "qty": 1, "rate": 1500}],
    })
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["is_intercompany"] is True
    assert inv["ic_counterparty_tenant_id"] == sub_tid
    assert inv["ic_mirror_bill_id"] is not None
    assert float(inv["total"]) == 1500.0
    assert inv["transaction_id"] is not None

    # Sister draft bill: same total, no GL
    bills = client.get("/api/bills?search=IC", headers=_hdr(sub_tok)).json()
    mirror = next(
        (b for b in bills["items"] if b["id"] == inv["ic_mirror_bill_id"]),
        None,
    )
    assert mirror is not None, bills
    assert mirror["status"] == "draft"
    assert mirror["transaction_id"] is None
    assert float(mirror["total"]) == float(inv["total"])
    assert mirror["is_intercompany"] is True
    assert mirror["ic_counterparty_tenant_id"] == hold_tid
    assert mirror["ic_mirror_invoice_id"] == inv["id"]
    assert mirror["vendor_name"] == "IC Counterpart"


def test_recon_shows_break_when_only_ar_posted(client: TestClient):
    hold_tok, sub_tok, hold_tid, sub_tid = _setup_group(client)

    issue, due = _doc_dates()
    r = client.post("/api/invoices", headers=_hdr(hold_tok), json={
        "customer_name": "SubCo IC",
        "issue_date": issue,
        "due_date": due,
        "gst_rate": 0,
        "is_intercompany": True,
        "ic_counterparty_tenant_id": sub_tid,
        "lines": [{"description": "IC sale", "qty": 1, "rate": 800}],
    })
    assert r.status_code == 201, r.text

    # Mirror is draft (no transaction_id) → AR open, AP open 0 → break
    recon = client.get("/api/intercompany/recon", headers=_hdr(hold_tok))
    assert recon.status_code == 200, recon.text
    body = recon.json()
    assert "total" in body and "items" in body
    assert body["total"] >= 1
    row = next(
        (
            i for i in body["items"]
            if i["from_tenant_id"] == hold_tid and i["to_tenant_id"] == sub_tid
        ),
        None,
    )
    assert row is not None, body
    assert abs(row["ar_open"] - 800) < 0.01
    assert abs(row["ap_open"]) < 0.01
    assert row["status"] == "break"
    assert abs(row["variance"] - 800) < 0.01
