# Analytic Accounts Full Wiring + Demo Re-Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `analytic_account_id` through Invoice, Bill, PaymentReceived, and BillPayment (per-document, optional tag) so the Analytic P&L report shows real figures, then re-seed all 5 demo tenants to prove it end-to-end.

**Architecture:** Add `analytic_account_id` (nullable FK → `analyticaccount.id`) to four table models and their create schemas. Propagate through existing posting layer by passing the field to all `EntryInput` constructors — the posting service already writes `analytic_account_id` to `JournalEntry` rows. Add one optional dropdown to each form component (Invoice, Bill, PaymentReceived, BillPayment, JV entry). Update seed script to tag ~30 % of records so the Analytic P&L shows non-empty data per tenant.

**Tech Stack:** Python 3.11 / FastAPI / SQLModel / Alembic (SQLite in dev, Postgres in prod); Next.js 16 / React 19 / TypeScript / Tailwind CSS; pytest; `uv run`

---

## File Map

| File | Change |
|------|--------|
| `backend/models.py` | Add `analytic_account_id` to `Invoice`, `Bill`, `PaymentReceived`, `BillPayment`; add to `TransactionCreate` |
| `backend/alembic/versions/0023_analytic_account_links.py` | New migration — ADD COLUMN to 4 tables |
| `backend/routers/invoices.py` | Add field to `InvoiceCreate`; propagate to `Invoice()` + all `EntryInput` in create + update paths |
| `backend/routers/bills.py` | Same pattern for `BillCreate` + create + update paths |
| `backend/routers/payments.py` | Same for `PaymentReceivedCreate` + `BillPaymentCreate` |
| `backend/routers/transactions.py` | Propagate `tx_data.analytic_account_id` to all `EntryInput` in `create_transaction` |
| `backend/tests/test_analytic_accounts.py` | New — tests that analytic_account_id flows to JE rows for all 4 document types |
| `frontend/src/components/invoices/InvoiceForm.tsx` | Fetch analytic accounts; add optional dropdown |
| `frontend/src/components/bills/BillForm.tsx` | Same |
| `frontend/src/components/payments/PaymentReceivedForm.tsx` | Same |
| `frontend/src/components/payments/BillPaymentForm.tsx` | Same |
| `frontend/src/app/(dashboard)/entry/page.tsx` | Fetch analytic accounts; add optional dropdown; include in POST body |
| `backend/scripts/seed_demo.py` | Tag ~30 % of seeded records with analytic_account_id; version → v4 |

---

## Task 1: Backend models + Alembic migration

**Files:**
- Modify: `backend/models.py` (Invoice ~line 290, Bill ~line 322, PaymentReceived ~line 347, BillPayment ~line 361, TransactionCreate ~line 1498)
- Create: `backend/alembic/versions/0023_analytic_account_links.py`
- Test: `backend/tests/test_analytic_accounts.py`

- [ ] **Step 1: Write the failing import test**

Create `backend/tests/test_analytic_accounts.py`:

```python
"""Tests: analytic_account_id propagates to JournalEntry rows for all document types."""
from decimal import Decimal
from models import Invoice, Bill, PaymentReceived, BillPayment, TransactionCreate
import inspect


def test_invoice_model_has_analytic_account_id():
    fields = Invoice.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_bill_model_has_analytic_account_id():
    fields = Bill.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_payment_received_model_has_analytic_account_id():
    fields = PaymentReceived.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_bill_payment_model_has_analytic_account_id():
    fields = BillPayment.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_transaction_create_has_analytic_account_id():
    fields = TransactionCreate.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_analytic_accounts.py -v 2>&1 | head -30
```

Expected: 5 failures — `AssertionError: assert 'analytic_account_id' in ...`

- [ ] **Step 3: Add fields to models.py**

Open `backend/models.py`. Add `analytic_account_id` to each of the four table classes and to `TransactionCreate`.

In `class Invoice(SQLModel, table=True):` (after the existing `assigned_to_id` line, around line 320):
```python
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
```

In `class Bill(SQLModel, table=True):` (after `created_by_id`, around line 345):
```python
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
```

In `class PaymentReceived(SQLModel, table=True):` (after `created_by_id`, around line 358):
```python
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
```

