# Issue #80 — Voucher Integrity, AR/AP Party Links, Asset Acquisition JV

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three workstreams: §1 restrict manual JVs to JV/CO types (remove dead SR/PV codes); §2 tag JournalEntry rows with customer_id/vendor_id for an AR/AP sub-ledger; §3 auto-post an IAS 16 acquisition GL entry when creating a fixed asset.

**Architecture:** §1 is a pure guard + cleanup (no schema change). §2 adds two nullable FK columns to `journalentry`, one nullable column to `account`, propagates through `EntryInput` → `post_transaction`, and adds a customer/vendor picker to the JV form. §3 adds one nullable FK column to `fixedasset` and conditionally calls `post_transaction` in `create_asset`. All three schema changes ship in one Alembic migration (0024).

**Tech Stack:** FastAPI / SQLModel / Alembic / SQLite (dev); Next.js 16 / React 19 / TypeScript / Tailwind CSS v4; `lucide-react` icons; pytest.

---

## File Map

| File | Change |
|------|--------|
| `backend/models.py` | `Account.party_type`, `JournalEntryBase.customer_id/vendor_id`, `FixedAsset.acquisition_transaction_id` |
| `backend/services/posting.py` | `EntryInput.customer_id/vendor_id`; write them to `JournalEntry` |
| `backend/alembic/versions/0024_party_links_asset_jv.py` | New migration |
| `backend/routers/transactions.py` | Validate `voucher_type` in `{"JV","CO"}`; pass `customer_id/vendor_id` to entries |
| `backend/routers/invoices.py` | AR `EntryInput` gets `customer_id` |
| `backend/routers/bills.py` | AP `EntryInput` gets `vendor_id` |
| `backend/routers/payments.py` | PaymentReceived AR entry gets `customer_id`; BillPayment AP entry gets `vendor_id` |
| `backend/routers/assets.py` | `AssetCreate.funding_account_id`; conditional `post_transaction` in `create_asset`; store `acquisition_transaction_id` |
| `backend/db.py` | Set `party_type` on AR/AP accounts after seeding |
| `backend/tests/test_voucher_integrity.py` | New: §1 tests |
| `backend/tests/test_party_links.py` | New: §2 tests |
| `backend/tests/test_asset_acquisition_jv.py` | New: §3 tests |
| `frontend/src/lib/voucherTypes.ts` | Remove SR/PV from all three maps |
| `frontend/src/app/(dashboard)/entry/page.tsx` | Restrict dropdown to JV/CO; remove dead allocation panel; add customer/vendor pickers |
| `frontend/src/app/(dashboard)/assets/new/page.tsx` (or `page.tsx` for assets list/form) | Add optional `funding_account_id` selector |

---

## Task 1: §1 Backend — Voucher Type Whitelist in `create_transaction`

**Files:**
- Modify: `backend/routers/transactions.py:207-233`
- Create: `backend/tests/test_voucher_integrity.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_voucher_integrity.py`:

```python
"""§1 — create_transaction must only accept JV and CO voucher types."""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _headers():
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    if r.status_code != 200:
        return None
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _minimal_jv_payload(voucher_type: str, accounts) -> dict:
    """Two-line balanced JV using the first two postable accounts."""
    a, b = accounts[0]["id"], accounts[1]["id"]
    return {
        "date": "2026-01-01",
        "description": "test",
        "voucher_type": voucher_type,
        "entries": [
            {"account_id": a, "debit": 100, "credit": 0},
            {"account_id": b, "debit": 0, "credit": 100},
        ],
    }


def _get_postable_accounts(headers):
    r = client.get("/api/accounts?limit=500", headers=headers)
    if r.status_code != 200:
        return []
    return [a for a in r.json()["items"] if a.get("postable", True) and not a.get("is_group")]


def test_jv_accepted():
    hdrs = _headers()
    if not hdrs:
        return
    accounts = _get_postable_accounts(hdrs)
    if len(accounts) < 2:
        return
    r = client.post("/api/transactions", json=_minimal_jv_payload("JV", accounts), headers=hdrs)
    assert r.status_code == 200, r.text


def test_co_accepted():
    hdrs = _headers()
    if not hdrs:
        return
    accounts = _get_postable_accounts(hdrs)
    if len(accounts) < 2:
        return
    r = client.post("/api/transactions", json=_minimal_jv_payload("CO", accounts), headers=hdrs)
    assert r.status_code == 200, r.text


def test_sl_rejected():
    hdrs = _headers()
    if not hdrs:
        return
    accounts = _get_postable_accounts(hdrs)
    if len(accounts) < 2:
        return
    r = client.post("/api/transactions", json=_minimal_jv_payload("SL", accounts), headers=hdrs)
    assert r.status_code == 400, r.text


def test_sr_rejected():
    hdrs = _headers()
    if not hdrs:
        return
    accounts = _get_postable_accounts(hdrs)
    if len(accounts) < 2:
        return
    r = client.post("/api/transactions", json=_minimal_jv_payload("SR", accounts), headers=hdrs)
    assert r.status_code == 400, r.text


def test_pr_rejected():
    hdrs = _headers()
    if not hdrs:
        return
    accounts = _get_postable_accounts(hdrs)
    if len(accounts) < 2:
        return
    r = client.post("/api/transactions", json=_minimal_jv_payload("PR", accounts), headers=hdrs)
    assert r.status_code == 400, r.text


def test_cn_rejected():
    hdrs = _headers()
    if not hdrs:
        return
    accounts = _get_postable_accounts(hdrs)
    if len(accounts) < 2:
        return
    r = client.post("/api/transactions", json=_minimal_jv_payload("CN", accounts), headers=hdrs)
    assert r.status_code == 400, r.text
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && uv run pytest tests/test_voucher_integrity.py -v 2>&1 | tail -20
```

