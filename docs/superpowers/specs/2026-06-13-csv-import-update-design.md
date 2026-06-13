# CSV Bulk Import — Field Sync Update Design

**Date:** 2026-06-13
**Status:** Approved
**Scope:** Backend `routers/imports.py` + Frontend `CsvImportButton.tsx` + Frontend `guide/page.tsx`

## Problem

The CSV bulk-import system covers five entities (accounts, customers, vendors, products, transactions).
Since it was written, several new model fields have shipped but were never reflected in the sample
files, import handlers, UI field hints, or the in-app guide. Consequences:

1. **Accounts** — `parent_code` / `is_group` / `is_memo` added in v2.5 (hierarchical CoA). Users
   importing a full CoA get a flat, unparented list; group accounts cannot be created via import.
2. **Products** — `category_id` (2-level taxonomy), `is_deferred` + `recognition_months` (IFRS 15)
   added post-launch. Categories are silently ignored; deferred-revenue products cannot be bulk-created.
3. **Transactions** — `voucher_type` (SL/PU/CR/CP/CN/DN) is accepted by `post_transaction` but the
   importer always passes `"JV"`.
4. **Guide page bug** — Products "required fields" text says `unit_price` (no such field; correct
   field is `default_rate`). Transactions import not listed in the guide table at all.

## Design (approved)

### Backward compatibility

All new CSV columns are **optional**. A CSV produced before this change imports identically.

---

## Section 1 — Backend `routers/imports.py`

### 1.1 `SAMPLE_CSVS` updates

**`accounts`** — add three optional columns:

```
code, name, type, parent_code, is_group, is_memo
1,    Assets,           Asset,     ,     true,  false
11,   Current Assets,   Asset,     1,    true,  false
1000, Cash,             Asset,     11,   false, false
1050, Petty Cash,       Asset,     11,   false, false
2210, Accrued Liabilities, Liability, 2, false, false
5200, Marketing Expense,   Expense,   5, false, false
```

**`products`** — add three optional columns:

```
code,    name,                     unit, product_type, default_rate, reorder_level, category_name, is_deferred, recognition_months
PRD-001, Widget A,                 pcs,  stock,        1500,         50,            Electronics,   false,
PRD-002, Annual Support Contract,  hrs,  service,      50000,        0,             Services,      true,        12
PRD-003, Raw Cotton,               kg,   stock,        350,          200,           ,              false,
```

**`transactions`** — add one optional column:

```
date,       description,    account_code, debit, credit, voucher_type
2025-01-01, Cash sale,      1000,         5000,  0,      SL
2025-01-01, Cash sale,      4000,         0,     5000,   SL
2025-01-02, Office supplies,5100,         1500,  0,      CP
2025-01-02, Office supplies,1000,         0,     1500,   CP
```

### 1.2 `import_accounts` — two-pass logic

Follow the same pattern as `db.py`'s `seed_data`:

**Pass 1** — create all Account rows without `parent_id`:
- Read `is_group` (`"true"/"1"` → `True`, else `False`), `is_memo` (same)
- Omit `parent_id` on creation
- Build a `code → Account.id` map covering both the newly-inserted rows and pre-existing accounts in the tenant

**Pass 2** — wire parents:
- For each row where `parent_code` is non-empty, look up the parent Account by code in the map
- If found: `session.exec(update Account where id = new_id set parent_id = parent_account_id)`
- If not found: append a row-level warning (not a hard error — the account is already created)

### 1.3 `import_products` — category + IFRS 15 fields

Before the main loop: build a `name.lower() → ProductCategory.id` map for this tenant (both active and
inactive categories — import should be permissive).

In the main loop:
- `category_name`: strip, lowercase, look up in map. Found → set `category_id`. Not found but
  non-empty → row-level error, skip row.
- `is_deferred`: `"true"/"1"` → `True`, else `False`.
- `recognition_months`: `int(value)` if non-empty and `is_deferred=True`, else default `12`.

### 1.4 `import_transactions` — `voucher_type` per group

Group key stays `(date, description)`. When iterating group rows, take the **first non-empty**
`voucher_type` value from the group (all rows in one JV group should agree). Fall back to `"JV"`.

