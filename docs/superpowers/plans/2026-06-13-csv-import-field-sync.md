# CSV Bulk Import Field-Sync Update — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the CSV bulk-import system in sync with all model fields added since it was written — accounts (parent_code/is_group/is_memo), products (category_name/is_deferred/recognition_months), transactions (voucher_type) — and fix two guide-page documentation bugs.

**Architecture:** Backend-only logic changes in `routers/imports.py` (extend sample CSVs, extend validators, rewrite `import_accounts` with a two-pass approach for parent wiring, extend `import_products` and `import_transactions`). Frontend changes are data-only: `ENTITY_FIELDS` constant in `CsvImportButton.tsx` and two text fixes in `guide/page.tsx`. New columns are always optional — old CSVs continue to work unchanged.

**Tech Stack:** FastAPI / SQLModel / SQLite (tests), Next.js 16, Tailwind CSS. Tests use pytest + FastAPI TestClient. Run tests with `cd backend && uv run pytest`.

---

## File map

| Action | File | What changes |
|--------|------|--------------|
| Modify | `backend/routers/imports.py` | `SAMPLE_CSVS`, `_validate_accounts`, `import_accounts` (two-pass), `_validate_products` (new sig), `import_products` (category + IFRS 15), `_validate_transactions`, `import_transactions` (voucher_type) |
| Create | `backend/tests/test_csv_imports.py` | 7 new tests |
| Modify | `frontend/src/components/CsvImportButton.tsx` | `ENTITY_FIELDS` constant |
| Modify | `frontend/src/app/(dashboard)/guide/page.tsx` | `CsvImportPanel` text fixes |

---

## Task 1: Accounts importer — parent_code, is_group, is_memo (TDD)

**Files:**
- Create: `backend/tests/test_csv_imports.py`
- Modify: `backend/routers/imports.py`

### Context

`import_accounts` currently creates flat accounts with no parent wiring. New fields on the `Account` model:
- `parent_id` — FK to parent Account (supports hierarchical CoA; added v2.5)
- `is_group` — bool; group accounts cannot be posted to (default `False`)
- `is_memo` — bool; excluded from A=L+E totals (default `False`)

The importer must use a **two-pass** approach: create all accounts first (collecting a `code→id` map), then wire `parent_id` from `parent_code` values. This handles forward references where a child row precedes its parent row in the file.

The `Account` list endpoint is `GET /api/accounts` (returns up to 200 accounts, fields include `id`, `code`, `name`, `type`, `parent_id`, `is_group`, `is_memo`).

- [ ] **Step 1: Create `test_csv_imports.py` with two failing account tests**

```python
# backend/tests/test_csv_imports.py
"""CSV bulk import — field-sync tests (accounts, products, transactions, compat)."""
import io
import csv as _csv_mod


def _csv(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    _csv_mod.writer(buf).writerows(rows)
    return buf.getvalue().encode()


def _upload(client, entity: str, rows: list[list[str]], headers: dict):
    data = _csv(rows)
    return client.post(
        f"/api/import/{entity}",
        headers=headers,
        files={"file": (f"{entity}.csv", data, "text/csv")},
    )


# ── Accounts ──────────────────────────────────────────────────────────────────

def test_import_accounts_parent_code(client, admin_headers):
    """parent_code in the CSV must wire parent_id after import."""
    h = admin_headers
    r = _upload(client, "accounts", [
        ["code", "name", "type", "parent_code", "is_group", "is_memo"],
        ["10",   "Assets Group",    "Asset", "",   "true",  "false"],
        ["1010", "Cash",            "Asset", "10", "false", "false"],
        ["1020", "Bank",            "Asset", "10", "false", "false"],
    ], h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 3, body
    # no hard errors (parent_code resolved from same batch)
    assert body["errors"] == [], body["errors"]

    accounts = client.get("/api/accounts", headers=h).json()
    by_code = {a["code"]: a for a in accounts}

    parent = by_code["10"]
    assert parent["is_group"] is True

    assert by_code["1010"]["parent_id"] == parent["id"]
    assert by_code["1020"]["parent_id"] == parent["id"]


def test_import_accounts_is_group_and_is_memo(client, admin_headers):
    """is_group and is_memo are written to the Account row."""
    h = admin_headers
    r = _upload(client, "accounts", [
        ["code", "name",           "type",    "parent_code", "is_group", "is_memo"],
        ["20",   "Memo Acct",      "Asset",   "",            "false",    "true"],
        ["21",   "Group Only",     "Expense", "",            "true",     "false"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2

    accounts = client.get("/api/accounts", headers=h).json()
    by_code = {a["code"]: a for a in accounts}

    assert by_code["20"]["is_memo"] is True
    assert by_code["20"]["is_group"] is False
    assert by_code["21"]["is_group"] is True
    assert by_code["21"]["is_memo"] is False
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd backend && uv run pytest tests/test_csv_imports.py::test_import_accounts_parent_code tests/test_csv_imports.py::test_import_accounts_is_group_and_is_memo -v
```

