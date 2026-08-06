"""Bank statement ↔ JV match confidence (#268)."""
from __future__ import annotations

from datetime import date as DateType, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session, func, select

from models import JournalEntry, StatementLine, Transaction
from services.money import D, ZERO

AUTO_ACCEPT_THRESHOLD = 90.0
DATE_WINDOW_DAYS = 3


def line_amount(line: StatementLine) -> Decimal:
    return D(line.debit) if D(line.debit) > ZERO else D(line.credit)


def _desc_overlap(a: str, b: str) -> float:
    ta = {t for t in re_split(a.lower()) if len(t) > 2}
    tb = {t for t in re_split(b.lower()) if len(t) > 2}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), 1)


def re_split(s: str) -> list[str]:
    import re
    return re.split(r"[^a-z0-9]+", s)


def score_candidate(
    line: StatementLine,
    *,
    txn_date: str,
    txn_total: Decimal,
    txn_description: str = "",
    recurring_boost: float = 0.0,
) -> float:
    amount = line_amount(line)
    if amount <= ZERO or abs(float(txn_total - amount)) > 0.005:
        return 0.0

    score = 50.0  # exact amount
    try:
        d_line = DateType.fromisoformat(line.date[:10])
        d_txn = DateType.fromisoformat(str(txn_date)[:10])
    except ValueError:
        return score
    delta = abs((d_line - d_txn).days)
    if delta == 0:
        score += 40.0
    elif delta == 1:
        score += 30.0
    elif delta == 2:
        score += 20.0
    elif delta <= DATE_WINDOW_DAYS:
        score += 10.0
    else:
        return 0.0

    # Remittance / merchant text (#301): weight description overlap a bit
    # higher so recurring Open Banking remittance strings surface as confident
    # suggestions even when the JV narration is abbreviated.
    overlap = _desc_overlap(line.description or "", txn_description)
    score += min(20.0, overlap * 20.0)

    # Recurring merchant fingerprint: prior accepted matches with the same
    # remittance tokens boost confidence for monthly DD / subscription strings.
    if recurring_boost > 0:
        score += min(15.0, recurring_boost)

    # Keyword hints common on OB remittance (DIRECT DEBIT / MONTHLY / SUB).
    desc = (line.description or "").lower()
    if any(k in desc for k in ("monthly", "direct debit", " dd ", "subscription", "salary")):
        if overlap >= 0.25:
            score += 5.0

    return min(100.0, round(score, 1))


def _recurring_merchant_boost(
    session: Session,
    *,
    tenant_id: int,
    line: StatementLine,
) -> float:
    """Boost when previously accepted lines share remittance tokens."""
    tokens = {t for t in re_split((line.description or "").lower()) if len(t) > 2}
    if len(tokens) < 2:
        return 0.0
    prior = session.exec(
        select(StatementLine).where(
            StatementLine.tenant_id == tenant_id,
            StatementLine.is_matched == True,  # noqa: E712
            StatementLine.id != line.id,
        ).limit(80)
    ).all()
    best = 0.0
    for p in prior:
        ov = _desc_overlap(line.description or "", p.description or "")
        if ov > best:
            best = ov
    return best * 15.0


