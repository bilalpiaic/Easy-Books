"""Depreciation calculation for IAS 16 (PP&E) and IAS 38 (intangibles)."""
from decimal import Decimal
from typing import Optional

from services.money import D, ZERO, money


def compute_depreciation(
    acquisition_cost: Decimal,
    salvage_value: Decimal,
    useful_life_months: int,
    accumulated_depreciation: Decimal,
    method: str,
    accum_impairment: Optional[Decimal] = None,
) -> Decimal:
    """Return the depreciation charge for one period (one month).

    Straight-line: (cost - salvage) / useful_life_months
    Reducing-balance: book_value * monthly_rate derived from salvage fraction
    Returns ZERO when the asset is fully depreciated.

    Remaining depreciable base subtracts accum_impairment (IAS 36 carrying amount).
    """
    cost = D(acquisition_cost)
    salvage = D(salvage_value)
    accum = D(accumulated_depreciation)
    impair = D(accum_impairment)
    depreciable = cost - salvage

    if depreciable <= ZERO or useful_life_months <= 0:
        return ZERO

    if method == "straight_line":
        charge = money(depreciable / useful_life_months)
    elif method == "reducing_balance":
        book_value = cost - accum - impair
        if book_value <= salvage:
            return ZERO
        # Annual rate = 1 - (salvage/cost)^(1/years); converted to monthly
        years = D(str(useful_life_months)) / D("12")
        if years > 0 and cost > 0 and salvage > 0:
            annual_rate = D("1") - (salvage / cost) ** (D("1") / years)
        else:
            annual_rate = D("1")
        monthly_rate = annual_rate / D("12")
        charge = money(book_value * monthly_rate)
    else:
        charge = ZERO

    # Do not depreciate below salvage value (after impairment)
    remaining = depreciable - accum - impair
    if remaining <= ZERO:
        return ZERO
    return min(charge, money(remaining))
