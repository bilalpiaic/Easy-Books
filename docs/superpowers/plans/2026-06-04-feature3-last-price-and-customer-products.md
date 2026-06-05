# Feature 3: Last Sale Price + Customer's Products Module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the last price a product was sold to / bought from a party while invoicing/billing, and add a "Products" module on the customer that lists every product sold to them with its last price.

**Architecture:** Two read-only endpoints. `GET /api/products/{id}/last-price` returns the most recent line rate for the product scoped to a party with a global fallback. `GET /api/customers/{id}/products` aggregates sold products. The shared `LineItemsTable` gains `customerId`/`priceKind` props and shows an inline hint with a "Use" button; a new customer sub-page renders the products table.

**Tech Stack:** FastAPI + SQLModel (backend), Next.js 16 / React 19 / TypeScript (frontend), pytest.

---

### Task 1: `GET /api/products/{id}/last-price` endpoint

**Files:**
- Modify: `backend/routers/products.py` (add endpoint)
- Test: `backend/tests/test_product_last_price.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_product_last_price.py
"""Last-price lookup: per-customer first, global fallback."""


def _make_invoice(client, h, customer_id, product_id, rate, date):
    return client.post("/api/invoices", headers=h, json={
        "customer_id": customer_id, "issue_date": date,
        "lines": [{"product_id": product_id, "description": "x",
                   "qty": 1, "rate": rate}],
    })


def test_last_price_prefers_this_customer(client, admin_headers):
    h = admin_headers
    a = client.post("/api/customers", headers=h, json={"name": "A"}).json()
    b = client.post("/api/customers", headers=h, json={"name": "B"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Widget", "product_type": "stock"}).json()
    _make_invoice(client, h, a["id"], p["id"], 100, "2026-01-01")
    _make_invoice(client, h, b["id"], p["id"], 250, "2026-02-01")  # later, other cust
    r = client.get(
        f"/api/products/{p['id']}/last-price?customer_id={a['id']}&kind=sale",
        headers=h,
    ).json()
    assert r["rate"] == 100
    assert r["scope"] == "customer"


def test_last_price_global_fallback(client, admin_headers):
    h = admin_headers
    a = client.post("/api/customers", headers=h, json={"name": "A"}).json()
    b = client.post("/api/customers", headers=h, json={"name": "B"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Gadget", "product_type": "stock"}).json()
    _make_invoice(client, h, b["id"], p["id"], 77, "2026-03-01")
    r = client.get(
        f"/api/products/{p['id']}/last-price?customer_id={a['id']}&kind=sale",
        headers=h,
    ).json()
    assert r["rate"] == 77
    assert r["scope"] == "global"


def test_last_price_none_when_never_sold(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "New", "product_type": "stock"}).json()
    r = client.get(f"/api/products/{p['id']}/last-price?kind=sale", headers=h).json()
    assert r["rate"] is None
    assert r["scope"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_product_last_price.py -v`
Expected: FAIL — 404, endpoint missing.

- [ ] **Step 3: Implement the endpoint**

Add to `backend/routers/products.py` (near the other `@router.get` handlers). Confirm imports `select`, `Optional` exist.

```python
@router.get("/{product_id}/last-price")
def product_last_price(
    session: SessionDep, user: CurrentUserDep, product_id: int,
    customer_id: Optional[int] = None, kind: str = "sale",
):
    """Most recent line rate for a product, scoped to a party with global
    fallback. kind='sale' uses invoices/customers, 'purchase' uses bills/vendors.
    Returns {rate, date, scope: 'customer'|'global'|None}."""
    from models import Invoice, InvoiceLine, Bill, BillLine

    if kind == "purchase":
        Line, Doc, party_col, date_col = BillLine, Bill, Bill.customer_id, Bill.issue_date
        line_doc_fk = BillLine.bill_id
    else:
        Line, Doc, party_col, date_col = InvoiceLine, Invoice, Invoice.customer_id, Invoice.issue_date
        line_doc_fk = InvoiceLine.invoice_id

    def latest(scoped: bool):
        q = (
            select(Line.rate, date_col)
            .join(Doc, Doc.id == line_doc_fk)
            .where(Doc.tenant_id == user.tenant_id, Line.product_id == product_id)
            .order_by(date_col.desc(), Doc.id.desc())
        )
        if scoped:
            q = q.where(party_col == customer_id)
        return session.exec(q).first()

    if customer_id is not None:
        row = latest(scoped=True)
        if row:
            return {"rate": float(row[0]), "date": row[1], "scope": "customer"}
    row = latest(scoped=False)
    if row:
        return {"rate": float(row[0]), "date": row[1], "scope": "global"}
    return {"rate": None, "date": None, "scope": None}
```

