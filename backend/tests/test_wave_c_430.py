"""#430 Wave C — invite-only signup, healthcare kill switch, ops provision, mill import."""
from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from models import Account, Customer, Invoice, InvoiceLine, JournalEntry, Tenant, Transaction, User
from services.saas import apply_plan_defaults


def _signup(client, email: str, *, company: str = "Co"):
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": company,
            "business_model": "simple",
        },
    )
    assert r.status_code == 200, r.text
    tid = r.json()["tenant_id"]
    tok = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert tok.status_code == 200, tok.text
    client.cookies.clear()
    return tid, {"Authorization": f"Bearer {tok.json()['access_token']}"}


def test_signup_still_open_in_dev(client):
    r = client.get("/api/auth/oauth/providers")
    assert r.status_code == 200
    assert r.json()["signup"] is True
    tid, _ = _signup(client, "open-signup@co.test")
    assert tid


def test_signup_403_when_disabled(client, monkeypatch):
    monkeypatch.setenv("SIGNUP_ENABLED", "false")
    monkeypatch.delenv("SIGNUP_ALLOWLIST", raising=False)
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "blocked@co.test",
            "password": "password123",
            "full_name": "Nope",
            "company_name": "Nope Co",
        },
    )
    assert r.status_code == 403, r.text
    assert "invite-only" in r.json()["detail"].lower()
    assert client.get("/api/auth/oauth/providers").json()["signup"] is False


def test_signup_allowlist_bypasses_gate(client, monkeypatch):
    monkeypatch.setenv("SIGNUP_ENABLED", "false")
    monkeypatch.setenv("SIGNUP_ALLOWLIST", "pilot@mill.test")
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "pilot@mill.test",
            "password": "password123",
            "full_name": "Pilot",
            "company_name": "Pilot Mill",
        },
    )
    assert r.status_code == 200, r.text


