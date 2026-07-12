# Purchase/Store Debt Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four correctness follow-ups triaged out of the #137/#145 final reviews: bill-reversal stock mutations invisible to the movement log, opening-qty bootstrap invisible to the movement log, missing row locks on Gate Inward create/cancel + PO convert-to-bill, and vendor-performance counting undelivered POs as 100% short-receipt.

**Architecture:** All stock-quantity mutations must emit a `StockMovement` row so the perpetual Stock Tie-out (`routers/store_reports.py`) reconciles to zero. `services/inventory.py` stays the only writer of layers/movements; routers call it. Row locks follow the existing `with_for_update()` idiom from `routers/gate_outward.py:172`.

**Tech Stack:** FastAPI + SQLModel, pytest via `TestClient`, SQLite in tests (locks are no-ops there; Postgres honours them).

## Global Constraints

- Branch: `fix/purchase-store-debt` off `main`.
- Run tests from `backend/`: `PYTHONPATH=. uv run pytest` — 2 pre-existing failures exist on main (`test_account_hierarchy`, update-migration test); record the baseline before starting and compare against it, not against zero.
- Every DB query filters by `tenant_id`.
- Use `D()` / `money()` / `ZERO` from `services/money.py` for all quantities/amounts.
- `record_movement` raises on `qty <= 0` — guard every new call site.
- The tie-out's `received_qty` display column must keep meaning "bill receipts only" — new movement rows use distinct `source_doc_type` values (`bill_void`, `opening`), never `"bill"`.

---

### Task 1: `reverse_purchase` writes an ADJUSTMENT StockMovement

Bill edit (`routers/bills.py:479`) and bill void (`routers/transactions.py:139` → `_unwind_bill`) call `reverse_purchase`, which decrements `Product.stock_qty` without writing a `StockMovement`. Every reversed bill leaves a permanent negative variance in the Stock Tie-out.

**Files:**
- Modify: `backend/services/inventory.py:285-341` (`reverse_purchase`)
- Modify: `backend/routers/store_reports.py:173-211` (`_movement_sign` + its doc comment)
- Test: `backend/tests/test_stock_movement_gaps.py` (create)

**Interfaces:**
- Produces: `StockMovement(direction="ADJUSTMENT", source_doc_type="bill_void")` rows, signed `-1` by `_movement_sign`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_stock_movement_gaps.py`:

```python
"""Follow-ups from the #137/#145 final reviews: every stock_qty mutation
must emit a StockMovement so the perpetual Stock Tie-out reconciles."""
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


def _tie_out_row(client, auth, product_id):
    rows = client.get(
        f"/api/store-reports/stock-tie-out?product_id={product_id}", headers=auth
    ).json()
    return rows[0]