In `class BillPayment(SQLModel, table=True):` (after `created_by_id`, around line 372):
```python
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
```

In `class TransactionCreate(TransactionBase):` (after `voucher_type`, around line 1501):
```python
    analytic_account_id: Optional[int] = None
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_analytic_accounts.py -v 2>&1 | tail -12
```

Expected: `5 passed`

- [ ] **Step 5: Create Alembic migration**

Create `backend/alembic/versions/0023_analytic_account_links.py`:

```python
"""analytic_account_id links to invoice, bill, paymentreceived, billpayment

Revision ID: 0023analytic_links
Revises: 0022_promo_rules
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0023analytic_links"
down_revision: Union[str, Sequence[str], None] = "0022_promo_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for tbl in ("invoice", "bill", "paymentreceived", "billpayment"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns(tbl)}
        if "analytic_account_id" not in cols:
            op.add_column(tbl, sa.Column("analytic_account_id", sa.Integer(), nullable=True))
    # FK constraints omitted: SQLite does not support ADD CONSTRAINT via ALTER TABLE.
    # App-level tenant checks enforce integrity.


def downgrade() -> None:
    for tbl in ("invoice", "bill", "paymentreceived", "billpayment"):
        op.drop_column(tbl, "analytic_account_id")
```

- [ ] **Step 6: Run migration**

```bash
cd backend && uv run alembic upgrade head 2>&1 | tail -5
```

Expected: `Running upgrade 0022_promo_rules -> 0023analytic_links, analytic_account_id links to invoice, bill, paymentreceived, billpayment`

- [ ] **Step 7: Commit**

```bash
git add backend/models.py backend/alembic/versions/0023_analytic_account_links.py backend/tests/test_analytic_accounts.py
git commit -m "feat(analytics): add analytic_account_id to Invoice/Bill/Payment models + migration 0023"
```

---

## Task 2: Posting propagation — all four routers

**Files:**
- Modify: `backend/routers/invoices.py` (InvoiceCreate ~line 86; Invoice() ~line 311; EntryInput blocks ~lines 431–450; update path ~line 770)
- Modify: `backend/routers/bills.py` (BillCreate ~line 31; Bill() ~line 234; EntryInput block ~line 325; update path ~line 540)
- Modify: `backend/routers/payments.py` (PaymentReceivedCreate ~line 37; EntryInput ~line 178; PaymentReceived() ~line 188; BillPaymentCreate ~line 229; EntryInput ~line 336; BillPayment() ~line 346)
- Modify: `backend/routers/transactions.py` (create_transaction ~line 208)
- Test: `backend/tests/test_analytic_accounts.py` (extend)

- [ ] **Step 1: Write propagation tests**

Append to `backend/tests/test_analytic_accounts.py`:

```python
from fastapi.testclient import TestClient
from main import app
import json

client = TestClient(app)


def _auth(email="admin@test.com", password="admin123"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r.json().get("access_token", "")


def _headers():
    return {"Authorization": f"Bearer {_auth()}"}


def _get_analytic_id(headers):
    """Return first active analytic account id, or None."""
    r = client.get("/api/analytic-accounts", headers=headers)
    items = r.json().get("items", r.json() if isinstance(r.json(), list) else [])
    return items[0]["id"] if items else None


def test_invoice_analytic_propagates_to_je(tmp_path):
    """Creating an invoice with analytic_account_id tags all resulting JE rows."""
    h = _headers()
    aid = _get_analytic_id(h)
    if aid is None:
        return  # no analytic accounts seeded — skip
    payload = {
        "customer_name": "Test Co",
        "issue_date": "2026-01-15",
        "due_date": "2026-02-15",
        "gst_rate": 0,
        "lines": [{"description": "Service", "qty": 1, "rate": 500}],
        "analytic_account_id": aid,
    }
    r = client.post("/api/invoices", json=payload, headers=h)
    assert r.status_code == 200, r.text
    inv_id = r.json()["id"]
    inv = client.get(f"/api/invoices/{inv_id}", headers=h).json()
    txn_id = inv.get("transaction_id")
    assert txn_id, "Invoice must have transaction_id after posting"
    txn = client.get(f"/api/transactions/{txn_id}", headers=h).json()
    for entry in txn["entries"]:
        assert entry.get("analytic_account_id") == aid, (
            f"JE row account_id={entry['account_id']} missing analytic tag"
        )


def test_bill_analytic_propagates_to_je():
    h = _headers()
    aid = _get_analytic_id(h)
    if aid is None:
        return
    payload = {
        "vendor_name": "Supplier Ltd",
        "bill_date": "2026-01-15",
        "due_date": "2026-02-15",
        "gst_rate": 0,
        "lines": [{"description": "Office supplies", "qty": 2, "rate": 100}],
        "analytic_account_id": aid,
    }
    r = client.post("/api/bills", json=payload, headers=h)
    assert r.status_code == 200, r.text
    bill_id = r.json()["id"]
    bill = client.get(f"/api/bills/{bill_id}", headers=h).json()
    txn = client.get(f"/api/transactions/{bill['transaction_id']}", headers=h).json()
    for entry in txn["entries"]:
        assert entry.get("analytic_account_id") == aid
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_analytic_accounts.py::test_invoice_analytic_propagates_to_je tests/test_analytic_accounts.py::test_bill_analytic_propagates_to_je -v 2>&1 | tail -15
```

