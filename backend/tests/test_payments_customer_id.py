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
