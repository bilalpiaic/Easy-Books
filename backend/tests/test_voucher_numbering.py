"""Tests for typed voucher numbering (Task 1 of voucher-series feature).

Verifies:
- Manual JV posts default to the JV type with zero-padded width-6 numbers.
- Consecutive posts of the same type produce monotonically incrementing numbers.
- The ``voucher_number`` helper directly produces correctly typed, incrementing numbers.
"""
import re

import pytest
from sqlmodel import Session, SQLModel, create_engine

from models import Account, Tenant, Transaction, User
from services.vouchers import voucher_number


# ── Service-level fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def session() -> Session:
    """Isolated in-memory SQLite DB for direct service-level tests."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def world(session: Session):
    """Minimal tenant + user + two GL accounts for a balanced JV."""
    tenant = Tenant(name="VoucherCo")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    user = User(email="test@voucherco.test", hashed_password="x", tenant_id=tenant.id)
    session.add(user)
    session.commit()
    session.refresh(user)

    cash = Account(code="1000", name="Cash", type="Asset", tenant_id=tenant.id)
    rev = Account(code="4000", name="Revenue", type="Revenue", tenant_id=tenant.id)
    session.add(cash)
    session.add(rev)
    session.commit()
    session.refresh(cash)
    session.refresh(rev)

    return {"tenant": tenant, "user": user, "cash": cash, "rev": rev}


# ── API-level helpers ──────────────────────────────────────────────────────────


def _get_accounts(client, headers):
    """Return the two GL accounts used for balanced JVs (Cash=1000, Revenue=4000)."""
    r = client.get("/api/accounts", headers=headers)
    assert r.status_code == 200, r.text
    accounts = r.json()["items"]
    cash = next(a for a in accounts if a["code"] == "1000")
    sales = next(a for a in accounts if a["code"] == "4000")
    return cash, sales


def _post_jv(client, headers):
    """Post a balanced manual JV via the transactions API and return the response."""
    cash, sales = _get_accounts(client, headers)
    body = {
        "date": "2026-04-01",
        "description": "test jv",
        "entries": [
            {"account_id": cash["id"], "debit": 10, "credit": 0},
            {"account_id": sales["id"], "debit": 0, "credit": 10},
        ],
    }
    return client.post("/api/transactions", headers=headers, json=body)


# ── API-level tests ────────────────────────────────────────────────────────────


def test_manual_post_defaults_to_jv_typed_number(client, admin_headers):
    """A manual JV via the API should get a JV- prefixed, 6-digit number."""
    r = _post_jv(client, admin_headers)
    assert r.status_code in (200, 201), r.text
    num = r.json()["jv_number"]
    assert num.startswith("JV-"), f"Expected JV- prefix, got: {num!r}"
    seq_part = num.split("-")[1]
    assert len(seq_part) == 6, f"Expected width-6 sequence, got: {seq_part!r}"
    assert seq_part.isdigit(), f"Sequence part should be digits, got: {seq_part!r}"


def test_second_manual_post_increments_sequence(client, admin_headers):
    """Two manual JVs should get consecutive JV- numbers."""
    r1 = _post_jv(client, admin_headers)
    r2 = _post_jv(client, admin_headers)
    assert r1.status_code in (200, 201), r1.text
    assert r2.status_code in (200, 201), r2.text

    num1 = r1.json()["jv_number"]
    num2 = r2.json()["jv_number"]

    seq1 = int(num1.split("-")[1])
    seq2 = int(num2.split("-")[1])
    assert seq2 == seq1 + 1, f"Expected consecutive numbers, got {num1!r} and {num2!r}"


# ── Service-level tests ────────────────────────────────────────────────────────


def test_voucher_number_format_sl(world, session: Session):
    """voucher_number() returns SL-000001 for the SL type."""
    tenant_id = world["tenant"].id
    num = voucher_number(session, tenant_id, "SL")
    session.commit()
    assert num == "SL-000001", f"Unexpected number: {num!r}"


def test_voucher_number_increments_sl(world, session: Session):
    """Two calls for SL produce SL-000001 then SL-000002."""
    tenant_id = world["tenant"].id
    n1 = voucher_number(session, tenant_id, "SL")
    session.flush()
    n2 = voucher_number(session, tenant_id, "SL")
    session.commit()
    assert n1 == "SL-000001", f"Expected SL-000001, got {n1!r}"
    assert n2 == "SL-000002", f"Expected SL-000002, got {n2!r}"


def test_voucher_number_types_are_independent(world, session: Session):
    """SL and JV sequences are independent — each starts at 000001."""
    tenant_id = world["tenant"].id
    sl1 = voucher_number(session, tenant_id, "SL")
    jv1 = voucher_number(session, tenant_id, "JV")
    session.commit()
    assert sl1 == "SL-000001"
    assert jv1 == "JV-000001"


def test_voucher_number_unknown_type_falls_back_to_jv(world, session: Session):
    """An unrecognised type falls back to JV numbering."""
    tenant_id = world["tenant"].id
    num = voucher_number(session, tenant_id, "XX")
    session.commit()
    assert num.startswith("JV-"), f"Expected JV fallback, got: {num!r}"


def test_voucher_number_regex_format(world, session: Session):
    """All standard types produce numbers matching ^[A-Z]{2}-\\d{6}$."""
    from services.vouchers import VOUCHER_TYPES

    tenant_id = world["tenant"].id
    pattern = re.compile(r"^[A-Z]{2}-\d{6}$")
    for vtype in VOUCHER_TYPES:
        num = voucher_number(session, tenant_id, vtype)
        session.flush()
        assert pattern.match(num), f"Type {vtype!r} produced non-conformant number: {num!r}"
    session.commit()