Expected: `test_jv_accepted` and `test_co_accepted` pass (already do); `test_sl_rejected`, `test_sr_rejected`, `test_pr_rejected`, `test_cn_rejected` FAIL with status 200.

- [ ] **Step 3: Add validation to `create_transaction`**

In `backend/routers/transactions.py`, insert at line 209 (right after the function signature, before `txn = post_transaction`):

```python
_MANUAL_VOUCHER_TYPES = {"JV", "CO"}

@router.post("")
def create_transaction(
    session: SessionDep, user: WriteUserDep, tx_data: TransactionCreate
):
    vt = (tx_data.voucher_type or "JV").upper()
    if vt not in _MANUAL_VOUCHER_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Voucher type '{vt}' cannot be created via the journal entry form. "
                   f"Use the dedicated invoice / bill / payment module instead.",
        )
    txn = post_transaction(
        session, user,
        date=tx_data.date,
        description=tx_data.description or "",
        entries=[
            EntryInput(
                account_id=e.account_id,
                debit=D(e.debit),
                credit=D(e.credit),
                analytic_account_id=tx_data.analytic_account_id,
            )
            for e in tx_data.entries
        ],
        reference=tx_data.reference,
        party=tx_data.party,
        payment_method=tx_data.payment_method,
        notes=tx_data.notes,
        voucher_type=vt,
        audit_entity_type="transaction",
    )
    if tx_data.allocations:
        _apply_allocations(session, user, txn, tx_data.allocations, tx_data.date)
    session.commit()
    return {"id": txn.id, "jv_number": txn.jv_number}
```

Note: `_MANUAL_VOUCHER_TYPES` is a module-level constant placed just before the `@router.post("")` decorator. Also import `HTTPException` at the top if not already present (it already is via FastAPI).

- [ ] **Step 4: Run tests — all 6 should pass**

```bash
cd backend && uv run pytest tests/test_voucher_integrity.py -v
```

Expected: 6 PASSED.

- [ ] **Step 5: Run full suite to catch regressions**

```bash
cd backend && uv run pytest -x -q 2>&1 | tail -10
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_voucher_integrity.py backend/routers/transactions.py
git commit -m "feat(transactions): restrict manual JV to JV/CO voucher types (#80 §1)"
```

---

## Task 2: §1 Frontend — Remove SR/PV + Restrict JV Form Dropdown

**Files:**
- Modify: `frontend/src/lib/voucherTypes.ts`
- Modify: `frontend/src/app/(dashboard)/entry/page.tsx`

- [ ] **Step 1: Remove SR and PV from `voucherTypes.ts`**

In `frontend/src/lib/voucherTypes.ts`, remove the `SR` and `PV` entries from `VOUCHER_TYPES`, `VOUCHER_TYPE_COLORS`, and `VOUCHER_ACCOUNT_HINTS`. Also update the comment in `VOUCHER_SIDE_FILTERS` that mentions SR/PV.

The file after changes:

```typescript
/** Canonical voucher-type catalog — mirrors backend services/vouchers.py VOUCHER_TYPES */
export const VOUCHER_TYPES: Record<string, string> = {
  JV: "Journal Voucher",
  CP: "Cash Payment",
  CR: "Cash Receipt",
  BP: "Bank Payment",
  BR: "Bank Receipt",
  SL: "Sales Invoice",
  PR: "Purchase Invoice",
  CO: "Contra",
  DN: "Debit Note",
  CN: "Credit Note",
}

/** Tailwind colour classes for each voucher type badge. */
export const VOUCHER_TYPE_COLORS: Record<string, string> = {
  JV: "bg-gray-100 text-gray-700",
  CP: "bg-orange-100 text-orange-700",
  CR: "bg-green-100 text-green-700",
  BP: "bg-orange-100 text-orange-700",
  BR: "bg-green-100 text-green-700",
  SL: "bg-blue-100 text-blue-700",
  PR: "bg-purple-100 text-purple-700",
  CO: "bg-cyan-100 text-cyan-700",
  DN: "bg-amber-100 text-amber-700",
  CN: "bg-amber-100 text-amber-700",
}
```

In `VOUCHER_SIDE_FILTERS`, update the comment above it:

```typescript
/**
 * Smart account-head filtering rules (Issue #77 Part 1).
 * Voucher types not listed here (JV, SL, PR, DN, CN, CO) have no
 * restriction and show the full COA on both sides.
 */
```

In `VOUCHER_ACCOUNT_HINTS`, remove SR and PV entries:

```typescript
/** @deprecated Use VOUCHER_SIDE_FILTERS + filterAccountsForSide instead. */
export const VOUCHER_ACCOUNT_HINTS: Record<string, AccountType[]> = {
  CP: ["Asset"],
  CR: ["Asset"],
  BP: ["Asset"],
  BR: ["Asset"],
  CO: ["Asset"],
  SL: ["Asset", "Revenue"],
  CN: ["Asset", "Revenue"],
  PR: ["Asset", "Expense", "Liability"],
  DN: ["Asset", "Expense", "Liability"],
  JV: [],
}
```

- [ ] **Step 2: Restrict the JV form dropdown to JV and CO only**

In `frontend/src/app/(dashboard)/entry/page.tsx`, find the voucher type `<select>` block (around line 274–282). Replace the `Object.entries(VOUCHER_TYPES)` map with a hardcoded list of JV and CO:

```tsx
<select
  value={voucherType}
  onChange={e => setVoucherType(e.target.value)}
  className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm"
>
  <option value="JV">Journal Voucher</option>
  <option value="CO">Contra</option>
</select>
```

Also remove the `VOUCHER_TYPES` import from the `import` line since it's no longer used by the dropdown (but keep `VOUCHER_SIDE_FILTERS` and `filterAccountsForSide` for the CO filter logic).

- [ ] **Step 3: Remove dead allocation panel code**

The allocation panel (`isAllocationVoucher`, `partyAccountId`, `allocationMode`, `openItems`, `allocRows`, the `useEffect` for fetching open items, `toggleAlloc`, `setAllocAmount`, `totalAllocated`) was only reachable for CP/CR/BP/BR types. Now that those are not selectable, remove all of it:

Delete or comment out from `entry/page.tsx`:
- `const [openItems, setOpenItems] = useState<OpenItem[]>([])` 
- `const [allocRows, setAllocRows] = useState<AllocRow[]>([])`
- The `OpenItem` and `AllocRow` interface definitions
- `const isAllocationVoucher = ...`
- `const partyAccountId = useMemo(...)`
- `const allocationMode = useMemo(...)`
- The `useEffect(() => { ... }, [partyAccountId, allocationMode])` block
- `const totalAllocated = ...`
- `function toggleAlloc(...)` 
- `function setAllocAmount(...)`
- In `handleSubmit`, remove the `if (activeAllocs.length > 0 && allocationMode)` block and the `activeAllocs` variable
- In the JSX, remove the `{openItems.length > 0 && (...)}` allocation panel section
- Remove `AllocationInput` from the API payload in submit
- In the `import` list, remove `Link2` icon if only used in the allocation panel

Also set default `voucherType` initial state to `"JV"` (it already is, just confirm it stays).

- [ ] **Step 4: Run TypeScript check**

```bash
cd frontend && npm run lint 2>&1 | grep -E "error|Error" | head -20
```

Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/voucherTypes.ts frontend/src/app/(dashboard)/entry/page.tsx
git commit -m "feat(frontend): remove SR/PV dead codes; restrict JV form to JV/CO (#80 §1)"
```

---

## Task 3: §2+§3 Schema — Party Fields + Asset Acquisition FK + Migration 0024

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/services/posting.py`
- Create: `backend/alembic/versions/0024_party_links_asset_jv.py`

- [ ] **Step 1: Write failing model-field tests**

Create `backend/tests/test_party_links.py`:

```python
"""§2 — JournalEntry carries customer_id/vendor_id; Account carries party_type."""
from models import JournalEntry, Account, FixedAsset
import inspect


def test_journal_entry_has_customer_id():
    fields = JournalEntry.model_fields
    assert "customer_id" in fields
    assert fields["customer_id"].default is None


def test_journal_entry_has_vendor_id():
    fields = JournalEntry.model_fields
    assert "vendor_id" in fields
    assert fields["vendor_id"].default is None


def test_account_has_party_type():
    fields = Account.model_fields
    assert "party_type" in fields
    assert fields["party_type"].default is None


def test_fixed_asset_has_acquisition_transaction_id():
    fields = FixedAsset.model_fields
    assert "acquisition_transaction_id" in fields
    assert fields["acquisition_transaction_id"].default is None
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd backend && uv run pytest tests/test_party_links.py::test_journal_entry_has_customer_id tests/test_party_links.py::test_journal_entry_has_vendor_id tests/test_party_links.py::test_account_has_party_type tests/test_party_links.py::test_fixed_asset_has_acquisition_transaction_id -v
```

Expected: all 4 FAIL.

- [ ] **Step 3: Add fields to `backend/models.py`**

**`JournalEntryBase`** (after `analytic_account_id`):

```python
class JournalEntryBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    account_id: int = Field(foreign_key="account.id")
    debit: Money = money_col()
    credit: Money = money_col()
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    # AR/AP sub-ledger party tagging (Issue #80 §2)
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")
```

**`Account`** (after `is_active`):

```python
    is_active: bool = Field(default=True)
    # "customer" for AR accounts (code 12xx), "vendor" for AP accounts (code 21xx), None otherwise
    party_type: Optional[str] = None
```

**`FixedAsset`** (after `last_depreciation_date`, before `created_at`):

```python
    last_depreciation_date: Optional[str] = None
    # GL transaction posted at acquisition (IAS 16). None if asset registered without a GL entry.
    acquisition_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 4: Update `EntryInput` in `backend/services/posting.py`**

Add `customer_id` and `vendor_id` to the frozen dataclass and write them to `JournalEntry`:

```python
@dataclass(frozen=True)
class EntryInput:
    """One side of a journal entry. Exactly one of debit / credit must be > 0."""
    account_id: int
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    analytic_account_id: Optional[int] = None
    customer_id: Optional[int] = None
    vendor_id: Optional[int] = None

    def normalised(self) -> "EntryInput":
        return EntryInput(
            account_id=self.account_id,
            debit=D(self.debit),
            credit=D(self.credit),
            analytic_account_id=self.analytic_account_id,
            customer_id=self.customer_id,
            vendor_id=self.vendor_id,
        )
```

In `post_transaction`, update the `JournalEntry` construction loop:

```python
    for e in norm:
        session.add(
            JournalEntry(
                tenant_id=user.tenant_id,
                transaction_id=txn.id,
                account_id=e.account_id,
                debit=e.debit,
                credit=e.credit,
                analytic_account_id=e.analytic_account_id,
                customer_id=e.customer_id,
                vendor_id=e.vendor_id,
            )
        )
