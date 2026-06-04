# Feature 5: Editing Posted Invoices/Bills — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow editing a POSTED (unpaid, open-period) invoice/bill by reversing the original GL **and stock**, then re-posting the corrected document — preserving the document number and a full audit chain.

**Architecture:** Replace the blanket draft-only gate with an eligibility check. Eligible = posted/sent/overdue AND no payment allocated (**block-if-paid**) AND date not in a locked period AND not already reversed. The existing update path already reverses GL (`invoices.py:441-462`); we add the missing **stock reversal** using `services.inventory.reverse_consumption` (sales) / `reverse_purchase` (purchases) before re-applying lines.

**Tech Stack:** FastAPI + SQLModel (backend), Next.js 16 / React 19 / TypeScript (frontend), pytest.

**Pre-existing-bug note:** the current draft-edit path re-consumes stock *without* restoring the original consumption. Drafts that were GL-posted+stock-consumed therefore double-relieve on edit. This plan fixes that gap (Task 2) since posted editing makes it material.

---

### Task 1: Eligibility guard for posted-invoice edit

**Files:**
- Modify: `backend/routers/invoices.py:381-392` (`update_invoice` gate)
- Create: `backend/routers/_edit_guards.py` (shared helper)
- Test: `backend/tests/test_edit_posted_invoice.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_edit_posted_invoice.py
"""Editing a posted invoice: allowed when unpaid+open, blocked otherwise."""
from sqlmodel import Session
import db as _db_module
from models import Invoice


def _post_invoice(client, h, customer_id, product_id, rate=100, qty=2, date="2026-03-01"):
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": customer_id, "issue_date": date,
        "lines": [{"product_id": product_id, "description": "x", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    return inv


def _setup(client, h):
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    return c, p


def test_edit_posted_unpaid_succeeds(client, admin_headers):
    h = admin_headers
    c, p = _setup(client, h)
    inv = _post_invoice(client, h, c["id"], p["id"], rate=100, qty=2)
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01",
        "lines": [{"product_id": p["id"], "description": "x", "qty": 3, "rate": 120}],
    })
    assert r.status_code == 200
    assert r.json()["total"] == 360            # 3 * 120
    assert r.json()["number"] == inv["number"]  # number preserved


def test_edit_blocked_when_paid(client, admin_headers):
    h = admin_headers
    c, p = _setup(client, h)
    inv = _post_invoice(client, h, c["id"], p["id"], rate=100, qty=2)
    client.post("/api/payments-received", headers=h, json={
        "customer_id": c["id"], "amount": 50, "method": "cash",
        "payment_date": "2026-03-02",
        "allocations": [{"invoice_id": inv["id"], "amount": 50}],
    })
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01",
        "lines": [{"product_id": p["id"], "description": "x", "qty": 3, "rate": 120}],
    })
    assert r.status_code == 400
    assert "payment" in r.json()["detail"].lower()
```

> Confirm the allocation payload shape against `payments.py` `PaymentReceivedCreate` (it has an `allocations` list of `AllocationLine`); adjust the keys if needed during execution.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_edit_posted_invoice.py -v`
Expected: FAIL — posted edit returns 403 (current gate).

- [ ] **Step 3: Create the shared eligibility helper**

```python
# backend/routers/_edit_guards.py
"""Shared eligibility checks for editing posted invoices/bills."""
from fastapi import HTTPException
from sqlmodel import Session, select

from models import PaymentAllocation, Transaction
from services.posting import _check_period_locked


def assert_doc_editable(session: Session, *, tenant_id: int, doc, kind: str) -> None:
    """Raise HTTPException if a posted invoice/bill may not be edited.

    kind: 'invoice' or 'bill'. Drafts are always editable (caller short-circuits).
    Rules: block if any payment allocated; block if date in a locked period;
    block if the GL txn is already reversed.
    """
    if doc.status == "draft":
        return

    alloc_filter = (
        PaymentAllocation.invoice_id == doc.id if kind == "invoice"
        else PaymentAllocation.bill_id == doc.id
    )
    allocated = session.exec(
        select(PaymentAllocation).where(
            PaymentAllocation.tenant_id == tenant_id, alloc_filter
        )
    ).first()
    if allocated:
        raise HTTPException(400, "Unallocate payments before editing this document.")

    # Locked period (raises HTTPException if locked)
    _check_period_locked(session, tenant_id, doc.issue_date)

    if doc.transaction_id:
        txn = session.get(Transaction, doc.transaction_id)
        if txn and txn.is_reversed:
            raise HTTPException(400, "This document was already reversed and cannot be edited.")