def _received_bill(client, auth, product_id, qty, rate=4):
    bill = client.post("/api/bills", headers=auth, json={
        "vendor_name": "Sup", "bill_date": "2026-02-01", "gst_rate": 0,
        "lines": [{"product_id": product_id, "description": "Nut", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/bills/{bill['id']}/status?status=received", headers=auth)
    return client.get(f"/api/bills/{bill['id']}", headers=auth).json()


def test_bill_edit_reversal_ties_out(client: TestClient):
    auth = _signup(client, "rev1@t.com")
    p = client.post("/api/products", headers=auth,
                    json={"name": "Nut", "product_type": "stock", "unit": "pcs"}).json()
    bill = _received_bill(client, auth, p["id"], qty=50)
    client.put(f"/api/bills/{bill['id']}", headers=auth, json={
        "vendor_name": "Sup", "bill_date": "2026-02-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Nut", "qty": 30, "rate": 4}],
    })
    row = _tie_out_row(client, auth, p["id"])
    assert float(row["actual_closing"]) == 30
    assert float(row["variance"]) == 0     # was -50 before the fix
    # the reversal must not masquerade as a bill receipt in the display column
    assert float(row["received_qty"]) == 80  # 50 original + 30 re-post


def test_bill_void_reversal_ties_out(client: TestClient):
    auth = _signup(client, "rev2@t.com")
    p = client.post("/api/products", headers=auth,
                    json={"name": "Bolt", "product_type": "stock", "unit": "pcs"}).json()
    bill = _received_bill(client, auth, p["id"], qty=20, rate=5)
    r = client.post(f"/api/transactions/{bill['transaction_id']}/reverse", headers=auth)
    assert r.status_code == 200
    row = _tie_out_row(client, auth, p["id"])
    assert float(row["actual_closing"]) == 0
    assert float(row["variance"]) == 0     # was -20 before the fix
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_stock_movement_gaps.py -v`
Expected: both FAIL on the `variance == 0` assertion (variance is -50 / -20).

- [ ] **Step 3: Implement**

In `services/inventory.py::reverse_purchase`, capture the layer's values before `session.delete(layer)` and emit the movement (skip when nothing remains to reverse):

```python
    for layer in layers:
        prod = session.exec(
            select(Product)
            .where(Product.id == layer.product_id, Product.tenant_id == tenant_id)
            .with_for_update()
        ).first()
        if not prod:
            continue
        reversed_qty = D(layer.qty_remaining)
        layer_loc, layer_lot, layer_cost = layer.location_id, layer.lot_no, D(layer.unit_cost)
        prod.stock_qty = D(prod.stock_qty) - reversed_qty
        session.add(prod)
        session.delete(layer)
        session.flush()

        # Event log — without this row the Stock Tie-out shows a permanent
        # negative variance for every voided/edited bill (#145 follow-up).
        if reversed_qty > 0:
            record_movement(
                session,
                tenant_id=tenant_id,
                product_id=prod.id,
                direction="ADJUSTMENT",
                qty=reversed_qty,
                from_location_id=layer_loc or _default_own_location(session, tenant_id),
                lot_no=layer_lot,
                unit_cost=layer_cost,
                source_doc_type="bill_void",
                posted_to_gl=True,
                notes=f"Reversal of receipt from {source_doc}",
            )
```

In `routers/store_reports.py::_movement_sign`:

```python
    if direction == "ADJUSTMENT":
        return -1 if source_doc_type in ("debit_note", "bill_void") else None
```

Extend the `-1 source_doc_type == "debit_note"` bullet in the `_STOCK_QTY_SIGN` comment block with a `bill_void` bullet citing `services/inventory.py::reverse_purchase` (deterministic decrement, same shape as the debit-note writer).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_stock_movement_gaps.py tests/test_edit_posted_bill.py tests/test_store_issues.py -v`
Expected: all PASS (edit-posted-bill and tie-out suites guard against regressions).

- [ ] **Step 5: Commit**

```bash
git add backend/services/inventory.py backend/routers/store_reports.py backend/tests/test_stock_movement_gaps.py
git commit -m "fix(inventory): reverse_purchase emits ADJUSTMENT movement so tie-out reconciles voided/edited bills"
```

---

### Task 2: opening-qty bootstrap writes a movement + layer

`POST /api/products` (`routers/products.py:190`) and the CSV importer (`routers/imports.py:457`) set `stock_qty`/`avg_cost` directly — no `StockMovement`, no `InventoryLayer`. Bootstrapped products show a permanent tie-out variance equal to their opening balance, and FIFO consumption has no layer to deplete.

**Files:**
- Modify: `backend/services/inventory.py:95-165` (`record_purchase` — add `source_doc_type` / `posted_to_gl` params)
- Modify: `backend/routers/products.py:184-197` (`create_product`)
- Modify: `backend/routers/imports.py:455-462` (products import loop)
- Test: `backend/tests/test_stock_movement_gaps.py` (extend)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `record_purchase(session, *, tenant_id, product_id, qty, unit_cost, source_doc=None, location_id=None, lot_no=None, source_doc_type="bill", posted_to_gl=True)` — existing callers unchanged by the defaults. Bootstrap rows: `direction="RECEIPT", source_doc_type="opening", posted_to_gl=False` (no GL entry is posted for opening balances).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_stock_movement_gaps.py`:

```python
def test_opening_qty_bootstrap_ties_out(client: TestClient):
    auth = _signup(client, "open1@t.com")
    p = client.post("/api/products", headers=auth, json={
        "name": "Washer", "product_type": "stock", "unit": "pcs",
        "opening_qty": 5, "opening_cost": 2,
    }).json()
    assert float(p["stock_qty"]) == 5
    assert float(p["avg_cost"]) == 2
    row = _tie_out_row(client, auth, p["id"])
    assert float(row["variance"]) == 0        # was -5 before the fix
    assert float(row["received_qty"]) == 0    # opening is not a bill receipt


def test_csv_import_opening_qty_ties_out(client: TestClient):
    auth = _signup(client, "open2@t.com")
    csv_body = (
        "code,name,unit,product_type,default_rate,reorder_level,category_name,"
        "is_deferred,recognition_months,hs_code,opening_qty,opening_cost\n"
        "IMP1,Imported Widget,pcs,stock,10,0,,,,,8,3\n"
    )
    r = client.post("/api/imports/products", headers=auth,
                    files={"file": ("products.csv", csv_body, "text/csv")})
    assert r.json()["imported"] == 1
    prods = client.get("/api/products", headers=auth).json()
    prod = next(x for x in (prods if isinstance(prods, list) else prods["items"])
                if x["name"] == "Imported Widget")
    row = _tie_out_row(client, auth, prod["id"])
    assert float(row["variance"]) == 0        # was -8 before the fix
```

(Adjust the products-list unwrapping to the actual response shape when running.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_stock_movement_gaps.py -v -k opening`
Expected: both FAIL on `variance == 0`.

- [ ] **Step 3: Implement**

`services/inventory.py::record_purchase` — new signature and pass-through:

```python
def record_purchase(
    session: Session,
    *,
    tenant_id: int,
    product_id: int,
    qty: Decimal,
    unit_cost: Decimal,
    source_doc: Optional[str] = None,
    location_id: Optional[int] = None,
    lot_no: Optional[str] = None,
    source_doc_type: str = "bill",
    posted_to_gl: bool = True,
) -> None:
```

and in its `record_movement(...)` call replace the hardcoded values:

```python
        source_doc_type=source_doc_type,
        notes=source_doc,
        posted_to_gl=posted_to_gl,
```

`routers/products.py::create_product` — replace the direct assignment:

```python
    p = Product(tenant_id=user.tenant_id, **body.model_dump(exclude=_bootstrap))
    session.add(p)
    if body.product_type == "stock" and body.opening_qty > 0:
        session.flush()
        record_purchase(
            session, tenant_id=user.tenant_id, product_id=p.id,
            qty=body.opening_qty, unit_cost=body.opening_cost,
            source_doc="OPENING", source_doc_type="opening", posted_to_gl=False,
        )
```

(import `record_purchase` from `services.inventory` at the top of the file if not already there).

`routers/imports.py` products loop — replace the direct assignment:

```python
        session.add(prod)
        if ptype == "stock" and opening_qty > 0:
            session.flush()
            record_purchase(
                session, tenant_id=user.tenant_id, product_id=prod.id,
                qty=opening_qty, unit_cost=opening_cost,
                source_doc="OPENING", source_doc_type="opening", posted_to_gl=False,
            )
        imported += 1
```

No `_movement_sign` change needed: `RECEIPT` is already `+1` regardless of `source_doc_type`, and the `received_qty` display column filters on `source_doc_type == "bill"` so opening rows don't pollute it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_stock_movement_gaps.py tests/test_csv_imports.py tests/test_edit_posted_invoice_stock.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/inventory.py backend/routers/products.py backend/routers/imports.py backend/tests/test_stock_movement_gaps.py
git commit -m "fix(inventory): opening-qty bootstrap goes through record_purchase — movement + layer, tie-out reconciles"
```

---

### Task 3: row locks on GI create/cancel and PO convert-to-bill

Two concurrent GI creates can both pass the remaining-qty check (over-receipt); two concurrent convert-to-bill calls can both see `bill_id is None` (double bill + double GL). Gate Outward's scrap approve already has the lock (`routers/gate_outward.py:172-176`); mirror it. SQLite ignores the locks (single-writer), Postgres honours them — so the deliverable is verified by the existing suite staying green, not by a new concurrency test.

**Files:**
- Modify: `backend/routers/gate_inward.py:99-103` (`create_gi`), `:165` (`cancel_gi`)
- Modify: `backend/routers/purchase_orders.py:227-231` (`convert_to_bill`)

**Interfaces:** none — behavior identical under SQLite; serialized under Postgres.

- [ ] **Step 1: Add the locks**

`create_gi` — add `.with_for_update()` to the PO fetch with the idiom comment:

```python
    # Row-locked fetch (see routers/gate_outward.py:172 for the idiom): two
    # concurrent GI creates against the same PO must not both read the same
    # coverage snapshot and jointly over-receive. SQLite ignores the lock;
    # Postgres serializes on the PO row.
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == body.po_id, PurchaseOrder.tenant_id == user.tenant_id
        ).with_for_update()
    ).first()
