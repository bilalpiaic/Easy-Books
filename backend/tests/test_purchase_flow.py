"""#137 Phase 1 — Demand → Quotation → Comparative → PO chain."""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str, model: str = "manufacturing") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": model,
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_purchase_store_module_registered(client: TestClient):
    auth = _signup(client, "mod@t.com")
    mods = client.get("/api/modules", headers=auth).json()
    ids = {m["id"] for m in mods}
    assert "purchase_store" in ids
    entry = next(m for m in mods if m["id"] == "purchase_store")
    assert entry["installed"] is True  # manufacturing pre-installs it


def test_permission_resources_registered(client: TestClient):
    from services.permissions import PERMISSION_RESOURCES
    assert "purchase.demand" in PERMISSION_RESOURCES
    assert "purchase.comparative" in PERMISSION_RESOURCES


def _make_demand(client, auth, lines=None):
    r = client.post(
        "/api/purchase-demands",
        headers=auth,
        json={
            "demand_date": "2026-07-04",
            "purpose": "Line restock",
            "lines": lines or [{"description": "Steel rods 12mm", "qty": 100, "unit": "kg"}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _second_admin(client, auth, email="approver@t.com"):
    """Invite a second admin in the same tenant and return their auth header."""
    client.post(
        "/api/users",
        headers=auth,
        json={"email": email, "password": "password123", "full_name": "Approver", "role": "admin"},
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_demand_lifecycle_and_self_approval_block(client: TestClient):
    auth = _signup(client, "pd1@t.com")
    d = _make_demand(client, auth)
    assert d["number"].startswith("PD-") and d["status"] == "draft"
    assert d["lines"][0]["description"] == "Steel rods 12mm"

    # Self-approval must be rejected
    r = client.patch(f"/api/purchase-demands/{d['id']}/approve", headers=auth)
    assert r.status_code == 400
    assert "creator" in r.json()["detail"].lower()

    # A different admin approves
    auth2 = _second_admin(client, auth)
    r = client.patch(f"/api/purchase-demands/{d['id']}/approve", headers=auth2)
    assert r.status_code == 200
    got = client.get(f"/api/purchase-demands/{d['id']}", headers=auth).json()
    assert got["status"] == "approved" and got["approved_by_id"] is not None

    # Editing an approved demand is blocked
    r = client.put(
        f"/api/purchase-demands/{d['id']}", headers=auth,
        json={"demand_date": "2026-07-05", "lines": [{"description": "x", "qty": 1}]},
    )
    assert r.status_code == 400


def test_demand_tenant_isolation(client: TestClient):
    auth_a = _signup(client, "pd2a@t.com")
    auth_b = _signup(client, "pd2b@t.com")
    d = _make_demand(client, auth_a)
    assert client.get(f"/api/purchase-demands/{d['id']}", headers=auth_b).status_code == 404


def _make_vendor(client, auth, name="Acme Steel"):
    r = client.post("/api/vendors", headers=auth, json={"name": name})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _approved_demand(client, auth):
    d = _make_demand(client, auth)
    auth2 = _second_admin(client, auth, email=f"appr-{d['id']}@t.com")
    client.patch(f"/api/purchase-demands/{d['id']}/approve", headers=auth2)
    return client.get(f"/api/purchase-demands/{d['id']}", headers=auth).json(), auth2


def _quote(client, auth, demand, vendor_id, rate):
    return client.post(
        "/api/quotations", headers=auth,
        json={
            "demand_id": demand["id"], "vendor_id": vendor_id, "quote_date": "2026-07-04",
            "lines": [{"demand_line_id": demand["lines"][0]["id"], "rate": rate,
                       "qty": demand["lines"][0]["qty"]}],
        },
    )


def test_quotation_requires_approved_demand(client: TestClient):
    auth = _signup(client, "vq1@t.com")
    v = _make_vendor(client, auth)
    draft = _make_demand(client, auth)
    r = _quote(client, auth, draft, v["id"], 250)
    assert r.status_code == 400  # demand still draft

    approved, _ = _approved_demand(client, auth)
    r = _quote(client, auth, approved, v["id"], 250)
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["number"].startswith("VQ-") and float(q["total"]) == 250 * 100


def test_quotation_update_rejects_foreign_vendor(client: TestClient):
    auth = _signup(client, "vq2@t.com")
    v = _make_vendor(client, auth)
    demand, _ = _approved_demand(client, auth)
    q = _quote(client, auth, demand, v["id"], 250).json()
    r = client.put(f"/api/quotations/{q['id']}", headers=auth, json={
        "demand_id": demand["id"], "vendor_id": 999999, "quote_date": "2026-07-04",
        "lines": [{"demand_line_id": demand["lines"][0]["id"], "rate": 200, "qty": 1}],
    })
    assert r.status_code == 400
    assert "vendor" in r.json()["detail"].lower()


def _cs_setup(client, prefix):
    """Demand with two quotes: vendor A @250 (lowest), vendor B @300."""
    auth = _signup(client, f"{prefix}@t.com")
    va = _make_vendor(client, auth, "Vendor A")
    vb = _make_vendor(client, auth, "Vendor B")
    demand, auth2 = _approved_demand(client, auth)
    qa = _quote(client, auth, demand, va["id"], 250).json()
    qb = _quote(client, auth, demand, vb["id"], 300).json()
    cs = client.post(
        "/api/comparatives", headers=auth,
        json={"demand_id": demand["id"], "cs_date": "2026-07-04"},
    ).json()
    return auth, auth2, demand, qa, qb, cs


def test_cs_lowest_or_justify(client: TestClient):
    auth, auth2, demand, qa, qb, cs = _cs_setup(client, "cs1")

    # Selecting the HIGHER quote without justification → blocked at approve
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": qb["id"], "justification": None})
    r = client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2)
    assert r.status_code == 400 and "justif" in r.json()["detail"].lower()

    # With justification → approved
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": qb["id"],
                     "justification": "Vendor A failed last delivery"})
    r = client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2)
    assert r.status_code == 200

    # Quotations are now frozen
    r = _quote(client, auth, demand, qa["vendor_id"], 111)
    assert r.status_code == 400


