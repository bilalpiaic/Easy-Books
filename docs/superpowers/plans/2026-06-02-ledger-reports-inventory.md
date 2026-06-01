# Ledger Fix, Reports & Inventory Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix the General-Ledger opening-balance bug, surface the existing Product-Category feature, add an optional over-sell guard with on-hand display, ship four reports (Aging V+C, Product Ledger, Inventory & Customer Performance), seed demo data for them, and update the docs.

**Architecture:** All report endpoints are read-only, computed live from the GL / stock tables, tenant-filtered, in `backend/routers/reports.py` (or `aging.py`). Frontend pages are client components using `apiFetch` + existing report-page styling. The over-sell guard lives in `services/inventory.py` (where stock is relieved). **No DB migrations** — `ProductCategory` already exists and the over-sell flag is a key-value `Settings` row.

**Tech Stack:** FastAPI · SQLModel · pytest · Next.js 16 / React / TypeScript · Tailwind v4.

> **Spec:** `docs/superpowers/specs/2026-06-02-ledger-reports-inventory-design.md`.
> **Verified anchors:** `reports.py:429 get_ledger` (the GL bug); `subledger.py` (correct opening-balance reference); `routers/aging.py` (`/api/invoices/aging` + `/api/bills/aging` already return buckets + per-item lists); `services/inventory.py consume_stock` (relieves stock, lets it go negative — guard goes here; `InventoryError` class already exists); `StockMovement` (`occurred_at`, `direction`, `qty`, `from/to_location_id`); `Sidebar.tsx` `NAV` array (`Products` is under `section:"Payable"`); current Alembic head not needed (no migrations).

---

## FILE STRUCTURE

| File | Responsibility | Phase |
|------|---------------|-------|
| `frontend/src/components/Sidebar.tsx` (modify) | New "Inventory" nav section; move Products; add Categories + report links | A, D |
| `backend/db.py` (modify) | Starter categories for all models incl. `simple` | A |
| `frontend/src/app/(dashboard)/products/page.tsx` (modify) | Cursor + tooltip on description; on-hand already in data | A |
| `backend/routers/reports.py` (modify) | GL opening/closing; new report endpoints | B, D |
| `backend/tests/test_ledger_opening.py` (new) | GL opening+movements=closing | B |
| `frontend/src/app/(dashboard)/ledger/page.tsx` (modify) | Opening/Closing rows | B |
| `backend/routers/settings.py` (modify) | `block_negative_stock` setting | C |
| `frontend/src/context/SettingsContext.tsx` (modify) | `block_negative_stock` default | C |
| `frontend/src/app/(dashboard)/settings/page.tsx` (modify) | Over-sell toggle | C |
| `backend/services/inventory.py` (modify) | Over-sell guard in `consume_stock` | C |
| `backend/routers/invoices.py` (modify) | Pass the setting into stock relief | C |
| `backend/tests/test_oversell_guard.py` (new) | Guard on/off behaviour | C |
| `frontend/src/app/(dashboard)/invoices/page.tsx`, `bills/page.tsx` (modify) | On-hand display + warning on lines | C |
| `backend/routers/aging.py` (modify) | Add party id to items for drill-down | D1 |
| `frontend/src/app/(dashboard)/aging/receivable/page.tsx`, `aging/payable/page.tsx` (new) | Aging pages | D1 |
| `backend/tests/test_reports_new.py` (new) | product-ledger / inventory / customer endpoints | D |
| `frontend/src/app/(dashboard)/products/ledger/page.tsx` (new) | Product Ledger | D2 |
| `frontend/src/app/(dashboard)/inventory/performance/page.tsx` (new) | Inventory Performance | D3 |
| `frontend/src/app/(dashboard)/customer-performance/page.tsx` (new) | Customer Performance | D4 |
| `backend/scripts/seed_demo.py` (modify) | Assign categories; ensure report variety | E |
| `USER_GUIDE.md`, `WORKFLOW.md`, `CLAUDE.md`, `README.md` (modify) | Docs | F |

---

## PHASE A — Surface & polish

### Task A1: Dedicated Inventory nav section (items 2 + 6)
**Files:** Modify `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1:** In the `NAV` array, change the `Products` row's section from `"Payable"` to `"Inventory"`, and add a Categories row right after it:
```tsx
  { label: "Products",          href: "/products",            icon: Package,  section: "Inventory" },
  { label: "Product Categories",href: "/products/categories", icon: Tags,     section: "Inventory" },
```
(`Tags` is already imported.)
- [ ] **Step 2:** Add `"Inventory"` to `ALL_SECTIONS` immediately after `"Payable"`:
```tsx
const ALL_SECTIONS = ["Overview","Ledger","Receivable","Payable","Inventory","Manufacturing","Telecom","Banking","Reports","System"]
```
- [ ] **Step 3:** Add a colour in `SECTION_COLORS`:
```tsx
  Inventory:     "text-amber-400",
