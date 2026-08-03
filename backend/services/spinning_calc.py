"""Shared yarn spinning calculations — Kg canonical, Lbs/Bags derived."""
from __future__ import annotations

from decimal import Decimal

from services.money import D, ZERO, money

KG_TO_LB = Decimal("2.2046226218")


def weight_triple(kg: Decimal | float | int | str | None) -> dict[str, float]:
    k = money(kg) if kg is not None else ZERO
    lbs = money(k * KG_TO_LB)
    bags = money(lbs / Decimal("100")) if lbs != ZERO else ZERO
    return {"kg": float(k), "lbs": float(lbs), "bags": float(bags)}


def net_kg(gross: Decimal | float | int | str | None,
           tare: Decimal | float | int | str | None) -> Decimal:
    return money(D(gross or 0) - D(tare or 0))


def moisture_adjusted_kg(net: Decimal | float | int | str | None,
                         moisture_pct: Decimal | float | int | str | None) -> Decimal:
    n = money(net)
    m = D(moisture_pct or 0)
    if m <= 0:
        return n
    return money(n * (Decimal("100") - m) / Decimal("100"))


def stage_yield_pct(input_kg: Decimal | float | int | str | None,
                    output_kg: Decimal | float | int | str | None) -> float:
    inp = money(input_kg)
    if inp == ZERO:
        return 0.0
    out = money(output_kg)
    return float(money(out / inp * Decimal("100")))


def lot_yield_pct(total_input: Decimal | float | int | str | None,
                  total_output: Decimal | float | int | str | None) -> float:
    return stage_yield_pct(total_input, total_output)


def waste_pct(input_kg: Decimal | float | int | str | None,
              waste_kg: Decimal | float | int | str | None) -> float:
    inp = money(input_kg)
    if inp == ZERO:
        return 0.0
    w = money(waste_kg)
    return float(money(w / inp * Decimal("100")))


def ne_to_nm(count_ne: Decimal | float | int | str | None) -> float:
    ne = D(count_ne or 0)
    if ne <= 0:
        return 0.0
    return float(money(Decimal("590.5") / ne))


def nm_to_ne(count_nm: Decimal | float | int | str | None) -> float:
    nm = D(count_nm or 0)
    if nm <= 0:
        return 0.0
    return float(money(Decimal("590.5") / nm))


def expected_output_kg(input_kg: Decimal | float | int | str | None,
                       expected_yield_pct: Decimal | float | int | str | None) -> Decimal:
    inp = money(input_kg)
    y = D(expected_yield_pct or 100)
    return money(inp * y / Decimal("100"))


def spindle_efficiency(actual_kg: Decimal | float | int | str | None,
                       spindle_count: int,
                       shift_hours: Decimal | float | int | str | None,
                       std_kg_per_spindle_hour: Decimal | float | int | str | None) -> float:
    if spindle_count <= 0:
        return 0.0
    hours = D(shift_hours or 0)
    std = D(std_kg_per_spindle_hour or 0)
    if hours <= 0 or std <= 0:
        return 0.0
    expected = money(D(spindle_count) * hours * std)
    if expected == ZERO:
        return 0.0
    actual = money(actual_kg)
    return float(money(actual / expected * Decimal("100")))


def cost_per_kg(total_cost: Decimal | float | int | str | None,
                output_kg: Decimal | float | int | str | None) -> Decimal:
    out = money(output_kg)
    if out == ZERO:
        return ZERO
    return money(D(total_cost or 0) / out)


def dispatch_value(net_kg_val: Decimal | float | int | str | None,
                   rate_per_kg: Decimal | float | int | str | None) -> Decimal:
    return money(D(net_kg_val or 0) * D(rate_per_kg or 0))


def rate_per_lb(rate_per_kg: Decimal | float | int | str | None) -> float:
    r = money(rate_per_kg) if rate_per_kg is not None else ZERO
    if r == ZERO:
        return 0.0
    return float(money(r / KG_TO_LB))
