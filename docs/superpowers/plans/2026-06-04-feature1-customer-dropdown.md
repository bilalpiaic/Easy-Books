# Feature 1: Compulsory Customer Dropdown — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the free-text customer name on Record Payment with a required dropdown bound to `customer_id`, resolving the canonical name server-side.

**Architecture:** `PaymentReceivedCreate` gains an optional `customer_id`; the create handler resolves the canonical `customer_name` from the `Customer` row (tenant-scoped) when an id is given. The frontend swaps the text input for a required `<select>` populated from `GET /api/customers`.

**Tech Stack:** FastAPI + SQLModel (backend), Next.js 16 / React 19 / TypeScript (frontend), pytest.

---

### Task 1: Backend accepts and resolves `customer_id` on payment create

**Files:**
- Modify: `backend/routers/payments.py:35-44` (`PaymentReceivedCreate`)
- Modify: `backend/routers/payments.py:121-175` (`create_payment_received`)
- Test: `backend/tests/test_payments_customer_id.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_payments_customer_id.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_payments_customer_id.py -v`
Expected: FAIL — `customer_id` is ignored / name not resolved.

- [ ] **Step 3: Add `customer_id` to the schema**

In `backend/routers/payments.py`, add to `PaymentReceivedCreate` (next to `customer_name`):

```python
    customer_id: Optional[int] = None
```

- [ ] **Step 4: Resolve the name in `create_payment_received`**

In `create_payment_received`, immediately after `cname = body.customer_name` (~line 126) insert:

```python
    if body.customer_id is not None:
        from models import Customer
        cust = session.exec(
            select(Customer).where(
                Customer.id == body.customer_id,
                Customer.tenant_id == user.tenant_id,
            )
        ).first()
        if not cust:
            raise HTTPException(404, "Customer not found")
        cname = cust.name
```

(Confirm `select`, `HTTPException`, and `Optional` are already imported at the top of the file; they are used elsewhere in this module.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_payments_customer_id.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Run the full payments suite for regressions**

Run: `cd backend && uv run pytest -k payment -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/payments.py backend/tests/test_payments_customer_id.py
git commit -m "feat(payments): accept customer_id and resolve canonical name"
```

---

### Task 2: Frontend Record-Payment uses a required customer dropdown

**Files:**
- Modify: `frontend/src/app/(dashboard)/payments-received/page.tsx`

- [ ] **Step 1: Read the Next.js 16 form/select guidance**

Run: `ls frontend/node_modules/next/dist/docs/` and skim the relevant client-component note. Heed `frontend/AGENTS.md`.

- [ ] **Step 2: Add customer state and fetch the list**

Near the other `useState` hooks in `payments-received/page.tsx`, add:

```tsx
const [customers, setCustomers] = useState<{ id: number; name: string }[]>([])
```

Add a fetch (alongside the existing initial `useEffect` that loads invoices):

```tsx
useEffect(() => {
  apiFetch<{ items: { id: number; name: string }[] }>('/api/customers?limit=500')
    .then(d => setCustomers(d.items))
    .catch(() => {})
}, [])
```

Add `customer_id: ''` to the `form` initial state object (line ~53).

- [ ] **Step 3: Replace the free-text input with a required select**

Replace the Customer Name `<input>` block (around line 285-287) with:

```tsx
<label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Customer *</label>
<select
  required
  value={form.customer_id}
  onChange={e => setForm(p => ({ ...p, customer_id: e.target.value }))}
  className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
>
  <option value="">— Select customer —</option>
  {customers.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
</select>
```

- [ ] **Step 4: Send `customer_id` and gate the submit button**

In the submit handler payload (around line 137), replace `customer_name: form.customer_name || null` with:

```tsx
customer_id: form.customer_id ? Number(form.customer_id) : null,
```

On the "Record Payment" button, add `disabled={!form.customer_id || submitting}` (combine with any existing disabled condition).

- [ ] **Step 5: Verify the build compiles**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 6: Manual smoke check**

Start the app (`./dev.sh` or backend `python main.py` + `npm run dev`). Open Record Payment: the customer field is a dropdown, the button is disabled until a customer is chosen, and a recorded payment shows the chosen name in the list.

- [ ] **Step 7: Commit**

```bash
git add "frontend/src/app/(dashboard)/payments-received/page.tsx"
git commit -m "feat(payments): require customer dropdown on Record Payment"
```

---

### Task 3: Audit other free-text customer/vendor entry points

**Files:**
- Inspect: `frontend/src/app/(dashboard)/invoices/[id]/page.tsx`, `frontend/src/app/(dashboard)/bills/[id]/page.tsx`, `bill-payments/page.tsx`

- [ ] **Step 1: Grep for free-text customer/vendor inputs**

Run: `grep -rn "customer_name\|vendor_name" frontend/src/app | grep -i "input"`
For each plain text input still used for selecting an existing party, convert it to a dropdown using the same pattern as Task 2 (customers from `/api/customers`, vendors from `/api/vendors`). Leave create-new-party flows untouched.

- [ ] **Step 2: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src
git commit -m "refactor(ui): use party dropdowns for existing customer/vendor selection"
```

---

## Self-Review Notes
- Spec Feature 1 fully covered: backend resolves id→name (Task 1), required dropdown (Task 2), consistency pass (Task 3).
- Back-compat preserved: `customer_name` still stored; `customer_id` optional on the schema so existing callers that send only a name keep working.
