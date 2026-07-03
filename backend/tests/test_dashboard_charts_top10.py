"""Top Customers on the dashboard charts payload returns up to 10 rows (#131)."""
from decimal import Decimal

from sqlmodel import Session

import db as _db_module
from models import Customer, Invoice


def test_top_customers_returns_up_to_ten(client, admin_headers):
    h = admin_headers
    first = client.post("/api/customers", headers=h, json={"name": "Cust 0"}).json()
    with Session(_db_module.engine) as s:
        tid = s.get(Customer, first["id"]).tenant_id
        customers = [s.get(Customer, first["id"])]
        for i in range(1, 12):
            c = Customer(tenant_id=tid, name=f"Cust {i}")
            s.add(c)
            s.commit()
            s.refresh(c)
            customers.append(c)
        for i, c in enumerate(customers):
            s.add(Invoice(
                tenant_id=tid, number=f"INV-{i:03d}", customer_id=c.id,
                issue_date="2026-05-01", due_date="2026-05-31",
                subtotal=Decimal(100 + i), gst_amount=Decimal(0),
                total=Decimal(100 + i), status="posted",
            ))
        s.commit()

    charts = client.get("/api/reports/dashboard/charts", headers=h).json()
    tc = charts["top_customers"]
    assert len(tc) == 10                       # 12 customers exist, capped at 10
    totals = [float(row["total"]) for row in tc]
    assert totals == sorted(totals, reverse=True)   # ranking preserved