```

> Confirm `_check_period_locked` raises `HTTPException` (not a custom error); if it raises a domain error, wrap it. Check its body in `services/posting.py:84`.

- [ ] **Step 4: Relax the gate in `update_invoice`**

Replace the gate at `invoices.py:391-392`:

```python
    if inv.status != "draft":
        raise HTTPException(403, f"Cannot edit invoice with status '{inv.status}'. Only draft invoices can be edited.")
```

with:

```python
    from routers._edit_guards import assert_doc_editable
    assert_doc_editable(session, tenant_id=user.tenant_id, doc=inv, kind="invoice")
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_edit_posted_invoice.py -v`
Expected: `test_edit_blocked_when_paid` PASSES; `test_edit_posted_unpaid_succeeds` may still fail on stock double-count (fixed in Task 2) but should now return 200 — verify the status/total/number assertions pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/_edit_guards.py backend/routers/invoices.py backend/tests/test_edit_posted_invoice.py
git commit -m "feat(invoices): allow editing posted unpaid invoices (block-if-paid, locked-period, reversed)"
```

---

### Task 2: Restore stock before re-consuming on edit

**Files:**
- Modify: `backend/routers/invoices.py` (in `update_invoice`, before the line-delete loop ~464)
- Test: `backend/tests/test_edit_posted_invoice_stock.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_edit_posted_invoice_stock.py
"""Editing a posted invoice restores original stock then re-applies the new qty."""
from sqlmodel import Session
import db as _db_module
from models import Product


def _onhand(pid):
    with Session(_db_module.engine) as s:
        return float(s.get(Product, pid).stock_qty)


def test_edit_restores_then_reapplies_stock(client, admin_headers):
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    # receive 100 via a bill so there is stock to relieve
    client.post("/api/bills", headers=h, json={
        "vendor_name": "Sup", "issue_date": "2026-02-01",
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 100, "rate": 5}],
    })
    start = _onhand(p["id"])               # 100
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01",
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 10, "rate": 20}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    assert _onhand(p["id"]) == start - 10   # 90 after selling 10
    # edit: now sell 4 instead of 10 → on-hand should be 96, not double-counted
    client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01",
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 20}],
    })
    assert _onhand(p["id"]) == start - 4    # 96
```

> Confirm the bill create payload (`vendor_name` vs `customer_name`, line shape) against `routers/bills.py` `BillCreate`; adjust during execution.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_edit_posted_invoice_stock.py -v`
Expected: FAIL — on-hand is `start - 14` (10 original + 4 new), not `start - 4`.

- [ ] **Step 3: Reverse original stock before deleting lines**

In `update_invoice`, immediately BEFORE the "Delete existing lines" block (~line 464), add:

```python
    # Restore stock relieved by the original posting before re-applying lines.
    from models import StockMovement
    from services.inventory import reverse_consumption
    orig_moves = session.exec(
        select(StockMovement).where(
            StockMovement.tenant_id == user.tenant_id,
            StockMovement.source_doc_type == "invoice",
            StockMovement.source_doc_id == inv.id,
            StockMovement.direction.in_(("SHIPMENT", "DELIVERY", "ISSUE")),
        )
    ).all()
    restored: dict[int, list] = {}
    for m in orig_moves:
        restored.setdefault(m.product_id, [ZERO, ZERO])
        restored[m.product_id][0] += D(m.qty)
        restored[m.product_id][1] += D(m.total_cost)
    for pid, (qty, cogs) in restored.items():
        reverse_consumption(
            session, tenant_id=user.tenant_id,
            product_id=pid, qty=qty, cogs_total=cogs,
        )
```

> If invoice stock movements are not tagged with `source_doc_type='invoice'`/`source_doc_id=inv.id` at posting time, add that tagging in the create path's `consume_stock` call site, or look them up via `transaction_id`. Verify the tagging during execution by inspecting a posted invoice's `StockMovement` rows.

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_edit_posted_invoice_stock.py tests/test_edit_posted_invoice.py -v`
Expected: PASS (all).

- [ ] **Step 5: Run the full invoice + inventory suites**

Run: `cd backend && uv run pytest -k "invoice or inventory or stock" -v`
Expected: PASS (no regressions to draft editing or posting).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/invoices.py backend/tests/test_edit_posted_invoice_stock.py
git commit -m "fix(invoices): restore original stock before re-consuming on edit"
```

---

### Task 3: Mirror posted-edit support for bills

**Files:**
- Modify: `backend/routers/bills.py:327-...` (`update_bill` gate + stock restore)
- Test: `backend/tests/test_edit_posted_bill.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_edit_posted_bill.py
"""Editing a posted bill: allowed when unpaid+open; restores receipt stock."""
from sqlmodel import Session
import db as _db_module
from models import Product