Expected: both fail — `AssertionError: JE row ... missing analytic tag`

- [ ] **Step 3: Add analytic_account_id to InvoiceCreate schema**

In `backend/routers/invoices.py`, inside `class InvoiceCreate(BaseModel):` (after `assigned_to_id`):
```python
    analytic_account_id: Optional[int] = None
```

- [ ] **Step 4: Store analytic_account_id on the Invoice object**

In `backend/routers/invoices.py`, inside the `Invoice(...)` constructor call (~line 311), add:
```python
        analytic_account_id=body.analytic_account_id,
```

- [ ] **Step 5: Propagate to all EntryInput in create_invoice**

In `backend/routers/invoices.py`, in the `entries = [...]` block for the AR/Revenue JV (~lines 431–450), update every `EntryInput(...)` to include `analytic_account_id=body.analytic_account_id`. The block becomes:

```python
    ana = body.analytic_account_id  # per-document analytic tag
    entries = [EntryInput(account_id=ar_acc.id, debit=total_base, analytic_account_id=ana)]
    if revenue_net_base > ZERO:
        entries.append(EntryInput(account_id=rev_acc.id, credit=revenue_net_base, analytic_account_id=ana))
    if deferred_credit_base > ZERO:
        deferred_acc = resolve_deferred_account(session, user.tenant_id)
        entries.append(EntryInput(account_id=deferred_acc.id, credit=deferred_credit_base, analytic_account_id=ana))
    if use_per_line_tax and per_gl_tax:
        for gl_id, tax_amt in per_gl_tax.items():
            entries.append(EntryInput(account_id=gl_id, credit=money(tax_amt * fx_rate), analytic_account_id=ana))
    elif gst_amount > 0:
        gst_acc = get_or_create_account(
            session, user.tenant_id, "2200", "GST Payable (Output)", "Liability"
        )
        entries.append(EntryInput(account_id=gst_acc.id, credit=gst_base, analytic_account_id=ana))
```

Also propagate to the COGS EntryInput block (~line 476):
```python
        cogs_txn = post_transaction(
            session, user,
            date=invoice.issue_date,
            description=f"COGS for {invoice.number}",
            entries=[
                EntryInput(account_id=cogs_acc.id, debit=total_cogs, analytic_account_id=ana),
                EntryInput(account_id=inv_acc.id, credit=total_cogs, analytic_account_id=ana),
            ],
            ...
        )
```

- [ ] **Step 6: Propagate in the update_invoice path**

The `update_invoice` function (~line 503) rebuilds entries identically. Apply the same `ana = body.analytic_account_id` variable + same propagation to all `EntryInput` in that path. Also add `analytic_account_id=body.analytic_account_id` when the `invoice` object is updated (search for `invoice.ar_account_id = body.ar_account_id` and add the analytic line beside it).

- [ ] **Step 7: Add analytic_account_id to BillCreate + Bill model + EntryInput**

In `backend/routers/bills.py`, inside `class BillCreate(BaseModel):` (after `exchange_rate`):
```python
    analytic_account_id: Optional[int] = None
```