Valid values: `{"JV", "SL", "PU", "CR", "CP", "CN", "DN"}`. Invalid value → row-level error for the
whole group (not silently ignored).

Pass the resolved `voucher_type` to `post_transaction(..., voucher_type=voucher_type)`.

### 1.5 Validator updates

**`_validate_accounts`**:
- Accept `is_group` and `is_memo` columns: if present, validate they are `"true"/"false"/"1"/"0"`.
- Do **not** validate `parent_code` in the pre-flight validator — the parent may be in the same
  import batch, so resolution happens at import time only.

**`_validate_products`**:
- If `category_name` is non-empty: verify it exists in the tenant's `ProductCategory` table. Unknown
  category → validation error for that row.
- If `is_deferred` is present: validate it is a valid boolean string.
- If `recognition_months` is present: validate it is a positive integer.

**`_validate_transactions`** (no change to existing logic):
- New: after grouping, if a group has a non-empty `voucher_type` that is not in the valid set,
  add a group-level error.

---

## Section 2 — Frontend `CsvImportButton.tsx`

Update `ENTITY_FIELDS` constant only — no structural change:

**`accounts`** — add after `type`:
```ts
{ field: "parent_code",  required: false, note: "code of parent account (for hierarchical CoA)" },
{ field: "is_group",     required: false, note: "true / false — group accounts cannot be posted to" },
{ field: "is_memo",      required: false, note: "true / false — excluded from A=L+E totals" },
```

**`products`** — add after `reorder_level`:
```ts
{ field: "category_name",      required: false, note: "must match an existing product category name" },
{ field: "is_deferred",        required: false, note: "true / false — IFRS 15 deferred revenue" },
{ field: "recognition_months", required: false, note: "integer, only when is_deferred=true (default 12)" },
```

**`transactions`** — add after `credit`:
```ts
{ field: "voucher_type", required: false, note: "JV / SL / PU / CR / CP / CN / DN (default: JV)" },
```

---

## Section 3 — Frontend `guide/page.tsx`

Two targeted fixes inside `CsvImportPanel`:

1. **Products row** — change required fields text:
   `"name, type, unit_price"` → `"code, name, product_type, default_rate"`

2. **Add Transactions row** to the guide table:
   `["Transactions", "Journal page", "date, description, account_code, debit, credit"]`

---

## Section 4 — Tests (`backend/tests/test_imports.py`)

Seven new test cases (all isolated, no fixture reuse with existing tests):

| # | Test | What it asserts |
|---|------|-----------------|
| 1 | `test_import_accounts_with_parent_code` | Creates 3 accounts (1 group, 2 leaves with `parent_code`); asserts `parent_id` is wired correctly after import |
| 2 | `test_import_accounts_is_group` | Creates account with `is_group=true`; asserts `account.is_group is True` |
| 3 | `test_import_products_category_name` | Creates product with `category_name`; asserts `product.category_id` resolves to the correct category |
| 4 | `test_import_products_unknown_category` | CSV with unknown `category_name`; asserts row-level error, 0 imported |
| 5 | `test_import_products_is_deferred` | Creates product with `is_deferred=true, recognition_months=6`; asserts both fields |
| 6 | `test_import_transactions_voucher_type` | Imports a 2-line SL JV; asserts `transaction.voucher_type == "SL"` |
| 7 | `test_import_backward_compat` | Imports old-style CSVs without new columns for all 5 entities; asserts all import cleanly |

---

## Error handling

- Unknown `category_name`: row-level error, row skipped, rest of file continues.
- Invalid `voucher_type`: group-level error, group skipped, rest of file continues.
- `parent_code` not found after both passes: row-level warning appended to the errors list, account
  already created (without parent) — not a hard rollback.
- All new fields missing (old CSV): default behaviour, no error.

## What is NOT changing

- `customers` and `vendors` imports — their models have no new fields since the importer was written.
- The `CsvImportButton` component UX flow (3-step upload/review/done) — unchanged.
- The `bank_imports` import path — separate system, out of scope.
- No new import entities (invoices, bills) — out of scope for this change.