Expected: FAIL — `is_group` and `parent_id` are not set by the current importer.

- [ ] **Step 3: Update `SAMPLE_CSVS["accounts"]` in `imports.py`**

Replace the `"accounts"` entry in `SAMPLE_CSVS`:

```python
"accounts": [
    ["code", "name", "type", "parent_code", "is_group", "is_memo"],
    ["10",   "Assets",           "Asset",     "",  "true",  "false"],
    ["11",   "Current Assets",   "Asset",     "10","true",  "false"],
    ["1000", "Cash",             "Asset",     "11","false", "false"],
    ["1050", "Petty Cash",       "Asset",     "11","false", "false"],
    ["2210", "Accrued Liabilities", "Liability", "2", "false", "false"],
    ["5200", "Marketing Expense",   "Expense",   "5", "false", "false"],
],
```

- [ ] **Step 4: Update `_validate_accounts` to validate boolean columns**

Replace the existing `_validate_accounts` function:

```python
def _validate_accounts(rows: list[dict], session: Session, tenant_id: int):
    VALID_TYPES = {"Asset", "Liability", "Equity", "Revenue", "Expense"}
    VALID_BOOLS = {"true", "false", "1", "0", ""}
    valid, errors = 0, []
    for i, row in enumerate(rows, start=2):
        code = (row.get("code") or "").strip()
        name = (row.get("name") or "").strip()
        atype = (row.get("type") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        if atype not in VALID_TYPES:
            errors.append({"row": i, "message": f"type must be one of {sorted(VALID_TYPES)}"}); continue
        bool_err = None
        for bool_col in ("is_group", "is_memo"):
            val = (row.get(bool_col) or "").strip().lower()
            if val not in VALID_BOOLS:
                bool_err = {"row": i, "message": f"{bool_col} must be 'true' or 'false'"}
                break
        if bool_err:
            errors.append(bool_err); continue
        if code:
            existing = session.exec(
                select(Account).where(Account.code == code, Account.tenant_id == tenant_id)
            ).first()
            if existing:
                errors.append({"row": i, "message": f"account code '{code}' already exists"}); continue
        valid += 1
    return valid, errors
```

- [ ] **Step 5: Replace `import_accounts` with two-pass implementation**

Replace the existing `import_accounts` function completely:

```python
@router.post("/accounts")
async def import_accounts(
    file: UploadFile, session: SessionDep, user: WriteUserDep,
):
    VALID_TYPES = {"Asset", "Liability", "Equity", "Revenue", "Expense"}

    def _bool(val: str) -> bool:
        return (val or "").strip().lower() in ("true", "1")

    rows = _parse_csv(await file.read())
    _valid, errors = _validate_accounts(rows, session, user.tenant_id)

    # Seed code→id from pre-existing tenant accounts (for parent resolution)
    existing = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id, Account.code.isnot(None))
    ).all()
    code_to_id: dict[str, int] = {a.code: a.id for a in existing}

    imported = 0
    # Each entry: (account_id, parent_code_raw) — resolved in pass 2
    deferred_parents: list[tuple[int, str]] = []

    # ── Pass 1: create all accounts (no parent_id yet) ──────────────────────
    for row in rows:
        code = (row.get("code") or "").strip()
        name = (row.get("name") or "").strip()
        atype = (row.get("type") or "").strip()
        if not name or atype not in VALID_TYPES:
            continue
        if code and code in code_to_id:
            continue

        acct = Account(
            tenant_id=user.tenant_id,
            code=code or None,
            name=name,
            type=atype,
            is_group=_bool(row.get("is_group")),
            is_memo=_bool(row.get("is_memo")),
        )
        session.add(acct)
        session.flush()  # assigns acct.id without committing

        if code:
            code_to_id[code] = acct.id
        parent_code_raw = (row.get("parent_code") or "").strip()
        if parent_code_raw:
            deferred_parents.append((acct.id, parent_code_raw))
        imported += 1

    # ── Pass 2: wire parent_id ───────────────────────────────────────────────
    for acct_id, parent_code_raw in deferred_parents:
        parent_id = code_to_id.get(parent_code_raw)
        if parent_id is not None:
            acct = session.get(Account, acct_id)
            if acct:
                acct.parent_id = parent_id
        else:
            errors.append({
                "row": 0,
                "message": f"parent_code '{parent_code_raw}' not found — account created without parent",
            })

    session.commit()
    log_audit(session, user, "import", "Account", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
cd backend && uv run pytest tests/test_csv_imports.py::test_import_accounts_parent_code tests/test_csv_imports.py::test_import_accounts_is_group_and_is_memo -v
```