```
- [ ] **Step 4: Verify** `cd frontend && npx tsc --noEmit` (clean) and that `/products` + `/products/categories` now appear under an "Inventory" heading (`npm run dev`, check sidebar). The Product-Ledger and Inventory-Report links are added in Tasks D2/D3.
- [ ] **Step 5: Commit** `git add frontend/src/components/Sidebar.tsx && git commit -m "feat(nav): dedicated Inventory section with Products + Categories"`

### Task A2: Starter categories for every business model
**Files:** Modify `backend/db.py` (the `STARTER_CATEGORIES` dict added earlier in `seed_data`)

- [ ] **Step 1:** Add a `simple` (and a generic `services`) entry so no model starts categoryless:
```python
        STARTER_CATEGORIES = {
            "simple":            {"General": ["Products", "Services"]},
            "services":          {"Services": ["Consulting", "Recurring"]},
            "trader":            {"Goods": ["General", "Imported"]},
            "manufacturing":     {"Raw Materials": ["Metals", "Consumables"],
                                  "Finished Goods": ["Standard"]},
            "telecom_franchise": {"SIM": ["Prepaid", "Postpaid"],
                                  "Devices": ["Handsets", "Accessories"]},
        }
```
(Leave the existing guard — `if not s.exec(select(ProductCategory)...).first()` — so it only seeds an empty tenant.)
- [ ] **Step 2: Verify** `cd backend && PYTHONPATH=. uv run pytest -q` stays green.
- [ ] **Step 3: Commit** `git add backend/db.py && git commit -m "feat(products): seed starter categories for all business models"`

### Task A3: Cursor + tooltip on product description (item 9); confirm Quick Actions
**Files:** Modify `frontend/src/app/(dashboard)/products/page.tsx`

- [ ] **Step 1:** Find the table cell rendering the product `name`/`description`. Add `cursor-pointer` and a `title` tooltip, and make it open the existing edit modal on click (so the pointer is meaningful):
```tsx
  <td className="px-4 py-3 cursor-pointer" title={p.name} onClick={() => openEdit(p)}>
    <span className="...">{p.name}</span>
  </td>
```
Use the page's real edit handler name (search for where the modal is opened, e.g. `openEdit`/`setEditProduct`); match it.
- [ ] **Step 2: Confirm Quick Actions** is already a top toolbar in `frontend/src/app/(dashboard)/dashboard/page.tsx` (a `QUICK_ACTIONS` bar rendered right under the header, above the KPIs). It is — no change. If a regression is found, move the block back under the header.
- [ ] **Step 3: Verify** `cd frontend && npx tsc --noEmit` clean.
- [ ] **Step 4: Commit** `git add "frontend/src/app/(dashboard)/products/page.tsx" && git commit -m "feat(products): pointer cursor + tooltip on description; opens edit"`

---

## PHASE B — General Ledger opening balance (item 1)

### Task B1: GL endpoint computes opening + closing
**Files:** Modify `backend/routers/reports.py` (`get_ledger`, ~line 429); Test `backend/tests/test_ledger_opening.py`

- [ ] **Step 1: Write the failing test**
```python
# backend/tests/test_ledger_opening.py
def _post_jv(client, headers, date, debit_code, credit_code, amount):
    """Post a balanced 2-line journal via the transactions API."""
    accts = client.get("/api/accounts?limit=500", headers=headers).json()["items"]
    by_code = {a["code"]: a["id"] for a in accts}
    r = client.post("/api/transactions", headers=headers, json={
        "date": date, "description": "test",
        "entries": [
            {"account_id": by_code[debit_code], "debit": amount, "credit": 0},
            {"account_id": by_code[credit_code], "debit": 0, "credit": amount},
        ],
    })
    assert r.status_code in (200, 201), r.text


def test_ledger_opening_plus_movements_equals_closing(client, admin_headers):
    h = admin_headers
    # 1000 Cash (Asset) debited 100 before the window, 40 inside it.
    _post_jv(client, h, "2026-01-10", "1000", "3000", 100)   # before start
    _post_jv(client, h, "2026-03-15", "1000", "3000", 40)    # in window
    data = client.get("/api/reports/ledger?start=2026-03-01&end=2026-03-31&account_code=1000",
                      headers=h).json()
    acct = data["items"][0]
    assert float(acct["opening_balance"]) == 100.0          # carried in
    assert float(acct["closing_balance"]) == 140.0          # opening + 40
    assert float(acct["closing_balance"]) == float(acct["opening_balance"]) + 40.0
