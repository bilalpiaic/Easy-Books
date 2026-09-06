"""GL-correctness tests for editing a posted stock invoice.

These cover the COGS journal-voucher reversal + re-post on edit (so accounts
5010 Cost of Goods Sold and 1200 Inventory end correct), the global
trial-balance invariant after an edit, multi-edit stock consistency, and the
locked-period / already-reversed edit guards.
"""
from decimal import Decimal

from sqlmodel import Session, select

import db as _db_module
from models import Account, Invoice, JournalEntry, Product, Tenant, Transaction


def _tenant_id():
    with Session(_db_module.engine) as s:
        return s.exec(select(Tenant.id).order_by(Tenant.id)).first()


def _net_by_code(code: str) -> float:
    """Σ(debit - credit) across all JEs posted to the account with `code`
    for the (single) test tenant."""
    tid = _tenant_id()
    with Session(_db_module.engine) as s:
        acc = s.exec(
            select(Account).where(Account.tenant_id == tid, Account.code == code)
        ).first()
        if not acc:
            return 0.0
        rows = s.exec(
            select(JournalEntry).where(
                JournalEntry.tenant_id == tid,
                JournalEntry.account_id == acc.id,
            )
        ).all()
        return float(sum((Decimal(str(r.debit)) - Decimal(str(r.credit)) for r in rows), Decimal("0")))


def _trial_balance():
    """Returns (total_debit, total_credit) across ALL journal entries."""
    tid = _tenant_id()
    with Session(_db_module.engine) as s:
        rows = s.exec(select(JournalEntry).where(JournalEntry.tenant_id == tid)).all()
        td = sum((Decimal(str(r.debit)) for r in rows), Decimal("0"))
        tc = sum((Decimal(str(r.credit)) for r in rows), Decimal("0"))
        return float(td), float(tc)


def _onhand(pid):
    with Session(_db_module.engine) as s:
        return float(s.get(Product, pid).stock_qty)


def _setup_stocked(client, h, receive_qty=100, cost=5):
    """Customer + a stock product that has been received at `cost` so avg_cost
    is nonzero and consume_stock posts a real COGS."""
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    client.post("/api/bills", headers=h, json={
        "vendor_name": "Sup", "issue_date": "2026-02-01", "bill_date": "2026-02-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt",
                   "qty": receive_qty, "rate": cost}],
    })
    return c, p


def _post_invoice(client, h, c, p, qty, rate=20, date="2026-03-01"):
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"], "issue_date": date, "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    return inv


def test_edit_corrects_cogs_gl(client, admin_headers):
    """Sell qty=10 @ avg_cost=5 (COGS 50), then edit to qty=4 (COGS 20).
    After the edit, the NET GL on 5010 must be a 20 debit and on 1200 a 20
    credit — i.e. original COGS JV + its reversal + the new COGS JV net out
    to the edited 4 * 5 = 20."""
    h = admin_headers
    c, p = _setup_stocked(client, h, receive_qty=100, cost=5)
    inv = _post_invoice(client, h, c, p, qty=10)
    # Inventory 1200 starts at +500 (bill receipt 100*5 debit).
    # original COGS = 10 * 5 = 50 debit on 5010, 50 credit on 1200 → 1200 net 450
    assert _net_by_code("5010") == 50.0
    assert _net_by_code("1200") == 450.0

    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 20}],
    })
    assert r.status_code == 200, r.text
    # COGS 5010: 50 (orig) - 50 (reversal) + 20 (new) = 20 net debit
    assert _net_by_code("5010") == 20.0
    # Inventory 1200: 500 (receipt) - 50 (orig COGS) + 50 (reversal) - 20 (new COGS) = 480
    assert _net_by_code("1200") == 480.0


def test_edit_balances_overall(client, admin_headers):
    """Global trial balance must stay balanced after an edit that reverses +
    re-posts both the AR/Revenue JV and the COGS JV."""
    h = admin_headers
    c, p = _setup_stocked(client, h, receive_qty=100, cost=5)
    inv = _post_invoice(client, h, c, p, qty=10)
    client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 20}],
    })
    td, tc = _trial_balance()
    assert td == tc, f"trial balance broken: debits={td} credits={tc}"


def test_multi_edit_stock_consistent(client, admin_headers):
    """Receive 100; sell 10 (on-hand 90); edit to 4 (96); edit to 7 (93).
    The second edit must not double-restore the first edit's movements."""
    h = admin_headers
    c, p = _setup_stocked(client, h, receive_qty=100, cost=5)
    inv = _post_invoice(client, h, c, p, qty=10)
    assert _onhand(p["id"]) == 90
    client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 20}],
    })
    assert _onhand(p["id"]) == 96
    client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 7, "rate": 20}],
    })
    assert _onhand(p["id"]) == 93


def test_edit_blocked_locked_period(client, admin_headers):
    """Locking the period covering the invoice date blocks the edit (400)."""
    h = admin_headers
    client.patch("/api/settings", headers=h, json={"period_close_require_checklist": "false"})
    c, p = _setup_stocked(client, h, receive_qty=100, cost=5)
    inv = _post_invoice(client, h, c, p, qty=10, date="2026-03-15")
    period = client.post("/api/periods", headers=h, json={
        "name": "Mar-2026", "period_start": "2026-03-01", "period_end": "2026-03-31",
    }).json()
    lr = client.patch(f"/api/periods/{period['id']}/lock?is_locked=true", headers=h)
    assert lr.status_code == 200, lr.text
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-15", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 20}],
    })
    assert r.status_code == 400, r.text


def test_edit_blocked_already_reversed(client, admin_headers):
    """If the invoice's GL txn is already reversed, editing is blocked (400)."""
    h = admin_headers
    c, p = _setup_stocked(client, h, receive_qty=100, cost=5)
    inv = _post_invoice(client, h, c, p, qty=10)
    # Directly mark the linked AR/Revenue txn reversed to exercise the guard.
    tid = _tenant_id()
    with Session(_db_module.engine) as s:
        db_inv = s.get(Invoice, inv["id"])
        txn = s.get(Transaction, db_inv.transaction_id)
        txn.is_reversed = True
        s.add(txn)
        s.commit()
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 20}],
    })
    assert r.status_code == 400, r.text
    assert "reversed" in r.json()["detail"].lower()
