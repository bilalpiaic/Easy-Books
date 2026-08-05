"""Tests for WS-2: admin endpoints to load/remove demo sample data.

GET   /api/admin/demo/status — catalog + loaded flags, admin+ only
POST  /api/admin/demo/seed  — full or per-email seeder, admin+ only
DELETE /api/admin/demo/seed  — purge demo tenants, admin+ only
"""
from scripts.seed_demo import DEMO_TENANTS

DEMO_N = len(DEMO_TENANTS)  # 8 (incl. spinning)


def test_demo_status_and_per_email_seed(client, admin_headers):
    headers = admin_headers

    assert client.get("/api/admin/demo/status").status_code == 401

    st = client.get("/api/admin/demo/status", headers=headers)
    assert st.status_code == 200, st.text
    tenants = st.json()["tenants"]
    assert len(tenants) == DEMO_N
    assert {t["email"] for t in tenants} == {e for e, _, _ in DEMO_TENANTS}
    assert all("exists" in t and "loaded" in t for t in tenants)

    # Unknown email → 400
    bad = client.post(
        "/api/admin/demo/seed",
        headers=headers,
        json={"email": "not.a.demo@example.com"},
    )
    assert bad.status_code == 400

    # Per-email seed — one report
    r = client.post(
        "/api/admin/demo/seed",
        headers=headers,
        json={"email": "demo.simple@easy-books.app"},
    )
    assert r.status_code == 200, r.text
    reports = r.json()["tenants"]
    assert len(reports) == 1
    assert reports[0]["email"] == "demo.simple@easy-books.app"
    assert "error" not in reports[0]

    st2 = client.get("/api/admin/demo/status", headers=headers)
    simple = next(t for t in st2.json()["tenants"] if t["email"] == "demo.simple@easy-books.app")
    assert simple["exists"] is True
    assert simple["loaded"] is True


def test_demo_seed_is_idempotent_and_admin_gated(client, admin_headers):
    # 1. No token → 401
    assert client.post("/api/admin/demo/seed").status_code == 401

    headers = admin_headers

    # 2. First full seed — creates all demo tenants with rich data
    #    (+ optional consolidation/intercompany summary entries without email)
    r1 = client.post("/api/admin/demo/seed", headers=headers)
    assert r1.status_code == 200, r1.text
    email_reports = [t for t in r1.json()["tenants"] if "email" in t]
    assert len(email_reports) == DEMO_N

    # 3. Second seed — idempotent; same emails, no error, no duplicates
    r2 = client.post("/api/admin/demo/seed", headers=headers)
    assert r2.status_code == 200
    emails = {t["email"] for t in r2.json()["tenants"] if "email" in t}
    assert "demo.simple@easy-books.app" in emails
    assert "demo.spinning@easy-books.app" in emails
    assert len(emails) == DEMO_N

    # 4. Purge — removes at least the demo tenants
    rd = client.delete("/api/admin/demo/seed", headers=headers)
    assert rd.status_code == 200, rd.text
    assert rd.json()["removed_tenants"] >= DEMO_N

    # 5. The caller's OWN tenant must survive the purge (the critical safety
    #    invariant: purge deletes only the demo tenants, never the caller's data).
    relogin = client.post(
        "/api/auth/login",
        data={"username": "owner@acme.test", "password": "pw12345678"},
    )
    assert relogin.status_code == 200, "purge must not delete the caller's own account"
    # And a second purge is a harmless no-op once the demo tenants are gone.
    rd2 = client.delete("/api/admin/demo/seed", headers=headers)
    assert rd2.status_code == 200
    assert rd2.json()["removed_tenants"] == 0
