# Feature 4: Customer Performance Report Expansion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand Customer Performance with per-customer sales volume, COGS/GP, and a product & category trade summary; and add a per-product period inventory movement (Opening / Purchased / Sold / Closing) report.

**Architecture:** Extend `GET /api/reports/customer-performance` to accept `customer_id`; when supplied it returns a detailed breakdown (monthly volume, COGS/GP, category→product trade) in addition to the existing all-customers ranking. Add `GET /api/reports/product-performance` deriving opening/purchased/sold/closing from `StockMovement`. COGS uses live `Product.avg_cost`.

**Tech Stack:** FastAPI + SQLModel (backend), Next.js 16 / React 19 / TypeScript + react-chartjs-2 (frontend), pytest.

---

### Task 1: Per-customer breakdown on customer-performance

**Files:**
- Modify: `backend/routers/reports.py:1126-1168` (`customer_performance`)
- Test: `backend/tests/test_customer_performance_detail.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_customer_performance_detail.py
"""customer-performance returns a per-customer breakdown when customer_id given."""


def _seed(client, h):
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-01-15",
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 100}],
    })
    client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-02-10",
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 6, "rate": 100}],
    })
    return c, p


def test_breakdown_has_monthly_volume_and_gp(client, admin_headers):
    h = admin_headers
    c, p = _seed(client, h)
    data = client.get(
        f"/api/reports/customer-performance?customer_id={c['id']}"
        f"&start=2026-01-01&end=2026-12-31", headers=h,
    ).json()
    d = data["detail"]
    assert d is not None
    # two months of activity
    months = {m["month"]: m for m in d["monthly"]}
    assert months["2026-01"]["revenue"] == 400
    assert months["2026-02"]["revenue"] == 600
    # GP = revenue - COGS(qty * avg_cost); avg_cost may be 0 if no purchase posted
    assert d["totals"]["revenue"] == 1000
    assert "cogs" in d["totals"] and "gp" in d["totals"]
    # product/category trade summary present
    prod_row = next(r for r in d["products"] if r["product_id"] == p["id"])
    assert prod_row["qty"] == 10
    assert prod_row["revenue"] == 1000


def test_ranking_still_returned_without_customer_id(client, admin_headers):
    h = admin_headers
    _seed(client, h)
    data = client.get("/api/reports/customer-performance", headers=h).json()
    assert "items" in data and len(data["items"]) >= 1
    assert data.get("detail") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_customer_performance_detail.py -v`
Expected: FAIL — `detail` key missing / `customer_id` param unsupported.

- [ ] **Step 3: Extend the endpoint signature and return a `detail` block**

In `backend/routers/reports.py`, change the signature of `customer_performance` to add `customer_id: Optional[int] = None`. Keep the existing ranking logic; after building `out`, add the detail computation and return `{"items": out, "detail": detail}` (detail is `None` when `customer_id` is omitted).