def find_candidates(
    session: Session,
    *,
    tenant_id: int,
    line: StatementLine,
    exclude_txn_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    amount = line_amount(line)
    if amount <= ZERO:
        return []
    try:
        line_date = DateType.fromisoformat(line.date[:10])
    except ValueError:
        return []
    date_lo = (line_date - timedelta(days=DATE_WINDOW_DAYS)).isoformat()
    date_hi = (line_date + timedelta(days=DATE_WINDOW_DAYS)).isoformat()
    exclude = exclude_txn_ids or set()
    recurring = _recurring_merchant_boost(session, tenant_id=tenant_id, line=line)

    rows = session.exec(
        select(
            Transaction.id,
            Transaction.date,
            Transaction.description,
            Transaction.jv_number,
            func.sum(JournalEntry.debit).label("total_debit"),
        )
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .where(
            Transaction.tenant_id == tenant_id,
            Transaction.date >= date_lo,
            Transaction.date <= date_hi,
            Transaction.is_reversed == False,  # noqa: E712
        )
        .group_by(
            Transaction.id,
            Transaction.date,
            Transaction.description,
            Transaction.jv_number,
        )
        .having(func.sum(JournalEntry.debit) == amount)
    ).all()

    out: list[dict[str, Any]] = []
    for row in rows:
        if row.id in exclude:
            continue
        conf = score_candidate(
            line,
            txn_date=row.date,
            txn_total=D(row.total_debit),
            txn_description=row.description or "",
            recurring_boost=recurring,
        )
        if conf <= 0:
            continue
        out.append({
            "transaction_id": row.id,
            "jv_number": row.jv_number,
            "date": row.date,
            "description": row.description,
            "confidence": conf,
        })
    out.sort(key=lambda x: (-x["confidence"], x["transaction_id"]))
    return out


def apply_match_suggestions(
    session: Session,
    *,
    tenant_id: int,
    import_id: int,
    auto_accept: bool = True,
) -> dict[str, int]:
    """Score unmatched lines; auto-accept unique high-confidence matches."""
    lines = list(session.exec(
        select(StatementLine).where(
            StatementLine.import_id == import_id,
            StatementLine.tenant_id == tenant_id,
            StatementLine.is_matched == False,  # noqa: E712
        )
    ).all())

    already = {
        x for x in session.exec(
            select(StatementLine.matched_transaction_id).where(
                StatementLine.tenant_id == tenant_id,
                StatementLine.import_id == import_id,
                StatementLine.is_matched == True,  # noqa: E712
            )
        ).all()
        if x is not None
    }

    newly_matched = 0
    suggested = 0
    for line in lines:
        cands = find_candidates(
            session, tenant_id=tenant_id, line=line, exclude_txn_ids=already
        )
        if not cands:
            line.suggested_transaction_id = None
            line.match_confidence = None
            if line.match_status not in ("accepted", "rejected"):
                line.match_status = None
            session.add(line)
            continue

        best = cands[0]
        unique_best = len(cands) == 1 or (
            len(cands) > 1 and cands[0]["confidence"] > cands[1]["confidence"]
        )
        if (
            auto_accept
            and unique_best
            and best["confidence"] >= AUTO_ACCEPT_THRESHOLD
        ):
            line.matched_transaction_id = best["transaction_id"]
            line.is_matched = True
            line.suggested_transaction_id = best["transaction_id"]
            line.match_confidence = best["confidence"]
            line.match_status = "accepted"
            already.add(best["transaction_id"])
            newly_matched += 1
        else:
            line.suggested_transaction_id = best["transaction_id"]
            line.match_confidence = best["confidence"]
            line.match_status = "suggested"
            suggested += 1
        session.add(line)

    return {"newly_matched": newly_matched, "suggested": suggested}


def accept_match(
    session: Session,
    *,
    line: StatementLine,
    user_id: int,
    transaction_id: Optional[int] = None,
) -> StatementLine:
    txn_id = transaction_id or line.suggested_transaction_id
    if not txn_id:
        raise ValueError("No suggested transaction to accept")
    line.matched_transaction_id = txn_id
    line.is_matched = True
    line.suggested_transaction_id = txn_id
    line.match_status = "accepted"
    line.match_decided_by_id = user_id
    line.match_decided_at = datetime.utcnow()
    if line.match_confidence is None:
        line.match_confidence = 100.0
    session.add(line)
    return line


def reject_match(
    session: Session,
    *,
    line: StatementLine,
    user_id: int,
) -> StatementLine:
    line.matched_transaction_id = None
    line.is_matched = False
    line.suggested_transaction_id = None
    line.match_confidence = None
    line.match_status = "rejected"
    line.match_decided_by_id = user_id
    line.match_decided_at = datetime.utcnow()
    session.add(line)
    return line