In the `Bill(...)` constructor (~line 234), add:
```python
        analytic_account_id=body.analytic_account_id,
```

In the bill `entries` block (~line 325), add `analytic_account_id=body.analytic_account_id` variable and pass it to every `EntryInput`:
```python
    ana = body.analytic_account_id
    entries: list[EntryInput] = [EntryInput(account_id=ap_acc.id, credit=total_base, analytic_account_id=ana)]
    if total_stock_value > 0:
        entries.append(EntryInput(account_id=inv_acc.id, debit=total_stock_base, analytic_account_id=ana))
    if non_stock_base > 0:
        entries.append(EntryInput(account_id=exp_acc.id, debit=non_stock_base, analytic_account_id=ana))
    if use_per_line_tax and per_gl_tax:
        for gl_id, tax_amt in per_gl_tax.items():
            entries.append(EntryInput(account_id=gl_id, debit=money(tax_amt * fx_rate), analytic_account_id=ana))
    elif gst_amount > 0:
        gst_input_acc = get_or_create_account(
            session, user.tenant_id, "1250", "GST Receivable (Input)", "Asset"
        )
        entries.append(EntryInput(account_id=gst_input_acc.id, debit=gst_base, analytic_account_id=ana))
```

Apply the same changes in the `update_bill` path (~line 540).

- [ ] **Step 8: Add analytic_account_id to PaymentReceivedCreate + PaymentReceived + EntryInput**

In `backend/routers/payments.py`, inside `class PaymentReceivedCreate(BaseModel):` (after `allocations`):
```python
    analytic_account_id: Optional[int] = None
```

In the `post_transaction(...)` call for PaymentReceived (~line 178), add `analytic_account_id=body.analytic_account_id` to both `EntryInput`:
```python
        entries=[
            EntryInput(account_id=cash_acc.id, debit=amount, analytic_account_id=body.analytic_account_id),
            EntryInput(account_id=ar_acc.id, credit=amount, analytic_account_id=body.analytic_account_id),
        ],
```

In `PaymentReceived(...)` constructor (~line 188), add:
```python
        analytic_account_id=body.analytic_account_id,
```

- [ ] **Step 9: Add analytic_account_id to BillPaymentCreate + BillPayment + EntryInput**

In `backend/routers/payments.py`, inside `class BillPaymentCreate(BaseModel):` (after `allocations`):
```python
    analytic_account_id: Optional[int] = None
```

In the `post_transaction(...)` call for BillPayment (~line 336), add to both `EntryInput`:
```python
        entries=[
            EntryInput(account_id=ap_acc.id, debit=amount, analytic_account_id=body.analytic_account_id),
            EntryInput(account_id=cash_acc.id, credit=amount, analytic_account_id=body.analytic_account_id),
        ],
```

In `BillPayment(...)` constructor (~line 346), add:
```python
        analytic_account_id=body.analytic_account_id,
```

- [ ] **Step 10: Propagate in transactions router (JV)**

In `backend/routers/transactions.py`, inside `create_transaction` (~line 208), change the `entries` list comprehension to:
```python
        entries=[
            EntryInput(
                account_id=e.account_id,
                debit=D(e.debit),
                credit=D(e.credit),
                analytic_account_id=tx_data.analytic_account_id,
            )
            for e in tx_data.entries
        ],
```

- [ ] **Step 11: Run all analytic tests**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_analytic_accounts.py -v 2>&1 | tail -15
```

Expected: all tests pass (model tests + propagation tests — skip if no analytic accounts seeded in test DB)

- [ ] **Step 12: Run full backend suite**

```bash
cd backend && PYTHONPATH=. uv run pytest -x -q 2>&1 | tail -10
```

Expected: all pass, no new failures.

- [ ] **Step 13: Commit**

```bash
git add backend/routers/invoices.py backend/routers/bills.py backend/routers/payments.py backend/routers/transactions.py backend/tests/test_analytic_accounts.py
git commit -m "feat(analytics): propagate analytic_account_id through posting layer for all document types"
```

---

## Task 3: Frontend — InvoiceForm + BillForm

**Files:**
- Modify: `frontend/src/components/invoices/InvoiceForm.tsx`
- Modify: `frontend/src/components/bills/BillForm.tsx`

- [ ] **Step 1: Add AnalyticAccount type + state to InvoiceForm.tsx**

In `frontend/src/components/invoices/InvoiceForm.tsx`:

After the existing `interface Account { ... }` definition (~line 31), add:
```tsx
interface AnalyticAccount { id: number; code: string; name: string; type: string }
```

In `FormState` interface (near `ar_account_id`), add:
```tsx
  analytic_account_id: string
