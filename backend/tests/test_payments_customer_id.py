"""Record-payment must accept a customer_id and resolve its canonical name."""


def test_payment_resolves_name_from_customer_id(client, admin_headers):
    h = admin_headers
    cust = client.post("/api/customers", headers=h, json={"name": "Bilal Traders"}).json()
    pay = client.post(
        "/api/payments-received", headers=h,
        json={"customer_id": cust["id"], "amount": 100, "method": "cash",
              "payment_date": "2026-06-04"},
    )
    assert pay.status_code == 201
    assert pay.json()["customer_name"] == "Bilal Traders"


def test_payment_rejects_foreign_customer_id(client, admin_headers):
    h = admin_headers
    pay = client.post(
        "/api/payments-received", headers=h,
        json={"customer_id": 999999, "amount": 50, "method": "cash",
              "payment_date": "2026-06-04"},
    )
    assert pay.status_code == 404


def test_payment_rejects_other_tenant_customer(client, admin_headers):
    """Customer belonging to a *different* tenant must resolve to 404 (not 200),
    proving that the WHERE clause is tenant-scoped, not merely an existence check."""
    import db as _db_module
    from sqlmodel import Session
    from models import Customer, Tenant

    # Insert a Customer row directly for a different tenant_id (9999 – no such
    # tenant in the test DB; tenant FK is not enforced on SQLite).
    other_tenant_id = 9999
    with Session(_db_module.engine) as s:
        alien_cust = Customer(tenant_id=other_tenant_id, name="Alien Co")
        s.add(alien_cust)
        s.commit()
        s.refresh(alien_cust)
        alien_id = alien_cust.id

    pay = client.post(
        "/api/payments-received", headers=admin_headers,
        json={"customer_id": alien_id, "amount": 75, "method": "cash",
              "payment_date": "2026-06-04"},
    )
    assert pay.status_code == 404


def test_bill_payment_resolves_name_from_vendor_id(client, admin_headers):
    h = admin_headers
    vend = client.post("/api/vendors", headers=h, json={"name": "Pak Supplies Ltd"}).json()
    pay = client.post(
        "/api/bill-payments", headers=h,
        json={"vendor_id": vend["id"], "amount": 200, "method": "bank_transfer",
              "payment_date": "2026-06-04"},
    )
    assert pay.status_code == 201
    assert pay.json()["vendor_name"] == "Pak Supplies Ltd"


def test_bill_payment_rejects_foreign_vendor_id(client, admin_headers):
    h = admin_headers
    pay = client.post(
        "/api/bill-payments", headers=h,
        json={"vendor_id": 999999, "amount": 80, "method": "cash",
              "payment_date": "2026-06-04"},
    )
    assert pay.status_code == 404
