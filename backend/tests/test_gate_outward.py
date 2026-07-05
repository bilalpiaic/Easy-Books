"""#137 Phase 2b — Gate Outward: invoice/debit-note memo exits + scrap draft→approve."""
from decimal import Decimal

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


def test_gate_outward_models_and_permission_registered(client: TestClient):
    from models import GateOutward, GateOutwardLine  # importable = tables exist
    from services.permissions import PERMISSION_RESOURCES
    assert "store.gate_outward" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["store.gate_outward"]["category"] == "Store"


def test_consume_stock_accepts_source_doc_type_override(client: TestClient):
    """Existing callers (invoices) still get 'invoice'; new callers can override."""
    from decimal import Decimal
    from sqlmodel import Session, select
    from models import Product, StockMovement, Tenant
    from services.inventory import consume_stock
    import db as _db

    with Session(_db.engine) as s:
        t = Tenant(name="ConsCo"); s.add(t); s.commit(); s.refresh(t)
        p = Product(tenant_id=t.id, name="Widget", product_type="stock",
                    stock_qty=Decimal("50"), avg_cost=Decimal("10"))
        s.add(p); s.commit(); s.refresh(p)

        cogs = consume_stock(
            s, tenant_id=t.id, product_id=p.id, qty=Decimal("5"),
            source_doc_id=999, source_doc_type="gate_outward",
        )
        s.commit()
        assert cogs == Decimal("50")  # 5 * avg_cost(10)

        mv = s.exec(
            select(StockMovement).where(StockMovement.product_id == p.id)
        ).first()
        assert mv.source_doc_type == "gate_outward"
        assert mv.source_doc_id == 999


def _posted_invoice(client, auth, lines=None):
    lines = lines or [{"description": "Widget", "qty": 3, "rate": 20}]
    for ln in lines:
        if "product_id" not in ln:
            p = client.post("/api/products", headers=auth,
                             json={"name": ln["description"], "product_type": "stock"})
            ln["product_id"] = p.json()["id"]
    r = client.post("/api/invoices", headers=auth, json={
        "issue_date": "2026-07-06", "due_date": "2026-08-06",
        "customer_name": "Walk-in Customer",
        "lines": lines,
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_go_invoice_memo_lifecycle(client: TestClient):
    auth = _signup(client, "go1@t.com")
    inv = _posted_invoice(client, auth)

    r = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv["id"],
        "gate_date": "2026-07-06", "vehicle_no": "LEB-1111",
        "lines": [{"product_id": inv["lines"][0]["product_id"], "qty": 3}],
    })
    assert r.status_code == 201, r.text
    go = r.json()
    assert go["number"].startswith("GO-")
    assert go["status"] == "approved"  # immediate, no draft step for memo exits

    r = client.patch(f"/api/gate-outwards/{go['id']}/cancel", headers=auth,
                     json={"reason": "wrong truck logged"})
    assert r.status_code == 200
    assert client.get(f"/api/gate-outwards/{go['id']}", headers=auth).json()["status"] == "cancelled"


def test_go_rejects_void_invoice_and_foreign_tenant(client: TestClient):
    auth = _signup(client, "go2@t.com")
    inv = _posted_invoice(client, auth)
    client.post("/api/invoices/bulk", headers=auth,
                json={"ids": [inv["id"]], "action": "void"})
    r = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv["id"],
        "gate_date": "2026-07-06",
        "lines": [{"product_id": inv["lines"][0]["product_id"], "qty": 1}],
    })
    assert r.status_code == 400
    assert "void" in r.json()["detail"].lower()

    auth_b = _signup(client, "go2b@t.com")
    inv_a = _posted_invoice(client, auth)
    r = client.post("/api/gate-outwards", headers=auth_b, json={
        "source_doc_type": "invoice", "source_doc_id": inv_a["id"],
        "gate_date": "2026-07-06",
        "lines": [{"product_id": inv_a["lines"][0]["product_id"], "qty": 1}],
    })
    assert r.status_code == 404


def test_go_multiple_partial_exits_allowed_for_same_invoice(client: TestClient):
    """Reconciliation-only, not enforcement — no qty cap, batched shipment is fine."""
    auth = _signup(client, "go3@t.com")
    inv = _posted_invoice(client, auth, lines=[{"description": "Widget", "qty": 10, "rate": 5}])
    pid = inv["lines"][0]["product_id"]
    for _ in range(2):
        r = client.post("/api/gate-outwards", headers=auth, json={
            "source_doc_type": "invoice", "source_doc_id": inv["id"],
            "gate_date": "2026-07-06",
            "lines": [{"product_id": pid, "qty": 10}],  # deliberately over — no cap
        })
        assert r.status_code == 201, r.text


