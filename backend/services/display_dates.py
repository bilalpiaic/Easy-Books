"""Display-only date formatting: ISO YYYY-MM-DD → dd-mmm-yy (e.g. 11-Oct-26).

Storage, APIs, and HTML date inputs stay ISO. Use these helpers only when a
date is shown to a person — PDF templates, print HTML, axis labels.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

MONTHS_SHORT = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

_DISPLAY_DATE_RE = re.compile(r"^\d{2}-[A-Z][a-z]{2}-\d{2}$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def fmt_display_date(value: Any) -> str:
    """ISO date/datetime (or already-formatted dd-mmm-yy) → ``dd-mmm-yy``.

    Idempotent: values that already match the display pattern are returned
    as-is (time suffix stripped if present). Unparseable input is returned
    unchanged as a string.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.day:02d}-{MONTHS_SHORT[value.month - 1]}-{str(value.year)[-2:]}"

    s = str(value).strip()
    date_part = s.split("T", 1)[0].split(" ", 1)[0]
    if _DISPLAY_DATE_RE.match(date_part):
        return date_part
    m = _ISO_DATE_RE.match(date_part)
    if not m:
        return s
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    if not 1 <= mo <= 12 or not 1 <= d <= 31:
        return s
    return f"{d:02d}-{MONTHS_SHORT[mo - 1]}-{y[-2:]}"


def fmt_display_datetime(value: Any) -> str:
    """ISO datetime → ``dd-mmm-yy HH:mm``. Date-only values omit the clock."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return f"{fmt_display_date(value)} {value.hour:02d}:{value.minute:02d}"
    if isinstance(value, date):
        return fmt_display_date(value)

    s = str(value).strip()
    day = fmt_display_date(s)
    clock = ""
    if "T" in s:
        clock = s.split("T", 1)[1][:5]
    elif " " in s and ":" in s.split(" ", 1)[1]:
        clock = s.split(" ", 1)[1][:5]
    if len(clock) == 5 and clock[2] == ":":
        return f"{day} {clock}"
    return day


def apply_display_dates(doc: dict, keys: tuple[str, ...]) -> dict:
    """Copy ``doc`` with named ISO date fields rewritten for display."""
    out = dict(doc)
    for key in keys:
        if out.get(key):
            out[key] = fmt_display_date(out[key])
    return out
