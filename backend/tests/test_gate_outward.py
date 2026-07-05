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