> NOTE: `Bill.customer_id` — confirm bills store the vendor on `customer_id` (model line 278 shows `customer_name`; check the bill's party FK column name and use it). If bills use `vendor_id`, substitute it for `party_col`/the purchase branch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_product_last_price.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/products.py backend/tests/test_product_last_price.py
git commit -m "feat(products): last-price lookup (per-customer with global fallback)"
```

---

### Task 2: `GET /api/customers/{id}/products` endpoint

**Files:**
- Modify: `backend/routers/customers.py` (add endpoint)
- Test: `backend/tests/test_customer_products.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_customer_products.py
"""Customer's-products module: every product sold to a customer + last price."""


def test_customer_products_aggregates(client, admin_headers):
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    for rate, date, qty in [(10, "2026-01-01", 5), (12, "2026-02-01", 3)]:
        client.post("/api/invoices", headers=h, json={
            "customer_id": c["id"], "issue_date": date,
            "lines": [{"product_id": p["id"], "description": "Bolt",
                       "qty": qty, "rate": rate}],
        })
    data = client.get(f"/api/customers/{c['id']}/products", headers=h).json()
    row = next(r for r in data["items"] if r["product_id"] == p["id"])
    assert row["last_rate"] == 12          # most recent
    assert row["last_date"] == "2026-02-01"
    assert row["total_qty"] == 8           # 5 + 3
    assert row["invoice_count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_customer_products.py -v`
Expected: FAIL — endpoint missing.

- [ ] **Step 3: Implement the endpoint**

Add to `backend/routers/customers.py`:

```python
@router.get("/{customer_id}/products")
def customer_products(session: SessionDep, user: CurrentUserDep, customer_id: int):
    """Every product ever sold to this customer with last price/date, total qty,
    and invoice count."""
    from models import Invoice, InvoiceLine, Product

    rows = session.exec(
        select(InvoiceLine, Invoice.issue_date)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(Invoice.tenant_id == user.tenant_id,
               Invoice.customer_id == customer_id,
               InvoiceLine.product_id.is_not(None))
        .order_by(Invoice.issue_date.asc(), Invoice.id.asc())
    ).all()

    agg: dict = {}
    for line, issue_date in rows:
        a = agg.setdefault(line.product_id, {
            "product_id": line.product_id, "total_qty": 0.0,
            "invoice_count": 0, "last_rate": None, "last_date": None,
        })
        a["total_qty"] += float(line.qty)
        a["invoice_count"] += 1
        a["last_rate"] = float(line.rate)     # rows ascending → last wins
        a["last_date"] = issue_date

    prod_ids = list(agg.keys())
    names = {}
    if prod_ids:
        for p in session.exec(
            select(Product).where(Product.id.in_(prod_ids),
                                  Product.tenant_id == user.tenant_id)
        ).all():
            names[p.id] = {"name": p.name, "code": p.code}
    items = []
    for pid, a in agg.items():
        a.update(names.get(pid, {"name": "—", "code": None}))
        items.append(a)
    items.sort(key=lambda r: r["total_qty"], reverse=True)
    return {"items": items}
```

(Confirm `CurrentUserDep` and `select` are imported in `customers.py`; add `from auth import CurrentUserDep` style import matching the file if missing.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_customer_products.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/customers.py backend/tests/test_customer_products.py
git commit -m "feat(customers): customer-products module endpoint"
```

---

### Task 3: Last-price hint in the shared line editor

**Files:**
- Modify: `frontend/src/components/LineItemsTable.tsx`
- Modify: `frontend/src/app/(dashboard)/invoices/[id]/page.tsx` and `bills/[id]/page.tsx` (pass new props)

- [ ] **Step 1: Read Next.js 16 guidance**

Run: `ls frontend/node_modules/next/dist/docs/`; heed `frontend/AGENTS.md`.

- [ ] **Step 2: Add props to `LineItemsTable`**

In the `Props` interface (line ~34) add:

```tsx
  customerId?: number | null
  priceKind?: 'sale' | 'purchase'
```

Add to the destructured params (line ~53): `customerId = null, priceKind = 'sale'`.

Add hint state at the top of the component body:

```tsx
const [hints, setHints] = useState<Record<number, { rate: number; date: string; scope: string } | null>>({})
```

- [ ] **Step 3: Fetch the last price on product select**

In `onProductSelect` (line ~70), after the product is set, fetch the hint for that row index:

```tsx
if (prod) {
  const qs = new URLSearchParams({ kind: priceKind })
  if (customerId) qs.set('customer_id', String(customerId))
  apiFetch<{ rate: number | null; date: string | null; scope: string | null }>(
    `/api/products/${prod.id}/last-price?${qs}`
  ).then(r => setHints(h => ({ ...h, [idx]: r.rate != null ? { rate: r.rate, date: r.date!, scope: r.scope! } : null })))
   .catch(() => {})
}
```

(Confirm `apiFetch` and `useState` are imported at top of the file.)

- [ ] **Step 4: Render the hint with a "Use" button**

Below the rate input cell (line ~195), render when a hint exists for the row:

```tsx
{hints[idx] && hints[idx]!.rate !== line.rate && (
  <button type="button"
    onClick={() => update(idx, { rate: hints[idx]!.rate, amount: Math.round(line.qty * hints[idx]!.rate * 100) / 100 })}
    className="block mt-1 text-[10px] text-[#b8943f] hover:underline"
    title={`Last ${priceKind === 'purchase' ? 'bought' : 'sold'} (${hints[idx]!.scope}) on ${hints[idx]!.date}`}
  >
    Last: {fmt(hints[idx]!.rate)} — Use
  </button>
)}
```

- [ ] **Step 5: Pass the props from invoice/bill editors**

In `invoices/[id]/page.tsx` where `<LineItemsTable ... />` is rendered, pass `customerId={form.customer_id ? Number(form.customer_id) : null}` and `priceKind="sale"`. In `bills/[id]/page.tsx` pass the vendor id and `priceKind="purchase"`.

- [ ] **Step 6: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 7: Manual smoke check**

On a new invoice for a customer who has bought before, pick a product → the "Last: ₨X — Use" hint appears; clicking fills the rate; the hint hides once the rate matches.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/LineItemsTable.tsx "frontend/src/app/(dashboard)/invoices/[id]/page.tsx" "frontend/src/app/(dashboard)/bills/[id]/page.tsx"
git commit -m "feat(lines): inline last-price hint with one-click Use"
```

---

### Task 4: Customer's Products page

**Files:**
- Create: `frontend/src/app/(dashboard)/customers/[id]/products/page.tsx`
- Modify: `frontend/src/app/(dashboard)/customers/page.tsx` (link to the new page)

- [ ] **Step 1: Create the page**

Mirror the structure of `customers/[id]/ledger/page.tsx` (client component, `apiFetch`, `useFmt`). Render a table from `GET /api/customers/{id}/products` with columns: Product, Code, Last Price, Last Date, Total Qty, Invoices. Each product name links to `/products/ledger?product=<product_id>`.

```tsx
'use client'
import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'

interface Row { product_id: number; name: string; code: string | null; last_rate: number; last_date: string; total_qty: number; invoice_count: number }

export default function CustomerProducts({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[]>([])
  useEffect(() => {
    apiFetch<{ items: Row[] }>(`/api/customers/${id}/products`).then(d => setRows(d.items)).catch(() => {})
  }, [id])
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-serif font-medium">Products Sold</h1>
      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Product</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/60">Last Price</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/60">Last Date</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/60">Total Qty</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/60">Invoices</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {rows.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-10 text-center text-black/50">No products sold yet.</td></tr>
            ) : rows.map(r => (
              <tr key={r.product_id} className="hover:bg-[#f6f3ee]/50">
                <td className="px-6 py-3"><Link href={`/products/ledger?product=${r.product_id}`} className="hover:text-[#b8943f] hover:underline">{r.name}</Link>{r.code && <span className="ml-2 font-mono text-xs text-[#b8943f]">{r.code}</span>}</td>
                <td className="px-6 py-3 text-right font-mono">{fmt(r.last_rate)}</td>
                <td className="px-6 py-3 text-right text-black/60">{r.last_date}</td>
                <td className="px-6 py-3 text-right font-mono">{r.total_qty.toLocaleString()}</td>
                <td className="px-6 py-3 text-right">{r.invoice_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

> Confirm the `params: Promise<...>` + `use(params)` pattern against `customers/[id]/ledger/page.tsx` — match whatever that page does (Next.js 16 async params).

- [ ] **Step 2: Link from the customers list**

In `customers/page.tsx`, add a "Products" link per row alongside the existing ledger/statement links, pointing to `/customers/${c.id}/products`.

- [ ] **Step 3: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 4: Manual smoke check**

Open a customer → Products: shows sold products with last price/date/qty; product links open the ledger filtered to that product.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(dashboard)/customers"
git commit -m "feat(customers): Products Sold module page"
```

---

## Self-Review Notes
- Spec Feature 3 fully covered: per-customer-with-global-fallback last price (Task 1), customer products aggregation (Task 2), inline hint + Use (Task 3), customer products page (Task 4).
- Open verification flagged inline: bill party FK name (Task 1 Step 3 note) and the Next.js 16 async-params pattern (Task 4 Step 1 note) must be confirmed against existing code during execution.
