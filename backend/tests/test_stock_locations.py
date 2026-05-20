"""V2.2 tests: stock locations, movements, lot tracking, custody report."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import InventoryLayer, StockLocation, StockMovement


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    app.state.engine = engine
    app.dependency_overrides[get_session] = _override
    client = TestClient(app)
    yield client, engine
    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _signup(client: TestClient, model: str, email: str) -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": model,
        },
    )
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_simple_tenant_gets_main_store_only(client):
    c, _ = client
    auth = _signup(c, "simple", "s@s.test")
    items = c.get("/api/stock-locations", headers=auth).json()["items"]
    codes = [i["code"] for i in items]
    assert codes == ["MAIN"]
    assert items[0]["type"] == "own"


def test_manufacturing_tenant_seeds_main_godown_wip(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "m@m.test")
    items = c.get("/api/stock-locations", headers=auth).json()["items"]
    codes = sorted(i["code"] for i in items)
    types_by_code = {i["code"]: i["type"] for i in items}
    assert codes == ["GODOWN", "MAIN", "WIP"]
    assert types_by_code["MAIN"] == "own"
    assert types_by_code["GODOWN"] == "customer_custodial"
    assert types_by_code["WIP"] == "wip"


def test_create_extra_raw_material_store(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "rm@rm.test")
    r = c.post(
        "/api/stock-locations", headers=auth,
        json={"code": "RM-2", "name": "Raw Materials Store 2", "type": "own"},
    )
    assert r.status_code == 201, r.text
    # Duplicate code → 400
    r2 = c.post(
        "/api/stock-locations", headers=auth,
        json={"code": "RM-2", "name": "dupe", "type": "own"},
    )
    assert r2.status_code == 400


def test_invalid_location_type_rejected(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "bad@bad.test")
    r = c.post(
        "/api/stock-locations", headers=auth,
        json={"code": "X", "name": "X", "type": "unicorn"},
    )
    assert r.status_code == 400


def test_bill_records_movement_with_lot_and_location(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "mov@mov.test")
    # Make a stock product
    prod = c.post(
        "/api/products", headers=auth,
        json={
            "code": "RAW-A", "name": "Raw A", "unit": "kg",
            "product_type": "stock", "default_rate": 0,
        },
    ).json()
    vendor = c.post("/api/vendors", headers=auth, json={"name": "Acme Supplies"}).json()
    bill = c.post(
        "/api/bills", headers=auth,
        json={
            "vendor_id": vendor["id"], "bill_date": "2026-05-02",
            "due_date": "2026-05-31", "gst_rate": 0,
            "lines": [{"product_id": prod["id"], "description": "buy", "qty": 50, "rate": 4}],
        },
    ).json()
    # Layer should be at MAIN and a movement recorded
    with Session(engine) as s:
        layer = s.exec(select(InventoryLayer)).first()
        assert layer is not None
        assert layer.location_id is not None  # auto-attached to MAIN

        mv = s.exec(select(StockMovement)).first()
        assert mv is not None
        assert mv.direction == "RECEIPT"
        assert Decimal(str(mv.qty)) == Decimal("50")
        assert mv.posted_to_gl is True


def test_invoice_records_shipment_movement(client):
    c, engine = client
    auth = _signup(c, "trader", "sh@sh.test")
    prod = c.post(
        "/api/products", headers=auth,
        json={
            "code": "P1", "name": "P1", "unit": "ea",
            "product_type": "stock", "default_rate": 100,
        },
    ).json()
    vendor = c.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    # Purchase
    c.post(
        "/api/bills", headers=auth,
        json={
            "vendor_id": vendor["id"], "bill_date": "2026-05-01",
            "due_date": "2026-05-31", "gst_rate": 0,
            "lines": [{"product_id": prod["id"], "description": "buy", "qty": 10, "rate": 5}],
        },
    )
    # Sale
    cust = c.post("/api/customers", headers=auth, json={"name": "C"}).json()
    c.post(
        "/api/invoices", headers=auth,
        json={
            "customer_id": cust["id"], "issue_date": "2026-05-02",
            "due_date": "2026-05-31", "gst_rate": 0,
            "lines": [{"product_id": prod["id"], "description": "sell", "qty": 3, "rate": 100}],
        },
    )
    with Session(engine) as s:
        mvs = s.exec(select(StockMovement).order_by(StockMovement.id)).all()
        directions = [m.direction for m in mvs]
        assert "RECEIPT" in directions
        assert "SHIPMENT" in directions


def test_stock_at_location_endpoint(client):
    c, _ = client
    auth = _signup(c, "trader", "at@at.test")
    prod = c.post(
        "/api/products", headers=auth,
        json={
            "code": "P1", "name": "P1", "unit": "ea",
            "product_type": "stock", "default_rate": 0,
        },
    ).json()
    vendor = c.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    c.post(
        "/api/bills", headers=auth,
        json={
            "vendor_id": vendor["id"], "bill_date": "2026-05-01",
            "due_date": "2026-05-31", "gst_rate": 0,
            "lines": [{"product_id": prod["id"], "description": "buy", "qty": 20, "rate": 3}],
        },
    )
    locs = c.get("/api/stock-locations", headers=auth).json()["items"]
    main = next(l for l in locs if l["code"] == "MAIN")
    r = c.get(f"/api/stock-locations/{main['id']}/stock", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_lines"] == 1
    assert Decimal(str(body["items"][0]["qty"])) == Decimal("20")


def test_movements_filterable_by_direction(client):
    c, _ = client
    auth = _signup(c, "trader", "f@f.test")
    prod = c.post(
        "/api/products", headers=auth,
        json={
            "code": "P", "name": "P", "unit": "ea",
            "product_type": "stock", "default_rate": 0,
        },
    ).json()
    vendor = c.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    c.post(
        "/api/bills", headers=auth,
        json={
            "vendor_id": vendor["id"], "bill_date": "2026-05-01",
            "due_date": "2026-05-31", "gst_rate": 0,
            "lines": [{"product_id": prod["id"], "description": "buy", "qty": 5, "rate": 1}],
        },
    )
    r = c.get("/api/stock-locations/movements?direction=RECEIPT", headers=auth)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(m["direction"] == "RECEIPT" for m in items)


def test_custody_report_empty_for_simple_tenant(client):
    c, _ = client
    auth = _signup(c, "simple", "noc@noc.test")
    r = c.get("/api/stock-locations/custody", headers=auth)
    assert r.status_code == 200
    assert r.json() == []
