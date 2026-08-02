"""OFX / QFX statement parsing (#268).

Supports the common SGML-ish OFX 1.x shape used by most banks' .ofx/.qfx
downloads (STMTTRN blocks). OFX 2.x XML is also accepted when tags match.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from services.money import D, ZERO


_TRN_RE = re.compile(
    r"<STMTTRN>(.*?)</STMTTRN>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(
    r"<([A-Z0-9.]+)>([^<\r\n]*)",
    re.IGNORECASE,
)


def _tag_map(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _TAG_RE.finditer(block):
        key = m.group(1).upper()
        val = m.group(2).strip()
        if key and key not in out:
            out[key] = val
    return out


def _parse_ofx_date(raw: str) -> str:
    """OFX dates look like YYYYMMDD[HHMMSS][...]. Return YYYY-MM-DD."""
    digits = re.sub(r"[^0-9]", "", raw or "")
    if len(digits) < 8:
        raise ValueError(f"Invalid OFX date: {raw!r}")
    return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"


def _signed_amount(raw: str) -> Decimal:
    try:
        return D(raw.replace(",", ""))
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"Invalid OFX amount: {raw!r}") from exc


def parse_ofx(content: str) -> list[dict[str, Any]]:
    """Parse OFX/QFX text into bank_imports row dicts.

    Returns list of {date, description, debit, credit, balance, external_id}.
    OFX TRNAMT: negative = money out (debit), positive = money in (credit)
    — matching common US bank download convention.
    """
    blocks = _TRN_RE.findall(content)
    if not blocks:
        # Some files omit closing tags; split on <STMTTRN>
        parts = re.split(r"<STMTTRN>", content, flags=re.IGNORECASE)
        blocks = parts[1:] if len(parts) > 1 else []

    rows: list[dict[str, Any]] = []
    for block in blocks:
        tags = _tag_map(block)
        if "TRNAMT" not in tags or "DTPOSTED" not in tags:
            continue
        amt = _signed_amount(tags["TRNAMT"])
        if amt < ZERO:
            debit, credit = abs(amt), ZERO
        else:
            debit, credit = ZERO, amt
        desc = (
            tags.get("MEMO")
            or tags.get("NAME")
            or tags.get("PAYEE")
            or "OFX transaction"
        ).strip()
        fitid = tags.get("FITID") or tags.get("REFNUM")
        rows.append({
            "date": _parse_ofx_date(tags["DTPOSTED"]),
            "description": desc[:500],
            "debit": debit,
            "credit": credit,
            "balance": ZERO,
            "external_id": str(fitid) if fitid else None,
        })
    return rows