Expected: PASS

- [ ] **Step 7: Run the full suite to confirm no regressions**

```bash
cd backend && uv run pytest -v 2>&1 | tail -20
```

Expected: all previously-passing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add backend/routers/imports.py backend/tests/test_csv_imports.py
git commit -m "feat(imports): accounts — parent_code/is_group/is_memo support (two-pass)"
```

---

## Task 2: Products importer — category_name, is_deferred, recognition_months (TDD)

**Files:**
- Modify: `backend/tests/test_csv_imports.py`
- Modify: `backend/routers/imports.py`

### Context

`Product` fields added since the importer was written:
- `category_id` — FK to `ProductCategory`; the CSV uses `category_name` (resolved by name lookup)
- `is_deferred` — bool (IFRS 15); default `False`
- `recognition_months` — int; default `12`

The `_validate_products` function currently takes no `session`/`tenant_id` args — its signature must be extended to support the category-name DB lookup. The `validate_import` endpoint call must be updated to pass `session` and `user.tenant_id`.

Product categories are created via `POST /api/product-categories` (body: `{"name": "..."}` or `{"name": "...", "parent_id": <id>}`).

Product list endpoint: `GET /api/products` returns objects with `id`, `name`, `category_id`, `is_deferred`, `recognition_months`.

- [ ] **Step 1: Append three failing product tests to `test_csv_imports.py`**

Add after the accounts tests:

```python
# ── Products ──────────────────────────────────────────────────────────────────