```

- [ ] **Step 5: Create Alembic migration 0024**

Create `backend/alembic/versions/0024_party_links_asset_jv.py`:

```python
"""customer_id/vendor_id on journalentry, party_type on account, acquisition_transaction_id on fixedasset

Revision ID: 0024_party_links
Revises: 0023analytic_links
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0024_party_links"
down_revision: Union[str, Sequence[str], None] = "0023analytic_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # journalentry — customer_id, vendor_id
    je_cols = {c["name"] for c in sa.inspect(bind).get_columns("journalentry")}
    if "customer_id" not in je_cols:
        op.add_column("journalentry", sa.Column("customer_id", sa.Integer(), nullable=True))
    if "vendor_id" not in je_cols:
        op.add_column("journalentry", sa.Column("vendor_id", sa.Integer(), nullable=True))

    # account — party_type
    acc_cols = {c["name"] for c in sa.inspect(bind).get_columns("account")}
    if "party_type" not in acc_cols:
        op.add_column("account", sa.Column("party_type", sa.String(), nullable=True))

    # fixedasset — acquisition_transaction_id
    fa_cols = {c["name"] for c in sa.inspect(bind).get_columns("fixedasset")}
    if "acquisition_transaction_id" not in fa_cols:
        op.add_column(
            "fixedasset",
            sa.Column("acquisition_transaction_id", sa.Integer(), nullable=True),
        )
    # FK constraints omitted: SQLite does not support ADD CONSTRAINT via ALTER TABLE.


def downgrade() -> None:
    op.drop_column("journalentry", "customer_id")
    op.drop_column("journalentry", "vendor_id")
    op.drop_column("account", "party_type")
    op.drop_column("fixedasset", "acquisition_transaction_id")
```

- [ ] **Step 6: Apply migration**

```bash
cd backend && uv run alembic upgrade head 2>&1
```

Expected: "Running upgrade 0023analytic_links -> 0024_party_links, ..."

- [ ] **Step 7: Run model-field tests — all 4 pass**

```bash
cd backend && uv run pytest tests/test_party_links.py::test_journal_entry_has_customer_id tests/test_party_links.py::test_journal_entry_has_vendor_id tests/test_party_links.py::test_account_has_party_type tests/test_party_links.py::test_fixed_asset_has_acquisition_transaction_id -v
```

Expected: all 4 PASSED.

- [ ] **Step 8: Run full suite**

```bash
cd backend && uv run pytest -x -q 2>&1 | tail -10
```

Expected: all tests pass (new columns are nullable, no existing code breaks).

- [ ] **Step 9: Commit**

```bash
git add backend/models.py backend/services/posting.py backend/alembic/versions/0024_party_links_asset_jv.py
git commit -m "feat(schema): customer_id/vendor_id on JE, party_type on Account, acquisition_transaction_id on FixedAsset (#80 §2/§3)"
```

---

## Task 4: §2 Router Wiring — AR/AP Party Tags in Document Routers

**Files:**
- Modify: `backend/routers/invoices.py`
- Modify: `backend/routers/bills.py`
- Modify: `backend/routers/payments.py`
- Modify: `backend/routers/transactions.py`
- Modify: `backend/tests/test_party_links.py`

- [ ] **Step 1: Add integration tests to `test_party_links.py`**

Append to `backend/tests/test_party_links.py`:

```python
# ── Integration tests: customer_id/vendor_id propagates to JournalEntry rows ──

from fastapi.testclient import TestClient
from main import app
from models import JournalEntry, Invoice, Bill
from sqlmodel import Session, create_engine, select

client = TestClient(app)


def _login_headers():
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    if r.status_code != 200:
        return None
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _get_first_customer_id(headers) -> int | None:
    r = client.get("/api/customers?limit=5", headers=headers)
    if r.status_code != 200:
        return None
    items = r.json().get("items") or r.json() if isinstance(r.json(), list) else []
    if isinstance(r.json(), dict):
        items = r.json().get("items", [])
    return items[0]["id"] if items else None


def _get_first_vendor_id(headers) -> int | None:
    r = client.get("/api/vendors?limit=5", headers=headers)
    if r.status_code != 200:
        return None
    items = r.json().get("items") if isinstance(r.json(), dict) else r.json()
    return items[0]["id"] if items else None


def _get_accounts(headers) -> list:
    r = client.get("/api/accounts?limit=500", headers=headers)
    return r.json().get("items", []) if r.status_code == 200 else []


def test_invoice_ar_je_has_customer_id():
    """Invoice posting must tag the AR JournalEntry row with customer_id."""
    headers = _login_headers()
    if not headers:
        return
    customer_id = _get_first_customer_id(headers)
    if not customer_id:
        return
    accounts = _get_accounts(headers)
    rev_acc = next((a for a in accounts if a["type"] == "Revenue" and not a.get("is_group")), None)
    if not rev_acc:
        return

    payload = {
        "customer_id": customer_id,
        "issue_date": "2026-01-01",
        "due_date": "2026-01-31",
        "lines": [{"description": "Test service", "qty": 1, "rate": 500, "account_id": rev_acc["id"]}],
    }
    r = client.post("/api/invoices", json=payload, headers=headers)
    if r.status_code not in (200, 201):
        return
    inv_id = r.json()["id"]

    inv_r = client.get(f"/api/invoices/{inv_id}", headers=headers)
    txn_id = inv_r.json().get("transaction_id")
    if not txn_id:
        return

    txn_r = client.get(f"/api/transactions/{txn_id}", headers=headers)
    entries = txn_r.json().get("entries", [])
    # Find the AR entry (debit side)
    ar_entries = [e for e in entries if (e.get("debit") or 0) > 0 and e.get("account_type") == "Asset"]
    assert any(e.get("customer_id") == customer_id for e in ar_entries), \
        f"No AR entry with customer_id={customer_id}. Entries: {entries}"


def test_bill_ap_je_has_vendor_id():
    """Bill posting must tag the AP JournalEntry row with vendor_id."""
    headers = _login_headers()
    if not headers:
        return
    vendor_id = _get_first_vendor_id(headers)
    if not vendor_id:
        return
    accounts = _get_accounts(headers)
    exp_acc = next((a for a in accounts if a["type"] == "Expense" and not a.get("is_group")), None)
    if not exp_acc:
        return

    payload = {
        "vendor_id": vendor_id,
        "bill_date": "2026-01-01",
        "due_date": "2026-01-31",
        "lines": [{"description": "Test expense", "qty": 1, "rate": 300, "account_id": exp_acc["id"]}],
    }
    r = client.post("/api/bills", json=payload, headers=headers)
    if r.status_code not in (200, 201):
        return
    bill_id = r.json()["id"]

    bill_r = client.get(f"/api/bills/{bill_id}", headers=headers)
    txn_id = bill_r.json().get("transaction_id")
    if not txn_id:
        return

    txn_r = client.get(f"/api/transactions/{txn_id}", headers=headers)
    entries = txn_r.json().get("entries", [])
    # AP entry is the credit side Liability
    ap_entries = [e for e in entries if (e.get("credit") or 0) > 0 and e.get("account_type") == "Liability"]
    assert any(e.get("vendor_id") == vendor_id for e in ap_entries), \
        f"No AP entry with vendor_id={vendor_id}. Entries: {entries}"
```

Note: these tests skip gracefully (via `return`) if no seeded data is present.

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && uv run pytest tests/test_party_links.py::test_invoice_ar_je_has_customer_id tests/test_party_links.py::test_bill_ap_je_has_vendor_id -v 2>&1 | tail -20
```

Expected: both FAIL (AssertionError — customer_id/vendor_id is None on JE rows).

- [ ] **Step 3: Update `routers/invoices.py` — AR entry gets `customer_id`**

In `routers/invoices.py`, find the block that sets `ana = body.analytic_account_id` (around line 433) and builds `entries`. Add a `cust` variable alongside `ana`:

```python
    ana = body.analytic_account_id
    cust = body.customer_id
    entries = [EntryInput(account_id=ar_acc.id, debit=total_base, analytic_account_id=ana, customer_id=cust)]
```

Only the first entry (AR debit) gets `customer_id`. All revenue/GST entries remain unchanged (no customer_id).

Also update the `update_invoice` path the same way (search for the analogous `EntryInput(account_id=ar_acc.id,` in the update handler and add `customer_id=inv.customer_id`).

- [ ] **Step 4: Update `routers/bills.py` — AP entry gets `vendor_id`**

In `routers/bills.py`, find the `ana = body.analytic_account_id` block (around line 327). Add `vend`:

```python
    ana = body.analytic_account_id
    vend = body.vendor_id
    entries: list[EntryInput] = [EntryInput(account_id=ap_acc.id, credit=total_base, analytic_account_id=ana, vendor_id=vend)]
```

Only the AP credit entry gets `vendor_id`. In the `update_bill` path, add `vendor_id=bill.vendor_id` to the AP EntryInput.

- [ ] **Step 5: Update `routers/payments.py` — PaymentReceived AR entry + BillPayment AP entry**

In `routers/payments.py`, find the PaymentReceived entry creation (around line 179):

```python
            EntryInput(account_id=cash_acc.id, debit=amount, analytic_account_id=body.analytic_account_id),
            EntryInput(account_id=ar_acc.id, credit=amount, analytic_account_id=body.analytic_account_id),
```

Add `customer_id=body.customer_id` to the AR entry (credit side):

```python
            EntryInput(account_id=cash_acc.id, debit=amount, analytic_account_id=body.analytic_account_id),
            EntryInput(account_id=ar_acc.id, credit=amount, analytic_account_id=body.analytic_account_id, customer_id=body.customer_id),
```

For BillPayment (around line 339):

```python
            EntryInput(account_id=ap_acc.id, debit=amount, analytic_account_id=body.analytic_account_id, vendor_id=body.vendor_id),
            EntryInput(account_id=cash_acc.id, credit=amount, analytic_account_id=body.analytic_account_id),
```

- [ ] **Step 6: Update `routers/transactions.py` — pass customer_id/vendor_id from `TransactionCreate`**

First, add the fields to `TransactionCreate` in `models.py` (add after `analytic_account_id`):

```python
class TransactionCreate(SQLModel):
    ...
    analytic_account_id: Optional[int] = None
    customer_id: Optional[int] = None
    vendor_id: Optional[int] = None
```

Then in `create_transaction`, update the `EntryInput` comprehension:

```python
        entries=[
            EntryInput(
                account_id=e.account_id,
                debit=D(e.debit),
                credit=D(e.credit),
                analytic_account_id=tx_data.analytic_account_id,
                customer_id=tx_data.customer_id,
                vendor_id=tx_data.vendor_id,
            )
            for e in tx_data.entries
        ],
```

Also update `get_transaction` to expose `customer_id` and `vendor_id` per entry in the response (so tests can verify it):

```python
    entries = [
        {
            "account_id": je.account_id,
            "account_name": je.account.name,
            "account_type": je.account.type,
            "debit": je.debit,
            "credit": je.credit,
            "customer_id": je.customer_id,
            "vendor_id": je.vendor_id,
        }
        for je in tx.journal_entries
    ]
```

- [ ] **Step 7: Run integration tests**

```bash
cd backend && uv run pytest tests/test_party_links.py -v 2>&1 | tail -20
```

Expected: all tests PASSED (or gracefully skipped).

- [ ] **Step 8: Run full suite**

```bash
cd backend && uv run pytest -x -q 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/models.py backend/routers/invoices.py backend/routers/bills.py backend/routers/payments.py backend/routers/transactions.py backend/tests/test_party_links.py
git commit -m "feat(gl): tag AR/AP JournalEntry rows with customer_id/vendor_id (#80 §2)"
```

---

## Task 5: §2 Seeding — `party_type` on AR/AP Accounts

**Files:**
- Modify: `backend/db.py`
- Modify: `backend/scripts/seed_demo.py`

- [ ] **Step 1: Add `party_type` setter in `db.py`**

In `backend/db.py`, after the two-pass account seeding (after both passes where `parent_id` is wired), add a loop to set `party_type` based on account code prefix:

```python
    # Set party_type on AR accounts (code 12xx → customer) and AP accounts (code 21xx → vendor)
    for account in session.exec(select(Account).where(Account.tenant_id == tenant_id)).all():
        if account.code.startswith("12") and account.type == "Asset":
            account.party_type = "customer"
        elif account.code.startswith("21") and account.type == "Liability":
            account.party_type = "vendor"
        else:
            continue
        session.add(account)
    session.flush()
```

This runs for both the default tenant and demo tenant seeding since both call the same `seed_data` function.

- [ ] **Step 2: Add `party_type` setter in `seed_demo.py`**

In `backend/scripts/seed_demo.py`, after the `_ensure_coa` step for each tenant, add the same `party_type` loop. Find the function `_ensure_coa` or the location where accounts are seeded per demo tenant. Add:

```python
def _set_party_types(session, tenant_id: int) -> None:
    """Set party_type on AR (12xx) and AP (21xx) accounts."""
    from models import Account
    from sqlmodel import select
    for acc in session.exec(select(Account).where(Account.tenant_id == tenant_id)).all():
        if acc.code.startswith("12") and acc.type == "Asset":
            if acc.party_type != "customer":
                acc.party_type = "customer"
                session.add(acc)
        elif acc.code.startswith("21") and acc.type == "Liability":
            if acc.party_type != "vendor":
                acc.party_type = "vendor"
                session.add(acc)
    session.flush()
```

Call `_set_party_types(session, tenant_id)` after `_ensure_coa` in each tenant's seed function.

- [ ] **Step 3: Verify seeding works**

```bash
cd backend && PYTHONPATH=. python -c "
from db import engine
from sqlmodel import Session, select
from models import Account
with Session(engine) as s:
    rows = s.exec(select(Account).where(Account.party_type != None)).all()
    print(f'{len(rows)} accounts have party_type set')
    for a in rows[:5]:
        print(f'  {a.code} {a.name}: {a.party_type}')
"
```

Expected: several accounts have `party_type = "customer"` or `"vendor"`.

- [ ] **Step 4: Run full suite**

```bash
cd backend && uv run pytest -x -q 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/scripts/seed_demo.py
git commit -m "feat(seed): set party_type on AR/AP accounts (#80 §2)"
```

---

## Task 6: §2 Frontend — Customer/Vendor Pickers in JV Form

**Files:**
- Modify: `frontend/src/app/(dashboard)/entry/page.tsx`

The JV form now only has JV and CO voucher types. When the user selects an account whose `party_type` is `"customer"` on any row, show a **Customer** dropdown at the header level. Similarly for `"vendor"`. These propagate to all rows (same pattern as `analytic_account_id`).

- [ ] **Step 1: Add interface + state to the JV form**

In `frontend/src/app/(dashboard)/entry/page.tsx`, add:

```tsx
interface PartyItem { id: number; name: string }
```

And new state:

```tsx
const [customers, setCustomers] = useState<PartyItem[]>([])
const [vendors, setVendors]     = useState<PartyItem[]>([])
const [customerId, setCustomerId] = useState<string>("")
const [vendorId, setVendorId]     = useState<string>("")
```

- [ ] **Step 2: Fetch customers and vendors alongside accounts**

Update the `Promise.all` in `useEffect` to also fetch customers and vendors:

```tsx
  useEffect(() => {
    Promise.all([
      apiFetch<{ total: number; items: Account[] }>("/api/accounts?limit=500"),
      apiFetch<AnalyticAccount[] | { items: AnalyticAccount[] }>("/api/analytic-accounts"),
      apiFetch<{ items: PartyItem[] } | PartyItem[]>("/api/customers?limit=500"),
      apiFetch<{ items: PartyItem[] } | PartyItem[]>("/api/vendors?limit=500"),
    ])
      .then(([d, an, custs, vends]) => {
        setAccounts(d.items.filter(a => a.postable !== false))
        const anItems = Array.isArray(an) ? an : ((an as { items: AnalyticAccount[] }).items ?? [])
        setAnalyticAccounts(anItems)
        const custItems = Array.isArray(custs) ? custs : ((custs as { items: PartyItem[] }).items ?? [])
        setCustomers(custItems)
        const vendItems = Array.isArray(vends) ? vends : ((vends as { items: PartyItem[] }).items ?? [])
        setVendors(vendItems)
      })
      .catch(console.error)
  }, [])
```

- [ ] **Step 3: Derive whether AR/AP accounts are in use**

```tsx
  const hasArAccount = useMemo(
    () => rows.some(r => {
      const a = accounts.find(a => a.id === parseInt(r.account_id))
      return a?.party_type === "customer"
    }),
    [rows, accounts],
  )

  const hasApAccount = useMemo(
    () => rows.some(r => {
      const a = accounts.find(a => a.id === parseInt(r.account_id))
      return a?.party_type === "vendor"
    }),
    [rows, accounts],
  )
```

Note: `Account` interface needs `party_type?: string` added:

```tsx
interface Account {
  id: number
  code: string
  name: string
  type?: string
  postable?: boolean
  party_type?: string
}
```

- [ ] **Step 4: Add pickers to the JSX header section**

After the `analyticAccounts.length > 0` dropdown block, add:

```tsx
{hasArAccount && customers.length > 0 && (
  <div>
    <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
      Customer <span className="font-normal normal-case">(optional)</span>
    </label>
    <select
      value={customerId}
      onChange={e => setCustomerId(e.target.value)}
      className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm"
    >
      <option value="">— none —</option>
      {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
    </select>
  </div>
)}
{hasApAccount && vendors.length > 0 && (
  <div>
    <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
      Vendor <span className="font-normal normal-case">(optional)</span>
    </label>
    <select
      value={vendorId}
      onChange={e => setVendorId(e.target.value)}
      className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm"
    >
      <option value="">— none —</option>
      {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
    </select>
  </div>
)}
```

- [ ] **Step 5: Include in submit payload**

In `handleSubmit`, add to `payload`:

```tsx
    const payload: Record<string, unknown> = {
      date,
      description,
      voucher_type: voucherType,
      analytic_account_id: analyticAccountId ? parseInt(analyticAccountId) : null,
      customer_id: customerId ? parseInt(customerId) : null,
      vendor_id: vendorId ? parseInt(vendorId) : null,
      entries: rows
        .filter(r => r.account_id && (parseFloat(r.debit) > 0 || parseFloat(r.credit) > 0))
        .map(r => ({
          account_id: parseInt(r.account_id),
          debit: parseFloat(r.debit)  || 0,
          credit: parseFloat(r.credit) || 0,
        })),
    }
```

- [ ] **Step 6: TypeScript check**

```bash
cd frontend && npm run lint 2>&1 | grep -E "error|Error" | head -20
```

Expected: no new errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/(dashboard)/entry/page.tsx
git commit -m "feat(frontend): customer/vendor pickers in JV form for AR/AP rows (#80 §2)"
```

---

## Task 7: §3 Asset Acquisition JV

**Files:**
- Modify: `backend/routers/assets.py`
- Create: `backend/tests/test_asset_acquisition_jv.py`
- Modify: `frontend/src/app/(dashboard)/assets/new/page.tsx` (or wherever the asset creation form lives — check with `find frontend/src -name "*.tsx" | xargs grep -l "AssetCreate\|acquisition_cost" 2>/dev/null`)

- [ ] **Step 1: Locate the asset creation frontend file**

```bash
find /home/mbilal71/projects/Easy-Books/frontend/src -name "*.tsx" | xargs grep -l "acquisition_cost\|new.*asset\|asset.*form" 2>/dev/null | head -5
```

Use the result in the step below.

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_asset_acquisition_jv.py`:

```python
"""§3 — create_asset with funding_account_id posts an acquisition GL entry."""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _headers():
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    if r.status_code != 200:
        return None
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _get_accounts(headers) -> list:
    r = client.get("/api/accounts?limit=500", headers=headers)
    return r.json().get("items", []) if r.status_code == 200 else []


def test_asset_without_funding_account_has_no_acquisition_txn():
    """Creating an asset without funding_account_id must NOT post a GL entry."""
    headers = _headers()
    if not headers:
        return
    accounts = _get_accounts(headers)
    asset_acc = next(
        (a for a in accounts if a["type"] == "Asset" and not a.get("is_group") and not a.get("is_memo")), None
    )
    if not asset_acc:
        return
    payload = {
        "name": "Test Machine No GL",
        "asset_account_id": asset_acc["id"],
        "accum_depr_account_id": asset_acc["id"],
        "depr_expense_account_id": asset_acc["id"],
        "acquisition_date": "2026-01-01",
        "acquisition_cost": "10000.00",
        "useful_life_months": 60,
    }
    r = client.post("/api/assets", json=payload, headers=headers)
    if r.status_code not in (200, 201):
        return
    asset = r.json()
    assert asset.get("acquisition_transaction_id") is None


def test_asset_with_funding_account_posts_acquisition_jv():
    """Creating an asset with funding_account_id must post a balanced GL entry."""
    headers = _headers()
    if not headers:
        return
    accounts = _get_accounts(headers)
    asset_acc = next(
        (a for a in accounts if a["type"] == "Asset" and not a.get("is_group") and not a.get("is_memo")), None
    )
    bank_acc = next(
        (a for a in accounts if a["type"] == "Asset" and "bank" in a.get("name", "").lower() and not a.get("is_group")), None
    )
    if not asset_acc or not bank_acc or asset_acc["id"] == bank_acc["id"]:
        return
    payload = {
        "name": "Test Machine With GL",
        "asset_account_id": asset_acc["id"],
        "accum_depr_account_id": asset_acc["id"],
        "depr_expense_account_id": asset_acc["id"],
        "acquisition_date": "2026-01-01",
        "acquisition_cost": "15000.00",
        "useful_life_months": 60,
        "funding_account_id": bank_acc["id"],
    }
    r = client.post("/api/assets", json=payload, headers=headers)
    if r.status_code not in (200, 201):
        return
    asset = r.json()
    assert asset.get("acquisition_transaction_id") is not None, \
        "acquisition_transaction_id should be set when funding_account_id is provided"

    txn_id = asset["acquisition_transaction_id"]
    txn_r = client.get(f"/api/transactions/{txn_id}", headers=headers)
    assert txn_r.status_code == 200
    entries = txn_r.json()["entries"]
    total_debit  = sum(e.get("debit", 0) for e in entries)
    total_credit = sum(e.get("credit", 0) for e in entries)
    assert abs(total_debit - 15000.0) < 0.01, f"Expected debit total 15000, got {total_debit}"
    assert abs(total_credit - 15000.0) < 0.01, f"Expected credit total 15000, got {total_credit}"
```

- [ ] **Step 3: Run to confirm they fail**

```bash
cd backend && uv run pytest tests/test_asset_acquisition_jv.py -v 2>&1 | tail -20
```

Expected: `test_asset_with_funding_account_posts_acquisition_jv` FAIL (no `acquisition_transaction_id` in response).

- [ ] **Step 4: Update `routers/assets.py`**

Add `funding_account_id` to `AssetCreate` and implement acquisition JV in `create_asset`:

```python
class AssetCreate(BaseModel):
    name: str
    code: Optional[str] = None
    asset_account_id: int
    accum_depr_account_id: int
    depr_expense_account_id: int
    acquisition_date: str
    acquisition_cost: Decimal
    salvage_value: Decimal = Decimal("0")
    useful_life_months: int
    method: str = "straight_line"
    funding_account_id: Optional[int] = None  # Cash/Bank or AP to credit at acquisition
```

In `create_asset`, after the existing IDOR checks and before `session.add(asset)`:

```python
@router.post("", status_code=201)
def create_asset(session: SessionDep, user: WriteUserDep, body: AssetCreate):
    if body.method not in ("straight_line", "reducing_balance"):
        raise HTTPException(400, "method must be 'straight_line' or 'reducing_balance'")

    # Verify all three required account IDs belong to this tenant (IDOR protection)
    for aid in (body.asset_account_id, body.accum_depr_account_id, body.depr_expense_account_id):
        acc = session.exec(
            select(Account).where(Account.id == aid, Account.tenant_id == user.tenant_id)
        ).first()
        if not acc:
            raise HTTPException(400, f"Account {aid} not found for this tenant")

    # Validate funding account (optional) also belongs to this tenant
    if body.funding_account_id is not None:
        funding_acc = session.exec(
            select(Account).where(
                Account.id == body.funding_account_id, Account.tenant_id == user.tenant_id
            )
        ).first()
        if not funding_acc:
            raise HTTPException(400, f"Funding account {body.funding_account_id} not found for this tenant")

    asset_data = body.model_dump(exclude={"funding_account_id"})
    asset = FixedAsset(
        tenant_id=user.tenant_id,
        book_value=body.acquisition_cost,
        **asset_data,
    )
    session.add(asset)
    session.flush()  # get asset.id before conditional JV

    if body.funding_account_id is not None:
        txn = post_transaction(
            session, user,
            date=body.acquisition_date,
            description=f"Asset acquisition: {body.name}",
            entries=[
                EntryInput(account_id=body.asset_account_id, debit=D(body.acquisition_cost)),
                EntryInput(account_id=body.funding_account_id, credit=D(body.acquisition_cost)),
            ],
            voucher_type="JV",
            audit_entity_type="fixed_asset",
            audit_detail={"asset_id": asset.id, "name": body.name},
        )
        asset.acquisition_transaction_id = txn.id
        session.add(asset)

    log_audit(session, user, "CREATE", "fixed_asset", asset.id, {"name": body.name})
    session.commit()
    session.refresh(asset)
    return asset
```

- [ ] **Step 5: Run asset acquisition tests**

```bash
cd backend && uv run pytest tests/test_asset_acquisition_jv.py -v
```

Expected: both tests PASSED.

- [ ] **Step 6: Run full suite**

```bash
cd backend && uv run pytest -x -q 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 7: Add `funding_account_id` to the asset creation frontend form**

First locate the form file:

```bash
find /home/mbilal71/projects/Easy-Books/frontend/src -name "*.tsx" | xargs grep -l "acquisition_cost" 2>/dev/null
```

In that file, add an optional `Funding Account` select (same pattern as the analytic account picker in other forms):

```tsx
{/* Funding Account (optional — posts acquisition GL entry) */}
<div>
  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
    Funded By <span className="font-normal normal-case">(optional — posts acquisition JV)</span>
  </label>
  <select
    value={form.funding_account_id ?? ""}
    onChange={e => setForm(f => ({ ...f, funding_account_id: e.target.value || null }))}
    className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm"
  >
    <option value="">— no GL entry —</option>
    {accounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
  </select>
</div>
```

Also include `funding_account_id: form.funding_account_id ? parseInt(form.funding_account_id) : null` in the submit payload. Add `accounts` state if not already present (fetch from `/api/accounts?limit=500`).

- [ ] **Step 8: TypeScript check**

```bash
cd frontend && npm run lint 2>&1 | grep -E "error|Error" | head -20
```

Expected: no new errors.

- [ ] **Step 9: Commit**

```bash
git add backend/routers/assets.py backend/tests/test_asset_acquisition_jv.py
git add frontend/src/app/(dashboard)/assets  # or the exact form file
git commit -m "feat(assets): post acquisition GL entry when funding_account_id provided (IAS 16, #80 §3)"
```

---

## Final Verification

- [ ] **Run full test suite**

```bash
cd backend && uv run pytest -v 2>&1 | tail -30
```

Expected: all tests pass (no regressions; new tests for §1, §2, §3 pass).

- [ ] **TypeScript check**

```bash
cd frontend && npm run lint 2>&1 | grep -E "error TS|Error" | head -20
```

Expected: no errors.
