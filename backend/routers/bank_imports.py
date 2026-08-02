"""Bank statement CSV / OFX import + confidence-scored auto-match (#268).

CSV:
    Default columns: date, description, debit, credit, balance
    Optional Form mapping: date_col, description_col, debit_col, credit_col,
    amount_col, balance_col — when a bank uses different headers. amount_col
    alone is signed (negative = debit / money out).

OFX/QFX:
    Detected by filename / content; FITID stored as external_id for de-dupe.

Workflow:
    1. POST /api/bank-imports        upload → StatementLines + apply rules
    2. POST /api/bank-imports/{id}/auto-match
                                     score candidates; auto-accept ≥90 unique
    3. POST /api/statement-lines/{id}/accept|reject
                                     one-click decision (audited)
"""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import select

from models import (
    BankAccount, BankStatementImport, StatementLine, Transaction,
)
from services.bank_match import (
    accept_match, apply_match_suggestions, find_candidates, reject_match,
)
from services.bank_rules import apply_rules_to_lines
from services.money import D, ZERO, money
from services.ofx_parse import parse_ofx
from services.permissions import perm_dep

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(tags=["bank-imports"], dependencies=[perm_dep("bank_imports")])


def _looks_like_ofx(filename: str | None, content: str) -> bool:
    name = (filename or "").lower()
    if name.endswith(".ofx") or name.endswith(".qfx"):
        return True
    head = content.lstrip()[:200].upper()
    return "OFXHEADER" in head or "<OFX>" in head or "<STMTTRN>" in head


def _parse_csv(
    content: str,
    *,
    date_col: str = "date",
    description_col: str = "description",
    debit_col: str = "debit",
    credit_col: str = "credit",
    amount_col: str | None = None,
    balance_col: str = "balance",
) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return []
    # Normalise header → original for lookup
    headers = { (h or "").strip().lower(): (h or "").strip() for h in reader.fieldnames }

    def col(name: str) -> str | None:
        key = name.strip().lower()
        return headers.get(key)

    d_key = col(date_col)
    desc_key = col(description_col)
    if not d_key or not desc_key:
        raise HTTPException(
            400,
            f"CSV missing required columns '{date_col}' / '{description_col}' "
            f"(found: {list(headers.keys())})",
        )
    debit_key = col(debit_col)
    credit_key = col(credit_col)
    amount_key = col(amount_col) if amount_col else None
    balance_key = col(balance_col)

    rows: list[dict] = []
    for raw in reader:
        date_v = (raw.get(d_key) or "").strip()
        desc_v = (raw.get(desc_key) or "").strip()
        if not date_v or not desc_v:
            continue
        debit = ZERO
        credit = ZERO
        if amount_key:
            amt = D((raw.get(amount_key) or "0").replace(",", "") or 0)
            if amt < ZERO:
                debit = abs(amt)
            else:
                credit = amt
        else:
            debit = D((raw.get(debit_key) or "0").replace(",", "") or 0) if debit_key else ZERO
            credit = D((raw.get(credit_key) or "0").replace(",", "") or 0) if credit_key else ZERO
        bal = D((raw.get(balance_key) or "0").replace(",", "") or 0) if balance_key else ZERO
        rows.append({
            "date": date_v[:10],
            "description": desc_v[:500],
            "debit": debit,
            "credit": credit,
            "balance": bal,
            "external_id": None,
        })
    return rows


def _add_lines(session, user, imp: BankStatementImport, rows: list[dict]) -> int:
    """Insert rows; skip by external_id when already present. Returns inserted count."""
    inserted = 0
    for r in rows:
        ext = r.get("external_id")
        if ext:
            exists = session.exec(
                select(StatementLine).where(
                    StatementLine.tenant_id == user.tenant_id,
                    StatementLine.external_id == str(ext),
                )
            ).first()
            if exists:
                continue
        session.add(StatementLine(
            tenant_id=user.tenant_id,
            import_id=imp.id,
            date=r["date"],
            description=r["description"],
            debit=money(r["debit"]),
            credit=money(r["credit"]),
            balance=money(r.get("balance") or 0),
            external_id=str(ext) if ext else None,
        ))
        inserted += 1
    return inserted