```python
    detail = None
    if customer_id is not None:
        from models import InvoiceLine, Product
        dq = select(Invoice).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.customer_id == customer_id,
        )
        if start:
            dq = dq.where(Invoice.issue_date >= start)
        if end:
            dq = dq.where(Invoice.issue_date <= end)
        cust_invoices = session.exec(dq).all()
        inv_ids = [i.id for i in cust_invoices]
        # avg_cost lookup
        avg_cost = {p.id: D(p.avg_cost) for p in session.exec(
            select(Product).where(Product.tenant_id == user.tenant_id)
        ).all()}
        monthly: dict = {}
        products: dict = {}
        for inv in cust_invoices:
            mk = inv.issue_date[:7]  # YYYY-MM
            m = monthly.setdefault(mk, {"month": mk, "revenue": ZERO, "units": ZERO})
            m["revenue"] += D(inv.total)
        lines = []
        if inv_ids:
            lines = session.exec(
                select(InvoiceLine).where(InvoiceLine.invoice_id.in_(inv_ids))
            ).all()
        tot_rev = tot_cogs = ZERO
        inv_date = {i.id: i.issue_date for i in cust_invoices}
        for ln in lines:
            line_rev = D(ln.amount)
            line_cogs = D(ln.qty) * avg_cost.get(ln.product_id, ZERO)
            tot_rev += line_rev
            tot_cogs += line_cogs
            mk = inv_date[ln.invoice_id][:7]
            monthly[mk]["units"] += D(ln.qty)
            pr = products.setdefault(ln.product_id, {
                "product_id": ln.product_id, "qty": ZERO,
                "revenue": ZERO, "cogs": ZERO,
            })
            pr["qty"] += D(ln.qty)
            pr["revenue"] += line_rev
            pr["cogs"] += line_cogs
        # attach product names + category labels
        from models import Product as _P, ProductCategory
        cats = {c.id: c for c in session.exec(
            select(ProductCategory).where(ProductCategory.tenant_id == user.tenant_id)
        ).all()}
        def cat_label(cid):
            c = cats.get(cid)
            if not c:
                return "Uncategorized"
            if c.parent_id is None:
                return c.name
            par = cats.get(c.parent_id)
            return f"{par.name} › {c.name}" if par else c.name
        prod_rows = []
        for pid, pr in products.items():
            p = session.get(_P, pid) if pid else None
            pr["gp"] = money(pr["revenue"] - pr["cogs"])
            pr["name"] = p.name if p else "—"
            pr["category"] = cat_label(p.category_id) if p else "Uncategorized"
            prod_rows.append(pr)
        prod_rows.sort(key=lambda r: r["revenue"], reverse=True)
        detail = {
            "monthly": [monthly[k] for k in sorted(monthly)],
            "products": prod_rows,
            "totals": {
                "revenue": money(tot_rev),
                "cogs": money(tot_cogs),
                "gp": money(tot_rev - tot_cogs),
                "gp_pct": float(round((tot_rev - tot_cogs) / tot_rev * 100, 1)) if tot_rev else 0.0,
            },
        }
    return {"items": out, "detail": detail}
```

(Confirm `money`, `D`, `ZERO`, `select`, `Optional` are already imported in `reports.py`; they are used throughout.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_customer_performance_detail.py -v`
Expected: PASS (both).

- [ ] **Step 5: Run the existing reports suite for regressions**

Run: `cd backend && uv run pytest tests/test_reports_new.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_customer_performance_detail.py
git commit -m "feat(reports): per-customer sales volume, COGS/GP, product+category trade"
```

---

### Task 2: `GET /api/reports/product-performance` (period inventory movement)

**Files:**
- Modify: `backend/routers/reports.py` (add endpoint)
- Test: `backend/tests/test_product_performance.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_product_performance.py
"""Opening + Purchased - Sold = Closing, from StockMovement."""
from sqlmodel import Session
import db as _db_module
from models import StockMovement, Product
from datetime import datetime


def _mv(tid, pid, direction, qty, when, unit_cost=0):
    with Session(_db_module.engine) as s:
        s.add(StockMovement(tenant_id=tid, product_id=pid, direction=direction,
                            qty=qty, unit_cost=unit_cost,
                            occurred_at=datetime.fromisoformat(when)))
        s.commit()


def test_opening_purchased_sold_closing(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "Nut", "product_type": "stock"}).json()
    with Session(_db_module.engine) as s:
        tid = s.get(Product, p["id"]).tenant_id
    _mv(tid, p["id"], "RECEIPT", 20, "2025-12-01T10:00", unit_cost=5)   # before period → opening
    _mv(tid, p["id"], "RECEIPT", 10, "2026-01-10T10:00", unit_cost=5)   # purchased in period
    _mv(tid, p["id"], "SHIPMENT", 6, "2026-01-15T10:00")                # sold in period
    data = client.get(
        "/api/reports/product-performance?start=2026-01-01&end=2026-01-31",
        headers=h,
    ).json()
    row = next(r for r in data["items"] if r["product_id"] == p["id"])
    assert row["opening_qty"] == 20
    assert row["purchased_qty"] == 10
    assert row["sold_qty"] == 6
    assert row["closing_qty"] == 24    # 20 + 10 - 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_product_performance.py -v`
Expected: FAIL — endpoint missing.

- [ ] **Step 3: Implement the endpoint**

Add to `backend/routers/reports.py`:

```python
@router.get("/product-performance")
def product_performance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    """Per-product period movement: opening/purchased/sold(net)/closing with
    values at avg_cost, plus GP (sales revenue - COGS) for the window."""
    from models import StockMovement, Product, Invoice, InvoiceLine

    IN_DIRS = ("RECEIPT", "COMPLETION", "ADJUSTMENT")
    OUT_DIRS = ("SHIPMENT", "DELIVERY", "ISSUE")

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
            )
        ).all()
        opening = purchased = sold = ZERO
        for m in mv:
            d = m.occurred_at.date().isoformat()
            signed = D(m.qty) if m.direction in IN_DIRS else (-D(m.qty) if m.direction in OUT_DIRS else ZERO)
            if start and d < start:
                opening += signed
            elif (not start or d >= start) and (not end or d <= end):
                if m.direction in IN_DIRS:
                    purchased += D(m.qty)
                elif m.direction in OUT_DIRS:
                    sold += D(m.qty)
        avg = D(p.avg_cost)
        closing = opening + purchased - sold
        # sales revenue for the product in window
        rq = (select(func.coalesce(func.sum(InvoiceLine.amount), 0))
              .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
              .where(Invoice.tenant_id == user.tenant_id,
                     InvoiceLine.product_id == p.id))
        if start:
            rq = rq.where(Invoice.issue_date >= start)
        if end:
            rq = rq.where(Invoice.issue_date <= end)
        revenue = D(session.exec(rq).first() or 0)
        cogs = sold * avg
        out.append({
            "product_id": p.id, "name": p.name, "code": p.code,
            "opening_qty": opening, "opening_value": money(opening * avg),
            "purchased_qty": purchased,
            "sold_qty": sold,
            "closing_qty": closing, "closing_value": money(closing * avg),
            "gp": money(revenue - cogs), "revenue": money(revenue),
        })
    out.sort(key=lambda r: r["closing_value"], reverse=True)
    return {"items": out}
```

(Confirm `func` is imported in `reports.py`; it is used elsewhere.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_product_performance.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_product_performance.py
git commit -m "feat(reports): product-performance period movement (opening/purchased/sold/closing/GP)"
```

---

### Task 3: Frontend — customer selector + breakdown UI

**Files:**
- Modify: `frontend/src/app/(dashboard)/customer-performance/page.tsx`

- [ ] **Step 1: Read Next.js 16 guidance**

Run: `ls frontend/node_modules/next/dist/docs/`; heed `frontend/AGENTS.md`.

- [ ] **Step 2: Add a customer dropdown + date range**

Add a required customer `<select>` (from `/api/customers?limit=500`) and start/end date inputs. When a customer is selected, call `/api/reports/customer-performance?customer_id=&start=&end=` and render the `detail` block; with no customer selected keep the existing all-customers ranking table.

- [ ] **Step 3: Render the three detail sections**

- **Monthly Sales Volume** — a small table or `react-chartjs-2` bar chart from `detail.monthly` (revenue + units).
- **COGS & GP cards** — `detail.totals` (revenue, cogs, gp, gp_pct).
- **Product & Category trade** — table from `detail.products` grouped/sorted, columns: Category, Product, Qty, Revenue, COGS, GP.

- [ ] **Step 4: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(dashboard)/customer-performance/page.tsx"
git commit -m "feat(reports): customer-performance detail UI (volume, COGS/GP, trade summary)"
```

---

### Task 4: Frontend — Product Performance columns

**Files:**
- Modify: `frontend/src/app/(dashboard)/inventory/performance/page.tsx`

- [ ] **Step 1: Add a date range and switch to product-performance data**

Add start/end inputs; fetch `/api/reports/product-performance?start=&end=` and render columns: Product, Opening Qty/Value, Qty Purchased, Qty Sold (Net), GP, Closing Qty/Value. Keep product names linking to the ledger (existing behavior).

- [ ] **Step 2: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(dashboard)/inventory/performance/page.tsx"
git commit -m "feat(inventory): product-performance period columns (opening/purchased/sold/closing/GP)"
```

---

## Self-Review Notes
- Spec Feature 4 fully covered: periodical sales volume (Task 1 `monthly`), COGS/GP (Task 1 `totals`), product+category trade (Task 1 `products`), product performance O/stock·purchased·sold·GP·C/stock (Task 2).
- COGS uses live `avg_cost` per the locked decision.
- Back-compat: ranking still returned when `customer_id` omitted (Task 1 Step 3, test in Step 1).
- `inventory/performance` page path assumed from CLAUDE.md ("/inventory/performance"); confirm exact file during execution.
