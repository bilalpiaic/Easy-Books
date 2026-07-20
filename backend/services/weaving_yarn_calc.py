"""Weaving / sizing yarn planning calculators (#196).

Pure formulas — separate from ops helpers in weaving_calc.py.
Intermediate % factors use D() (not money()) so 1.5% stays 0.015.
Lbs→Kg uses 1/KG_TO_LB so bags stay consistent with weight_triple.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from services.money import D, ZERO, money
from services.weaving_calc import KG_TO_LB, weight_triple

LB_TO_KG = D("1") / KG_TO_LB


def _waste_factor(visible_waste_pct, invisible_waste_pct) -> Decimal:
    vis = D(visible_waste_pct) / Decimal("100")
    inv = D(invisible_waste_pct) / Decimal("100")
    return D("1") + vis + inv


def _leg_lbs(
    ends_or_picks,
    width_in,
    length_yd,
    crimp_pct,
    waste: Decimal,
    ne,
) -> Decimal:
    n = D(ne)
    if n == ZERO:
        return ZERO
    ends = D(ends_or_picks)
    width = D(width_in)
    length = D(length_yd)
    crimp = D("1") + D(crimp_pct) / Decimal("100")
    return (ends * width * length * crimp * waste) / (Decimal("840") * n)


def calculate_weaving(
    *,
    epi,
    ppi,
    width_in,
    length_yd,
    warp_ne,
    weft_ne,
    warp_crimp_pct=0,
    weft_crimp_pct=0,
    visible_waste_pct=0,
    invisible_waste_pct=0,
) -> dict[str, Any]:
    waste = _waste_factor(visible_waste_pct, invisible_waste_pct)
    warp_lbs = _leg_lbs(epi, width_in, length_yd, warp_crimp_pct, waste, warp_ne)
    weft_lbs = _leg_lbs(ppi, width_in, length_yd, weft_crimp_pct, waste, weft_ne)
    total_lbs = warp_lbs + weft_lbs
    warp_kg = warp_lbs * LB_TO_KG
    weft_kg = weft_lbs * LB_TO_KG
    total_kg = total_lbs * LB_TO_KG
    net_lbs = (total_lbs / waste) if waste != ZERO else ZERO
    return {
        "warp_lbs": float(money(warp_lbs)),
        "weft_lbs": float(money(weft_lbs)),
        "total_lbs": float(money(total_lbs)),
        "warp_kg": float(money(warp_kg)),
        "weft_kg": float(money(weft_kg)),
        "total_kg": float(money(total_kg)),
        "waste_factor": float(waste),
        "net_lbs_before_waste": float(money(net_lbs)),
        "warp_ne": float(D(warp_ne)),
        "weft_ne": float(D(weft_ne)),
        "warp": weight_triple(warp_kg),
        "weft": weight_triple(weft_kg),
        "total": weight_triple(total_kg),
        "net_before_waste": weight_triple(net_lbs * LB_TO_KG),
    }


def calculate_sizing(
    *,
    unsized_kg,
    pickup_pct=0,
    stretch_pct=0,
    visible_waste_pct=0,
    invisible_waste_pct=0,
) -> dict[str, Any]:
    unsized = D(unsized_kg)
    pickup = D("1") + D(pickup_pct) / Decimal("100")
    stretch = D("1") + D(stretch_pct) / Decimal("100")
    waste = _waste_factor(visible_waste_pct, invisible_waste_pct)
    net = unsized * pickup * stretch
    gross = net * waste
    return {
        "unsized_kg": float(money(unsized)),
        "net_before_waste_kg": float(money(net)),
        "gross_kg": float(money(gross)),
        "waste_factor": float(waste),
        "total_kg": float(money(gross)),
        "unsized": weight_triple(unsized),
        "net_before_waste": weight_triple(net),
        "gross": weight_triple(gross),
        "total": weight_triple(gross),
    }


def compare_to_contract(
    calc: dict[str, Any],
    contract: dict[str, Any],
    *,
    threshold: float = 0.10,
) -> dict[str, Any]:
    """Return {ok, warnings[]} comparing calc totals/counts to contract planned snapshot."""
    warnings: list[str] = []
    planned = contract.get("planned_total_yarn_kg")
    calc_total = float(calc.get("total_kg") or 0)

    if planned is not None and D(planned) > ZERO:
        p = float(D(planned))
        if p > 0 and abs(calc_total - p) / p > threshold:
            warnings.append(
                f"Quantity mismatch: calculated {calc_total:.4f} kg vs planned {p:.4f} kg "
                f"(>{threshold * 100:.0f}% deviation)"
            )

    for key, label in (("warp_ne", "warp_count_ne"), ("weft_ne", "weft_count_ne")):
        contract_ne = contract.get(label)
        calc_ne = calc.get(key)
        if contract_ne is not None and D(contract_ne) > ZERO and calc_ne is not None:
            if float(D(contract_ne)) != float(D(calc_ne)):
                warnings.append(
                    f"Count mismatch: calculated {key.replace('_', ' ')} {calc_ne} "
                    f"vs contract {float(D(contract_ne))}"
                )

    return {"ok": len(warnings) == 0, "warnings": warnings}
