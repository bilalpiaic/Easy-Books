"""
Account-level helpers used by posting control and hierarchy validation.

JournalEntry.tenant_id exists directly on the table (inherited from
JournalEntryBase), so tenant-scoped postings counts query it directly without
needing a join to Transaction.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlmodel import Session, func, select

from models import Account, JournalEntry


def account_has_children(session: Session, tenant_id: int, account_id: int) -> bool:
    """Return True if any account in the tenant has parent_id == account_id."""
    count = session.exec(
        select(func.count()).select_from(Account).where(
            Account.tenant_id == tenant_id,
            Account.parent_id == account_id,
        )
    ).one()
    return count > 0


def account_has_postings(session: Session, tenant_id: int, account_id: int) -> bool:
    """Return True if any JournalEntry exists for this account in the tenant."""
    count = session.exec(
        select(func.count()).select_from(JournalEntry).where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.account_id == account_id,
        )
    ).one()
    return count > 0


def assert_account_postable(session: Session, tenant_id: int, account: Account) -> None:
    """Raise HTTP 400 if the account is not a valid posting target.

    An account is postable iff it is ALL of:
      - not a group/header account  (is_group == False)
      - active                       (is_active == True)
      - a leaf                       (no child accounts)
    """
    from fastapi import HTTPException

    if account.is_group:
        raise HTTPException(
            400,
            f"Cannot post to '{account.code} {account.name}' — it is a group/header account.",
        )
    if not account.is_active:
        raise HTTPException(
            400,
            f"Cannot post to '{account.code} {account.name}' — it is inactive.",
        )
    if account_has_children(session, tenant_id, account.id):
        raise HTTPException(
            400,
            f"Cannot post to '{account.code} {account.name}' — it has sub-accounts; "
            "post to a detail account.",
        )


def suggest_next_code(
    session: Session, tenant_id: int, parent_id: Optional[int]
) -> str:
    """Suggest the next available account code under *parent_id*.

    Strategy:
    - If parent has existing child accounts, increment the highest numeric
      child code by 1 (handles both plain '1101' and structured '1100-01').
    - If parent has no children yet, derive from the parent code:
        * If parent code ends in a hyphen-suffix  (e.g. '1100-00') → next is '1100-01'
        * If parent code is purely numeric → append '01' (e.g. '1100' → '110001')
          unless the parent ends in '00' (e.g. '1100' → '1101')
        * Otherwise: parent_code + '-01'
    - If no parent (top-level): find the largest existing numeric top-level
      code and add 1000, rounded up to the nearest thousand.
    - Result is guaranteed not to collide with any existing tenant code.
    """
    # Fetch all existing codes for the tenant once (set for O(1) lookup)
    all_codes: set[str] = set(
        session.exec(
            select(Account.code).where(Account.tenant_id == tenant_id)
        ).all()
    )

    def _free(candidate: str) -> str:
        """Increment candidate until it's not already in use."""
        if candidate not in all_codes:
            return candidate
        # Try numeric increment on the whole string
        m = re.match(r"^(.*?)(\d+)$", candidate)
        if not m:
            # Fall back: append -01, -02, …
            i = 1
            while True:
                c = f"{candidate}-{i:02d}"
                if c not in all_codes:
                    return c
                i += 1
        prefix, num_part = m.group(1), m.group(2)
        val = int(num_part)
        width = len(num_part)
        while True:
            val += 1
            c = f"{prefix}{val:0{width}d}"
            if c not in all_codes:
                return c

    if parent_id is not None:
        parent = session.get(Account, parent_id)
        if parent is None:
            # Parent not found — fall back to top-level suggestion
            return suggest_next_code(session, tenant_id, None)

        # Get codes of direct children
        child_codes = list(
            session.exec(
                select(Account.code).where(
                    Account.tenant_id == tenant_id,
                    Account.parent_id == parent_id,
                )
            ).all()
        )

        if child_codes:
            # Find the largest code numerically (ignoring prefix/suffix structure)
            def _numeric_val(code: str) -> int:
                digits = re.sub(r"\D", "", code)
                return int(digits) if digits else 0

            best = max(child_codes, key=_numeric_val)
            return _free(best)
        else:
            # No children yet — derive from parent code
            pcode = parent.code
            # If the code ends with a hyphen-number suffix e.g. '1100-00' → '1100-01'
            m_hyp = re.match(r"^(.+?)-(\d+)$", pcode)
            if m_hyp:
                prefix_part, num_part = m_hyp.group(1), m_hyp.group(2)
                val = int(num_part)
                width = len(num_part)
                candidate = f"{prefix_part}-{val + 1:0{width}d}"
                return _free(candidate)

            # Pure numeric code like '1100' → try '1101'
            m_num = re.match(r"^(\d+)$", pcode)
            if m_num:
                val = int(pcode)
                candidate = str(val + 1)
                return _free(candidate)

            # Alphanumeric like 'AP-20' → 'AP-20-01'
            return _free(f"{pcode}-01")

    else:
        # Top-level: find the largest purely numeric code and add 1000,
        # rounded up to the next thousand.
        numeric_codes = []
        for code in all_codes:
            if re.match(r"^\d+$", code):
                numeric_codes.append(int(code))
        if numeric_codes:
            largest = max(numeric_codes)
            # Round up to next thousand
            next_val = ((largest // 1000) + 1) * 1000
            while str(next_val) in all_codes:
                next_val += 1000
            return str(next_val)
        else:
            return "1000"
