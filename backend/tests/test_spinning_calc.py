"""Unit tests for spinning_calc."""
from decimal import Decimal

from services import spinning_calc as calc


def test_weight_triple():
    w = calc.weight_triple(Decimal("100"))
    assert w["kg"] == 100.0
    assert w["lbs"] > 220.0
    assert w["bags"] > 2.0


def test_net_kg():
    assert calc.net_kg(520, 20) == Decimal("500")


def test_stage_yield_pct():
    assert calc.stage_yield_pct(100, 92) == 92.0
    assert calc.stage_yield_pct(0, 50) == 0.0


def test_lot_yield_pct():
    assert calc.lot_yield_pct(1000, 850) == 85.0


def test_cost_per_kg():
    assert calc.cost_per_kg(8500, 100) == Decimal("85")
    assert calc.cost_per_kg(100, 0) == Decimal("0")


def test_ne_nm_conversion():
    ne = 30
    nm = calc.ne_to_nm(ne)
    assert abs(calc.nm_to_ne(nm) - ne) < 0.1
