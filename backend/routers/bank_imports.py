"""Bank statement CSV import + auto-match.

Generic 5-column CSV format:
    date,description,debit,credit,balance

`date` is ISO yyyy-mm-dd. `debit` / `credit` are the bank's perspective —
debit = money leaving the account (e.g. a payment to a vendor), credit =
money arriving (e.g. a customer payment). Either column may be blank.

Workflow:
    1. POST /api/bank-imports        upload CSV → StatementLines created
    2. POST /api/bank-imports/{id}/auto-match
                                     matches lines to JVs by amount + date
    3. GET  /api/bank-imports/{id}/lines
                                     review; manual-match remaining lines
       PATCH /api/statement-lines/{id} { "matched_transaction_id": ... }
"""
import csv
import hashlib
import io
from datetime import date as DateType, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import func, select

from models import (
    BankAccount, BankStatementImport, JournalEntry, StatementLine, Transaction,
)
from services.money import D, money

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(tags=["bank-imports"])


def _parse_csv(content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    rows: list[dict] = []
    required = {"date", "description"}
    for raw in reader:
        # Normalise keys
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw.items()}
        if not row.get("date") or not row.get("description"):
            continue
        if not required.issubset(row):
            continue
        rows.append({
            "date": row["date"],
            "description": row["description"],
            "debit": D(row.get("debit") or 0),
            "credit": D(row.get("credit") or 0),
            "balance": D(row.get("balance") or 0),
        })
    return rows