def test_import_products_category_name(client, admin_headers):
    """category_name resolves to category_id on import."""
    h = admin_headers
    cat = client.post("/api/product-categories", json={"name": "Electronics"}, headers=h).json()

    r = _upload(client, "products", [
        ["code",    "name",     "unit", "product_type", "default_rate", "reorder_level", "category_name", "is_deferred", "recognition_months"],
        ["EL-001", "Gadget A", "pcs",  "stock",        "1500",         "10",            "Electronics",   "false",       ""],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    assert r.json()["errors"] == []

    products = client.get("/api/products", headers=h).json()
    items = products if isinstance(products, list) else products.get("items", products)
    gadget = next(p for p in items if p["code"] == "EL-001")
    assert gadget["category_id"] == cat["id"]


def test_import_products_unknown_category(client, admin_headers):
    """An unknown category_name causes a row-level error; no product is created."""
    h = admin_headers
    r = _upload(client, "products", [
        ["code",    "name",      "unit", "product_type", "default_rate", "reorder_level", "category_name", "is_deferred", "recognition_months"],
        ["XX-001", "Unknown Cat", "pcs", "stock",        "100",          "0",             "DoesNotExist",  "false",       ""],
    ], h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 0
    assert len(body["errors"]) == 1
    assert "DoesNotExist" in body["errors"][0]["message"]


def test_import_products_is_deferred(client, admin_headers):
    """is_deferred=true and recognition_months=6 are written to the Product row."""
    h = admin_headers
    r = _upload(client, "products", [
        ["code",    "name",               "unit", "product_type", "default_rate", "reorder_level", "category_name", "is_deferred", "recognition_months"],
        ["SV-001", "Annual Maintenance", "hrs",  "service",      "50000",        "0",             "",              "true",        "6"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    assert r.json()["errors"] == []

    products = client.get("/api/products", headers=h).json()
    items = products if isinstance(products, list) else products.get("items", products)
    svc = next(p for p in items if p["code"] == "SV-001")
    assert svc["is_deferred"] is True
    assert svc["recognition_months"] == 6
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && uv run pytest tests/test_csv_imports.py::test_import_products_category_name tests/test_csv_imports.py::test_import_products_unknown_category tests/test_csv_imports.py::test_import_products_is_deferred -v
```

Expected: FAIL — category_id, is_deferred, recognition_months not set by current importer.

- [ ] **Step 3: Add `ProductCategory` to the top-level imports in `imports.py`**

Find line 9 in `backend/routers/imports.py`:

```python
from models import Account, Customer, Product, Vendor
```

Replace with:

```python
from models import Account, Customer, Product, ProductCategory, Vendor
```

Remove the `from models import ProductCategory` lines from inside `_validate_products` and `import_products` in subsequent steps — the top-level import covers both.

- [ ] **Step 4: Update `SAMPLE_CSVS["products"]`**

Replace the `"products"` entry in `SAMPLE_CSVS`:

```python
"products": [
    ["code",    "name",                    "unit", "product_type", "default_rate", "reorder_level", "category_name", "is_deferred", "recognition_months"],
    ["PRD-001", "Widget A",                "pcs",  "stock",        "1500",         "50",            "Electronics",   "false",       ""],
    ["PRD-002", "Annual Support Contract", "hrs",  "service",      "50000",        "0",             "Services",      "true",        "12"],
    ["PRD-003", "Raw Cotton",              "kg",   "stock",        "350",          "200",           "",              "false",       ""],
],
```

- [ ] **Step 5: Update `_validate_products` signature and add category + IFRS 15 validation**

The function currently has signature `_validate_products(rows: list[dict])`. Replace the entire function with a version that takes `session` and `tenant_id`:

```python
def _validate_products(rows: list[dict], session: Session, tenant_id: int):
    # ProductCategory already imported at top of file
    VALID_TYPES = {"stock", "service"}
    VALID_UNITS = {"pcs", "kg", "mtr", "hrs", "ltr", "box", "doz"}
    VALID_BOOLS = {"true", "false", "1", "0", ""}

    cats = session.exec(
        select(ProductCategory).where(ProductCategory.tenant_id == tenant_id)
    ).all()
    cat_names = {c.name.lower() for c in cats}

    valid, errors = 0, []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        ptype = (row.get("product_type") or "service").strip().lower()
        if ptype not in VALID_TYPES:
            errors.append({"row": i, "message": "product_type must be 'stock' or 'service'"}); continue
        unit = (row.get("unit") or "pcs").strip().lower()
        if unit not in VALID_UNITS:
            errors.append({"row": i, "message": f"unit must be one of {sorted(VALID_UNITS)}"}); continue
        try:
            D(row.get("default_rate") or "0")
            D(row.get("reorder_level") or "0")
        except Exception:
            errors.append({"row": i, "message": "default_rate and reorder_level must be numbers"}); continue
        cat_name_raw = (row.get("category_name") or "").strip()
        if cat_name_raw and cat_name_raw.lower() not in cat_names:
            errors.append({"row": i, "message": f"category '{cat_name_raw}' not found"}); continue
        is_def_raw = (row.get("is_deferred") or "").strip().lower()
        if is_def_raw not in VALID_BOOLS:
            errors.append({"row": i, "message": "is_deferred must be 'true' or 'false'"}); continue
        rm_raw = (row.get("recognition_months") or "").strip()
        if rm_raw:
            try:
                if int(rm_raw) < 1:
                    raise ValueError()
            except (ValueError, TypeError):
                errors.append({"row": i, "message": "recognition_months must be a positive integer"}); continue
        valid += 1
    return valid, errors
```

- [ ] **Step 6: Update the `validate_import` endpoint to pass `session` + `tenant_id` for products**

In `validate_import`, change the `elif entity == "products":` branch from:

```python
    elif entity == "products":
        valid, errors = _validate_products(rows)
```

To:

```python
    elif entity == "products":
        valid, errors = _validate_products(rows, session, user.tenant_id)
```

- [ ] **Step 7: Replace `import_products` with updated inline logic**

Replace the existing `import_products` function completely:

```python
@router.post("/products")
async def import_products(
    file: UploadFile, session: SessionDep, user: WriteUserDep,
):
    # ProductCategory already imported at top of file
    VALID_TYPES = {"stock", "service"}
    VALID_UNITS = {"pcs", "kg", "mtr", "hrs", "ltr", "box", "doz"}

    cats = session.exec(
        select(ProductCategory).where(ProductCategory.tenant_id == user.tenant_id)
    ).all()
    cat_name_to_id: dict[str, int] = {c.name.lower(): c.id for c in cats}

    rows = _parse_csv(await file.read())
    imported, errors = 0, []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        ptype = (row.get("product_type") or "service").strip().lower()
        if ptype not in VALID_TYPES:
            errors.append({"row": i, "message": "product_type must be 'stock' or 'service'"}); continue
        unit = (row.get("unit") or "pcs").strip().lower()
        if unit not in VALID_UNITS:
            unit = "pcs"
        try:
            rate = D(row.get("default_rate") or "0")
            reorder = D(row.get("reorder_level") or "0")
        except Exception:
            errors.append({"row": i, "message": "default_rate and reorder_level must be numbers"}); continue

        # category_name → category_id
        category_id = None
        cat_name_raw = (row.get("category_name") or "").strip()
        if cat_name_raw:
            category_id = cat_name_to_id.get(cat_name_raw.lower())
            if category_id is None:
                errors.append({"row": i, "message": f"category '{cat_name_raw}' not found"}); continue

        # IFRS 15 fields
        is_deferred = (row.get("is_deferred") or "").strip().lower() in ("true", "1")
        rm_raw = (row.get("recognition_months") or "").strip()
        try:
            recognition_months = int(rm_raw) if rm_raw else 12
            if recognition_months < 1:
                raise ValueError()
        except (ValueError, TypeError):
            errors.append({"row": i, "message": "recognition_months must be a positive integer"}); continue

        session.add(Product(
            tenant_id=user.tenant_id,
            code=(row.get("code") or "").strip() or None,
            name=name,
            unit=unit,
            product_type=ptype,
            default_rate=rate,
            reorder_level=reorder,
            category_id=category_id,
            is_deferred=is_deferred,
            recognition_months=recognition_months,
            is_active=True,
        ))
        imported += 1

    session.commit()
    log_audit(session, user, "import", "Product", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}
```

- [ ] **Step 8: Run product tests — verify they pass**

```bash
cd backend && uv run pytest tests/test_csv_imports.py::test_import_products_category_name tests/test_csv_imports.py::test_import_products_unknown_category tests/test_csv_imports.py::test_import_products_is_deferred -v
```

Expected: PASS

- [ ] **Step 9: Run full suite**

```bash
cd backend && uv run pytest -v 2>&1 | tail -20
```

Expected: all previously-passing tests still pass.

- [ ] **Step 10: Commit**

```bash
git add backend/routers/imports.py backend/tests/test_csv_imports.py
git commit -m "feat(imports): products — category_name/is_deferred/recognition_months support"
```

---

## Task 3: Transactions importer — voucher_type (TDD)

**Files:**
- Modify: `backend/tests/test_csv_imports.py`
- Modify: `backend/routers/imports.py`

### Context

`post_transaction` already accepts `voucher_type: str = "JV"`. The current importer always passes the default. The fix:
1. Add `voucher_type` to `SAMPLE_CSVS["transactions"]`
2. Add `voucher_type` validation to `_validate_transactions`
3. Resolve `voucher_type` per group in `import_transactions` and pass it through

**Grouping key stays `(date, description)`.** `voucher_type` is taken from the first non-empty value among a group's rows. An unrecognised type is a group-level error.

Valid voucher types: `{"JV", "SL", "PU", "CR", "CP", "CN", "DN"}`

Verification: use `GET /api/reports/journal?limit=50` — returns `{items: [{transaction_id, voucher_type, ...}]}`.

- [ ] **Step 1: Append a failing transaction test to `test_csv_imports.py`**

The test needs two pre-existing accounts to form a balanced JV. Add after the product tests:

```python
# ── Transactions ──────────────────────────────────────────────────────────────

def test_import_transactions_voucher_type(client, admin_headers):
    """A CSV with voucher_type=SL posts the transaction with that voucher series."""
    h = admin_headers
    # Create two leaf accounts for a balanced JV
    ar = client.post("/api/accounts", headers=h, json={"code": "9810", "name": "AR Test", "type": "Asset"}).json()
    rev = client.post("/api/accounts", headers=h, json={"code": "9820", "name": "Rev Test", "type": "Revenue"}).json()

    r = _upload(client, "transactions", [
        ["date",       "description", "account_code", "debit", "credit", "voucher_type"],
        ["2025-03-01", "Test sale",   "9810",         "5000",  "0",      "SL"],
        ["2025-03-01", "Test sale",   "9820",         "0",     "5000",   "SL"],
    ], h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 1, body
    assert body["errors"] == []

    journal = client.get("/api/reports/journal?limit=50", headers=h).json()
    rows = journal if isinstance(journal, list) else journal.get("items", journal)
    assert any(row["voucher_type"] == "SL" for row in rows), rows
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && uv run pytest tests/test_csv_imports.py::test_import_transactions_voucher_type -v
```

Expected: FAIL — the test expects `voucher_type == "SL"` but the importer always posts `"JV"`.

- [ ] **Step 3: Update `SAMPLE_CSVS["transactions"]`**

Replace the `"transactions"` entry in `SAMPLE_CSVS`:

```python
"transactions": [
    ["date",       "description",   "account_code", "debit", "credit", "voucher_type"],
    ["2025-01-01", "Cash sale",     "1000",         "5000",  "0",      "SL"],
    ["2025-01-01", "Cash sale",     "4000",         "0",     "5000",   "SL"],
    ["2025-01-02", "Office supplies","5100",        "1500",  "0",      "CP"],
    ["2025-01-02", "Office supplies","1000",        "0",     "1500",   "CP"],
],
```

- [ ] **Step 4: Update `_validate_transactions` to validate voucher_type per group**

In `_validate_transactions`, add the following block immediately after the `groups` dict is built and before the per-group validation loop. The constant and check go at the top of the per-group loop:

Replace the entire `_validate_transactions` function with:

```python
def _validate_transactions(rows: list[dict], session: Session, tenant_id: int):
    VALID_VOUCHER_TYPES = {"JV", "SL", "PU", "CR", "CP", "CN", "DN"}
    errors: list[dict] = []
    groups: dict[tuple, list] = {}
    for i, row in enumerate(rows, start=2):
        date = (row.get("date") or "").strip()
        desc = (row.get("description") or "").strip()
        if not date or not desc:
            errors.append({"row": i, "message": "date and description are required"}); continue
        groups.setdefault((date, desc), []).append((i, row))

    valid = 0
    for (_date, _desc), group_rows in groups.items():
        group_errors = []

        # Validate voucher_type (from first non-empty value in group)
        for _, row in group_rows:
            vt = (row.get("voucher_type") or "").strip().upper()
            if vt:
                if vt not in VALID_VOUCHER_TYPES:
                    group_errors.append({
                        "row": group_rows[0][0],
                        "message": f"voucher_type '{vt}' is not valid; must be one of {sorted(VALID_VOUCHER_TYPES)}",
                    })
                break

        for i, row in group_rows:
            acct_code = (row.get("account_code") or "").strip()
            if not acct_code:
                group_errors.append({"row": i, "message": "account_code is required"}); continue
            acct = session.exec(
                select(Account).where(Account.tenant_id == tenant_id, Account.code == acct_code)
            ).first()
            if not acct:
                group_errors.append({"row": i, "message": f"account code '{acct_code}' not found"}); continue
            try:
                D(row.get("debit") or "0")
                D(row.get("credit") or "0")
            except Exception:
                group_errors.append({"row": i, "message": "debit and credit must be numbers"}); continue
        if group_errors:
            errors.extend(group_errors)
        else:
            valid += 1
    return valid, errors
```

- [ ] **Step 5: Update `import_transactions` to resolve and pass voucher_type**

Replace the entire `import_transactions` function with:

```python
@router.post("/transactions")
async def import_transactions(
    file: UploadFile, session: SessionDep, user: WriteUserDep,
):
    VALID_VOUCHER_TYPES = {"JV", "SL", "PU", "CR", "CP", "CN", "DN"}
    rows = _parse_csv(await file.read())
    errors: list[dict] = []
    imported = 0

    groups: dict[tuple, list] = {}
    for i, row in enumerate(rows, start=2):
        date = (row.get("date") or "").strip()
        desc = (row.get("description") or "").strip()
        if not date or not desc:
            errors.append({"row": i, "message": "date and description are required"}); continue
        groups.setdefault((date, desc), []).append((i, row))

    for (date, desc), group_rows in groups.items():
        # Resolve voucher_type from first non-empty value in group
        voucher_type = "JV"
        invalid_vt = False
        for _, row in group_rows:
            vt = (row.get("voucher_type") or "").strip().upper()
            if vt:
                if vt not in VALID_VOUCHER_TYPES:
                    errors.append({
                        "row": group_rows[0][0],
                        "message": f"voucher_type '{vt}' is not valid; must be one of {sorted(VALID_VOUCHER_TYPES)}",
                    })
                    invalid_vt = True
                else:
                    voucher_type = vt
                break
        if invalid_vt:
            continue

        entries: list[EntryInput] = []
        group_errors = []
        for i, row in group_rows:
            acct_code = (row.get("account_code") or "").strip()
            if not acct_code:
                group_errors.append({"row": i, "message": "account_code is required"}); continue
            acct = session.exec(
                select(Account).where(
                    Account.tenant_id == user.tenant_id, Account.code == acct_code
                )
            ).first()
            if not acct:
                group_errors.append({"row": i, "message": f"account code '{acct_code}' not found"}); continue
            try:
                dr = D(row.get("debit") or "0")
                cr = D(row.get("credit") or "0")
            except Exception:
                group_errors.append({"row": i, "message": "debit and credit must be numbers"}); continue
            if dr == 0 and cr == 0:
                continue
            entries.append(EntryInput(account_id=acct.id, debit=dr, credit=cr))

        if group_errors:
            errors.extend(group_errors); continue
        if not entries:
            continue
        try:
            post_transaction(
                session, user,
                date=date, description=desc, entries=entries,
                voucher_type=voucher_type,
                audit_entity_type="transaction_import",
            )
            imported += 1
        except HTTPException as ex:
            errors.append({"row": group_rows[0][0], "message": ex.detail})

    session.commit()
    log_audit(session, user, "import", "Transaction", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}
```

- [ ] **Step 6: Run transaction test — verify it passes**

```bash
cd backend && uv run pytest tests/test_csv_imports.py::test_import_transactions_voucher_type -v
```

Expected: PASS

- [ ] **Step 7: Run full suite**

```bash
cd backend && uv run pytest -v 2>&1 | tail -20
```

Expected: all previously-passing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add backend/routers/imports.py backend/tests/test_csv_imports.py
git commit -m "feat(imports): transactions — voucher_type support"
```

---

## Task 4: Backward compatibility tests

**Files:**
- Modify: `backend/tests/test_csv_imports.py`

### Context

Old CSVs (without the new columns) must still import cleanly. This task adds a single test that covers all five entities using their original column sets.

- [ ] **Step 1: Append the backward-compat test to `test_csv_imports.py`**

Add after the transaction test:

```python
# ── Backward compatibility ────────────────────────────────────────────────────

def test_import_backward_compat_all_entities(client, admin_headers):
    """Old-style CSVs (no new columns) import cleanly for all five entities."""
    h = admin_headers

    # Accounts — original 3-column format
    r = _upload(client, "accounts", [
        ["code", "name",              "type"],
        ["8810", "Compat Cash",       "Asset"],
        ["8820", "Compat Equity",     "Equity"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2, r.json()
    assert r.json()["errors"] == []

    # Customers — original 5-column format
    r = _upload(client, "customers", [
        ["name",          "email",              "phone",          "address",  "opening_balance"],
        ["Compat Cust",   "compat@example.com", "0300-0000000",   "Karachi",  "0"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1

    # Vendors — original 5-column format
    r = _upload(client, "vendors", [
        ["name",          "email",               "phone",         "address",    "opening_balance"],
        ["Compat Vend",   "vcompat@example.com", "0311-0000000",  "Lahore",     "0"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1

    # Products — original 6-column format
    r = _upload(client, "products", [
        ["code",    "name",         "unit", "product_type", "default_rate", "reorder_level"],
        ["CP-001", "Compat Widget", "pcs",  "stock",        "100",          "5"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1

    # Transactions — original 5-column format
    acct1 = client.post("/api/accounts", headers=h, json={"code": "9910", "name": "Compat Cash Acct", "type": "Asset"}).json()
    acct2 = client.post("/api/accounts", headers=h, json={"code": "9920", "name": "Compat Eq Acct", "type": "Equity"}).json()
    r = _upload(client, "transactions", [
        ["date",       "description",  "account_code", "debit", "credit"],
        ["2025-06-01", "Compat entry", "9910",         "1000",  "0"],
        ["2025-06-01", "Compat entry", "9920",         "0",     "1000"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    assert r.json()["errors"] == []
```

- [ ] **Step 2: Run the backward-compat test**

```bash
cd backend && uv run pytest tests/test_csv_imports.py::test_import_backward_compat_all_entities -v
```

Expected: PASS — old-format CSVs must work unchanged.

- [ ] **Step 3: Run the full test file**

```bash
cd backend && uv run pytest tests/test_csv_imports.py -v
```

Expected: all 7 tests in the file pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_csv_imports.py
git commit -m "test(imports): backward-compat coverage for all five entities"
```

---

## Task 5: Frontend — update `ENTITY_FIELDS` in `CsvImportButton.tsx`

**Files:**
- Modify: `frontend/src/components/CsvImportButton.tsx`

### Context

`ENTITY_FIELDS` drives the "Required columns" panel shown in the import dialog before upload (lines 40–75). Three entities need new optional field entries. No structural change to the component.

- [ ] **Step 1: Replace the `ENTITY_FIELDS` constant**

In `frontend/src/components/CsvImportButton.tsx`, replace the entire `ENTITY_FIELDS` constant (lines 40–75) with:

```typescript
const ENTITY_FIELDS: Record<ImportEntity, { field: string; required: boolean; note?: string }[]> = {
  transactions: [
    { field: "date",         required: true,  note: "YYYY-MM-DD" },
    { field: "description",  required: true,  note: "rows with same date+description = 1 transaction" },
    { field: "account_code", required: true,  note: "must exist in Chart of Accounts" },
    { field: "debit",        required: true,  note: "numeric, 0 if not applicable" },
    { field: "credit",       required: true,  note: "numeric, 0 if not applicable" },
    { field: "voucher_type", required: false, note: "JV / SL / PU / CR / CP / CN / DN (default: JV)" },
  ],
  accounts: [
    { field: "code",        required: false, note: "optional unique code" },
    { field: "name",        required: true },
    { field: "type",        required: true,  note: "Asset / Liability / Equity / Revenue / Expense" },
    { field: "parent_code", required: false, note: "code of parent account (for hierarchical CoA)" },
    { field: "is_group",    required: false, note: "true / false — group accounts cannot be posted to" },
    { field: "is_memo",     required: false, note: "true / false — excluded from A=L+E totals" },
  ],
  customers: [
    { field: "name",            required: true },
    { field: "email",           required: false },
    { field: "phone",           required: false },
    { field: "address",         required: false },
    { field: "opening_balance", required: false, note: "numeric, default 0" },
  ],
  vendors: [
    { field: "name",            required: true },
    { field: "email",           required: false },
    { field: "phone",           required: false },
    { field: "address",         required: false },
    { field: "opening_balance", required: false, note: "numeric, default 0" },
  ],
  products: [
    { field: "code",               required: false },
    { field: "name",               required: true },
    { field: "unit",               required: false, note: "pcs / kg / mtr / hrs / ltr / box / doz" },
    { field: "product_type",       required: false, note: "stock or service (default: service)" },
    { field: "default_rate",       required: false, note: "numeric" },
    { field: "reorder_level",      required: false, note: "numeric, only for stock" },
    { field: "category_name",      required: false, note: "must match an existing product category name" },
    { field: "is_deferred",        required: false, note: "true / false — IFRS 15 deferred revenue" },
    { field: "recognition_months", required: false, note: "integer, only when is_deferred=true (default 12)" },
  ],
}
```

- [ ] **Step 2: Build the frontend to verify no TypeScript errors**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds (pre-existing 2 errors / 14 warnings at baseline; no new errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CsvImportButton.tsx
git commit -m "feat(imports): update ENTITY_FIELDS — accounts/products/transactions new columns"
```

---

## Task 6: Guide page — fix CsvImportPanel documentation

**Files:**
- Modify: `frontend/src/app/(dashboard)/guide/page.tsx`

### Context

Two bugs in `CsvImportPanel` (around line 1131):
1. The Products row says `"name, type, unit_price"` — `unit_price` does not exist; the field is `default_rate`.
2. Transactions are importable but not listed in the guide table at all.

- [ ] **Step 1: Fix the guide table in `CsvImportPanel`**

In `frontend/src/app/(dashboard)/guide/page.tsx`, find the table data array inside `CsvImportPanel` (around line 1130). Replace this block:

```typescript
            {[
              ["Products",    "Products page",         "name, type, unit_price"],
              ["Customers",   "Customers page",        "name, email"],
              ["Vendors",     "Vendors page",          "name, email"],
              ["Accounts",    "Chart of Accounts",     "code, name, type"],
            ].map(([entity, where, fields]) => (
```

With:

```typescript
            {[
              ["Transactions", "Journal page",      "date, description, account_code, debit, credit"],
              ["Accounts",     "Chart of Accounts", "code, name, type · optional: parent_code, is_group, is_memo"],
              ["Products",     "Products page",     "name, product_type, default_rate · optional: category_name, is_deferred"],
              ["Customers",    "Customers page",    "name · optional: email, phone, opening_balance"],
              ["Vendors",      "Vendors page",      "name · optional: email, phone, opening_balance"],
            ].map(([entity, where, fields]) => (
```

- [ ] **Step 2: Build the frontend**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/(dashboard)/guide/page.tsx
git commit -m "fix(guide): correct CSV import table — fix unit_price bug, add Transactions row"
```

---

## Final verification

- [ ] **Run the complete backend suite one last time**

```bash
cd backend && uv run pytest -v 2>&1 | tail -30
```

Expected: all tests pass (existing suite + 7 new tests in `test_csv_imports.py`).

- [ ] **Run the frontend build one last time**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: no new TypeScript/lint errors beyond the pre-existing baseline.
