# Voucher-Type Selector on New Entry (#52 §4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users pick a voucher type on the manual New-Entry form so the posted transaction is classified and numbered under the right voucher series (instead of always JV).

**Architecture:** Backend is a one-line thread-through — `TransactionCreate` already inherits `voucher_type` (default `"JV"`) from `TransactionBase`; `create_transaction` just needs to pass `tx_data.voucher_type` to `post_transaction` (which already applies the per-type number series, #44). Frontend adds a `<select>` to `entry/page.tsx` and includes `voucher_type` in the POST body.

**Tech Stack:** FastAPI/SQLModel/pytest (backend); Next.js 16/React/TS (frontend). `VOUCHER_TYPES` from `@/lib/voucherTypes`.

**Spec:** `docs/superpowers/specs/2026-06-09-voucher-lov-new-entry-design.md`

**Base:** `main` @ v2.5.0. Branch: `feature/issue52-voucher-lov-entry`. **Run backend tests from `backend/` with `PYTHONPATH=.`.**

**Correction (found during execution):** `voucher_type` lives on the **`Transaction` table model** (`models.py:163`), **not** on `TransactionBase` — so `TransactionCreate` did NOT inherit it, and `tx_data.voucher_type` raised `AttributeError`. Task 1 therefore needs **two** changes: add `voucher_type: str = "JV"` to `TransactionCreate` in `models.py`, *and* thread it through `create_transaction`. (Both are committed.)

---

### Task 1: Backend — thread `voucher_type` through `create_transaction`

**Files:**
- Modify: `backend/routers/transactions.py` (`create_transaction`, ~lines 138-157)
- Test: `backend/tests/test_manual_voucher_type.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_manual_voucher_type.py`:

```python
"""Manual New-Entry can set the transaction's voucher_type (#52 §4)."""


def _accts(client, h):
    a = client.post("/api/accounts", headers=h, json={"code": "9610", "name": "Cash X", "type": "Asset"}).json()
    b = client.post("/api/accounts", headers=h, json={"code": "9620", "name": "Capital X", "type": "Equity"}).json()
    return a["id"], b["id"]


def test_manual_entry_honors_voucher_type(client, admin_headers):
    h = admin_headers
    dr, cr = _accts(client, h)
    r = client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01", "description": "cash receipt",
        "voucher_type": "CR",
        "entries": [
            {"account_id": dr, "debit": 100, "credit": 0},
            {"account_id": cr, "debit": 0, "credit": 100},
        ],
    })
    assert r.status_code in (200, 201), r.text
    tid = r.json()["id"]
    got = client.get("/api/reports/journal?limit=50", headers=h).json()
    row = next(x for x in got["items"] if x["transaction_id"] == tid)
    assert row["voucher_type"] == "CR", f"expected CR, got {row['voucher_type']}"


def test_manual_entry_defaults_to_jv_when_omitted(client, admin_headers):
    h = admin_headers
    dr, cr = _accts(client, h)
    r = client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01", "description": "adjustment",
        "entries": [
            {"account_id": dr, "debit": 50, "credit": 0},
            {"account_id": cr, "debit": 0, "credit": 50},
        ],
    })
    assert r.status_code in (200, 201), r.text
    tid = r.json()["id"]
    got = client.get("/api/reports/journal?limit=50", headers=h).json()
    row = next(x for x in got["items"] if x["transaction_id"] == tid)
    assert row["voucher_type"] == "JV"
```

- [ ] **Step 2: Run — verify the CR test FAILS, the JV test PASSES**

Run: `PYTHONPATH=. uv run pytest tests/test_manual_voucher_type.py -v`
Expected: `test_manual_entry_honors_voucher_type` FAILS (`expected CR, got JV` — the endpoint ignores the field today); `test_manual_entry_defaults_to_jv_when_omitted` PASSES.

- [ ] **Step 3: Thread `voucher_type` in `create_transaction`**

In `backend/routers/transactions.py`, in `create_transaction`, add the `voucher_type` argument to the `post_transaction(...)` call:

```python
    txn = post_transaction(
        session, user,
        date=tx_data.date,
        description=tx_data.description or "",
        entries=[
            EntryInput(account_id=e.account_id, debit=D(e.debit), credit=D(e.credit))
            for e in tx_data.entries
        ],
        reference=tx_data.reference,
        party=tx_data.party,
        payment_method=tx_data.payment_method,
        notes=tx_data.notes,
        voucher_type=tx_data.voucher_type or "JV",
        audit_entity_type="transaction",
    )
```

(Only the `voucher_type=tx_data.voucher_type or "JV",` line is added; everything else is unchanged. `voucher_type` is already on `tx_data` via `TransactionBase`.)

- [ ] **Step 4: Run — verify both PASS**

Run: `PYTHONPATH=. uv run pytest tests/test_manual_voucher_type.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Regression (transactions/posting)**

Run: `PYTHONPATH=. uv run pytest tests/ -k "transaction or posting or voucher" -q`
Expected: PASS — the default keeps existing callers on JV.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/transactions.py backend/tests/test_manual_voucher_type.py
git commit -m "feat(transactions): honor voucher_type on manual New-Entry (#52 §4)"
```

---

### Task 2: Frontend — voucher-type selector on the entry form

**Files:**
- Modify: `frontend/src/app/(dashboard)/entry/page.tsx`

- [ ] **Step 1: Add the import + state**

In `frontend/src/app/(dashboard)/entry/page.tsx`:
- Add the import near the others (after the `apiFetch` import, ~line 5):
```tsx
import { VOUCHER_TYPES } from "@/lib/voucherTypes"
```
- Add state next to the existing `date` state (~line 24):
```tsx
  const [voucherType, setVoucherType] = useState("JV")
```

- [ ] **Step 2: Add the selector to the header grid**

The header is a `grid grid-cols-1 sm:grid-cols-2` with Date and Description/Memo cells (~lines 111-137). Add a **third** cell for the voucher type. Change the grid to three columns and insert the select as the FIRST cell (before Date):

Change `<div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">` to `<div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">`, then insert this cell as the first child (immediately after that opening `<div>`):

```tsx
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">
                Voucher Type
              </label>
              <select
                value={voucherType}
                onChange={e => setVoucherType(e.target.value)}
                className="w-full px-3 py-2.5 bg-[#faf6ec] border border-transparent rounded-lg focus:ring-2 focus:ring-[#b8943f] focus:bg-white outline-none text-sm"
              >
                {Object.entries(VOUCHER_TYPES).map(([code, label]) => (
                  <option key={code} value={code}>{code} — {label}</option>
                ))}
              </select>
            </div>
```

(Date and Description remain the 2nd and 3rd cells.)

- [ ] **Step 3: Include `voucher_type` in the POST payload**

In `handleSubmit`, add `voucher_type` to the `payload` object (alongside `date`, `description`):

```tsx
    const payload = {
      date,
      description,
      voucher_type: voucherType,
      entries: rows
        .filter(r => r.account_id && (parseFloat(r.debit) > 0 || parseFloat(r.credit) > 0))
        .map(r => ({
          account_id: parseInt(r.account_id),
          debit: parseFloat(r.debit)  || 0,
          credit: parseFloat(r.credit) || 0,
        })),
    }
```

- [ ] **Step 4: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors in `entry/page.tsx`.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(dashboard)/entry/page.tsx"
git commit -m "feat(entry-ui): voucher-type selector on New Entry form (#52 §4)"
```

---

### Task 3: Final verification

- [ ] **Step 1: Backend suite slice + frontend lint**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_manual_voucher_type.py -q` → PASS.
Run: `cd frontend && npm run lint` → no new errors in `entry/page.tsx`.

- [ ] **Step 2: Manual smoke (if running the app)**

On `/entry`: the Voucher Type select defaults to JV; pick "CR — Cash Receipt", post a balanced entry, and confirm the resulting voucher is classified CR (visible in the journal / its number series).

- [ ] **Step 3: Done** — no commit needed if all green.

---

## Self-Review notes

- **Spec coverage:** §1 backend thread-through → Task 1 (no schema change needed — `voucher_type` already on `TransactionBase`); §2 frontend selector + payload → Task 2; §3 testing → Task 1 pytest + Task 2/3 lint.
- **Back-compat:** `voucher_type=tx_data.voucher_type or "JV"` keeps omitted requests on JV (asserted by `test_manual_entry_defaults_to_jv_when_omitted`); existing transaction tests unaffected.
- **Type consistency:** `voucherType` state ↔ `voucher_type` payload key ↔ `tx_data.voucher_type` backend field; selector options from `VOUCHER_TYPES` (`code → label`).
- **Test codes** use `9610`/`9620` to avoid colliding with the seeded hierarchical CoA.
