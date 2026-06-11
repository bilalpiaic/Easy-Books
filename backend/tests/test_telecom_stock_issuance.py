"""#42 Telecom Stock & Issuance report — per-RSO aggregation + franchise FCA footer."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import User
from models_telecom import (
    FcaEvent, LoadTransfer, RsoAgent, RsoDailyCollection, RsoStockIssue,
)


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    app.state.engine = engine
    app.dependency_overrides[get_session] = _override
    c = TestClient(app)
    yield c, engine
    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _signup(c, email, model="telecom_franchise"):
    c.post("/api/auth/signup", json={
        "email": email, "password": "password123", "full_name": "U",
        "company_name": "Telco", "business_model": model,
    })
    tok = c.post("/api/auth/login", data={
        "username": email, "password": "password123",
    }).json()["access_token"]
    c.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def _tenant_id(engine, email):
    with Session(engine) as s:
        return s.exec(select(User).where(User.email == email)).first().tenant_id


def test_stock_issuance_aggregates_and_footer(client):
    c, engine = client
    auth = _signup(c, "tel@t.test")
    tid = _tenant_id(engine, "tel@t.test")
    with Session(engine) as s:
        r1 = RsoAgent(tenant_id=tid, name="Ahmed", territory="North")
        r2 = RsoAgent(tenant_id=tid, name="Bilal", territory="South")
        s.add(r1); s.add(r2); s.commit(); s.refresh(r1); s.refresh(r2)
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r1.id, issue_date="2026-03-10", stock_type="scratch_card", stock_ref_id=1, qty_issued=120, face_value=12000))
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r1.id, issue_date="2026-03-10", stock_type="sim_batch", stock_ref_id=2, qty_issued=50, face_value=5000))
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r1.id, issue_date="2026-03-10", stock_type="bundle", stock_ref_id=3, qty_issued=10, face_value=1200))
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r2.id, issue_date="2026-03-11", stock_type="scratch_card", stock_ref_id=4, qty_issued=95, face_value=9500))
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r2.id, issue_date="2026-03-11", stock_type="imsi", stock_ref_id=5, qty_issued=30, face_value=3000))
        s.add(LoadTransfer(tenant_id=tid, transfer_date="2026-03-10", from_type="msr", from_ref_id=1, to_type="rso", to_ref_id=r1.id, amount=8000))
        s.add(LoadTransfer(tenant_id=tid, transfer_date="2026-03-11", from_type="msr", from_ref_id=1, to_type="rso", to_ref_id=r2.id, amount=6200))
        s.add(RsoDailyCollection(tenant_id=tid, rso_id=r1.id, collection_date="2026-03-12", total_deposited=9800))
        s.add(RsoDailyCollection(tenant_id=tid, rso_id=r2.id, collection_date="2026-03-12", total_deposited=6200))
        s.add(FcaEvent(tenant_id=tid, event_date="2026-03-12", msisdn="0300", source_channel="rso_retail"))
        s.add(FcaEvent(tenant_id=tid, event_date="2026-03-12", msisdn="0301", source_channel="counter"))
        s.add(FcaEvent(tenant_id=tid, event_date="2026-03-13", msisdn="0302", source_channel="rso_retail"))
        s.commit()

    data = c.get("/api/telecom/reports/stock-issuance", headers=auth).json()
    rows = {r["name"]: r for r in data["items"]}
    a = rows["Ahmed"]
    assert Decimal(a["stock_issuance"]) == Decimal("12000")
    assert Decimal(a["load_issued"]) == Decimal("8000")
    assert Decimal(a["hlr_issued"]) == Decimal("5000")
    assert a["sim_issued_qty"] == 50
    assert Decimal(a["other_stock"]) == Decimal("1200")
    assert Decimal(a["bank_deposits"]) == Decimal("9800")
    assert Decimal(a["closing_hlr_load_dep"]) == Decimal("3200")
    assert a["fca_hits"] is None
    assert a["closing_sim_fca"] is None

    t = data["totals"]
    assert t["sim_issued_qty"] == 80
    assert t["fca_hits"] == 3
    assert t["closing_sim_fca"] == 77
    assert Decimal(t["hlr_issued"]) == Decimal("8000")
    assert Decimal(t["load_issued"]) == Decimal("14200")
    assert Decimal(t["bank_deposits"]) == Decimal("16000")
    assert Decimal(t["closing_hlr_load_dep"]) == Decimal("6200")


def test_stock_issuance_period_filter(client):
    c, engine = client
    auth = _signup(c, "per@t.test")
    tid = _tenant_id(engine, "per@t.test")
    with Session(engine) as s:
        r = RsoAgent(tenant_id=tid, name="Cee"); s.add(r); s.commit(); s.refresh(r)
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r.id, issue_date="2026-01-05", stock_type="scratch_card", stock_ref_id=1, qty_issued=10, face_value=1000))
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r.id, issue_date="2026-03-05", stock_type="scratch_card", stock_ref_id=2, qty_issued=20, face_value=2000))
        s.add(FcaEvent(tenant_id=tid, event_date="2026-01-09", msisdn="x", source_channel="counter"))
        s.add(FcaEvent(tenant_id=tid, event_date="2026-03-09", msisdn="y", source_channel="counter"))
        s.commit()
    data = c.get("/api/telecom/reports/stock-issuance?start=2026-03-01&end=2026-03-31", headers=auth).json()
    assert Decimal(data["items"][0]["stock_issuance"]) == Decimal("2000")
    assert data["totals"]["fca_hits"] == 1
    assert data["period"] == {"start": "2026-03-01", "end": "2026-03-31"}


def test_stock_issuance_tenant_isolation(client):
    c, engine = client
    auth_a = _signup(c, "a@t.test")
    _signup(c, "b@t.test")
    tid_b = _tenant_id(engine, "b@t.test")
    with Session(engine) as s:
        rb = RsoAgent(tenant_id=tid_b, name="OtherTenantRSO"); s.add(rb); s.commit(); s.refresh(rb)
        s.add(RsoStockIssue(tenant_id=tid_b, rso_id=rb.id, issue_date="2026-03-01", stock_type="scratch_card", stock_ref_id=1, qty_issued=5, face_value=500))
        s.add(FcaEvent(tenant_id=tid_b, event_date="2026-03-01", msisdn="z", source_channel="counter"))
        s.commit()
    data = c.get("/api/telecom/reports/stock-issuance", headers=auth_a).json()
    assert data["items"] == []
    assert data["totals"]["fca_hits"] == 0
