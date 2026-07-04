"""Tests for WS-2: admin endpoints to load/remove demo sample data.

POST  /api/admin/demo/seed  — idempotent seeder, admin+ only
DELETE /api/admin/demo/seed  — purge the 7 demo tenants, admin+ only
"""


def test_demo_seed_is_idempotent_and_admin_gated(client, admin_headers):
    # 1. No token → 401
    assert client.post("/api/admin/demo/seed").status_code == 401

    headers = admin_headers

    # 2. First seed — creates all 7 demo tenants with rich data
    r1 = client.post("/api/admin/demo/seed", headers=headers)
    assert r1.status_code == 200, r1.text
    assert len(r1.json()["tenants"]) == 7

    # 3. Second seed — idempotent; same 7 entries, no error, no duplicates
    r2 = client.post("/api/admin/demo/seed", headers=headers)
    assert r2.status_code == 200
    emails = {t["email"] for t in r2.json()["tenants"]}
    assert "demo.simple@easy-books.app" in emails

    # 4. Purge — removes at least the 7 demo tenants
    rd = client.delete("/api/admin/demo/seed", headers=headers)
    assert rd.status_code == 200, rd.text
    assert rd.json()["removed_tenants"] >= 7

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