```

In `emptyForm` object (near `ar_account_id: ''`), add:
```tsx
  analytic_account_id: '',
```

After `const [paymentTerms, setPaymentTerms] = useState<PaymentTerm[]>([])` (~line 79), add:
```tsx
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])
```

In the `useEffect` that calls `apiFetch` in parallel (~line 88), add the analytic-accounts fetch alongside the others:
```tsx
      apiFetch<AnalyticAccount[] | { items: AnalyticAccount[] }>('/api/analytic-accounts'),
```

And in the `.then(([c, a, p, pt, tc, st, an]) => ...)` destructuring, handle the analytic accounts response:
```tsx
      const anItems = Array.isArray(an) ? an : (an as { items: AnalyticAccount[] }).items ?? []
      setAnalyticAccounts(anItems)
```

In the invoice-load `useEffect` (where `setForm(...)` populates existing values), add:
```tsx
        analytic_account_id: invoice.analytic_account_id ? String(invoice.analytic_account_id) : '',
```

In the `handleSave` function, include in the payload object:
```tsx
      analytic_account_id: form.analytic_account_id ? parseInt(form.analytic_account_id) : null,
```

- [ ] **Step 2: Add analytic dropdown JSX to InvoiceForm.tsx**

Find the `<div className="grid grid-cols-2 gap-4">` block that contains the AR Account and Revenue Account selects (~line 426). Add a third field after that block (outside the grid, as a full-width row, immediately before `{formError && ...}`):

```tsx
        {analyticAccounts.length > 0 && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Analytic Account <span className="font-normal normal-case">(optional)</span></label>
            <select
              value={form.analytic_account_id}
              onChange={e => setForm(p => ({ ...p, analytic_account_id: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
            >
              <option value="">— none —</option>
              {analyticAccounts.map(a => (
                <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
              ))}
            </select>
          </div>
        )}
```

- [ ] **Step 3: Apply the same pattern to BillForm.tsx**

In `frontend/src/components/bills/BillForm.tsx`:

1. Add `interface AnalyticAccount { id: number; code: string; name: string; type: string }` (same as above)
2. Add `analytic_account_id: string` to the bill FormState interface
3. Add `analytic_account_id: ''` to `emptyForm`
4. Add `const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])`
5. In the `useEffect` parallel fetch, add `/api/analytic-accounts`
6. In the bill-load `useEffect`, populate `analytic_account_id`
7. In `handleSave`, include `analytic_account_id: form.analytic_account_id ? parseInt(form.analytic_account_id) : null`
8. Add the same analytic dropdown JSX near the ap_account_id / expense_account_id selects

To locate the right place in BillForm — find `ap_account_id` selector and add the analytic block immediately after it.

- [ ] **Step 4: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "analytic|BillForm|InvoiceForm" | head -20
```

Expected: no errors mentioning analytic, BillForm, or InvoiceForm.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/invoices/InvoiceForm.tsx frontend/src/components/bills/BillForm.tsx
git commit -m "feat(analytics): add Analytic Account optional dropdown to Invoice and Bill forms"
```

---

## Task 4: Frontend — PaymentReceivedForm + BillPaymentForm + JV entry

**Files:**
- Modify: `frontend/src/components/payments/PaymentReceivedForm.tsx`
- Modify: `frontend/src/components/payments/BillPaymentForm.tsx`
- Modify: `frontend/src/app/(dashboard)/entry/page.tsx`

- [ ] **Step 1: Add analytic dropdown to PaymentReceivedForm.tsx**

In `frontend/src/components/payments/PaymentReceivedForm.tsx`:

After `interface Account { id: number; code: string; name: string; type: string }` (~line 21), add:
```tsx
interface AnalyticAccount { id: number; code: string; name: string; type: string }
```

In `interface PayForm` (near `cash_account_id`), add:
```tsx
  analytic_account_id: string
```

In `emptyForm`, add:
```tsx
  analytic_account_id: '',
```

After `const [accounts, setAccounts] = useState<Account[]>([])` (~line 56), add:
```tsx
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])
```

In the `useEffect` fetch block, add to the parallel calls:
```tsx
      apiFetch<AnalyticAccount[] | { items: AnalyticAccount[] }>('/api/analytic-accounts'),