def test_cs_self_approval_block_and_convert(client: TestClient):
    auth, auth2, demand, qa, qb, cs = _cs_setup(client, "cs2")
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": qa["id"], "justification": None})

    # Creator cannot approve their own CS
    r = client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth)
    assert r.status_code == 400

    client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2)
    r = client.post(f"/api/comparatives/{cs['id']}/convert-to-po", headers=auth)
    assert r.status_code == 201, r.text
    po = r.json()
    assert po["status"] == "draft"
    assert po["comparative_id"] == cs["id"] and po["demand_id"] == demand["id"]
    assert float(po["total"]) == 250 * 100  # winner's rate × demand qty

    # CS and demand both flip to converted
    assert client.get(f"/api/comparatives/{cs['id']}", headers=auth).json()["status"] == "converted"
    assert client.get(f"/api/purchase-demands/{demand['id']}", headers=auth).json()["status"] == "converted"


def test_cs_single_quote_needs_justification(client: TestClient):
    auth = _signup(client, "cs3@t.com")
    v = _make_vendor(client, auth)
    demand, auth2 = _approved_demand(client, auth)
    q = _quote(client, auth, demand, v["id"], 500).json()
    cs = client.post("/api/comparatives", headers=auth,
                     json={"demand_id": demand["id"], "cs_date": "2026-07-04"}).json()
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": q["id"], "justification": None})
    assert client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2).status_code == 400
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": q["id"], "justification": "Single-source item"})
    assert client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2).status_code == 200


def test_cs_approve_rejects_deleted_selected_quotation(client: TestClient):
    auth, auth2, demand, qa, qb, cs = _cs_setup(client, "cs4")
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": qa["id"], "justification": "x"})
    client.delete(f"/api/quotations/{qa['id']}", headers=auth)
    r = client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2)
    assert r.status_code == 400
    assert "no longer exists" in r.json()["detail"]


def test_cs_approve_rejects_partial_quotation(client: TestClient):
    auth = _signup(client, "cs5@t.com")
    v = _make_vendor(client, auth)
    d = _make_demand(client, auth, lines=[
        {"description": "Item A", "qty": 10, "unit": "pc"},
        {"description": "Item B", "qty": 5, "unit": "pc"},
    ])
    auth2 = _second_admin(client, auth, email="cs5appr@t.com")
    client.patch(f"/api/purchase-demands/{d['id']}/approve", headers=auth2)
    d = client.get(f"/api/purchase-demands/{d['id']}", headers=auth).json()
    # Quote only the FIRST line
    q = client.post("/api/quotations", headers=auth, json={
        "demand_id": d["id"], "vendor_id": v["id"], "quote_date": "2026-07-04",
        "lines": [{"demand_line_id": d["lines"][0]["id"], "rate": 50, "qty": 10}],
    }).json()
    cs = client.post("/api/comparatives", headers=auth,
                     json={"demand_id": d["id"], "cs_date": "2026-07-04"}).json()
    client.put(f"/api/comparatives/{cs['id']}", headers=auth,
               json={"selected_quotation_id": q["id"], "justification": "single source"})
    r = client.patch(f"/api/comparatives/{cs['id']}/approve", headers=auth2)
    assert r.status_code == 400
    assert "does not price" in r.json()["detail"]


def test_chain_enforcement(client: TestClient):
    # manufacturing tenant → purchase_store pre-installed → chain required by default
    auth = _signup(client, "enf1@t.com")
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-04",
        "vendor_name": "Walk-in Vendor",
        "lines": [{"description": "Widget", "qty": 1, "rate": 10}],
    })
    assert r.status_code == 400
    assert "demand" in r.json()["detail"].lower() or "comparative" in r.json()["detail"].lower()

    # Toggle the setting off → bare PO allowed
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-04",
        "vendor_name": "Walk-in Vendor",
        "lines": [{"description": "Widget", "qty": 1, "rate": 10}],
    })
    assert r.status_code == 201, r.text


def test_no_enforcement_without_module(client: TestClient):
    # simple tenant → purchase_store NOT installed → no enforcement
    auth = _signup(client, "enf2@t.com", model="simple")
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-04",
        "vendor_name": "Walk-in Vendor",
        "lines": [{"description": "Widget", "qty": 1, "rate": 10}],
    })
    assert r.status_code == 201, r.text


def test_po_rejects_foreign_or_mismatched_demand(client: TestClient):
    # Tenant A creates a demand; tenant B (module off) must not be able to link it
    auth_a = _signup(client, "sec1a@t.com")
    d = _make_demand(client, auth_a)
    auth_b = _signup(client, "sec1b@t.com", model="simple")
    r = client.post("/api/purchase-orders", headers=auth_b, json={
        "order_date": "2026-07-04", "vendor_name": "V",
        "demand_id": d["id"],
        "lines": [{"description": "Widget", "qty": 1, "rate": 10}],
    })
    assert r.status_code == 400
    assert "demand" in r.json()["detail"].lower()
