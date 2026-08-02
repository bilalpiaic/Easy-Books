"""#255 Multi-entity consolidation (IFRS 10) — IC elim, NCI, locked-period gate."""
from __future__ import annotations

import jwt
from fastapi.testclient import TestClient

from auth import ALGORITHM, SECRET_KEY


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


def _by_code(client, headers):
    accts = client.get("/api/accounts?limit=500", headers=headers).json()["items"]
    return {a["code"]: a["id"] for a in accts}


def _post_jv(client, headers, jv_date, entries, description="consol test"):
    by_code = _by_code(client, headers)
    r = client.post("/api/transactions", headers=headers, json={
        "date": jv_date,
        "description": description,
        "entries": [
            {"account_id": by_code[code], "debit": debit, "credit": credit}
            for code, debit, credit in entries
        ],
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _attach(client, owner_tok: str, email: str, role: str = "accountant"):
    r = client.post(
        "/api/users/invites",
        headers=_hdr(owner_tok),
        json={"email": email, "role": role},
    )
    assert r.status_code in (200, 201), r.text
    assert r.json().get("attached") is True


def _setup_group(client: TestClient):
    """Parent HoldCo + SubCo; HoldCo owner is member of both."""
    _signup(client, "hold@consol.test", "HoldCo")
    _signup(client, "sub@consol.test", "SubCo")
    hold_tok = _login(client, "hold@consol.test")
    sub_tok = _login(client, "sub@consol.test")
    sub_tid = jwt.decode(sub_tok, SECRET_KEY, algorithms=[ALGORITHM])["tenant_id"]
    hold_tid = jwt.decode(hold_tok, SECRET_KEY, algorithms=[ALGORITHM])["tenant_id"]

    _attach(client, sub_tok, "hold@consol.test", "accountant")
    # Re-login so membership is fresh (token still HoldCo active)
    hold_tok = _login(client, "hold@consol.test")

    # Ensure parent member exists + add subsidiary with IC codes
    r = client.get("/api/consolidation/members", headers=_hdr(hold_tok))
    assert r.status_code == 200, r.text
    assert any(m["relationship"] == "parent" for m in r.json())

    r = client.post("/api/consolidation/members", headers=_hdr(hold_tok), json={
        "member_tenant_id": sub_tid,
        "relationship": "subsidiary",
        "ownership_pct": 80,
        "ic_ar_code": "1100",
        "ic_ap_code": "2000",
    })
    assert r.status_code == 201, r.text

    # Also set IC codes on parent for reverse direction
    members = client.get("/api/consolidation/members", headers=_hdr(hold_tok)).json()
    parent = next(m for m in members if m["relationship"] == "parent")
    client.patch(
        f"/api/consolidation/members/{parent['id']}",
        headers=_hdr(hold_tok),
        json={"ic_ar_code": "1100", "ic_ap_code": "2000"},
    )

    return hold_tok, sub_tok, hold_tid, sub_tid


def test_ic_balance_eliminates_to_zero(client: TestClient):
    hold_tok, sub_tok, _, _ = _setup_group(client)

    # Sub owes Hold: Sub AP 2000 Cr 500 / Hold AR 1100 Dr 500
    # Fund via bank/cash + capital so entries balance
    # Hold: Dr AR 1100 500 / Cr Revenue 4100 500  (IC receivable)
    _post_jv(client, _hdr(hold_tok), "2026-07-15", [
        ("1100", 500, 0),
        ("4000", 0, 500),
    ], "IC sale to sub")
    # Sub: Dr Expense 5100 500 / Cr AP 2000 500
    _post_jv(client, _hdr(sub_tok), "2026-07-15", [
        ("5100", 500, 0),
        ("2000", 0, 500),
    ], "IC purchase from parent")

    # Also give both some equity so NCI math is non-zero later
    _post_jv(client, _hdr(hold_tok), "2026-07-01", [
        ("1000", 10000, 0),
        ("3000", 0, 10000),
    ], "capital")
    _post_jv(client, _hdr(sub_tok), "2026-07-01", [
        ("1000", 4000, 0),
        ("3000", 0, 4000),
    ], "capital")

    r = client.post("/api/consolidation/runs", headers=_hdr(hold_tok), json={
        "period_start": "2026-07-01",
        "period_end": "2026-07-31",
        "name": "Jul consol",
    })
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]

    lines = client.post(
        f"/api/consolidation/runs/{run_id}/propose", headers=_hdr(hold_tok),
    )
    assert lines.status_code == 200, lines.text
    elims = lines.json()
    ic = [e for e in elims if e["kind"] == "ic_balance"]
    assert len(ic) >= 2
    ic_dr = sum(e["debit"] for e in ic)
    ic_cr = sum(e["credit"] for e in ic)
    assert abs(ic_dr - ic_cr) < 0.01
    assert abs(ic_dr - 500) < 0.01

    stmts = client.get(
        f"/api/consolidation/runs/{run_id}/statements", headers=_hdr(hold_tok),
    ).json()
    # After elim, worksheet AR/AP IC should net toward zero on those codes
    ws = {w["code"]: w for w in stmts["worksheet"]}
    # Combined AR before elim was 500 (hold only for IC); elim credits AR 500 → ~0 IC remnant
    # AP on sub was 500; elim debits AP 500 → ~0
    assert abs(ws.get("1100", {}).get("balance", 0)) < 0.01 or abs(
        ws["1100"]["debit"] - ws["1100"]["credit"]
    ) < 0.01
    if "2000" in ws:
        assert abs(ws["2000"]["debit"] - ws["2000"]["credit"]) < 0.01


def test_nci_math(client: TestClient):
    hold_tok, sub_tok, _, _ = _setup_group(client)

    # Sub equity 1,000 via capital (ownership 80% → NCI 20% = 200)
    _post_jv(client, _hdr(sub_tok), "2026-07-01", [
        ("1000", 1000, 0),
        ("3000", 0, 1000),
    ])
    _post_jv(client, _hdr(hold_tok), "2026-07-01", [
        ("1000", 5000, 0),
        ("3000", 0, 5000),
    ])

    run_id = client.post("/api/consolidation/runs", headers=_hdr(hold_tok), json={
        "period_start": "2026-07-01", "period_end": "2026-07-31",
    }).json()["id"]

    elims = client.post(
        f"/api/consolidation/runs/{run_id}/propose", headers=_hdr(hold_tok),
    ).json()
    nci = [e for e in elims if e["kind"] == "nci"]
    assert nci, "expected NCI elimination lines"
    nci_credit = sum(e["credit"] for e in nci if e["account_code"] == "NCI")
    assert abs(nci_credit - 200) < 0.01


def test_locked_period_blocks_accountant_allows_owner(client: TestClient):
    hold_tok, sub_tok, hold_tid, _ = _setup_group(client)
    _post_jv(client, _hdr(hold_tok), "2026-07-01", [
        ("1000", 100, 0), ("3000", 0, 100),
    ])
    _post_jv(client, _hdr(sub_tok), "2026-07-01", [
        ("1000", 50, 0), ("3000", 0, 50),
    ])

    # Disable checklist requirement so soft-close works
    client.patch(
        "/api/settings",
        headers=_hdr(hold_tok),
        json={"period_close_require_checklist": "false"},
    )
    period = client.post("/api/periods", headers=_hdr(hold_tok), json={
        "name": "Jul", "period_start": "2026-07-01", "period_end": "2026-07-31",
    }).json()
    close = client.post(f"/api/periods/{period['id']}/close?mode=soft", headers=_hdr(hold_tok))
    assert close.status_code == 200, close.text

    run_id = client.post("/api/consolidation/runs", headers=_hdr(hold_tok), json={
        "period_start": "2026-07-01", "period_end": "2026-07-31",
    }).json()["id"]
    client.post(f"/api/consolidation/runs/{run_id}/propose", headers=_hdr(hold_tok))

    # Invite an accountant on HoldCo and try post as them
    client.post("/api/auth/signup", json={
        "email": "acct@consol.test",
        "password": "pw12345678",
        "full_name": "Acct",
        "company_name": "OtherCo",
    })
    # Attach accountant to HoldCo
    inv = client.post("/api/users/invites", headers=_hdr(hold_tok), json={
        "email": "acct@consol.test", "role": "accountant",
    })
    assert inv.status_code in (200, 201), inv.text

    # Switch accountant into HoldCo
    acct_tok = _login(client, "acct@consol.test")
    switched = client.post(
        "/api/auth/switch-tenant",
        headers=_hdr(acct_tok),
        json={"tenant_id": hold_tid},
    )
    assert switched.status_code == 200, switched.text
    acct_hold = switched.json()["access_token"]

    blocked = client.post(
        f"/api/consolidation/runs/{run_id}/post", headers=_hdr(acct_hold),
    )
    assert blocked.status_code == 403, blocked.text
    assert "locked" in blocked.json()["detail"].lower()

    # Owner can override
    ok = client.post(
        f"/api/consolidation/runs/{run_id}/post", headers=_hdr(hold_tok),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "posted"
    assert ok.json()["package"] is not None

    # Immutable: propose fails
    again = client.post(
        f"/api/consolidation/runs/{run_id}/propose", headers=_hdr(hold_tok),
    )
    assert again.status_code == 400