def _stock_product(client, auth, qty=100, avg_cost=10):
    """Create a stock product with a known qty/avg_cost by inserting it
    directly (bypassing the product-creation API, which has no field for
    pre-setting stock_qty/avg_cost — those only move via consume_stock/
    receive_stock in normal use)."""
    from decimal import Decimal
    from sqlmodel import Session
    from models import Product
    import db as _db
    r = client.get("/api/auth/me", headers=auth)
    tenant_id = r.json()["tenant"]["id"]
    with Session(_db.engine) as s:
        p = Product(tenant_id=tenant_id, name="Scrap Widget", product_type="stock",
                    stock_qty=Decimal(str(qty)), avg_cost=Decimal(str(avg_cost)))
        s.add(p); s.commit(); s.refresh(p)
        return p.id


def test_go_scrap_draft_then_approve_posts_gl_and_relieves_stock(client: TestClient):
    auth = _signup(client, "go4@t.com")
    pid = _stock_product(client, auth, qty=100, avg_cost=Decimal("10") if False else 10)

    r = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 5, "unit_cost": 10, "unit_value": 2}],
    })
    assert r.status_code == 201, r.text
    go = r.json()
    assert go["status"] == "draft"

    # draft: no GL, no stock change yet
    from decimal import Decimal as Dec
    prod = client.get(f"/api/products/{pid}", headers=auth).json()
    assert Dec(str(prod["stock_qty"])) == Dec("100")

    auth2 = _second_admin(client, auth, email="approver4@t.com")
    r = client.patch(f"/api/gate-outwards/{go['id']}/approve", headers=auth2)
    assert r.status_code == 200, r.text
    go_after = client.get(f"/api/gate-outwards/{go['id']}", headers=auth).json()
    assert go_after["status"] == "approved"

    prod_after = client.get(f"/api/products/{pid}", headers=auth).json()
    assert Dec(str(prod_after["stock_qty"])) == Dec("95")


def test_go_scrap_self_approval_blocked(client: TestClient):
    auth = _signup(client, "go5@t.com")
    pid = _stock_product(client, auth)
    go = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 1, "unit_cost": 10}],
    }).json()
    r = client.patch(f"/api/gate-outwards/{go['id']}/approve", headers=auth)
    assert r.status_code == 400
    assert "self" in r.json()["detail"].lower() or "creator" in r.json()["detail"].lower()


def test_go_scrap_cancel_allowed_only_while_draft(client: TestClient):
    auth = _signup(client, "go6@t.com")
    pid = _stock_product(client, auth)
    go = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 1, "unit_cost": 10}],
    }).json()
    r = client.patch(f"/api/gate-outwards/{go['id']}/cancel", headers=auth,
                     json={"reason": "wrong product"})
    assert r.status_code == 200

    go2 = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 1, "unit_cost": 10}],
    }).json()
    auth2 = _second_admin(client, auth)
    client.patch(f"/api/gate-outwards/{go2['id']}/approve", headers=auth2)
    r = client.patch(f"/api/gate-outwards/{go2['id']}/cancel", headers=auth,
                     json={"reason": "too late"})
    assert r.status_code == 400


def _second_admin(client, auth, email="approver2@t.com"):
    client.post("/api/users", headers=auth, json={
        "email": email, "password": "password123", "full_name": "Approver", "role": "admin",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_go_scrap_gl_balanced_with_revenue_leg(client: TestClient):
    """value > 0 posts BOTH the revenue JV and the expense/inventory JV."""
    auth = _signup(client, "go7@t.com")
    pid = _stock_product(client, auth, qty=50, avg_cost=8)
    go = client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "scrap", "gate_date": "2026-07-06",
        "lines": [{"product_id": pid, "qty": 10, "unit_cost": 8, "unit_value": 3}],
    }).json()
    auth2 = _second_admin(client, auth)
    r = client.patch(f"/api/gate-outwards/{go['id']}/approve", headers=auth2)
    assert r.status_code == 200, r.text

    from decimal import Decimal

    def _find_account(node, code):
        if node.get("code") == code:
            return node
        for child in node.get("children") or []:
            found = _find_account(child, code)
            if found is not None:
                return found
        return None

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    def bal(code):
        for node in tb["tree"]:
            found = _find_account(node, code)
            if found is not None:
                return found
        return None

    cash = bal("1000")
    scrap_rev = bal("4902")
    scrap_exp = bal("5901")
    assert cash is not None and Decimal(str(cash["debit"])) == Decimal("30")   # 10 * unit_value(3)
    assert scrap_rev is not None and Decimal(str(scrap_rev["credit"])) == Decimal("30")
    assert scrap_exp is not None and Decimal(str(scrap_exp["debit"])) == Decimal("80")  # 10 * unit_cost(8)


