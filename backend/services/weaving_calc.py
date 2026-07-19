"""Shared weaving unit-control calculations.

Kg→Lbs→Bags and Rate/Lb live here once — routers/serializers and reports must
call these helpers rather than duplicating the Excel formulas.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from services.money import D, ZERO, money

KG_TO_LB = Decimal("2.2046226218")


def weight_triple(kg: Decimal | float | int | str | None) -> dict[str, float]:
    """Return Kg, Lbs, and 100-lb Bags for a yarn weight."""
    k = money(kg) if kg is not None else ZERO
    lbs = money(k * KG_TO_LB)
    bags = money(lbs / Decimal("100")) if lbs != ZERO else ZERO
    return {"kg": float(k), "lbs": float(lbs), "bags": float(bags)}


def rate_per_lb(rate_per_kg: Decimal | float | int | str | None) -> float:
    """Assumed yarn rate per Lb derived from rate per Kg."""
    r = money(rate_per_kg) if rate_per_kg is not None else ZERO
    if r == ZERO:
        return 0.0
    return float(money(r / KG_TO_LB))


def net_kg(gross: Decimal | float | int | str | None,
           tare: Decimal | float | int | str | None) -> Decimal:
    return money(D(gross or 0) - D(tare or 0))


def sizing_gain_shrink_pct(
    input_kg: Decimal | float | int | str | None,
    output_kg: Decimal | float | int | str | None,
) -> float:
    """(output − input) / input × 100. Positive = gain, negative = shrink."""
    inp = money(input_kg)
    if inp == ZERO:
        return 0.0
    out = money(output_kg)
    return float(money((out - inp) / inp * Decimal("100")))


def production_efficiency_pct(
    grey_meters: Decimal | float | int | str | None,
    contract_meters: Decimal | float | int | str | None,
) -> float:
    cm = money(contract_meters)
    if cm == ZERO:
        return 0.0
    return float(money(D(grey_meters or 0) / cm * Decimal("100")))


def dispatch_value(
    meters: Decimal | float | int | str | None,
    fabric_return_price_per_meter: Decimal | float | int | str | None,
) -> Decimal:
    return money(D(meters or 0) * D(fabric_return_price_per_meter or 0))


def weaving_charges(
    meters: Decimal | float | int | str | None,
    weaving_rate: Decimal | float | int | str | None,
) -> Decimal:
    return money(D(meters or 0) * D(weaving_rate or 0))


def net_receivable(
    dispatch_val: Decimal | float | int | str | None,
    charges_billed: Decimal | float | int | str | None,
) -> Decimal:
    return money(D(dispatch_val or 0) - D(charges_billed or 0))


def expected_weaving_revenue(
    contract_meters: Decimal | float | int | str | None,
    weaving_rate: Decimal | float | int | str | None,
) -> Decimal:
    return weaving_charges(contract_meters, weaving_rate)


def attach_weight(payload: dict[str, Any], kg_key: str, prefix: str | None = None) -> dict[str, Any]:
    """Add `{prefix_}lbs` / `{prefix_}bags` (or `lbs`/`bags`) from a kg field."""
    triple = weight_triple(payload.get(kg_key))
    if prefix:
        payload[f"{prefix}_lbs"] = triple["lbs"]
        payload[f"{prefix}_bags"] = triple["bags"]
    else:
        payload["lbs"] = triple["lbs"]
        payload["bags"] = triple["bags"]
    return payload