```
> Adapt `_post_jv` to the real `POST /api/transactions` shape if it differs (check `routers/transactions.py`); keep the three assertions. Uses the shared `client`/`admin_headers` fixtures from `conftest.py`.

- [ ] **Step 2: Run — expect FAIL** (`opening_balance` missing / closing == 40 not 140): `cd backend && PYTHONPATH=. uv run pytest tests/test_ledger_opening.py -v`

- [ ] **Step 3: Replace `get_ledger`** in `backend/routers/reports.py` with:
```python
@router.get("/ledger")
def get_ledger(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    search: Optional[str] = None,
    account_id: Optional[int] = None, account_code: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    from collections import defaultdict
    acc_q = select(Account).where(Account.tenant_id == user.tenant_id)
    if account_id:
        acc_q = acc_q.where(Account.id == account_id)
    elif account_code:
        acc_q = acc_q.where(Account.code == account_code)
    elif search:
        acc_q = acc_q.where(Account.name.ilike(f"%{search}%"))
    scope = {a.id: a for a in session.exec(acc_q).all()}
    if not scope:
        return {"total": 0, "items": []}

    def signed(atype, debit, credit):
        d, c = D(debit), D(credit)
        return (d - c) if atype in ("Asset", "Expense") else (c - d)

    # Opening balance per account = net of all entries strictly before `start`.
    opening: dict = defaultdict(lambda: ZERO)
    if start:
        for acc_id, debit, credit in (
            session.query(JournalEntry.account_id, JournalEntry.debit, JournalEntry.credit)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .filter(Transaction.tenant_id == user.tenant_id,
                    Transaction.date < start,
                    JournalEntry.account_id.in_(list(scope.keys())))
            .all()
        ):
            opening[acc_id] += signed(scope[acc_id].type, debit, credit)

    q = (
        session.query(Transaction, JournalEntry)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(Transaction.tenant_id == user.tenant_id,
                JournalEntry.account_id.in_(list(scope.keys())))
    )
    if start:
        q = q.filter(Transaction.date >= start)
    if end:
        q = q.filter(Transaction.date <= end)
    inrange = q.order_by(JournalEntry.account_id, Transaction.date, Transaction.id).all()

    accounts: dict = {}
    def ensure(acc_id):
        if acc_id not in accounts:
            a = scope[acc_id]
            accounts[acc_id] = {
                "id": a.id, "code": a.code, "name": a.name, "type": a.type,
                "opening_balance": opening[acc_id], "entries": [],
                "running_balance": opening[acc_id],
            }
        return accounts[acc_id]

    for acc_id, bal in opening.items():        # accounts with only an opening
        if bal != ZERO:
            ensure(acc_id)
    for tx, je in inrange:
        rec = ensure(je.account_id)
        rec["running_balance"] += signed(rec["type"], je.debit, je.credit)
        rec["entries"].append({
            "date": tx.date, "transaction_id": tx.id, "jv_number": tx.jv_number,
            "description": tx.description or "", "debit": je.debit,
            "credit": je.credit, "balance": rec["running_balance"],
        })

    items = []
    for rec in accounts.values():
        rec["closing_balance"] = rec["running_balance"]
        items.append(rec)
    items.sort(key=lambda r: r["code"])
    return {"total": len(items), "items": items[skip: skip + limit]}
```
- [ ] **Step 4: Run — expect PASS.** Then full suite: `PYTHONPATH=. uv run pytest -q` (stays green).
- [ ] **Step 5: Commit** `git add backend/routers/reports.py backend/tests/test_ledger_opening.py && git commit -m "fix(reports): GL opening balance on date filter (closing = opening + dr - cr)"`

### Task B2: Ledger page shows Opening / Closing rows
**Files:** Modify `frontend/src/app/(dashboard)/ledger/page.tsx`

- [ ] **Step 1:** Read the page; add `opening_balance: number|string` and `closing_balance: number|string` to its `LedgerAccount` interface. For each account block, render an **Opening Balance** row above its entries and a **Closing Balance** row below, using the brand styling already used for totals (`fmt(...)` from `useFmt`). Example rows:
```tsx
<tr className="bg-[#f6f3ee] text-[#1a1814]/70 text-xs font-semibold">
  <td className="px-4 py-2" colSpan={3}>Opening Balance</td>
  <td className="px-4 py-2 text-right">{fmt(Number(acct.opening_balance))}</td>
</tr>
{/* ...existing entry rows... */}
<tr className="bg-[#faf8f4] font-bold text-[#1a1814]">
  <td className="px-4 py-2" colSpan={3}>Closing Balance</td>
  <td className="px-4 py-2 text-right">{fmt(Number(acct.closing_balance))}</td>
</tr>
```
Match the existing column count/markup.
- [ ] **Step 2: Verify** `npx tsc --noEmit` clean; `/ledger` with a date range shows Opening + Closing and Closing = Opening + (debits−credits) per the convention.
- [ ] **Step 3: Commit** `git add "frontend/src/app/(dashboard)/ledger/page.tsx" && git commit -m "feat(ledger): show opening + closing balance rows per account"`

---

## PHASE C — Inventory posting: on-hand + over-sell guard (item 8)

### Task C1: `block_negative_stock` setting
**Files:** Modify `backend/routers/settings.py`, `frontend/src/context/SettingsContext.tsx`, `frontend/src/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1:** In `routers/settings.py`, add `block_negative_stock: Optional[str] = None` to the `SettingsUpdate` model, and include `"block_negative_stock"` with default `"false"` wherever the settings defaults/GET are assembled (follow the pattern of an existing boolean-ish key like `email_notifications`).
- [ ] **Step 2:** In `SettingsContext.tsx`, add `block_negative_stock: string` to the `AppSettings` interface and `block_negative_stock: "false"` to the `defaults`.
- [ ] **Step 3:** In `settings/page.tsx`, add a toggle (mirror an existing toggle field) labelled **"Block overselling (prevent negative stock)"** bound to `block_negative_stock` ("true"/"false"), persisted via the existing `/api/settings` PATCH save.
- [ ] **Step 4: Verify** `cd backend && PYTHONPATH=. uv run pytest -q` green; `cd frontend && npx tsc --noEmit` clean.
- [ ] **Step 5: Commit** `git add backend/routers/settings.py frontend/src/context/SettingsContext.tsx "frontend/src/app/(dashboard)/settings/page.tsx" && git commit -m "feat(inventory): add block_negative_stock setting"`

### Task C2: Over-sell guard in stock relief
**Files:** Modify `backend/services/inventory.py`, `backend/routers/invoices.py`; Test `backend/tests/test_oversell_guard.py`

- [ ] **Step 1: Write the failing test**
```python
# backend/tests/test_oversell_guard.py
def _setup_stock_product(client, h, on_hand):
    # Create a stock product, then receive `on_hand` via a bill (or set stock).
    p = client.post("/api/products", headers=h, json={
        "name": "Widget", "product_type": "stock", "default_rate": 10}).json()
    # Receive stock so on-hand = on_hand (use the bill flow used elsewhere in tests).
    ...
    return p

def test_oversell_blocked_when_setting_on(client, admin_headers):
    h = admin_headers
    client.patch("/api/settings", headers=h, json={"block_negative_stock": "true"})
    p = _setup_stock_product(client, h, on_hand=5)
    # Invoice selling 9 (> 5 on hand) must be rejected, leaving stock untouched.
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "due_date": "2026-03-31",
        "lines": [{"product_id": p["id"], "description": "Widget", "qty": 9, "rate": 10}]})
    assert r.status_code == 400
    assert "stock" in r.json()["detail"].lower()
    prod = client.get(f"/api/products/{p['id']}", headers=h).json()
    assert float(prod["stock_qty"]) == 5.0  # unchanged

def test_oversell_allowed_when_setting_off(client, admin_headers):
    h = admin_headers
    client.patch("/api/settings", headers=h, json={"block_negative_stock": "false"})
    p = _setup_stock_product(client, h, on_hand=5)
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "due_date": "2026-03-31",
        "lines": [{"product_id": p["id"], "description": "Widget", "qty": 9, "rate": 10}]})
    assert r.status_code in (200, 201)
```
> Wire `_setup_stock_product` to the real stock-receipt path used by other inventory tests (look at `tests/` for how stock is received — e.g. posting a bill with a stock line, or `record_purchase`). Adapt the invoice payload to the real `POST /api/invoices` shape. Keep the behavioural assertions.

- [ ] **Step 2: Run — expect FAIL** (oversell currently allowed): `cd backend && PYTHONPATH=. uv run pytest tests/test_oversell_guard.py -v`

- [ ] **Step 3:** Add a `block_negative` param + guard to `consume_stock` in `services/inventory.py`. After the product is fetched (the `with_for_update()` block) and confirmed `product_type == "stock"`, before mutating:
```python
def consume_stock(
    session: Session, *, tenant_id: int, product_id: int, qty: Decimal,
    block_negative: bool = False,
) -> Decimal:
    ...
    if not prod or prod.product_type != "stock":
        return ZERO
    if block_negative and D(prod.stock_qty) < qty:
        raise InventoryError(
            f"Insufficient stock for {prod.name}: on hand {money(prod.stock_qty)}, "
            f"sale {money(qty)}"
        )
    ...
```
- [ ] **Step 4:** In `routers/invoices.py`, where the invoice posting calls `consume_stock(...)`, read the setting once and pass it. Add near the top of the posting handler:
```python
    from models import Settings as _Settings
    _blk = session.exec(
        select(_Settings).where(_Settings.tenant_id == user.tenant_id,
                                _Settings.key == "block_negative_stock")
    ).first()
    block_negative = bool(_blk and (_blk.value or "").lower() == "true")
```
and pass `block_negative=block_negative` to each `consume_stock(...)` call. Ensure the `InventoryError` is translated to `HTTPException(400, str(e))` (the endpoint likely already catches `InventoryError`; if not, wrap the posting in try/except). The check runs before any GL/stock write, so a rejected sale leaves data untouched.
- [ ] **Step 5: Run — expect PASS**; then full suite green.
- [ ] **Step 6: Commit** `git add backend/services/inventory.py backend/routers/invoices.py backend/tests/test_oversell_guard.py && git commit -m "feat(inventory): optional over-sell guard on sales (block_negative_stock)"`

### Task C3: On-hand qty + warning on invoice/bill lines
**Files:** Modify `frontend/src/app/(dashboard)/invoices/page.tsx`, `frontend/src/app/(dashboard)/bills/page.tsx`

- [ ] **Step 1:** These forms already load products (for the line product picker) — each product has `stock_qty` and `product_type`. When a **stock** product is selected on a line, render **`On hand: {fmt-qty}`** next to the qty input. On invoices, if the line qty `>` the product's `stock_qty`, show an amber inline hint (e.g. `text-amber-600`: "exceeds on-hand"). Read the product from the already-loaded products list by `product_id`; no new fetch.
- [ ] **Step 2: Verify** `npx tsc --noEmit` clean; selecting a stock product on an invoice line shows on-hand, and an over-qty line shows the warning (saving still works when the setting is off; the server enforces when on).
- [ ] **Step 3: Commit** `git add "frontend/src/app/(dashboard)/invoices/page.tsx" "frontend/src/app/(dashboard)/bills/page.tsx" && git commit -m "feat(inventory): show on-hand qty + over-sell warning on invoice/bill lines"`

---

## PHASE D — New reports (items 3, 4, 5, 7)

### Task D1: Aging pages (Receivable & Payable)
**Files:** Modify `backend/routers/aging.py`; Create `frontend/src/app/(dashboard)/aging/receivable/page.tsx`, `aging/payable/page.tsx`; Modify `Sidebar.tsx`

- [ ] **Step 1:** In `aging.py`, add the party id to each item so the page can drill to the party ledger. In `invoice_aging`, select `Invoice.customer_id` and add `"customer_id": r.customer_id` to each item dict; in `bill_aging`, select `Bill.vendor_id` and add `"vendor_id": r.vendor_id`. (If those columns aren't on the model, drill to the invoice/bill instead and skip the id.)
- [ ] **Step 2:** Create `aging/receivable/page.tsx` (client component): fetch `GET /api/invoices/aging`, render the five bucket totals as summary cards (Current / 1-30 / 31-60 / 61-90 / 90+) and a table of `items` (name, number, due_date, days_past, amount, bucket) grouped by `name`; each party links to `/customers/${customer_id}/ledger` when present. Use `useFmt` + existing report-page styling. `aging/payable/page.tsx` is the same against `/api/bills/aging` → `/vendors/${vendor_id}/ledger`.
- [ ] **Step 3:** In `Sidebar.tsx` `NAV`, add under `Reports`:
```tsx
  { label: "AR Aging",  href: "/aging/receivable", icon: Clock, section: "Reports" },
  { label: "AP Aging",  href: "/aging/payable",    icon: Clock, section: "Reports" },
```
(import `Clock` from lucide-react if not already imported.)
- [ ] **Step 4: Verify** `npx tsc --noEmit` clean; both pages render buckets + items and links resolve.
- [ ] **Step 5: Commit** `git add backend/routers/aging.py "frontend/src/app/(dashboard)/aging" frontend/src/components/Sidebar.tsx && git commit -m "feat(reports): AR/AP aging pages with drill-down"`

### Task D2: Product Ledger (by store or consolidated)
**Files:** Modify `backend/routers/reports.py`; Test `backend/tests/test_reports_new.py`; Create `frontend/src/app/(dashboard)/products/ledger/page.tsx`; Modify `Sidebar.tsx`

- [ ] **Step 1: Write the failing test** (in `test_reports_new.py`)
```python
def test_product_ledger_running_qty(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h, json={
        "name": "Bolt", "product_type": "stock"}).json()
    # Receive 10 then sell 4 (use the real stock paths as in other tests).
    ...
    data = client.get(f"/api/reports/product-ledger?product_id={p['id']}", headers=h).json()
    assert data["items"][-1]["running_qty"] == 6        # 10 in, 4 out
```
- [ ] **Step 2:** Add to `reports.py`:
```python
_IN_DIRECTIONS = {"RECEIPT", "CUSTODIAL_RECEIPT", "COMPLETION", "CUSTODIAL_COMPLETION"}

@router.get("/product-ledger")
def product_ledger(
    session: SessionDep, user: CurrentUserDep,
    product_id: int, location_id: Optional[int] = None,
    start: Optional[str] = None, end: Optional[str] = None,
):
    from models import StockMovement
    q = select(StockMovement).where(
        StockMovement.tenant_id == user.tenant_id,
        StockMovement.product_id == product_id,
    )
    if location_id is not None:
        q = q.where(
            (StockMovement.from_location_id == location_id)
            | (StockMovement.to_location_id == location_id)
        )
    rows = session.exec(q.order_by(StockMovement.occurred_at, StockMovement.id)).all()
    running = ZERO
    items = []
    for m in rows:
        d = m.occurred_at.date().isoformat() if hasattr(m.occurred_at, "date") else str(m.occurred_at)[:10]
        if start and d < start:
            continue
        if end and d > end:
            continue
        sign = 1 if m.direction in _IN_DIRECTIONS else -1
        running += sign * D(m.qty)
        items.append({
            "date": d, "direction": m.direction, "qty_in": D(m.qty) if sign > 0 else ZERO,
            "qty_out": D(m.qty) if sign < 0 else ZERO, "running_qty": running,
            "unit_cost": m.unit_cost, "source": m.source_doc_type or "",
        })
    return {"product_id": product_id, "location_id": location_id, "items": items}
```
> Note: when `start`/`end` are given the running qty still accumulates from the first movement (date-filtering only hides earlier *rows* from the table). If a true opening-qty-at-start is wanted later, mirror the GL opening pattern; out of scope here.

- [ ] **Step 3: Run — expect PASS.**
- [ ] **Step 4:** Create `products/ledger/page.tsx`: a product `<select>` (from `/api/products`), a store `<select>` (from `/api/stock-locations`, plus a "Consolidated (all stores)" option = no `location_id`), optional date range; table of movements (date, direction, in, out, running qty). Add a `Sidebar.tsx` `Reports`→ actually `Inventory` section link:
```tsx
  { label: "Product Ledger", href: "/products/ledger", icon: BookOpen, section: "Inventory" },
```
- [ ] **Step 5: Verify + Commit** `npx tsc --noEmit` clean; `git add backend/routers/reports.py backend/tests/test_reports_new.py "frontend/src/app/(dashboard)/products/ledger" frontend/src/components/Sidebar.tsx && git commit -m "feat(reports): product ledger by store or consolidated"`

### Task D3: Inventory Performance
**Files:** Modify `backend/routers/reports.py`, `backend/tests/test_reports_new.py`; Create `frontend/src/app/(dashboard)/inventory/performance/page.tsx`; Modify `Sidebar.tsx`

- [ ] **Step 1: Test**
```python
def test_inventory_performance_value(client, admin_headers):
    h = admin_headers
    # product with on-hand 10 @ avg_cost 3 → value 30 (via the real receipt path)
    ...
    data = client.get("/api/reports/inventory-performance", headers=h).json()
    row = next(r for r in data["items"] if r["name"] == "Gizmo")
    assert float(row["stock_value"]) == 30.0
```
- [ ] **Step 2:** Add to `reports.py`:
```python
@router.get("/inventory-performance")
def inventory_performance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    from models import StockMovement
    prods = session.exec(
        select(Product).where(Product.tenant_id == user.tenant_id,
                              Product.product_type == "stock")
    ).all()
    out = []
    for p in prods:
        mv = session.exec(
            select(StockMovement).where(
                StockMovement.tenant_id == user.tenant_id,
                StockMovement.product_id == p.id,
            ).order_by(StockMovement.occurred_at.desc())
        ).all()
        last = mv[0].occurred_at.date().isoformat() if mv else None
        units_sold = sum(
            (D(m.qty) for m in mv
             if m.direction in ("SHIPMENT", "DELIVERY", "ISSUE")
             and (not start or m.occurred_at.date().isoformat() >= start)
             and (not end or m.occurred_at.date().isoformat() <= end)),
            start=ZERO,
        )
        out.append({
            "id": p.id, "name": p.name, "code": p.code,
            "on_hand": D(p.stock_qty), "avg_cost": D(p.avg_cost),
            "stock_value": money(D(p.stock_qty) * D(p.avg_cost)),
            "reorder_level": D(p.reorder_level),
            "low_stock": D(p.stock_qty) <= D(p.reorder_level),
            "last_movement": last,
            "units_sold": units_sold,
            "cogs": money(units_sold * D(p.avg_cost)),
        })
    out.sort(key=lambda r: r["stock_value"], reverse=True)
    return {"items": out}
```
- [ ] **Step 3: Run PASS.**
- [ ] **Step 4:** Create `inventory/performance/page.tsx`: period picker + sortable table (name, on-hand, value, low-stock badge, last-movement, units sold, COGS). `Sidebar.tsx` `Inventory` link:
```tsx
  { label: "Inventory Report", href: "/inventory/performance", icon: PieChart, section: "Inventory" },
```
- [ ] **Step 5: Verify + Commit** `git add backend/routers/reports.py backend/tests/test_reports_new.py "frontend/src/app/(dashboard)/inventory" frontend/src/components/Sidebar.tsx && git commit -m "feat(reports): inventory performance report"`

### Task D4: Customer Performance
**Files:** Modify `backend/routers/reports.py`, `backend/tests/test_reports_new.py`; Create `frontend/src/app/(dashboard)/customer-performance/page.tsx`; Modify `Sidebar.tsx`

- [ ] **Step 1: Test**
```python
def test_customer_performance_revenue(client, admin_headers):
    h = admin_headers
    # one customer, two invoices in-period totalling 300 (real invoice path)
    ...
    data = client.get("/api/reports/customer-performance?start=2026-01-01&end=2026-12-31",
                      headers=h).json()
    row = next(r for r in data["items"] if r["name"] == "Acme")
    assert float(row["revenue"]) == 300.0
    assert row["invoice_count"] == 2
```
- [ ] **Step 2:** Add to `reports.py` (aggregate invoices per customer; outstanding via `PaymentAllocation`; avg days-to-pay from paid invoices using payment dates):
```python
@router.get("/customer-performance")
def customer_performance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    from models import Invoice, PaymentAllocation, PaymentReceived
    q = select(Invoice).where(Invoice.tenant_id == user.tenant_id)
    if start:
        q = q.where(Invoice.issue_date >= start)
    if end:
        q = q.where(Invoice.issue_date <= end)
    invoices = session.exec(q).all()
    agg: dict = {}
    for inv in invoices:
        a = agg.setdefault(inv.customer_name or "—", {
            "name": inv.customer_name or "—", "revenue": ZERO, "invoice_count": 0,
            "outstanding": ZERO, "_paydays": [], "_paydates": 0,
        })
        a["revenue"] += D(inv.total)
        a["invoice_count"] += 1
        allocated = session.exec(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
            .where(PaymentAllocation.invoice_id == inv.id)
        ).one()
        allocated = D(allocated[0] if isinstance(allocated, tuple) else allocated)
        a["outstanding"] += max(D(inv.total) - allocated, ZERO)
        # avg days-to-pay: for fully-paid invoices, last allocation's payment date − issue date
        if allocated >= D(inv.total) and D(inv.total) > 0:
            last_pay = session.exec(
                select(PaymentReceived.payment_date)
                .join(PaymentAllocation, PaymentAllocation.payment_id == PaymentReceived.id)
                .where(PaymentAllocation.invoice_id == inv.id)
                .order_by(PaymentReceived.payment_date.desc())
            ).first()
            if last_pay:
                from datetime import date as _date
                a["_paydays"].append((_date.fromisoformat(last_pay) - _date.fromisoformat(inv.issue_date)).days)
    out = []
    for a in agg.values():
        days = a.pop("_paydays"); a.pop("_paydates", None)
        a["avg_days_to_pay"] = round(sum(days) / len(days), 1) if days else None
        out.append(a)
    out.sort(key=lambda r: r["revenue"], reverse=True)
    return {"items": out}
```
> Adapt the `PaymentReceived`/`PaymentAllocation` join column names to the real models (check `models.py`); the `subledger.py` customer ledger already joins these — mirror it. Keep revenue/count/outstanding/avg-days semantics.

- [ ] **Step 3: Run PASS.**
- [ ] **Step 4:** Create `customer-performance/page.tsx`: period picker + ranked table (name, revenue, # invoices, outstanding, avg days-to-pay), top-3 highlighted. `Sidebar.tsx` under `Receivable` or `Reports`:
```tsx
  { label: "Customer Performance", href: "/customer-performance", icon: TrendingUp, section: "Reports" },
```
- [ ] **Step 5: Verify + Commit** `git add backend/routers/reports.py backend/tests/test_reports_new.py "frontend/src/app/(dashboard)/customer-performance" frontend/src/components/Sidebar.tsx && git commit -m "feat(reports): customer performance report"`

---

## PHASE E — Demo data for the new features

### Task E1: Seed categories on products + ensure report variety
**Files:** Modify `backend/scripts/seed_demo.py`; extend `backend/tests/test_reports_new.py`

- [ ] **Step 1:** In `seed_demo.py`'s product-seeding (`_seed_products`), after products + categories exist for the tenant, **assign each product a category**: load the tenant's `ProductCategory` rows, and set `product.category_id` to a sub-category (round-robin) for stock products. (Categories are seeded by `seed_data`/`db.py`; ensure `_seed_products` runs after that, or create a couple inline if none exist.)
- [ ] **Step 2:** Confirm the seeder already produces: multiple stock receipts + sales (→ Product Ledger history + Inventory fast/slow movers — leave ≥2 products unsold for "no-movers"), and invoices with a mix of paid (varied `payment_date`) and unpaid/overdue (→ aging buckets + avg-days-to-pay). If any category is empty after seeding, adjust counts minimally. Do **not** break idempotency (guard new work with existence checks).
- [ ] **Step 3: Test** — extend `test_reports_new.py`:
```python
def test_demo_seed_populates_new_reports(client, admin_headers, monkeypatch):
    # Reuse the demo seeder against the test DB (see test_admin_demo for the pattern),
    # then assert the new reports are non-empty for a demo tenant.
    from scripts.seed_demo import seed_one_tenant
    seed_one_tenant("demo.trader@easy-books.app", "Demo Trading Co.", "trader")
    # (Use a tenant-scoped client/login for the demo tenant, then:)
    # - /api/invoices/aging has at least one non-current bucket populated
    # - /api/reports/inventory-performance items include low_stock and a no-mover
    # - /api/reports/customer-performance items have revenue > 0
    ...
```
> This test is integration-heavy and slow (full seed). Mark it `@pytest.mark.slow` if the repo uses markers, or keep it minimal (assert one report non-empty). Keep it correct, not exhaustive.
- [ ] **Step 4: Verify** `cd backend && PYTHONPATH=. uv run pytest -q` green. Optionally run the real seeder: `PYTHONPATH=. uv run python -m scripts.seed_demo` and spot-check a report endpoint.
- [ ] **Step 5: Commit** `git add backend/scripts/seed_demo.py backend/tests/test_reports_new.py && git commit -m "feat(demo): assign categories + ensure new reports have demo data"`

---

## PHASE F — Documentation

### Task F1: Guides
**Files:** Modify `USER_GUIDE.md`, `WORKFLOW.md`, `CLAUDE.md`

- [ ] **Step 1: `USER_GUIDE.md`** — add: GL now shows Opening/Closing on date filters; Product Categories live under the **Inventory** sidebar section (manage at Product Categories, assign on the product form); on-hand shows on invoice/bill lines and **Settings → Block overselling** prevents negative stock on sales; the four new reports (AR/AP Aging, Product Ledger, Inventory Performance, Customer Performance) — what each shows and how to read it.
- [ ] **Step 2: `WORKFLOW.md`** — add the four reports to the reporting workflow; note the over-sell setting in the sales/inventory flow.
- [ ] **Step 3: `CLAUDE.md`** — document the new report endpoints (`/api/reports/ledger` opening/closing, `/api/reports/product-ledger`, `/inventory-performance`, `/customer-performance`, aging party-ids), the `block_negative_stock` setting + `consume_stock(block_negative=...)`, and the new **Inventory** nav section.
- [ ] **Step 4: Verify + Commit** `grep`-confirm additions; `git add USER_GUIDE.md WORKFLOW.md CLAUDE.md && git commit -m "docs: GL opening/closing, categories, over-sell, new reports"`

### Task F2: README
**Files:** Modify `README.md`

- [ ] **Step 1:** In the feature-highlights section, add: 2-level product categories, the four reports (AR/AP aging, product ledger by store, inventory & customer performance), GL opening/closing balances, and the optional over-sell guard. Keep it scannable and consistent with the current structure.
- [ ] **Step 2: Verify** links still resolve; **Commit** `git add README.md && git commit -m "docs: README feature highlights for reports + inventory + categories"`

---

## Self-Review

**Spec coverage:** A1→items 2,6 ✓ · A2 category usability ✓ · A3→items 9 + Quick-Actions verify (3.2) ✓ · B1/B2→item 1 ✓ · C1/C2/C3→item 8 ✓ · D1→item 3 ✓ · D2→item 7 ✓ · D3→item 4 ✓ · D4→item 5 ✓ · E1→demo data ✓ · F1/F2→docs+README ✓.

**Placeholder scan:** Backend endpoints, the GL fix, and the over-sell guard have complete code. Tests for stock-dependent behaviour (C2, D2, D3, D4, E1) carry `...` only in the **setup helper** that must wire to the repo's real stock-receipt/invoice paths (explicitly flagged each time) — the assertions are concrete. Frontend tasks give exact nav/code snippets + the file to mirror.

**Type/name consistency:** `block_negative_stock` (settings key), `consume_stock(..., block_negative=)`, and the response fields (`opening_balance`/`closing_balance`, `running_qty`, `stock_value`, `units_sold`, `avg_days_to_pay`) are used identically across backend tasks and the frontend pages that read them. New routes (`/api/reports/product-ledger`, `/inventory-performance`, `/customer-performance`, `/aging/*` pages) match between endpoint and page. Sidebar `section:"Inventory"` is introduced in A1 and reused by D2/D3.

**Assumptions to confirm at execution:** the real `POST /api/transactions` and `POST /api/invoices` shapes (tests note this); whether `Invoice.customer_id`/`Bill.vendor_id` exist (D1 falls back to doc drill-down if not); `PaymentReceived`↔`PaymentAllocation` join column names (mirror `subledger.py`).

---

## VERIFICATION (whole plan)
```bash
cd backend && PYTHONPATH=. uv run pytest -q     # full suite green incl. new tests
cd frontend && npm run build                    # compiles incl. new pages
```
**Definition of done:** GL shows opening + dr−cr = closing on date filters; Products & Product Categories appear under an Inventory sidebar section; product descriptions show a pointer + tooltip; on-hand shows on invoice/bill lines and the over-sell setting blocks negative-stock sales when on; the four reports render with data; a fresh demo seed populates all four; guides + README updated.