def test_gate_outward_register_and_search(client: TestClient):
    auth = _signup(client, "rep1@t.com")
    inv = _posted_invoice(client, auth)
    client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv["id"],
        "gate_date": "2026-07-06", "vehicle_no": "LEB-8888", "challan_no": "CH-501",
        "lines": [{"product_id": inv["lines"][0]["product_id"], "qty": 3}],
    })
    rows = client.get("/api/store-reports/gate-outward-register", headers=auth).json()
    assert len(rows) == 1
    assert rows[0]["reference"] == inv["number"]

    rows = client.get("/api/store-reports/gate-outward-register?q=CH-501", headers=auth).json()
    assert len(rows) == 1
    rows = client.get("/api/store-reports/gate-outward-register?q=NOPE", headers=auth).json()
    assert rows == []


def test_dispatch_reconciliation_flags_missing_exit(client: TestClient):
    auth = _signup(client, "rep2@t.com")
    inv_with_exit = _posted_invoice(client, auth)
    inv_without_exit = _posted_invoice(client, auth)
    client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv_with_exit["id"],
        "gate_date": "2026-07-06",
        "lines": [{"product_id": inv_with_exit["lines"][0]["product_id"], "qty": 3}],
    })
    rows = client.get("/api/store-reports/dispatch-reconciliation", headers=auth).json()
    by_number = {r["doc_number"]: r for r in rows}
    assert by_number[inv_with_exit["number"]]["has_gate_exit"] is True
    assert by_number[inv_without_exit["number"]]["has_gate_exit"] is False


def test_store_reports_honor_my_data_only(client: TestClient):
    auth = _signup(client, "rep3@t.com")
    inv = _posted_invoice(client, auth)
    client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv["id"],
        "gate_date": "2026-07-06",
        "lines": [{"product_id": inv["lines"][0]["product_id"], "qty": 3}],
    })
    # second user, restricted to own data on store.gate_outward
    client.post("/api/users", headers=auth, json={
        "email": "storeonly@t.com", "password": "password123",
        "full_name": "Store User", "role": "accountant",
    })
    r = client.post("/api/auth/login", data={"username": "storeonly@t.com", "password": "password123"})
    store_user = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # apply_own_filter only engages when the user-rights module is on
    client.patch("/api/settings", headers=auth, json={"user_rights_enabled": "true"})
    users = client.get("/api/users", headers=auth).json()["items"]
    uid = next(u["id"] for u in users if u["email"] == "storeonly@t.com")
    r = client.patch(f"/api/permissions/users/{uid}/my-data-only", headers=auth,
                     params={"enabled": "true"})
    assert r.status_code == 200, r.text

    # owner sees the entry; restricted user sees none (they recorded nothing) —
    # both on the list endpoint (already filtered) and the register (parity).
    assert len(client.get("/api/store-reports/gate-outward-register", headers=auth).json()) == 1
    assert client.get("/api/gate-outwards", headers=store_user).json() == []
    assert client.get("/api/store-reports/gate-outward-register", headers=store_user).json() == []

    # dispatch reconciliation: owner sees the exit, restricted user does not.
    owner_rows = client.get("/api/store-reports/dispatch-reconciliation", headers=auth).json()
    owner_row = {r["doc_number"]: r for r in owner_rows}[inv["number"]]
    assert owner_row["has_gate_exit"] is True
    assert owner_row["go_number"] is not None

    restricted_rows = client.get("/api/store-reports/dispatch-reconciliation", headers=store_user).json()
    restricted_row = {r["doc_number"]: r for r in restricted_rows}[inv["number"]]
    assert restricted_row["has_gate_exit"] is False
    assert restricted_row["go_number"] is None