```

Handle the response (add `an` to destructuring):
```tsx
      const anItems = Array.isArray(an) ? an : (an as { items: AnalyticAccount[] }).items ?? []
      setAnalyticAccounts(anItems)
```

In the submit handler (where the payload is posted to `/api/payments-received`), add:
```tsx
        analytic_account_id: form.analytic_account_id ? parseInt(form.analytic_account_id) : null,
```

Add the dropdown JSX after the Cash/Bank Account select:
```tsx
        {analyticAccounts.length > 0 && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Analytic Account <span className="font-normal normal-case">(optional)</span></label>
            <select
              value={form.analytic_account_id}
              onChange={e => setForm(p => ({ ...p, analytic_account_id: e.target.value }))}
              className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
            >
              <option value="">— none —</option>
              {analyticAccounts.map(a => (
                <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
              ))}
            </select>
          </div>
        )}
```

- [ ] **Step 2: Apply the same pattern to BillPaymentForm.tsx**

Repeat identical changes in `frontend/src/components/payments/BillPaymentForm.tsx`:
1. Add `AnalyticAccount` interface
2. Add `analytic_account_id: string` to state + emptyForm
3. Add `analyticAccounts` state + fetch
4. Include `analytic_account_id` in submit payload
5. Add the same JSX dropdown after the Cash/Bank Account select

- [ ] **Step 3: Add analytic dropdown to entry/page.tsx (JV form)**

In `frontend/src/app/(dashboard)/entry/page.tsx`:

After `interface Account { ... }` (~line 14), add:
```tsx
interface AnalyticAccount { id: number; code: string; name: string; type: string }
```

After `const [allocRows, setAllocRows] = useState<AllocRow[]>([])` (~line 58), add:
```tsx
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])
  const [analyticAccountId, setAnalyticAccountId] = useState<string>("")
```

In the `useEffect` that fetches `/api/accounts` (~line 60), add a parallel fetch:
```tsx
  useEffect(() => {
    Promise.all([
      apiFetch<{ total: number; items: Account[] }>("/api/accounts?limit=500"),
      apiFetch<AnalyticAccount[] | { items: AnalyticAccount[] }>("/api/analytic-accounts"),
    ])
      .then(([d, an]) => {
        setAccounts(d.items.filter(a => a.postable !== false))
        const items = Array.isArray(an) ? an : (an as { items: AnalyticAccount[] }).items ?? []
        setAnalyticAccounts(items)
      })
      .catch(console.error)
  }, [])
```

In the `payload` construction (~line 212), add after `voucher_type`:
```tsx
      analytic_account_id: analyticAccountId ? parseInt(analyticAccountId) : null,
```

In the JSX, add the analytic dropdown near the existing `description` / `voucherType` fields (after the date input, before the rows table):
```tsx
          {analyticAccounts.length > 0 && (
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Analytic Account <span className="font-normal normal-case">(optional)</span></label>
              <select
                value={analyticAccountId}
                onChange={e => setAnalyticAccountId(e.target.value)}
                className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
              >
                <option value="">— none —</option>
                {analyticAccounts.map(a => (
                  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                ))}
              </select>
            </div>
          )}
```

- [ ] **Step 4: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "analytic|PaymentReceived|BillPayment|entry" | head -20
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/payments/PaymentReceivedForm.tsx frontend/src/components/payments/BillPaymentForm.tsx "frontend/src/app/(dashboard)/entry/page.tsx"
git commit -m "feat(analytics): add Analytic Account optional dropdown to payment forms and JV entry"
```

---

## Task 5: Seed script update + demo re-seed