@router.post("/api/bank-imports", status_code=201)
async def upload_bank_statement(
    session: SessionDep, user: WriteUserDep,
    bank_account_id: int = Form(...),
    file: UploadFile = File(...),
    date_col: str = Form("date"),
    description_col: str = Form("description"),
    debit_col: str = Form("debit"),
    credit_col: str = Form("credit"),
    amount_col: Optional[str] = Form(None),
    balance_col: str = Form("balance"),
):
    acct = session.exec(
        select(BankAccount).where(
            BankAccount.id == bank_account_id,
            BankAccount.tenant_id == user.tenant_id,
        )
    ).first()
    if not acct:
        raise HTTPException(404, "Bank account not found")

    raw_bytes = await file.read()
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    existing = session.exec(
        select(BankStatementImport).where(
            BankStatementImport.tenant_id == user.tenant_id,
            BankStatementImport.bank_account_id == bank_account_id,
            BankStatementImport.file_hash == file_hash,
        )
    ).first()
    if existing:
        raise HTTPException(409, f"This file was already imported as #{existing.id}")

    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Upload must be UTF-8 text (CSV or OFX/QFX)")

    filename = file.filename or "statement.csv"
    if _looks_like_ofx(filename, content):
        try:
            rows = parse_ofx(content)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if not rows:
            raise HTTPException(400, "OFX/QFX contained no STMTTRN transactions")
    else:
        try:
            rows = _parse_csv(
                content,
                date_col=date_col,
                description_col=description_col,
                debit_col=debit_col,
                credit_col=credit_col,
                amount_col=amount_col or None,
                balance_col=balance_col,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, f"CSV parse error: {exc}") from exc
        if not rows:
            raise HTTPException(
                400,
                "CSV is empty or missing required columns (date, description)",
            )

    imp = BankStatementImport(
        tenant_id=user.tenant_id,
        bank_account_id=bank_account_id,
        file_name=filename,
        file_hash=file_hash,
        line_count=0,
    )
    session.add(imp)
    session.flush()

    inserted = _add_lines(session, user, imp, rows)
    imp.line_count = inserted
    session.add(imp)
    session.flush()

    lines = list(session.exec(
        select(StatementLine).where(StatementLine.import_id == imp.id)
    ).all())
    apply_rules_to_lines(session, tenant_id=user.tenant_id, lines=lines)

    log_audit(
        session, user, "CREATE", "bank_import", imp.id,
        {"file_name": imp.file_name, "lines": imp.line_count, "format": "ofx" if _looks_like_ofx(filename, content) else "csv"},
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
    lines = session.exec(
        select(StatementLine)
        .where(StatementLine.import_id == imp.id)
        .order_by(StatementLine.date)
    ).all()
    out = []
    for line in lines:
        data = line.model_dump()
        if not line.is_matched:
            data["suggestions"] = find_candidates(
                session, tenant_id=user.tenant_id, line=line
            )[:5]
        else:
            data["suggestions"] = []
        out.append(data)
    return out


@router.post("/api/bank-imports/{import_id}/auto-match")
def auto_match(session: SessionDep, user: WriteUserDep, import_id: int):
    """Score unmatched lines; auto-accept unique matches with confidence ≥ 90."""
    imp = session.exec(
        select(BankStatementImport).where(
            BankStatementImport.id == import_id,
            BankStatementImport.tenant_id == user.tenant_id,
        )
    ).first()
    if not imp:
        raise HTTPException(404, "Import not found")

    counts = apply_match_suggestions(
        session, tenant_id=user.tenant_id, import_id=imp.id, auto_accept=True
    )
    newly_matched = counts["newly_matched"]
    imp.matched_count = (imp.matched_count or 0) + newly_matched
    if imp.line_count and imp.matched_count >= imp.line_count:
        imp.status = "matched"
    session.add(imp)
    log_audit(
        session, user, "UPDATE", "bank_import", imp.id,
        {"action": "auto_match", **counts},
    )
    session.commit()
    session.refresh(imp)
    return {
        "newly_matched": newly_matched,
        "suggested": counts["suggested"],
        "total_matched": imp.matched_count,
        "import": imp,
    }


@router.post("/api/bank-imports/{import_id}/apply-rules")
def apply_rules(session: SessionDep, user: WriteUserDep, import_id: int):
    imp = session.exec(
        select(BankStatementImport).where(
            BankStatementImport.id == import_id,
            BankStatementImport.tenant_id == user.tenant_id,
        )
    ).first()
    if not imp:
        raise HTTPException(404, "Import not found")
    lines = list(session.exec(
        select(StatementLine).where(StatementLine.import_id == imp.id)
    ).all())
    # Allow re-run: clear prior categorization on unmatched lines
    for ln in lines:
        if not ln.is_matched:
            ln.categorized_account_id = None
            ln.expense_draft_suggested = False
            session.add(ln)
    session.flush()
    n = apply_rules_to_lines(session, tenant_id=user.tenant_id, lines=lines)
    session.commit()
    return {"categorized": n}


class StatementLinePatch(BaseModel):
    matched_transaction_id: Optional[int] = None
    clear_match: bool = False


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

    if body.clear_match or (
        "matched_transaction_id" in body.model_dump(exclude_unset=True)
        and body.matched_transaction_id is None
    ):
        was_matched = line.is_matched
        line.matched_transaction_id = None
        line.is_matched = False
        line.match_status = None
        line.suggested_transaction_id = None
        line.match_confidence = None
        session.add(line)
        if was_matched:
            imp = session.get(BankStatementImport, line.import_id)
            if imp and imp.tenant_id == user.tenant_id:
                imp.matched_count = max(0, (imp.matched_count or 0) - 1)
                session.add(imp)
        session.commit()
        session.refresh(line)
        return line

    if body.matched_transaction_id is not None:
        txn = session.get(Transaction, body.matched_transaction_id)
        if not txn or txn.tenant_id != user.tenant_id:
            raise HTTPException(400, "Transaction not found")
        was_matched = line.is_matched
        line.matched_transaction_id = txn.id
        line.is_matched = True
        line.suggested_transaction_id = txn.id
        line.match_status = "accepted"
        line.match_decided_by_id = user.id
        line.match_decided_at = datetime.utcnow()
        line.match_confidence = line.match_confidence or 100.0
        session.add(line)
        if not was_matched:
            imp = session.get(BankStatementImport, line.import_id)
            if imp and imp.tenant_id == user.tenant_id:
                imp.matched_count = (imp.matched_count or 0) + 1
                session.add(imp)
        log_audit(
            session, user, "UPDATE", "statement_line", line.id,
            {"action": "accept", "transaction_id": txn.id},
        )
    session.commit()
    session.refresh(line)
    return line


class AcceptBody(BaseModel):
    transaction_id: Optional[int] = None


@router.post("/api/statement-lines/{line_id}/accept")
def accept_line_match(
    session: SessionDep, user: WriteUserDep, line_id: int, body: AcceptBody = AcceptBody(),
):
    line = session.exec(
        select(StatementLine).where(
            StatementLine.id == line_id, StatementLine.tenant_id == user.tenant_id
        )
    ).first()
    if not line:
        raise HTTPException(404, "Line not found")
    txn_id = body.transaction_id or line.suggested_transaction_id
    if not txn_id:
        raise HTTPException(400, "No suggested transaction to accept")
    txn = session.get(Transaction, txn_id)
    if not txn or txn.tenant_id != user.tenant_id:
        raise HTTPException(400, "Transaction not found")
    was_matched = line.is_matched
    try:
        accept_match(session, line=line, user_id=user.id, transaction_id=txn_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not was_matched:
        imp = session.get(BankStatementImport, line.import_id)
        if imp and imp.tenant_id == user.tenant_id:
            imp.matched_count = (imp.matched_count or 0) + 1
            session.add(imp)
    log_audit(
        session, user, "UPDATE", "statement_line", line.id,
        {"action": "accept", "transaction_id": txn_id, "confidence": line.match_confidence},
    )
    session.commit()
    session.refresh(line)
    return line


@router.post("/api/statement-lines/{line_id}/reject")
def reject_line_match(session: SessionDep, user: WriteUserDep, line_id: int):
    line = session.exec(
        select(StatementLine).where(
            StatementLine.id == line_id, StatementLine.tenant_id == user.tenant_id
        )
    ).first()
    if not line:
        raise HTTPException(404, "Line not found")
    was_matched = line.is_matched
    reject_match(session, line=line, user_id=user.id)
    if was_matched:
        imp = session.get(BankStatementImport, line.import_id)
        if imp and imp.tenant_id == user.tenant_id:
            imp.matched_count = max(0, (imp.matched_count or 0) - 1)
            session.add(imp)
    log_audit(
        session, user, "UPDATE", "statement_line", line.id,
        {"action": "reject"},
    )
    session.commit()
    session.refresh(line)
    return line
