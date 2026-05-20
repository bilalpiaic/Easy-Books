"""
Decimal-money primitives.

All monetary math in Easy-Books goes through this module. Internally everything
is Decimal (no IEEE-754 drift); JSON output is coerced to float so the
frontend's existing Number-based code keeps working at the API edge.

Why ROUND_HALF_EVEN ("banker's rounding"): aligns with ISO 4217 / IFRS guidance
and avoids the systematic upward bias of ROUND_HALF_UP across large datasets.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from typing import Annotated, Iterable, Union

from pydantic import PlainSerializer

# 28 digits is Python's default; enough for currency math at any reasonable scale.
getcontext().prec = 28

CENTS = Decimal("0.01")
ZERO = Decimal("0")
ONE = Decimal("1")

Numeric = Union[int, float, str, Decimal, None]


def D(value: Numeric) -> Decimal:
    """Coerce any numeric input to Decimal. None becomes 0."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    # str() round-trip avoids importing a float's binary garbage.
    return Decimal(str(value))


def money(value: Numeric) -> Decimal:
    """Quantize to 2 dp using banker's rounding. Use at boundaries (responses, GL writes)."""
    return D(value).quantize(CENTS, rounding=ROUND_HALF_EVEN)


def sum_money(values: Iterable[Numeric]) -> Decimal:
    total = ZERO
    for v in values:
        total += D(v)
    return total


# Pydantic field type: stores as Decimal, serialises to JSON as float.
# Using this preserves the existing frontend contract (numeric JSON) while
# the entire backend operates on Decimal under the hood.
Money = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v) if v is not None else None, return_type=float, when_used="json"),
]
