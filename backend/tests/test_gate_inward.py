"""#137 Phase 2 — Gate Inward chain: GI → billing gate → reports."""
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


def test_gate_models_and_permission_registered(client: TestClient):
    from models import GateInward, GateInwardLine  # importable = tables exist
    from services.permissions import PERMISSION_RESOURCES
    assert "purchase.gate" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["purchase.gate"]["category"] == "Purchasing"


def test_gi_coverage_pure_math(client: TestClient):
    """Coverage helper sums non-cancelled GI lines per PO line."""
    from decimal import Decimal
    from sqlmodel import Session
    from models import (GateInward, GateInwardLine, PurchaseOrder,
                        PurchaseOrderLine, Tenant, User)
    from services.gate import gi_coverage, po_fully_covered
    import db as _db
    with Session(_db.engine) as s:
        t = Tenant(name="CovCo"); s.add(t); s.commit(); s.refresh(t)
        u = User(email="cov@t.test", hashed_password="x", full_name="U",
                 tenant_id=t.id, role="owner")
        s.add(u); s.commit(); s.refresh(u)
        po = PurchaseOrder(tenant_id=t.id, number="PO-X", order_date="2026-07-05",
                           status="approved")
        s.add(po); s.commit(); s.refresh(po)
        l1 = PurchaseOrderLine(po_id=po.id, description="A", qty=Decimal("10"), rate=Decimal("2"), amount=Decimal("20"))
        l2 = PurchaseOrderLine(po_id=po.id, description="B", qty=Decimal("5"), rate=Decimal("3"), amount=Decimal("15"))
        s.add(l1); s.add(l2); s.commit(); s.refresh(l1); s.refresh(l2)

        gi1 = GateInward(tenant_id=t.id, number="GI-1", po_id=po.id,
                         gate_date="2026-07-05", created_by_id=u.id)
        s.add(gi1); s.commit(); s.refresh(gi1)
        s.add(GateInwardLine(gate_inward_id=gi1.id, po_line_id=l1.id, qty_received=Decimal("4")))
        gi2 = GateInward(tenant_id=t.id, number="GI-2", po_id=po.id,
                         gate_date="2026-07-05", created_by_id=u.id, status="cancelled")
        s.add(gi2); s.commit(); s.refresh(gi2)
        s.add(GateInwardLine(gate_inward_id=gi2.id, po_line_id=l1.id, qty_received=Decimal("99")))
        s.commit()

        cov = gi_coverage(s, t.id, po.id)
        assert cov == {l1.id: Decimal("4")}          # cancelled GI excluded
        assert po_fully_covered(s, t.id, po.id) is False

        gi3 = GateInward(tenant_id=t.id, number="GI-3", po_id=po.id,
                         gate_date="2026-07-05", created_by_id=u.id)
        s.add(gi3); s.commit(); s.refresh(gi3)
        s.add(GateInwardLine(gate_inward_id=gi3.id, po_line_id=l1.id, qty_received=Decimal("6")))
        s.add(GateInwardLine(gate_inward_id=gi3.id, po_line_id=l2.id, qty_received=Decimal("5")))
        s.commit()
        assert po_fully_covered(s, t.id, po.id) is True