def test_production_signup_defaults_off(monkeypatch):
    monkeypatch.delenv("SIGNUP_ENABLED", raising=False)
    monkeypatch.delenv("REQUIRE_OPS_TOTP", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    from services import security_policy as sp
    assert sp.signup_enabled() is False
    assert sp.require_ops_totp() is True
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert sp.signup_enabled() is True


def test_healthcare_patients_404_when_disabled(client, monkeypatch):
    monkeypatch.setenv("DISABLED_MODULES", "healthcare")
    r = client.get(
        "/api/healthcare/patients",
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "Not Found"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    v1 = client.get("/api/v1/healthcare/patients")
    assert v1.status_code == 404


def test_healthcare_install_refused_when_disabled(client, monkeypatch):
    monkeypatch.setenv("DISABLED_MODULES", "healthcare")
    _tid, auth = _signup(client, "hc-kill@co.test")
    r = client.post("/api/modules/healthcare/install", headers=auth)
    assert r.status_code == 403, r.text
    assert "disabled" in r.json()["detail"].lower()


def test_ops_provision_invite_no_email(client, monkeypatch):
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-c@easy-books.test")
    _ops_tid, ops = _signup(client, "ops-c@easy-books.test", company="Ops")
    r = client.post(
        "/api/ops/tenants",
        headers=ops,
        json={
            "company_name": "Mill Pilot",
            "owner_email": "mill.owner@pilot.test",
            "owner_name": "Mill Owner",
            "plan": "starter",
            "no_email": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["plan"] == "starter"
    assert body["invite"]["attached"] is False
    assert body["invite"]["invite_token"]
    assert body["subscription_status"] == "complimentary"

    # Public signup still independent; invite can be inspected.
    token = body["invite"]["invite_token"]
    inspect = client.get(f"/api/auth/invite/{token}")
    assert inspect.status_code == 200, inspect.text
    assert inspect.json()["email"] == "mill.owner@pilot.test"


def test_ops_provision_requires_smtp_unless_no_email(client, monkeypatch):
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-smtp@easy-books.test")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    _ops_tid, ops = _signup(client, "ops-smtp@easy-books.test", company="Ops")
    r = client.post(
        "/api/ops/tenants",
        headers=ops,
        json={
            "company_name": "Needs Mail",
            "owner_email": "needs@mail.test",
            "no_email": False,
        },
    )
    assert r.status_code == 400, r.text
    assert "SMTP" in r.json()["detail"]


def test_ops_comp_plan_is_audited(client, monkeypatch):
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-plan@easy-books.test")
    mill_id, mill_auth = _signup(client, "comp-mill@co.test", company="Comp Mill")
    _ops_tid, ops = _signup(client, "ops-plan@easy-books.test", company="Ops")
    r = client.put(
        f"/api/ops/tenants/{mill_id}/plan",
        headers=ops,
        json={"plan": "pro", "reason": "pilot complimentary"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == "pro"
    usage = client.get("/api/billing/usage", headers=mill_auth).json()
    assert usage["plan"] == "pro"
    audit = client.get("/api/audit-log?entity_type=ops.plan&limit=20", headers=mill_auth)
    assert audit.status_code == 200, audit.text
    blob = audit.text
    assert "ops.plan" in blob
    assert "pilot complimentary" in blob


def test_ops_totp_required_when_flag_on(client, monkeypatch):
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-2fa@easy-books.test")
    monkeypatch.setenv("REQUIRE_OPS_TOTP", "true")
    _tid, ops = _signup(client, "ops-2fa@easy-books.test", company="Ops")
    r = client.get("/api/ops/tenants", headers=ops)
    assert r.status_code == 403
    assert "2FA" in r.json()["detail"] or "authenticator" in r.json()["detail"]


def test_suspended_tenant_cannot_post_invoice(client, admin_headers):
    cust = client.post("/api/customers", headers=admin_headers, json={"name": "Susp Cust"})
    assert cust.status_code in (200, 201), cust.text
    prod = client.post(
        "/api/products",
        headers=admin_headers,
        json={"name": "Svc", "product_type": "service", "sale_price": 10},
    )
    assert prod.status_code in (200, 201), prod.text
    import db as dbmod
    with Session(dbmod.engine) as s:
        t = s.exec(select(Tenant)).first()
        assert t is not None
        t.is_suspended = True
        s.add(t)
        s.commit()
    r = client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_id": cust.json()["id"],
            "issue_date": "2026-04-01",
            "gst_rate": 0,
            "lines": [{
                "product_id": prod.json()["id"],
                "description": "svc",
                "qty": 1,
                "rate": 10,
            }],
        },
    )
    assert r.status_code == 402, r.text
    assert r.json().get("code") == "tenant_suspended"


def _build_mill_sqlite(path: Path) -> dict:
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        tenant = Tenant(name="Desktop Mill")
        apply_plan_defaults(tenant, "starter")
        s.add(tenant)
        s.flush()
        mill_user = User(
            email="old-mill-user@desktop.test",
            hashed_password="not-used",
            full_name="Old Mill User",
            tenant_id=tenant.id,
            role="owner",
        )
        s.add(mill_user)
        s.flush()
        ar = Account(
            tenant_id=tenant.id, code="1100", name="AR", type="Asset",
        )
        rev = Account(
            tenant_id=tenant.id, code="4100", name="Revenue", type="Revenue",
        )
        s.add(ar)
        s.add(rev)
        s.flush()
        cust = Customer(tenant_id=tenant.id, name="Mill Customer")
        s.add(cust)
        s.flush()
        txn = Transaction(
            tenant_id=tenant.id,
            date="2026-03-01",
            description="SL mill",
            jv_number="SL-2026-0001",
            voucher_type="SL",
            created_by_id=mill_user.id,
        )
        s.add(txn)
        s.flush()
        s.add(JournalEntry(
            tenant_id=tenant.id, transaction_id=txn.id, account_id=ar.id,
            debit=Decimal("250.00"), credit=Decimal("0"),
        ))
        s.add(JournalEntry(
            tenant_id=tenant.id, transaction_id=txn.id, account_id=rev.id,
            debit=Decimal("0"), credit=Decimal("250.00"),
        ))
        inv = Invoice(
            tenant_id=tenant.id,
            number="INV-MILL-1",
            customer_id=cust.id,
            customer_name=cust.name,
            issue_date="2026-03-01",
            due_date="2026-03-31",
            subtotal=Decimal("250"),
            gst_rate=Decimal("0"),
            gst_amount=Decimal("0"),
            total=Decimal("250"),
            status="open",
            ar_account_id=ar.id,
            revenue_account_id=rev.id,
            transaction_id=txn.id,
            created_by_id=mill_user.id,
        )
        s.add(inv)
        s.flush()
        s.add(InvoiceLine(
            invoice_id=inv.id,
            description="Yarn",
            qty=Decimal("1"),
            rate=Decimal("250"),
            amount=Decimal("250"),
        ))
        s.commit()
        return {"tenant_id": tenant.id, "invoice_id": inv.id, "user_email": mill_user.email}


def test_mill_import_dry_run_matches_and_apply_remaps(client, monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-imp@easy-books.test")
    mill_sqlite = tmp_path / "database.db"
    src = _build_mill_sqlite(mill_sqlite)
    dest_id, dest_auth = _signup(client, "import-dest@co.test", company="SaaS Dest")
    _ops_tid, ops = _signup(client, "ops-imp@easy-books.test", company="Ops")
    cust = client.post("/api/customers", headers=dest_auth, json={"name": "Existing Dest"}).json()
    prod = client.post(
        "/api/products",
        headers=dest_auth,
        json={"name": "Dest Svc", "product_type": "service", "sale_price": 40},
    ).json()
    existing = client.post(
        "/api/invoices",
        headers=dest_auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-04-01",
            "gst_rate": 0,
            "lines": [{"product_id": prod["id"], "description": "existing", "qty": 1, "rate": 40}],
        },
    )
    assert existing.status_code == 201, existing.text
    existing_id = existing.json()["id"]
    existing_number = existing.json()["number"]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(mill_sqlite, "database.db")
    buf.seek(0)

    dry = client.post(
        f"/api/ops/tenants/{dest_id}/import?dry_run=true",
        headers=ops,
        files={"file": ("backup.zip", buf.getvalue(), "application/zip")},
    )
    assert dry.status_code == 200, dry.text
    body = dry.json()
    assert body["dry_run"] is True
    assert body["invoice_count_match"] is True
    assert body["trial_balance_match"] is True
    assert body["source"]["invoice_count"] == 1
    assert body["users_skipped"] == 1
    listed = client.get("/api/invoices", headers=dest_auth).json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == existing_id

    buf.seek(0)
    apply = client.post(
        f"/api/ops/tenants/{dest_id}/import?dry_run=false",
        headers=ops,
        files={"file": ("backup.zip", buf.getvalue(), "application/zip")},
    )
    assert apply.status_code == 200, apply.text
    applied = apply.json()
    assert applied["dry_run"] is False
    assert applied["invoice_count_match"] is True
    assert applied["trial_balance_match"] is True

    listed = client.get("/api/invoices", headers=dest_auth).json()
    assert listed["total"] == 2
    by_number = {row["number"]: row for row in listed["items"]}
    assert existing_number in by_number
    assert by_number[existing_number]["id"] == existing_id
    mill_inv = by_number["INV-MILL-1"]
    assert mill_inv["id"] != existing_id
    assert len({row["id"] for row in listed["items"]}) == 2

    import db as dbmod
    with Session(dbmod.engine) as s:
        leaked = s.exec(
            select(User).where(User.email == "old-mill-user@desktop.test")
        ).first()
        assert leaked is None
        dest_user_emails = [
            u.email for u in s.exec(select(User).where(User.tenant_id == dest_id)).all()
        ]
        assert "import-dest@co.test" in dest_user_emails
        assert "old-mill-user@desktop.test" not in dest_user_emails


def test_import_healthcare_rows_rejected_when_disabled(
    client, monkeypatch, tmp_path,
):
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-hc-imp@easy-books.test")
    monkeypatch.setenv("DISABLED_MODULES", "healthcare")
    mill_sqlite = tmp_path / "database.db"
    engine = create_engine(f"sqlite:///{mill_sqlite}")
    SQLModel.metadata.create_all(engine)
    from models_healthcare import HcPatient
    with Session(engine) as s:
        tenant = Tenant(name="Hospital Desktop")
        s.add(tenant)
        s.flush()
        s.add(HcPatient(
            tenant_id=tenant.id,
            mr_number="MR-20260001",
            name="Pat",
        ))
        s.commit()
        src_tid = tenant.id
    dest_id, _dest = _signup(client, "hc-imp-dest@co.test", company="Dest")
    _ops_tid, ops = _signup(client, "ops-hc-imp@easy-books.test", company="Ops")
    r = client.post(
        f"/api/ops/tenants/{dest_id}/import?dry_run=true&source_tenant_id={src_tid}",
        headers=ops,
        files={"file": ("database.db", mill_sqlite.read_bytes(), "application/octet-stream")},
    )
    assert r.status_code == 400, r.text
    assert "healthcare" in r.json()["detail"].lower()
