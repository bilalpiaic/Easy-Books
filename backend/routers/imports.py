"""CSV bulk imports (accounts / customers / vendors / products / transactions)."""
import csv
import io

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from models import Account, Customer, Product, Vendor
from services.money import D
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/import", tags=["import"])


SAMPLE_CSVS: dict[str, list[list[str]]] = {
    "transactions": [
        ["date", "description", "account_code", "debit", "credit"],
        ["2025-01-01", "Cash sale", "1000", "5000", "0"],
        ["2025-01-01", "Cash sale", "4000", "0", "5000"],
        ["2025-01-02", "Office supplies", "5100", "1500", "0"],
        ["2025-01-02", "Office supplies", "1000", "0", "1500"],
    ],
    "accounts": [
        ["code", "name", "type", "parent_code", "is_group", "is_memo"],
        ["10",   "Assets",           "Asset",     "",  "true",  "false"],
        ["11",   "Current Assets",   "Asset",     "10","true",  "false"],
        ["1000", "Cash",             "Asset",     "11","false", "false"],
        ["1050", "Petty Cash",       "Asset",     "11","false", "false"],
        ["2210", "Accrued Liabilities", "Liability", "2", "false", "false"],
        ["5200", "Marketing Expense",   "Expense",   "5", "false", "false"],
    ],
    "customers": [
        ["name", "email", "phone", "address", "opening_balance"],
        ["Ahmed Traders", "ahmed@example.com", "0300-1234567", "Karachi", "0"],
        ["Bilal Enterprises", "bilal@example.com", "0321-9876543", "Lahore", "50000"],
    ],
    "vendors": [
        ["name", "email", "phone", "address", "opening_balance"],
        ["Ali Suppliers", "ali@supplier.com", "0311-1111111", "Islamabad", "0"],
        ["Khan & Sons", "khan@supplier.com", "0333-2222222", "Faisalabad", "25000"],
    ],
    "products": [
        ["code", "name", "unit", "product_type", "default_rate", "reorder_level"],
        ["PRD-001", "Widget A", "pcs", "stock", "1500", "50"],
        ["PRD-002", "Consulting Hour", "hrs", "service", "5000", "0"],
        ["PRD-003", "Raw Cotton", "kg", "stock", "350", "200"],
    ],
}


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig").strip()
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _csv_response(entity: str) -> StreamingResponse:
    rows = SAMPLE_CSVS.get(entity)
    if not rows:
        raise HTTPException(404, "No sample for this entity")
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sample_{entity}.csv"'},
    )


# ── Validation helpers (no DB writes) ────────────────────────────────────────

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


def _validate_customers(rows: list[dict]):
    valid, errors = 0, []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        try:
            D(row.get("opening_balance") or "0")
        except Exception:
            errors.append({"row": i, "message": "opening_balance must be a number"}); continue
        valid += 1
    return valid, errors


def _validate_vendors(rows: list[dict]):
    valid, errors = 0, []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        try:
            D(row.get("opening_balance") or "0")
        except Exception:
            errors.append({"row": i, "message": "opening_balance must be a number"}); continue
        valid += 1
    return valid, errors


def _validate_products(rows: list[dict]):
    VALID_TYPES = {"stock", "service"}
    VALID_UNITS = {"pcs", "kg", "mtr", "hrs", "ltr", "box", "doz"}
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
        valid += 1
    return valid, errors


def _validate_transactions(rows: list[dict], session: Session, tenant_id: int):
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


# ── Validate endpoint (no DB write) ──────────────────────────────────────────

@router.post("/{entity}/validate")
async def validate_import(
    entity: str, file: UploadFile,
    session: SessionDep, user: WriteUserDep,
):
    rows = _parse_csv(await file.read())
    if entity == "accounts":
        valid, errors = _validate_accounts(rows, session, user.tenant_id)
    elif entity == "customers":
        valid, errors = _validate_customers(rows)
    elif entity == "vendors":
        valid, errors = _validate_vendors(rows)
    elif entity == "products":
        valid, errors = _validate_products(rows)
    elif entity == "transactions":
        valid, errors = _validate_transactions(rows, session, user.tenant_id)
    else:
        raise HTTPException(404, f"Unknown entity: {entity}")
    return {"valid_count": valid, "total_rows": len(rows), "errors": errors}


@router.get("/{entity}/sample")
def download_sample(entity: str, _user: CurrentUserDep):
    return _csv_response(entity)


# ── Per-entity bulk import endpoints ─────────────────────────────────────────


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
                "row": None,
                "message": f"parent_code '{parent_code_raw}' not found — account created without parent",
            })

    session.commit()
    log_audit(session, user, "import", "Account", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


@router.post("/customers")
async def import_customers(
    file: UploadFile, session: SessionDep, user: WriteUserDep,
):
    rows = _parse_csv(await file.read())
    imported, errors = 0, []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        try:
            ob = D(row.get("opening_balance") or "0")
        except Exception:
            errors.append({"row": i, "message": "opening_balance must be a number"}); continue
        session.add(Customer(
            tenant_id=user.tenant_id,
            name=name,
            email=(row.get("email") or "").strip() or None,
            phone=(row.get("phone") or "").strip() or None,
            address=(row.get("address") or "").strip() or None,
            opening_balance=ob,
            is_active=True,
        ))
        imported += 1
    session.commit()
    log_audit(session, user, "import", "Customer", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


@router.post("/vendors")
async def import_vendors(
    file: UploadFile, session: SessionDep, user: WriteUserDep,
):
    rows = _parse_csv(await file.read())
    imported, errors = 0, []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        try:
            ob = D(row.get("opening_balance") or "0")
        except Exception:
            errors.append({"row": i, "message": "opening_balance must be a number"}); continue
        session.add(Vendor(
            tenant_id=user.tenant_id,
            name=name,
            email=(row.get("email") or "").strip() or None,
            phone=(row.get("phone") or "").strip() or None,
            address=(row.get("address") or "").strip() or None,
            opening_balance=ob,
            is_active=True,
        ))
        imported += 1
    session.commit()
    log_audit(session, user, "import", "Vendor", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


@router.post("/products")
async def import_products(
    file: UploadFile, session: SessionDep, user: WriteUserDep,
):
    VALID_TYPES = {"stock", "service"}
    VALID_UNITS = {"pcs", "kg", "mtr", "hrs", "ltr", "box", "doz"}
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
        session.add(Product(
            tenant_id=user.tenant_id,
            code=(row.get("code") or "").strip() or None,
            name=name,
            unit=unit,
            product_type=ptype,
            default_rate=rate,
            reorder_level=reorder,
            is_active=True,
        ))
        imported += 1
    session.commit()
    log_audit(session, user, "import", "Product", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


@router.post("/transactions")
async def import_transactions(
    file: UploadFile, session: SessionDep, user: WriteUserDep,
):
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
                audit_entity_type="transaction_import",
            )
            imported += 1
        except HTTPException as ex:
            errors.append({"row": group_rows[0][0], "message": ex.detail})

    session.commit()
    log_audit(session, user, "import", "Transaction", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}
