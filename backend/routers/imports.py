"""CSV bulk imports (accounts / customers / vendors / products / transactions)."""
import csv
import io

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import select

from models import Account, Customer, Product, Vendor
from services.money import D
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, log_audit

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
        ["code", "name", "type"],
        ["1050", "Petty Cash", "Asset"],
        ["2210", "Accrued Liabilities", "Liability"],
        ["5200", "Marketing Expense", "Expense"],
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


@router.get("/{entity}/sample")
def download_sample(entity: str, _user: CurrentUserDep):
    return _csv_response(entity)


# ── Per-entity bulk import endpoints ─────────────────────────────────────────


@router.post("/accounts")
async def import_accounts(
    file: UploadFile, session: SessionDep, user: CurrentUserDep,
):
    VALID_TYPES = {"Asset", "Liability", "Equity", "Revenue", "Expense"}
    rows = _parse_csv(await file.read())
    imported, errors = 0, []
    for i, row in enumerate(rows, start=2):
        code = (row.get("code") or "").strip()
        name = (row.get("name") or "").strip()
        atype = (row.get("type") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        if atype not in VALID_TYPES:
            errors.append({"row": i, "message": f"type must be one of {sorted(VALID_TYPES)}"}); continue
        if code:
            existing = session.exec(
                select(Account).where(
                    Account.code == code, Account.tenant_id == user.tenant_id
                )
            ).first()
            if existing:
                errors.append({"row": i, "message": f"account code '{code}' already exists"}); continue
        session.add(Account(
            tenant_id=user.tenant_id, code=code or None, name=name, type=atype,
        ))
        imported += 1
    session.commit()
    log_audit(session, user, "import", "Account", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


@router.post("/customers")
async def import_customers(
    file: UploadFile, session: SessionDep, user: CurrentUserDep,
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
    file: UploadFile, session: SessionDep, user: CurrentUserDep,
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
    file: UploadFile, session: SessionDep, user: CurrentUserDep,
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
    file: UploadFile, session: SessionDep, user: CurrentUserDep,
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
