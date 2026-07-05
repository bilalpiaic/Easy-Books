"""#137 Phase 2b — Gate Outward: invoice/debit-note memo exits + scrap draft→approve."""
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