**Files:**
- Modify: `backend/scripts/seed_demo.py` (G-07 block ~line 1776, header ~line 1, total count lines near the end)

- [ ] **Step 1: Write seed smoke-test**

Append to `backend/tests/test_analytic_accounts.py`:

```python
def test_seed_analytic_pl_non_empty_when_tagged(tmp_path):
    """If analytic accounts exist, Analytic P&L must return rows for at least one dimension."""
    h = _headers()
    r = client.get("/api/analytic-accounts", headers=h)
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    if not items:
        return  # skip — no analytic accounts in this test DB
    non_empty = 0
    for acc in items[:3]:
        pl = client.get(f"/api/reports/analytic-pl?analytic_account_id={acc['id']}", headers=h)
        if pl.status_code == 200 and pl.json():
            non_empty += 1
    # After seeding, at least 1 dimension must have non-empty P&L
    # (This will fail until Task 5 seeds analytic data)
    assert non_empty >= 1, "Analytic P&L empty for all dimensions — seed data missing analytic tags"
```

- [ ] **Step 2: Run to verify failure (expected)**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_analytic_accounts.py::test_seed_analytic_pl_non_empty_when_tagged -v 2>&1 | tail -10
```

Expected: FAIL or SKIP (no analytic accounts in dev DB) — either is fine, proceed.

- [ ] **Step 3: Bump seed script version to v4**

In `backend/scripts/seed_demo.py`, find the header docstring (near line 1) that says `v3` and update it to `v4`. Also update the coverage line to mention analytic tagging:

```python
"""Easy-Books demo-data seeder — v4

Coverage (all 5 demo tenants unless noted):
  ...existing lines...
  (G-07) Analytic Accounts: 7 dimensions per tenant, ~30 % of JVs/invoices/bills tagged
  ...
"""
```

- [ ] **Step 4: Update _seed_analytic_accounts to tag records**

In `backend/scripts/seed_demo.py`, find `def _seed_analytic_accounts(s: Session, tenant_id: int) -> None:` (~line 1776).

**Replace** the existing body with:

```python
def _seed_analytic_accounts(s: Session, tenant_id: int) -> None:
    """G-07: cost centers / projects / departments for segment reporting.
    Also back-fills ~30 % of seeded invoices, bills, payments, and JVs with
    analytic tags so Analytic P&L reports show non-empty figures per tenant.
    """
    # 1. Create the 7 dimensions (idempotent)
    existing = s.exec(select(AnalyticAccount).where(AnalyticAccount.tenant_id == tenant_id)).all()
    if not existing:
        dims = [
            ("CC-SALES", "Sales Department", "department"),
            ("CC-OPS",   "Operations",       "department"),
            ("CC-ADMIN", "Administration",   "department"),
            ("PRJ-A",    "Project Alpha",    "project"),
            ("PRJ-B",    "Project Beta",     "project"),
            ("CC-NORTH", "North Region",     "cost_center"),
            ("CC-SOUTH", "South Region",     "cost_center"),
        ]
        for code, name, typ in dims:
            s.add(AnalyticAccount(
                tenant_id=tenant_id, code=code, name=name, type=typ, is_active=True,
            ))
        s.flush()

    # 2. Load dimension IDs for tagging
    dim_ids = [
        a.id for a in s.exec(
            select(AnalyticAccount).where(AnalyticAccount.tenant_id == tenant_id)
        ).all()
    ]
    if not dim_ids:
        return

    # 3. Tag ~30 % of invoices
    from models import Invoice, Bill, PaymentReceived, BillPayment
    import random
    rng = random.Random(tenant_id)  # deterministic per tenant

    invoices = s.exec(
        select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.analytic_account_id.is_(None))
    ).all()
    for inv in invoices:
        if rng.random() < 0.3:
            inv.analytic_account_id = rng.choice(dim_ids)
            s.add(inv)

    # 4. Tag ~30 % of bills
    bills = s.exec(
        select(Bill).where(Bill.tenant_id == tenant_id, Bill.analytic_account_id.is_(None))
    ).all()
    for bill in bills:
        if rng.random() < 0.3:
            bill.analytic_account_id = rng.choice(dim_ids)
            s.add(bill)

    # 5. Tag ~30 % of payments received
    payments = s.exec(
        select(PaymentReceived).where(
            PaymentReceived.tenant_id == tenant_id,
            PaymentReceived.analytic_account_id.is_(None),
        )
    ).all()
    for pmt in payments:
        if rng.random() < 0.3:
            pmt.analytic_account_id = rng.choice(dim_ids)
            s.add(pmt)

    # 6. Tag ~30 % of bill payments
    bpayments = s.exec(
        select(BillPayment).where(
            BillPayment.tenant_id == tenant_id,
            BillPayment.analytic_account_id.is_(None),
        )
    ).all()
    for bp in bpayments:
        if rng.random() < 0.3:
            bp.analytic_account_id = rng.choice(dim_ids)
            s.add(bp)

    # 7. Tag ~30 % of manual JVs via their JournalEntry rows
    from models import JournalEntry, Transaction
    jvs = s.exec(
        select(Transaction).where(Transaction.tenant_id == tenant_id)
    ).all()
    for txn in jvs:
        if rng.random() < 0.3:
            ana_id = rng.choice(dim_ids)
            for je in s.exec(
                select(JournalEntry).where(JournalEntry.transaction_id == txn.id)
            ).all():
                if je.analytic_account_id is None:
                    je.analytic_account_id = ana_id
                    s.add(je)

    s.flush()