@router.post("/api/bank-imports", status_code=201)
async def upload_bank_statement(
    session: SessionDep, user: WriteUserDep,
    bank_account_id: int = Form(...),
    file: UploadFile = File(...),
):
    # Verify the bank account belongs to the tenant
    acct = session.exec(
        select(BankAccount).where(
            BankAccount.id == bank_account_id,
            BankAccount.tenant_id == user.tenant_id,
        )
    ).first()
    if not acct:
        raise HTTPException(404, "Bank account not found")

    raw = await file.read()
    file_hash = hashlib.sha256(raw).hexdigest()

    # De-dupe: same hash + account → 409
    existing = session.exec(
        select(BankStatementImport).where(
            BankStatementImport.tenant_id == user.tenant_id,
            BankStatementImport.bank_account_id == bank_account_id,
            BankStatementImport.file_hash == file_hash,
        )
    ).first()
    if existing:
        raise HTTPException(
            409,
            f"This file was already imported as #{existing.id}",
        )

    try:
        rows = _parse_csv(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(400, "Upload must be a UTF-8 CSV file")
    if not rows:
        raise HTTPException(400, "CSV is empty or missing required columns (date, description)")

    imp = BankStatementImport(
        tenant_id=user.tenant_id,
        bank_account_id=bank_account_id,
        file_name=file.filename or "statement.csv",
        file_hash=file_hash,
        line_count=len(rows),
    )
    session.add(imp)
    session.flush()

    for r in rows:
        session.add(
            StatementLine(
                tenant_id=user.tenant_id,
                import_id=imp.id,
                date=r["date"],
                description=r["description"],
                debit=money(r["debit"]),
                credit=money(r["credit"]),
                balance=money(r["balance"]),
            )
        )

    log_audit(
        session, user, "CREATE", "bank_import", imp.id,
        {"file_name": imp.file_name, "lines": imp.line_count},
    )
    session.commit()
    session.refresh(imp)
    return imp


@router.get("/api/bank-imports")
def list_imports(session: SessionDep, user: CurrentUserDep):
    return session.exec(
        select(BankStatementImport)
        .where(BankStatementImport.tenant_id == user.tenant_id)
        .order_by(BankStatementImport.created_at.desc())
    ).all()


@router.get("/api/bank-imports/{import_id}/lines")
def list_lines(session: SessionDep, user: CurrentUserDep, import_id: int):
    imp = session.exec(
        select(BankStatementImport).where(
            BankStatementImport.id == import_id,
            BankStatementImport.tenant_id == user.tenant_id,
        )
    ).first()
    if not imp:
        raise HTTPException(404, "Import not found")
    return session.exec(
        select(StatementLine)
        .where(StatementLine.import_id == imp.id)
        .order_by(StatementLine.date)
    ).all()


@router.post("/api/bank-imports/{import_id}/auto-match")
def auto_match(session: SessionDep, user: WriteUserDep, import_id: int):
    """Match unmatched lines to existing transactions by amount + date
    (±3 days window). For each line, the candidate transaction is one whose
    JV totals exactly equal the line's debit/credit amount and whose
    JV date falls in the window. First match wins; ties leave the line
    unmatched (the user can resolve manually).
    """
    imp = session.exec(
        select(BankStatementImport).where(
            BankStatementImport.id == import_id,
            BankStatementImport.tenant_id == user.tenant_id,
        )
    ).first()
    if not imp:
        raise HTTPException(404, "Import not found")

    lines = session.exec(
        select(StatementLine).where(
            StatementLine.import_id == imp.id,
            StatementLine.is_matched == False,  # noqa: E712
        )
    ).all()

    newly_matched = 0
    for line in lines:
        amount = D(line.debit) if D(line.debit) > 0 else D(line.credit)
        if amount <= 0:
            continue
        line_date = DateType.fromisoformat(line.date)
        date_lo = (line_date - timedelta(days=3)).isoformat()
        date_hi = (line_date + timedelta(days=3)).isoformat()

        # Find candidate JVs whose total debit (= total credit) matches amount
        candidates = session.exec(
            select(
                Transaction.id,
                func.sum(JournalEntry.debit).label("total_debit"),
            )
            .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
            .where(
                Transaction.tenant_id == user.tenant_id,
                Transaction.date >= date_lo,
                Transaction.date <= date_hi,
                Transaction.is_reversed == False,  # noqa: E712
            )
            .group_by(Transaction.id)
            .having(func.sum(JournalEntry.debit) == amount)
        ).all()

        # Skip JVs already claimed by another line *in this import*. Other
        # imports run independently — a JV consumed there shouldn't suppress
        # the same match here.
        already = session.exec(
            select(StatementLine.matched_transaction_id).where(
                StatementLine.tenant_id == user.tenant_id,
                StatementLine.import_id == imp.id,
                StatementLine.is_matched == True,  # noqa: E712
            )
        ).all()
        already_set = {x for x in already if x is not None}
        candidates = [c for c in candidates if c.id not in already_set]
        if len(candidates) != 1:
            continue
        line.matched_transaction_id = candidates[0].id
        line.is_matched = True
        session.add(line)
        newly_matched += 1

    imp.matched_count = (imp.matched_count or 0) + newly_matched
    if imp.matched_count >= imp.line_count:
        imp.status = "matched"
    session.add(imp)
    session.commit()
    session.refresh(imp)
    return {"newly_matched": newly_matched, "total_matched": imp.matched_count, "import": imp}


class StatementLinePatch(BaseModel):
    matched_transaction_id: Optional[int] = None


@router.patch("/api/statement-lines/{line_id}")
def patch_line(
    session: SessionDep, user: WriteUserDep,
    line_id: int, body: StatementLinePatch,
):
    line = session.exec(
        select(StatementLine).where(
            StatementLine.id == line_id, StatementLine.tenant_id == user.tenant_id
        )
    ).first()
    if not line:
        raise HTTPException(404, "Line not found")
    if body.matched_transaction_id is not None:
        txn = session.get(Transaction, body.matched_transaction_id)
        if not txn or txn.tenant_id != user.tenant_id:
            raise HTTPException(400, "Transaction not found")
        line.matched_transaction_id = txn.id
        line.is_matched = True
    session.add(line)
    session.commit()
    session.refresh(line)
    return line