```

`cancel_gi` — replace `po = session.get(PurchaseOrder, gi.po_id)` with:

```python
    # Lock the PO so cancel can't race a concurrent convert-to-bill past the
    # billed check (same idiom as create_gi above).
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == gi.po_id, PurchaseOrder.tenant_id == user.tenant_id
        ).with_for_update()
    ).first()
```

`convert_to_bill` — add `.with_for_update()` to the PO fetch:

```python
    # Row-locked fetch: two concurrent converts must not both observe
    # bill_id is None and double-bill the PO (idiom: routers/gate_outward.py:172).
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == user.tenant_id
        ).with_for_update()
    ).first()
```

- [ ] **Step 2: Run the affected suites**

Run: `PYTHONPATH=. uv run pytest tests/test_gate_inward.py tests/test_purchase_flow.py tests/test_vendor_performance.py -v`
Expected: all PASS (no behavior change under SQLite).

- [ ] **Step 3: Commit**

```bash
git add backend/routers/gate_inward.py backend/routers/purchase_orders.py
git commit -m "fix(purchase): row-lock PO on GI create/cancel and convert-to-bill (Postgres concurrency)"
```

---

### Task 4: vendor-performance excludes undelivered POs from short-receipt

`routers/purchase_reports.py:146-153` accumulates `total_variance` for every PO — a PO with zero gate activity contributes `-qty` on every line, so a vendor with one pending order reads as 100% short-receipt. Only POs with at least one non-cancelled Gate Inward belong in the numerator/denominator.

**Files:**
- Modify: `backend/routers/purchase_reports.py:143-164`
- Test: `backend/tests/test_vendor_performance.py` (append)

**Interfaces:** response shape unchanged (`po_count` still counts all POs).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_vendor_performance.py`:

```python
def test_vendor_performance_pending_po_not_counted_short(client: TestClient):
    """An approved PO with no gate activity yet is an undelivered order,
    not a 100% short receipt (#145 review follow-up)."""
    auth = _signup(client, "vp4@t.com")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Pending Vendor"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "Pending Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    _full_chain_po(client, auth, vendor["id"], product["id"], qty=10)  # fully received
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    po2 = client.post("/api/purchase-orders", headers=auth, json={
        "vendor_id": vendor["id"], "order_date": "2026-06-20",
        "lines": [{"product_id": product["id"], "description": "Item", "qty": 10, "rate": 5}],
    }).json()
    client.patch(f"/api/purchase-orders/{po2['id']}/approve", headers=auth)  # no GI ever

    rows = client.get("/api/purchase-reports/vendor-performance", headers=auth).json()
    row = next(r for r in rows if r["vendor_id"] == vendor["id"])
    assert row["po_count"] == 2
    assert row["short_receipt_rate_pct"] == 0.0   # was 50.0 before the fix
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_vendor_performance.py::test_vendor_performance_pending_po_not_counted_short -v`
Expected: FAIL — `short_receipt_rate_pct == 50.0`.

- [ ] **Step 3: Implement**

Restructure the per-PO loop so the GI fetch happens first and gate-less POs are skipped:

```python
        lead_times = []
        total_ordered = D("0")
        total_variance = D("0")
        for po in pos:
            gis = session.exec(
                select(GateInward).where(
                    GateInward.po_id == po.id, GateInward.status != "cancelled",
                ).order_by(GateInward.gate_date)
            ).all()
            if not gis:
                # No gate activity — the PO is still undelivered (or predates
                # the gate module). Counting it would report every pending
                # order as a 100% short receipt.
                continue
            po_lines = session.exec(
                select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
            ).all()
            total_ordered += sum(D(l.qty) for l in po_lines)
            cov = gi_coverage(session, user.tenant_id, po.id)
            for l in po_lines:
                total_variance += cov.get(l.id, D(0)) - D(l.qty)

            earliest_gi = gis[0]
            d_po = _date.fromisoformat(po.order_date)
            d_gi = _date.fromisoformat(earliest_gi.gate_date)
            lead_times.append((d_gi - d_po).days)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_vendor_performance.py -v`
Expected: all PASS, including the 3-way-match cross-check test (both of its POs have GIs, so its denominator is unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/purchase_reports.py backend/tests/test_vendor_performance.py
git commit -m "fix(reports): vendor performance skips gate-less POs in short-receipt rate"
```

---

### Task 5: full-suite verification + BLUEPRINT "Still Pending" update

**Files:**
- Modify: `BLUEPRINT.md` (the "Still Pending" list — strike the four items fixed here; keep FK-cycle, report pagination, `purchase.gate` permission coupling, and signless physical-count adjustments as still pending)

- [ ] **Step 1: Run the whole backend suite**

Run: `PYTHONPATH=. uv run pytest`
Expected: same pass/fail count as the baseline recorded before Task 1 (only the 2 pre-existing failures).

- [ ] **Step 2: Update BLUEPRINT.md**

Locate the "Still Pending" items describing (a) `reverse_purchase` missing StockMovement, (b) opening-qty bootstrap missing StockMovement, (c) missing row locks on GI create/cancel + convert-to-bill, (d) vendor-performance zero-GI denominator — mark each as fixed with today's date and this branch, leaving the untouched items in place.

- [ ] **Step 3: Commit**

```bash
git add BLUEPRINT.md
git commit -m "docs: mark four purchase/store review follow-ups as fixed in BLUEPRINT"
```