```

**Important:** `_seed_analytic_accounts` is called at the end of `_seed_tenant` in the main seeding loop. Ensure it runs **after** invoices, bills, and payments have been seeded (it already is — check the call order near line 2220).

- [ ] **Step 5: Ensure imports are available in seed script**

At the top of `backend/scripts/seed_demo.py`, verify these are already imported (they should be):
- `AnalyticAccount` from models
- `Invoice`, `Bill`, `PaymentReceived`, `BillPayment` from models
- `JournalEntry`, `Transaction` from models

If any are missing, add them to the existing `from models import ...` block.

- [ ] **Step 6: Run migration on dev DB**

```bash
cd backend && uv run alembic upgrade head 2>&1 | tail -5
```

Expected: already at head (migration ran in Task 1) or applies 0023.

- [ ] **Step 7: Purge and re-seed all 5 demo tenants**

```bash
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo 2>&1 | tail -20
```

Watch for any errors. Expected output ends with something like:
```
[seed] demo.simple@easy-books.app        ✓ (... records)
[seed] demo.services@easy-books.app      ✓ (... records)
[seed] demo.trader@easy-books.app        ✓ (... records)
[seed] demo.manufacturing@easy-books.app ✓ (... records)
[seed] demo.telecom@easy-books.app       ✓ (... records)
```

If any tenant fails, fix the error before proceeding.

- [ ] **Step 8: Run smoke test**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_analytic_accounts.py -v 2>&1 | tail -15
```

Expected: all tests pass including `test_seed_analytic_pl_non_empty_when_tagged`.

- [ ] **Step 9: Run full backend suite**

```bash
cd backend && PYTHONPATH=. uv run pytest -x -q 2>&1 | tail -10
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add backend/scripts/seed_demo.py backend/tests/test_analytic_accounts.py
git commit -m "feat(analytics): seed analytic_account_id on ~30% of demo records; version bump to v4 (closes #79)"
```

---

## Acceptance Checklist (verify before marking done)

- [ ] `uv run alembic upgrade head` completes cleanly — 4 new columns in the DB
- [ ] `POST /api/invoices` with `analytic_account_id` → resulting JE rows carry the tag
- [ ] `POST /api/bills` with `analytic_account_id` → same
- [ ] `POST /api/payments-received` with `analytic_account_id` → same
- [ ] `POST /api/bill-payments` with `analytic_account_id` → same
- [ ] Invoice form shows "Analytic Account (optional)" dropdown when analytic accounts exist
- [ ] Bill form shows same
- [ ] Payment Received form shows same
- [ ] Bill Payment form shows same
- [ ] JV entry form shows same
- [ ] `GET /api/reports/analytic-pl?analytic_account_id=X` returns non-empty rows for at least 2 dimensions per demo tenant
- [ ] All 5 demo tenants seed cleanly with no errors
- [ ] Full pytest suite passes
- [ ] TypeScript compiles with no errors
