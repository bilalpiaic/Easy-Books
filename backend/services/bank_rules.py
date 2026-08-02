"""Bank statement categorization rules (#268)."""
from __future__ import annotations

from sqlmodel import Session, select

from models import CategorizationRule, StatementLine
from services.money import D, ZERO


def apply_rules_to_lines(
    session: Session,
    *,
    tenant_id: int,
    lines: list[StatementLine],
) -> int:
    """Apply active rules (ascending priority) to unmatched lines.

    First match wins. Sets categorized_account_id and optionally
    expense_draft_suggested. Returns count of lines categorized.
    """
    rules = list(session.exec(
        select(CategorizationRule).where(
            CategorizationRule.tenant_id == tenant_id,
            CategorizationRule.is_active == True,  # noqa: E712
        ).order_by(CategorizationRule.priority, CategorizationRule.id)  # type: ignore
    ).all())
    if not rules:
        return 0

    applied = 0
    for line in lines:
        if line.is_matched or line.categorized_account_id is not None:
            continue
        desc = (line.description or "").lower()
        amount = D(line.debit) if D(line.debit) > ZERO else D(line.credit)
        for rule in rules:
            if rule.pattern.lower() not in desc:
                continue
            if rule.match_amount is not None and abs(float(amount) - float(rule.match_amount)) > 0.005:
                continue
            line.categorized_account_id = rule.account_id
            if rule.create_expense_draft:
                line.expense_draft_suggested = True
            session.add(line)
            applied += 1
            break
    return applied