def _onhand(pid):
    with Session(_db_module.engine) as s:
        return float(s.get(Product, pid).stock_qty)


def test_edit_posted_bill_adjusts_stock(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "Nut", "product_type": "stock"}).json()
    bill = client.post("/api/bills", headers=h, json={
        "vendor_name": "Sup", "issue_date": "2026-02-01",
        "lines": [{"product_id": p["id"], "description": "Nut", "qty": 50, "rate": 4}],
    }).json()
    client.patch(f"/api/bills/{bill['id']}/status?status=received", headers=h)
    assert _onhand(p["id"]) == 50
    client.put(f"/api/bills/{bill['id']}", headers=h, json={
        "vendor_name": "Sup", "issue_date": "2026-02-01",
        "lines": [{"product_id": p["id"], "description": "Nut", "qty": 30, "rate": 4}],
    })
    assert _onhand(p["id"]) == 30   # not 80
```

> Confirm bill status values (`received`/`posted`) and the status-patch route from `bills.py:504`; adjust the patch call accordingly.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_edit_posted_bill.py -v`
Expected: FAIL — posted bill edit blocked / stock double-counted.

- [ ] **Step 3: Apply the same two changes to `update_bill`**

In `bills.py` `update_bill`: replace the draft-only gate with
`assert_doc_editable(session, tenant_id=user.tenant_id, doc=bill, kind="bill")`,
and before re-applying lines reverse the original receipt stock using
`reverse_purchase(session, tenant_id=user.tenant_id, source_doc=bill.number)`
(bills receive stock via `record_purchase` keyed on `bill.number`; confirm the
`source_doc` key used at the bill posting call site).

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_edit_posted_bill.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full bill suite**

Run: `cd backend && uv run pytest -k "bill" -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/bills.py backend/tests/test_edit_posted_bill.py
git commit -m "feat(bills): allow editing posted unpaid bills with stock reversal"
```

---

### Task 4: Frontend — enable edit on posted docs with confirmation

**Files:**
- Modify: `frontend/src/app/(dashboard)/invoices/[id]/page.tsx`
- Modify: `frontend/src/app/(dashboard)/bills/[id]/page.tsx`

- [ ] **Step 1: Read Next.js 16 guidance**

Run: `ls frontend/node_modules/next/dist/docs/`; heed `frontend/AGENTS.md`.

- [ ] **Step 2: Enable the edit affordance for eligible posted docs**

Where the edit button is currently hidden/disabled for non-draft status, allow it for posted/sent/overdue. (The backend is the source of truth for eligibility; the UI just needs to permit the attempt.) Keep it disabled with a tooltip when the doc is clearly paid (the page already knows payment/allocation state) — message: *"Unallocate payments to edit."*

- [ ] **Step 3: Add a confirmation modal before saving a posted edit**

When saving a doc whose status is not draft, show a confirm dialog:
*"This will reverse the original ledger entry and post a correction, keeping the same document number. Continue?"* Proceed with the existing `PUT` on confirm. Surface backend 400 errors (paid / locked period / already reversed) inline.

- [ ] **Step 4: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 5: Manual smoke check**

Post an invoice → edit it → confirm modal → save → totals update, number unchanged, GL shows a reversal + a new correction JV, stock reconciles. Allocate a payment → edit is blocked with the guidance message.

- [ ] **Step 6: Commit**

```bash
git add "frontend/src/app/(dashboard)/invoices/[id]/page.tsx" "frontend/src/app/(dashboard)/bills/[id]/page.tsx"
git commit -m "feat(ui): edit posted invoices/bills with reversal confirmation"
```

---

## Self-Review Notes
- Spec Feature 5 fully covered: reverse-&-re-post (reuses existing GL reversal), block-if-paid (Task 1 guard + test), locked-period block (`_check_period_locked`), already-reversed block, stock reversal for both sales and purchases (Tasks 2-3), number preserved, audit chain via `is_reversed`/`reversed_by_id`, frontend confirmation (Task 4).
- Pre-existing stock double-count on draft edits is fixed as a side effect (Task 2).
- **Execution-time verifications flagged inline:** allocation payload shape (Task 1), `_check_period_locked` raise type (Task 1), invoice StockMovement tagging (Task 2), bill `record_purchase` source_doc key + status values (Task 3). Resolve each by reading the cited code before implementing.
- Edge cases from spec (multi-currency re-snapshot, `is_deferred` deferral re-post) are handled by the existing re-post path which already recomputes FX; deferred-revenue invoices route through the same posting service. Add a targeted test if the tenant uses `is_deferred` products.
